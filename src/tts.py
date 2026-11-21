"""Synthesize the voiceover with Kokoro and write a timeline.

Output:
  build/audio/<scene>.wav   one file per scene (lead-in + sentences + tail)
  build/timeline.json       scene durations and per-sentence start/end times

Scene length is driven entirely by the audio, as the production notes require.
"""
import json
import os
import re
import sys

import numpy as np
import soundfile as sf

sys.path.insert(0, os.path.dirname(__file__))
from script import REEL, SCENES, TTS_REPLACEMENTS  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD = os.path.join(ROOT, "build")
MODEL_DIR = os.environ.get("KOKORO_DIR", os.path.join(ROOT, "models"))

VOICE = os.environ.get("VOICE", "af_heart")
SPEED = float(os.environ.get("SPEED", "0.9"))
LEAD = 0.8          # silence before the first sentence of a scene
GAP = 0.55          # silence between sentences
TAIL = 1.1          # silence after the last sentence (room for transitions)


def tts_text(s):
    for a, b in TTS_REPLACEMENTS.items():
        s = re.sub(re.escape(a), b, s, flags=re.I)
    return s


def trim(samples, sr, thresh=0.004):
    """Strip leading/trailing near-silence so gaps are consistent."""
    idx = np.where(np.abs(samples) > thresh)[0]
    if len(idx) == 0:
        return samples
    a = max(0, idx[0] - int(0.02 * sr))
    b = min(len(samples), idx[-1] + int(0.06 * sr))
    return samples[a:b]


def main():
    import argparse
    from kokoro_onnx import Kokoro

    global BUILD, SPEED, LEAD, GAP, TAIL
    ap = argparse.ArgumentParser()
    ap.add_argument("--cut", choices=["full", "reel"], default="full")
    args = ap.parse_args()
    scenes = SCENES
    if args.cut == "reel":
        scenes = REEL
        BUILD = os.path.join(BUILD, "reel")
        SPEED = float(os.environ.get("SPEED", "0.93"))
        LEAD, GAP, TAIL = 0.4, 0.4, 0.7
    os.makedirs(os.path.join(BUILD, "audio"), exist_ok=True)
    k = Kokoro(os.path.join(MODEL_DIR, "kokoro-v1.0.onnx"),
               os.path.join(MODEL_DIR, "voices-v1.0.bin"))
    timeline = {"voice": VOICE, "speed": SPEED, "scenes": []}
    for scene in scenes:
        pieces, cues = [], []
        sr = 24000
        t = LEAD
        pieces.append(np.zeros(int(LEAD * sr), dtype=np.float32))
        for i, sentence in enumerate(scene["sentences"]):
            samples, sr = k.create(tts_text(sentence), voice=VOICE, speed=SPEED, lang="en-us")
            samples = trim(samples.astype(np.float32), sr)
            dur = len(samples) / sr
            cues.append({"text": sentence, "start": round(t, 3), "end": round(t + dur, 3)})
            pieces.append(samples)
            t += dur
            pad = GAP if i < len(scene["sentences"]) - 1 else TAIL
            pieces.append(np.zeros(int(pad * sr), dtype=np.float32))
            t += pad
        audio = np.concatenate(pieces)
        path = os.path.join(BUILD, "audio", f"{scene['id']}.wav")
        sf.write(path, audio, sr)
        duration = len(audio) / sr
        entry = {"id": scene["id"], "duration": round(duration, 3), "cues": cues}
        if "uses" in scene:
            entry["uses"], entry["map"] = scene["uses"], scene["map"]
        timeline["scenes"].append(entry)
        print(f"{scene['id']:<10} {duration:6.2f}s  ({len(cues)} sentences)")
    total = sum(s["duration"] for s in timeline["scenes"])
    timeline["total"] = round(total, 3)
    with open(os.path.join(BUILD, "timeline.json"), "w") as f:
        json.dump(timeline, f, indent=2)
    print(f"total      {total:6.2f}s  ({int(total // 60)}:{total % 60:04.1f})")


if __name__ == "__main__":
    main()
