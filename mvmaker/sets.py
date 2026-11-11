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
    rock = C("#3b3150") if time != "day" else C("#7d6e66")
    pts = [(-20, 860), (500, 850), (1000, 870), (1320, 880), (1380, 1000), (1420, WH + 20), (-20, WH + 20)]
    c.poly(pts, fill=rock, width=6, wob=2)
    c.poly([(-20, 846), (500, 836), (1000, 856), (1325, 866), (1330, 884), (-20, 880)], fill=C("#4f6b55") if time == "day" else C("#3a4a4e"), width=4, wob=1.5)
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


def from_library(name):
    def make(seed, time=None):
        return scn.build(name, seed)
    return make


SETS = {
    "beach": beach, "pier": pier, "island": island, "underwater": underwater, "storm_sea": storm_sea,
    "cliff": cliff, "lighthouse": lighthouse,
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
