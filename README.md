# Adipose Tissue: Your Body's Energy Bank

Educational explainer video, about 3:19, 1920x1080, 30 fps. Every graphic is drawn in code with Cairo. There are no third-party images.
The voiceover is generated locally with the open-source Kokoro TTS model, and each scene's length comes from its audio.
Subtitles are burned in and synced per sentence.

**Final videos**
- `output/adipose_tissue.mp4`: full version, 3:19, 16:9
- `output/adipose_tissue_reel45_vertical.mp4`: 45 s reel, 1080x1920
- `output/adipose_tissue_reel45.mp4`: 45 s reel, 16:9

45 s cut: `python3 src/tts.py --cut reel && python3 src/render.py --cut reel --vertical`. Its narration and cue retiming live in `REEL` in `src/script.py`.

## Rebuild

```bash
pip install -r requirements.txt          # ffmpeg must be on PATH
mkdir -p models
curl -L -o models/kokoro-v1.0.onnx https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx
curl -L -o models/voices-v1.0.bin  https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin

python3 src/tts.py                 # voiceover -> build/audio/*.wav + build/timeline.json
python3 src/render.py --stills     # quick preview PNGs per sentence -> build/stills/
python3 src/render.py              # full render -> build/adipose_tissue.mp4 (~1.5 min on 4 cores)
python3 src/render.py --only types # re-render one scene clip
```

Voice and pace: `VOICE=am_michael SPEED=0.95 python3 src/tts.py` (default `af_heart`, 0.9).

## Layout

| File | Purpose |
|---|---|
| `src/script.py` | Narration, split into sentences per scene |
| `src/tts.py` | Kokoro TTS, sentence timings to `timeline.json` |
| `src/gfx.py` | Palette, easing, text, body silhouettes, cell drawings |
| `src/scenes.py` | The 9 scenes, animated against sentence cues |
| `src/render.py` | Frame rendering, subtitles, ffmpeg encode and concat |

Accent colours: white fat cream, brown fat `#C0662C`, beige `#E3A96B`, subcutaneous amber, visceral coral, hormones teal/violet.
