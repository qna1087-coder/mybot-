"""Generate the Arabic voice-over, one file per narration line.

Usage: python tools/voiceover.py

Reads film/vo-script.json ([caption text, diacritized spoken text] pairs), checks it
matches the narration lines in film/cues.js, synthesizes each line with an offline
neural Arabic voice (Piper "ar_JO kareem", run through sherpa-onnx; it scored the
most intelligible of the available Arabic voices in a Whisper round-trip test) and writes
assets/vo/NN.wav plus assets/vo/durations.json, which the film uses for its timing.

Needs: pip install sherpa-onnx numpy. The voice model (~60 MB) is downloaded once
into ~/.cache/br-promo/.
"""

import json
import os
import re
import tarfile
import urllib.request
import wave
from pathlib import Path

import numpy as np
import sherpa_onnx

ROOT = Path(__file__).resolve().parent.parent
VOICE = os.environ.get("BR_VOICE", "vits-piper-ar_JO-kareem-medium")
URL = f"https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models/{VOICE}.tar.bz2"
CACHE = Path.home() / ".cache" / "br-promo"
LENGTH_SCALE = 0.78  # natural pace; still clear in the Whisper round-trip test


def ensure_model() -> Path:
    d = CACHE / VOICE
    if not (d / "tokens.txt").exists():
        CACHE.mkdir(parents=True, exist_ok=True)
        archive = CACHE / f"{VOICE}.tar.bz2"
        print(f"downloading {URL}")
        urllib.request.urlretrieve(URL, archive)
        with tarfile.open(archive) as t:
            t.extractall(CACHE, filter="data")
        archive.unlink()
    return d


def trim(x, sr=22050):
    loud = np.flatnonzero(np.abs(x) > 0.003 * np.max(np.abs(x)))
    return x[max(0, loud[0] - int(0.02 * sr)) : loud[-1] + int(0.12 * sr)]


def cue_lines() -> list[str]:
    src = (ROOT / "film" / "cues.js").read_text(encoding="utf-8")
    return re.findall(r"\{ vo: '([^']*)' \}", src)


def main() -> None:
    script = json.loads((ROOT / "film" / "vo-script.json").read_text(encoding="utf-8"))
    shown = [s for s, _ in script]
    expected = cue_lines()
    if shown != expected:
        missing = [x for x in expected if x not in shown]
        extra = [x for x in shown if x not in expected]
        raise SystemExit(f"vo-script.json is out of sync with cues.js\nmissing: {missing}\nextra: {extra}")

    model = ensure_model()
    onnx = next(model.glob("*.onnx"))
    cfg = sherpa_onnx.OfflineTtsConfig(
        model=sherpa_onnx.OfflineTtsModelConfig(
            vits=sherpa_onnx.OfflineTtsVitsModelConfig(
                model=str(onnx),
                tokens=str(model / "tokens.txt"),
                data_dir=str(model / "espeak-ng-data"),
                length_scale=LENGTH_SCALE,
                noise_scale=0.5,
                noise_scale_w=0.6,
            ),
            num_threads=4,
        )
    )
    tts = sherpa_onnx.OfflineTts(cfg)

    out = Path(os.environ.get("BR_VO_OUT", ROOT / "assets" / "vo"))
    out.mkdir(parents=True, exist_ok=True)
    durations = {}
    for i, (shown_text, spoken) in enumerate(script, 1):
        # "..." marks a deliberate pause: synthesize the pieces and breathe between them
        parts = []
        for k, piece in enumerate(p.strip() for p in spoken.split("...")):
            if not piece:
                continue
            audio = tts.generate(piece, sid=0, speed=1.0)
            seg = trim(np.asarray(audio.samples, dtype=np.float32))
            if k:
                parts.append(np.zeros(int(0.42 * audio.sample_rate), dtype=np.float32))
            parts.append(seg)
        x = np.concatenate(parts)
        x = x / (np.max(np.abs(x)) + 1e-9) * 0.9
        name = f"{i:02}.wav"
        with wave.open(str(out / name), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(audio.sample_rate)
            w.writeframes((x * 32767).astype("<i2").tobytes())
        durations[shown_text] = {"file": name, "dur": round(len(x) / audio.sample_rate, 3)}
        print(f"{name}  {durations[shown_text]['dur']:5.2f}s  {shown_text}")
    (out / "durations.json").write_text(json.dumps(durations, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"total speech {sum(d['dur'] for d in durations.values()):.1f}s")


if __name__ == "__main__":
    main()
