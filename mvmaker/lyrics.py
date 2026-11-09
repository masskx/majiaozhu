"""Getting timed lyric lines: from an .lrc file, from plain text aligned to the audio, or by transcription."""
import difflib
import os
import re
import subprocess
import sys

import numpy as np

from .common import PUNCT, tokenize

# things whisper likes to invent on music-only passages
HALLUCINATIONS = ("字幕", "订阅", "點贊", "点赞", "谢谢观看", "感谢观看", "請不吝", "请不吝", "Amara", "明镜", "栏目",
                  "以下是普通话", "独播剧场", "YoYo", "Television", "Exclusive")
CREDIT_RE = re.compile(r"^(作词|作曲|编曲|演唱|歌手|制作|制作人|混音|母带|和声|吉他|贝斯|鼓|词|曲|监制|出品|OP|SP)\s*[:：]", re.I)


class Line:
    """One subtitle line. tokens = [(char_start, char_end, t_start, t_end)] for karaoke filling."""

    def __init__(self, text, start, end, tokens=None):
        self.text = text.strip()
        self.start = float(start)
        self.end = float(end)
        if tokens is None:
            spans = tokenize(self.text)
            n = max(1, len(spans))
            d = (self.end - self.start) / n
            tokens = [(a, b, self.start + i * d, self.start + (i + 1) * d) for i, (a, b, _) in enumerate(spans)]
        self.tokens = tokens

    def __repr__(self):
        return f"Line({self.start:.2f}-{self.end:.2f} {self.text!r})"


# ---------------------------------------------------------------- audio
def load_audio(path, sr=16000):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-f", "f32le", "-ac", "1", "-ar", str(sr), "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).copy()


# ---------------------------------------------------------------- LRC / text
LRC_TIME = re.compile(r"\[(\d+):(\d+(?:\.\d+)?)\]")
LRC_META = re.compile(r"^\[(ti|ar|al|by|offset):(.*)\]\s*$", re.I)


def parse_lrc(path, duration=None):
    meta, stamped = {}, []
    with open(path, encoding="utf-8-sig", errors="replace") as f:
        for raw in f:
            raw = raw.strip()
            m = LRC_META.match(raw)
            if m:
                meta[m.group(1).lower()] = m.group(2).strip()
                continue
            times = [int(a) * 60 + float(b) for a, b in LRC_TIME.findall(raw)]
            text = re.sub(r"<\d+:\d+(?:\.\d+)?>", "", LRC_TIME.sub("", raw)).strip()
            for t in times:
                stamped.append((t, text))
    offset = float(meta.get("offset", 0) or 0) / 1000.0
    stamped.sort()
    lines = []
    for i, (t, text) in enumerate(stamped):
        if not text or CREDIT_RE.match(text):
            continue  # blank spacer or credits line such as 作词：xxx
        nxt = stamped[i + 1][0] if i + 1 < len(stamped) else (duration or t + 6)
        n = max(1, len(tokenize(text)))
        end = min(nxt - 0.05, t + max(2.0, 0.42 * n + 1.2))
        lines.append(Line(text, t - offset, max(end - offset, t - offset + 0.6)))
    return lines, meta


def parse_text(path):
    out = []
    with open(path, encoding="utf-8-sig", errors="replace") as f:
        for raw in f:
            t = LRC_TIME.sub("", raw).strip()
            if not t or CREDIT_RE.match(t):
                continue
            out.append(t)
    return out


def write_lrc(lines, path, title="", artist=""):
    def ts(t):
        t = max(0.0, t)
        return "[%02d:%05.2f]" % (int(t // 60), t % 60)
    with open(path, "w", encoding="utf-8") as f:
        if title:
            f.write(f"[ti:{title}]\n")
        if artist:
            f.write(f"[ar:{artist}]\n")
        for ln in lines:
            f.write(f"{ts(ln.start)}{ln.text}\n")


# ---------------------------------------------------------------- transcription
def transcribe(audio, model_name="large-v3-turbo", hint_text=""):
    """Return a stream of (token, t_start, t_end, is_break_after)."""
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        print("! faster-whisper not installed (pip install faster-whisper) - continuing without lyrics", file=sys.stderr)
        return []
    print(f"> transcribing vocals with whisper '{model_name}' (first run downloads the model)...", file=sys.stderr)
    model = WhisperModel(model_name, device="cpu", compute_type="int8", cpu_threads=os.cpu_count() or 4)
    prompt = "以下是普通话歌曲的歌词。" + (hint_text[:120] if hint_text else "")
    stream = _run(model, audio, prompt, vad=True)
    minutes = len(audio) / 16000 / 60
    if len(stream) < 25 * minutes:
        # heavy beats (DJ remixes etc.) make the voice-activity filter drop the vocals: retry without it
        print("> few words found; retrying without the voice-activity filter...", file=sys.stderr)
        alt = _run(model, audio, prompt, vad=False)
        if len(alt) > len(stream):
            stream = alt
    return stream


def _run(model, audio, prompt, vad):
    length = len(audio) / 16000
    segs, _info = model.transcribe(audio, language="zh", vad_filter=vad, word_timestamps=True,
                                   initial_prompt=prompt, condition_on_previous_text=False)
    stream = []
    for seg in segs:
        if any(h in seg.text for h in HALLUCINATIONS) or seg.start >= length - 0.5:
            continue
        for w in seg.words or []:
            word = to_simplified(w.word)
            toks = tokenize(word)
            if not toks:
                if stream:
                    stream[-1] = stream[-1][:3] + (True,)
                continue
            d = (w.end - w.start) / len(toks)
            for i, (_a, _b, tok) in enumerate(toks):
                stream.append((tok, w.start + i * d, w.start + (i + 1) * d, False))
            if word.rstrip() and word.rstrip()[-1] in PUNCT:
                stream[-1] = stream[-1][:3] + (True,)
        if stream:
            stream[-1] = stream[-1][:3] + (True,)
    return stream


def to_simplified(text):
    try:
        import opencc
        return opencc.OpenCC("t2s").convert(text)
    except Exception:
        return text


def _join(tokens):
    out = ""
    for t in tokens:
        if out and re.match(r"[A-Za-z0-9']", t) and re.match(r".*[A-Za-z0-9']$", out):
            out += " "
        out += t
    return out


def lines_from_stream(stream, max_len=14, gap=0.9):
    """Group transcribed tokens into subtitle lines."""
    groups, cur = [], []
    for i, item in enumerate(stream):
        if cur and item[1] - cur[-1][2] > gap:
            groups.append(cur)
            cur = []
        cur.append(item)
        if item[3]:
            groups.append(cur)
            cur = []
    if cur:
        groups.append(cur)
    # glue 1-2 character fragments onto the neighbouring line
    # (usually a pickup syllable of the next line, so prefer gluing forward)
    merged, carry = [], []
    for i, g in enumerate(groups):
        g = carry + g
        carry = []
        nxt = groups[i + 1] if i + 1 < len(groups) else None
        if len(g) <= 2 and nxt and nxt[0][1] - g[-1][2] < 4.0 and len(g) + len(nxt) <= max_len + 2:
            carry = g
        elif len(g) <= 2 and merged and g[0][1] - merged[-1][-1][2] < 4.0:
            merged[-1] = merged[-1] + g
        else:
            merged.append(g)
    groups = merged
    final = []
    for g in groups:
        while len(g) > max_len:
            # split at the biggest pause near the middle
            mid = len(g) // 2
            cands = range(max(2, mid - 4), min(len(g) - 2, mid + 4))
            k = max(cands, key=lambda j: g[j][1] - g[j - 1][2]) if cands else mid
            final.append(g[:k])
            g = g[k:]
        final.append(g)
    lines = []
    for g in final:
        text = _join([t[0] for t in g])
        spans = tokenize(text)
        if len(spans) != len(g):
            lines.append(Line(text, g[0][1], g[-1][2]))
            continue
        toks = [(a, b, it[1], it[2]) for (a, b, _), it in zip(spans, g)]
        lines.append(Line(text, g[0][1], g[-1][2], toks))
    return lines


def align_text(texts, stream):
    """Give each user-supplied lyric line times by matching its characters against the transcription."""
    lyr = []  # (line_idx, span_a, span_b, token)
    for li, t in enumerate(texts):
        for a, b, tok in tokenize(t):
            lyr.append((li, a, b, tok.lower()))
    if not lyr:
        return []
    asr = [s[0].lower() for s in stream]
    times = [None] * len(lyr)
    sm = difflib.SequenceMatcher(None, [x[3] for x in lyr], asr, autojunk=False)
    matched = 0
    for a, b, size in sm.get_matching_blocks():
        for k in range(size):
            times[a + k] = (stream[b + k][1], stream[b + k][2])
            matched += 1
    ratio = matched / len(lyr)
    print(f"> lyric alignment: matched {matched}/{len(lyr)} characters ({ratio:.0%})", file=sys.stderr)
    if matched == 0:
        return None
    # fill unmatched runs
    per = 0.38
    i = 0
    while i < len(lyr):
        if times[i] is not None:
            i += 1
            continue
        j = i
        while j < len(lyr) and times[j] is None:
            j += 1
        n = j - i
        prev_end = times[i - 1][1] if i > 0 else None
        next_start = times[j][0] if j < len(lyr) else None
        if prev_end is None:
            start = next_start - n * per - 0.1
        elif next_start is None:
            start = prev_end + 0.1
        else:
            span = next_start - prev_end
            if span <= n * per * 2.2:
                d = span / (n + 1)
                for k in range(n):
                    times[i + k] = (prev_end + d * (k + 0.5), prev_end + d * (k + 1.4))
                i = j
                continue
            # long gap (instrumental): stick the run to the side belonging to the same line
            same_prev = lyr[i - 1][0] == lyr[i][0]
            start = prev_end + 0.1 if same_prev else next_start - n * per - 0.1
        for k in range(n):
            times[i + k] = (start + k * per, start + (k + 1) * per)
        i = j
    lines = []
    for li, t in enumerate(texts):
        idx = [k for k, x in enumerate(lyr) if x[0] == li]
        if not idx:
            continue
        toks = [(lyr[k][1], lyr[k][2], times[k][0], times[k][1]) for k in idx]
        # a character matched far away from its neighbours is a false match: pull it back
        for k in range(1, len(toks)):
            if toks[k][2] - toks[k - 1][3] > 2.5:
                s0 = toks[k - 1][3] + 0.05
                toks[k] = (toks[k][0], toks[k][1], s0, s0 + per)
        lines.append(Line(t, toks[0][2], toks[-1][3], toks))
    # keep lines monotonic and non-overlapping
    for a, b in zip(lines, lines[1:]):
        if b.start < a.start:
            b.start = a.start + 0.2
        a.end = min(a.end, b.start - 0.05)
        if a.end <= a.start:
            a.end = a.start + 0.5
    return lines


def get_lines(audio_path, lyrics_path=None, use_asr=True, model="large-v3-turbo", duration=None):
    """Main entry. Returns (lines, meta, source_description)."""
    if lyrics_path and lyrics_path.lower().endswith(".lrc"):
        lines, meta = parse_lrc(lyrics_path, duration)
        if len(lines) >= 3:
            return lines, meta, "lrc"
    texts = parse_text(lyrics_path) if lyrics_path else []
    if not use_asr:
        if texts:
            print("! plain-text lyrics without timing and --no-asr: spreading lines evenly", file=sys.stderr)
            dur = duration or 180
            t0, t1 = min(15.0, dur * 0.1), dur - 8
            d = (t1 - t0) / len(texts)
            return [Line(t, t0 + i * d, t0 + (i + 0.92) * d) for i, t in enumerate(texts)], {}, "even"
        return [], {}, "none"
    audio = load_audio(audio_path)
    stream = transcribe(audio, model, hint_text="，".join(texts[:6]) if texts else "")
    if texts and stream:
        lines = align_text(texts, stream)
        if lines:
            return lines, {}, "text+asr"
    if not stream:
        return [], {}, "none"
    return lines_from_stream(stream), {}, "asr"
