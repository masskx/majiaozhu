"""Video covers: 3:4 portrait (1080x1440) and 4:3 landscape (1440x1080).

A cover = the opening scene re-framed for the aspect ratio + the lead character drawn sharply at cover size
+ the brush-lettered title, singer, and a short emotional line on notebook-paper strips.
"""
import math
import re
import sys

import numpy as np

from PIL import Image, ImageChops, ImageDraw, ImageFilter

from .character import sprite
from .common import OUTLINE, WH, WW, draw_text, paper_overlay, text_width
from .lyrics import Line
from .render import Shot, Subtitles

SIZES = {"3x4": (1080, 1440), "4x3": (1440, 1080)}


def split_tagline(text, max_chars=13):
    """Explicit breaks with '/' or newlines; otherwise split long lines at a comma or space near the middle."""
    parts = [p.strip() for p in re.split(r"[/\n]", text or "") if p.strip()]
    out = []
    for p in parts:
        while len(p) > max_chars:
            seps = [m.start() for m in re.finditer(r"[，,。 、！？!?]", p) if 0 < m.start() < len(p) - 1]
            if seps:
                k = min(seps, key=lambda i: abs(i - len(p) // 2))
                out.append(p[:k].strip())
                p = p[k + 1:].strip()
            else:
                k = len(p) // 2
                out.append(p[:k])
                p = p[k:]
        out.append(p.rstrip("，,"))
    return out


def _title_layer(size_wh, title, artist, x, y, size, align="center", max_w=None):
    """Brush title + gold underline + singer, with a soft shadow. (x, y) = title baseline anchor."""
    W, H = size_wh
    while max_w and size > 70 and text_width(title, "brush", size) > max_w:
        size -= 6
    tw = text_width(title, "brush", size)
    x0 = x - tw / 2 if align == "center" else x
    layer = Image.new("RGBA", size_wh, (0, 0, 0, 0))
    sh = Image.new("RGBA", size_wh, (0, 0, 0, 0))
    draw_text(ImageDraw.Draw(sh), x0 + 8, y + 9, title, "brush", size, (15, 10, 25, 150), stroke_width=12, stroke_fill=(15, 10, 25, 150))
    layer.alpha_composite(sh.filter(ImageFilter.GaussianBlur(7)))
    d = ImageDraw.Draw(layer)
    draw_text(d, x0, y, title, "brush", size, (249, 241, 222), stroke_width=max(6, size // 22), stroke_fill=OUTLINE)
    # brush underline
    uw, uy = tw + 40, y + size * 0.16
    top = [(x0 - 20 + i, uy - 6 * math.sin(i / uw * math.pi)) for i in range(0, int(uw), 8)]
    bot = [(px, py + 4 + 9 * math.sin(min(1, (px - x0 + 20) / uw * 1.3) * math.pi)) for px, py in top]
    d.polygon(top + bot[::-1], fill=(226, 178, 58), outline=OUTLINE)
    if artist:
        asz = max(40, int(size * 0.32))
        aw = text_width(artist, "brush", asz)
        ax = x0 + tw / 2 - aw / 2 if align == "center" else x0 + 4
        draw_text(d, ax, uy + asz * 1.35, artist, "brush", asz, (240, 196, 92), stroke_width=4, stroke_fill=OUTLINE)
        return layer, uy + asz * 1.35
    return layer, uy + 20


def _strip(text, seed, max_w):
    subs = Subtitles([Line(text, 0, 1)], "paper", seed)
    base, _dim, ink, _marks = subs._build(0)
    comp = base.copy()
    comp.alpha_composite(ink)
    if comp.width > max_w:
        comp = comp.resize((int(max_w), int(comp.height * max_w / comp.width)), Image.LANCZOS)
    return comp


def make_cover(proj, kind, out_path, tagline=None):
    OW, OH = SIZES[kind]
    portrait = OH > OW
    if getattr(proj, "cover_shot", None) is not None:   # storyboard picks the cover shot
        shot0 = proj.shots[proj.cover_shot]
        sc = shot0.scene
    else:
        shot0 = proj.shots[0]
        sc = next((s.scene for s in proj.shots if s.scene.name == "dusk_stop"), shot0.scene) \
            if proj.mood == "melancholy" else shot0.scene
    world = proj.render_world(Shot(0, 10, sc, [], shot0.cam), 3.0, 90, actors=False)

    # extend the ground downward (stretching the bottom rows) so a tall crop can sit the character higher
    EXT = 360
    tall = Image.new("RGB", (WW, WH + EXT))
    tall.paste(world, (0, 0))
    tall.paste(world.crop((0, WH - 30, WW, WH)).resize((WW, EXT + 10)), (0, WH - 10))
    world, WHX = tall, WH + EXT
    fg_src = None
    if sc.fg is not None:
        fg_src = Image.new("RGBA", (WW, WHX), (0, 0, 0, 0))
        fg_src.paste(sc.fg, (0, 0))

    # frame the world for this aspect ratio
    ar = OW / OH
    ch = WH * 0.95
    cw = ch * ar
    if cw > WW:
        cw, ch = WW, WW / ar
    hero_x = sc.slots[2]
    fx = 0.5 if portrait else 0.7
    x0 = min(max(hero_x - fx * cw, 0), WW - cw)
    y0 = min(max(sc.ground - (0.66 if portrait else 0.84) * ch, 0), WHX - ch)
    box = (x0, y0, x0 + cw, y0 + ch)
    img = world.resize((OW, OH), Image.LANCZOS, box=box)
    k = OW / cw

    # lead character, drawn at cover resolution so it stays crisp
    leads = [x for x in shot0.actors if getattr(x, "who", "hero") == "hero"] or shot0.actors
    look = leads[0].look if leads else None
    if look:
        body_px = OW * (0.30 if portrait else 0.19)
        q = max(10, int(round(body_px / 240 * 20 / 1)))
        expr = "sad" if proj.mood in ("melancholy", "sad") else "happy"
        sp, (ax, ay) = sprite(look.key(), expr, False, 0, 0, 0, 0, q, sc.tint)
        fx_px, fy_px = (hero_x - x0) * k, (sc.ground - y0) * k
        img.paste(sp, (int(fx_px - ax), int(fy_px - ay)), sp)
    if fg_src is not None:
        fg = fg_src.resize((OW, OH), Image.LANCZOS, box=box)
        img.paste(fg, (0, 0), fg)

    img = ImageChops.multiply(img, paper_overlay(OW, OH, proj.seed, vignette=0.42, tint=proj.grade))

    # darken behind the text so it always reads
    if portrait:   # darker towards the top
        ramp = np.clip(np.linspace(1, 0, int(OH * 0.45)), 0, 1)[:, None] * np.ones((1, OW))
        full = np.zeros((OH, OW)); full[:ramp.shape[0]] = ramp
    else:          # darker towards the left
        ramp = np.clip(np.linspace(1, 0, int(OW * 0.58)), 0, 1)[None, :] * np.ones((OH, 1))
        full = np.zeros((OH, OW)); full[:, :ramp.shape[1]] = ramp
    shade = Image.fromarray((full ** 1.3 * 165).astype(np.uint8), "L")
    img = Image.composite(Image.new("RGB", (OW, OH), (12, 10, 28)), img, shade)

    img = img.convert("RGBA")
    title = proj.title_text
    if portrait:
        layer, bottom = _title_layer((OW, OH), title, proj.artist, OW / 2, OH * 0.2, 190, max_w=OW * 0.86)
    else:
        layer, bottom = _title_layer((OW, OH), title, proj.artist, OW * 0.08, OH * 0.3, 170, align="left", max_w=OW * 0.5)
    img.alpha_composite(layer)

    lines = split_tagline(tagline, 12 if portrait else 11)[:3]
    if lines:
        strips = [_strip(t, proj.seed + i, OW * (0.9 if portrait else 0.5)) for i, t in enumerate(lines)]
        total = sum(s.height for s in strips) - 78 * (len(strips) - 1)
        y = (OH - total - 40) if portrait else max(bottom + 30, OH * 0.56)
        for i, s in enumerate(strips):
            s = s.rotate((-1.2, 1.0, -0.6)[i % 3], resample=Image.BICUBIC, expand=True)
            if portrait:
                x = OW / 2 - s.width / 2 + (-18, 22, -8)[i % 3]
            else:
                x = OW * 0.08 - 34 + (0, 26, 8)[i % 3]
            img.alpha_composite(s, (int(x), int(y)))
            y += s.height - 78
    img.convert("RGB").save(out_path, quality=93)
    print(f"> cover {kind} ({OW}x{OH}) -> {out_path}", file=sys.stderr)
    return out_path


def make_covers(proj, out_base, tagline=None):
    return [make_cover(proj, k, f"{out_base}_cover_{k}.jpg", tagline) for k in SIZES]
