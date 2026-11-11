"""Composable scenery for storyboard shots: sea, beach, pier, island, underwater, storm, cliff, lighthouse, crowd.

Each painter returns a scenes.Scene. Extra attributes used by the effects in fx.py:
  horizon  y of the sea horizon        shore  y where sea meets sand (beach)
  sea_top / sea_bottom                 lamp   (x, y) of a lighthouse lamp
Time of day ("dusk", "night", "storm", "day") changes the palette.
"""
import math
import random

from . import scenes as scn
from .common import WH, WW, Canvas, darker, hexrgb, mix
from .scenes import Scene, draw_stars, moon, skyline, stars_list, tree

C = hexrgb

PALETTES = {
    #          sky top    sky mid    horizon    sea top    sea bottom  sand       light tint for characters
    "dusk":  ("#2c2c60", "#b5648a", "#f2a660", "#7a5a86", "#3a3262", "#c99a86", (236, 204, 222)),
    "night": ("#0e1434", "#1f2a5c", "#34437e", "#22306a", "#111a40", "#4b4f74", (188, 194, 236)),
    "storm": ("#15182a", "#2a3048", "#3f4762", "#2a3346", "#151b2b", "#3a3a48", (170, 176, 205)),
    "day":   ("#9cc3dc", "#cfe2ea", "#f2efdd", "#6fa3c4", "#3f739c", "#e8d3a8", (255, 250, 240)),
    # cute & sweet: candy pastels
    "pastel": ("#f6bfd3", "#fde0e6", "#fff3e2", "#9fd6e8", "#78bfdc", "#f7dcc2", (255, 248, 250)),
    "pastel_night": ("#4a4683", "#7e6fb0", "#c9a6d4", "#6f7fc0", "#4b5a9c", "#9e93c4", (226, 220, 250)),
}


def _pal(time):
    p = PALETTES.get(time, PALETTES["dusk"])
    return [C(x) if isinstance(x, str) else x for x in p]


def sky(c, rng, time, horizon):
    top, mid, hor, *_ = _pal(time)
    c.vgrad(0, 0, WW, horizon * 0.55, top, mid)
    c.vgrad(0, horizon * 0.55, WW, horizon + 2, mid, hor)
    stars = []
    if time in ("night", "dusk"):
        stars = stars_list(rng, 140 if time == "night" else 30, horizon * (0.8 if time == "night" else 0.35))
        draw_stars(c, stars)
    if time == "night":
        moon(c, 430, 170, 46)
    if time in ("pastel", "day"):
        for k in range(5):   # puffy candy clouds
            cx, cy = rng.uniform(100, WW - 100), rng.uniform(70, horizon * 0.55)
            for dx, dy, r in ((-70, 10, 55), (0, -15, 75), (75, 8, 58), (0, 22, 60)):
                c.ellipse(cx + dx, cy + dy, r * 1.3, r, fill=(255, 255, 255), outline=None, wob=0.5)
            c.ellipse(cx, cy + 40, 150, 22, fill=(255, 236, 244), outline=None, wob=0)
    if time == "pastel_night":
        stars = stars_list(rng, 90, horizon * 0.8)
        draw_stars(c, stars)
        moon(c, 430, 170, 46, color=(255, 240, 210))
    if time == "dusk":
        for k in range(4):   # thin evening clouds
            y = horizon * (0.3 + 0.12 * k)
            c.ellipse(rng.uniform(200, WW - 200), y, rng.uniform(200, 380), 14, fill=(255, 205, 215, 55), outline=None, wob=0)
    if time == "storm":
        for k in range(26):   # heavy cloud masses
            x, y = rng.uniform(-100, WW + 100), rng.uniform(-40, horizon * 0.7)
            r = rng.uniform(120, 260)
            c.ellipse(x, y, r, r * 0.55, fill=mix(_pal("storm")[1], (10, 10, 20), rng.uniform(0, 0.5)) + (230,), outline=None, wob=2)
    return stars


def sea(c, rng, time, top, bottom, reflect_x=None):
    _, _, hor, st, sb, *_ = _pal(time)
    c.vgrad(0, top, WW, bottom, st, sb)
    c.line([(-20, top), (WW + 20, top)], fill=mix(hor, (255, 255, 255), 0.2), width=3, wob=0)
    if reflect_x is not None and time in ("dusk", "night"):
        col = (255, 196, 130) if time == "dusk" else (240, 230, 190)
        for k in range(10):
            y = top + 18 + k * (bottom - top) / 12
            w = (130 - k * 9) * (1.3 if time == "dusk" else 0.8)
            c.ellipse(reflect_x + rng.uniform(-12, 12), y, w, 5, fill=col + (150 - k * 12,), outline=None, wob=0)


def _sun(c, time, x, horizon):
    if time == "pastel":
        c.glow(x, horizon - 200, 420, (255, 236, 200), 0.8)
        c.ellipse(x, horizon - 200, 70, 70, fill=(255, 238, 190), outline=None, wob=0)
    if time == "dusk":
        c.glow(x, horizon - 30, 620, (255, 190, 120), 1.0)
        c.ellipse(x, horizon - 40, 95, 95, fill=(255, 214, 150), outline=None, wob=0)


def _scene(name, c, ground, slots, time, **extra):
    pal = _pal(time)
    sc = Scene(name, c.final(), ground=ground, slots=slots, mood="lonely", particles=None, tint=pal[6],
               glows=extra.pop("glows", []), stars=extra.pop("stars", []), fg=extra.pop("fg", None))
    for k, v in extra.items():
        setattr(sc, k, v)
    return sc


# ---------------------------------------------------------------- painters
def beach(seed, time="dusk"):
    rng = random.Random(seed)
    c = Canvas(WW, WH, seed=seed)
    horizon, shore = 600, 850
    stars = sky(c, rng, time, horizon)
    _sun(c, time, 1500, horizon)
    sea(c, rng, time, horizon, shore + 40, reflect_x=1500 if time == "dusk" else 430)
    sand = _pal(time)[5]
    pts = [(-20, shore)] + [(x, shore + 10 * math.sin(x / 230)) for x in range(0, WW + 80, 80)] + [(WW + 20, WH + 20), (-20, WH + 20)]
    c.poly(pts, fill=sand, width=5, wob=1)
    c.vgrad(0, 1000, WW, WH, sand, darker(sand, 0.85))
    for _ in range(60):
        c.ellipse(rng.uniform(0, WW), rng.uniform(900, WH), rng.uniform(3, 7), 2, fill=darker(sand, 0.85), outline=None, wob=0)
    for x in (180, 1880):
        c.ellipse(x, rng.uniform(1080, 1150), 26, 14, fill=mix(sand, (255, 255, 255), 0.4), width=3)   # shells/pebbles
    return _scene("beach", c, ground=990, slots=[900, 1220, 1075], time=time, horizon=horizon, shore=shore, stars=stars[::4])


def pier(seed, time="dusk"):
    rng = random.Random(seed)
    c = Canvas(WW, WH, seed=seed)
    horizon = 620
    stars = sky(c, rng, time, horizon)
    _sun(c, time, 1700, horizon)
    sea(c, rng, time, horizon, WH, reflect_x=1700 if time == "dusk" else 430)
    wood = C("#6b4a3f") if time != "night" else C("#3f3550")
    deck_y = 900
    for x in range(40, 1600, 150):   # posts
        c.rect(x, deck_y + 30, x + 26, WH + 20, fill=darker(wood, 0.8), width=5)
    c.rect(-20, deck_y, 1600, deck_y + 34, fill=wood, width=5)
    for x in range(0, 1600, 70):
        c.line([(x, deck_y + 2), (x, deck_y + 32)], fill=darker(wood, 0.8), width=3)
    c.rect(1540, 560, 1556, deck_y, fill=C("#2e2a44"), width=4)   # lamp at the end of the pier
    c.poly([(1505, 560), (1590, 560), (1572, 532), (1523, 532)], fill=C("#2e2a44"), width=4)
    c.rect(1460, 790, 1640, 800, fill=darker(wood, 0.9), width=3)
    glows = [(1548, 575, 260, (255, 196, 110), 0.75 if time != "day" else 0.0, "lamp")]
    return _scene("pier", c, ground=deck_y + 4, slots=[1050, 1330, 1300], time=time, horizon=horizon,
                  glows=glows, stars=stars[::4], deck=deck_y)


def island(seed, time="night"):
    rng = random.Random(seed)
    c = Canvas(WW, WH, seed=seed)
    horizon = 520
    stars = sky(c, rng, time, horizon)
    _sun(c, time, 1650, horizon)
    sea(c, rng, time, horizon, WH, reflect_x=1650 if time == "dusk" else 430)
    sand = _pal(time)[5]
    cx, cy = 1075, 860
    c.ellipse(cx, cy + 22, 330, 54, fill=mix(_pal(time)[3], (255, 255, 255), 0.25), outline=None, wob=1)  # surf ring
    c.ellipse(cx, cy, 300, 46, fill=sand, width=5, wob=1)
    # palm tree
    px = cx + 150
    pts = [(px - 10, cy - 10), (px + 10, cy - 10), (px + 40, cy - 300), (px + 22, cy - 300)]
    c.poly(pts, fill=C("#6e4a35"), width=5)
    leaf = C("#3e6b4f") if time == "day" else C("#2c3f45")
    for a in (-160, -120, -60, -20, 20):
        r = math.radians(a)
        tip = (px + 31 + 170 * math.cos(r), cy - 300 + 90 * math.sin(r) + 60)
        c.poly([(px + 31, cy - 305), (px + 31 + 90 * math.cos(r), cy - 330 + 40 * math.sin(r)), tip,
                (px + 31 + 70 * math.cos(r), cy - 290 + 50 * math.sin(r))], fill=leaf, width=4, wob=1)
    return _scene("island", c, ground=cy + 6, slots=[cx - 80, cx + 40, cx - 60], time=time, horizon=horizon,
                  stars=stars[::4])


def underwater(seed, time="night"):
    rng = random.Random(seed)
    c = Canvas(WW, WH, seed=seed)
    c.vgrad(0, 0, WW, WH, C("#2f6f9a"), C("#0a1836"))
    c.vgrad(0, 0, WW, 60, C("#7fb6d6"), C("#2f6f9a"))
    floor = 1060
    pts = [(-20, floor)] + [(x, floor + 22 * math.sin(x / 260) + rng.uniform(-6, 6)) for x in range(0, WW + 80, 80)] + [(WW + 20, WH + 20), (-20, WH + 20)]
    c.poly(pts, fill=C("#24324f"), width=5, wob=1)
    for _ in range(9):
        x = rng.uniform(0, WW)
        r = rng.uniform(40, 110)
        c.ellipse(x, floor + 10, r, r * 0.55, fill=C("#1b2640"), width=4, wob=2)
    for _ in range(40):
        c.ellipse(rng.uniform(0, WW), rng.uniform(80, floor), rng.uniform(1, 3), rng.uniform(1, 3), fill=(200, 230, 255, 60), outline=None, wob=0)
    return _scene("underwater", c, ground=floor, slots=[900, 1200, 1075], time="night", floor=floor)


def storm_sea(seed, time="storm"):
    rng = random.Random(seed)
    c = Canvas(WW, WH, seed=seed)
    horizon = 560
    sky(c, rng, "storm", horizon)
    sea(c, rng, "storm", horizon, WH)
    for _ in range(40):   # chop
        x, y = rng.uniform(0, WW), rng.uniform(horizon + 20, WH)
        w = 30 + (y - horizon) * 0.12
        c.line([(x, y), (x + w / 2, y - w * 0.25), (x + w, y)], fill=C("#4a5674"), width=3, wob=0)
    return _scene("storm_sea", c, ground=930, slots=[1075, 1300, 1075], time="storm", horizon=horizon)


def cliff(seed, time="dusk"):
    rng = random.Random(seed)
    c = Canvas(WW, WH, seed=seed)
    horizon = 640
    stars = sky(c, rng, time, horizon)
    _sun(c, time, 1750, horizon)
    sea(c, rng, time, horizon, WH, reflect_x=1750 if time == "dusk" else 430)
    rock = {"day": C("#7d6e66"), "pastel": C("#d9a7b8")}.get(time, C("#3b3150"))
    pts = [(-20, 860), (500, 850), (1000, 870), (1320, 880), (1380, 1000), (1420, WH + 20), (-20, WH + 20)]
    c.poly(pts, fill=rock, width=6, wob=2)
    c.poly([(-20, 846), (500, 836), (1000, 856), (1325, 866), (1330, 884), (-20, 880)], fill={"day": C("#4f6b55"), "pastel": C("#a8d4a0")}.get(time, C("#3a4a4e")), width=4, wob=1.5)
    for _ in range(14):
        x = rng.uniform(0, 1250)
        c.line([(x, 850), (x + 6, 830), (x + 12, 850)], fill=C("#2d3a3c"), width=3)
    return _scene("cliff", c, ground=872, slots=[1050, 1230, 1180], time=time, horizon=horizon, stars=stars[::4])


def lighthouse(seed, time="night"):
    rng = random.Random(seed)
    c = Canvas(WW, WH, seed=seed)
    horizon = 600
    stars = sky(c, rng, time, horizon)
    sea(c, rng, time, horizon, WH, reflect_x=430)
    rock = C("#2c2a40")
    c.poly([(1350, WH + 20), (1450, 900), (1600, 860), (1900, 870), (2050, 930), (WW + 20, 980), (WW + 20, WH + 20)], fill=rock, width=6, wob=2)
    lx, top = 1720, 300
    c.poly([(lx - 70, 870), (lx + 70, 870), (lx + 45, top + 60), (lx - 45, top + 60)], fill=C("#e9e2d6"), width=6, wob=1)
    for k in range(3):
        y0 = top + 120 + k * 170
        c.poly([(lx - 48 - k * 7, y0), (lx + 48 + k * 7, y0), (lx + 52 + k * 7, y0 + 60), (lx - 52 - k * 7, y0 + 60)], fill=C("#c9473f"), width=4, wob=0.5)
    c.rect(lx - 55, top + 10, lx + 55, top + 60, fill=C("#ffe3a0"), width=5)
    c.poly([(lx - 70, top + 10), (lx, top - 50), (lx + 70, top + 10)], fill=C("#c9473f"), width=5)
    c.rect(lx - 80, top + 58, lx + 80, top + 72, fill=C("#3a3350"), width=4)
    # foreground rocks for the character (left)
    c.poly([(-20, 980), (300, 950), (700, 970), (900, 1010), (940, WH + 20), (-20, WH + 20)], fill=darker(rock, 1.1), width=6, wob=2)
    glows = [(lx, top + 35, 300, (255, 220, 140), 0.9, "lamp")]
    return _scene("lighthouse", c, ground=975, slots=[420, 640, 520], time=time, horizon=horizon, glows=glows,
                  stars=stars[::4], lamp=(lx, top + 35))


def mountains(seed, time="dusk"):
    """Layered mountains with a river winding through: 跨越山河."""
    rng = random.Random(seed)
    c = Canvas(WW, WH, seed=seed)
    horizon = 640
    stars = sky(c, rng, time, horizon)
    _sun(c, time, 1550, 600)
    base = _pal(time)[2]
    for k, (y0, amp, dark) in enumerate(((560, 170, 0.55), (650, 140, 0.45), (760, 110, 0.35))):
        col = mix(_pal(time)[1], (30, 26, 50), dark + 0.15 * k)
        pts = [(-20, WH)]
        x = -20
        while x < WW + 40:
            pts.append((x, y0 - amp * abs(math.sin(x / (260 + 60 * k) + k * 1.7)) - rng.uniform(0, 30)))
            x += 70
        pts.append((WW + 20, WH))
        c.poly(pts, fill=col, width=5, wob=1.5)
    river = mix(_pal(time)[3], (255, 255, 255), 0.2)
    left = [(1000 + 30 * math.sin(y / 60) + (y - 700) * (y - 700) / 900, y) for y in range(700, WH + 40, 30)]
    right = [(x + 30 + (y - 700) * 0.9, y) for x, y in left]
    c.poly(left + right[::-1], fill=river, width=4, wob=1)
    grass = mix(_pal(time)[1], (60, 90, 60), 0.55)
    pts = [(-20, 930)] + [(x, 930 + 25 * math.sin(x / 300)) for x in range(0, 860, 60)] + [(960, 1010), (1040, WH + 20), (-20, WH + 20)]
    c.poly(pts, fill=grass, width=5, wob=1)
    pts = [(1380, WH + 20), (1470, 1000)] + [(x, 950 + 20 * math.sin(x / 260)) for x in range(1560, WW + 80, 60)] + [(WW + 20, WH + 20)]
    c.poly(pts, fill=grass, width=5, wob=1)
    return _scene("mountains", c, ground=985, slots=[450, 1750, 600], time=time, horizon=horizon, stars=stars[::4])


def meadow(seed, time="day"):
    """Spring field with blossom trees and flowers: 人间四月天."""
    rng = random.Random(seed)
    c = Canvas(WW, WH, seed=seed)
    horizon = 700
    stars = sky(c, rng, time, horizon)
    _sun(c, time, 1700, 640)
    if time == "day":
        c.glow(1700, 160, 380, (255, 250, 220), 0.9)
    hill = mix(_pal(time)[1], (110, 150, 100), 0.6)
    c.poly([(-20, 720), (500, 640), (1000, 690), (1500, 630), (WW + 20, 690), (WW + 20, 800), (-20, 800)], fill=darker(hill, 0.9), width=5, wob=2)
    field = mix(_pal(time)[1], (130, 175, 105), 0.65)
    c.vgrad(0, 760, WW, WH, field, darker(field, 0.8))
    c.line([(-20, 762), (WW + 20, 760)], width=5)
    for x in (260, 1880):
        tree(c, rng, x, 800, 260, C("#f0b7c4"), r=190)
    for _ in range(420):
        x, y = rng.uniform(0, WW), rng.uniform(780, WH)
        r = 3 + (y - 780) / 70
        col = rng.choice([(255, 236, 160), (255, 190, 210), (255, 255, 255), (200, 180, 255)])
        c.ellipse(x, y, r, r, fill=col, outline=None, wob=0, n=10)
    return _scene("meadow", c, ground=985, slots=[900, 1200, 1075], time=time, horizon=horizon, stars=stars[::4])


def snow_town(seed, time="night"):
    """Snowy northern street: little houses with snowy roofs and warm windows."""
    rng = random.Random(seed)
    c = Canvas(WW, WH, seed=seed)
    horizon = 900
    autumn = time.startswith("pastel") or time == "autumn"
    stars = sky(c, rng, "pastel" if time == "autumn" else time, horizon)
    glows = []
    x = -60
    k = 0
    while x < WW + 40:
        w = rng.uniform(300, 420)
        h = rng.uniform(260, 380)
        col = ([C("#f2a7a0"), C("#a9c8e8"), C("#f6d28c"), C("#c9b2e6")] if autumn else
               [C("#8a5a54"), C("#5f6f8f"), C("#9c7a58"), C("#6d5a7e")])[k % 4]
        top = 880 - h
        c.rect(x, top, x + w, 900, fill=col, width=6, wob=1)
        c.poly([(x - 30, top + 10), (x + w / 2, top - 150), (x + w + 30, top + 10)], fill=darker(col, 0.7), width=6, wob=1)
        if not autumn:
            c.poly([(x - 34, top + 14), (x + w / 2, top - 156), (x + w + 34, top + 14), (x + w + 10, top + 30), (x + w / 2, top - 120), (x - 10, top + 30)],
                   fill=C("#f2f5fb"), width=5, wob=1.5)
        for wx in (x + w * 0.25, x + w * 0.65):
            lit = rng.random() < 0.75
            c.rect(wx - 34, top + 70, wx + 34, top + 150, fill=C("#f6c66e") if lit else C("#2c3352"), width=5)
            c.line([(wx, top + 70), (wx, top + 150)], width=3)
            if lit:
                c.glow(wx, top + 110, 120, (255, 190, 100), 0.5)
        if k % 2 == 0:
            c.rect(x + w * 0.42, top + 190, x + w * 0.58, 900, fill=darker(col, 0.6), width=5)
        x += w + rng.uniform(10, 50)
        k += 1
    ground_col = (C("#f3d9b8"), C("#e6c49c")) if autumn else (C("#e2e8f4"), C("#c4cde2"))
    c.rect(-20, 895, WW + 20, WH + 20, fill=ground_col[0], width=6)
    c.vgrad(0, 1000, WW, WH, *ground_col)
    if autumn:
        for _ in range(70):
            c.ellipse(rng.uniform(0, WW), rng.uniform(905, WH), 10, 5, fill=rng.choice([C("#f29a6b"), C("#f6c35c"), C("#e8806e")]), width=2, wob=0)
    for lx in (720, 1560):
        c.rect(lx - 8, 560, lx + 8, 960, fill=C("#2d2f48"), width=4)
        c.poly([(lx - 40, 560), (lx + 40, 560), (lx + 26, 532), (lx - 26, 532)], fill=C("#2d2f48"), width=4)
        c.ellipse(lx, 527, 30, 10, fill=C("#f2f5fb"), width=3)
        glows.append((lx, 575, 260, (255, 200, 120), 0.2 if time in ("day", "pastel", "autumn") else 0.8, "lamp"))
    return _scene("snow_town", c, ground=990, slots=[930, 1230, 1075], time=time, horizon=horizon, stars=stars[::4], glows=glows)


def kitchen(seed, time="night"):
    """Small warm kitchen: 柴米油盐."""
    rng = random.Random(seed)
    c = Canvas(WW, WH, seed=seed)
    wall = C("#e8cfa6") if time == "day" else C("#b98f78")
    c.vgrad(0, 0, WW, 760, wall, darker(wall, 0.9))
    for x in range(0, WW, 60):
        for y in range(330, 760, 60):
            c.rect(x, y, x + 58, y + 58, fill=mix(wall, (255, 255, 255), 0.25 if (x // 60 + y // 60) % 2 else 0.15), outline=darker(wall, 0.85), width=2, wob=0)
    wx0, wy0, wx1, wy1 = 760, 90, 1300, 470
    c.vgrad(wx0, wy0, wx1, wy1, C("#1d2550") if time != "day" else C("#a9d0e6"), C("#3a3f78") if time != "day" else C("#e8f1ee"))
    if time != "day":
        moon(c, 1180, 180, 34)
    c.rect(wx0, wy0, wx1, wy1, fill=None, width=14)
    c.line([((wx0 + wx1) / 2, wy0), ((wx0 + wx1) / 2, wy1)], width=8)
    c.rect(wx0 - 30, wy1, wx1 + 30, wy1 + 22, fill=C("#f2ebdc"), width=5)
    c.ellipse(900, wy1 - 30, 40, 30, fill=C("#5a9a6a"), width=4)      # potted plant
    c.rect(870, wy1 - 20, 930, wy1, fill=C("#c26a4e"), width=4)
    c.rect(-20, 760, WW + 20, 790, fill=C("#d9d2c4"), width=6)       # counter top
    c.rect(-20, 790, WW + 20, 1000, fill=C("#7a9a8f"), width=6)       # cabinets
    for x in range(0, WW, 240):
        c.rect(x + 14, 810, x + 226, 985, fill=C("#86a89c"), width=4)
        c.ellipse(x + 200, 900, 7, 7, fill=C("#e8e2d0"), width=2)
    c.rect(1250, 730, 1520, 762, fill=C("#3a3a48"), width=5)        # stove + pot
    c.rect(1300, 640, 1470, 735, fill=C("#d8574c"), width=6)
    c.rect(1280, 630, 1490, 652, fill=C("#b8463d"), width=5)
    c.ellipse(1385, 618, 20, 10, fill=C("#3a3a48"), width=3)
    for i, col in enumerate(("#e8c46a", "#e0e0e0", "#c97c5d", "#9fc38a")):    # jars on a shelf
        c.rect(260 + i * 90, 560, 330 + i * 90, 660, fill=C(col), width=4)
    c.rect(220, 660, 640, 676, fill=C("#7a5a40"), width=4)
    for i in range(4):                                                    # hanging utensils
        x = 1650 + i * 90
        c.line([(x, 360), (x, 520)], width=5)
        c.ellipse(x, 540, 26, 30 if i % 2 else 18, fill=C("#9a9aa8"), width=4)
    c.rect(-20, 1000, WW + 20, WH + 20, fill=C("#d6b98e"), width=6)
    for x in range(-20, WW, 120):
        c.line([(x, 1000), (x - 40, WH)], fill=C("#c4a67c"), width=3)
    glows = [(1030, 280, 500, (255, 210, 150), 0.5 if time != "day" else 0.2, "breath")]
    return _scene("kitchen", c, ground=1000, slots=[930, 1230, 1075], time=time, glows=glows, pot=(1385, 600))


def autumn_park(seed, time="pastel"):
    """Cute pastel autumn park: coral/yellow trees, leaf carpet, a bench (characters can sit: seated)."""
    rng = random.Random(seed)
    c = Canvas(WW, WH, seed=seed)
    horizon = 760
    stars = sky(c, rng, time, horizon)
    _sun(c, time, 1700, horizon)
    hill = C("#f4c9b0") if time != "pastel_night" else C("#6b5c99")
    c.poly([(-20, 780), (400, 690), (900, 740), (1400, 680), (WW + 20, 740), (WW + 20, 820), (-20, 820)], fill=hill, width=5, wob=2)
    ground = C("#f7d7b0") if time != "pastel_night" else C("#8a7fb5")
    c.vgrad(0, 800, WW, WH, ground, darker(ground, 0.9))
    c.line([(-20, 800), (WW + 20, 802)], width=5)
    c.poly([(800, WH + 20), (1000, 800), (1150, 800), (1350, WH + 20)], fill=mix(ground, (255, 255, 255), 0.35), width=4, wob=1)
    for x, col in ((180, "#f29a6b"), (520, "#f6c35c"), (1680, "#ee8a8a"), (1990, "#f6c35c")):
        tree(c, rng, x, 820, 240, C(col), r=170)
    for _ in range(160):
        x, y = rng.uniform(0, WW), rng.uniform(810, WH)
        r = 5 + (y - 800) / 60
        c.ellipse(x, y, r * 1.6, r, fill=rng.choice([C("#f29a6b"), C("#f6c35c"), C("#e8806e"), C("#f7b2a0")]), width=2, wob=0)
    lx = 1450
    c.rect(lx - 9, 470, lx + 9, 830, fill=C("#7a6a8a"), width=4)
    c.ellipse(lx, 455, 34, 34, fill=C("#fff1c8"), width=4)
    for y in (640, 700):   # bench back; characters sit at 812 like the park
        c.rect(700, y, 1420, y + 26, fill=C("#c98a6a"), width=5)
    c.rect(730, 600, 752, 820, fill=C("#a86e52"), width=5)
    c.rect(1368, 600, 1390, 820, fill=C("#a86e52"), width=5)
    f = Canvas(WW, WH, seed=seed + 5, rgba=True)
    f.rect(650, 800, 1470, 832, fill=C("#b97a5c"), width=5)
    f.rect(700, 832, 722, 930, fill=C("#8e5a42"), width=5)
    f.rect(1400, 832, 1422, 930, fill=C("#8e5a42"), width=5)
    glows = [(lx, 455, 220, (255, 220, 150), 0.6 if time == "pastel_night" else 0.15, "lamp")]
    sc = _scene("autumn_park", c, ground=990, slots=[930, 1200, 1075], time=time, horizon=horizon, stars=stars[::4],
                glows=glows, fg=f.final())
    sc.seated = 812
    sc.fg_y = 940      # characters standing below this line are in front of the bench
    return sc

def from_library(name):
    def make(seed, time=None):
        return scn.build(name, seed)
    return make


SETS = {
    "beach": beach, "pier": pier, "island": island, "underwater": underwater, "storm_sea": storm_sea,
    "cliff": cliff, "lighthouse": lighthouse, "mountains": mountains, "meadow": meadow, "snow_town": snow_town,
    "kitchen": kitchen, "autumn_park": autumn_park,
    # the earlier library (fixed time of day)
    "city_rain": from_library("city_rain"), "city_night": from_library("city_night"), "bedroom": from_library("bedroom"),
    "park": from_library("park"), "snow_lake": from_library("snow_lake"), "bar": from_library("bar"),
    "school": from_library("school"), "rooftop": from_library("rooftop"), "classroom": from_library("classroom"),
    "dusk_stop": from_library("dusk_stop"),
}


def build(name, time, seed):
    sc = SETS[name](seed, time) if name in SETS else scn.build(name, seed)
    sc.time = time
    return sc
