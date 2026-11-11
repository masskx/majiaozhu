#!/usr/bin/env python3
"""Turn an MP3 into an animated lyric music video (1920x1080, 30fps, H.264 + AAC).

Examples
Each song lives in its own folder, songs/<歌手-歌名>/, next to everything made for it:
  <name>.mp3  <name>.txt / <name>.lrc  <name>.story.json  <name>_文案.md   (inputs)
  <name>.mp4  <name>_cover_3x4.jpg  <name>_cover_4x3.jpg  <name>.lrc       (outputs)

  python3 -m mvmaker.make_mv songs/<name>/<name>.mp3                      # finds lyrics/storyboard/文案 itself
  python3 -m mvmaker.make_mv songs/<name>/<name>.mp3 --stills 3,40,90     # quick look at a few frames
  python3 -m mvmaker.make_mv songs/<name>/<name>.mp3 --start 30 --length 15   # short preview clip
  python3 -m mvmaker.make_mv song.mp3 --title 失眠 --artist Suki刘舒妤 --lyrics song.lrc
"""
import argparse
import json
import os
import re
import subprocess
import sys

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    __package__ = "mvmaker"

from mvmaker.lyrics import get_lines, write_lrc  # noqa: E402
from mvmaker.render import Project, encode  # noqa: E402

SAD_WORDS = "泪哭痛伤失眠离开分手孤单寂寞遗憾再见心碎回不去难过想念错过后悔冷雨夜醉放手等不到"
SWEET_WORDS = "甜笑喜欢心动拥抱牵手阳光开心幸福温柔一起永远宝贝可爱美好浪漫"


def probe(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration:format_tags", "-of", "json", path],
                         capture_output=True, text=True, check=True).stdout
    fmt = json.loads(out)["format"]
    tags = {k.lower(): v for k, v in (fmt.get("tags") or {}).items()}
    return float(fmt["duration"]), tags


def guess_names(path, tags):
    title, artist = tags.get("title", "").strip(), tags.get("artist", "").strip()
    stem = os.path.splitext(os.path.basename(path))[0]
    stem = re.sub(r"^\s*\d+[\s._-]*", "", stem)                 # leading track number
    stem = re.sub(r"[（(\[【].*?[)）\]】]", "", stem).strip()      # (Live), [伴奏] ...
    parts = [p.strip() for p in re.split(r"\s*[-–—_]\s*", stem) if p.strip()]
    if not title:
        title = parts[-1] if parts else stem
    if not artist and len(parts) >= 2:
        artist = parts[0] if parts[-1] == title else parts[-1]
    return title, artist


def guess_mood(lines):
    """Default is the quiet evening 'melancholy' look; only clearly happy love songs switch to 'sweet'."""
    text = "".join(l.text for l in lines)
    sad = sum(text.count(c) for c in SAD_WORDS)
    sweet = sum(text.count(c) for c in SWEET_WORDS)
    return "sweet" if sweet > max(4, sad * 2) else "melancholy"


def read_copy(path):
    """Pull the cover line (封面短句) out of a <name>_文案.md written for the song."""
    if not path or not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        for line in f:
            m = re.match(r"^\s*[-*]?\s*\**封面短句\**\s*[:：]\s*(.+?)\s*$", line)
            if m:
                return m.group(1).strip("「」\"' ")
    return None


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("audio", help="input .mp3 (or any audio ffmpeg can read)")
    ap.add_argument("-o", "--output", help="output .mp4 (default: <name>.mp4 next to the audio, i.e. in the song folder)")
    ap.add_argument("--title", help="song title shown on the title card (default: from tags/filename)")
    ap.add_argument("--artist", help="singer shown under the title (default: from tags/filename)")
    ap.add_argument("--lyrics", help=".lrc (timed) or .txt (one line per lyric line; timing found automatically). "
                    "Default: <name>.lrc, else <name>.txt, next to the audio")
    ap.add_argument("--no-asr", action="store_true", help="never run speech recognition")
    ap.add_argument("--no-lyrics", action="store_true", help="no subtitles at all")
    ap.add_argument("--asr-model", default="large-v3-turbo", help="faster-whisper model (small is faster, less accurate)")
    ap.add_argument("--mood", choices=["auto", "melancholy", "sad", "sweet"], default="auto",
                    help="scene set: melancholy (default, quiet evening), sad (rain/tears), sweet")
    ap.add_argument("--style", choices=["auto", "paper", "banner", "candy"], default="auto",
                    help="lyric subtitle look (auto: candy for sweet, paper otherwise)")
    ap.add_argument("--seed", type=int, default=None, help="change for a different scene order / characters")
    ap.add_argument("--start", type=float, default=0.0, help="render from this second (preview)")
    ap.add_argument("--length", type=float, default=None, help="render only this many seconds (preview)")
    ap.add_argument("--stills", help="comma separated seconds: save PNG frames instead of a video")
    ap.add_argument("--story", help="storyboard JSON (default: <name>.story.json next to the audio)")
    ap.add_argument("--tagline", help="short line for the covers; '/' = line break (default: 封面短句 in <name>_文案.md)")
    ap.add_argument("--covers-only", action="store_true", help="only make the 3:4 and 4:3 covers")
    ap.add_argument("--no-covers", action="store_true")
    ap.add_argument("--workers", type=int, default=None)
    ap.add_argument("--crf", type=int, default=22, help="x264 quality (lower = better/bigger)")
    a = ap.parse_args(argv)

    duration, tags = probe(a.audio)
    title, artist = guess_names(a.audio, tags)
    title, artist = a.title or title, a.artist if a.artist is not None else artist
    stem = os.path.splitext(os.path.basename(a.audio))[0]
    song_dir = os.path.dirname(os.path.abspath(a.audio))
    out = a.output or os.path.join(song_dir, stem + ".mp4")
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    if not a.lyrics and not a.no_lyrics:   # corrected .lrc first, then plain-text lyrics, else transcription
        for ext in (".lrc", ".txt"):
            cand = os.path.join(song_dir, stem + ext)
            if os.path.exists(cand):
                a.lyrics = cand
                print(f"> lyrics: {cand}", file=sys.stderr)
                break

    if a.no_lyrics:
        lines, meta, src = [], {}, "none"
    else:
        lines, meta, src = get_lines(a.audio, a.lyrics, use_asr=not a.no_asr, model=a.asr_model, duration=duration)
    title = a.title or meta.get("ti") or title
    artist = a.artist if a.artist is not None else (meta.get("ar") or artist)
    mood = guess_mood(lines) if a.mood == "auto" else a.mood
    seed = a.seed if a.seed is not None else sum(map(ord, title)) % 1000

    print(f"> {title} / {artist or '-'}  {duration:.1f}s  lyrics: {len(lines)} lines ({src})  mood: {mood}  seed: {seed}", file=sys.stderr)
    if lines and src != "lrc":
        lrc = os.path.splitext(out)[0] + ".lrc"
        write_lrc(lines, lrc, title, artist)
        print(f"> wrote the timed lyrics to {lrc} - fix any wrong words there and re-run with --lyrics {lrc}", file=sys.stderr)

    story = None
    story_path = a.story or os.path.join(song_dir, stem + ".story.json")
    if os.path.exists(story_path):
        from mvmaker.story import load
        story = load(story_path)
        print(f"> storyboard: {story_path} ({len(story['shots'])} shots)", file=sys.stderr)
    elif a.story:
        sys.exit(f"storyboard not found: {a.story}")
    else:
        print("! no storyboard found: using template scenes (write songs/<name>/<name>.story.json for lyric-matched shots)", file=sys.stderr)
    if story and story.get("mood"):
        mood = story["mood"]   # the storyboard can set the look of the whole video (e.g. "sweet")
        print(f"> mood from storyboard: {mood}", file=sys.stderr)
    style = a.style if a.style != "auto" else ("candy" if mood == "sweet" else "paper")
    proj = Project(a.audio, duration, lines, title, artist, mood=mood, style=style, seed=seed, story=story)
    proj.describe()
    base = os.path.splitext(out)[0]
    tagline = a.tagline or read_copy(base + "_文案.md")
    if a.covers_only or not a.no_covers:
        from mvmaker.cover import make_covers
        make_covers(proj, base, tagline)
        if a.covers_only:
            return
    if a.stills:
        for s in a.stills.split(","):
            f = int(float(s) * 30)
            p = f"{base}_{float(s):06.1f}s.png"
            proj.render(f).save(p)
            print(f"> {p}", file=sys.stderr)
        return
    encode(proj, out, start=a.start, length=a.length, workers=a.workers, crf=a.crf)


if __name__ == "__main__":
    main()
