# BR — الحزب الإصلاحي · promotional film

A procedural 3D motion-graphics film (1920×1080, 30 fps, ~4:26) with an Arabic voice-over,
rendered with three.js in headless Chromium and encoded with ffmpeg. Every frame is a pure
function of time, so any range can be re-rendered on its own.

Look: black, graphite, silver and white with champagne-gold accents. The presenter wears a
tailored black suit (white shirt, tie with gold clip, satin lapels, gold buttons) with a
gold-embroidered BR emblem on the chest.

## Deliverables (`release/`)

| File | What it is |
| --- | --- |
| `BR_promo_1080p.mp4` | The film: voice-over, music and sound design; Arabic captions burned in, plus a selectable Arabic subtitle track |
| `BR_full_mix.wav` | The film's soundtrack (voice + music + sound design) |
| `BR_voice_stem.wav` | Narration only |
| `BR_music_fx_no_voice.wav` | Music + sound design without the voice, for re-recording with a human narrator |
| `BR_music_stem.wav`, `BR_sfx_stem.wav` | Separate stems for re-mixing |
| `BR_captions_ar.srt` | Caption timings |
| `BR_vo_cue_sheet.txt` | Every narration line with its start time and length |

## Voice-over

The narration is synthesized offline by `tools/voiceover.py` from `film/vo-script.json`,
which pairs each caption with a hand-diacritized spoken form (the tashkeel fixes
pronunciation; years are written out as words, "BR" is spoken "بي آر", "Pera" "بيرا").
The voice is Piper's Arabic "kareem" model run through sherpa-onnx. In a Whisper
round-trip test it was the most intelligible of the available Arabic voices. It speaks
with a Levantine/MSA accent rather than an Iraqi one. For a native Iraqi narrator, record
to `BR_vo_cue_sheet.txt` and lay the recording over `BR_music_fx_no_voice.wav`.

The film's timing follows the recordings: `assets/vo/durations.json` sets how long each
caption (and so each scene) lasts.

## Structure

The film follows the brief's scenes 1–6 and 11–18. Scenes 7–10 (data system, AI agent,
large-scale automation, internal/external systems) are not part of this cut.

| Time | Scene |
| --- | --- |
| 0:00 | Darkness, metal particles, the beam reveals the BR logo, the command center powers up, the presenter walks in |
| 0:28 | The floating timeline: 2022 (the structure forms), 2023 (systems switch on) |
| 1:11 | 2024: the logo is frozen inside glass |
| 1:27 | 2026: the glass cracks and shatters into gold, THE RETURN, the headquarters expands into sectors |
| 1:45 | Technology hall holograms |
| 1:57 | Server corridor → POWERED BY PERA SERVICES |
| 2:12 | "We want experience", member profiles join departments |
| 2:30 | BR STRUCTURE: three divisions (العمليات · الاستخبارات · التجارة) |
| 3:07 | إنت تفيدنا / وإحنا نفيدك: value flowing both ways |
| 3:25 | The BR ecosystem ring |
| 3:35 | Presenter close-up: BUILD · DEVELOP · ORGANIZE |
| 3:50 | Timeline recap 2022 → 2026 |
| 4:06 | Everything converges into the BR logo, end card, fade, final impact |

## Rebuild

```bash
cd promo
npm install                                   # three.js
python3 tools/trace_logos.py                  # logos → assets/logos.json (only if the artwork changes)
pip install sherpa-onnx && python3 tools/voiceover.py   # voice → assets/vo/ (downloads the voice model once)
node render.mjs --cues out/cues.json          # timing for the soundtrack
python3 tools/soundtrack.py out/cues.json out # voice processing, music, sfx, mixes, captions, cue sheet
node render.mjs --from 0 --to 67 --out out/chunks/c0.mp4   # …render ranges in parallel (the software GPU uses one core each)
tools/assemble.sh                             # join + mux → release/
```

Look at single frames with `node render.mjs --stills 12,68,186`, or watch it live by
serving `promo/` over HTTP and opening `film/index.html?play`.

## Editing

- **Narration / timing:** `film/cues.js`. Each line lasts as long as its recording (or a
  word-count estimate before the voice is generated); pictures, captions, titles and
  sound cues all follow, so adding or removing lines re-times the whole film.
- **Camera & presenter blocking:** `film/direction.js`
- **Sets:** `film/set-hq.js` (command center), `film/set-timeline.js` (timeline + finale),
  `film/set-pera.js` (server corridor)
- **Presenter:** `film/presenter.js` loads `assets/presenter.glb` (a Mixamo-rigged figure)
  and paints the suit on in a shader by body region (`SUIT_GLSL`). Any Mixamo-rigged GLB
  with `idle`/`walk` clips can be swapped in.
- **Narration text / pronunciation:** `film/vo-script.json`, then re-run `tools/voiceover.py`.

Fonts: Noto Kufi Arabic and Sora (SIL Open Font License).
