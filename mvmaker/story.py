"""Storyboard mode: every shot is written for its lyric lines (songs/<name>/<name>.story.json).

Storyboard format (world coordinates are 2150 x 1209; the frame shows the middle ~1920 x 1080):
{
  "hero": ["#e08a52", "cap"], "partner": ["#e59ab0", "flower"],      # optional looks
  "cover": 3,                                                       # optional: shot index used for the covers
  "cover_face": "neutral",                                          # optional: lead's face on the covers
  "mood": "sweet",                                                  # optional: whole-video look (melancholy | sad | sweet)
  "shots": [
    {"lines": [5, 6],                 # lyric line indexes this shot illustrates (or "from": seconds, for instrumentals)
     "note": "一个岛锁住一个人",          # the lyric, for humans
     "set": "island", "time": "night",  # scenery (see sets.SETS) and dusk/night/storm/day
     "cast": [{"who": "hero", "x": 1000, "face": "sad", "act": "sit", "back": true, "umbrella": "#d9473f",
               "x1": 1300, "y": 900, "y1": 700, "s": 20, "s1": 12, "fade": "out", "emote": "cloud"},
              {"who": "crowd", "n": 10, "umbrella": true}],
     "fx": ["waves", {"name": "tide", "amp": 120}, {"name": "sand_heart", "x": 700, "tide": {"amp": 120}}],
     "weather": "rain",                # rain | storm | snow | sand | dust | fireflies | petals | leaves | none
     "cam": "pull"}                    # push | pull | pan_left | pan_right | close | static
  ]
}
who: hero ("I"), partner ("you"), extra (a third person, e.g. the one who took my place), crowd.
acts: stand, walk (x -> x1), sit, float, sink (y -> y1), boat (sits in a rocking boat), dance.
more cast keys: "look": [colour, accessory, accessory colour] (e.g. white "hair" for old age), "scarf": colour,
  "phone": true (glowing phone in hand), "umbrella_dx": px (shift the umbrella over someone beside you),
  "hull": 0 (sit in someone else's boat; 1.5 = a wider boat for two), "z": 1 (draw on top), "arms": 0/1/2,
  crowd: {"who": "crowd", "n": 12, "umbrella": true, "colorful": true}
"""
import json
import math
import random
import sys

from PIL import Image, ImageDraw

from . import fx as fxm
from . import sets
from .character import BODY_H, LEG_H, Look, sprite
from .common import OUTLINE, WH, WW, add_glow, ease, hexrgb

GREYS = ["#7d8496", "#8a8fa0", "#6f7688", "#9095a5", "#767b8c"]


class SActor:
    def __init__(self, look, d, scene):
        self.look = Look(*d["look"]) if d.get("look") else look   # e.g. white hair for old age: ["#e08a52","hair","#eeeeee"]
        self.who = d.get("who", "hero")
        self.face = d.get("face", "sad")
        self.act = d.get("act", "stand")
        self.back = d.get("back", False)
        self.x0 = d.get("x", scene.slots[2])
        self.x1 = d.get("x1", self.x0)
        seat = getattr(scene, "seated", None)
        default_y = seat + LEG_H * d.get("s", 20) / 20 if (self.act == "sit" and seat) else scene.ground
        self.y0 = d.get("y", default_y)
        self.y1 = d.get("y1", self.y0)
        self.s0 = d.get("s", 20)
        self.s1 = d.get("s1", self.s0)
        self.t0, self.t1 = d.get("t0", 0.0), d.get("t1", 1.0)   # fraction of the shot the move takes
        self.fade = d.get("fade")
        self.umbrella = d.get("umbrella")
        if self.umbrella is True:
            self.umbrella = "#d9473f"
        self.emote = d.get("emote")
        self.umbrella_dx = d.get("umbrella_dx", 30)   # shift the umbrella to shelter someone beside you
        self.hull = d.get("hull", 1.0)                 # boat hull size; 0 = sitting in someone else's boat
        self.scarf = d.get("scarf")                    # colour of a scarf
        self.phone = d.get("phone", False)             # holding a glowing phone
        self.z = d.get("z", 0)                         # drawing order among named characters
        self.arms = d.get("arms", 0)
        self.phase = d.get("phase", random.random() * 3)
        self.sort_y = max(self.y0, self.y1) + 10000 * d.get("z", 0)
        # compatibility with the template renderer / covers
        self.expr, self.scale, self.x1_ = self.face, self.s0, self.x1


def crowd(d, scene, rng):
    out = []
    n = d.get("n", 10)
    palette = ["#e8a87c", "#85c1c8", "#f2d06b", "#c3a6e0", "#9fd39a", "#f19aa8"] if d.get("colorful") else GREYS
    for k in range(n):
        row = k % 2
        s = 15 if row == 0 else 23
        y = scene.ground - (45 if row == 0 else -25)
        dirn = 1 if rng.random() < 0.5 else -1
        span = rng.uniform(500, 1100)
        x0 = rng.uniform(-200, WW + 200)
        a = SActor(Look(rng.choice(palette), None), {"face": rng.choice(["neutral", "neutral", "sad"]), "act": "walk",
                    "x": x0, "x1": x0 + dirn * span, "y": y, "s": s, "back": rng.random() < 0.3,
                    "umbrella": "#4a4f63" if d.get("umbrella") else None}, scene)
        a.who = "crowd"
        out.append(a)
    return out


def camera(spec, scene, actors, rng):
    focus = actors[0] if actors else None
    cy = WH / 2 + 20
    if isinstance(spec, dict):
        return (spec.get("z0", 1.0), spec.get("z1", 1.05), spec.get("x0", WW / 2), spec.get("x1", WW / 2), spec.get("y", cy))
    if spec == "pull":   # start close on the character, open up to the whole scene
        if not focus:
            return (1.3, 1.0, WW / 2, WW / 2, cy, cy)
        fy = min(focus.y0, focus.y1) - 170 * focus.s0 / 20
        return (1.3, 1.0, focus.x0, WW / 2, fy, cy)
    if spec == "close" and focus:
        y = min(focus.y0, focus.y1) - 260 * focus.s0 / 20
        return (1.16, 1.24, focus.x0, focus.x1 if focus.act != "walk" else focus.x0, y)
    if spec == "pan_left":
        return (1.06, 1.06, WW / 2 + 110, WW / 2 - 110, cy)
    if spec == "pan_right":
        return (1.06, 1.06, WW / 2 - 110, WW / 2 + 110, cy)
    if spec == "static":
        return (1.03, 1.04, WW / 2, WW / 2, cy)
    return (1.0, 1.1, WW / 2, WW / 2 + rng.uniform(-40, 40), cy)   # push


def plan_story(story, lines, duration, seed):
    from .render import Shot
    rng = random.Random(seed)
    hero = Look(*story.get("hero", ["#e08a52", "cap"]))
    partner = Look(*story.get("partner", ["#e59ab0", "flower"]))
    built = {}
    starts = []
    for i, sp in enumerate(story["shots"]):
        if i == 0:
            starts.append(0.0)
        elif "lines" in sp:
            starts.append(max(0.0, lines[sp["lines"][0]].start - 0.35))
        else:
            starts.append(float(sp["from"]))
    shots = []
    for i, sp in enumerate(story["shots"]):
        start, end = starts[i], (starts[i + 1] if i + 1 < len(starts) else duration)
        key = (sp["set"], sp.get("time", "dusk"), sp.get("variant", 0))
        if key not in built:
            built[key] = sets.build(sp["set"], key[1], seed * 31 + len(built) * 7 + key[2])
        sc = built[key]
        actors = []
        for d in sp.get("cast", []):
            if d.get("who") == "crowd":
                actors += crowd(d, sc, rng)
            else:
                who = d.get("who", "hero")
                base_look = hero if who == "hero" else partner if who == "partner" else Look("#8fb3d9", "cap")   # "extra"
                actors.append(SActor(base_look, d, sc))
        cam = camera(sp.get("cam", "push"), sc, [a for a in actors if a.who != "crowd"], rng)
        sh = Shot(start, end, sc, actors, cam)
        sh.fx = sp.get("fx", [])
        sh.weather = sp.get("weather", sc.particles)
        sh.framing = sp.get("cam", "push") if isinstance(sp.get("cam", "push"), str) else "custom"
        sh.note = sp.get("note", "")
        if end - start < 1.0:
            print(f"! storyboard shot {i} is only {end - start:.1f}s long", file=sys.stderr)
        shots.append(sh)
    return shots


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------- drawing
def _umbrella(d, x, top, s, color):
    col = hexrgb(color) if isinstance(color, str) else color
    R = 150 * s
    pts = []
    for k in range(25):
        a = math.pi + math.pi * k / 24
        pts.append((x + R * math.cos(a), top + 0.62 * R * math.sin(a) + 0.62 * R))
    scal = []
    for k in range(6):   # scalloped rim
        xa = x - R + 2 * R * k / 6
        xb = x - R + 2 * R * (k + 1) / 6
        for j in range(1, 6):
            f = j / 6
            scal.append((xa + (xb - xa) * f, top + 0.62 * R + 0.12 * R * math.sin(math.pi * f)))
    poly = pts + scal[::-1]
    d.polygon(poly, fill=col + (255,), outline=OUTLINE)
    d.line(poly + [poly[0]], fill=OUTLINE, width=max(2, int(5 * s)))
    for k in (-0.5, 0, 0.5):
        d.line([(x, top), (x + k * R, top + 0.7 * R)], fill=OUTLINE + (150,), width=max(1, int(3 * s)))
    d.line([(x, top - 18 * s), (x, top + 0.62 * R + 150 * s)], fill=OUTLINE, width=max(2, int(6 * s)))


def draw_actor(world, a, ctx, f, ai, energy, pulse, singing):
    sc, t, lt, D = ctx["sc"], ctx["t"], ctx["lt"], ctx["D"]
    span = max(0.05, (a.t1 - a.t0) * D)
    m = min(1.0, max(0.0, (lt - a.t0 * D) / span))
    walking = a.act == "walk" and 0 < m < 1 and abs(a.x1 - a.x0) > 1
    mm = m if a.act == "walk" else ease(m)
    x = a.x0 + (a.x1 - a.x0) * mm
    y = a.y0 + (a.y1 - a.y0) * mm
    s_q = a.s0 + (a.s1 - a.s0) * mm
    s = s_q / 20.0
    alpha = 1.0
    if a.fade == "out":
        alpha = 1 - ease((lt / D - 0.35) / 0.55)
    elif a.fade == "in":
        alpha = ease(lt / (D * 0.4))
    if alpha <= 0.01:
        return
    legs = 3 if a.act in ("sit", "boat") else (1 + int((t + a.phase) * 5) % 2 if walking else 0)
    arms = a.arms
    rot = 0.0
    if a.act in ("float", "sink"):
        rot = 9 * math.sin(t * 0.9 + a.phase)
        arms = 1 if math.sin(t * 0.7 + a.phase) > 0.3 else 0
    elif a.act == "dance":
        rot = 8 * math.sin(t * 2.6 + a.phase)
        arms = 1 + int(t * 1.3 + a.phase) % 2
    elif a.act == "boat":
        rot = 6 * math.sin(t * 1.4 + a.phase)
    face = "back" if a.back else a.face
    sing = singing and ai == 0 and a.who == "hero" and not a.back
    mouth = (2 if energy > 0.75 else 1 if energy > 0.45 else 0) if sing else 0
    blink = ((t + a.phase * 2.3) % 3.7) < 0.14
    boil = int(f / 5) % 3
    img, (ax, ay) = sprite(a.look.key(), face, blink, mouth, legs, arms, boil, int(round(s_q)), sc.tint)
    if walking:
        bob = -abs(math.sin((t + a.phase) * math.pi * 2.5)) * 8 * s
    elif a.act in ("float", "sink"):
        bob = 14 * s * math.sin(t * 1.1 + a.phase)
    elif a.act == "boat":
        bob = 10 * math.sin(t * 1.6 + a.phase)
    else:
        bob = -(math.sin((t + a.phase) * 2.2) * 0.5 + 0.5) * 4 * s - pulse * 7 * s
    if a.act in ("sit", "boat") and not getattr(sc, "seated", None):
        y_feet = y + LEG_H * s       # sitting on the ground: the body rests on y
    else:
        y_feet = y
    if rot:
        cx, cy = img.width / 2, img.height / 2
        img = img.rotate(rot, resample=Image.BICUBIC, expand=True)
        r = math.radians(-rot)
        vx, vy = ax - cx, ay - cy
        ax = img.width / 2 + vx * math.cos(r) - vy * math.sin(r)
        ay = img.height / 2 + vx * math.sin(r) + vy * math.cos(r)
    if alpha < 1:
        img = img.copy()
        img.putalpha(img.getchannel("A").point(lambda v: int(v * alpha)))
    yy = y_feet + bob
    if a.umbrella:
        ud = ImageDraw.Draw(world, "RGBA")
        _umbrella(ud, x + a.umbrella_dx * s, yy - (BODY_H + LEG_H + 170) * s, s, a.umbrella)
    world.paste(img, (int(x - ax), int(yy - ay)), img)
    d = ImageDraw.Draw(world, "RGBA")
    body_bottom = yy - LEG_H * s
    if a.scarf:
        col = hexrgb(a.scarf) if isinstance(a.scarf, str) else a.scarf
        sy = body_bottom - BODY_H * s * 0.17      # below the mouth (the box body is also the head)
        band = [(x - 124 * s, sy - 12 * s), (x + 124 * s, sy - 16 * s), (x + 124 * s, sy + 16 * s), (x - 124 * s, sy + 20 * s)]
        d.polygon(band, fill=col + (255,), outline=OUTLINE)
        d.line(band + [band[0]], fill=OUTLINE, width=max(2, int(4 * s)))
        tail = [(x + 50 * s, sy), (x + 86 * s, sy), (x + 96 * s + 6 * s * math.sin(t * 3), sy + 90 * s), (x + 62 * s + 6 * s * math.sin(t * 3), sy + 92 * s)]
        d.polygon(tail, fill=col + (255,), outline=OUTLINE)
        d.line(tail + [tail[0]], fill=OUTLINE, width=max(2, int(4 * s)))
    if a.phone:
        px, py = x + 150 * s, body_bottom - BODY_H * s * 0.55
        add_glow(world, px, py - 30 * s, 160 * s, (170, 210, 255), 0.6)
        d.rounded_rectangle([px - 26 * s, py - 70 * s, px + 26 * s, py + 20 * s], radius=int(8 * s), fill=(40, 40, 60, 255), outline=OUTLINE, width=max(2, int(4 * s)))
        d.rounded_rectangle([px - 19 * s, py - 62 * s, px + 19 * s, py + 10 * s], radius=int(5 * s), fill=(190, 225, 255, 255))
    if a.act == "boat" and a.hull > 0:
        c, sn = math.cos(math.radians(-rot)), math.sin(math.radians(-rot))

        def R(px, py):
            return (x + px * s * c - py * s * sn, yy - LEG_H * s + px * s * sn + py * s * c)
        hw = 210 * a.hull
        hull = [R(-hw, -40), R(hw, -40), R(hw - 50, 40), R(-hw + 50, 40)]
        d.polygon(hull, fill=(110, 72, 58, 255), outline=OUTLINE)
        d.line(hull + [hull[0]], fill=OUTLINE, width=max(2, int(6 * s)))
        d.line([R(-hw + 10, -22), R(hw - 10, -22)], fill=(150, 104, 80, 255), width=max(2, int(5 * s)))
    if a.act in ("float", "sink"):
        for k in range(4):
            ph = (t * 0.8 + k * 0.25) % 1.0
            bx = x + (30 + 10 * k) * s * (1 if k % 2 else -1)
            by = yy - (BODY_H + LEG_H) * s - ph * 220 * s
            rr = (6 + 4 * k) * s
            d.ellipse([bx - rr, by - rr, bx + rr, by + rr], outline=(225, 245, 255, int(200 * (1 - ph))), width=2)
    if a.emote and not walking:
        from .render import draw_emote
        hat = {"beanie": 80, "cap": 50, "flower": 15, "bow": 20, "hair": 10}.get(a.look.accessory, 0)
        draw_emote(world, a.emote, x, yy - (BODY_H + LEG_H) * s - hat * s - (150 * s if a.umbrella else 0), t, s)
