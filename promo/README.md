# BR — الحزب الإصلاحي · promotional film

A procedural 3D motion-graphics film (1920×1080, 30 fps, ~3:12), rendered with
three.js in headless Chromium and encoded with ffmpeg. Every frame is a pure
function of time, so any range can be re-rendered on its own.

## Deliverables (`release/`)

| File | What it is |
| --- | --- |
| `BR_promo_1080p.mp4` | The film: Arabic captions burned in, music & sound design on the audio track, plus a selectable Arabic subtitle track |
| `BR_music_fx_mix.wav` | Music + sound design, dipped ~4 dB under each narration line: the clean bed for the Iraqi voice-over |
| `BR_music_stem.wav`, `BR_sfx_stem.wav` | Separate stems for re-mixing |
| `BR_captions_ar.srt` | Caption timings |
| `BR_vo_cue_sheet.txt` | Every narration line with its start time and length, for recording the voice-over |

No Iraqi Arabic voice was generated. Record the voice-over to the cue sheet and lay it
on top of `BR_music_fx_mix.wav`.

## Structure

The film follows the brief's scenes 1–6 and 11–18. Scenes 7–10 (data system, AI agent,
large-scale automation, internal/external systems) are not part of this cut.

| Time | Scene |
| --- | --- |
| 0:00 | Darkness, metal particles, the beam reveals the BR logo, the command center powers up, the presenter walks in |
| 0:25 | The floating timeline: 2022 (the structure forms), 2023 (systems switch on) |
| 0:54 | 2024: the logo is frozen inside glass |
| 1:06 | 2026: the glass cracks and shatters, THE RETURN, the headquarters expands into sectors |
| 1:20 | Technology hall holograms |
| 1:29 | Server corridor → POWERED BY PERA SERVICES |
| 1:39 | "We want experience", member profiles join departments |
| 1:54 | BR STRUCTURE: three divisions (العمليات · الاستخبارات · التجارة) |
| 2:17 | إنت تفيدنا / وإحنا نفيدك: value flowing both ways |
| 2:29 | The BR ecosystem ring |
| 2:36 | Presenter close-up: BUILD · DEVELOP · ORGANIZE |
| 2:46 | Timeline recap 2022 → 2026 |
| 2:55 | Everything converges into the BR logo, end card, fade, final impact |

## Rebuild

```bash
cd promo
npm install                                   # three.js
python3 tools/trace_logos.py                  # logos → assets/logos.json (only if the artwork changes)
node render.mjs --cues out/cues.json          # timing for the soundtrack
python3 tools/soundtrack.py out/cues.json out # music, sfx, mix, captions, cue sheet
node render.mjs --from 0 --to 48 --out out/chunks/c0.mp4   # …render ranges, in parallel if you like
tools/assemble.sh                             # join + mux → release/
```

Look at single frames with `node render.mjs --stills 12,68,186`, or watch it live by
serving `promo/` over HTTP and opening `film/index.html?play`.

## Editing

- **Narration / timing:** `film/cues.js`. Each line's length comes from its word count;
  pictures, captions, titles and sound cues all follow, so adding or removing lines
  re-times the whole film.
- **Camera & presenter blocking:** `film/direction.js`
- **Sets:** `film/set-hq.js` (command center), `film/set-timeline.js` (timeline + finale),
  `film/set-pera.js` (server corridor)
- **Presenter:** `film/presenter.js` loads `assets/presenter.glb` (a Mixamo-rigged figure,
  restyled in a black suit). Any Mixamo-rigged GLB with `idle`/`walk` clips can be
  swapped in.

Fonts: Noto Kufi Arabic and Sora (SIL Open Font License).
