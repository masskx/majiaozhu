# Project: animated lyric MVs from MP3s

The four `*.mp4` files in the repo root are the style references (see README.md section 1 for the breakdown).
`mvmaker/` turns an MP3 into a video in that style.

## When the user uploads / mentions an MP3, do this

1. **Find the file.** It may be attached to the chat (uploaded files), committed to the repo (often `input/`), or given as a URL. Copy it into `input/` if it isn't there.
2. **Install dependencies** if needed (fresh containers don't have them). ffmpeg is preinstalled.
   ```bash
   pip install -q -r mvmaker/requirements.txt
   ```
3. **Settle the title, singer and lyrics.**
   * Title and singer come from tags or the file name (`歌手-歌名.mp3`). If they look wrong, pass `--title`/`--artist`. The singer is the performer, not the uploader account (the references are by the account 蔡蔡 but credit the singer, e.g. Suki刘舒妤).
   * If the user gave lyrics, save them as `input/<name>.txt` or `.lrc` and pass `--lyrics`. Otherwise Whisper transcribes the vocals.
4. **Preview the look first** (takes about 1 minute; Whisper's large-v3-turbo model downloads about 1.6 GB on first use):
   ```bash
   python3 -m mvmaker.make_mv "input/<name>.mp3" --stills 3,30,60,90,120
   ```
   Look at the PNGs in `output/` and read the generated `output/<name>.lrc`. Fix obviously misheard lyric words in the .lrc (you know the lyrics of many songs; if unsure, keep what Whisper heard). Then render with `--lyrics output/<name>.lrc`.
5. **Render the full video** (about 5–10 min for a 4-min song). Run it in the background and wait for the notification:
   ```bash
   python3 -m mvmaker.make_mv "input/<name>.mp3" --lyrics "output/<name>.lrc"
   ```
6. **Check it.** Use `ffprobe` (1920x1080, 30 fps, duration equal to the song) and pull a few frames to look at.
7. **Deliver.** Send `output/<name>.mp4` to the user with SendUserFile. Commit `input/<name>.mp3`, `output/<name>.mp4` and `output/<name>.lrc` to the session's branch and push. Tell the user what title, singer, mood and seed were used, and how to ask for changes (different seed/scenes, `--mood`, `--style banner`, corrected lyrics).

## Code map
* `mvmaker/make_mv.py` CLI: name guessing, mood guessing, writes the .lrc
* `mvmaker/lyrics.py` LRC parsing, Whisper transcription, aligning plain-text lyrics to the transcription
* `mvmaker/scenes.py` background library (one function per scene, `POOLS` = which scenes are used for each mood)
* `mvmaker/character.py` box characters (expressions, accessories, walk cycle) as cached sprites
* `mvmaker/render.py` storyboard planning, camera, particles, emotes, title card, karaoke subtitles, parallel encode

Rendering is stateless per frame (everything is a function of time), so frames render in a multiprocessing pool and are piped into ffmpeg.
