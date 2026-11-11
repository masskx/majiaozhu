"""The box-shaped cartoon characters (an original design in the flat 'paper cut-out' style)."""
import math
import zlib
from functools import lru_cache

from PIL import Image, ImageChops

from .common import OUTLINE, Canvas, darker, hexrgb, mix

BODY_W, BODY_H, LEG_H = 240, 165, 46

# expression names
EXPRESSIONS = ("neutral", "happy", "sad", "cry", "sleepy", "love", "surprised", "back")

MOUTH_DARK = (92, 35, 52)
TONGUE = (232, 120, 130)
BLUSH = (255, 125, 150, 105)
TEAR = (125, 195, 245, 230)


class Look:
    """Visual identity of one character."""

    def __init__(self, color="#e08a52", accessory=None, acc_color=None):
        self.color = hexrgb(color) if isinstance(color, str) else tuple(color)
        self.accessory = accessory
        self.acc_color = hexrgb(acc_color) if isinstance(acc_color, str) else acc_color

    def key(self):
        return (self.color, self.accessory, self.acc_color)


def _arm(c, bx, by, side, angle, s, color, lw):
    """Little rectangular arm. side=-1 left, +1 right; angle in degrees above horizontal."""
    L, T = 56 * s, 21 * s
    a = math.radians(angle)
    dx, dy = side * math.cos(a), -math.sin(a)
    nx, ny = -dy, dx
    x0, y0 = bx - dx * 14 * s, by - dy * 14 * s
    x1, y1 = bx + dx * L, by + dy * L
    pts = [(x0 + nx * T / 2, y0 + ny * T / 2), (x1 + nx * T / 2, y1 + ny * T / 2),
           (x1 - nx * T / 2, y1 - ny * T / 2), (x0 - nx * T / 2, y0 - ny * T / 2)]
    c.poly(pts, fill=color, width=lw * 0.85, wob=0.6 * s)


def _eyes(c, expr, blink, ex, ey, s, lw):
    r = 8.5 * s
    for i, x in enumerate(ex):
        side = -1 if i == 0 else 1
        if expr in ("happy", "love"):
            c.line([(x - 12 * s, ey + 5 * s), (x, ey - 7 * s), (x + 12 * s, ey + 5 * s)], width=lw, wob=0.3)
        elif expr == "cry":
            # squeezed > <
            d = side
            c.line([(x - d * 11 * s, ey - 9 * s), (x + d * 8 * s, ey), (x - d * 11 * s, ey + 9 * s)], width=lw, wob=0.3)
        elif expr == "sleepy" or blink:
            c.line([(x - 12 * s, ey + 1 * s), (x, ey + 4 * s), (x + 12 * s, ey + 1 * s)], width=lw, wob=0.3)
        else:
            rr = r * (1.35 if expr == "surprised" else 1.0)
            c.ellipse(x, ey, rr, rr * 1.12, fill=OUTLINE, outline=None, wob=0.2)
            c.ellipse(x - rr * 0.3, ey - rr * 0.35, rr * 0.32, rr * 0.32, fill=(255, 255, 255), outline=None, wob=0)
        if expr == "sad":
            # worried brows, inner ends raised
            inner = 1 if i == 0 else -1
            c.line([(x - inner * 13 * s, ey - 13 * s), (x + inner * 9 * s, ey - 21 * s)], width=lw * 0.8, wob=0.3)


def _mouth(c, expr, level, mx, my, s, lw):
    def half_open(w, h, sad=False):
        if sad:   # flat bottom, arched top: a wailing mouth
            pts = [(mx - w, my + h * 0.8)]
            for k in range(1, 12):
                a = math.pi * k / 12
                pts.append((mx - w * math.cos(a), my + h * 0.8 - h * math.sin(a)))
            pts.append((mx + w, my + h * 0.8))
            c.poly(pts, fill=MOUTH_DARK, width=lw * 0.8, wob=0.3)
            c.ellipse(mx, my + h * 0.62, w * 0.5, h * 0.2, fill=TONGUE, outline=None, wob=0)
            return
        pts = [(mx - w, my - h * 0.15)]
        for k in range(1, 12):
            a = math.pi * k / 12
            pts.append((mx - w * math.cos(a), my - h * 0.15 + h * math.sin(a)))
        pts.append((mx + w, my - h * 0.15))
        c.poly(pts, fill=MOUTH_DARK, width=lw * 0.8, wob=0.3)
        c.ellipse(mx, my + h * 0.55, w * 0.55, h * 0.28, fill=TONGUE, outline=None, wob=0)

    def oval(w, h):
        c.ellipse(mx, my + 2 * s, w, h, fill=MOUTH_DARK, outline=OUTLINE, width=lw * 0.7, wob=0.3)

    def arc(w, h, up=True):
        pts = []
        for k in range(13):
            a = math.pi * k / 12
            pts.append((mx + w * math.cos(a), my + (h * math.sin(a) if up else -h * math.sin(a) + h)))
        c.line(pts, width=lw, wob=0.2)

    if expr == "cry":
        half_open(17 * s + level * 3 * s, 16 * s + level * 4 * s, sad=True)
    elif expr in ("happy", "love"):
        if level == 0 and expr == "love":
            arc(14 * s, 8 * s)
        else:
            half_open((15 + level * 3) * s, (13 + level * 5) * s)
    elif expr == "surprised":
        oval(9 * s, 11 * s)
    elif level >= 1:
        oval((6 + level * 2) * s, (6 + level * 3.5) * s)
    elif expr == "sad":
        arc(12 * s, 6 * s, up=False)
    elif expr == "sleepy":
        oval(5 * s, 5 * s)
    else:
        arc(13 * s, 7 * s)


def _accessory(c, look, x0, y0, x1, s, lw):
    acc, bw = look.accessory, x1 - x0
    col = look.acc_color
    if acc == "flower":
        cx, cy = x0 + bw * 0.22, y0 - 4 * s
        for k in range(6):
            a = 2 * math.pi * k / 6
            c.ellipse(cx + 12 * s * math.cos(a), cy + 12 * s * math.sin(a), 9 * s, 9 * s,
                      fill=(255, 252, 240), width=lw * 0.55, wob=0.2)
        c.ellipse(cx, cy, 8 * s, 8 * s, fill=(245, 190, 60), width=lw * 0.55, wob=0.2)
    elif acc == "beanie":
        col = col or (63, 143, 134)
        cx, top = (x0 + x1) / 2, y0 - 62 * s
        pts = [(x0 + 6 * s, y0 + 22 * s)]
        for k in range(1, 16):
            a = math.pi * k / 16
            pts.append((cx - (bw / 2 - 6 * s) * math.cos(a), y0 + 10 * s - (y0 + 10 * s - top) * math.sin(a)))
        pts.append((x1 - 6 * s, y0 + 22 * s))
        c.poly(pts, fill=col, width=lw, wob=0.8 * s)
        c.rect(x0 - 2 * s, y0 + 4 * s, x1 + 2 * s, y0 + 30 * s, fill=mix(col, (255, 255, 255), 0.18), width=lw, wob=0.6 * s)
        c.ellipse(cx, top - 4 * s, 18 * s, 17 * s, fill=(250, 246, 236), width=lw * 0.8, wob=0.3)
    elif acc == "cap":
        col = col or (238, 178, 52)
        cx, top = x0 + bw * 0.42, y0 - 48 * s
        pts = [(x0 + 4 * s, y0 + 14 * s)]
        for k in range(1, 14):
            a = math.pi * k / 14
            pts.append((cx - (bw * 0.42 - 4 * s) * math.cos(a), y0 + 10 * s - (y0 + 10 * s - top) * math.sin(a)))
        pts.append((x0 + bw * 0.84, y0 + 14 * s))
        c.poly(pts, fill=col, width=lw, wob=0.6 * s)
        c.poly([(x0 + bw * 0.62, y0 + 2 * s), (x1 + 52 * s, y0 + 6 * s), (x1 + 48 * s, y0 + 20 * s), (x0 + bw * 0.6, y0 + 16 * s)],
               fill=darker(col, 0.9), width=lw, wob=0.5 * s)
    elif acc == "hair":
        col = col or (55, 42, 64)
        pts = [(x0 - 4 * s, y0 - 10 * s), (x1 + 4 * s, y0 - 12 * s), (x1 + 4 * s, y0 + 26 * s)]
        n = 7
        for k in range(1, n):
            fx = 1 - k / n
            pts.append((x0 + bw * fx + 10 * s, y0 + (36 if k % 2 else 18) * s))
        pts.append((x0 - 4 * s, y0 + 34 * s))
        c.poly(pts, fill=col, width=lw, wob=0.8 * s)
    elif acc == "bow":
        col = col or (238, 110, 140)
        cx, cy = x0 + bw * 0.78, y0 - 6 * s
        c.poly([(cx, cy), (cx - 30 * s, cy - 18 * s), (cx - 30 * s, cy + 16 * s)], fill=col, width=lw * 0.8, wob=0.3)
        c.poly([(cx, cy), (cx + 30 * s, cy - 18 * s), (cx + 30 * s, cy + 16 * s)], fill=col, width=lw * 0.8, wob=0.3)
        c.ellipse(cx, cy, 9 * s, 9 * s, fill=darker(col, 0.85), width=lw * 0.8, wob=0.2)


@lru_cache(maxsize=320)
def sprite(look_key, expr="neutral", blink=False, mouth=0, legs=0, arms=0, boil=0, scale_q=20, tint=(255, 255, 255)):
    """Render one pose. Returns (RGBA image, (anchor_x, anchor_y)) where the anchor is the feet centre.

    legs: 0 stand, 1/2 walk cycle, 3 sitting (legs hidden)
    arms: 0 down, 1 both up, 2 right arm waving
    """
    color, accessory, acc_color = look_key
    look = Look(color, accessory, acc_color)
    s = scale_q / 20.0
    bw, bh, lh = BODY_W * s, BODY_H * s, LEG_H * s
    pad, top = 100 * s, 110 * s
    cw, ch = int(bw + 2 * pad), int(top + bh + lh + 26 * s)
    c = Canvas(cw, ch, seed=boil * 7919 + zlib.crc32(repr(look_key).encode()) % 1000, rgba=True)
    x0, y0 = pad, top
    x1, y1 = x0 + bw, y0 + bh
    lw = max(3.0, 5.5 * s)
    feet = y1 + lh

    # soft contact shadow
    if legs != 3:
        c.ellipse((x0 + x1) / 2, feet - 2 * s, bw * 0.56, 11 * s, fill=(0, 0, 0, 55), outline=None, wob=0)

    if legs != 3:
        for i, fx in enumerate((0.15, 0.37, 0.63, 0.85)):
            lift, dx = 0.0, 0.0
            if legs in (1, 2):
                swing = (i % 2 == 0) == (legs == 1)
                lift = 10 * s if swing else 0
                dx = 7 * s if swing else -3 * s
            lx = x0 + bw * fx + dx
            c.rect(lx - 10 * s, y1 - 8 * s, lx + 10 * s, feet - lift, fill=darker(look.color, 0.86), width=lw * 0.8, wob=0.4 * s)

    arm_y = y0 + bh * 0.58
    left_a, right_a = -38, -38
    if arms == 1:
        left_a = right_a = 42
    elif arms == 2:
        right_a = 55
    _arm(c, x0, arm_y, -1, left_a, s, look.color, lw)
    _arm(c, x1, arm_y, +1, right_a, s, look.color, lw)

    # body + watercolour-ish shading
    c.poly([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], fill=look.color, width=lw, wob=1.3 * s)
    c.poly([(x0 + lw, y1 - bh * 0.24), (x1 - lw, y1 - bh * 0.28), (x1 - lw, y1 - lw), (x0 + lw, y1 - lw)],
           fill=mix(look.color, darker(look.color, 0.8), 0.45), outline=None, wob=2.5 * s)
    c.poly([(x0 + bw * 0.08, y0 + bh * 0.1), (x0 + bw * 0.45, y0 + bh * 0.08), (x0 + bw * 0.3, y0 + bh * 0.3), (x0 + bw * 0.07, y0 + bh * 0.34)],
           fill=mix(look.color, (255, 255, 255), 0.16), outline=None, wob=3 * s)

    ex = (x0 + bw * 0.34, x0 + bw * 0.66)
    ey = y0 + bh * 0.44
    if expr in ("happy", "love", "neutral", "surprised", "cry"):
        c.ellipse(x0 + bw * 0.2, ey + 22 * s, 15 * s, 8 * s, fill=BLUSH, outline=None, wob=0)
        c.ellipse(x0 + bw * 0.8, ey + 22 * s, 15 * s, 8 * s, fill=BLUSH, outline=None, wob=0)
    if expr == "cry":
        for x in ex:
            c.poly([(x - 7 * s, ey + 8 * s), (x + 7 * s, ey + 8 * s), (x + 8 * s, y1 - 3 * s), (x - 8 * s, y1 - 3 * s)],
                   fill=TEAR, outline=None, wob=0.6 * s)
    if expr != "back":   # back view: no face, a quiet silhouette looking away
        _eyes(c, expr, blink, ex, ey, s, lw)
        _mouth(c, expr, mouth, x0 + bw * 0.5, y0 + bh * 0.64, s, lw)
    if look.accessory:
        _accessory(c, look, x0, y0, x1, s, lw)

    img = c.final()
    if tint != (255, 255, 255):
        rgb = ImageChops.multiply(img.convert("RGB"), Image.new("RGB", img.size, tint))
        rgb.putalpha(img.getchannel("A"))
        img = rgb
    return img, (cw / 2.0, feet)
