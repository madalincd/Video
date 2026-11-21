"""Render the video.

  python3 src/render.py                 full render -> build/adipose_tissue.mp4
  python3 src/render.py --stills        one PNG per scene cue -> build/stills/
  python3 src/render.py --only types    render a single scene

Each scene renders in its own process (frames piped to ffmpeg with its audio),
then the scene clips are concatenated.
"""
import argparse
import json
import math
import os
import subprocess
import sys
from multiprocessing import Pool

import cairo

sys.path.insert(0, os.path.dirname(__file__))
from gfx import C, FPS, H, W, clamp, col, font, prog, rrect, text, wrap  # noqa: E402
from scenes import SCENE_FUNCS, Cue  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD = os.path.join(ROOT, "build")
FADE = 0.45
SUB_SIZE = 40
SUB_MAXW = 1500


# ---------------------------------------------------------------- background
def make_background():
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
    ctx = cairo.Context(surf)
    g = cairo.RadialGradient(W / 2, H * 0.42, 100, W / 2, H / 2, W * 0.75)
    g.add_color_stop_rgb(0, *C["bg0"])
    g.add_color_stop_rgb(1, *C["bg1"])
    ctx.set_source(g)
    ctx.paint()
    return surf


# ---------------------------------------------------------------- subtitles
def subtitle_chunks(ctx, cues):
    """Split each sentence into <=2-line chunks, timed by character share."""
    chunks = []
    for i, c in enumerate(cues):
        lines = wrap(ctx, c["text"], SUB_SIZE, SUB_MAXW)
        groups = [lines[k:k + 2] for k in range(0, len(lines), 2)]
        total = sum(len(" ".join(g)) for g in groups)
        t = c["start"]
        dur = c["end"] - c["start"]
        nxt = cues[i + 1]["start"] if i + 1 < len(cues) else c["end"] + 0.6
        for gi, g in enumerate(groups):
            d = dur * len(" ".join(g)) / total
            end = t + d if gi < len(groups) - 1 else min(c["end"] + 0.35, nxt - 0.05)
            chunks.append((t, end, g))
            t += d
    return chunks


def draw_subtitle(ctx, t, chunks):
    for (s, e, lines) in chunks:
        if s - 0.1 <= t <= e + 0.1:
            a = clamp(min((t - s + 0.1) / 0.15, (e + 0.1 - t) / 0.15))
            font(ctx, SUB_SIZE)
            lh = SUB_SIZE * 1.3
            w = max(ctx.text_extents(l)[4] for l in lines) + 56
            h = lh * len(lines) + 30
            y0 = H - 50 - h
            rrect(ctx, W / 2 - w / 2, y0, w, h, 14)
            col(ctx, (0.02, 0.03, 0.05), 0.72 * a)
            ctx.fill()
            for k, l in enumerate(lines):
                text(ctx, l, W / 2, y0 + 15 + lh * (k + 0.78), SUB_SIZE, C["ink"], a)
            return


# ---------------------------------------------------------------- frames
def draw_frame(ctx, bg, scene, t, chunks):
    ctx.set_source_surface(bg)
    ctx.paint()
    D = scene["duration"]
    a = min(prog(t, 0, FADE), 1 - prog(t, D - FADE, FADE))
    ctx.push_group()
    ctx.set_line_cap(cairo.LINE_CAP_ROUND)
    ctx.set_line_join(cairo.LINE_JOIN_ROUND)
    SCENE_FUNCS[scene["id"]](ctx, t, D, Cue(scene["cues"]))
    ctx.pop_group_to_source()
    ctx.paint_with_alpha(a)
    draw_subtitle(ctx, t, chunks)


def render_scene(args):
    idx, scene = args
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
    ctx = cairo.Context(surf)
    bg = make_background()
    chunks = subtitle_chunks(ctx, scene["cues"])
    n = int(round(scene["duration"] * FPS))
    out = os.path.join(BUILD, "clips", f"{idx:02d}_{scene['id']}.mp4")
    audio = os.path.join(BUILD, "audio", f"{scene['id']}.wav")
    cmd = ["ffmpeg", "-y", "-loglevel", "error",
           "-f", "rawvideo", "-pix_fmt", "bgra", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
           "-i", audio,
           "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
           "-t", f"{n / FPS:.3f}", out]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for f in range(n):
        draw_frame(ctx, bg, scene, f / FPS, chunks)
        surf.flush()
        proc.stdin.write(bytes(surf.get_data()))
    proc.stdin.close()
    proc.wait()
    print(f"  rendered {scene['id']} ({n} frames)", flush=True)
    return out


def stills(timeline, only=None):
    os.makedirs(os.path.join(BUILD, "stills"), exist_ok=True)
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
    ctx = cairo.Context(surf)
    bg = make_background()
    for scene in timeline["scenes"]:
        if only and scene["id"] != only:
            continue
        chunks = subtitle_chunks(ctx, scene["cues"])
        times = [c["end"] - 0.2 for c in scene["cues"]]
        for k, t in enumerate(times):
            draw_frame(ctx, bg, scene, t, chunks)
            surf.write_to_png(os.path.join(BUILD, "stills", f"{scene['id']}_{k}.png"))
    print("stills written to", os.path.join(BUILD, "stills"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stills", action="store_true")
    ap.add_argument("--only")
    ap.add_argument("--jobs", type=int, default=os.cpu_count())
    args = ap.parse_args()
    with open(os.path.join(BUILD, "timeline.json")) as f:
        timeline = json.load(f)
    if args.stills:
        stills(timeline, args.only)
        return
    os.makedirs(os.path.join(BUILD, "clips"), exist_ok=True)
    work = [(i, s) for i, s in enumerate(timeline["scenes"]) if not args.only or s["id"] == args.only]
    work.sort(key=lambda w: -w[1]["duration"])
    with Pool(args.jobs) as pool:
        clips = sorted(pool.map(render_scene, work))
    if args.only:
        return
    lst = os.path.join(BUILD, "clips", "list.txt")
    with open(lst, "w") as f:
        for c in clips:
            f.write(f"file '{os.path.basename(c)}'\n")
    out = os.path.join(BUILD, "adipose_tissue.mp4")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst,
                    "-c", "copy", "-movflags", "+faststart", out], check=True)
    print("done:", out)


if __name__ == "__main__":
    main()
