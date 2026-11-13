"""Animated storyboard effects, drawn in world coordinates every frame.

Each effect is fx_<name>(img, p, ctx) where p is the dict from the storyboard (all keys optional) and ctx has
t (song time), lt (time inside the shot), D (shot length), sc (Scene), seed.
BACK effects are drawn before the characters, everything else after them.
"""
import math
import random

from PIL import Image, ImageChops, ImageDraw

from .common import OUTLINE, WH, WW, add_glow, ease, heart_points, star_points

BACK = {"waves", "tide", "footprints", "sand_heart", "boat_far", "seagulls", "rays", "beam", "lightning",
        "shooting_star", "clock", "aurora", "fireworks", "sunbeam", "calendar", "steam", "sunlight", "autumn_turn", "train", "portrait", "ripples"}


def _d(img):
    return ImageDraw.Draw(img, "RGBA")


def _rng(ctx, k=0):
    return random.Random(ctx["seed"] * 977 + k)


# ---------------------------------------------------------------- sea
def fx_waves(img, p, ctx):
    sc, t = ctx["sc"], ctx["t"]
    top = getattr(sc, "horizon", 600) + 12
    bottom = p.get("bottom", getattr(sc, "shore", WH))
    d = _d(img)
    r = _rng(ctx, 1)
    for k in range(int(p.get("n", 46))):
        y = top + (bottom - top) * (r.random() ** 0.8)
        depth = (y - top) / max(1, bottom - top)
        w = 20 + 70 * depth
        x = (r.uniform(0, WW) + t * (14 + 30 * depth) * (1 if k % 2 else -1)) % (WW + 200) - 100
        a = int(70 + 110 * (0.5 + 0.5 * math.sin(t * 1.7 + k)))
        d.line([(x, y), (x + w * 0.5, y - 3 - 4 * depth), (x + w, y)], fill=(225, 230, 255, a), width=2 + int(2 * depth))


def tide_edge(sc, lt, p):
    amp, period = p.get("amp", 120), p.get("period", 5.0)
    return sc.shore + 30 + amp * (0.5 - 0.5 * math.cos(2 * math.pi * lt / period))


def _max_edge(sc, lt, p):
    return max(tide_edge(sc, lt * k / 24, p) for k in range(25))


def fx_tide(img, p, ctx):
    """The water line creeping up the sand and pulling back."""
    sc, lt, t = ctx["sc"], ctx["lt"], ctx["t"]
    edge = tide_edge(sc, lt, p)
    d = _d(img)
    pts = [(-20, sc.shore - 5)]
    for x in range(-20, WW + 60, 60):
        pts.append((x, edge + 10 * math.sin(x / 90 + t * 2)))
    pts += [(WW + 20, sc.shore - 5)]
    d.polygon(pts, fill=(120, 130, 190, 150))
    foam = [(x, edge + 10 * math.sin(x / 90 + t * 2)) for x in range(-20, WW + 60, 30)]
    d.line(foam, fill=(250, 245, 255, 220), width=7, joint="curve")
    d.line([(x, y - 14) for x, y in foam], fill=(250, 245, 255, 90), width=3, joint="curve")


def _erasure(sc, lt, p, y):
    if "tide" not in p:
        return 1.0
    return 1.0 - max(0.0, min(1.0, (_max_edge(sc, lt, p["tide"]) - y + 10) / 30))


def fx_footprints(img, p, ctx):
    sc, lt = ctx["sc"], ctx["lt"]
    d = _d(img)
    x0, x1 = p.get("x0", 200), p.get("x1", 1000)
    y = p.get("y", sc.shore + 110)
    n = int(abs(x1 - x0) / 70)
    for i in range(n):
        x = x0 + (x1 - x0) * i / max(1, n - 1)
        yy = y + (12 if i % 2 else -12) + 30 * math.sin(i / 3)
        a = _erasure(sc, lt, p, yy)
        if a > 0.02:
            d.ellipse([x - 13, yy - 7, x + 13, yy + 7], fill=(80, 60, 70, int(110 * a)))


def fx_sand_heart(img, p, ctx):
    """A heart drawn in the sand; the tide washes it away."""
    sc, lt = ctx["sc"], ctx["lt"]
    x, y, s = p.get("x", 760), p.get("y", sc.shore + 150), p.get("size", 120)
    a = _erasure(sc, lt, p, y - s * 0.7)
    if a <= 0.02:
        return
    pts = [(px, y + (py - y) * 0.45) for px, py in heart_points(x, y, s, 48)]
    d = _d(img)
    d.line(pts + [pts[0]], fill=(90, 60, 80, int(150 * a)), width=9, joint="curve")
    d.line([(px, py + 4) for px, py in pts + [pts[0]]], fill=(255, 235, 220, int(80 * a)), width=3, joint="curve")


def _boat(d, x, y, s, rock=0.0, col=(60, 45, 60), sail=(240, 232, 222)):
    c, sn = math.cos(rock), math.sin(rock)

    def R(px, py):
        return (x + px * s * c - py * s * sn, y + px * s * sn + py * s * c)
    d.polygon([R(-60, 0), R(60, 0), R(42, 22), R(-42, 22)], fill=col, outline=OUTLINE)
    d.line([R(0, 0), R(0, -110)], fill=OUTLINE, width=max(2, int(4 * s)))
    d.polygon([R(4, -105), R(4, -10), R(52, -10)], fill=sail, outline=OUTLINE)


def fx_boat_far(img, p, ctx):
    """A small boat on the horizon, drifting (away, or past without stopping)."""
    sc, lt, D = ctx["sc"], ctx["lt"], ctx["D"]
    hz = getattr(sc, "horizon", 600)
    k = ease(min(1, max(0, lt / D)))
    x = p.get("x0", 1500) + (p.get("x1", 1900) - p.get("x0", 1500)) * k
    s = p.get("s0", 0.5) + (p.get("s1", p.get("s0", 0.5)) - p.get("s0", 0.5)) * k
    _boat(_d(img), x, hz + 6 - 20 * s, s, rock=0.04 * math.sin(ctx["t"] * 1.5), col=(40, 34, 50), sail=(220, 210, 215))


def fx_seagulls(img, p, ctx):
    t = ctx["t"]
    d = _d(img)
    r = _rng(ctx, 3)
    for k in range(int(p.get("n", 4))):
        x = (r.uniform(0, WW) + t * r.uniform(40, 90)) % (WW + 300) - 150
        y = p.get("y", 260) + r.uniform(-120, 120) + 10 * math.sin(t * 1.3 + k)
        s = r.uniform(0.6, 1.2)
        f = math.sin(t * 6 + k) * 12 * s
        d.line([(x - 26 * s, y - f), (x, y), (x + 26 * s, y - f)], fill=(40, 34, 52, 230), width=max(2, int(4 * s)), joint="curve")


def fx_big_waves(img, p, ctx):
    """Foreground storm swell rolling past."""
    t = ctx["t"]
    d = _d(img)
    base = p.get("y", 980)
    for layer, (col, amp, speed, off) in enumerate((((40, 52, 78), 70, 90, 0), ((28, 38, 60), 55, 140, 80))):
        pts = [(-20, WH + 20)]
        for x in range(-20, WW + 60, 40):
            y = base + off + amp * math.sin((x + t * speed) / 210 + layer) + 18 * math.sin((x - t * speed * 0.6) / 70)
            pts.append((x, y))
        pts.append((WW + 20, WH + 20))
        d.polygon(pts, fill=col + (255,))
        crest = pts[1:-1]
        d.line(crest, fill=(220, 228, 245, 210), width=6, joint="curve")
        for x, y in crest[::3]:
            d.ellipse([x - 6, y - 10, x + 6, y + 2], fill=(235, 240, 250, 160))


def wave_height(x, t, p):
    base = p.get("y", 980)
    return base + 70 * math.sin((x + t * 90) / 210) + 18 * math.sin((x - t * 54) / 70)


def fx_lightning(img, p, ctx):
    """Every few seconds: a bolt and a flash."""
    t = ctx["t"]
    period = p.get("period", 3.3)
    ph = (t + ctx["seed"] * 0.37) % period
    if ph > 0.22:
        return
    r = random.Random(int((t + ctx["seed"] * 0.37) // period) * 31 + ctx["seed"])
    x = r.uniform(300, WW - 300)
    pts, y = [(x, 0)], 0
    while y < getattr(ctx["sc"], "horizon", 600) - 20:
        y += r.uniform(50, 110)
        x += r.uniform(-70, 70)
        pts.append((x, y))
    d = _d(img)
    d.line(pts, fill=(250, 250, 255, 255), width=7, joint="curve")
    d.line(pts, fill=(170, 190, 255, 120), width=20, joint="curve")
    k = 1 - ph / 0.22
    flash = Image.new("RGB", img.size, (int(90 * k), int(95 * k), int(120 * k)))
    img.paste(ImageChops.screen(img.convert("RGB"), flash))


def fx_shooting_star(img, p, ctx):
    t = ctx["t"]
    period = p.get("period", 4.0)
    ph = (t % period) / 0.9
    if ph > 1:
        return
    k = int(t // period)
    r = random.Random(k * 13 + ctx["seed"])
    x0, y0 = r.uniform(300, WW - 600), r.uniform(60, 300)
    x, y = x0 + 500 * ph, y0 + 160 * ph
    _d(img).line([(x - 160, y - 52), (x, y)], fill=(255, 250, 225, int(230 * (1 - ph))), width=4)
    add_glow(img, x, y, 30, (255, 240, 200), 0.8 * (1 - ph))


def fx_beam(img, p, ctx):
    """Rotating lighthouse beam."""
    sc, t = ctx["sc"], ctx["t"]
    lx, ly = getattr(sc, "lamp", (WW / 2, 300))
    a = t * p.get("speed", 1.1)
    L = 1500 * math.cos(a)
    w = 120 + 60 * abs(math.sin(a))
    d = _d(img)
    if abs(L) > 30:
        d.polygon([(lx, ly - 12), (lx, ly + 12), (lx + L, ly + w), (lx + L, ly - w)], fill=(255, 240, 180, 40))
        d.polygon([(lx, ly - 6), (lx, ly + 6), (lx + L * 0.6, ly + w * 0.4), (lx + L * 0.6, ly - w * 0.4)], fill=(255, 245, 200, 45))
    add_glow(img, lx, ly, 240, (255, 230, 160), 0.4 + 0.6 * (1 - abs(math.cos(a))))


# ---------------------------------------------------------------- underwater
def fx_rays(img, p, ctx):
    t = ctx["t"]
    d = _d(img)
    for k in range(7):
        x = 150 + k * 320 + 60 * math.sin(t * 0.4 + k)
        a = int(22 + 18 * math.sin(t * 0.9 + k * 1.7))
        d.polygon([(x - 40, 0), (x + 40, 0), (x + 260, WH), (x + 60, WH)], fill=(200, 235, 255, max(0, a)))
    for x in range(0, WW, 90):   # shimmering surface
        y = 30 + 8 * math.sin(x / 60 + t * 2)
        d.line([(x, y), (x + 50, y + 4)], fill=(230, 245, 255, 120), width=3)


def fx_bubbles(img, p, ctx):
    t = ctx["t"]
    d = _d(img)
    r = _rng(ctx, 5)
    x0, x1 = p.get("x0", 200), p.get("x1", WW - 200)
    for k in range(int(p.get("n", 30))):
        sp = r.uniform(60, 160)
        x = r.uniform(x0, x1) + 14 * math.sin(t * 2 + k)
        y = WH - ((r.uniform(0, WH) + t * sp) % (WH + 60))
        rr = r.uniform(4, 14)
        d.ellipse([x - rr, y - rr, x + rr, y + rr], outline=(225, 245, 255, 190), width=2)
        d.ellipse([x - rr * 0.4, y - rr * 0.6, x - rr * 0.1, y - rr * 0.3], fill=(255, 255, 255, 170))


def fx_seaweed(img, p, ctx):
    sc, t = ctx["sc"], ctx["t"]
    d = _d(img)
    r = _rng(ctx, 7)
    floor = getattr(sc, "floor", WH - 140)
    for k in range(int(p.get("n", 9))):
        x0 = r.uniform(0, WW)
        h = r.uniform(160, 360)
        pts = []
        for i in range(12):
            f = i / 11
            pts.append((x0 + 30 * f * math.sin(t * 1.2 + k + f * 3), floor + 20 - h * f))
        d.line(pts, fill=(40, 110, 90, 255), width=14, joint="curve")
        d.line(pts, fill=(70, 150, 115, 255), width=6, joint="curve")


def fx_heart_sink(img, p, ctx):
    """A cracked heart sinking to the bottom of the sea."""
    lt, D, t = ctx["lt"], ctx["D"], ctx["t"]
    k = ease(min(1, max(0, lt / (D * p.get("speed", 1.0)))))
    x = p.get("x", 1075) + 40 * math.sin(t * 1.3)
    y = p.get("y0", 150) + (p.get("y1", 950) - p.get("y0", 150)) * k
    s = p.get("size", 110)
    d = _d(img)
    hp = heart_points(x, y, s, 48)
    d.polygon(hp, fill=(214, 70, 92, 245), outline=OUTLINE)
    d.line(hp + [hp[0]], fill=OUTLINE, width=6)
    d.line([(x - 6, y - s * 0.75), (x + 14, y - s * 0.35), (x - 12, y), (x + 10, y + s * 0.35), (x, y + s * 0.7)],
           fill=OUTLINE, width=6, joint="curve")
    d.ellipse([x - s * 0.55, y - s * 0.6, x - s * 0.3, y - s * 0.35], fill=(255, 200, 210, 160))


def _polaroid(w, h, seed):
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, w - 1, h - 1], fill=(250, 246, 236, 255), outline=OUTLINE, width=4)
    iw, ih = w - 24, int(h * 0.68)
    for y in range(ih):   # little sunset inside
        f = y / ih
        d.line([(12, 12 + y), (12 + iw, 12 + y)], fill=(int(240 - 60 * f), int(170 - 40 * f), int(150 + 20 * f), 255))
    d.rectangle([12, 12 + int(ih * 0.72), 12 + iw, 12 + ih], fill=(200, 150, 130, 255))
    r = random.Random(seed)
    for k, col in enumerate(((224, 138, 82), (229, 154, 176))):
        bx = 12 + iw * (0.32 + 0.3 * k)
        by = 12 + ih * 0.78
        d.rectangle([bx - 20, by - 30, bx + 20, by], fill=col + (255,), outline=OUTLINE, width=3)
        d.ellipse([bx - 9, by - 22, bx - 5, by - 18], fill=OUTLINE)
        d.ellipse([bx + 5, by - 22, bx + 9, by - 18], fill=OUTLINE)
    d.polygon(heart_points(12 + iw * 0.47, 12 + ih * 0.42, 14 + r.uniform(0, 4)), fill=(240, 90, 120, 255))
    d.rectangle([12, 12, 12 + iw, 12 + ih], outline=OUTLINE, width=3)
    return im


def fx_photos(img, p, ctx):
    """Memory photos floating up (往事浮上来)."""
    t, lt = ctx["t"], ctx["lt"]
    r = _rng(ctx, 11)
    for k in range(int(p.get("n", 5))):
        x = r.uniform(250, WW - 250)
        sp = r.uniform(70, 120)
        y = WH + 150 - (lt * sp + r.uniform(0, 500))
        if y < -250:
            continue
        ph = _polaroid(170, 200, ctx["seed"] + k).rotate(12 * math.sin(t * 0.8 + k * 2), resample=Image.BICUBIC, expand=True)
        a = max(0.0, min(1.0, lt / 0.8))
        if a < 1:
            ph.putalpha(ph.getchannel("A").point(lambda v: int(v * a)))
        img.paste(ph, (int(x - ph.width / 2), int(y - ph.height / 2)), ph)


def fx_clock(img, p, ctx):
    """Wall clock whose hands race (time passing)."""
    t = ctx["t"]
    x, y, r = p.get("x", 1075), p.get("y", 160), p.get("r", 70)
    d = _d(img)
    d.ellipse([x - r, y - r, x + r, y + r], fill=(250, 244, 230, 255), outline=OUTLINE, width=7)
    for k in range(12):
        a = k * math.pi / 6
        d.line([(x + 0.8 * r * math.cos(a), y + 0.8 * r * math.sin(a)), (x + 0.92 * r * math.cos(a), y + 0.92 * r * math.sin(a))], fill=OUTLINE, width=4)
    sp = p.get("speed", 4.0)
    for L, w, a in ((0.5, 7, t * sp / 12), (0.78, 5, t * sp)):
        d.line([(x, y), (x + L * r * math.sin(a), y - L * r * math.cos(a))], fill=OUTLINE, width=w)


def fx_aurora(img, p, ctx):
    t = ctx["t"]
    d = _d(img)
    for k, col in enumerate(((90, 230, 170), (120, 200, 255), (190, 140, 255))):
        pts = [(x, 160 + 60 * k + 50 * math.sin(x / 260 + t * 0.5 + k)) for x in range(-50, WW + 100, 50)]
        poly = pts + [(x, y + 140) for x, y in reversed(pts)]
        d.polygon(poly, fill=col + (26,))


def fx_fireworks(img, p, ctx):
    t = ctx["t"]
    d = _d(img)
    for k in range(int(p.get("n", 3))):
        period = 2.4 + k * 0.7
        ph = ((t + k * 0.9) % period) / period
        r = random.Random(int((t + k * 0.9) // period) * 17 + k)
        x, y = r.uniform(300, WW - 300), r.uniform(120, 420)
        col = r.choice([(255, 200, 120), (255, 140, 170), (170, 210, 255), (200, 255, 190)])
        if ph < 0.25:
            d.line([(x, WH * 0.75 - (WH * 0.75 - y) * ph / 0.25), (x, WH * 0.75 - (WH * 0.75 - y) * ph / 0.25 + 30)], fill=col + (200,), width=3)
            continue
        q = (ph - 0.25) / 0.75
        R = 40 + 200 * ease(q)
        for i in range(18):
            a = 2 * math.pi * i / 18
            d.line([(x + R * 0.7 * math.cos(a), y + R * 0.7 * math.sin(a) + 30 * q * q),
                    (x + R * math.cos(a), y + R * math.sin(a) + 40 * q * q)], fill=col + (int(255 * (1 - q)),), width=4)
        add_glow(img, x, y, 220, col, 0.5 * (1 - q))


def fx_messages(img, p, ctx):
    """Chat bubbles popping up one after another (messages from you)."""
    lt = ctx["lt"]
    d = _d(img)
    x0, y0 = p.get("x", 1300), p.get("y", 520)
    for k in range(int(p.get("n", 5))):
        t0 = 0.35 + k * p.get("every", 0.7)
        if lt < t0:
            break
        a = min(1.0, (lt - t0) / 0.25)
        y = y0 - k * 92 + (1 - a) * 30
        w = 150 + 70 * ((k * 37) % 3)
        x = x0 + (60 if k % 2 else -60) - w / 2
        col = (250, 250, 245) if k % 2 else (152, 222, 140)
        d.rounded_rectangle([x, y - 34, x + w, y + 34], radius=26, fill=col + (int(240 * a),), outline=OUTLINE + (int(255 * a),), width=4)
        tail = (x + 30, y + 30) if k % 2 == 0 else (x + w - 30, y + 30)
        d.polygon([tail, (tail[0] + (-18 if k % 2 == 0 else 18), tail[1] + 22), (tail[0] + (20 if k % 2 == 0 else -20), tail[1])],
                  fill=col + (int(240 * a),))
        if k % 3 == 2:
            d.polygon(heart_points(x + w / 2, y, 18), fill=(235, 80, 110, int(255 * a)))
        else:
            for j in range(3 if k % 2 else 2):
                d.line([(x + 24, y - 10 + j * 14), (x + w - 30 - j * 20, y - 10 + j * 14)], fill=(90, 90, 110, int(200 * a)), width=5)


def fx_calendar(img, p, ctx):
    """Wall calendar shedding its pages: days passing."""
    t, lt = ctx["t"], ctx["lt"]
    x, y = p.get("x", 420), p.get("y", 300)
    d = _d(img)
    w, h = 170, 190
    sp = p.get("speed", 2.0)
    day = int(lt * sp) + p.get("start", 1)
    d.rectangle([x - w / 2, y - h / 2, x + w / 2, y + h / 2], fill=(250, 246, 236, 255), outline=OUTLINE, width=5)
    d.rectangle([x - w / 2, y - h / 2, x + w / 2, y - h / 2 + 50], fill=(214, 82, 80, 255), outline=OUTLINE, width=5)
    from .common import font
    d.text((x, y + 30), str((day - 1) % 30 + 1), font=font("fallback", 84), fill=OUTLINE, anchor="mm")
    ph = (lt * sp) % 1.0     # the page that just tore off, drifting down
    if lt > 1 / sp:
        px, py = x + 80 * ph, y + 60 + 260 * ph
        page = [(px - 60, py - 60), (px + 60, py - 50), (px + 55, py + 60), (px - 65, py + 52)]
        a = int(230 * (1 - ph))
        d.polygon(page, fill=(250, 246, 236, a), outline=OUTLINE + (a,))


def fx_steam(img, p, ctx):
    t = ctx["t"]
    x0, y0 = p.get("x", getattr(ctx["sc"], "pot", (1385, 600))[0]), p.get("y", getattr(ctx["sc"], "pot", (1385, 600))[1])
    d = _d(img)
    for k in range(6):
        ph = (t * 0.45 + k / 6) % 1.0
        x = x0 + 40 * math.sin(t * 1.5 + k * 2) * ph + (k - 3) * 12
        y = y0 - ph * 300
        r = 16 + 34 * ph
        d.ellipse([x - r, y - r, x + r, y + r], fill=(255, 255, 255, int(110 * (1 - ph))))


def fx_sunlight(img, p, ctx):
    """A warm beam of sunlight falling on a spot (愿你的冬天永远不缺暖阳)."""
    t = ctx["t"]
    x, y = p.get("x", 1075), p.get("y", 990)
    d = _d(img)
    a = int(55 + 15 * math.sin(t * 1.3))
    d.polygon([(x - 120 + 300, 0), (x + 120 + 300, 0), (x + 260, y), (x - 260, y)], fill=(255, 214, 140, a))
    add_glow(img, x, y - 140, 360, (255, 200, 120), 0.55 + 0.1 * math.sin(t * 1.3))


def fx_heart_break(img, p, ctx):
    """A big cute heart that cracks and splits in two (爱已被时间撕裂)."""
    lt, D, t = ctx["lt"], ctx["D"], ctx["t"]
    x, y, size = p.get("x", 1075), p.get("y", 380), p.get("size", 150)
    k = ease(min(1, max(0, (lt - D * p.get("at", 0.35)) / (D * 0.45))))
    bob = 10 * math.sin(t * 2)
    hp = heart_points(0, 0, size, 64)
    for side in (-1, 1):
        half = [(px, py) for px, py in hp if px * side >= -2] or hp
        if k > 0:   # tilt each half away and let it drop a little
            a = math.radians(18 * k * side)
            half = [(px * math.cos(a) - py * math.sin(a), px * math.sin(a) + py * math.cos(a)) for px, py in half]
        pts = [(x + px + side * 70 * k, y + py + bob + 60 * k * k) for px, py in half]
        d = _d(img)
        d.polygon(pts, fill=(244, 112, 158, 255))
        d.line(pts + [pts[0]], fill=(196, 82, 128, 255), width=7, joint="curve")
        hx = x + side * 70 * k + (-0.45 if side < 0 else 0.15) * size
        d.ellipse([hx, y - 0.55 * size + bob + 60 * k * k, hx + 0.25 * size, y - 0.35 * size + bob + 60 * k * k], fill=(255, 220, 232, 200))
    if k > 0:   # little sparkles where it cracked
        for j in range(5):
            r = 8 + 10 * (1 - k)
            sx = x + 30 * math.cos(j * 1.3 + t) * k * 2
            sy = y + 40 * math.sin(j * 1.9 + t) * k * 2
            d.polygon(star_points(sx, sy, r, r * 0.35), fill=(255, 240, 200, int(220 * (1 - k * 0.6))))


def fx_dream(img, p, ctx):
    """Thought bubble with someone's smiling face in it (想念你微笑的脸)."""
    from .character import Look, sprite
    t, lt = ctx["t"], ctx["lt"]
    x, y, r = p.get("x", 1350), p.get("y", 420), p.get("r", 190)
    a = ease(min(1, lt / 0.6))
    if a <= 0:
        return
    bob = 8 * math.sin(t * 1.6)
    d = _d(img)
    tail = p.get("from", (x - 260, y + 330))
    for k, rr in enumerate((16, 26, 38)):
        f = (k + 1) / 4
        cx = tail[0] + (x - tail[0]) * f
        cy = tail[1] + (y - tail[1]) * f + bob
        d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], fill=(255, 255, 255, int(235 * a)), outline=(226, 160, 190, int(255 * a)), width=4)
    for dx, dy, q in ((-0.6, 0.15, 0.55), (0.6, 0.15, 0.55), (0, -0.35, 0.62), (-0.35, -0.2, 0.55), (0.35, -0.2, 0.55), (0, 0.25, 0.7)):
        rr = r * q
        d.ellipse([x + dx * r - rr, y + dy * r - rr + bob, x + dx * r + rr, y + dy * r + rr + bob], fill=(255, 255, 255, int(240 * a)))
    look = Look(p.get("color", "#e59ab0"), p.get("accessory", "flower"))
    sp, (ax, ay) = sprite(look.key(), p.get("face", "happy"), False, 0, 0, 1 if (t % 2.4) < 1.2 else 0, 0, p.get("s", 12))
    if a < 1:
        sp = sp.copy()
        sp.putalpha(sp.getchannel("A").point(lambda v: int(v * a)))
    img.paste(sp, (int(x - ax), int(y + 0.45 * r - ay + bob)), sp)
    for k in range(3):
        ph = (t * 0.6 + k / 3) % 1
        d.polygon(heart_points(x + (k - 1) * 90, y - r * 0.7 - ph * 90 + bob, 16), fill=(244, 112, 158, int(220 * (1 - ph) * a)))


def fx_autumn_turn(img, p, ctx):
    """Summer turning into autumn during the shot (时光旋转 夏天瞬间秋天): warm orange wash creeping in."""
    lt, D = ctx["lt"], ctx["D"]
    k = ease(min(1, max(0, (lt - D * 0.2) / (D * 0.6))))
    if k <= 0:
        return
    warm = Image.new("RGB", img.size, (246, 160, 92))
    blended = ImageChops.multiply(img.convert("RGB"), Image.blend(Image.new("RGB", img.size, (255, 255, 255)), warm, 0.5 * k))
    img.paste(blended)


def fx_train(img, p, ctx):
    """A little train on the tracks, arriving (x0 -> x1, slowing down) or leaving."""
    sc, lt, D, t = ctx["sc"], ctx["lt"], ctx["D"], ctx["t"]
    k = min(1, max(0, lt / (D * p.get("dur", 0.7))))
    k = 1 - (1 - k) ** 2 if p.get("ease", "out") == "out" else k * k
    head = p.get("x0", -200) + (p.get("x1", 1600) - p.get("x0", -200)) * k
    base = getattr(sc, "track", 850)
    d = _d(img)
    body = p.get("color", (110, 150, 170))
    n, L = int(p.get("cars", 3)), 640
    for c in range(n):
        x1 = head - c * (L + 24)
        x0 = x1 - L
        y0, y1 = base - 230, base - 18
        d.rounded_rectangle([x0, y0, x1, y1], radius=26, fill=body + (255,), outline=OUTLINE, width=6)
        d.rectangle([x0 + 6, y1 - 50, x1 - 6, y1 - 28], fill=(240, 228, 200, 255))
        for wx in range(int(x0 + 50), int(x1 - 80), 110):
            d.rounded_rectangle([wx, y0 + 40, wx + 80, y0 + 120], radius=10, fill=(255, 214, 140, 255), outline=OUTLINE, width=4)
        for wx in (x0 + 110, x1 - 110):
            d.ellipse([wx - 26, y1 - 14, wx + 26, y1 + 38], fill=(60, 54, 70, 255), outline=OUTLINE, width=4)
        if c == 0:
            add_glow(img, x1 - 10, y1 - 80, 160, (255, 230, 170), 0.6)
    if 0 < k < 1:   # steam puffs while moving
        for j in range(4):
            ph = (t * 1.2 + j / 4) % 1
            r = 20 + 50 * ph
            d.ellipse([head - 120 - ph * 200 - r, base - 260 - ph * 120 - r, head - 120 - ph * 200 + r, base - 260 - ph * 120 + r],
                      fill=(255, 255, 255, int(130 * (1 - ph))))


def fx_wind(img, p, ctx):
    """起风了: long curving gusts sweeping across the picture, with leaves or petals riding them."""
    t = ctx["t"]
    d = _d(img)
    r = _rng(ctx, 21)
    strength = p.get("strength", 1.0)
    for k in range(int(8 * strength)):
        y0 = r.uniform(150, WH - 250)
        sp = r.uniform(500, 900)
        ph = ((t * sp / 2400) + r.random()) % 1.4 - 0.2
        L = r.uniform(500, 900)
        x_head = -200 + ph * (WW + 600)
        pts = []
        for i in range(24):
            f = i / 23
            x = x_head - L * (1 - f)
            y = y0 + 40 * math.sin(f * 4 + t * 1.5 + k) - 60 * f * f
            pts.append((x, y))
        a = int(90 * strength * math.sin(min(1, max(0, ph + 0.2) / 1.4) * math.pi))
        d.line(pts, fill=(255, 255, 255, max(0, a)), width=5, joint="curve")
        x, y = pts[-1]   # curl at the head of the gust
        d.arc([x - 40, y - 60, x + 40, y + 20], 200, 470, fill=(255, 255, 255, max(0, a)), width=5)
    cols = p.get("colors", [(250, 190, 200), (255, 230, 170), (230, 160, 120)])
    for k in range(int(26 * strength)):
        sp = r.uniform(300, 650)
        x = (r.uniform(0, WW) + t * sp) % (WW + 200) - 100
        y = r.uniform(100, WH - 150) + 50 * math.sin(t * 2 + k)
        a = t * 4 + k
        rx, ry = 12, 6
        pts = [(x + rx * math.cos(th) * math.cos(a) - ry * math.sin(th) * math.sin(a),
                y + rx * math.cos(th) * math.sin(a) + ry * math.sin(th) * math.cos(a)) for th in [i * math.pi / 6 for i in range(12)]]
        d.polygon(pts, fill=cols[k % len(cols)] + (230,), outline=OUTLINE + (120,))


def fx_portrait(img, p, ctx):
    """A framed painting of someone (走进床头藏起的画 / 画中的你 低着头说话)."""
    from .character import Look, sprite
    x, y, w, h = p.get("x", 1075), p.get("y", 330), p.get("w", 300), p.get("h", 340)
    d = _d(img)
    d.rectangle([x - w / 2 - 22, y - h / 2 - 22, x + w / 2 + 22, y + h / 2 + 22], fill=(170, 120, 80, 255), outline=OUTLINE, width=6)
    d.rectangle([x - w / 2, y - h / 2, x + w / 2, y + h / 2], fill=(248, 232, 210, 255), outline=OUTLINE, width=4)
    for i in range(int(h)):   # soft painted background
        f = i / h
        d.line([(x - w / 2 + 4, y - h / 2 + i), (x + w / 2 - 4, y - h / 2 + i)], fill=(int(250 - 40 * f), int(214 - 30 * f), int(200 + 10 * f), 255))
    look = Look(p.get("color", "#e59ab0"), p.get("accessory", "flower"), p.get("acc_color"))
    sp, (ax, ay) = sprite(look.key(), p.get("face", "sleepy"), False, 0, 0, 0, 0, p.get("s", 14))
    sp = sp.rotate(p.get("tilt", -6), resample=Image.BICUBIC, expand=True)   # head bowed a little
    img.paste(sp, (int(x - sp.width / 2), int(y + h / 2 - sp.height + 30)), sp)
    add_glow(img, x, y, max(w, h) * 0.9, (255, 220, 170), 0.25 + 0.08 * math.sin(ctx["t"] * 1.3))


def fx_ripples(img, p, ctx):
    """Rings of water spreading out and closing around a spot (爱如潮水 它将你我包围)."""
    t = ctx["t"]
    x, y = p.get("x", 1075), p.get("y", 880)
    rx_max, ry_max = p.get("rx", 620), p.get("ry", 150)
    d = _d(img)
    n = int(p.get("n", 5))
    for k in range(n):
        ph = (t * p.get("speed", 0.25) + k / n) % 1.0
        f = 1 - ph if p.get("inward", True) else ph      # rings travel in towards the pair
        rx0, ry0 = p.get("rx_min", 120), p.get("ry_min", 30)
        rx, ry = rx0 + (rx_max - rx0) * f, ry0 + (ry_max - ry0) * f
        a = int(170 * math.sin(math.pi * ph))
        d.ellipse([x - rx, y - ry, x + rx, y + ry], outline=(225, 238, 255, a), width=5)
        d.ellipse([x - rx * 0.97, y - ry * 0.9, x + rx * 0.97, y + ry * 0.9], outline=(150, 180, 230, a // 2), width=2)


def draw(img, effects, ctx, back):
    for e in effects:
        name, p = (e, {}) if isinstance(e, str) else (e["name"], e)
        if (name in BACK) != back:
            continue
        fn = globals().get("fx_" + name)
        if fn:
            fn(img, p, ctx)
