"""Bring in an externally recorded or generated voice-over.

Usage: python tools/import_vo.py path/to/folder

The folder holds one audio file per narration line, named by line number as listed in
tts/BR_tts_lines.txt: 01.wav (or 01.mp3, 1.m4a, 01 - anything.ogg …) up to 61. Any format
ffmpeg can read works. Each file is converted to 48 kHz mono, trimmed of leading and
trailing silence, peak-normalized and written to assets/vo/NN.wav; assets/vo/durations.json
is rewritten so the film re-times itself to the new recordings.

After importing: node render.mjs --cues out/cues.json, then tools/soundtrack.py and a
re-render (see README.md).
"""

import json
import re
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
SR = 48000
AUDIO = {".wav", ".mp3", ".m4a", ".aac", ".ogg", ".opus", ".flac", ".webm"}


def decode(path: Path) -> np.ndarray:
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path), "-ac", "1", "-ar", str(SR), "-f", "s16le", "-"],
        check=True,
        capture_output=True,
    ).stdout
    return np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768


def trim(x: np.ndarray) -> np.ndarray:
    # 20 ms RMS windows; keep from the first to the last window above -45 dB of the peak
    win = int(0.02 * SR)
    n = len(x) // win
    rms = np.sqrt(np.mean(x[: n * win].reshape(n, win) ** 2, axis=1))
    loud = np.flatnonzero(rms > np.max(rms) * 10 ** (-45 / 20))
    a = max(0, (loud[0] - 1) * win)
    b = min(len(x), (loud[-1] + 2) * win + int(0.08 * SR))
    return x[a:b]


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    src = Path(sys.argv[1])
    script = json.loads((ROOT / "film" / "vo-script.json").read_text(encoding="utf-8"))
    found = {}
    for f in sorted(src.iterdir()):
        m = re.match(r"\s*0*(\d+)", f.stem)
        if f.suffix.lower() in AUDIO and m:
            found.setdefault(int(m.group(1)), f)
    missing = [i for i in range(1, len(script) + 1) if i not in found]
    if missing:
        raise SystemExit(f"missing recordings for lines: {', '.join(f'{i:02}' for i in missing)}")

    out = ROOT / "assets" / "vo"
    out.mkdir(parents=True, exist_ok=True)
    durations = {}
    for i, (caption, _) in enumerate(script, 1):
        x = trim(decode(found[i]))
        x = x / (np.max(np.abs(x)) + 1e-9) * 0.9
        name = f"{i:02}.wav"
        with wave.open(str(out / name), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(SR)
            w.writeframes((x * 32767).astype("<i2").tobytes())
        durations[caption] = {"file": name, "dur": round(len(x) / SR, 3)}
        print(f"{name}  {durations[caption]['dur']:5.2f}s  ← {found[i].name}")
    (out / "durations.json").write_text(json.dumps(durations, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"total speech {sum(d['dur'] for d in durations.values()):.1f}s")


if __name__ == "__main__":
    main()
