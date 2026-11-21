"""The nine scenes. Each draw(ctx, t, D, cue) renders one frame.

t   seconds since scene start
D   scene duration (from the voiceover)
cue Cue helper: cue.s(i) / cue.e(i) start/end of sentence i,
    cue.at(i, f) time at fraction f through sentence i.
"""
import math
import random

import cairo
import numpy as np
from scipy.spatial import Voronoi

from gfx import (C, W, H, arrow_head, body_path, body_prims, bezier_pts, brown_cell,
                 callout, capsule, circle, clamp, col, droplet, ease, ease_back, ease_out,
                 ellipse, glow_body, glow_circle, heading, heat_waves, hexc, lerp, mix,
                 mito, nucleus, pill, poly_partial, poly_point, prog, rrect, scatter_in_body,
                 text, white_cell, window)


class Cue:
    def __init__(self, cues):
        self.c = cues

    def s(self, i):
        return self.c[i]["start"]

    def e(self, i):
        return self.c[i]["end"]

    def at(self, i, f):
        return lerp(self.s(i), self.e(i), f)


class MappedCue(Cue):
    """Retime an original scene's cues onto a shorter narration (reel cut)."""
    NEVER = 1e6

    def __init__(self, cues, mapping):
        self.c = cues
        self.m = {int(k): v for k, v in mapping.items()}

    def _t(self, i, which):
        if i not in self.m:
            return self.NEVER
        j, f0, f1 = self.m[i]
        a, b = self.c[j]["start"], self.c[j]["end"]
        return lerp(a, b, f0 if which == 0 else f1)

    def s(self, i):
        return self._t(i, 0)

    def e(self, i):
        return self._t(i, 1)


# ---------------------------------------------------------------- Voronoi tissue
_vor_cache = {}


def tissue(cx, cy, R, spacing, seed=7, jitter=0.32):
    key = (cx, cy, R, spacing, seed)
    if key in _vor_cache:
        return _vor_cache[key]
    rnd = random.Random(seed)
    pts = []
    rows = int(2 * (R + 3 * spacing) / (spacing * 0.866)) + 2
    cols = int(2 * (R + 3 * spacing) / spacing) + 2
    for j in range(rows):
        for i in range(cols):
            x = cx - R - 3 * spacing + i * spacing + (spacing / 2 if j % 2 else 0)
            y = cy - R - 3 * spacing + j * spacing * 0.866
            x += rnd.uniform(-jitter, jitter) * spacing
            y += rnd.uniform(-jitter, jitter) * spacing
            pts.append((x, y))
    vor = Voronoi(np.array(pts))
    cells = []
    for pi, reg_i in enumerate(vor.point_region):
        reg = vor.regions[reg_i]
        if not reg or -1 in reg:
            continue
        poly = [tuple(vor.vertices[v]) for v in reg]
        px, py = pts[pi]
        if math.dist((px, py), (cx, cy)) > R + spacing:
            continue
        gx = sum(p[0] for p in poly) / len(poly)
        gy = sum(p[1] for p in poly) / len(poly)
        cells.append({"poly": poly, "c": (gx, gy), "r": rnd.random(), "ang": rnd.uniform(0, 6.28)})
    edges = []
    for (a, b) in vor.ridge_vertices:
        if a < 0 or b < 0:
            continue
        p, q = tuple(vor.vertices[a]), tuple(vor.vertices[b])
        if math.dist(p, (cx, cy)) < R + 10 and math.dist(q, (cx, cy)) < R + 10:
            edges.append((p, q))
    _vor_cache[key] = (cells, edges)
    return cells, edges


def poly_path(ctx, poly, center, inset):
    gx, gy = center
    pts = []
    for (x, y) in poly:
        d = math.dist((x, y), (gx, gy))
        k = max(0.0, (d - inset) / d) if d > 0 else 0
        pts.append((gx + (x - gx) * k, gy + (y - gy) * k))
    # rounded polygon via midpoints + quadratic-like curves
    n = len(pts)
    mids = [((pts[i][0] + pts[(i + 1) % n][0]) / 2, (pts[i][1] + pts[(i + 1) % n][1]) / 2) for i in range(n)]
    ctx.new_sub_path()
    ctx.move_to(*mids[-1])
    for i in range(n):
        x, y = pts[i]
        mx, my = mids[i]
        px, py = mids[i - 1]
        ctx.curve_to(lerp(px, x, 0.7), lerp(py, y, 0.7), lerp(mx, x, 0.7), lerp(my, y, 0.7), mx, my)
    ctx.close_path()


def draw_tissue(ctx, cells, a=1.0, glow=0.0, empty=0.0, inset=5, nuclei=True, tint=None):
    """Adipocyte tissue. empty: 0 = lipid-filled, 1 = 'washed-out' histology look."""
    base = tint or C["white"]
    for cell in cells:
        gx, gy = cell["c"]
        poly_path(ctx, cell["poly"], cell["c"], inset)
        fill = mix(mix(base, C["accent"], 0.18 + 0.25 * glow * (0.6 + 0.4 * cell["r"])), hexc("#FFF6FA"), empty)
        col(ctx, fill, a * lerp(0.92, 0.95, empty))
        ctx.fill_preserve()
        edge = mix(mix(base, (0, 0, 0), 0.3), hexc("#C2649A"), empty)
        col(ctx, edge, a)
        ctx.set_line_width(lerp(2.0, 3.2, empty))
        ctx.stroke()
        if nuclei and cell["r"] < 0.35:
            # nucleus squashed against the membrane
            poly = cell["poly"]
            v = poly[int(cell["r"] * 100) % len(poly)]
            w = poly[(int(cell["r"] * 100) + 1) % len(poly)]
            mx, my = (v[0] + w[0]) / 2, (v[1] + w[1]) / 2
            nx, ny = lerp(mx, gx, 0.14), lerp(my, gy, 0.14)
            ang = math.atan2(gy - my, gx - mx)
            ellipse(ctx, nx, ny, 5, 13, ang)
            col(ctx, mix(C["nucleus"], hexc("#4B2A7B"), empty), a)
            ctx.fill()


def microscope_ring(ctx, cx, cy, R, a=1.0):
    ctx.set_line_width(14)
    col(ctx, hexc("#2A3344"), a)
    circle(ctx, cx, cy, R + 7)
    ctx.stroke()
    ctx.set_line_width(2)
    col(ctx, C["muted"], 0.6 * a)
    circle(ctx, cx, cy, R + 15)
    ctx.stroke()


# ================================================================ 1. HOOK
_hook_dots = None


def hook(ctx, t, D, cue):
    global _hook_dots
    prims = body_prims("neutral")
    cx, top, s = 620, 105, 7.9
    if _hook_dots is None:
        _hook_dots = scatter_in_body(prims, cx, top, s, 260, seed=4)
    a_body = prog(t, 0.0, 1.2)
    glow_body(ctx, prims, cx, top, s, C["accent"], a_body)
    # fat 'cells' appearing inside the silhouette
    ctx.save()
    ctx.new_path()
    body_path(ctx, prims, cx, top, s, -2)
    ctx.clip()
    t0 = cue.s(0) + 0.6
    for (x, y, r) in _hook_dots:
        p = prog(t, t0 + r * 3.2, 0.5)
        if p > 0:
            pulse = 0.85 + 0.15 * math.sin(t * 2 + r * 20)
            col(ctx, C["accent"], 0.75 * p * pulse)
            circle(ctx, x, y, (5 + 6 * r) * ease_back(p))
            ctx.fill()
    ctx.restore()

    # right column
    rx = 1350
    end_stats = cue.s(3) - 0.2
    a_stat = window(t, cue.s(0) + 0.4, end_stats + 0.5, 0.7, 0.6)
    n = ease_out((t - cue.s(0) - 0.4) / 3.0)
    lo, hi = int(round(20 * n)), int(round(25 * n))
    text(ctx, f"{lo}–{hi}%", rx, 420, 150, C["accent"], a_stat)
    text(ctx, "of your body weight", rx, 495, 44, C["ink"], a_stat, bold=False)

    a_bin = window(t, cue.s(1), cue.s(2) + 0.2, 0.5, 0.4)
    if a_bin > 0:
        text(ctx, "“just a storage bin”", rx, 640, 40, C["muted"], a_bin, bold=False)
        p = prog(t, cue.at(1, 0.55), 0.5)
        w = 380
        ctx.set_line_width(5)
        col(ctx, C["bad"], a_bin)
        ctx.move_to(rx - w / 2, 627)
        ctx.line_to(rx - w / 2 + w * p, 627)
        ctx.stroke()
    a_jobs = window(t, cue.s(2), end_stats + 0.5, 0.4, 0.6)
    if a_jobs > 0:
        jobs = [("Energy store", C["accent"]), ("Insulation", C["subq"]),
                ("Cushioning", C["visc"]), ("Hormones", C["hormone"])]
        for i, (lab, c) in enumerate(jobs):
            px = rx + (-170 if i % 2 == 0 else 170)
            py = 610 + (i // 2) * 90
            pill(ctx, lab, px, py, c, prog(t, cue.s(2) + 0.25 * i, 0.5) * a_jobs, size=30)

    a_title = prog(t, cue.s(3) - 0.1, 0.9)
    if a_title > 0:
        text(ctx, "ADIPOSE TISSUE", rx, 470 + 25 * (1 - a_title), 92, C["ink"], a_title)
        text(ctx, "Your Body's Energy Bank", rx, 550 + 25 * (1 - a_title), 46, C["accent"], a_title, bold=False)
        ctx.set_line_width(3)
        col(ctx, C["accent"], a_title)
        ctx.move_to(rx - 160 * a_title, 600)
        ctx.line_to(rx + 160 * a_title, 600)
        ctx.stroke()


# ================================================================ 2. WHAT IT IS
_vessels = None


def _vessel_paths(cx, cy, R):
    v1 = bezier_pts((cx - R - 20, cy + 120), (cx - 200, cy - 60), (cx + 80, cy + 220), (cx + R + 20, cy - 40), 80)
    v2 = bezier_pts((cx - 40, cy + 30), (cx + 20, cy - 140), (cx - 160, cy - 240), (cx - 60, cy - R - 20), 50)
    v3 = bezier_pts((cx + 150, cy + 90), (cx + 260, cy + 200), (cx + 180, cy + 300), (cx + 120, cy + R + 20), 50)
    nerve = bezier_pts((cx - R - 20, cy - 150), (cx - 120, cy - 260), (cx + 160, cy - 80), (cx + R + 20, cy - 220), 80)
    return [v1, v2, v3], nerve


def what(ctx, t, D, cue):
    global _vessels
    cx, cy, R = 960, 470, 370
    cells, edges = tissue(cx, cy, R, 92, seed=11)
    if _vessels is None:
        _vessels = _vessel_paths(cx, cy, R)
    vessels, nerve = _vessels

    # zoom from the silhouette into the tissue
    z = prog(t, 0.0, 2.2)
    if z < 1:
        prims = body_prims("neutral")
        scale = lerp(7.9, 7.9 * 9, ease(z))
        # keep the belly point (unit 0, 40) pinned to screen centre
        bx = lerp(620, cx, ease(z))
        by = lerp(105 + 40 * 7.9, cy, ease(z))
        top = by - 40 * scale
        glow_body(ctx, prims, bx, top, scale, C["accent"], 1 - ease(z * 1.4 - 0.3))

    a_t = prog(t, 1.0, 1.4)
    if a_t <= 0:
        return
    zoom = lerp(0.6, 1.0, ease_out((t - 1.0) / 1.6))
    ctx.save()
    ctx.translate(cx, cy)
    ctx.scale(zoom, zoom)
    ctx.translate(-cx, -cy)
    ctx.save()
    circle(ctx, cx, cy, R)
    ctx.clip()
    col(ctx, hexc("#2B1F1A"), a_t)
    ctx.paint()
    glow = 0.5 + 0.5 * math.sin((t - cue.s(1)) * 3) if t > cue.s(1) else 0
    glow *= window(t, cue.s(1), cue.s(2) + 0.3, 0.4, 0.6)
    act = prog(t, cue.s(3), 0.8)
    glow = max(glow, act * (0.5 + 0.5 * math.sin(t * 2.4)))
    draw_tissue(ctx, cells, a_t, glow=glow)

    # reticular fibres in the gaps
    p_fib = prog(t, cue.at(2, 0.15), 1.6)
    if p_fib > 0:
        ctx.set_line_width(1.6)
        col(ctx, hexc("#D7DCE6"), 0.75 * p_fib)
        for (p, q) in edges:
            mx, my = (p[0] + q[0]) / 2, (p[1] + q[1]) / 2
            f = p_fib
            ctx.move_to(lerp(mx, p[0], f), lerp(my, p[1], f))
            ctx.line_to(lerp(mx, q[0], f), lerp(my, q[1], f))
        ctx.stroke()
    # blood vessels
    p_v = prog(t, cue.at(2, 0.5), 1.6)
    if p_v > 0:
        ctx.set_line_cap(cairo.LINE_CAP_ROUND)
        for k, vp in enumerate(vessels):
            f = clamp(p_v * 1.4 - k * 0.2)
            for wdt, cc, al in ((22, hexc("#6E1E28"), 1), (15, C["blood"], 1), (5, hexc("#FF9AA5"), 0.6)):
                ctx.set_line_width(wdt if k == 0 else wdt * 0.65)
                col(ctx, cc, al)
                ctx.new_path()
                poly_partial(ctx, vp, f)
                ctx.stroke()
        if t > cue.s(3):
            # blood flow particles
            for k, vp in enumerate(vessels):
                for j in range(7):
                    f = ((t - cue.s(3)) * 0.18 + j / 7) % 1.0
                    x, y = poly_point(vp, f)
                    col(ctx, hexc("#FFD1D6"), 0.9 * act)
                    circle(ctx, x, y, 4 if k == 0 else 3)
                    ctx.fill()
    # nerve
    p_n = prog(t, cue.at(2, 0.8), 1.2)
    if p_n > 0:
        ctx.set_line_width(4)
        col(ctx, C["nerve"], 0.95)
        ctx.set_dash([14, 8])
        ctx.new_path()
        poly_partial(ctx, nerve, p_n)
        ctx.stroke()
        ctx.set_dash([])
    ctx.restore()
    microscope_ring(ctx, cx, cy, R, a_t)
    ctx.restore()

    # labels
    callout(ctx, "Adipocytes", cx - 120, cy + 60, 380, 300, C["white"], prog(t, cue.at(0, 0.7), 0.9))
    a_lip = window(t, cue.s(1), D, 0.6, 0.6)
    if a_lip > 0:
        droplet(ctx, 255, 452, 16, C["accent"], a_lip)
        text(ctx, "Energy stored", 290, 445, 30, C["ink"], a_lip, align="left")
        text(ctx, "as lipids", 290, 482, 30, C["accent"], a_lip, align="left")
    callout(ctx, "Reticular fibers", cx + 190, cy - 160, 1530, 250, hexc("#D7DCE6"), prog(t, cue.at(2, 0.3), 0.9))
    callout(ctx, "Blood vessels", cx + 300, cy + 40, 1530, 450, C["blood"], prog(t, cue.at(2, 0.62), 0.9))
    callout(ctx, "Nerves", cx + 255, cy - 175, 1530, 350, C["nerve"], prog(t, cue.at(2, 0.88), 0.9))
    pill(ctx, "Metabolically active", cx, 900, C["accent"], prog(t, cue.at(3, 0.45), 0.6), size=32)


# ================================================================ 3. WHERE IT LIVES
def _kidney(ctx, x, y, flip, a, halo, squash=1.0):
    if halo > 0:
        g = cairo.RadialGradient(x, y, 20, x, y, 120)
        c = C["visc"]
        g.add_color_stop_rgba(0, c[0], c[1], c[2], 0.95 * halo * a)
        g.add_color_stop_rgba(0.75, c[0], c[1], c[2], 0.75 * halo * a)
        g.add_color_stop_rgba(1, c[0], c[1], c[2], 0)
        ctx.set_source(g)
        ellipse(ctx, x, y, 92 * squash, 118 / squash)
        ctx.fill()
    ellipse(ctx, x, y, 44 * squash, 66 / squash, 0.15 * flip)
    col(ctx, hexc("#9C3D54"), a)
    ctx.fill()
    ellipse(ctx, x - 30 * flip * squash, y, 13, 20)
    col(ctx, hexc("#2B1F2A"), a)
    ctx.fill()


def where(ctx, t, D, cue):
    cx, cy, RX, RY = 700, 480, 470, 315
    a = prog(t, cue.s(0), 1.0)
    sub_hi = window(t, cue.s(1), D, 0.5, 0.6)
    vis_hi = window(t, cue.s(2), D, 0.5, 0.6)
    focus_sub = window(t, cue.s(1), cue.s(2), 0.5, 0.5) + window(t, cue.s(3), cue.s(4), 0.5, 0.5)
    focus_vis = window(t, cue.s(2), cue.s(3), 0.5, 0.5) + window(t, cue.s(4), D, 0.5, 0.6)
    focus_sub, focus_vis = min(1, focus_sub), min(1, focus_vis)
    dim_sub = 1 - 0.55 * focus_vis
    dim_vis = 1 - 0.55 * focus_sub

    if a > 0:
        # skin
        ellipse(ctx, cx, cy, RX, RY)
        col(ctx, C["skin"], a)
        ctx.fill()
        # subcutaneous fat ring
        ellipse(ctx, cx, cy, RX - 10, RY - 10)
        col(ctx, mix(hexc("#6B5A35"), C["subq"], sub_hi) , a * dim_sub)
        ctx.fill()
        # texture dots in the subcutaneous layer
        if sub_hi > 0:
            rnd = random.Random(5)
            for i in range(170):
                ang = i / 170 * 2 * math.pi + rnd.uniform(-0.01, 0.01)
                k = rnd.uniform(0.2, 0.8)
                rx = lerp(RX - 14, RX - 60, k)
                ry = lerp(RY - 14, RY - 60, k)
                col(ctx, hexc("#FFE7A6"), 0.55 * sub_hi * a * dim_sub)
                circle(ctx, cx + rx * math.cos(ang), cy + ry * math.sin(ang), 6)
                ctx.fill()
        # muscle wall
        ellipse(ctx, cx, cy, RX - 64, RY - 64)
        col(ctx, C["muscle"], a)
        ctx.fill()
        # cavity
        ellipse(ctx, cx, cy, RX - 92, RY - 92)
        col(ctx, hexc("#1B1F2B"), a)
        ctx.fill()
        # visceral fat bed between organs (front)
        squash = 1 + 0.12 * math.sin(clamp((t - cue.at(4, 0.4)) / 0.9) * math.pi * 3) * (1 - clamp((t - cue.at(4, 0.4)) / 0.9)) if t > cue.at(4, 0.4) else 1
        col(ctx, mix(hexc("#5A3A33"), C["visc"], vis_hi), 0.85 * a * dim_vis)
        ellipse(ctx, cx, cy - 55, 300 * squash, 150 / squash)
        ctx.fill()
        # intestines
        rnd = random.Random(9)
        for i in range(11):
            ang = i / 11 * 2 * math.pi
            ix = cx + 205 * math.cos(ang) * (0.35 + 0.65 * rnd.random()) * squash
            iy = cy - 60 + 95 * math.sin(ang) * (0.3 + 0.7 * rnd.random()) / squash
            r = rnd.uniform(26, 38)
            circle(ctx, ix, iy, r)
            col(ctx, hexc("#D98C8C"), a)
            ctx.fill()
            circle(ctx, ix, iy, r * 0.45)
            col(ctx, hexc("#8F4B55"), a)
            ctx.fill()
        # spine + aorta
        circle(ctx, cx, cy + 165, 44)
        col(ctx, hexc("#DCD4C2"), a)
        ctx.fill()
        circle(ctx, cx, cy + 165, 22)
        col(ctx, hexc("#9A927F"), a)
        ctx.fill()
        circle(ctx, cx - 70, cy + 110, 18)
        col(ctx, C["blood"], a)
        ctx.fill()
        # kidneys with perirenal fat
        _kidney(ctx, cx - 165, cy + 120, 1, a, vis_hi * dim_vis, squash)
        _kidney(ctx, cx + 165, cy + 120, -1, a, vis_hi * dim_vis, squash)

    text(ctx, "Two groups by location", W / 2, 105, 50, C["ink"], window(t, cue.s(0), cue.s(1) + 0.4, 0.6, 0.5))

    callout(ctx, "Subcutaneous fat", cx + 300, cy - 255, 1270, 170, C["subq"], prog(t, cue.at(1, 0.15), 0.9), size=36)
    text(ctx, "just under the skin", 1284, 220, 28, C["muted"], prog(t, cue.at(1, 0.5), 0.6), align="left", bold=False)
    callout(ctx, "Visceral fat", cx + 170, cy + 60, 1270, 420, C["visc"], prog(t, cue.at(2, 0.1), 0.9), size=36)
    text(ctx, "around internal organs", 1284, 470, 28, C["muted"], prog(t, cue.at(2, 0.4), 0.6), align="left", bold=False)

    # eye inset ("even the eyeballs")
    pe = prog(t, cue.at(2, 0.75), 0.8)
    if pe > 0:
        ex, ey = 1700, 330
        ctx.save()
        ctx.translate(ex, ey)
        ctx.scale(0.8 + 0.2 * ease_back(pe), 0.8 + 0.2 * ease_back(pe))
        rrect(ctx, -105, -105, 210, 210, 26)
        col(ctx, C["panel"], pe)
        ctx.fill_preserve()
        col(ctx, C["visc"], 0.7 * pe)
        ctx.set_line_width(2)
        ctx.stroke()
        # orbital fat cushion behind the eye
        for i in range(9):
            ang = math.pi * 0.35 + i / 8 * math.pi * 1.3
            col(ctx, C["visc"], 0.9 * pe)
            circle(ctx, 22 + 62 * math.cos(ang), 62 * math.sin(ang), 18)
            ctx.fill()
        circle(ctx, -8, 0, 52)
        col(ctx, hexc("#F3F1EC"), pe)
        ctx.fill()
        circle(ctx, -42, 0, 22)
        col(ctx, hexc("#3E8EDE"), pe)
        ctx.fill()
        circle(ctx, -50, 0, 10)
        col(ctx, hexc("#0B0E14"), pe)
        ctx.fill()
        ctx.restore()
        text(ctx, "eye socket", ex, ey + 135, 24, C["muted"], pe, bold=False)

    # insulation: heat arrows bouncing back off the subcutaneous layer
    pin = window(t, cue.s(3), cue.s(4) + 0.2, 0.4, 0.5)
    if pin > 0:
        for i in range(8):
            ang = -math.pi / 2 + (i - 3.5) * 0.24
            ph = ((t - cue.s(3)) * 0.8 + i * 0.13) % 1.0
            r0 = 0.45
            r1 = 0.86
            k = ph * 2 if ph < 0.5 else 2 - ph * 2
            rr = lerp(r0, r1, k)
            x = cx + RX * rr * math.cos(ang)
            y = cy + RY * rr * math.sin(ang)
            heading_ang = math.atan2(RY * math.sin(ang), RX * math.cos(ang)) + (0 if ph < 0.5 else math.pi)
            arrow_head(ctx, x, y, heading_ang, 22, hexc("#FF7A59"), pin)
        pill(ctx, "Insulation", 1430, 620, C["subq"], pin, size=32)
    pcu = window(t, cue.s(4), D, 0.4, 0.6)
    if pcu > 0:
        k = clamp((t - cue.s(4)) / (cue.at(4, 0.4) - cue.s(4)))
        x = lerp(cx + 650, cx + 230, ease(k))
        ctx.set_line_width(10)
        col(ctx, C["ink"], pcu * (1 - prog(t, cue.at(4, 0.6), 0.5)))
        ctx.move_to(x + 120, cy + 120)
        ctx.line_to(x + 12, cy + 120)
        ctx.stroke()
        arrow_head(ctx, x - 10, cy + 120, math.pi, 34, C["ink"], pcu * (1 - prog(t, cue.at(4, 0.6), 0.5)))
        pill(ctx, "Cushion", 1430, 720, C["visc"], pcu, size=32)


# ================================================================ 4. THREE TYPES
def types(ctx, t, D, cue):
    heading(ctx, "Three types of adipocytes", t, cue.s(0), y=110)
    cols_x = [380, 960, 1540]
    cy = 450

    # WHITE
    pw = prog(t, cue.s(1), 0.9)
    if pw > 0:
        f = prog(t, cue.at(2, 0.1), 2.6)
        ctx.save()
        ctx.translate(cols_x[0], cy)
        ctx.scale(0.7 + 0.3 * ease_back(pw), 0.7 + 0.3 * ease_back(pw))
        white_cell(ctx, 0, 0, 200, f=f, a=pw)
        ctx.restore()
        text(ctx, "WHITE", cols_x[0], 735, 44, C["white"], pw)
        text(ctx, "one large droplet", cols_x[0], 785, 28, C["muted"], prog(t, cue.at(2, 0.4), 0.6), bold=False)
        text(ctx, "nucleus at the edge", cols_x[0], 822, 28, C["muted"], prog(t, cue.at(2, 0.8), 0.6), bold=False)
    # BROWN
    pb = prog(t, cue.s(3), 0.9)
    if pb > 0:
        pm = prog(t, cue.s(4), 2.2)
        ctx.save()
        ctx.translate(cols_x[1], cy)
        ctx.scale(0.7 + 0.3 * ease_back(pb), 0.7 + 0.3 * ease_back(pb))
        brown_cell(ctx, 0, 0, 140, mito_p=pm, a=pb, seed=3, n_drop=16)
        ctx.restore()
        text(ctx, "BROWN", cols_x[1], 735, 44, C["brown"], pb)
        text(ctx, "many small droplets", cols_x[1], 785, 28, C["muted"], prog(t, cue.at(3, 0.5), 0.6), bold=False)
        text(ctx, "packed with mitochondria", cols_x[1], 822, 28, C["muted"], prog(t, cue.at(4, 0.3), 0.6), bold=False)
        if pm > 0:
            mx, my = cols_x[1] + 175, cy - 150
            mito(ctx, mx, my, 16, -0.4, pm)
            text(ctx, "mitochondria", mx + 26, my - 20, 24, mix(C["brown"], C["ink"], 0.4), pm, align="left", bold=False)
    # BEIGE
    pg = prog(t, cue.s(5), 0.9)
    if pg > 0:
        ps = prog(t, cue.at(6, 0.35), 1.6)
        if ps > 0:
            for i in range(12):
                ang = i / 12 * 2 * math.pi + 0.2
                x, y = cols_x[2] + 205 * math.cos(ang), cy + 205 * math.sin(ang)
                pi = ease_back(clamp(ps * 2 - i / 12))
                if pi <= 0:
                    continue
                if i in (3, 8):
                    brown_cell(ctx, x, y, 34 * pi, a=clamp(pi), base=C["beige"], n_drop=6, seed=i)
                else:
                    white_cell(ctx, x, y, 40 * pi, f=1, a=clamp(pi) * 0.9, nuc_ang=ang)
        ctx.save()
        ctx.translate(cols_x[2], cy)
        ctx.scale(0.7 + 0.3 * ease_back(pg), 0.7 + 0.3 * ease_back(pg))
        brown_cell(ctx, 0, 0, 150, mito_p=0.6, a=pg, seed=8, base=C["beige"], n_drop=9)
        ctx.restore()
        text(ctx, "BEIGE", cols_x[2], 735, 44, C["beige"], pg)
        text(ctx, "discovered more recently", cols_x[2], 785, 28, C["muted"], prog(t, cue.at(5, 0.6), 0.6), bold=False)
        text(ctx, "scattered inside white fat", cols_x[2], 822, 28, C["muted"], prog(t, cue.at(6, 0.5), 0.6), bold=False)


# ================================================================ 5. WHITE FAT
def white(ctx, t, D, cue):
    tA = (0, cue.s(1))
    tB = (cue.s(1), cue.s(2))
    tC = (cue.s(2), cue.s(3))
    tD = (cue.s(3), D + 1)

    heading(ctx, "White fat", t, 0.2, y=105, c=C["white"])

    # A: dominant in adults
    a = window(t, *tA, 0.6, 0.5)
    if a > 0:
        text(ctx, "In adults", W / 2, 300, 40, C["muted"], a, bold=False)
        bars = [("White", C["white"], 1.0), ("Brown", C["brown"], 0.06)]
        for i, (lab, c, v) in enumerate(bars):
            y = 400 + i * 130
            p = prog(t, 0.7 + i * 0.3, 1.2)
            text(ctx, lab, 640, y + 15, 40, c, a, align="right")
            rrect(ctx, 680, y - 30, max(16, 700 * v * p), 60, 14)
            col(ctx, c, 0.9 * a)
            ctx.fill()
        text(ctx, "Dominant", 680 + 700 + 30, 415, 34, C["white"], a * prog(t, 1.6, 0.5), align="left")

    # B: layer beneath the skin
    b = window(t, *tB, 0.6, 0.5)
    if b > 0:
        x0, x1 = 360, 1400
        y = 230
        layers = [("Epidermis", C["skin"], 22), ("Dermis", hexc("#C98477"), 70),
                  ("Subcutaneous fat", C["white"], 240), ("Muscle", C["muscle"], 90)]
        yy = y
        for name, c, h in layers:
            if name == "Subcutaneous fat":
                rrect(ctx, x0, yy, x1 - x0, h, 4)
                col(ctx, hexc("#3A3326"), b)
                ctx.fill()
                rnd = random.Random(2)
                for i in range(70):
                    cxp = x0 + 40 + (i % 14) * ((x1 - x0 - 80) / 13) + rnd.uniform(-10, 10)
                    cyp = yy + 45 + (i // 14) * 38 + rnd.uniform(-6, 6)
                    if cyp > yy + h - 22:
                        continue
                    pi = clamp(prog(t, tB[0] + 0.3, 1.2) * 1.8 - i / 70)
                    if pi > 0:
                        white_cell(ctx, cxp, cyp, 30 * ease_back(pi), f=1, a=b * pi)
            else:
                rrect(ctx, x0, yy, x1 - x0, h, 4)
                col(ctx, c, 0.9 * b)
                ctx.fill()
            text(ctx, name, x1 + 30, yy + h / 2 + 12, 32, c if name != "Muscle" else mix(c, C["ink"], 0.4), b, align="left")
            yy += h + 4
        # bracket
        ctx.set_line_width(3)
        col(ctx, C["accent"], b)
        bx = x0 - 30
        ctx.move_to(bx + 14, y + 96)
        ctx.line_to(bx, y + 96)
        ctx.line_to(bx, y + 96 + 240)
        ctx.line_to(bx + 14, y + 96 + 240)
        ctx.stroke()

    # C: sex differences
    c_ = window(t, *tC, 0.6, 0.5)
    if c_ > 0:
        pf = prog(t, cue.at(2, 0.35), 0.9)
        pm = prog(t, cue.at(2, 0.75), 0.9)
        for (kind, x, p, lab, spots) in (
            ("female", 640, pf, "Women: thighs, breasts",
             [(-5.5, 63, 9), (5.5, 63, 9), (-4.5, 27, 6), (4.5, 27, 6)]),
            ("male", 1280, pm, "Men: abdomen", [(0, 41, 12)]),
        ):
            prims = body_prims(kind)
            s, top = 6.3, 180
            glow_body(ctx, prims, x, top, s, C["white"], c_ * 0.9)
            ctx.save()
            ctx.new_path()
            body_path(ctx, prims, x, top, s, -1)
            ctx.clip()
            for (ux, uy, ur) in spots:
                glow_circle(ctx, x + ux * s, top + uy * s, ur * s * 1.7, C["accent"], p * c_ * (0.85 + 0.15 * math.sin(t * 3)))
            ctx.restore()
            text(ctx, lab, x, 855, 36, C["ink"], p * c_)

    # D: histology
    d = prog(t, tD[0], 0.8)
    if d > 0:
        cx, cy, R = 960, 500, 330
        cells, _ = tissue(cx, cy, R, 86, seed=31, jitter=0.36)
        emp = prog(t, cue.at(3, 0.35), 2.4)
        ctx.save()
        circle(ctx, cx, cy, R)
        ctx.clip()
        col(ctx, mix(hexc("#2B1F1A"), hexc("#F6DCE8"), emp), d)
        ctx.paint()
        draw_tissue(ctx, cells, d, empty=emp, inset=3)
        ctx.restore()
        microscope_ring(ctx, cx, cy, R, d)
        callout(ctx, "lipid dissolves during preparation", cx + 230, cy - 190, 1380, 260, C["accent"],
                prog(t, cue.at(3, 0.45), 0.9), size=28)
        callout(ctx, "empty-looking cells", cx - 200, cy + 150, 520, 760, hexc("#E7A6C6"),
                prog(t, cue.at(3, 0.8), 0.9), size=28)


# ================================================================ 6. BROWN FAT
def brown(ctx, t, D, cue):
    heading(ctx, "Brown fat: the built-in heater", t, 0.2, y=105, c=C["brown"])
    lx = 560

    # left: baby -> adult
    a_baby = window(t, cue.s(1), cue.s(3) + 0.2, 0.8, 0.7)
    if a_baby > 0:
        prims = body_prims("baby")
        s, top = 6.0, 175
        glow_body(ctx, prims, lx, top, s, C["brown"], a_baby)
        ctx.save()
        ctx.new_path()
        body_path(ctx, prims, lx, top, s, -1)
        ctx.clip()
        for (ux, uy, ur) in ((0, 47, 14), (-8, 43, 7), (8, 43, 7), (0, 60, 8)):
            glow_circle(ctx, lx + ux * s, top + uy * s, ur * s * 1.6, C["brown"], a_baby * 0.9)
        ctx.restore()
        heat_waves(ctx, lx + 150, top + 120, t, hexc("#FF8A5B"), a_baby, n=3, h=80)
        p5 = prog(t, cue.at(1, 0.3), 1.2)
        n = ease_out((t - cue.at(1, 0.3)) / 1.5)
        text(ctx, f"≈{max(0, round(5 * n))}%", lx, 790, 64, C["brown"], p5 * a_baby)
        text(ctx, "of a newborn's body mass", lx, 835, 28, C["muted"], p5 * a_baby, bold=False)

    a_ad = prog(t, cue.s(3) - 0.1, 0.9)
    if a_ad > 0:
        prims = body_prims("neutral")
        s, top = 6.8, 150
        glow_body(ctx, prims, lx, top, s, C["muted"], a_ad * 0.8)
        spots = [((-4, 15.5), cue.at(3, 0.5), "neck", (-1, 0)),
                 ((0, 24), cue.at(3, 0.68), "between shoulder blades", (1, -1)),
                 ((1.5, 38), cue.at(3, 0.88), "near major vessels", (1, 1))]
        for (u, ts, lab, dirn) in spots:
            p = prog(t, ts, 0.7)
            x, y = lx + u[0] * s, top + u[1] * s
            glow_circle(ctx, x, y, 40, C["brown"], p * (0.85 + 0.15 * math.sin(t * 4)))
            col(ctx, C["brown"], p)
            circle(ctx, x, y, 9)
            ctx.fill()
            if dirn[0] < 0:
                callout(ctx, lab, x, y, x - 190, y - 40, C["brown"], p, size=28)
            else:
                callout(ctx, lab, x, y, x + 170, y + dirn[1] * 50, C["brown"], p, size=28)
        text(ctx, "small amounts remain in adults", lx, 860, 30, C["muted"], prog(t, cue.at(3, 0.25), 0.7), bold=False)

    # right side
    rx, ry = 1460, 470
    a_cell = window(t, cue.s(0), cue.s(2), 0.7, 0.6)
    if a_cell > 0:
        brown_cell(ctx, rx, ry, 170, mito_p=1.0, a=a_cell, seed=5, n_drop=14)
        heat_waves(ctx, rx, ry - 190, t, hexc("#FF8A5B"), a_cell, n=4, h=110, spread=60, width=5)
    a_flow = window(t, cue.s(2), D, 0.6, 0.6)
    if a_flow > 0:
        y = 380
        droplet(ctx, rx - 280, y, 52, hexc("#EBC58F"), a_flow)
        text(ctx, "Fat", rx - 280, y + 105, 30, C["ink"], a_flow)
        p1 = prog(t, cue.at(2, 0.2), 0.7)
        ctx.set_line_width(6)
        col(ctx, C["ink"], a_flow * p1)
        ctx.move_to(rx - 200, y)
        ctx.line_to(rx - 200 + 110 * p1, y)
        ctx.stroke()
        arrow_head(ctx, rx - 80 + 0 * p1, y, 0, 22, C["ink"], a_flow * p1)
        p2 = prog(t, cue.at(2, 0.4), 0.7)
        mito(ctx, rx, y, 34, 0.0, a_flow * p2)
        text(ctx, "Mitochondria", rx, y + 105, 30, C["ink"], a_flow * p2)
        p3 = prog(t, cue.at(2, 0.55), 0.7)
        heat_waves(ctx, rx + 220, y + 50, t, hexc("#FF8A5B"), a_flow * p3, n=3, h=100, spread=40, width=6)
        text(ctx, "Heat", rx + 220, y + 105, 34, hexc("#FF8A5B"), a_flow * p3)
        p4 = prog(t, cue.at(2, 0.75), 0.6)
        text(ctx, "Store", rx, y + 270, 40, C["muted"], a_flow * p4)
        ctx.set_line_width(5)
        col(ctx, C["bad"], a_flow * p4)
        ctx.move_to(rx - 70, y + 256)
        ctx.line_to(rx - 70 + 140 * prog(t, cue.at(2, 0.85), 0.4), y + 256)
        ctx.stroke()
        text(ctx, "burns energy instead", rx, y + 330, 30, C["muted"], a_flow * p4, bold=False)


# ================================================================ 7. ENDOCRINE ORGAN
def _brain(ctx, x, y, a, hi):
    c = mix(hexc("#E9A0B3"), (1, 1, 1), 0.2 * hi)
    for (dx, dy, rx, ry) in ((-30, 0, 62, 50), (30, 0, 62, 50), (0, -18, 70, 44)):
        ellipse(ctx, x + dx, y + dy, rx, ry)
        col(ctx, c, a)
        ctx.fill()
    ctx.set_line_width(3)
    col(ctx, hexc("#B5647A"), a)
    for k in range(5):
        ctx.move_to(x - 70 + k * 30, y - 30)
        ctx.curve_to(x - 50 + k * 30, y - 10, x - 80 + k * 30, y + 10, x - 60 + k * 30, y + 30)
    ctx.move_to(x, y - 55)
    ctx.line_to(x, y + 45)
    ctx.stroke()


def _liver(ctx, x, y, a, hi):
    ctx.new_path()
    ctx.move_to(x - 100, y - 30)
    ctx.curve_to(x - 60, y - 75, x + 60, y - 70, x + 105, y - 45)
    ctx.curve_to(x + 120, y - 20, x + 60, y + 10, x + 10, y + 45)
    ctx.curve_to(x - 30, y + 70, x - 110, y + 30, x - 100, y - 30)
    col(ctx, mix(hexc("#A8483B"), (1, 1, 1), 0.2 * hi), a)
    ctx.fill()
    ctx.set_line_width(3)
    col(ctx, hexc("#6B2A22"), a)
    ctx.move_to(x - 10, y - 62)
    ctx.curve_to(x - 5, y - 20, x + 15, y, x + 10, y + 40)
    ctx.stroke()


def _pancreas(ctx, x, y, a, hi):
    c = mix(hexc("#E6B07A"), (1, 1, 1), 0.2 * hi)
    for i in range(12):
        f = i / 11
        r = lerp(38, 14, f)
        circle(ctx, x - 100 + 200 * f, y + 10 * math.sin(f * 5), r)
        col(ctx, c, a)
        ctx.fill()


def _muscle(ctx, x, y, a, hi):
    ellipse(ctx, x, y, 120, 42, -0.15)
    col(ctx, mix(hexc("#C2414B"), (1, 1, 1), 0.2 * hi), a)
    ctx.fill()
    ctx.save()
    ctx.translate(x, y)
    ctx.rotate(-0.15)
    ctx.set_line_width(2.5)
    col(ctx, hexc("#7E1F2A"), a)
    for k in range(-4, 5):
        ctx.move_to(-95 + 0 * k, k * 7)
        ctx.curve_to(-30, k * 9, 30, k * 9, 95, k * 7)
    ctx.stroke()
    ctx.restore()


def endocrine(ctx, t, D, cue):
    cx, cy = 960, 470
    # fat tissue in the middle
    cells, _ = tissue(cx, cy, 130, 60, seed=41)
    grey = 1 - prog(t, cue.s(1), 1.0)
    a = prog(t, 0.1, 0.8)
    pulse = (1 - grey) * (0.5 + 0.5 * math.sin(t * 3))
    glow_circle(ctx, cx, cy, 260, C["accent"], (1 - grey) * 0.6 * (0.7 + 0.3 * pulse))
    ctx.save()
    circle(ctx, cx, cy, 140)
    ctx.clip()
    draw_tissue(ctx, cells, a, glow=pulse, tint=mix(C["white"], C["muted"], grey * 0.7), inset=3)
    ctx.restore()
    ctx.set_line_width(4)
    col(ctx, mix(C["accent"], C["muted"], grey), a)
    circle(ctx, cx, cy, 142)
    ctx.stroke()

    # passive fuel tank
    pt = window(t, cue.s(0) + 0.3, cue.s(1) + 0.2, 0.6, 0.5)
    if pt > 0:
        gx, gy = cx, cy - 230
        ctx.set_line_width(8)
        col(ctx, C["muted"], pt)
        ctx.new_path()
        ctx.arc(gx, gy, 60, math.pi, 2 * math.pi)
        ctx.stroke()
        ang = math.pi + math.pi * (0.85 - 0.1 * math.sin(t))
        ctx.set_line_width(5)
        col(ctx, C["ink"], pt)
        ctx.move_to(gx, gy)
        ctx.line_to(gx + 52 * math.cos(ang), gy + 52 * math.sin(ang))
        ctx.stroke()
        text(ctx, "E", gx - 80, gy + 8, 26, C["muted"], pt)
        text(ctx, "F", gx + 80, gy + 8, 26, C["muted"], pt)
        text(ctx, "Passive fuel tank?", cx, cy + 210, 38, C["muted"], pt)

    pe = window(t, cue.s(1), cue.s(3), 0.6, 0.5)
    text(ctx, "Endocrine organ", cx, cy + 215, 44, C["accent"], pe)

    # hormones
    ph = prog(t, cue.s(2), 0.6)
    if ph > 0:
        pill(ctx, "Leptin · fullness", cx - 250, cy - 200, C["hormone"], prog(t, cue.at(2, 0.25), 0.6), size=30)
        pill(ctx, "Adiponectin", cx + 250, cy - 200, C["hormone2"], prog(t, cue.at(2, 0.75), 0.6), size=30)
        rnd = random.Random(3)
        for i in range(26):
            ang = rnd.uniform(0, 6.28)
            sp = rnd.uniform(0.4, 1.0)
            f = ((t - cue.s(2)) * 0.22 * sp + rnd.random()) % 1.0
            r = lerp(150, 330, f)
            cc = C["hormone"] if i % 2 else C["hormone2"]
            col(ctx, cc, ph * math.sin(f * math.pi) * 0.9)
            circle(ctx, cx + r * math.cos(ang), cy + r * math.sin(ang) * 0.8, 6)
            ctx.fill()

    # target organs
    organs = [("Liver", _liver, (1500, 230), 0.25), ("Pancreas", _pancreas, (420, 720), 0.45),
              ("Muscle", _muscle, (1500, 720), 0.62), ("Brain", _brain, (420, 230), 0.85)]
    ir = prog(t, cue.at(4, 0.5), 0.8)
    for name, fn, (ox, oy), fr in organs:
        p = prog(t, cue.at(3, fr), 0.8)
        if p <= 0:
            continue
        hi = ir if name in ("Liver", "Muscle", "Pancreas") else 0
        # arrow path from blob to organ
        ang = math.atan2(oy - cy, ox - cx)
        sx, sy = cx + 160 * math.cos(ang), cy + 160 * math.sin(ang)
        ex, ey = ox - 150 * math.cos(ang), oy - 120 * math.sin(ang)
        mxp, myp = (sx + ex) / 2, (sy + ey) / 2
        nx, ny = -(ey - sy), (ex - sx)
        nl = math.hypot(nx, ny)
        ctrl = (mxp + nx / nl * 50, myp + ny / nl * 50)
        pts = bezier_pts((sx, sy), ctrl, ctrl, (ex, ey), 40)
        ctx.set_line_width(4)
        col(ctx, C["hormone"], 0.8 * p)
        ctx.new_path()
        poly_partial(ctx, pts, p)
        ctx.stroke()
        if p >= 1:
            ex2, ey2 = pts[-1]
            px2, py2 = pts[-3]
            arrow_head(ctx, ex2, ey2, math.atan2(ey2 - py2, ex2 - px2), 20, C["hormone"], 0.9)
            for j in range(3):
                f = ((t - cue.at(3, fr)) * 0.45 + j / 3) % 1.0
                x, y = poly_point(pts, f)
                col(ctx, C["hormone"], math.sin(f * math.pi))
                circle(ctx, x, y, 7)
                ctx.fill()
        if hi > 0:
            glow_circle(ctx, ox, oy, 190, C["visc"], hi * (0.7 + 0.3 * math.sin(t * 4)))
        ctx.save()
        ctx.translate(ox, oy)
        sc = 0.6 + 0.4 * ease_back(p)
        ctx.scale(sc, sc)
        fn(ctx, 0, 0, clamp(p * 1.5), hi)
        ctx.restore()
        text(ctx, name, ox, oy + 110, 32, C["ink"], p)

    pill(ctx, "Abdominal fat → insulin resistance", cx, cy + 215, C["visc"], prog(t, cue.at(4, 0.3), 0.7), size=32)


# ================================================================ 8. WHEN IT GOES WRONG
def wrong(ctx, t, D, cue):
    a_panels = 1 - prog(t, cue.s(2) - 0.3, 0.7)
    panels = [
        ("Too much", "Obesity", C["bad"], 520, cue.s(0),
         [("High blood pressure", 0.42), ("Type 2 diabetes", 0.58), ("Heart disease", 0.74), ("Stroke", 0.9)], 0),
        ("Too little", "Lipodystrophies (rare)", C["hormone2"], 1400, cue.s(1),
         [("Metabolic problems", 0.75)], 1),
    ]
    for (title, sub, c, px, ts, items, idx) in panels:
        p = prog(t, ts, 0.8) * a_panels
        if p <= 0:
            continue
        rrect(ctx, px - 400, 160 + 30 * (1 - p), 800, 680, 28)
        col(ctx, C["panel"], 0.9 * p)
        ctx.fill_preserve()
        col(ctx, c, 0.6 * p)
        ctx.set_line_width(2.5)
        ctx.stroke()
        text(ctx, title, px, 245, 52, c, p)
        text(ctx, sub, px, 295, 30, C["muted"], p, bold=False)
        # cell sketch: bloated vs sparse
        if idx == 0:
            for i, (dx, dy) in enumerate(((-90, 0), (0, -10), (90, 5), (-45, 70), (45, 72))):
                g = prog(t, ts + 0.3, 2.0)
                white_cell(ctx, px + dx * (1 + 0.12 * g), 390 + dy * 0.8, lerp(40, 52, g), f=1, a=p, nuc_ang=i * 1.3)
        else:
            for i, (dx, dy) in enumerate(((-110, 10), (0, -5), (110, 15))):
                white_cell(ctx, px + dx, 425 + dy, 26, f=0.6, a=p * 0.8, nuc_ang=i * 1.3)
        for k, (lab, fr) in enumerate(items):
            q = prog(t, cue.at(idx, fr), 0.5) * p
            y = 590 + k * 60
            col(ctx, c, q)
            circle(ctx, px - 230, y - 11, 9)
            ctx.fill()
            text(ctx, lab, px - 205, y, 34, C["ink"], q, align="left")

    # balance gauge
    g = prog(t, cue.s(2) - 0.1, 0.8)
    if g > 0:
        x0, x1, y = 360, 1560, 520
        text(ctx, "The goal isn't zero fat", W / 2, 260, 52, C["ink"], g)
        grad = cairo.LinearGradient(x0, 0, x1, 0)
        for stop, c in ((0, C["hormone2"]), (0.38, C["good"]), (0.62, C["good"]), (1, C["bad"])):
            grad.add_color_stop_rgba(stop, c[0], c[1], c[2], g)
        rrect(ctx, x0, y - 18, x1 - x0, 36, 18)
        ctx.set_source(grad)
        ctx.fill()
        text(ctx, "Too little", x0, y + 80, 30, C["muted"], g, align="left", bold=False)
        text(ctx, "Too much", x1, y + 80, 30, C["muted"], g, align="right", bold=False)
        m = prog(t, cue.s(3), 1.4)
        mx = lerp(x0 + 10, (x0 + x1) / 2, ease_out(m))
        col(ctx, C["ink"], g)
        ctx.move_to(mx, y - 30)
        ctx.line_to(mx - 18, y - 62)
        ctx.line_to(mx + 18, y - 62)
        ctx.close_path()
        ctx.fill()
        text(ctx, "0%", x0 + 10, y - 80, 30, C["bad"], g * (1 - m))
        if m > 0:
            text(ctx, "Healthy amount, right places", W / 2, 700, 46, C["good"], prog(t, cue.at(3, 0.3), 0.7))


# ================================================================ 9. OUTRO
def _icon(ctx, kind, x, y, c, a):
    ctx.set_line_width(6)
    col(ctx, c, a)
    if kind == "battery":
        rrect(ctx, x - 50, y - 28, 92, 56, 10)
        ctx.stroke()
        rrect(ctx, x + 44, y - 12, 10, 24, 3)
        ctx.fill()
        for i in range(3):
            rrect(ctx, x - 40 + i * 28, y - 18, 20, 36, 4)
            ctx.fill()
    elif kind == "shield":
        ctx.move_to(x, y - 55)
        ctx.curve_to(x + 30, y - 40, x + 50, y - 40, x + 50, y - 40)
        ctx.curve_to(x + 50, y + 10, x + 30, y + 40, x, y + 58)
        ctx.curve_to(x - 30, y + 40, x - 50, y + 10, x - 50, y - 40)
        ctx.curve_to(x - 50, y - 40, x - 30, y - 40, x, y - 55)
        ctx.close_path()
        ctx.stroke()
    elif kind == "flame":
        ctx.move_to(x, y + 55)
        ctx.curve_to(x - 55, y + 50, x - 50, y - 10, x - 10, y - 55)
        ctx.curve_to(x - 5, y - 20, x + 15, y - 15, x + 20, y - 35)
        ctx.curve_to(x + 55, y, x + 50, y + 50, x, y + 55)
        ctx.close_path()
        ctx.stroke()
    elif kind == "signal":
        circle(ctx, x, y + 10, 10)
        ctx.fill()
        for r in (28, 48):
            ctx.new_path()
            ctx.arc(x, y + 10, r, -math.pi * 0.85, -math.pi * 0.15)
            ctx.stroke()


def _emblem(ctx, x, y, r, a):
    glow_circle(ctx, x, y, r * 2.2, C["accent"], a * 0.5)
    circle(ctx, x, y, r)
    col(ctx, C["panel"], a)
    ctx.fill_preserve()
    col(ctx, C["accent"], a)
    ctx.set_line_width(5)
    ctx.stroke()
    droplet(ctx, x, y, r * 0.72, mix(C["white"], C["accent"], 0.35), a)
    nucleus(ctx, x + r * 0.6, y - r * 0.5, r * 0.17, rot=-0.7, flat=0.5, a=a)


def outro(ctx, t, D, cue):
    items = [("battery", "Stores energy", C["accent"], 0.12), ("shield", "Cushions organs", C["visc"], 0.36),
             ("flame", "Keeps you warm", C["brown"], 0.58), ("signal", "Sends signals", C["hormone"], 0.8)]
    out = prog(t, cue.s(2) - 0.4, 0.7)
    up = prog(t, cue.s(1), 0.8)
    for i, (kind, lab, c, fr) in enumerate(items):
        p = prog(t, cue.at(0, fr), 0.6) * (1 - out)
        if p <= 0:
            continue
        x = 360 + i * 400
        y = lerp(420, 300, up)
        ctx.save()
        ctx.translate(x, y)
        sc = 0.7 + 0.3 * ease_back(p)
        ctx.scale(sc, sc)
        circle(ctx, 0, 0, 100)
        col(ctx, c, 0.12 * p)
        ctx.fill()
        _icon(ctx, kind, 0, 0, c, p)
        ctx.restore()
        text(ctx, lab, x, y + 160, 34, C["ink"], p)
    pw = window(t, cue.s(1), cue.s(2) - 0.2, 0.7, 0.5)
    text(ctx, "Work with your body,", W / 2, 640, 50, C["ink"], pw)
    text(ctx, "not against it.", W / 2, 705, 50, C["accent"], pw)

    pe = prog(t, cue.s(2) - 0.3, 0.9)
    if pe > 0:
        _emblem(ctx, W / 2, 330, 90 * (0.8 + 0.2 * ease_back(pe)), pe)
        text(ctx, "ADIPOSE TISSUE", W / 2, 540, 70, C["ink"], pe)
        text(ctx, "Thanks for watching", W / 2, 610, 40, C["muted"], pe, bold=False)
        pill(ctx, "Subscribe for more", W / 2, 720, C["accent"], prog(t, cue.s(2) + 0.6, 0.6), size=34, fill_a=0.25)


SCENE_FUNCS = {
    "hook": hook, "what": what, "where": where, "types": types, "white": white,
    "brown": brown, "endocrine": endocrine, "wrong": wrong, "outro": outro,
}
