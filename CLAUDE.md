# Project: animated lyric MVs from MP3s

The four videos in `references/` are the style references (README.md section 1 has the breakdown).

## Folder layout
* `songs/<歌手-歌名>/`: one folder per song, every file named `<歌手-歌名>…` (`.mp3`, `.txt`, `.lrc`, `.story.json`,
  `_文案.md`, `.mp4`, `_cover_3x4.jpg`, `_cover_4x3.jpg`). Add a row to `songs/README.md` for every new song.
* `archive/template-mode/`: early videos from the old template mode. Don't add to it; redo those songs into `songs/`
  when asked (the user asked for 戴羽彤-漠河舞厅 and DJ柚仔-把回忆拼好给你 to be redone with lyric-matched visuals).
* `references/`, `mvmaker/` (code), `docs/`.
* `make_mv` takes only the MP3 path. It finds `<name>.lrc` (else `<name>.txt`), `<name>.story.json` and
  `<name>_文案.md` in the same folder and writes the outputs there.
`mvmaker/` turns an MP3 into a video in that style. README.md section 3 and docs/ARCHITECTURE.md describe the code.

## The user's standing requirements (apply to every MP3 they send)

0. **Visuals must match the lyrics, in the style of the four reference videos.** Never use the template mode
   (random scenes from mood pools) for a delivery. Always write a storyboard `songs/<name>/<name>.story.json` where every
   shot illustrates its lyric line(s): the place, what the characters do, the effects. **Code only**: everything is
   drawn by `mvmaker`. Do not call AI image/video generation services or APIs (the user said so explicitly).
1. **Style: melancholy** by default: a sentimental, evening, "posted late at night" feel (`--mood auto` resolves to `melancholy` unless the song is clearly a happy love song).
   When the user asks for another look for a song, follow it. "Cute and sweet" (可爱/甜) means
   `"mood": "sweet"` in the storyboard:
   * pastel palettes (`time: "pastel"` / `"pastel_night"`, `autumn` streets, `autumn_park`);
   * candy subtitles, a pink title and lifted shadows;
   * cute effects (`heart_break`, `dream`, hearts, sparkles).
   Example: `songs/牙牙乐格子兮-秋殇别恋/牙牙乐格子兮-秋殇别恋.story.json`, a sad song told cutely.
2. **Covers**: a 3:4 portrait (1080×1440) and a 4:3 landscape (1440×1080). `make_mv` produces both automatically.
3. **Title + 文案 in Chinese**: write `songs/<name>/<name>_文案.md` (format below) **before** rendering, so its 封面短句 is printed on the covers.
4. Keep README.md and docs/ARCHITECTURE.md accurate whenever the code changes.

## When the user uploads / mentions an MP3, do this

1. **Find the file.** It may be attached to the chat (uploaded files), committed to the repo, or given as a URL. Create `songs/<歌手-歌名>/` and copy it in as `songs/<歌手-歌名>/<歌手-歌名>.mp3` (take the names from the MP3 tags: `ffprobe -show_entries format_tags`).
2. **Install dependencies** if needed (fresh containers don't have them). ffmpeg is preinstalled.
   ```bash
   pip install -q -r mvmaker/requirements.txt
   ```
3. **Lyrics.**
   * If the user gave lyrics, save them as `songs/<name>/<name>.txt` (or `.lrc`).
   * If you know the song's lyrics well, write them yourself to `songs/<name>/<name>.txt`, one sung line per line in singing order, including repeated choruses. Alignment is much better than raw transcription.
   * Otherwise let Whisper transcribe.
   * The singer is the performer, not the uploader account (the references are by the account 蔡蔡 but credit e.g. Suki刘舒妤).
4. **Preview** (about 1 minute; the Whisper model downloads about 1.6 GB on first use):
   ```bash
   python3 -m mvmaker.make_mv "songs/<name>/<name>.mp3" --stills 3,30,60,90,120
   ```
   Look at the PNGs and read `songs/<name>/<name>.lrc` (once it exists, it is used instead of the .txt). Fix misheard words in the .lrc (if unsure, keep what was heard and tell the user which lines are uncertain). If the transcription found almost no lines, check the log for the no-VAD retry.
5. **Write the storyboard `songs/<name>/<name>.story.json`** (format: docstring of `mvmaker/story.py`; examples:
   `songs/洋澜一-伤心太平洋/洋澜一-伤心太平洋.story.json`, `songs/解忧邵帅-你是人间四月天/解忧邵帅-你是人间四月天.story.json`). Get the line indexes from the .lrc (0-based, in order). Rules of thumb:
   * one shot per 1–2 lyric lines (≈3–8 s); instrumental passages get `"from": seconds` shots (≤ 12 s each);
   * read each line for its literal images (sea, island, boat, rain, crowd, bed, clock, heart…) and its feeling.
     Pick the set and the act that show it: a lone character on an island for 「一个岛锁住一个人」, the partner
     walking away and fading for a goodbye, sinking underwater for 「沉入海」, memory photos rising for 「往事浮上来」;
   * repeated choruses reuse their imagery with a different camera, time of day or expression (like the references);
   * keep characters above the subtitle strip: feet/seat y ≤ ~990 on sets whose ground is lower;
   * the hero is the singer's "I"; the partner (pink, flower) is "you". Use `back: true` for looking away or waiting;
   * if a line needs a place, prop or effect that doesn't exist, add it in code (`sets.py`, `fx.py`, `story.py`) in
     the same flat, outlined, paper-textured style, and document it in README/ARCHITECTURE;
   * set `"cover"` to the shot index that best sums up the song.
   Check stills of many shots (`--stills` with one time per shot) and fix framing before the full render.
6. **Write `songs/<name>/<name>_文案.md`** in Chinese, melancholy/evening tone, in this format:
   ```markdown
   # 歌名 · 歌手 发布文案

   - **发布标题**：(one strong post title, ≤ 20 characters, evocative, not clickbait)
   - **备选标题**：
     - (2–3 alternatives; a striking lyric line is a good option)
   - **封面短句**：第一句/第二句   (≤ 2 short lines, `/` = line break, each ≤ 12 characters; printed on both covers)

   ## 文案

   (120–250 characters of the post text: a small story or feeling that grows out of the song's theme, short lines, quiet and sincere, may quote one lyric, end with a gentle 晚安-style closing)

   ## 话题

   #歌名 #歌手 #深夜emo #伤感音乐 #歌词动画 #晚安
   ```
   Don't invent factual claims about real people. Stay with feelings, or with a song's well-known story.
7. **Render the full video + covers** (about 5 min for a 4-min song). Run it in the background and wait for the notification:
   ```bash
   python3 -m mvmaker.make_mv "songs/<name>/<name>.mp3"
   ```
   Covers only (e.g. after editing the 封面短句): add `--covers-only`.
8. **Check.** Run `ffprobe` (1920x1080, 30 fps, duration equal to the song). Look at a contact sheet (`ffmpeg -vf "fps=1/7,scale=320:-1,tile=6x6"`) and at both covers.
9. **Deliver.**
   * Send the MP4 and both cover JPGs with SendUserFile.
   * Show the 发布标题, 备选标题 and 文案 in the reply, ready to copy.
   * Commit the whole `songs/<name>/` folder (stills are git-ignored) plus the new row in `songs/README.md`, and push.
   * Tell the user the mood and seed used, any uncertain lyric lines, and how to ask for changes (another seed, `--mood sad`, `--style banner`, corrected lyrics, a different cover line).

## Code map
* `mvmaker/make_mv.py` CLI: name guessing, mood guessing, reads 封面短句, writes the .lrc, covers, encode
* `mvmaker/lyrics.py` LRC parsing, Whisper transcription (with VAD fallback), aligning plain-text lyrics to the transcription
* `mvmaker/story.py` storyboard mode: shots from `songs/<name>/<name>.story.json`, extended character acts (walk away, sit, boat, float, sink, umbrella, fade, back view), crowds
* `mvmaker/sets.py` storyboard scenery (beach, pier, island, underwater, storm sea, cliff, lighthouse, mountains, meadow, snow_town, kitchen, autumn_park, station + the scenes library) in dusk/night/storm/day/pastel/pastel_night palettes
* `mvmaker/fx.py` animated lyric effects (tide, footprints, sand heart, boat, seagulls, lighthouse beam, lightning, rays, bubbles, seaweed, sinking heart, breaking heart, thought bubble, rising photos, messages, calendar, clock, steam, sunlight, summer-to-autumn, train, wind, portrait, ripples, aurora, fireworks, shooting star)
* `mvmaker/scenes.py` background library (one function per scene; `POOLS` = scenes per mood, used only in template mode)
* `mvmaker/character.py` box characters (expressions, accessories, walk cycle) as cached sprites
* `mvmaker/render.py` storyboard planning, camera, particles, emotes, title card, karaoke subtitles, parallel encode
* `mvmaker/cover.py` 3:4 and 4:3 covers
* `mvmaker/common.py` drawing toolkit (hand-inked canvas, glows, paper texture, fonts)

Rendering is stateless per frame (everything is a function of time), so frames render in a multiprocessing pool and are piped into ffmpeg.
