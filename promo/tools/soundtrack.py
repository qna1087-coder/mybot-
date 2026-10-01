"""Synthesize the film's music and sound design from the cue sheet.

Usage: python tools/soundtrack.py out/cues.json out/

Writes voice.wav (the narration from assets/vo, processed), music.wav, sfx.wav,
music_fx.wav (music + sound design with room left for a different voice-over),
mix.wav (everything), captions.srt and vo_cue_sheet.txt. Music and sound design are
procedural: no samples.
"""

import json
import sys
import wave
from pathlib import Path

import numpy as np
from scipy import signal

SR = 48000
RNG = np.random.default_rng(2026)


# ── helpers ──────────────────────────────────────────────────────────────────
def t_axis(dur):
    return np.arange(int(dur * SR)) / SR


def env_adsr(n, a, d, s, r, sustain=0.7):
    a, d, r = int(a * SR), int(d * SR), int(r * SR)
    hold = max(0, n - a - d - r)
    e = np.concatenate(
        [
            np.linspace(0, 1, a, endpoint=False),
            np.linspace(1, sustain, d, endpoint=False),
            np.full(hold, sustain),
            np.linspace(sustain, 0, r),
        ]
    )
    return np.pad(e, (0, max(0, n - len(e))))[:n]


def lowpass(x, hz, order=2):
    sos = signal.butter(order, hz, "low", fs=SR, output="sos")
    return signal.sosfilt(sos, x, axis=0)


def highpass(x, hz, order=2):
    sos = signal.butter(order, hz, "high", fs=SR, output="sos")
    return signal.sosfilt(sos, x, axis=0)


def bandpass(x, lo, hi, order=2):
    sos = signal.butter(order, [lo, hi], "band", fs=SR, output="sos")
    return signal.sosfilt(sos, x, axis=0)


def stereo(x, pan=0.0):
    left = np.cos((pan + 1) * np.pi / 4)
    right = np.sin((pan + 1) * np.pi / 4)
    return np.stack([x * left, x * right], axis=1)


def place(buf, clip, at):
    i = int(at * SR)
    if i >= len(buf):
        return
    if i < 0:
        clip = clip[-i:]
        i = 0
    n = min(len(clip), len(buf) - i)
    buf[i : i + n] += clip[:n]


def make_reverb(seconds=3.2, damp=6.0, seed=1):
    r = np.random.default_rng(seed)
    n = int(seconds * SR)
    tt = np.arange(n) / SR
    ir = r.standard_normal((n, 2)) * np.exp(-tt * damp / seconds)[:, None]
    ir = lowpass(ir, 6000)
    return ir / np.sqrt(np.sum(ir**2))


IR_LONG = make_reverb(4.0, 7.0, 3)
IR_MED = make_reverb(1.6, 6.0, 4)


def reverb(x, ir, wet=0.4):
    y = np.stack([signal.fftconvolve(x[:, c], ir[:, c])[: len(x)] for c in range(2)], axis=1)
    return x * (1 - wet) + y * wet


def noise(n):
    return RNG.standard_normal(n)


def curve(points, length):
    """Piecewise-linear automation from [(time, value), ...]."""
    pts = sorted(points)
    xs = np.array([p[0] for p in pts]) * SR
    ys = np.array([p[1] for p in pts])
    return np.interp(np.arange(length), xs, ys)


# ── sound design ─────────────────────────────────────────────────────────────
def sfx_impact(big=1.0):
    dur = 5.0
    tt = t_axis(dur)
    f = 30 + 55 * np.exp(-tt * 9)
    sub = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-tt * 1.1)
    body = lowpass(noise(len(tt)), 900) * np.exp(-tt * 9) * 0.9
    click = highpass(noise(len(tt)), 3000) * np.exp(-tt * 60) * 0.25
    x = (sub * 1.2 + body + click) * big
    return reverb(stereo(x), IR_LONG, 0.35)


def sfx_hit():
    dur = 2.5
    tt = t_axis(dur)
    f = 45 + 70 * np.exp(-tt * 14)
    sub = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-tt * 3)
    metal = sum(np.sin(2 * np.pi * h * tt + h) for h in (523, 1187, 1873, 2711)) * np.exp(-tt * 5) * 0.04
    x = sub * 0.7 + lowpass(noise(len(tt)), 1500) * np.exp(-tt * 18) * 0.4 + metal
    return reverb(stereo(x), IR_MED, 0.35)


def sfx_whoosh(dur=1.6, pan_from=-0.7, pan_to=0.7):
    tt = t_axis(dur)
    n = noise(len(tt))
    shape = np.sin(np.pi * np.clip(tt / dur, 0, 1)) ** 2
    # sweeping band: render in chunks with moving centre frequency
    out = np.zeros_like(n)
    chunk = 2048
    for i in range(0, len(n), chunk):
        u = i / len(n)
        fc = 300 + 3200 * np.sin(np.pi * u)
        seg = n[max(0, i - 4096) : i + chunk]
        out[i : i + chunk] = bandpass(seg, fc * 0.6, fc * 1.6)[-len(n[i : i + chunk]) :]
    out *= shape * 0.6
    pan = np.linspace(pan_from, pan_to, len(tt))
    left = np.cos((pan + 1) * np.pi / 4)
    right = np.sin((pan + 1) * np.pi / 4)
    return reverb(np.stack([out * left, out * right], axis=1), IR_MED, 0.3)


def sfx_riser(dur=1.4):
    tt = t_axis(dur)
    f = 120 * (2 ** (tt / dur * 3))
    tone = np.sin(2 * np.pi * np.cumsum(f) / SR) * 0.12
    nz = highpass(noise(len(tt)), 2000) * 0.18
    x = (tone + nz) * (tt / dur) ** 2.2
    return reverb(stereo(x), IR_MED, 0.4)


def sfx_beam():
    dur = 3.0
    tt = t_axis(dur)
    shimmer = sum(np.sin(2 * np.pi * f * tt) for f in (2093, 3136, 4186)) * 0.02
    air = highpass(noise(len(tt)), 5000) * 0.1
    x = (shimmer + air) * env_adsr(len(tt), 0.6, 0.6, 1.2, 1.4, 0.6)
    return reverb(stereo(x, -0.3), IR_LONG, 0.5)


def sfx_ui():
    dur = 0.6
    tt = t_axis(dur)
    x = np.sin(2 * np.pi * 1760 * tt) * np.exp(-tt * 30) * 0.12
    x += np.sin(2 * np.pi * 2637 * (tt - 0.07)) * np.exp(-np.clip(tt - 0.07, 0, None) * 30) * (tt > 0.07) * 0.08
    return reverb(stereo(x, 0.3), IR_MED, 0.3)


def sfx_power(up=True):
    dur = 2.2
    tt = t_axis(dur)
    k = tt / dur
    f = 55 * 2 ** ((k if up else 1 - k) * 2)
    x = np.sin(2 * np.pi * np.cumsum(f) / SR) * 0.22 * np.sin(np.pi * k)
    x += lowpass(noise(len(tt)), 400) * 0.1 * np.sin(np.pi * k)
    return reverb(stereo(x), IR_MED, 0.3)


def sfx_crack():
    dur = 1.4
    n = int(dur * SR)
    x = np.zeros(n)
    for _ in range(26):
        i = int(RNG.uniform(0, 1.2) * SR)
        ln = int(0.012 * SR)
        x[i : i + ln] += highpass(noise(ln), 2500) * np.exp(-np.arange(ln) / ln * 5) * RNG.uniform(0.2, 0.6)
    return reverb(stereo(x), IR_MED, 0.35)


def sfx_shatter():
    dur = 3.0
    n = int(dur * SR)
    x = highpass(noise(n), 1800) * np.exp(-t_axis(dur) * 5) * 0.5
    for _ in range(90):
        at = RNG.exponential(0.35)
        if at > 2.6:
            continue
        f = RNG.uniform(2500, 7000)
        tt = t_axis(0.25)
        tink = np.sin(2 * np.pi * f * tt) * np.exp(-tt * 28) * RNG.uniform(0.03, 0.09)
        i = int(at * SR)
        x[i : i + len(tink)] += tink[: n - i]
    return reverb(stereo(x), IR_LONG, 0.45)


def sfx_servers(dur):
    tt = t_axis(dur)
    hum = (np.sin(2 * np.pi * 50 * tt) * 0.05 + np.sin(2 * np.pi * 100 * tt) * 0.025)
    fans = lowpass(noise(len(tt)), 1200) * 0.06
    x = (hum + fans) * env_adsr(len(tt), 1.0, 0.5, 1, 1.5, 1.0)
    blips = np.zeros(len(tt))
    for _ in range(int(dur * 3)):
        i = int(RNG.uniform(0, dur - 0.1) * SR)
        b = np.sin(2 * np.pi * RNG.choice([2349, 2794, 3136]) * t_axis(0.05)) * 0.02
        blips[i : i + len(b)] += b
    return stereo(x) + stereo(blips, RNG.uniform(-0.8, 0.8))


# ── music ────────────────────────────────────────────────────────────────────
NOTE = {"D": 36.71, "Bb": 29.14, "F": 43.65, "C": 32.70, "G": 49.0, "A": 55.0}
# minor progression i – VI – III – VII
PROG = [("D", [0, 3, 7]), ("Bb", [0, 4, 7]), ("F", [0, 4, 7]), ("C", [0, 4, 7])]


def pad_voice(freq, n, detune=0.004):
    tt = np.arange(n) / SR
    vib = 1 + 0.002 * np.sin(2 * np.pi * 4.8 * tt)
    x = np.zeros(n)
    for k, amp in ((1, 1.0), (2, 0.42), (3, 0.22), (4, 0.12), (5, 0.07)):
        for d in (-detune, detune):
            x += amp * np.sin(2 * np.pi * freq * k * (1 + d) * np.cumsum(vib) / SR + k * 1.3)
    return x


def build_music(cues, length):
    m = cues["marks"]
    n = int(length * SR)
    out = np.zeros((n, 2))
    bpm = 96
    beat = 60 / bpm
    bar = 4 * beat
    chord_len = 2 * bar

    # intensity automation (0..1) for each layer
    drone_amt = curve(
        [(0, 0.0), (1.5, 0.6), (m["s2"], 0.8), (m["s4"], 0.8), (m["s4"] + 2, 0.45), (m["s5"], 0.6),
         (m["y2026"], 1.0), (m["s12"], 0.9), (m["s12"] + 1.5, 0.5), (m["s13"], 0.8), (m["s16"], 0.6),
         (m["s18"], 0.9), (m["finalLogo"], 1.0), (m["fade"], 1.0), (m["fade"] + 2, 0.0), (length, 0.0)], n)
    pad_amt = curve(
        [(0, 0.0), (m["logo"], 0.0), (m["hqReveal"], 0.5), (m["s2"], 0.6), (m["s4"], 0.65), (m["s5"], 0.4),
         (m["y2026"], 0.85), (m["s12"], 0.75), (m["s14"], 0.85), (m["s16"], 0.7), (m["s17"], 0.9),
         (m["finalLogo"], 1.0), (m["fade"], 0.9), (m["fade"] + 2.2, 0.0), (length, 0.0)], n)
    pulse_amt = curve(
        [(0, 0), (m["s2"], 0), (m["s2"] + 0.5, 0.55), (m["s4"], 0.55), (m["s4"] + 1, 0.0), (m["y2026"], 0.0),
         (m["y2026"] + 0.2, 0.9), (m["s12"] - 0.5, 0.9), (m["s12"], 0.0), (m["s13"], 0.0), (m["s13"] + 0.5, 0.7),
         (m["s16"], 0.7), (m["s16"] + 1, 0.2), (m["s17"], 0.9), (m["finalLogo"], 1.0), (m["lastLine"], 0.0),
         (length, 0)], n)
    arp_amt = curve(
        [(0, 0), (m["s3"], 0), (m["s3"] + 1, 0.45), (m["s4"], 0.0), (m["s6"], 0.0), (m["s6"] + 0.5, 0.6),
         (m["s12"], 0.0), (m["s13"], 0.3), (m["s14"], 0.0), (m["s15"], 0.45), (m["s16"], 0.0), (length, 0)], n)

    # Drone: low D with slow filter breathing
    tt = np.arange(n) / SR
    drone = np.zeros(n)
    for k, a in ((1, 1.0), (2, 0.5), (3, 0.3), (1.5, 0.25)):
        drone += a * np.sin(2 * np.pi * NOTE["D"] * k * tt + k)
    drone = lowpass(drone * (1 + 0.3 * np.sin(2 * np.pi * 0.07 * tt)), 260)
    out += stereo(drone * drone_amt * 0.16)

    # Pads: chord progression with soft attacks (strings-like)
    pad = np.zeros((n, 2))
    i = 0
    t0 = 0.0
    while t0 < length:
        root, iv = PROG[i % len(PROG)]
        seg = int(chord_len * SR) + int(1.5 * SR)
        for j, semi in enumerate(iv):
            f = NOTE[root] * 4 * 2 ** (semi / 12)
            v = pad_voice(f, seg) * env_adsr(seg, 1.4, 0.5, 1, 2.0, 0.8) * 0.05
            place(pad, stereo(v, (j - 1) * 0.5), t0)
        # high octave shimmer
        v = pad_voice(NOTE[root] * 8, seg, 0.006) * env_adsr(seg, 2.0, 0.5, 1, 2.0, 0.6) * 0.012
        place(pad, stereo(v, 0.2), t0)
        t0 += chord_len
        i += 1
    pad = lowpass(pad, 3500)
    out += reverb(pad, IR_LONG, 0.45) * pad_amt[:, None]

    # Pulse: controlled sub-bass on the beat + muted 8th ticks
    pulse = np.zeros((n, 2))
    k = 0
    tb = 0.0
    while tb < length:
        chord_root = PROG[int(tb // chord_len) % len(PROG)][0]
        ln = int(0.45 * SR)
        tt2 = np.arange(ln) / SR
        f = NOTE[chord_root] * 2 * (1 + 1.5 * np.exp(-tt2 * 40))
        kick = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-tt2 * 7) * (0.5 if k % 2 else 0.85)
        place(pulse, stereo(kick), tb)
        tick_len = int(0.05 * SR)
        tick = highpass(noise(tick_len), 7000) * np.exp(-np.arange(tick_len) / tick_len * 6) * 0.06
        place(pulse, stereo(tick, 0.4), tb + beat / 2)
        tb += beat
        k += 1
    out += pulse * pulse_amt[:, None] * 0.55

    # Arp: soft high plucks (technology sections)
    arp = np.zeros((n, 2))
    step = beat / 4
    ta = 0.0
    s = 0
    while ta < length:
        root, iv = PROG[int(ta // chord_len) % len(PROG)]
        semi = [iv[0], iv[1], iv[2], 12, iv[2], iv[1]][s % 6]
        f = NOTE[root] * 16 * 2 ** (semi / 12)
        ln = int(0.3 * SR)
        tt3 = np.arange(ln) / SR
        pl = np.sin(2 * np.pi * f * tt3) * np.exp(-tt3 * 16) * 0.05
        place(arp, stereo(pl, 0.6 * np.sin(s * 0.7)), ta)
        ta += step
        s += 1
    out += reverb(arp, IR_MED, 0.4) * arp_amt[:, None]

    # Final swell chord
    sw = int(9 * SR)
    swell = np.zeros(sw)
    for semi in (0, 7, 12, 15, 19):
        swell += pad_voice(NOTE["D"] * 4 * 2 ** (semi / 12), sw, 0.006)
    swell = lowpass(swell, 2600) * env_adsr(sw, 2.0, 1.0, 1, 4.5, 0.85) * 0.05
    place(out, reverb(stereo(swell), IR_LONG, 0.5), m["finalLogo"] - 1.5)
    return out


def build_sfx(cues, length):
    m = cues["marks"]
    n = int(length * SR)
    out = np.zeros((n, 2))
    makers = {
        "impact": lambda: sfx_impact(1.0),
        "final": lambda: sfx_impact(1.5),
        "hit": sfx_hit,
        "whoosh": sfx_whoosh,
        "riser": sfx_riser,
        "beam": sfx_beam,
        "ui": sfx_ui,
        "power": lambda: sfx_power(True),
        "powerdown": lambda: sfx_power(False),
        "crack": sfx_crack,
        "shatter": sfx_shatter,
        "build": lambda: sfx_riser(3.0) * 0.6,
        "converge": lambda: sfx_riser(2.6),
    }
    for c in cues["sfx"]:
        kind = c["kind"]
        if kind == "servers":
            place(out, sfx_servers(m["s12"] - c["time"] + 1.0), c["time"])
        elif kind in makers:
            gain = 0.8 if kind in ("whoosh", "ui") else 1.0
            place(out, makers[kind]() * gain, c["time"])
    # metallic particle sparkle in the opening darkness
    for _ in range(40):
        at = RNG.uniform(0.6, m["logo"])
        tt = t_axis(0.4)
        tink = np.sin(2 * np.pi * RNG.uniform(3000, 6500) * tt) * np.exp(-tt * 20) * 0.015
        place(out, reverb(stereo(tink, RNG.uniform(-0.9, 0.9)), IR_MED, 0.6), at)
    # command-center room tone
    tone_len = m["s2"] - m["hqReveal"]
    place(out, sfx_servers(tone_len) * 0.35, m["hqReveal"])
    return out


# ── voice ────────────────────────────────────────────────────────────────────
def read_wav_mono(path):
    with wave.open(str(path)) as w:
        sr = w.getframerate()
        x = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype(np.float64) / 32768
    return x, sr


def compress(x, threshold=0.25, ratio=3.0, attack=0.005, release=0.12):
    env = np.abs(x)
    a = np.exp(-1 / (attack * SR))
    r = np.exp(-1 / (release * SR))
    e = np.zeros_like(env)
    level = 0.0
    for i, v in enumerate(env):
        level = a * level + (1 - a) * v if v > level else r * level + (1 - r) * v
        e[i] = level
    gain = np.ones_like(e)
    over = e > threshold
    gain[over] = (threshold + (e[over] - threshold) / ratio) / e[over]
    return x * gain


def build_voice(cues, length, vo_dir):
    n = int(length * SR)
    out = np.zeros((n, 2))
    for c in cues["captions"]:
        if not c.get("file"):
            continue
        x, sr = read_wav_mono(vo_dir / c["file"])
        if sr != SR:
            g = np.gcd(SR, sr)
            x = signal.resample_poly(x, SR // g, sr // g)
        x = highpass(x, 80, 4)
        x = x + 0.35 * lowpass(x, 220)  # warmth
        x = x + 0.25 * bandpass(x, 2500, 6000)  # presence
        x = compress(x / (np.max(np.abs(x)) + 1e-9))
        x = x / (np.max(np.abs(x)) + 1e-9) * 0.8
        place(out, stereo(x), c["start"])
    return reverb(out, IR_MED, 0.12)


# ── output ───────────────────────────────────────────────────────────────────
def write_wav(path, x):
    x = np.clip(x, -1, 1)
    data = (x * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(data.tobytes())


def master(x, ceiling=0.89):
    peak = np.max(np.abs(x)) + 1e-9
    x = x / peak * 1.4
    x = np.tanh(x)  # gentle saturation / limiting
    return x / np.max(np.abs(x)) * ceiling


def srt_time(s):
    ms = int(round(s * 1000))
    h, ms = divmod(ms, 3600000)
    mi, ms = divmod(ms, 60000)
    se, ms = divmod(ms, 1000)
    return f"{h:02}:{mi:02}:{se:02},{ms:03}"


def main():
    cues = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    outdir = Path(sys.argv[2])
    outdir.mkdir(parents=True, exist_ok=True)
    length = cues["duration"]
    n = int(length * SR)

    music = build_music(cues, length)
    sfx = build_sfx(cues, length)
    voice = build_voice(cues, length, Path(__file__).resolve().parent.parent / "assets" / "vo")
    # dip the music under each narration line (~8 dB with the voice, ~4 dB without)
    talk = np.zeros(n)
    for c in cues["captions"]:
        a, b = int((c["start"] - 0.15) * SR), int((c["end"] + 0.25) * SR)
        talk[max(a, 0) : b] = 1
    talk = signal.filtfilt(*signal.butter(1, 3, fs=SR), talk)
    bed = music * (1 - 0.6 * talk)[:, None] * 0.9 + sfx * (1 - 0.35 * talk)[:, None] * 0.85
    bed_only = music * (1 - 0.37 * talk)[:, None] * 0.9 + sfx * 0.85
    write_wav(outdir / "voice.wav", master(voice, 0.8))
    write_wav(outdir / "music.wav", master(music, 0.8))
    write_wav(outdir / "sfx.wav", master(sfx, 0.8))
    write_wav(outdir / "music_fx.wav", master(bed_only))
    pv = np.max(np.abs(voice)) + 1e-9
    pb = np.max(np.abs(bed)) + 1e-9
    write_wav(outdir / "mix.wav", master(voice / pv * 1.0 + bed / pb * 0.55))

    lines = []
    for i, c in enumerate(cues["captions"], 1):
        lines += [str(i), f"{srt_time(c['start'])} --> {srt_time(c['end'])}", c["text"], ""]
    (outdir / "captions.srt").write_text("\n".join(lines), encoding="utf-8")

    sheet = ["BR — voice-over cue sheet (Iraqi Arabic)", f"Film length: {length:.1f} s", ""]
    for i, c in enumerate(cues["captions"], 1):
        sheet.append(f"{i:02}  {srt_time(c['start'])[:-4]}.{srt_time(c['start'])[-3:-1]}"
                     f"  ({c['end'] - c['start']:.1f} s)  {c['text']}")
    (outdir / "vo_cue_sheet.txt").write_text("\n".join(sheet) + "\n", encoding="utf-8")
    print(f"audio {length:.1f} s → {outdir}")


if __name__ == "__main__":
    main()
