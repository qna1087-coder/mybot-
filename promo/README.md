# BR — الحزب الإصلاحي · promotional film

A procedural 3D motion-graphics film (1920×1080, 30 fps, ~3:50) with an Arabic voice-over,
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

The narration is an ElevenLabs recording (voice "Sufyan"), delivered as one file, cut into
the 61 lines (`assets/vo/NN.wav`) and imported with `tools/import_vo.py`. The film's timing
follows the recordings: `assets/vo/durations.json` sets how long each caption, and so each
scene, lasts.

To replace the voice, generate the lines from `tts/` (one file per line, named 01–61) and
run `python3 tools/import_vo.py <folder>`. `tools/voiceover.py` can still synthesize an
offline fallback voice from the diacritized lines in `film/vo-script.json`.

## Structure

The film follows the brief's scenes 1–6 and 11–18. Scenes 7–10 (data system, AI agent,
large-scale automation, internal/external systems) are not part of this cut.

| Time | Scene |
| --- | --- |
| 0:00 | Darkness, metal particles, the beam reveals the BR logo, the command center powers up, the presenter walks in |
| 0:26 | The floating timeline: 2022 (the structure forms), 2023 (systems switch on) |
| 1:02 | 2024: the logo is frozen inside glass |
| 1:16 | 2026: the glass cracks and shatters into gold, THE RETURN, the headquarters expands into sectors |
| 1:32 | Technology hall holograms |
| 1:41 | Server corridor → POWERED BY PERA SERVICES |
| 1:52 | "We want experience", member profiles join departments |
| 2:07 | BR STRUCTURE: three divisions (العمليات · الاستخبارات · التجارة) |
| 2:38 | إنت تفيدنا / وإحنا نفيدك: value flowing both ways |
| 2:53 | The BR ecosystem ring |
| 3:04 | Presenter close-up: BUILD · DEVELOP · ORGANIZE |
| 3:17 | Timeline recap 2022 → 2026 |
| 3:30 | Everything converges into the BR logo, end card, fade, final impact |

## Render on a PC with a graphics card

On a machine with a GPU (e.g. RTX 4060) the whole film builds in roughly 10–25 minutes,
instead of hours on a CPU-only server. On Windows:

```powershell
winget install OpenJS.NodeJS.LTS Python.Python.3.12 Gyan.FFmpeg Git.Git
git clone -b claude/br-promotional-film-qfvb7p https://github.com/qna1087-coder/mybot-.git
cd mybot-\promo
npm install
npx playwright install chromium
pip install numpy scipy
node make.mjs --gpu
```

The finished film lands in `release/BR_promo_1080p.mp4`.

## Rebuild

```bash
cd promo
npm install                                   # three.js
python3 tools/trace_logos.py                  # logos → assets/logos.json (only if the artwork changes)
python3 tools/import_vo.py <folder>           # voice recordings → assets/vo/ (or tools/voiceover.py for the offline voice)
node render.mjs --cues out/cues.json          # timing for the soundtrack
python3 tools/soundtrack.py out/cues.json out # voice processing, music, sfx, mixes, captions, cue sheet
node render.mjs --from 0 --to 67 --out out/chunks/c0.mp4   # …render ranges in parallel (the software GPU uses one core each)
tools/assemble.sh                             # join + mux → release/
# or all of the above in one go: node make.mjs [--gpu] [--workers N]
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
