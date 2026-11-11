"""Shared constants and drawing helpers for the lyric-MV generator."""
import math
import os
import random
import re
from functools import lru_cache

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFont

W, H = 1920, 1080          # output frame size (matches the reference videos)
FPS = 30
WORLD_SCALE = 1.12         # scenes are painted larger than the frame so the camera can push/pan
WW, WH = int(W * WORLD_SCALE), int(H * WORLD_SCALE)

OUTLINE = (43, 34, 51)     # the dark plum ink line used for every outline

HERE = os.path.dirname(os.path.abspath(__file__))
FONT_DIR = os.path.join(HERE, "fonts")
FONTS = {
    "brush": os.path.join(FONT_DIR, "MaShanZheng-Regular.ttf"),   # title lettering
    "hand": os.path.join(FONT_DIR, "LongCang-Regular.ttf"),       # handwritten lyrics
}
_FALLBACKS = [
    "/root/.local/share/fonts/NotoSansCJKsc-VF.otf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]


def _fallback_path():
    for p in _FALLBACKS:
        if os.path.exists(p):
            return p
    return None


@lru_cache(None)
def font(name, size):
    path = FONTS.get(name) or name
    if name == "fallback" or not os.path.exists(path):
        path = _fallback_path()
    return ImageFont.truetype(path, size) if path else ImageFont.load_default()


@lru_cache(None)
def _coverage(name):
    path = FONTS.get(name)
    if name == "fallback" or not path or not os.path.exists(path):
        return None
    try:
        from fontTools.ttLib import TTFont
        return set(TTFont(path, lazy=True).getBestCmap().keys())
    except Exception:
        return None


# characters a font draws in a misleading form (Long Cang draws 时 like the traditional 時)
FONT_OVERRIDES = {"hand": {"时": "brush"}}


def text_runs(text, name):
    """Split text into (font_name, chunk) runs so glyphs missing from `name` use the fallback font."""
    cov = _coverage(name)
    over = FONT_OVERRIDES.get(name, {})
    if cov is None and not over:
        return [(name, text)]
    runs = []
    for ch in text:
        if ch in over:
            f = over[ch]
        else:
            f = name if (cov is None or ord(ch) in cov or ch.isspace()) else "fallback"
        if runs and runs[-1][0] == f:
            runs[-1] = (f, runs[-1][1] + ch)
        else:
            runs.append((f, ch))
    return runs


def text_width(text, name, size):
    w = 0.0
    for f, chunk in text_runs(text, name):
        fs = int(size * 0.82) if f == "fallback" else size
        w += font(f, fs).getlength(chunk)
    return w


def draw_text(draw, x, baseline, text, name, size, fill, stroke_width=0, stroke_fill=None):
    """Draw text left-aligned on a baseline, mixing fonts for missing glyphs."""
    for f, chunk in text_runs(text, name):
        fs = int(size * 0.82) if f == "fallback" else size
        fo = font(f, fs)
        draw.text((x, baseline), chunk, font=fo, fill=fill, anchor="ls",
                  stroke_width=stroke_width, stroke_fill=stroke_fill)
        x += fo.getlength(chunk)
    return x


TOKEN_RE = re.compile(r"[A-Za-z0-9']+|[^\sA-Za-z0-9']")
PUNCT = set(" ，。,.!?！？、；;：:…~～　\"“”'‘’()（）《》「」【】-—·/\\|")


def tokenize(text):
    """Return [(start, end, token)] for CJK characters and latin words, skipping punctuation."""
    return [(m.start(), m.end(), m.group()) for m in TOKEN_RE.finditer(text) if m.group() not in PUNCT]


# ---------------------------------------------------------------- colour helpers
def hexrgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def mix(a, b, t):
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(len(a)))


def darker(c, k=0.8):
    return tuple(int(v * k) for v in c[:3])


def ease(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


# ---------------------------------------------------------------- hand-drawn canvas
def wobble(pts, amp, rng, closed=True, seg=55):
    """Subdivide a polyline and jitter it so edges look hand-inked."""
    if amp <= 0:
        return pts
    out = []
    n = len(pts)
    rng_edges = n if closed else n - 1
    for i in range(rng_edges):
        x0, y0 = pts[i]
        x1, y1 = pts[(i + 1) % n]
        L = math.hypot(x1 - x0, y1 - y0)
        k = max(1, int(L / seg))
        nx, ny = (-(y1 - y0) / L, (x1 - x0) / L) if L else (0, 0)
        for j in range(k):
            t = j / k
            j_amp = rng.gauss(0, amp)
            out.append((x0 + (x1 - x0) * t + nx * j_amp, y0 + (y1 - y0) * t + ny * j_amp))
    if not closed:
        out.append(pts[-1])
    return out


class Canvas:
    """Supersampled drawing surface with wobbly outlined primitives (world coordinates)."""

    def __init__(self, w, h, bg=(0, 0, 0), seed=0, ss=2, rgba=False):
        self.w, self.h, self.ss = w, h, ss
        mode = "RGBA" if rgba else "RGB"
        fill = (0, 0, 0, 0) if rgba else bg
        self.img = Image.new(mode, (w * ss, h * ss), fill)
        self.d = ImageDraw.Draw(self.img, "RGBA")
        self.rng = random.Random(seed)

    def _s(self, pts):
        return [(x * self.ss, y * self.ss) for x, y in pts]

    def poly(self, pts, fill=None, outline=OUTLINE, width=5, wob=1.6):
        p = wobble(self._s(pts), wob * self.ss, self.rng)
        self.d.polygon(p, fill=fill)
        if outline and width:
            self.d.line(p + [p[0]], fill=outline, width=int(width * self.ss), joint="curve")

    def rect(self, x0, y0, x1, y1, **kw):
        self.poly([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], **kw)

    def ellipse(self, cx, cy, rx, ry, fill=None, outline=OUTLINE, width=5, wob=1.0, n=48):
        pts = [(cx + rx * math.cos(2 * math.pi * i / n), cy + ry * math.sin(2 * math.pi * i / n)) for i in range(n)]
        p = self._s(pts)
        if wob:
            p = [(x + self.rng.gauss(0, wob * self.ss * 0.5), y + self.rng.gauss(0, wob * self.ss * 0.5)) for x, y in p]
        self.d.polygon(p, fill=fill)
        if outline and width:
            self.d.line(p + [p[0]], fill=outline, width=int(width * self.ss), joint="curve")

    def line(self, pts, fill=OUTLINE, width=5, wob=1.0):
        p = wobble(self._s(pts), wob * self.ss, self.rng, closed=False)
        self.d.line(p, fill=fill, width=int(width * self.ss), joint="curve")

    def vgrad(self, x0, y0, x1, y1, top, bottom):
        g = vgradient(int((x1 - x0) * self.ss), int((y1 - y0) * self.ss), top, bottom)
        self.img.paste(g, (int(x0 * self.ss), int(y0 * self.ss)))

    def glow(self, cx, cy, r, color, strength=1.0):
        add_glow(self.img, cx * self.ss, cy * self.ss, r * self.ss, color, strength)

    def final(self):
        return self.img.resize((self.w, self.h), Image.LANCZOS)


def vgradient(w, h, top, bottom):
    t = np.linspace(0, 1, max(h, 1))[:, None]
    a = np.array(top, float)[None, :]
    b = np.array(bottom, float)[None, :]
    col = (a + (b - a) * t).astype(np.uint8)            # h x 3
    arr = np.repeat(col[:, None, :], max(w, 1), axis=1)
    return Image.fromarray(arr, "RGB")


@lru_cache(None)
def glow_sprite(r, color, strength_q, falloff=2.2):
    """RGB radial glow on black, for screen blending."""
    r = int(r)
    y, x = np.mgrid[-r:r + 1, -r:r + 1]
    d = np.sqrt(x * x + y * y) / r
    a = np.clip(1 - d, 0, 1) ** falloff * (strength_q / 16.0)
    arr = (a[..., None] * np.array(color, float)[None, None, :]).clip(0, 255).astype(np.uint8)
    return Image.fromarray(arr, "RGB")


def add_glow(img, cx, cy, r, color, strength=1.0):
    """Screen-blend a soft glow onto img (in place)."""
    q = int(round(max(0.0, min(1.6, strength)) * 16))
    if q <= 0:
        return
    g = glow_sprite(int(r), tuple(color), q)
    x0, y0 = int(cx - r), int(cy - r)
    box = (max(0, x0), max(0, y0), min(img.width, x0 + g.width), min(img.height, y0 + g.height))
    if box[2] <= box[0] or box[3] <= box[1]:
        return
    gc = g.crop((box[0] - x0, box[1] - y0, box[2] - x0, box[3] - y0))
    region = img.crop(box)
    if region.mode == "RGBA":
        rgb = ImageChops.screen(region.convert("RGB"), gc)
        rgb.putalpha(region.getchannel("A"))
        img.paste(rgb, box[:2])
    else:
        img.paste(ImageChops.screen(region, gc), box[:2])


def paper_overlay(w, h, seed=7, vignette=0.32, warm=True, tint=None):
    """Multiply layer: paper blotches + fine grain + vignette. Gives the textured, printed-on-paper look."""
    rng = np.random.default_rng(seed)

    def noise(cell):
        small = rng.random((h // cell + 2, w // cell + 2)).astype(np.float32)
        return np.asarray(Image.fromarray((small * 255).astype(np.uint8)).resize((w, h), Image.BICUBIC), np.float32) / 255

    v = 1.0 - 0.07 * noise(90) - 0.04 * noise(14) + 0.018 * rng.standard_normal((h, w)).astype(np.float32)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    dx, dy = (xx - w / 2) / (w / 2), (yy - h / 2) / (h / 2)
    v *= 1 - vignette * np.clip((dx * dx * 0.8 + dy * dy) - 0.25, 0, None) ** 1.2
    tint = np.array(tint or ([1.0, 0.985, 0.955] if warm else [1, 1, 1]), np.float32)
    arr = np.clip(v[..., None] * tint[None, None, :] * 255, 0, 255).astype(np.uint8)
    return Image.fromarray(arr, "RGB")


def heart_points(cx, cy, s, n=40):
    pts = []
    for i in range(n):
        t = 2 * math.pi * i / n
        x = 16 * math.sin(t) ** 3
        y = 13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)
        pts.append((cx + x * s / 16, cy - y * s / 16))
    return pts


def star_points(cx, cy, r_out, r_in, n=4, rot=0.0):
    pts = []
    for i in range(n * 2):
        r = r_out if i % 2 == 0 else r_in
        a = rot + math.pi * i / n - math.pi / 2
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts
