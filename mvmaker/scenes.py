"""Procedurally painted backgrounds in a flat, hand-inked 2D style.

Every scene is painted once (supersampled) at world size WW x WH. Things that move each frame
(glows that pulse, twinkling stars, weather) are described as data and drawn by the renderer.
"""
import math
import random

from PIL import Image

from .common import OUTLINE, WH, WW, Canvas, darker, heart_points, hexrgb, mix

C = hexrgb


class Scene:
    def __init__(self, name, bg, ground, slots, mood, particles=None, fg=None, tint=(255, 255, 255),
                 glows=(), stars=(), char_scale=20, seated=None, light=(255, 255, 255)):
        self.name = name
        self.bg = bg                  # RGB world image
        self.fg = fg                  # optional RGBA layer drawn over the characters
        self.ground = ground          # y of characters' feet
        self.slots = slots            # good x positions for characters
        self.mood = mood
        self.particles = particles    # rain | snow | petals | leaves | dust | fireflies | None
        self.tint = tint              # multiply colour applied to characters so they sit in the lighting
        self.glows = list(glows)      # (x, y, r, color, base_strength, flicker_kind)
        self.stars = list(stars)      # (x, y, size) twinkling points
        self.char_scale = char_scale
        self.seated = seated          # y of a seat (characters sit) or None
        self.light = light


# ---------------------------------------------------------------- painting helpers
def windows_grid(c, rng, x0, y0, x1, y1, cols, rows, lit_p, lit=(244, 199, 106), dark=(30, 37, 71),
                 frame=OUTLINE, ww=None, wh=None, bars=True, glow=None, curtain_p=0.25):
    lit_list = []
    cw, rh = (x1 - x0) / cols, (y1 - y0) / rows
    ww = ww or cw * 0.55
    wh = wh or rh * 0.62
    for i in range(cols):
        for j in range(rows):
            cx, cy = x0 + cw * (i + 0.5), y0 + rh * (j + 0.5)
            on = rng.random() < lit_p
            col = lit if on else dark
            c.rect(cx - ww / 2, cy - wh / 2, cx + ww / 2, cy + wh / 2, fill=col, width=4, wob=0.8)
            if on and rng.random() < curtain_p:
                c.poly([(cx - ww / 2 + 4, cy - wh / 2 + 4), (cx - ww / 2 + ww * 0.3, cy - wh / 2 + 4),
                        (cx - ww / 2 + ww * 0.18, cy + wh / 2 - 4), (cx - ww / 2 + 4, cy + wh / 2 - 4)],
                       fill=(214, 140, 160), outline=None, wob=0.5)
            if bars:
                c.line([(cx, cy - wh / 2), (cx, cy + wh / 2)], fill=frame, width=3, wob=0.3)
                c.line([(cx - ww / 2, cy - wh * 0.1), (cx + ww / 2, cy - wh * 0.1)], fill=frame, width=3, wob=0.3)
            if on:
                lit_list.append((cx, cy, ww, wh))
                if glow:
                    c.glow(cx, cy, max(ww, wh) * 1.1, glow, 0.35)
    return lit_list


def skyline(c, rng, base, hmin, hmax, color, win_color=None, win_p=0.12, outline=None):
    x = -30
    while x < WW + 30:
        w = rng.uniform(110, 260)
        h = rng.uniform(hmin, hmax)
        c.rect(x, base - h, x + w, base + 5, fill=color, outline=outline, width=3, wob=0.6)
        if win_color:
            for wx in range(int(x + 18), int(x + w - 18), 34):
                for wy in range(int(base - h + 24), int(base - 20), 44):
                    if rng.random() < win_p:
                        c.rect(wx, wy, wx + 12, wy + 16, fill=win_color, outline=None, wob=0)
        x += w + rng.uniform(-10, 18)


def tree(c, rng, x, base, h, canopy, trunk=(110, 74, 53), r=150):
    c.rect(x - 16, base - h, x + 16, base, fill=trunk, width=5, wob=1)
    cy = base - h - r * 0.3
    for k in range(3):
        cx = x + rng.uniform(-r * 0.5, r * 0.5)
        yy = cy + rng.uniform(-r * 0.35, r * 0.25)
        rr = r * rng.uniform(0.65, 0.9)
        pts = []
        n = 9
        for i in range(n):
            a = 2 * math.pi * i / n
            rad = rr * rng.uniform(0.78, 1.08)
            pts.append((cx + rad * math.cos(a), yy + rad * 0.85 * math.sin(a)))
        c.poly(pts, fill=mix(canopy, (255, 255, 255), 0.07 * k), width=5, wob=1.5)


def stars_list(rng, n, y_max, x0=0, x1=WW):
    return [(rng.uniform(x0, x1), rng.uniform(0, y_max), rng.uniform(1.5, 4.2)) for _ in range(n)]


def draw_stars(c, stars):
    for x, y, s in stars:
        c.ellipse(x, y, s, s, fill=(240, 240, 255), outline=None, wob=0, n=12)


def moon(c, x, y, r, color=(250, 236, 190)):
    c.glow(x, y, r * 6, (120, 120, 150), 0.9)
    c.glow(x, y, r * 2.4, (255, 240, 200), 0.7)
    c.ellipse(x, y, r, r, fill=color, width=4, wob=0.4)
    for dx, dy, rr in ((-0.3, -0.2, 0.18), (0.25, 0.3, 0.13), (0.35, -0.3, 0.1)):
        c.ellipse(x + dx * r, y + dy * r, rr * r, rr * r, fill=darker(color, 0.92), outline=None, wob=0)


# ---------------------------------------------------------------- scenes
def city_night(seed, rain=True):
    rng = random.Random(seed)
    c = Canvas(WW, WH, seed=seed)
    c.vgrad(0, 0, WW, WH, C("#151b37"), C("#2e3867"))
    stars = stars_list(rng, 40, 300) if not rain else []
    draw_stars(c, stars)
    skyline(c, rng, 930, 260, 620, C("#232a51"), win_color=C("#4a4f78"), win_p=0.12)
    lit = []
    xs = [(-40, 470, 210), (560, 1120, 120), (1230, 1660, 260), (1760, 2210, 160)]
    for k, (x0, x1, top) in enumerate(xs):
        col = C("#2f3a6c") if k % 2 == 0 else C("#36407a")
        c.rect(x0, top, x1, 940, fill=col, width=6, wob=1.2)
        c.rect(x0 - 12, top - 22, x1 + 12, top, fill=darker(col, 0.85), width=5, wob=0.8)
        lit += windows_grid(c, rng, x0 + 30, top + 40, x1 - 30, 820, cols=max(2, int((x1 - x0) / 140)), rows=4,
                            lit_p=0.33, glow=(255, 190, 90))
        if k == 1:
            c.rect(780, 830, 900, 940, fill=C("#5b86a0"), width=5)
            c.ellipse(885, 890, 5, 5, fill=C("#f0c050"), outline=None)
    # street lamp
    lx = 1500
    c.rect(lx - 9, 430, lx + 9, 1000, fill=C("#1d2140"), width=4)
    c.poly([(lx - 55, 430), (lx + 55, 430), (lx + 35, 395), (lx - 35, 395)], fill=C("#1d2140"), width=4)
    c.poly([(lx - 40, 432), (lx + 40, 432), (lx + 260, 1000), (lx - 260, 1000)], fill=(255, 214, 140, 34), outline=None, wob=0)
    # pavement and road
    c.rect(-20, 935, WW + 20, 1030, fill=C("#2a3054"), width=5)
    c.rect(-20, 1030, WW + 20, WH + 20, fill=C("#1d223f"), width=5)
    for x in range(-20, WW, 160):
        c.line([(x, 935), (x - 20, 1030)], fill=C("#232846"), width=3)
    # wet reflections
    for (x, y, w, h) in lit:
        c.rect(x - w * 0.18, 1045, x + w * 0.18, 1045 + rng.uniform(40, 90), fill=(244, 199, 106, 28), outline=None, wob=4)
    c.rect(lx - 50, 1035, lx + 50, WH, fill=(255, 214, 140, 45), outline=None, wob=3)
    for _ in range(5):
        px, py = rng.uniform(100, WW - 100), rng.uniform(1060, 1180)
        c.ellipse(px, py, rng.uniform(60, 130), 12, fill=(120, 140, 200, 40), outline=(150, 170, 220, 90), width=2)
    glows = [(lx, 445, 380, (255, 196, 110), 0.85, "lamp")]
    return Scene("city_rain" if rain else "city_night", c.final(), ground=1005, slots=[820, 1150, 520],
                 mood="sad" if rain else "lonely", particles="rain" if rain else "fireflies",
                 tint=(178, 182, 228), glows=glows, stars=stars)


def bedroom(seed):
    rng = random.Random(seed)
    c = Canvas(WW, WH, seed=seed)
    c.vgrad(0, 0, WW, 900, C("#262f5e"), C("#323c70"))
    for x in range(0, WW, 90):
        c.rect(x, 0, x + 45, 900, fill=(255, 255, 255, 8), outline=None, wob=0)
    # window with night city
    wx0, wy0, wx1, wy1 = 800, 140, 1330, 600
    c.vgrad(wx0, wy0, wx1, wy1, C("#121838"), C("#2a3466"))
    sub = random.Random(seed + 1)
    for _ in range(25):
        c.ellipse(sub.uniform(wx0, wx1), sub.uniform(wy0, wy0 + 200), 2, 2, fill=(240, 240, 255), outline=None, wob=0, n=8)
    moon(c, 1200, 250, 40)
    x = wx0
    while x < wx1:
        w, h = sub.uniform(50, 110), sub.uniform(80, 220)
        c.rect(x, wy1 - h, min(x + w, wx1), wy1, fill=C("#1a1f42"), outline=None, wob=0)
        for wy in range(int(wy1 - h + 15), wy1 - 10, 30):
            if sub.random() < 0.35:
                c.rect(x + 12, wy, x + 20, wy + 12, fill=C("#e8b960"), outline=None, wob=0)
        x += w + 6
    c.rect(wx0, wy0, wx1, wy1, fill=None, width=14, wob=0.8)
    c.line([((wx0 + wx1) / 2, wy0), ((wx0 + wx1) / 2, wy1)], width=10)
    c.line([(wx0, (wy0 + wy1) / 2 - 30), (wx1, (wy0 + wy1) / 2 - 30)], width=8)
    c.rect(wx0 - 40, wy1, wx1 + 40, wy1 + 28, fill=C("#4b4a73"), width=5)
    for side in (-1, 1):
        x0 = wx0 - 10 if side < 0 else wx1 + 10
        c.poly([(x0, wy0 - 40), (x0 - side * 120, wy0 - 40), (x0 - side * 150, wy1 + 120), (x0 - side * 10, wy1 + 60)],
               fill=C("#5f5390"), width=5, wob=1.5)
        for k in range(1, 3):
            xx = x0 - side * 40 * k
            c.line([(xx, wy0 - 30), (xx - side * 12 * k, wy1 + 70)], fill=darker(C("#5f5390"), 0.8), width=3)
    c.rect(wx0 - 80, wy0 - 52, wx1 + 80, wy0 - 38, fill=C("#3a3456"), width=4)
    # floor
    c.rect(-20, 900, WW + 20, WH + 20, fill=C("#3a3050"), width=6)
    for y in range(940, WH, 70):
        c.line([(-20, y), (WW + 20, y + 6)], fill=C("#30283f"), width=3)
    # desk + lamp (left)
    c.rect(130, 735, 660, 765, fill=C("#6c4c43"), width=5)
    c.rect(160, 765, 185, 960, fill=C("#5a3f38"), width=5)
    c.rect(600, 765, 625, 960, fill=C("#5a3f38"), width=5)
    c.rect(430, 765, 600, 860, fill=C("#5a3f38"), width=5)
    c.line([(470, 812), (560, 812)], width=5)
    c.rect(220, 690, 380, 735, fill=C("#b6a4c8"), width=4)   # books
    c.rect(235, 655, 360, 690, fill=C("#8b9bd0"), width=4)
    c.ellipse(520, 728, 60, 10, fill=C("#2a2a44"), width=4)
    c.line([(520, 722), (470, 590), (560, 520)], width=9)
    c.poly([(520, 470), (640, 520), (600, 580), (500, 545)], fill=C("#2e3256"), width=5)
    c.poly([(560, 577), (618, 560), (570, 760), (380, 760)], fill=(255, 210, 140, 30), outline=None, wob=0)
    # chair
    c.rect(700, 600, 730, 960, fill=C("#4c3a4a"), width=5)
    c.rect(700, 790, 860, 815, fill=C("#4c3a4a"), width=5)
    c.rect(835, 815, 858, 960, fill=C("#4c3a4a"), width=5)
    c.poly([(690, 560), (760, 620), (740, 900), (680, 860)], fill=C("#4f5a8c"), width=4, wob=2)  # jacket
    # bed (right)
    c.rect(1500, 560, 1540, 960, fill=C("#4a3a5e"), width=5)
    c.rect(1500, 760, 2190, 900, fill=C("#4a3a5e"), width=5)
    c.rect(1520, 700, 2190, 790, fill=C("#aeb5d8"), width=5)
    c.ellipse(1640, 690, 110, 40, fill=C("#d6d9ef"), width=5)
    c.poly([(1700, 690), (2190, 680), (2190, 830), (1720, 840), (1680, 760)], fill=C("#4e62a8"), width=5, wob=2)
    for k in range(4):
        x = 1780 + k * 100
        c.line([(x, 700), (x + 30, 820)], fill=C("#41538f"), width=4)
    glows = [(600, 560, 470, (255, 186, 105), 0.95, "lamp")]
    return Scene("bedroom", c.final(), ground=1010, slots=[1000, 1320, 1150], mood="lonely", particles="dust",
                 tint=(190, 190, 230), glows=glows)


def park_sunset(seed):
    rng = random.Random(seed)
    c = Canvas(WW, WH, seed=seed)
    c.vgrad(0, 0, WW, 780, C("#f2dcaa"), C("#d9a970"))
    c.glow(1650, 170, 620, (255, 248, 225), 1.2)
    c.ellipse(1650, 170, 85, 85, fill=(255, 250, 232), outline=None, wob=0)
    c.poly([(-20, 640), (300, 540), (800, 580), (1300, 520), (1800, 600), (WW + 20, 560), (WW + 20, 780), (-20, 780)],
           fill=C("#b49d6b"), width=5, wob=3)
    c.poly([(1100, 780), (1300, 650), (1700, 620), (WW + 20, 700), (WW + 20, 780)], fill=C("#a68f5e"), width=5, wob=3)
    c.vgrad(0, 780, WW, WH, C("#ab9461"), C("#8d784c"))
    c.line([(-20, 780), (WW + 20, 782)], width=5)
    tree(c, rng, 260, 790, 330, C("#d9a3a0"), r=210)
    for _ in range(40):
        c.ellipse(rng.uniform(0, WW), rng.uniform(800, WH), 7, 4, fill=C("#ecc9c5"), width=2, wob=0)
    # bench back (behind characters)
    for y in (630, 690):
        c.rect(700, y, 1460, y + 26, fill=C("#8c5b3b"), width=5)
    c.rect(730, 600, 752, 820, fill=C("#6e472f"), width=5)
    c.rect(1408, 600, 1430, 820, fill=C("#6e472f"), width=5)
    f = Canvas(WW, WH, seed=seed + 5, rgba=True)
    f.rect(650, 800, 1510, 832, fill=C("#7a4e33"), width=5)
    f.rect(700, 832, 722, 930, fill=C("#5e3c28"), width=5)
    f.rect(1440, 832, 1462, 930, fill=C("#5e3c28"), width=5)
    return Scene("park", c.final(), ground=1000, slots=[930, 1225, 1080], mood="sweet", particles="petals",
                 fg=f.final(), tint=(255, 236, 212), seated=812, glows=[(1650, 170, 500, (255, 240, 200), 0.35, "breath")])


def snow_lake(seed):
    rng = random.Random(seed)
    c = Canvas(WW, WH, seed=seed)
    c.vgrad(0, 0, WW, 660, C("#111943"), C("#2c3a7a"))
    for k in range(3):
        pts = [(x, 120 + 140 * k + 70 * math.sin(x / 300 + k)) for x in range(-50, WW + 100, 100)]
        pts += [(x, y + 120) for x, y in reversed(pts)]
        c.poly(pts, fill=(140, 160, 230, 22), outline=None, wob=0)
    stars = stars_list(rng, 160, 560)
    draw_stars(c, stars)
    moon(c, 420, 190, 50)
    c.poly([(-20, 660), (300, 600), (600, 630), (1300, 560), (1700, 610), (WW + 20, 590), (WW + 20, 662), (-20, 662)],
           fill=C("#1c2452"), outline=None, wob=2)
    c.vgrad(0, 660, WW, 950, C("#1d2859"), C("#151c44"))
    for k in range(9):
        y = 680 + k * 28
        w = 90 - k * 8
        c.ellipse(420 + rng.uniform(-10, 10), y, w, 5, fill=(240, 230, 190, 150 - k * 12), outline=None, wob=0)
    for _ in range(26):
        x, y = rng.uniform(0, WW), rng.uniform(690, 930)
        c.line([(x, y), (x + 20, y - 4), (x + 40, y)], fill=C("#3b4a8a"), width=3, wob=0)
    for _ in range(8):
        c.ellipse(rng.uniform(800, 1800), 655 + rng.uniform(-10, 10), rng.uniform(120, 260), 18, fill=(200, 210, 255, 26), outline=None, wob=0)
    pts = [(-20, 930)] + [(x, 930 + 18 * math.sin(x / 170) + rng.uniform(-4, 4)) for x in range(0, WW + 60, 60)] + [(WW + 20, WH + 20), (-20, WH + 20)]
    c.poly(pts, fill=C("#cdd5ec"), width=6, wob=1)
    c.poly([(-20, 1080), (WW + 20, 1060), (WW + 20, WH + 20), (-20, WH + 20)], fill=C("#b3bddc"), outline=None, wob=2)
    f = Canvas(WW, WH, seed=seed + 3, rgba=True)
    for x0, s in ((-60, 1), (WW - 330, -1)):
        f.poly([(x0, WH + 10), (x0 + 60, 1030), (x0 + 200, 990), (x0 + 360, WH + 10)], fill=C("#2a3160"), width=6, wob=2)
        f.poly([(x0 + 50, 1045), (x0 + 200, 985), (x0 + 330, 1060), (x0 + 220, 1035), (x0 + 120, 1060)], fill=C("#e6ebf7"), width=5, wob=1)
    return Scene("snow_lake", c.final(), ground=1010, slots=[960, 1280, 1120], mood="melancholic", particles="snow",
                 fg=f.final(), tint=(196, 202, 240), stars=stars[::4], glows=[(420, 190, 260, (220, 220, 255), 0.25, "breath")])


def bar_neon(seed):
    rng = random.Random(seed)
    c = Canvas(WW, WH, seed=seed)
    c.vgrad(0, 0, WW, 890, C("#3c2152"), C("#28183a"))
    for y in range(20, 880, 60):
        off = 0 if (y // 60) % 2 else 70
        for x in range(-70 + off, WW, 140):
            c.rect(x, y, x + 130, y + 52, fill=(255, 255, 255, 7), outline=(20, 10, 30, 40), width=2, wob=0.5)
    for y in (330, 520):
        c.rect(420, y, 1760, y + 20, fill=C("#5b3a52"), width=5)
        x = 440
        while x < 1720:
            bw = rng.uniform(26, 42)
            bh = rng.uniform(70, 125)
            col = rng.choice([C("#3fa58f"), C("#d99a3b"), C("#c8505a"), C("#6aa84f"), C("#e48ab0"), C("#7b8fd6")])
            c.rect(x, y - bh, x + bw, y, fill=col, width=4, wob=0.4)
            c.rect(x + bw * 0.32, y - bh - 28, x + bw * 0.68, y - bh, fill=col, width=4, wob=0.3)
            x += bw + rng.uniform(10, 28)
    # neon signs
    hp = heart_points(240, 260, 120)
    c.glow(240, 250, 330, (255, 80, 160), 0.6)
    c.line(hp + [hp[0]], fill=C("#ff5fa8"), width=12, wob=0)
    c.line(hp + [hp[0]], fill=C("#ffd0e6"), width=4, wob=0)
    gx, gy = 1960, 210
    c.glow(gx, gy + 40, 300, (70, 230, 210), 0.55)
    glass = [(gx - 95, gy - 30), (gx + 95, gy - 30), (gx, gy + 90)]
    c.line(glass + [glass[0]], fill=C("#46e0cf"), width=12, wob=0)
    c.line([(gx, gy + 90), (gx, gy + 190), (gx - 60, gy + 190), (gx + 60, gy + 190)], fill=C("#46e0cf"), width=12, wob=0)
    c.line(glass + [glass[0]], fill=C("#d3fff8"), width=4, wob=0)
    for x0 in (500, 1100, 1650):
        c.poly([(x0 - 30, 0), (x0 + 30, 0), (x0 + 260, 900), (x0 - 260, 900)], fill=(255, 150, 230, 18), outline=None, wob=0)
    c.rect(-20, 890, WW + 20, WH + 20, fill=C("#2b1c3c"), width=6)
    for i, x in enumerate(range(-100, WW + 100, 180)):
        for j, y in enumerate(range(890, WH, 90)):
            if (i + j) % 2 == 0:
                c.poly([(x + j * 20, y), (x + 180 + j * 20, y), (x + 180 + (j + 1) * 20, y + 90), (x + (j + 1) * 20, y + 90)],
                       fill=(130, 90, 200, 38), outline=None, wob=0)
    glows = [(240, 250, 300, (255, 70, 150), 0.6, "neon"), (1960, 250, 300, (60, 220, 200), 0.55, "neon2")]
    return Scene("bar", c.final(), ground=1015, slots=[930, 1250, 1090], mood="sad", particles="dust",
                 tint=(228, 192, 238), glows=glows)


def school_street(seed):
    rng = random.Random(seed)
    c = Canvas(WW, WH, seed=seed)
    c.vgrad(0, 0, WW, 820, C("#cfe5ec"), C("#f1efdc"))
    for x0, x1, top, col in ((-40, 560, 240, "#f2cba8"), (600, 1120, 160, "#f4e5c2"), (1160, 1640, 300, "#bfd8e4"), (1680, 2200, 200, "#ecbcb2")):
        col = C(col)
        c.rect(x0, top, x1, 830, fill=col, width=6, wob=1)
        lit = windows_grid(c, rng, x0 + 30, top + 40, x1 - 30, 760, cols=3, rows=max(2, int((760 - top) / 150)),
                           lit_p=0.0, dark=C("#a9cadd"), ww=90, wh=100, curtain_p=0)
        for _ in range(3):
            ax, ay = rng.uniform(x0 + 60, x1 - 60), rng.uniform(top + 80, 700)
            c.rect(ax, ay, ax + 40, ay + 26, fill=C("#d9d9d9"), width=3)
    c.rect(-20, 830, WW + 20, 1040, fill=C("#e7d7b9"), width=6)
    for x in range(-20, WW, 120):
        c.line([(x, 830), (x - 30, 1040)], fill=C("#d6c4a2"), width=3)
    c.line([(-20, 935), (WW + 20, 935)], fill=C("#d6c4a2"), width=3)
    c.rect(-20, 1040, WW + 20, WH + 20, fill=C("#a7a6ae"), width=6)
    for x in range(0, WW, 220):
        c.rect(x, 1120, x + 110, 1132, fill=C("#f2f0ea"), outline=None, wob=0.5)
    for x in (180, 980, 1780):
        tree(c, rng, x, 840, 220, C("#9cad6c"), r=150)
    return Scene("school", c.final(), ground=1005, slots=[950, 1270, 1110], mood="happy", particles="leaves")


def rooftop(seed):
    rng = random.Random(seed)
    c = Canvas(WW, WH, seed=seed)
    c.vgrad(0, 0, WW, 900, C("#0e1330"), C("#4b3f79"))
    stars = stars_list(rng, 220, 640)
    draw_stars(c, stars)
    skyline(c, rng, 880, 120, 380, C("#1f2148"), win_color=C("#e9b765"), win_p=0.18)
    # rail behind characters
    c.rect(-20, 800, WW + 20, 816, fill=C("#3a3a62"), width=4)
    for x in range(20, WW, 150):
        c.rect(x, 800, x + 14, 900, fill=C("#3a3a62"), width=4)
    c.rect(-20, 890, WW + 20, WH + 20, fill=C("#2c2e4e"), width=6)
    for x in range(-20, WW, 200):
        c.line([(x, 890), (x - 80, WH)], fill=C("#262842"), width=3)
    c.rect(1750, 520, 2000, 890, fill=C("#3b3c66"), width=6)   # water tank
    c.poly([(1730, 520), (1875, 440), (2020, 520)], fill=C("#45467a"), width=6)
    # string lights
    bulbs, glows = [], []
    for i in range(20):
        t = i / 19
        x = -20 + (WW + 40) * t
        y = 130 + 40 * t + 170 * 4 * t * (1 - t)
        bulbs.append((x, y))
    c.line(bulbs, width=3, wob=0.5)
    for i, (x, y) in enumerate(bulbs):
        c.glow(x, y + 14, 70, (255, 200, 120), 0.6)
        c.ellipse(x, y + 14, 9, 12, fill=C("#ffd98f"), width=3, wob=0)
        if i % 4 == 1:
            glows.append((x, y + 14, 120, (255, 200, 120), 0.45, "twinkle%d" % i))
    return Scene("rooftop", c.final(), ground=1010, slots=[930, 1250, 1090], mood="dreamy", particles="fireflies",
                 tint=(205, 198, 238), stars=stars[::3], glows=glows)


def classroom(seed):
    rng = random.Random(seed)
    c = Canvas(WW, WH, seed=seed)
    c.vgrad(0, 0, WW, 870, C("#f0e4c8"), C("#e5d3b0"))
    c.rect(-20, 650, WW + 20, 870, fill=C("#a3b79d"), width=5)
    c.rect(-20, 640, WW + 20, 660, fill=C("#8b9f85"), width=4)
    c.rect(500, 150, 1480, 540, fill=C("#3e5c4b"), width=16, wob=0.8)
    c.rect(520, 540, 1460, 560, fill=C("#7a5a40"), width=5)
    chalk = (232, 240, 228, 210)
    hp = heart_points(1270, 300, 70)
    c.line(hp + [hp[0]], fill=chalk, width=5, wob=0.8)
    for k in range(4):
        y = 230 + k * 62
        x = 600
        while x < 1080 - k * 60:
            w = rng.uniform(30, 80)
            c.line([(x, y), (x + w * 0.5, y - 10), (x + w, y)], fill=chalk, width=5, wob=1.2)
            x += w + 18
    c.ellipse(990, 85, 42, 42, fill=C("#fbf6ea"), width=6)
    c.line([(990, 85), (990, 58)], width=5)
    c.line([(990, 85), (1010, 95)], width=5)
    for x0 in (1620, 1870):
        c.vgrad(x0, 140, x0 + 210, 560, C("#bfe0f0"), C("#e8f3f2"))
        c.rect(x0, 140, x0 + 210, 560, fill=None, width=12)
        c.line([(x0 + 105, 140), (x0 + 105, 560)], width=8)
        c.poly([(x0, 160), (x0 + 210, 160), (x0 - 120, 1000), (x0 - 420, 1000)], fill=(255, 246, 214, 34), outline=None, wob=0)
    c.rect(-20, 870, WW + 20, WH + 20, fill=C("#b18e66"), width=6)
    for y in range(900, WH, 60):
        c.line([(-20, y), (WW + 20, y)], fill=C("#a07f59"), width=3)
    f = Canvas(WW, WH, seed=seed + 2, rgba=True)
    for x0 in (-60, WW - 420):
        f.rect(x0, 955, x0 + 480, 990, fill=C("#c49a6c"), width=6)
        f.rect(x0 + 30, 990, x0 + 450, 1060, fill=C("#a77f55"), width=6)
        f.rect(x0 + 60, 1060, x0 + 84, WH + 10, fill=C("#5f6b70"), width=5)
        f.rect(x0 + 396, 1060, x0 + 420, WH + 10, fill=C("#5f6b70"), width=5)
    return Scene("classroom", c.final(), ground=1010, slots=[930, 1250, 1090], mood="nostalgic", particles="dust",
                 fg=f.final(), tint=(255, 248, 236))


def dusk_stop(seed):
    """Evening bus stop at sunset: the 'posted at night, missing someone' mood."""
    rng = random.Random(seed)
    c = Canvas(WW, WH, seed=seed)
    c.vgrad(0, 0, WW, 470, C("#2c2c60"), C("#b5648a"))
    c.vgrad(0, 470, WW, 900, C("#b5648a"), C("#f2a660"))
    c.glow(1350, 820, 650, (255, 190, 120), 1.0)
    c.ellipse(1350, 830, 110, 110, fill=(255, 214, 150), outline=None, wob=0)
    for k in range(4):
        y = 230 + k * 70
        x0 = rng.uniform(-200, 1200)
        c.ellipse(x0 + 300, y, rng.uniform(180, 320), 16, fill=(255, 200, 210, 60), outline=None, wob=0)
    stars = stars_list(rng, 30, 220)
    draw_stars(c, stars)
    skyline(c, rng, 905, 160, 470, C("#3b2f58"), win_color=C("#f2c06a"), win_p=0.1)
    # power lines with a few birds
    for k, y0 in enumerate((150, 190)):
        pts = []
        for i in range(21):
            t = i / 20
            pts.append((-20 + (WW + 40) * t, y0 + 25 * k + 110 * 4 * t * (1 - t)))
        c.line(pts, fill=C("#2a2140"), width=3, wob=0.3)
        if k == 0:
            for bx in (520, 560, 1490):
                t = (bx + 20) / (WW + 40)
                by = y0 + 110 * 4 * t * (1 - t)
                c.ellipse(bx, by - 9, 11, 9, fill=C("#2a2140"), outline=None, wob=0)
                c.poly([(bx + 6, by - 14), (bx + 18, by - 16), (bx + 8, by - 8)], fill=C("#2a2140"), outline=None, wob=0)
    c.rect(-20, 905, WW + 20, 1030, fill=C("#5a4565"), width=5)
    for x in range(-20, WW, 150):
        c.line([(x, 905), (x - 25, 1030)], fill=C("#4e3b5a"), width=3)
    c.rect(-20, 1030, WW + 20, WH + 20, fill=C("#3a2d4a"), width=5)
    for x in range(40, WW, 240):
        c.rect(x, 1110, x + 120, 1122, fill=C("#e8c9a0"), outline=None, wob=0.5)
    c.rect(-20, 1040, WW + 20, WH, fill=(242, 166, 96, 22), outline=None, wob=0)
    # bus stop shelter (right)
    sx0, sx1 = 1500, 2010
    c.rect(sx0, 560, sx0 + 18, 1000, fill=C("#2e2a44"), width=4)
    c.rect(sx1 - 18, 560, sx1, 1000, fill=C("#2e2a44"), width=4)
    c.rect(sx0 - 40, 530, sx1 + 40, 565, fill=C("#3c3656"), width=5)
    c.rect(sx0 + 30, 600, sx1 - 30, 900, fill=(190, 210, 240, 45), outline=C("#2e2a44"), width=4, wob=0.5)
    c.rect(sx0 + 40, 900, sx1 - 40, 930, fill=C("#6b5a72"), width=4)
    c.rect(sx1 + 60, 420, sx1 + 74, 1000, fill=C("#2e2a44"), width=4)
    c.rect(sx1 + 30, 380, sx1 + 104, 440, fill=C("#f2e6c8"), width=5)
    c.ellipse(sx1 + 67, 410, 18, 18, fill=C("#5b86a0"), width=3)
    # street lamp just switched on (left)
    lx = 330
    c.rect(lx - 9, 470, lx + 9, 1000, fill=C("#2e2a44"), width=4)
    c.poly([(lx - 50, 470), (lx + 50, 470), (lx + 32, 438), (lx - 32, 438)], fill=C("#2e2a44"), width=4)
    c.poly([(lx - 38, 472), (lx + 38, 472), (lx + 220, 1000), (lx - 220, 1000)], fill=(255, 214, 140, 24), outline=None, wob=0)
    glows = [(lx, 485, 300, (255, 196, 110), 0.7, "lamp"), (sx1 + 67, 410, 160, (255, 240, 200), 0.35, "breath"),
             (1350, 830, 500, (255, 170, 110), 0.25, "breath")]
    return Scene("dusk_stop", c.final(), ground=1005, slots=[930, 1250, 1100], mood="lonely", particles="dust",
                 tint=(236, 204, 222), glows=glows, stars=stars[::3])


BUILDERS = {
    "city_rain": lambda s: city_night(s, rain=True),
    "city_night": lambda s: city_night(s, rain=False),
    "bedroom": bedroom,
    "park": park_sunset,
    "snow_lake": snow_lake,
    "bar": bar_neon,
    "school": school_street,
    "rooftop": rooftop,
    "classroom": classroom,
    "dusk_stop": dusk_stop,
}

# scene pools for the overall feeling of the song: [opening/closing scene candidates], [middle scenes], [happy flashbacks]
POOLS = {
    # default: quiet, evening, missing someone. Mostly dusk/night scenes, a few warm memories
    "melancholy": (["dusk_stop"],
                   ["city_night", "snow_lake", "rooftop", "dusk_stop", "city_rain", "bedroom", "bar"],
                   ["park", "classroom"]),
    "sad": (["city_rain", "bedroom"], ["bar", "snow_lake", "rooftop", "bedroom", "city_rain"], ["park", "classroom", "school"]),
    "sweet": (["school", "park"], ["classroom", "rooftop", "city_night", "park", "school"], ["snow_lake"]),
}


def build(name, seed):
    return BUILDERS[name](seed)
