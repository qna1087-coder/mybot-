# Vigil · Promo video

Programmatic 3D motion graphic (Three.js) rendered frame-by-frame with headless Chromium → ffmpeg.

```bash
cd promo
npm install
node render.mjs vigil-promo-silent.mp4 30         # 64 s, 1920×1080
node render.mjs --stills 4,15,48                   # preview frames into stills/
python bench_guards.py 1000                        # regenerate the benchmark numbers shown in the video
```

Benchmark numbers in scene 05 come from `bench_guards.py` (real `GuardPipeline`, 1,000 synthetic posts,
the AI moderation call stubbed and excluded from timing) and `pytest` (28 tests).
