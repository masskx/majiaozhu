# Project: animated lyric MVs from MP3s

The four `*.mp4` files in the repo root are the style references (README.md section 1 has the breakdown).
`mvmaker/` turns an MP3 into a video in that style. README.md section 3 and docs/ARCHITECTURE.md describe the code.

## The user's standing requirements (apply to every MP3 they send)

1. **Style: melancholy.** A sentimental, evening, "posted late at night" feel. This is the default mood (`--mood auto` resolves to `melancholy` unless the song is clearly a happy love song). Don't switch to `sweet` unless the user asks.
2. **Covers**: a 3:4 portrait (1080×1440) and a 4:3 landscape (1440×1080). `make_mv` produces both automatically.
3. **Title + 文案 in Chinese**: write `output/<name>_文案.md` (format below) **before** rendering, so its 封面短句 is printed on the covers.
4. Keep README.md and docs/ARCHITECTURE.md accurate whenever the code changes.

## When the user uploads / mentions an MP3, do this

1. **Find the file.** It may be attached to the chat (uploaded files), committed to the repo (often `input/`), or given as a URL. Copy it into `input/` as `<歌手-歌名>.mp3` (take the names from the MP3 tags: `ffprobe -show_entries format_tags`).
2. **Install dependencies** if needed (fresh containers don't have them). ffmpeg is preinstalled.
   ```bash
   pip install -q -r mvmaker/requirements.txt
   ```
3. **Lyrics.**
   * If the user gave lyrics, save them as `input/<name>.txt` (or `.lrc`).
   * If you know the song's lyrics well, write them yourself to `input/<name>.txt`, one sung line per line in singing order, including repeated choruses. Alignment is much better than raw transcription.
   * Otherwise let Whisper transcribe.
   * The singer is the performer, not the uploader account (the references are by the account 蔡蔡 but credit e.g. Suki刘舒妤).
4. **Preview** (about 1 minute; the Whisper model downloads about 1.6 GB on first use):
   ```bash
   python3 -m mvmaker.make_mv "input/<name>.mp3" --lyrics "input/<name>.txt" --stills 3,30,60,90,120
   ```
   Look at the PNGs and read `output/<name>.lrc`. Fix misheard words in the .lrc (if unsure, keep what was heard and tell the user which lines are uncertain). If the transcription found almost no lines, check the log for the no-VAD retry.
5. **Write `output/<name>_文案.md`** in Chinese, melancholy/evening tone, in this format:
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
6. **Render the full video + covers** (about 5 min for a 4-min song). Run it in the background and wait for the notification:
   ```bash
   python3 -m mvmaker.make_mv "input/<name>.mp3" --lyrics "output/<name>.lrc"
   ```
   Covers only (e.g. after editing the 封面短句): add `--covers-only`.
7. **Check.** Run `ffprobe` (1920x1080, 30 fps, duration equal to the song). Look at a contact sheet (`ffmpeg -vf "fps=1/7,scale=320:-1,tile=6x6"`) and at both covers.
8. **Deliver.**
   * Send the MP4 and both cover JPGs with SendUserFile.
   * Show the 发布标题, 备选标题 and 文案 in the reply, ready to copy.
   * Commit `input/<name>.*` and `output/<name>*` (`.mp4`, `.lrc`, `_cover_3x4.jpg`, `_cover_4x3.jpg`, `_文案.md`) and push.
   * Tell the user the mood and seed used, any uncertain lyric lines, and how to ask for changes (another seed, `--mood sad`, `--style banner`, corrected lyrics, a different cover line).

## Code map
* `mvmaker/make_mv.py` CLI: name guessing, mood guessing, reads 封面短句, writes the .lrc, covers, encode
* `mvmaker/lyrics.py` LRC parsing, Whisper transcription (with VAD fallback), aligning plain-text lyrics to the transcription
* `mvmaker/scenes.py` background library (one function per scene; `POOLS` = scenes per mood)
* `mvmaker/character.py` box characters (expressions, accessories, walk cycle) as cached sprites
* `mvmaker/render.py` storyboard planning, camera, particles, emotes, title card, karaoke subtitles, parallel encode
* `mvmaker/cover.py` 3:4 and 4:3 covers
* `mvmaker/common.py` drawing toolkit (hand-inked canvas, glows, paper texture, fonts)

Rendering is stateless per frame (everything is a function of time), so frames render in a multiprocessing pool and are piped into ffmpeg.
