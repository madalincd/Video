"""Drawing helpers shared by all scenes (pure Cairo, no external assets)."""
import math
import random

import cairo

W, H = 1920, 1080
FPS = 30
FONT = "Inter"


def hexc(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


# Palette: dark background, one accent per tissue type.
C = {
    "bg0": hexc("#141A24"),
    "bg1": hexc("#080B10"),
    "ink": hexc("#EEF1F5"),
    "muted": hexc("#8A94A6"),
    "panel": hexc("#1A2130"),
    "accent": hexc("#F2C14E"),      # brand / general fat
    "white": hexc("#F4E9D4"),       # white adipocytes
    "brown": hexc("#C0662C"),       # brown adipocytes
    "beige": hexc("#E3A96B"),       # beige adipocytes
    "subq": hexc("#F2C14E"),        # subcutaneous
    "visc": hexc("#EF7B5A"),        # visceral
    "hormone": hexc("#4FD1C5"),     # leptin / signals
    "hormone2": hexc("#A78BFA"),    # adiponectin
    "blood": hexc("#E04F5F"),
    "nerve": hexc("#F7E07A"),
    "nucleus": hexc("#7B5FC9"),
    "skin": hexc("#E8A598"),
    "muscle": hexc("#9A3D4A"),
    "good": hexc("#5FD38D"),
    "bad": hexc("#F06272"),
}


# ---------------------------------------------------------------- timing
def clamp(x, a=0.0, b=1.0):
    return a if x < a else b if x > b else x


def ease(x):
    x = clamp(x)
    return x * x * (3 - 2 * x)


def ease_out(x):
    x = clamp(x)
    return 1 - (1 - x) ** 3


def ease_back(x):
    x = clamp(x)
    c1, c3 = 1.70158, 2.70158
    return 1 + c3 * (x - 1) ** 3 + c1 * (x - 1) ** 2


def prog(t, start, dur=0.8):
    return ease((t - start) / dur)


def window(t, start, end, fin=0.5, fout=0.5):
    """1 inside [start, end], with eased fades at both ends."""
    return min(prog(t, start, fin), 1 - prog(t, end - fout, fout))


def lerp(a, b, f):
    return a + (b - a) * f


def mix(c1, c2, f):
    return tuple(lerp(a, b, f) for a, b in zip(c1, c2))


# ---------------------------------------------------------------- primitives
def col(ctx, c, a=1.0):
    ctx.set_source_rgba(c[0], c[1], c[2], a)


def circle(ctx, x, y, r):
    ctx.new_sub_path()
    ctx.arc(x, y, max(r, 0.01), 0, 2 * math.pi)


def ellipse(ctx, x, y, rx, ry, rot=0.0):
    ctx.save()
    ctx.translate(x, y)
    ctx.rotate(rot)
    ctx.scale(max(rx, 0.01), max(ry, 0.01))
    ctx.new_sub_path()
    ctx.arc(0, 0, 1, 0, 2 * math.pi)
    ctx.restore()


def capsule(ctx, x1, y1, x2, y2, r):
    a = math.atan2(y2 - y1, x2 - x1)
    ctx.new_sub_path()
    ctx.arc(x2, y2, r, a - math.pi / 2, a + math.pi / 2)
    ctx.arc(x1, y1, r, a + math.pi / 2, a + 3 * math.pi / 2)
    ctx.close_path()


def rrect(ctx, x, y, w, h, r):
    r = min(r, w / 2, h / 2)
    ctx.new_sub_path()
    ctx.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    ctx.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    ctx.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    ctx.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
    ctx.close_path()


def font(ctx, size, bold=True):
    ctx.select_font_face(FONT, cairo.FONT_SLANT_NORMAL,
                         cairo.FONT_WEIGHT_BOLD if bold else cairo.FONT_WEIGHT_NORMAL)
    ctx.set_font_size(size)


def text_w(ctx, s, size, bold=True):
    font(ctx, size, bold)
    return ctx.text_extents(s)[4]


def text(ctx, s, x, y, size, c, a=1.0, align="center", bold=True):
    """Draw text with baseline at y. align: left|center|right."""
    if a <= 0.001:
        return
    font(ctx, size, bold)
    w = ctx.text_extents(s)[4]
    dx = {"left": 0, "center": -w / 2, "right": -w}[align]
    col(ctx, c, a)
    ctx.move_to(x + dx, y)
    ctx.show_text(s)


def wrap(ctx, s, size, maxw, bold=True):
    font(ctx, size, bold)
    words, lines, cur = s.split(), [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if ctx.text_extents(trial)[4] <= maxw or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


# ---------------------------------------------------------------- polylines
def bezier_pts(p0, p1, p2, p3, n=40):
    pts = []
    for i in range(n + 1):
        t = i / n
        u = 1 - t
        x = u ** 3 * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t ** 3 * p3[0]
        y = u ** 3 * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t ** 3 * p3[1]
        pts.append((x, y))
    return pts


def poly_len(pts):
    return sum(math.dist(pts[i], pts[i + 1]) for i in range(len(pts) - 1))


def poly_partial(ctx, pts, f, f0=0.0):
    """Append the part of a polyline between fractions f0..f of its length."""
    if f <= f0 or len(pts) < 2:
        return
    total = poly_len(pts)
    a, b = f0 * total, f * total
    acc = 0.0
    started = False
    for i in range(len(pts) - 1):
        p, q = pts[i], pts[i + 1]
        seg = math.dist(p, q)
        if seg == 0:
            continue
        s0, s1 = acc, acc + seg
        if s1 >= a and s0 <= b:
            t0 = clamp((a - s0) / seg)
            t1 = clamp((b - s0) / seg)
            x0, y0 = lerp(p[0], q[0], t0), lerp(p[1], q[1], t0)
            x1, y1 = lerp(p[0], q[0], t1), lerp(p[1], q[1], t1)
            if not started:
                ctx.move_to(x0, y0)
                started = True
            ctx.line_to(x1, y1)
        acc = s1
        if acc > b:
            break


def poly_point(pts, f):
    total = poly_len(pts)
    target = clamp(f) * total
    acc = 0.0
    for i in range(len(pts) - 1):
        seg = math.dist(pts[i], pts[i + 1])
        if acc + seg >= target and seg > 0:
            u = (target - acc) / seg
            return (lerp(pts[i][0], pts[i + 1][0], u), lerp(pts[i][1], pts[i + 1][1], u))
        acc += seg
    return pts[-1]


def arrow_head(ctx, x, y, ang, size, c, a=1.0):
    col(ctx, c, a)
    ctx.move_to(x, y)
    ctx.line_to(x - size * math.cos(ang - 0.45), y - size * math.sin(ang - 0.45))
    ctx.line_to(x - size * math.cos(ang + 0.45), y - size * math.sin(ang + 0.45))
    ctx.close_path()
    ctx.fill()


# ---------------------------------------------------------------- UI pieces
def pill(ctx, s, cx, cy, c, p, size=30, fill_a=0.16):
    """Rounded label that pops in with progress p (0..1)."""
    if p <= 0.001:
        return
    font(ctx, size)
    tw = ctx.text_extents(s)[4]
    w, h = tw + size * 1.4, size * 1.75
    sc = 0.85 + 0.15 * ease_back(p)
    a = clamp(p * 1.5)
    ctx.save()
    ctx.translate(cx, cy)
    ctx.scale(sc, sc)
    rrect(ctx, -w / 2, -h / 2, w, h, h / 2)
    col(ctx, c, fill_a * a)
    ctx.fill_preserve()
    col(ctx, c, 0.9 * a)
    ctx.set_line_width(2.5)
    ctx.stroke()
    text(ctx, s, 0, size * 0.36, size, C["ink"], a)
    ctx.restore()


def callout(ctx, s, ax, ay, lx, ly, c, p, size=32, align=None):
    """Dot at anchor, leader line to label position, label text."""
    if p <= 0.001:
        return
    pl = ease(p * 1.6)
    pt = ease(p * 1.6 - 0.5)
    col(ctx, c, clamp(p * 3))
    circle(ctx, ax, ay, 7)
    ctx.fill()
    col(ctx, c, 0.35 * clamp(p * 3))
    circle(ctx, ax, ay, 7 + 8 * pl)
    ctx.fill()
    ctx.set_line_width(2.5)
    col(ctx, c, 0.9)
    ctx.move_to(ax, ay)
    ctx.line_to(lerp(ax, lx, pl), lerp(ay, ly, pl))
    ctx.stroke()
    if align is None:
        align = "left" if lx >= ax else "right"
    off = 14 if align == "left" else -14
    text(ctx, s, lx + off, ly + size * 0.35, size, C["ink"], pt, align=align)


def heading(ctx, s, t, start=0.2, y=120, size=56, c=None, a=1.0):
    p = prog(t, start, 0.7)
    text(ctx, s, W / 2, y + 20 * (1 - p), size, c or C["ink"], p * a)


def glow_circle(ctx, x, y, r, c, a=1.0):
    g = cairo.RadialGradient(x, y, 0, x, y, r)
    g.add_color_stop_rgba(0, c[0], c[1], c[2], 0.55 * a)
    g.add_color_stop_rgba(0.5, c[0], c[1], c[2], 0.18 * a)
    g.add_color_stop_rgba(1, c[0], c[1], c[2], 0)
    ctx.set_source(g)
    circle(ctx, x, y, r)
    ctx.fill()


def heat_waves(ctx, x, y, t, c, a=1.0, n=3, h=90, spread=46, width=4):
    """Rising wavy lines (heat)."""
    ctx.set_line_width(width)
    ctx.set_line_cap(cairo.LINE_CAP_ROUND)
    for i in range(n):
        ox = x + (i - (n - 1) / 2) * spread
        ph = (t * 0.9 + i * 0.33) % 1.0
        alpha = a * math.sin(ph * math.pi)
        col(ctx, c, alpha)
        base = y - ph * 40
        ctx.move_to(ox, base)
        for k in range(1, 21):
            yy = base - h * k / 20
            xx = ox + 9 * math.sin(k / 20 * 2 * math.pi * 1.5 + t * 4 + i)
            ctx.line_to(xx, yy)
        ctx.stroke()


# ---------------------------------------------------------------- body figure
def body_prims(kind="neutral"):
    """Body as circles/capsules in units (height ~100, x centered at 0)."""
    sh = {"neutral": 12.5, "female": 11.0, "male": 14.0, "baby": 9.0}[kind]
    hip = {"neutral": 6.5, "female": 8.5, "male": 6.0, "baby": 5.0}[kind]
    if kind == "baby":
        return [
            ("c", 0, 22, 17),                      # big head
            ("k", 0, 38, 0, 44, 5),                # neck
            ("k", -6, 50, 6, 50, 12),              # chest
            ("k", 0, 52, 0, 64, 13),               # belly
            ("k", -15, 49, -24, 63, 4.6),          # arms
            ("k", 15, 49, 24, 63, 4.6),
            ("k", -7, 70, -11, 88, 5.5),           # legs
            ("k", 7, 70, 11, 88, 5.5),
            ("k", -11, 90, -14, 91, 3.4),
            ("k", 11, 90, 14, 91, 3.4),
        ]
    return [
        ("c", 0, 8, 7.5),
        ("k", 0, 13, 0, 19, 3.2),
        ("k", -sh + 8, 25, sh - 8, 25, 9.6),
        ("k", 0, 28, 0, 44, 8.6 if kind != "female" else 7.8),
        ("k", -hip + 3, 50, hip - 3, 50, 9.0 if kind != "female" else 9.6),
        ("k", -sh, 23.5, -sh - 3.5, 40, 3.6),
        ("k", -sh - 3.5, 40, -sh - 5, 55, 3.1),
        ("k", sh, 23.5, sh + 3.5, 40, 3.6),
        ("k", sh + 3.5, 40, sh + 5, 55, 3.1),
        ("k", -5, 55, -6, 75, 5.4 if kind != "female" else 5.9),
        ("k", -6, 75, -6.5, 94, 3.8),
        ("k", 5, 55, 6, 75, 5.4 if kind != "female" else 5.9),
        ("k", 6, 75, 6.5, 94, 3.8),
        ("k", -6.5, 96, -9.5, 97, 2.2),
        ("k", 6.5, 96, 9.5, 97, 2.2),
    ]


def body_path(ctx, prims, cx, top, s, e=0.0):
    for p in prims:
        if p[0] == "c":
            circle(ctx, cx + p[1] * s, top + p[2] * s, p[3] * s + e)
        else:
            capsule(ctx, cx + p[1] * s, top + p[2] * s, cx + p[3] * s, top + p[4] * s, p[5] * s + e)


def glow_body(ctx, prims, cx, top, s, c, a=1.0, fill=None):
    """Glowing outline silhouette (union of primitives)."""
    for e, al in ((22, 0.04), (14, 0.07), (8, 0.12), (4.5, 0.25), (2.6, 1.0)):
        ctx.new_path()
        body_path(ctx, prims, cx, top, s, e)
        col(ctx, c, al * a)
        ctx.fill()
    ctx.new_path()
    body_path(ctx, prims, cx, top, s, 0)
    col(ctx, fill or C["panel"], a)
    ctx.fill()


def scatter_in_body(prims, cx, top, s, n, seed=1, margin=6):
    surf = cairo.ImageSurface(cairo.FORMAT_A8, 4, 4)
    c = cairo.Context(surf)
    body_path(c, prims, cx, top, s, -margin)
    xs = [cx + p[1] * s for p in prims] + [cx + p[3] * s for p in prims if p[0] == "k"]
    x0, x1 = min(xs) - 40 * s / 8, max(xs) + 40 * s / 8
    rnd = random.Random(seed)
    pts = []
    tries = 0
    while len(pts) < n and tries < n * 200:
        tries += 1
        x = rnd.uniform(x0, x1)
        y = rnd.uniform(top, top + 98 * s)
        if c.in_fill(x, y):
            pts.append((x, y, rnd.random()))
    return pts


# ---------------------------------------------------------------- cells
def nucleus(ctx, x, y, r, rot=0.0, flat=1.0, a=1.0):
    ellipse(ctx, x, y, r * flat, r, rot)
    col(ctx, C["nucleus"], a)
    ctx.fill()
    ellipse(ctx, x - r * 0.2, y - r * 0.25, r * 0.35 * flat, r * 0.3, rot)
    col(ctx, mix(C["nucleus"], C["ink"], 0.5), 0.5 * a)
    ctx.fill()


def droplet(ctx, x, y, r, c, a=1.0):
    g = cairo.RadialGradient(x - r * 0.35, y - r * 0.35, r * 0.05, x, y, r)
    hi = mix(c, (1, 1, 1), 0.55)
    g.add_color_stop_rgba(0, hi[0], hi[1], hi[2], a)
    g.add_color_stop_rgba(1, c[0], c[1], c[2], a)
    ctx.set_source(g)
    circle(ctx, x, y, r)
    ctx.fill()


def mito(ctx, x, y, r, rot, a=1.0):
    ellipse(ctx, x, y, r * 1.7, r, rot)
    col(ctx, hexc("#5B2A12"), a)
    ctx.fill_preserve()
    col(ctx, hexc("#E39A62"), 0.8 * a)
    ctx.set_line_width(1.6)
    ctx.stroke()
    ctx.save()
    ctx.translate(x, y)
    ctx.rotate(rot)
    ctx.set_line_width(1.4)
    col(ctx, hexc("#E39A62"), 0.7 * a)
    for k in range(-2, 3):
        ctx.move_to(k * r * 0.55, -r * 0.7)
        ctx.line_to(k * r * 0.55 + r * 0.25, r * 0.7)
    ctx.stroke()
    ctx.restore()


def white_cell(ctx, x, y, r, f=1.0, a=1.0, nuc_ang=-0.7):
    """Unilocular cell. f: 0 = small central droplet, 1 = droplet fills cell."""
    circle(ctx, x, y, r)
    col(ctx, hexc("#D9C7A6"), 0.35 * a)
    ctx.fill_preserve()
    col(ctx, C["white"], 0.9 * a)
    ctx.set_line_width(max(2, r * 0.025))
    ctx.stroke()
    dr = lerp(r * 0.35, r * 0.9, f)
    droplet(ctx, x, y, dr, mix(C["white"], C["accent"], 0.25), a)
    d = lerp(0, r * 0.92, f)
    nx, ny = x + d * math.cos(nuc_ang), y + d * math.sin(nuc_ang)
    nr = r * lerp(0.16, 0.13, f)
    nucleus(ctx, nx, ny, nr, rot=nuc_ang, flat=lerp(1.0, 0.45, f), a=a)


def brown_cell(ctx, x, y, r, mito_p=0.0, a=1.0, seed=3, base=None, n_drop=None):
    base = base or C["brown"]
    circle(ctx, x, y, r)
    col(ctx, mix(base, (0, 0, 0), 0.35), 0.9 * a)
    ctx.fill_preserve()
    col(ctx, base, a)
    ctx.set_line_width(max(2, r * 0.03))
    ctx.stroke()
    rnd = random.Random(seed)
    n = n_drop or 14
    placed = []
    for _ in range(400):
        if len(placed) >= n:
            break
        ang = rnd.uniform(0, 2 * math.pi)
        dist = rnd.uniform(r * 0.32, r * 0.8)
        dr = rnd.uniform(r * 0.1, r * 0.19)
        px, py = x + dist * math.cos(ang), y + dist * math.sin(ang)
        if math.dist((px, py), (x, y)) + dr > r * 0.93:
            continue
        if all(math.dist((px, py), (q[0], q[1])) > dr + q[2] + r * 0.03 for q in placed):
            placed.append((px, py, dr))
    for px, py, dr in placed:
        droplet(ctx, px, py, dr, hexc("#EBC58F"), a)
    if mito_p > 0:
        rnd2 = random.Random(seed + 10)
        for i in range(24):
            ang = rnd2.uniform(0, 2 * math.pi)
            dist = rnd2.uniform(r * 0.25, r * 0.88)
            px, py = x + dist * math.cos(ang), y + dist * math.sin(ang)
            if any(math.dist((px, py), (q[0], q[1])) < q[2] + r * 0.05 for q in placed):
                continue
            pi = clamp(mito_p * 24 - i * 0.6)
            if pi > 0:
                mito(ctx, px, py, r * 0.055 * (0.6 + 0.4 * ease_back(pi)), rnd2.uniform(0, 3.14), a * clamp(pi))
    nucleus(ctx, x, y, r * 0.2, a=a)
