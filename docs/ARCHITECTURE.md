# mvmaker internals

The README has the overview and the module map. This file explains the rules inside each stage and how to extend them.

## 1. Pipeline

```
MP3 ─┬─ ffprobe ───────────── duration, title/artist tags
     ├─ lyrics.get_lines ──── [Line(text, start, end, tokens=[(char_a, char_b, t0, t1)…])]
     ├─ audio_features ────── energy[f], pulse[f]  (per video frame, 30 fps)
     └─ Project
          ├─ plan() ───────── [Shot(start, end, Scene, [Actor…], camera, framing)]
          ├─ TitleCard, Subtitles, Particles, paper overlay (+ mood grade)
          ├─ make_covers() ── *_cover_3x4.jpg, *_cover_4x3.jpg
          └─ encode() ─────── Pool.imap(render, frames) → ffmpeg stdin → MP4
```

## 2. Lyrics (`lyrics.py`)

Three sources, best first:

1. **`.lrc`**: timestamps are used as-is. A line ends at the next line's start, capped at about 0.42 s per character + 1.2 s. Credit lines (作词：… etc.) are dropped.
2. **`.txt` + transcription**: Whisper produces a stream of `(token, start, end, break_after)`, where a token is one CJK character or one latin word. `align_text` runs a global Needleman-Wunsch alignment (`global_align`, match +3, mismatch/gap −1) between your lyric tokens and the transcribed tokens. difflib's longest-block-first matching was replaced because it could pin verse 1 onto the audio of verse 2 when verses repeat. Then:
   * matched tokens take the transcribed times;
   * unmatched runs are spread evenly between their matched neighbours;
   * a run that would span an instrumental gap sticks to the side its own line is on;
   * a token that lands more than 2.5 s from its neighbour in the same line is a false match and is pulled back next to it.
3. **Transcription only**: `lines_from_stream` cuts lines at punctuation, at pauses over 0.9 s, and at 14 characters (splitting at the largest pause near the middle). 1–2 character fragments are glued to the next line (usually a pickup syllable), otherwise to the previous one.

Transcription details: faster-whisper `large-v3-turbo` with int8 on the CPU, `language="zh"`, and a prompt that says these are Mandarin song lyrics. The first pass uses the voice-activity filter. If it finds fewer than 25 tokens per minute, or its tokens span less than 60% of the song (DJ remixes, live recordings with band and applause), it re-runs without the filter. Known hallucinations ("字幕由…", "优优独播剧场…", "Zither Harp" on instrumental intros) are filtered, and traditional characters are converted to simplified with OpenCC.

## 3a. Storyboard mode (`story.py`, `sets.py`, `fx.py`): what deliveries use

* **Shots**: shot *i* starts 0.35 s before its first lyric line (`lines[k].start - 0.35`), or at `"from"` seconds for instrumentals, and ends where the next shot starts. Shot 0 starts at 0 (the title card plays over it).
* **Sets** (`sets.build(name, time, seed)`): every set is painted once per run. Sea sets share `sky()` and `sea()`, which take a palette per time of day (`PALETTES`), and expose `horizon`, `shore`, `floor`, `lamp` for the effects. Library scenes from `scenes.py` are available under the same names.
* **Actors** (`story.SActor`):
  * position, scale and alpha are interpolated over the shot (`t0`..`t1` fraction);
  * acts change legs, arms, rotation and bob (boat rocks ±6°, float/sink sway ±9° with bubbles, dance sways and alternates arms);
  * `back` draws the faceless back view; `umbrella` draws a scalloped umbrella (`umbrella_dx` shifts it over someone else);
  * `look` overrides colour/accessory per shot (white `hair` = old age); `scarf` and `phone` draw props on the body;
  * `hull` sizes the boat (0 = sitting in someone else's boat); `z` lifts a character above others;
  * crowds are generated grey walkers in two depth rows;
  * named characters are drawn after the crowd.
* **Effects** (`fx.draw`): names in `fx.BACK` are drawn behind the characters, the rest in front.
  * Effects are stateless functions of `t` / `lt`. For example, the tide erases footprints and the sand heart once the highest water line so far has passed them (`_max_edge`).
  * Lightning is periodic (bolt + screen flash).
* **Foreground**: a set's `fg` layer (bench seat, desks) is drawn over characters; with `fg_y` it only covers those standing behind that line, so people walking in front of a bench pass in front of it.
* **Looks**: the storyboard's `"mood"` switches the whole video. `sweet` gives pastel grade + shadow lift (screen with (34, 20, 30)), `TITLE_THEMES["sweet"]`, `candy` subtitles and sweet covers.
* **Camera** tuples are `(z0, z1, cx0, cx1, cy0[, cy1])`. `pull` starts at 1.3× on the first named character and opens to the full scene; `close` frames the character's face.
* **Covers** use the storyboard's `"cover"` shot.
* **Adding vocabulary**:
  * a new place is a painter in `sets.py` registered in `SETS`;
  * a new effect is `fx_<name>(img, p, ctx)` in `fx.py` (add the name to `BACK` if it belongs behind the characters);
  * a new act is a branch in `story.draw_actor`.

## 3b. Template mode (`render.plan`): fallback without a storyboard

* **Cuts**: a cut can fall at a lyric start (0.35 s early) once the shot is ≥ 6.5 s long, randomly before 10 s and always after. Stretches without lyrics longer than 11 s are split evenly. A final shot shorter than 5 s merges into the previous one.
* **Scene sequence** from `scenes.POOLS[mood] = (openings, middles, flashbacks)`:
  * shot 0 is an opening scene; for melancholy that is always `dusk_stop`;
  * the last shot is the opening scene again, or for melancholy `bedroom` / `city_night` ("dusk into night");
  * flashback shots (22% of shots, 15% for melancholy) are spread across the middle;
  * other shots pick the least-used middle scene that isn't one of the last two.
* **Actors**:
  * Pairs (lead + partner) appear on benches, in flashbacks and in sweet scenes.
  * Solo shots are framed as close-up (30%, larger sprite, camera centred on the face), wide (15%, small sprite walking across), walk-in, or standing.
  * The closing shot is always solo.
* **Expressions** come from `choose_expr(scene mood, flashback, song mood)`. Melancholy keeps faces mostly `sad`/`neutral`, with occasional `cry` and few emotes. Flashbacks are `happy`/`love` with hearts and notes.
* **Camera**: a slow zoom pair (1.0↔1.1) with a small pan. Close-ups use 1.12–1.2 centred on the lead.

## 4. Rendering (`render.Project`)

* `render_world(shot, t, f)` draws the world layer:
  * glow strength = base × flicker(kind, t) + 0.25 × pulse[f];
  * characters bob with `pulse` (beat) and walk with two leg poses at 5 Hz;
  * they blink every 3.7 s;
  * the lead's mouth opens in three levels from `energy` while a lyric is active;
  * the line-boil variant (wobble seed) changes every 5 frames.
* `camera()` does a single `Image.resize(box=…)` crop and scale, then screen-space particles.
* `render(f)` adds the crossfade (0.6 s, centred on the cut), the paper/vignette/grade multiply, the title card, subtitles and the fades.
* **Caching**:
  * scene backgrounds are painted once per run at 2× and downsampled;
  * `character.sprite` is an LRU cache of 320 poses;
  * subtitle strips are built once per line (dim layer + ink layer; the karaoke fill crops the ink layer at the current token boundary).
* **Parallelism**: the `Project` is built in the parent and inherited by `fork`ed workers (copy-on-write). `Pool.imap(chunksize=4)` keeps frames in order for ffmpeg. About 13 frames/s on 4 cores.
* **Encoding**: `libx264 -crf 22 -maxrate R -bufsize 2R -tune animation -pix_fmt yuv420p`, AAC 192k at 44.1 kHz, `-movflags +faststart`. R is 2200k, or lower for long songs: `(85 MB × 8 / duration − 200 kbit/s audio)`, with a floor of 900k. This keeps every file under GitHub's 100 MB limit (6.5 min → about 1540k).

## 5. Covers (`cover.py`)

1. Pick the scene: `dusk_stop` for melancholy, otherwise the opening scene. Render its world without characters, then extend the ground 360 px downward (a mirrored copy of the bottom band) so a tall crop can sit the character higher.
2. Crop to the aspect ratio. In 3:4 the lead is centred with the ground at 66% height. In 4:3 the lead sits at 70% across and the text goes on the left.
3. Draw the lead sprite at cover resolution (sharp, not upscaled) with a `sad` face for melancholy/sad songs.
4. Apply the paper overlay and grade, then darken the top (3:4) or left (4:3) so the text reads.
5. Add the brush title with shadow and gold underline, the singer, and the tagline on 1–3 paper strips (split on `/`, or at a comma near the middle of long lines).

## 6. Extending

**New scene**: add a function in `scenes.py` that paints on a `Canvas(WW, WH)` and returns a `Scene`:

```python
def my_scene(seed):
    rng = random.Random(seed)
    c = Canvas(WW, WH, seed=seed)
    c.vgrad(0, 0, WW, 900, C("#1b2240"), C("#2d3765"))      # sky / wall
    c.rect(-20, 930, WW + 20, WH + 20, fill=C("#262c4a"))   # ground
    ...
    return Scene("my_scene", c.final(), ground=1005, slots=[930, 1250, 1100], mood="lonely",
                 particles="snow", tint=(200, 200, 235), glows=[(x, y, r, (255, 200, 120), 0.8, "lamp")])
```

Register it in `BUILDERS` and add it to a list in `POOLS`.
* `slots` = [pair left, pair right, solo];
* `tint` = multiply colour for the characters (match the scene's lighting);
* glow kinds: `lamp`, `neon`, `neon2`, `twinkleN`, `breath`;
* particles: `rain`, `snow`, `petals`, `leaves`, `dust`, `fireflies`;
* `fg` = an RGBA layer drawn over the characters;
* `seated` = seat height, which makes characters sit.

**New character look**: add `(body colour, accessory, accessory colour)` to `HEROES` / `PARTNERS` in `render.py`. Accessories are `cap`, `beanie`, `hair`, `flower`, `bow`; new ones go in `character._accessory`.

**New mood**: add a `POOLS` entry, a branch in `choose_expr`, optionally a grade in `Project.__init__`, and the choice in `make_mv.py`.

**New subtitle style**: add a branch in `Subtitles._build` that draws `base` (background), `dim` (unsung text) and `ink` (sung text).
