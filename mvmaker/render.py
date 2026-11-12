"""Timeline planning + frame compositing + encoding."""
import math
import multiprocessing as mp
import random
import subprocess
import sys
import time
from functools import lru_cache

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from . import scenes as scn
from .character import BODY_H, LEG_H, Look, sprite
from .common import (FPS, H, OUTLINE, W, WH, WW, add_glow, draw_text, ease, glow_sprite, heart_points, hexrgb,
                     paper_overlay, star_points, text_width)
from .lyrics import load_audio

HEROES = [("#e08a52", "cap", None), ("#8c9bd6", "beanie", None), ("#f0c27a", "hair", None), ("#e07a6a", "beanie", "#f2c14e")]
PARTNERS = [("#e59ab0", "flower", None), ("#7fa7d8", "bow", None), ("#f3b8c8", "bow", "#d9534f")]
XFADE = 0.6


# ---------------------------------------------------------------- audio features
def audio_features(path, n_frames):
    sr = 22050
    a = load_audio(path, sr)
    hop = sr / FPS
    e = np.zeros(n_frames, np.float32)
    for f in range(n_frames):
        seg = a[int(f * hop):int((f + 1) * hop)]
        e[f] = float(np.sqrt(np.mean(seg * seg))) if len(seg) else 0.0
    ref = np.percentile(e, 95) or 1.0
    e = np.clip(e / ref, 0, 1.2)
    e = np.convolve(e, np.ones(3) / 3, mode="same")
    avg = np.convolve(e, np.ones(15) / 15, mode="same")
    pulse = np.clip((e - avg) * 3.0, 0, 1)
    return e, pulse


# ---------------------------------------------------------------- planning
class Actor:
    def __init__(self, look, expr, x0, x1, t_walk, emote=None, seated=False, scale=20, phase=0.0):
        self.look, self.expr, self.x0, self.x1, self.t_walk = look, expr, x0, x1, t_walk
        self.emote, self.seated, self.scale, self.phase = emote, seated, scale, phase


class Shot:
    def __init__(self, start, end, scene, actors, cam):
        self.start, self.end, self.scene, self.actors, self.cam = start, end, scene, actors, cam
        self.framing = "medium"


def plan_cuts(duration, lines, rng):
    cuts = [0.0]
    for ln in lines:
        s = ln.start - 0.35
        gap = s - cuts[-1]
        if s < duration - 6 and gap >= 6.5 and (gap >= 10 or rng.random() < 0.5):
            cuts.append(s)
    cuts.append(duration)
    out = [cuts[0]]
    for a, b in zip(cuts, cuts[1:]):
        n = int((b - a) // 11.0)          # break up long instrumental stretches
        for k in range(1, n + 1):
            if b - (a + k * (b - a) / (n + 1)) > 4:
                out.append(a + k * (b - a) / (n + 1))
        out.append(b)
    if len(out) > 2 and out[-1] - out[-2] < 5:
        out.pop(-2)
    return out


def choose_expr(scene_mood, flash, rng, song_mood="sad"):
    if song_mood == "melancholy" and not flash:
        # quiet sadness: mostly still faces, rarely open crying
        hero = rng.choice(["sad", "sad", "neutral", "neutral", "cry"] if scene_mood != "sweet" else ["neutral", "happy"])
        partner = rng.choice(["neutral", "sad", "happy"])
        emote = rng.choice([None, None, "cloud", "sparkle"])
        return hero, partner, emote
    if flash or scene_mood in ("sweet", "happy", "nostalgic"):
        hero = rng.choice(["happy", "happy", "love", "neutral"])
        partner = rng.choice(["happy", "love"])
        emote = rng.choice(["heart", "notes", "heart", None]) if hero != "neutral" else "sparkle"
    elif scene_mood == "sad":
        hero = rng.choice(["sad", "sad", "cry", "neutral"])
        partner = rng.choice(["neutral", "happy"])
        emote = rng.choice(["cloud", "cloud", None])
    elif scene_mood == "lonely":
        hero = rng.choice(["sad", "neutral", "sleepy"])
        partner = "neutral"
        emote = "zzz" if hero == "sleepy" else rng.choice([None, "cloud"])
    else:  # dreamy / melancholic
        hero = rng.choice(["neutral", "sad", "happy"])
        partner = rng.choice(["happy", "neutral"])
        emote = rng.choice(["sparkle", None])
    return hero, partner, emote


def plan(duration, lines, mood, seed):
    rng = random.Random(seed)
    hero = Look(*HEROES[rng.randrange(len(HEROES))])
    partner = Look(*PARTNERS[rng.randrange(len(PARTNERS))])
    opening, middle, flashes = scn.POOLS[mood]
    first = rng.choice(opening)
    # melancholy tells "evening into night": open at dusk, close somewhere dark and quiet
    last = rng.choice(["bedroom", "city_night"]) if mood == "melancholy" else first
    cuts = plan_cuts(duration, lines, rng)
    n = len(cuts) - 1
    mids = [m for m in middle if m != first] or middle[:]
    rng.shuffle(mids)
    fl = flashes[:]
    rng.shuffle(fl)
    share = {"melancholy": 0.15}.get(mood, 0.22)   # how many shots are warm flashbacks
    k = max(1, round(n * share)) if n >= 3 else 0
    flash_at = {int(n * (0.28 + 0.5 * j / max(1, k - 1))) if k > 1 else n // 2 for j in range(k)}
    seq, fi = [], 0
    for i in range(n):
        if i == 0:
            name, flash = first, False
        elif i == n - 1 and n > 2:
            name, flash = last, False
        elif i in flash_at:
            name, flash = fl[fi % len(fl)], True
            fi += 1
        else:
            recent = [x[0] for x in seq[-2:]]
            choices = [m for m in mids if m not in recent] or mids
            # prefer scenes used least so far, randomly among ties
            used = {m: sum(1 for x in seq if x[0] == m) for m in choices}
            low = min(used.values())
            name, flash = rng.choice([m for m in choices if used[m] == low]), False
        seq.append((name, flash))

    built = {}
    for name, _ in seq:
        if name not in built:
            built[name] = scn.build(name, seed * 31 + len(built))
    glow_sprite.cache_clear()

    shots = []
    for i, (name, flash) in enumerate(seq):
        sc = built[name]
        a, b = cuts[i], cuts[i + 1]
        D = b - a
        hx, px, pe = choose_expr(sc.mood, flash, rng, mood)
        pair = sc.seated is not None or flash or (sc.mood in ("sweet", "happy") and rng.random() < 0.7) or \
            (0 < i < n - 1 and rng.random() < (0.45 if mood == "sweet" else 0.3))
        if i == n - 1 and n > 2:
            pair = False   # closing shot: alone again, like the opening
        actors = []
        framing = "medium"
        if pair:
            s = sc.char_scale
            if sc.seated is None and rng.random() < 0.4:
                t_walk = min(D * 0.55, 4.0)
                actors.append(Actor(hero, hx, -260, sc.slots[0], t_walk, emote=pe, scale=s))
                actors.append(Actor(partner, px, -520, sc.slots[1], t_walk, scale=s, phase=0.7))
            else:
                actors.append(Actor(hero, hx, sc.slots[0], sc.slots[0], 0, emote=pe, seated=sc.seated is not None, scale=s))
                actors.append(Actor(partner, px, sc.slots[1], sc.slots[1], 0, seated=sc.seated is not None, scale=s, phase=0.7))
        else:
            s = sc.char_scale + 3
            x = sc.slots[2]
            r = rng.random()
            if i == 0:
                actors.append(Actor(hero, hx, -300, x, min(D * 0.6, 6.0), emote=pe, scale=s))
            elif r < 0.3 and i < n - 1:
                framing = "close"
                actors.append(Actor(hero, hx, x, x, 0, emote=pe, scale=sc.char_scale + 12))
            elif r < 0.45:
                framing = "wide"
                actors.append(Actor(hero, hx, x - 520, x + 380, D, emote=None, scale=sc.char_scale - 5))
            elif r < 0.6:
                actors.append(Actor(hero, hx, x - 260, x + 200, D, emote=pe, scale=s))
            elif r < 0.72:
                actors.append(Actor(hero, hx, -300, x, min(D * 0.5, 4.5), emote=pe, scale=s))
            else:
                actors.append(Actor(hero, hx, x, x, 0, emote=pe, scale=s))
        if framing == "close":
            z0, z1 = rng.choice([(1.12, 1.2), (1.2, 1.14)])
            cx = actors[0].x1 + rng.uniform(-40, 40)
            cam = (z0, z1, cx, cx + rng.uniform(-30, 30), sc.ground - 260)
        elif framing == "wide":
            cam = (1.0, 1.0, WW / 2 - 40, WW / 2 + 40, WH / 2 + 20)
        else:
            z0, z1 = rng.choice([(1.0, 1.07), (1.07, 1.0), (1.02, 1.1), (1.0, 1.04)])
            dx = rng.uniform(-50, 50)
            cam = (z0, z1, WW / 2 + dx, WW / 2 - dx, WH / 2 + 20)
        shots.append(Shot(a, b, sc, actors, cam))
        shots[-1].framing = framing
    return shots


# ---------------------------------------------------------------- particles
class Particles:
    def __init__(self, seed):
        r = np.random.default_rng(seed)
        self.rain = r.random((170, 4))
        self.snow = r.random((170, 5))
        self.petal = r.random((28, 6))
        self.dust = r.random((70, 5))
        self.fly = r.random((32, 5))

    def draw(self, img, kind, t):
        if not kind or kind == "none":
            return
        d = ImageDraw.Draw(img, "RGBA")
        if kind == "storm":   # heavy, wind-driven rain
            for x0, y0, v, ln in self.rain:
                v = 2400 + v * 900
                L = 50 + ln * 60
                y = (y0 * (H + 200) + v * t) % (H + 200) - 100
                x = (x0 * (W + 600) - 0.45 * v * t) % (W + 600) - 300
                d.line([(x, y), (x - 0.45 * L, y + L)], fill=(215, 222, 255, int(90 + 80 * ln)), width=3)
            return
        if kind == "sand":    # wind blowing sand sideways
            for x0, y0, v, ln in self.rain[:120]:
                v = 900 + v * 700
                x = (x0 * (W + 300) + v * t) % (W + 300) - 150
                y = H * 0.35 + y0 * H * 0.65 + 20 * math.sin(t * 3 + x0 * 9)
                d.line([(x, y), (x + 25 + 40 * ln, y + 3)], fill=(235, 205, 160, int(80 + 90 * ln)), width=2)
            return
        if kind == "rain":
            for x0, y0, v, ln in self.rain:
                v = 1700 + v * 900
                L = 28 + ln * 40
                y = (y0 * (H + 200) + v * t) % (H + 200) - 100
                x = (x0 * (W + 300) + 0.16 * v * t) % (W + 300) - 150
                d.line([(x, y), (x + 0.16 * L, y + L)], fill=(205, 215, 255, int(70 + 70 * ln)), width=2)
        elif kind == "snow":
            for x0, y0, v, sz, ph in self.snow:
                v = 50 + v * 110
                y = (y0 * (H + 40) + v * t) % (H + 40) - 20
                x = (x0 * W + 35 * math.sin(t * (0.6 + ph) + ph * 6) + 20 * t) % W
                r = 2 + sz * 5
                d.ellipse([x - r, y - r, x + r, y + r], fill=(255, 255, 255, int(170 + 70 * sz)))
        elif kind in ("petals", "leaves"):
            n = 28 if kind == "petals" else 14
            cols = [(240, 180, 190), (250, 205, 210)] if kind == "petals" else [(170, 180, 100), (220, 160, 80), (200, 120, 70)]
            for k, (x0, y0, v, sz, ph, rot) in enumerate(self.petal[:n]):
                v = 60 + v * 90
                y = (y0 * (H + 60) + v * t) % (H + 60) - 30
                x = (x0 * (W + 200) + 50 * t + 60 * math.sin(t * 0.9 + ph * 6)) % (W + 200) - 100
                a = t * (1 + rot * 2) + ph * 6
                rx, ry = 10 + sz * 6, 5 + sz * 3
                pts = []
                for i in range(12):
                    th = 2 * math.pi * i / 12
                    px, py = rx * math.cos(th), ry * math.sin(th)
                    pts.append((x + px * math.cos(a) - py * math.sin(a), y + px * math.sin(a) + py * math.cos(a)))
                d.polygon(pts, fill=cols[k % len(cols)] + (225,), outline=OUTLINE + (120,))
        elif kind == "dust":
            for x0, y0, sz, ph, sp in self.dust:
                x = (x0 * W + 25 * math.sin(t * 0.3 + ph * 6) + 8 * t * (sp - 0.5)) % W
                y = (y0 * H - 12 * t * sp) % H
                a = int(40 + 90 * (0.5 + 0.5 * math.sin(t * (1 + sp) + ph * 6)))
                r = 1.5 + sz * 2.5
                d.ellipse([x - r, y - r, x + r, y + r], fill=(255, 240, 205, a))
        elif kind == "fireflies":
            for x0, y0, sz, ph, sp in self.fly:
                x = x0 * W + 60 * math.sin(t * (0.3 + sp * 0.4) + ph * 6)
                y = H * 0.35 + y0 * H * 0.55 + 40 * math.sin(t * (0.25 + sz * 0.3) + ph * 3)
                b = 0.5 + 0.5 * math.sin(t * (1.5 + sp) + ph * 9)
                d.ellipse([x - 10, y - 10, x + 10, y + 10], fill=(230, 255, 150, int(45 * b)))
                d.ellipse([x - 3, y - 3, x + 3, y + 3], fill=(240, 255, 190, int(60 + 180 * b)))


# ---------------------------------------------------------------- emotes
def draw_emote(img, kind, x, top, t, s):
    d = ImageDraw.Draw(img, "RGBA")
    if kind == "cloud":
        cy = top - 70 * s + 5 * math.sin(t * 2)
        for dx, dy, r in ((-38, 6, 30), (0, -10, 40), (40, 6, 30), (0, 14, 30)):
            r *= s
            d.ellipse([x + dx * s - r, cy + dy * s - r, x + dx * s + r, cy + dy * s + r], fill=(150, 156, 178), outline=OUTLINE, width=max(2, int(4 * s)))
        for dx, dy, r in ((-38, 6, 30), (0, -10, 40), (40, 6, 30), (0, 14, 30)):
            r = (r - 4) * s
            d.ellipse([x + dx * s - r, cy + dy * s - r, x + dx * s + r, cy + dy * s + r], fill=(150, 156, 178))
        for k in range(5):
            ph = (t * 1.8 + k * 0.37) % 1.0
            rx = x + (-48 + k * 24) * s
            ry = cy + 30 * s + ph * 70 * s
            d.line([(rx, ry), (rx - 2, ry + 14 * s)], fill=(140, 190, 240, int(230 * (1 - ph))), width=max(2, int(4 * s)))
    elif kind == "heart":
        for k in range(2):
            ph = (t * 0.45 + k * 0.5) % 1.0
            hx = x + (40 + 30 * k) * s * (1 if k else -1) + 10 * math.sin(t * 3 + k)
            hy = top - 20 * s - ph * 130 * s
            sz = (20 + 8 * math.sin(ph * math.pi)) * s
            a = int(255 * min(1, (1 - ph) * 2.2))
            d.polygon(heart_points(hx, hy, sz), fill=(242, 92, 120, a), outline=OUTLINE + (a,))
    elif kind == "notes":
        for k in range(2):
            ph = (t * 0.5 + k * 0.5) % 1.0
            nx = x + (60 if k else -70) * s + 20 * math.sin(t * 2 + k)
            ny = top - 10 * s - ph * 120 * s
            a = int(255 * min(1, (1 - ph) * 2))
            r = 11 * s
            d.ellipse([nx - r, ny - r * 0.8, nx + r, ny + r * 0.8], fill=OUTLINE + (a,))
            d.line([(nx + r - 2, ny), (nx + r - 2, ny - 42 * s), (nx + r + 16 * s, ny - 32 * s)], fill=OUTLINE + (a,), width=max(2, int(5 * s)))
    elif kind == "zzz":
        from .common import font
        for k in range(3):
            ph = (t * 0.4 + k / 3) % 1.0
            a = int(255 * min(1, (1 - ph) * 2))
            fs = int((30 + 14 * k) * s)
            d.text((x + 60 * s + ph * 60 * s, top - 20 * s - ph * 110 * s), "Z", font=font("fallback", fs),
                   fill=(240, 240, 255, a), stroke_width=max(1, int(3 * s)), stroke_fill=OUTLINE + (a,), anchor="ms")
    elif kind == "sparkle":
        for k, (dx, dy) in enumerate(((-90, -10), (95, -40), (60, -90))):
            b = 0.5 + 0.5 * math.sin(t * 3 + k * 2.1)
            r = (10 + 14 * b) * s
            d.polygon(star_points(x + dx * s, top + dy * s, r, r * 0.3), fill=(255, 245, 200, int(120 + 135 * b)))


# ---------------------------------------------------------------- title card
TITLE_THEMES = {
    "default": {"fill": (249, 241, 222), "stroke": OUTLINE, "line": (226, 178, 58), "artist": (238, 192, 84), "astroke": OUTLINE},
    "sweet": {"fill": (255, 251, 253), "stroke": (196, 82, 128), "line": (247, 160, 190), "artist": (255, 255, 255), "astroke": (226, 104, 150)},
}


class TitleCard:
    def __init__(self, title, artist, end_time, theme="default"):
        th = TITLE_THEMES.get(theme, TITLE_THEMES["default"])
        self.end = end_time
        self.title, self.artist = title, artist
        size = 190
        while size > 90 and text_width(title, "brush", size) > 1050:
            size -= 10
        self.size = size
        self.x, self.base = 230, 400
        self.chars = []
        x = self.x
        for ch in title:
            w = text_width(ch, "brush", size)
            img = Image.new("RGBA", (int(w + 60), int(size * 1.6)), (0, 0, 0, 0))
            dd = ImageDraw.Draw(img)
            draw_text(dd, 30 + 6, size * 1.25 + 7, ch, "brush", size, (20, 14, 26, 110), stroke_width=9, stroke_fill=(20, 14, 26, 110))
            img = img.filter(ImageFilter.GaussianBlur(4))
            dd = ImageDraw.Draw(img)
            draw_text(dd, 30, size * 1.25, ch, "brush", size, th["fill"], stroke_width=8, stroke_fill=th["stroke"])
            self.chars.append((img, x - 30, self.base - size * 1.25))
            x += w + size * 0.04
        self.width = x - self.x
        # brush underline
        uw = int(self.width + 40)
        ul = Image.new("RGBA", (uw + 20, 40), (0, 0, 0, 0))
        ud = ImageDraw.Draw(ul)
        pts_top = [(10 + i, 18 - 6 * math.sin(i / uw * math.pi) + 3 * (i / uw)) for i in range(0, uw, 8)]
        pts_bot = [(10 + i, 18 - 6 * math.sin(i / uw * math.pi) + 3 * (i / uw) + 3 + 7 * math.sin(min(1, i / uw * 1.3) * math.pi)) for i in range(0, uw, 8)]
        ud.polygon(pts_top + pts_bot[::-1], fill=th["line"], outline=th["stroke"])
        self.underline = ul
        self.ul_pos = (self.x - 30, int(self.base + 18))
        asz = max(46, int(size * 0.36))
        aw = text_width(artist, "brush", asz) if artist else 0
        ai = Image.new("RGBA", (int(aw + 40), int(asz * 1.6)), (0, 0, 0, 0))
        if artist:
            draw_text(ImageDraw.Draw(ai), 20, asz * 1.2, artist, "brush", asz, th["artist"], stroke_width=4, stroke_fill=th["astroke"])
        self.artist_img = ai
        self.artist_pos = (int(self.x + self.width / 2 - ai.width / 2), int(self.base + 60))

    def draw(self, img, t):
        if t > self.end + 0.7 or t < 0.4:
            return
        out = 1.0 - ease((t - self.end) / 0.7)
        t0 = 0.5
        for i, (ch, x, y) in enumerate(self.chars):
            p = ease((t - t0 - i * 0.14) / 0.35)
            if p <= 0:
                continue
            sc = 1.35 - 0.35 * p
            im = ch if abs(sc - 1) < 0.01 else ch.resize((int(ch.width * sc), int(ch.height * sc)), Image.BILINEAR)
            a = p * out
            if a < 1:
                im = im.copy()
                im.putalpha(im.getchannel("A").point(lambda v: int(v * a)))
            img.paste(im, (int(x + ch.width / 2 - im.width / 2), int(y + ch.height / 2 - im.height / 2)), im)
        tu = t0 + len(self.chars) * 0.14 + 0.1
        p = ease((t - tu) / 0.5)
        if p > 0:
            w = max(1, int(self.underline.width * p))
            ul = self.underline.crop((0, 0, w, self.underline.height))
            if out < 1:
                ul.putalpha(ul.getchannel("A").point(lambda v: int(v * out)))
            img.paste(ul, self.ul_pos, ul)
        p = ease((t - tu - 0.4) / 0.5)
        if p > 0 and self.artist:
            ai = self.artist_img
            if p * out < 1:
                ai = ai.copy()
                ai.putalpha(ai.getchannel("A").point(lambda v: int(v * p * out)))
            img.paste(ai, (self.artist_pos[0], int(self.artist_pos[1] + 15 * (1 - p))), ai)


# ---------------------------------------------------------------- subtitles
class Subtitles:
    def __init__(self, lines, style="paper", seed=0):
        self.lines = lines
        self.style = style
        self.rng = random.Random(seed)
        self.angles = [self.rng.uniform(-1.0, 1.0) if style == "paper" else 0 for _ in lines]
        self.cache = {}

    def _build(self, i):
        if i in self.cache:
            return self.cache[i]
        if len(self.cache) > 6:
            self.cache.pop(next(iter(self.cache)))
        ln = self.lines[i]
        fname = "hand" if self.style in ("paper", "candy") else "brush"
        size = 62 if self.style in ("paper", "candy") else 54
        while size > 34 and text_width(ln.text, fname, size) > 1500:
            size -= 4
        tw = text_width(ln.text, fname, size)
        if self.style == "paper":
            padl, padr, h = 80, 50, 104
        elif self.style == "candy":
            padl, padr, h = 92, 60, 100
        else:
            padl, padr, h = 70, 70, 92
        sw, sh = int(tw + padl + padr), h
        m = 30
        base = Image.new("RGBA", (sw + 2 * m, sh + 2 * m), (0, 0, 0, 0))
        d = ImageDraw.Draw(base)
        if self.style == "paper":
            d.rectangle([m + 4, m + 7, m + sw + 4, m + sh + 7], fill=(0, 0, 0, 70))
            base = base.filter(ImageFilter.GaussianBlur(6))
            d = ImageDraw.Draw(base, "RGBA")
            d.rectangle([m, m, m + sw, m + sh], fill=(251, 249, 242, 248))
            for y in (m + 30, m + sh - 26):
                d.line([(m, y), (m + sw, y)], fill=(160, 185, 230, 150), width=2)
            d.line([(m + 44, m), (m + 44, m + sh)], fill=(228, 130, 130, 180), width=2)
            d.polygon([(m - 18, m + 8), (m + 50, m - 16), (m + 62, m + 14), (m - 6, m + 38)], fill=(242, 160, 182, 150))
        elif self.style == "candy":   # cute: a white pill with a pink border and a little heart
            d.rounded_rectangle([m + 3, m + 8, m + sw + 3, m + sh + 8], radius=sh // 2, fill=(240, 130, 170, 90))
            base = base.filter(ImageFilter.GaussianBlur(5))
            d = ImageDraw.Draw(base, "RGBA")
            d.rounded_rectangle([m, m, m + sw, m + sh], radius=sh // 2, fill=(255, 251, 253, 250), outline=(247, 150, 186, 255), width=6)
            d.rounded_rectangle([m + 12, m + 12, m + sw - 12, m + sh - 12], radius=sh // 2 - 12, outline=(252, 214, 228, 255), width=3)
            d.polygon(heart_points(m + 52, m + sh / 2, 22), fill=(244, 112, 158, 255), outline=(196, 82, 128, 255))
        else:
            d.polygon([(m + 20, m + 4), (m + sw - 20, m), (m + sw, m + sh / 2), (m + sw - 22, m + sh), (m + 22, m + sh - 3), (m, m + sh / 2)],
                      fill=(70, 50, 72, 235), outline=OUTLINE)
        baseline = m + sh * (0.68 if self.style in ("paper", "candy") else 0.7)
        x0 = m + padl
        dim = Image.new("RGBA", base.size, (0, 0, 0, 0))
        ink = Image.new("RGBA", base.size, (0, 0, 0, 0))
        if self.style == "paper":
            draw_text(ImageDraw.Draw(dim), x0, baseline, ln.text, fname, size, (182, 176, 186))
            draw_text(ImageDraw.Draw(ink), x0, baseline, ln.text, fname, size, (100, 38, 72))
        elif self.style == "candy":
            draw_text(ImageDraw.Draw(dim), x0, baseline, ln.text, fname, size, (226, 190, 204))
            draw_text(ImageDraw.Draw(ink), x0, baseline, ln.text, fname, size, (214, 72, 126))
        else:
            draw_text(ImageDraw.Draw(dim), x0, baseline, ln.text, fname, size, (150, 128, 96))
            draw_text(ImageDraw.Draw(ink), x0, baseline, ln.text, fname, size, (244, 196, 92))
        marks = [(x0 + text_width(ln.text[:a], fname, size), x0 + text_width(ln.text[:b], fname, size), ts, te)
                 for a, b, ts, te in ln.tokens]
        self.cache[i] = (base, dim, ink, marks)
        return self.cache[i]

    def _cut(self, marks, t):
        if not marks:
            return 1e9
        x = marks[0][0]
        for xa, xb, ts, te in marks:
            if t >= te:
                x = xb
            elif t > ts:
                x = xa + (xb - xa) * (t - ts) / max(0.05, te - ts)
                break
            else:
                break
        return x

    def draw(self, img, t):
        for i, ln in enumerate(self.lines):
            nxt = self.lines[i + 1].start if i + 1 < len(self.lines) else 1e9
            show0, show1 = ln.start - 0.3, min(ln.end + 0.6, nxt - 0.15)
            if not (show0 <= t <= show1):
                continue
            base, dim, ink, marks = self._build(i)
            a = min(ease((t - show0) / 0.2), ease((show1 - t) / 0.2))
            comp = base.copy()
            comp.alpha_composite(dim)
            cut = int(self._cut(marks, t))
            if cut > 0:
                comp.alpha_composite(ink.crop((0, 0, min(cut, ink.width), ink.height)), (0, 0))
            if self.angles[i]:
                comp = comp.rotate(self.angles[i], resample=Image.BICUBIC, expand=True)
            if a < 1:
                comp.putalpha(comp.getchannel("A").point(lambda v: int(v * a)))
            y = int(H - 70 - comp.height / 2 + 14 * (1 - a))
            img.paste(comp, (int(W / 2 - comp.width / 2), y), comp)
            return


# ---------------------------------------------------------------- the project / frame renderer
class Project:
    def __init__(self, audio, duration, lines, title, artist, mood="sad", style="paper", seed=1, story=None):
        self.audio, self.duration = audio, duration
        self.n_frames = int(duration * FPS)
        self.energy, self.pulse = audio_features(audio, self.n_frames)
        self.lines = lines
        self.mood, self.seed = mood, seed
        self.title_text, self.artist = title, artist
        self.story = story
        if story:   # storyboard mode: every shot written for its lyric lines
            from .story import plan_story
            self.shots = plan_story(story, lines, duration, seed)
        else:       # template mode: scenes picked from mood pools
            self.shots = plan(duration, lines, mood, seed)
        self.cover_shot = (story or {}).get("cover")
        first = lines[0].start if lines else 8
        self.title = TitleCard(title, artist, max(4.5, min(first - 0.8, 9.0)), theme="sweet" if mood == "sweet" else "default")
        self.subs = Subtitles(lines, style, seed)
        self.particles = Particles(seed)
        # evening grade for melancholy: a little cooler/violet, deeper vignette
        self.grade = {"melancholy": (0.96, 0.94, 1.0), "sweet": (1.0, 0.975, 0.985)}.get(mood)
        self.overlay = paper_overlay(W, H, seed, vignette={"melancholy": 0.4, "sweet": 0.18}.get(mood, 0.32), tint=self.grade)
        # sweet: lift the shadows towards candy pink so nothing reads as dark and heavy
        self.lift = Image.new("RGB", (W, H), (34, 20, 30)) if mood == "sweet" else None
        self.singing = np.zeros(self.n_frames, bool)
        for ln in lines:
            self.singing[int(ln.start * FPS):int(ln.end * FPS)] = True

    def describe(self):
        for s in self.shots:
            acts = s.framing + ": " + ", ".join(f"{a.expr}{'/' + a.emote if a.emote else ''}" for a in s.actors
                                                if getattr(a, "who", "hero") != "crowd")
            note = getattr(s, "note", "")
            print(f"  {s.start:6.1f}-{s.end:6.1f}s  {s.scene.name:<11} {acts}  {note}", file=sys.stderr)

    def shot_at(self, t):
        for i, s in enumerate(self.shots):
            if s.start <= t < s.end:
                return i
        return len(self.shots) - 1

    def render_shot(self, shot, t, f):
        world = self.render_world(shot, t, f)
        return self.camera(shot, world, t)

    def render_world(self, shot, t, f, actors=True):
        """The scene at world resolution (before the camera): glows, stars, characters, emotes, foreground."""
        sc = shot.scene
        lt = t - shot.start
        D = max(0.1, shot.end - shot.start)
        world = sc.bg.copy()
        pulse = float(self.pulse[min(f, self.n_frames - 1)])
        for (x, y, r, col, base, kind) in sc.glows:
            k = 1.0
            if kind.startswith("neon"):
                k = 0.85 + 0.15 * math.sin(t * 7 + len(kind)) + (-.5 if (int(t * 10) % 37 == 0 and kind == "neon") else 0)
            elif kind.startswith("twinkle"):
                k = 0.7 + 0.3 * math.sin(t * 2.5 + len(kind) * 1.7)
            elif kind == "lamp":
                k = 0.92 + 0.06 * math.sin(t * 13) * math.sin(t * 3.1)
            elif kind == "breath":
                k = 0.85 + 0.15 * math.sin(t * 0.8)
            add_glow(world, x, y, r, col, base * k + 0.25 * pulse)
        if sc.stars:
            d = ImageDraw.Draw(world, "RGBA")
            for j, (x, y, s) in enumerate(sc.stars):
                b = 0.5 + 0.5 * math.sin(t * (1.3 + (j % 5) * 0.4) + j)
                r = s * (1.0 + 1.6 * b)
                d.polygon(star_points(x, y, r * 2.2, r * 0.5), fill=(255, 255, 240, int(90 + 150 * b)))

        shot_fx = getattr(shot, "fx", None)
        ctx = {"sc": sc, "t": t, "lt": lt, "D": D, "seed": self.seed + int(shot.start * 10)}
        if shot_fx:
            from . import fx as fxm
            fxm.draw(world, shot_fx, ctx, back=True)
        if getattr(shot, "note", None) is not None and actors:   # storyboard actors
            from .story import draw_actor
            e = float(self.energy[min((f // 3) * 3, self.n_frames - 1)])
            sing = bool(self.singing[min(f, self.n_frames - 1)])
            # crowd extras first, named characters on top of them
            order = sorted(range(len(shot.actors)), key=lambda i: (shot.actors[i].who != "crowd", shot.actors[i].sort_y))
            # the foreground layer (bench seat, desks…) covers only characters behind it (fg_y); people standing in
            # front of the bench are drawn after it
            fg_y = getattr(sc, "fg_y", None)
            front = [i for i in order if fg_y is not None and shot.actors[i].sort_y % 10000 > fg_y]
            for i in order:
                if i not in front:
                    draw_actor(world, shot.actors[i], ctx, f, i, e, pulse, sing)
            if sc.fg is not None:
                world.paste(sc.fg, (0, 0), sc.fg)
            for i in front:
                draw_actor(world, shot.actors[i], ctx, f, i, e, pulse, sing)
            if shot_fx:
                fxm.draw(world, shot_fx, ctx, back=False)
            return world
        boil = int(f / 5) % 3
        for ai, a in enumerate(shot.actors if actors else []):
            s = a.scale / 20.0
            if a.t_walk > 0 and lt < a.t_walk:
                p = max(0.0, lt) / a.t_walk
                if a.t_walk < D - 0.2:
                    p = ease(p) * 0.3 + p * 0.7
                x = a.x0 + (a.x1 - a.x0) * p
                walking = True
            else:
                x, walking = a.x1, False
            sing = self.singing[min(f, self.n_frames - 1)] and ai == 0
            e = float(self.energy[min((f // 3) * 3, self.n_frames - 1)])
            mouth = (2 if e > 0.75 else 1 if e > 0.45 else 0) if sing else 0
            blink = ((t + a.phase * 2.3) % 3.7) < 0.14
            if a.seated:
                legs = 3
            elif walking:
                legs = 1 + int((t + a.phase) * 5) % 2
            else:
                legs = 0
            arms = 0
            if a.expr in ("happy", "love") and not walking and ((t + a.phase * 3) % 5.0) < 1.4:
                arms = 2 if a.expr == "love" else (1 if ai else 2)
            img, (axx, ayy) = sprite(a.look.key(), a.expr, blink, mouth, legs, arms, boil, a.scale, sc.tint)
            if walking:
                bob = -abs(math.sin((t + a.phase) * math.pi * 2.5)) * 8 * s
            else:
                bob = -(math.sin((t + a.phase) * 2.2) * 0.5 + 0.5) * 4 * s - pulse * 9 * s
            y = (sc.seated + LEG_H * s) if a.seated else sc.ground
            world.paste(img, (int(x - axx), int(y - ayy + bob)), img)
            if a.emote and (not walking or a.emote in ("cloud",)):
                hat = {"beanie": 80, "cap": 50, "flower": 15, "bow": 20, "hair": 10}.get(a.look.accessory, 0)
                top = y - (BODY_H + LEG_H) * s + bob - hat * s
                draw_emote(world, a.emote, x, top, t, s)
        if sc.fg is not None and actors:
            world.paste(sc.fg, (0, 0), sc.fg)
        return world

    def camera(self, shot, world, t):
        sc = shot.scene
        lt = t - shot.start
        D = max(0.1, shot.end - shot.start)
        z0, z1, cx0, cx1, cy0, *rest = shot.cam
        cy1 = rest[0] if rest else cy0
        p = ease(min(1.0, max(0.0, lt / D)))
        z = z0 + (z1 - z0) * p
        cx = cx0 + (cx1 - cx0) * p
        cy = cy0 + (cy1 - cy0) * p
        cw, ch = W / z, H / z
        cx = min(max(cx, cw / 2), WW - cw / 2)
        cy = min(max(cy, ch / 2), WH - ch / 2)
        view = world.resize((W, H), Image.BILINEAR, box=(cx - cw / 2, cy - ch / 2, cx + cw / 2, cy + ch / 2))
        self.particles.draw(view, getattr(shot, "weather", sc.particles), t)
        return view

    def render(self, f):
        t = f / FPS
        i = self.shot_at(t)
        img = self.render_shot(self.shots[i], t, f)
        # crossfade around cuts
        if i > 0 and t - self.shots[i].start < XFADE / 2:
            prev = self.render_shot(self.shots[i - 1], t, f)
            img = Image.blend(prev, img, 0.5 + (t - self.shots[i].start) / XFADE)
        elif i + 1 < len(self.shots) and self.shots[i].end - t < XFADE / 2:
            nxt = self.render_shot(self.shots[i + 1], t, f)
            img = Image.blend(img, nxt, 0.5 - (self.shots[i].end - t) / XFADE)
        img = ImageChops.multiply(img, self.overlay)
        if self.lift is not None:
            img = ImageChops.screen(img, self.lift)
        self.title.draw(img, t)
        self.subs.draw(img, t)
        fade = min(1.0, t / 0.8, (self.duration - t) / 2.0)
        if fade < 1:
            img = Image.blend(Image.new("RGB", (W, H)), img, max(0.0, fade))
        return img


_PROJ = None


def _render_bytes(f):
    return _PROJ.render(f).tobytes()


def encode(project, out_path, start=0.0, length=None, workers=None, crf=22, maxrate=None, max_mb=85):
    global _PROJ
    _PROJ = project
    f0 = int(start * FPS)
    f1 = project.n_frames if length is None else min(project.n_frames, f0 + int(length * FPS))
    workers = workers or max(1, (mp.cpu_count() or 2) - 1)
    if maxrate is None:
        # 2.2 Mbit/s normally; lower for long songs so the file stays under ~85 MB (GitHub's limit is 100 MB)
        secs = (f1 - f0) / FPS
        kbps = int(min(2200, max(900, (max_mb * 8e6 / max(secs, 1) - 200e3) / 1000)))
        maxrate = f"{kbps}k"
    bufsize = f"{int(maxrate.rstrip('k')) * 2}k"
    cmd = ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
           "-i", "-", "-ss", f"{f0 / FPS:.3f}", "-i", project.audio, "-map", "0:v:0", "-map", "1:a:0",
           "-c:v", "libx264", "-preset", "medium", "-crf", str(crf), "-maxrate", maxrate, "-bufsize", bufsize,
           "-tune", "animation", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-shortest", "-map_chapters", "-1", "-movflags", "+faststart", out_path]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    t0 = time.time()
    ctx = mp.get_context("fork")
    with ctx.Pool(workers) as pool:
        for k, buf in enumerate(pool.imap(_render_bytes, range(f0, f1), chunksize=4)):
            proc.stdin.write(buf)
            if k % (FPS * 10) == 0 and k:
                el = time.time() - t0
                print(f"  {k / FPS:6.1f}s / {(f1 - f0) / FPS:.1f}s rendered  ({el:.0f}s elapsed, ~{el / k * (f1 - f0 - k):.0f}s left)",
                      file=sys.stderr)
    proc.stdin.close()
    if proc.wait() != 0:
        raise RuntimeError("ffmpeg failed")
    print(f"> done in {time.time() - t0:.0f}s -> {out_path}", file=sys.stderr)
