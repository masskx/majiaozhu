# majiaozhu: animated lyric MVs

This repo holds four reference videos and `mvmaker/`, a tool that turns an MP3 into a video in the same style.

```bash
pip install -r mvmaker/requirements.txt          # ffmpeg must also be installed
python3 -m mvmaker.make_mv "input/歌手-歌名.mp3"     # -> output/歌手-歌名.mp4 (+ .lrc with the timed lyrics)
```

---

## 1. How the reference videos are made

| | 11 坏女孩 | 12 失眠 | 13 天龙八部之宿敌 | 14 等你下课 |
|---|---|---|---|---|
| Length | 4:02 | 3:31 | 4:23 | 4:30 |
| Opening card | title in brush lettering, red underline, singer | brush title, gold underline, singer "Suki刘舒妤" | title in a vertical paper strip on the right | title handwritten on an envelope with a pen |
| Look | flat colours, thick outlines, rain/night, purple neon bar | painted, textured, warm "old town" | snowy night lake, moon, stars | pastel paper-craft school town |
| Lyrics | small yellow text, bottom centre | gold text on a dark tag | – | notebook-paper strip with pink tape, **karaoke fill** |

### Technical specs (all four)
* 1920×1080, **30 fps**, H.264 (yuv420p) at about 1.1–1.8 Mbit/s, AAC 44.1 kHz stereo
* Exported for Douyin (the `vid:` tag in the metadata). The encoder string is `Lavf58.76.100`, the ffmpeg build used by 剪映/CapCut exports, so they were probably finished in 剪映.
* Every video has exactly one audio track, the original song, with no voice-over or sound effects.

### Visual language
1. **Characters are simple boxes.** Each one is a rectangle body with four stick legs, two small block arms and a minimal face (dot eyes, `^ ^`, `> <`, a small mouth, pink blush). You tell characters apart by one accessory (a flower, beanie, cap or fringe of hair) and by body colour. This design is cheap to animate, so one person can make a 4-minute story.
2. **Emotion is shown with symbols**: blue tear streams, a rain cloud over the head, floating hearts, music notes, sparkles, "Zzz".
3. **Flat 2D scenes with thick dark-plum outlines** (never pure black). Lines are slightly wobbly so they look hand-inked. Shading uses flat darker bands.
4. **A paper texture and vignette sit over everything**, so frames look like printed illustrations instead of clean vectors.
5. **Each scene has its own palette, and the palette carries the mood:**
   * present-day sadness uses cold night blues, warm lit windows, street lamps and rain
   * memories and happy flashbacks use warm sepia or pastel daylight (the park bench at sunset in 坏女孩, the classroom in 等你下课)
   * nightlife uses purple, with neon heart and cocktail-glass signs
6. **Ambient motion**: rain, snow, falling petals, dust in lamplight, fireflies, flickering neon, twinkling stars.

### Structure and editing
* 0–5 s: an establishing shot with the **title card** (title, underline, singer).
* After that, **a new shot every 1–2 lyric lines** (about 5–10 s). Shots change on the downbeat where a lyric starts, with short crossfades or simple wipes.
* The story is told literally from the lyrics. Lonely now, a flashback to being happy together, back to lonely.
* The videos are **bookended**: the last shot returns to the opening location (the rainy street in 坏女孩, the bedroom with the desk lamp in 失眠), usually with the character alone.
* Animation is **limited** (cut-out style): walk cycles, body bobbing, slow camera push-ins and pans. There is very little frame-by-frame animation.
* Lyrics show one line at a time at the bottom centre. In 等你下课 the text fills in character by character as it is sung (karaoke). 剪映's "识别歌词" (lyric recognition) feature plus a karaoke text animation produces exactly this.

### Probable original workflow
1. Write a small storyboard from the lyrics, choosing scenes and what the character feels.
2. Draw the backgrounds and character parts as layers (Procreate/Photoshop; 失眠's painted textures may also use AI-generated backgrounds).
3. Animate with keyframes in 剪映 or After Effects: move, bob, swap the face, zoom the camera.
4. Run lyric recognition, fix the text, and apply a subtitle template.
5. Export at 1080p30 and upload to Douyin.

---

## 2. The generator (`mvmaker/`)

`make_mv.py` automates the same recipe:

| Step | What the tool does |
|---|---|
| Title / singer | taken from the MP3 tags, otherwise from the file name (`歌手-歌名.mp3`). Override with `--title` / `--artist`. |
| Lyrics + timing | `--lyrics x.lrc` uses its timings directly. `--lyrics x.txt` (plain lines) gets aligned to the vocals automatically. With no lyrics, the song is transcribed with Whisper. A `.lrc` file is always written next to the video so you can fix wrong words and re-run. |
| Mood | `sad` or `sweet` is detected from the lyric words, or set it with `--mood`. It decides which scene set is used. |
| Storyboard | about 6–11 s shots cut on lyric line starts. The opening and closing scenes match, with two warm "flashback" shots in the middle. Each shot gets expressions, symbols (cloud, hearts…), walk-ins, pairs sitting on a bench, and so on. |
| Scenes | rainy city street, quiet night city, bedroom with desk lamp, sunset park bench, snowy moonlit lake, neon bar, pastel school street, rooftop with string lights, classroom. All are drawn in code in the flat, outlined style. |
| Motion | walk cycles, blinking, bobbing to the music's energy, the lead "singing" (mouth follows the vocal loudness), hand-drawn line boil, camera push-in and pan, crossfades, weather particles, flickering lamps and neon. |
| Text | brush-lettered title with an animated underline. Notebook-paper karaoke subtitles (`--style paper`, default) or gold-on-dark tags (`--style banner`). |
| Output | 1920×1080, 30 fps, H.264 (CRF 22, capped near 2.2 Mbit/s, about 60 MB for 4 minutes) plus AAC 192k, faststart MP4, so it is ready to upload to Douyin. |

Useful flags:

```bash
python3 -m mvmaker.make_mv song.mp3 --stills 3,40,90          # save a few PNG frames to check the look first
python3 -m mvmaker.make_mv song.mp3 --start 30 --length 15    # short preview clip
python3 -m mvmaker.make_mv song.mp3 --seed 7                  # different scene order / characters
python3 -m mvmaker.make_mv song.mp3 --lyrics output/song.lrc   # re-render after correcting the lyrics
python3 -m mvmaker.make_mv song.mp3 --mood sweet --style banner
```

A 3.5-minute song takes about 5–10 minutes on 4 CPU cores, plus about 1 minute for transcription.

### Limits compared with the hand-made originals
* Scenes come from a fixed library and are chosen by mood. They don't illustrate each lyric's specific objects (for example 等你下课's letters and bus stop). Feel free to ask for new scenes; each one is a single function in `mvmaker/scenes.py`.
* Whisper usually gets most of the words right but not all. Supplying the lyrics as `.txt` or `.lrc` gives exact text.

Fonts: Ma Shan Zheng and Long Cang (SIL Open Font License, `mvmaker/fonts/OFL.txt`).
