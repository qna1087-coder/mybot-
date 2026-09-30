# BR — The Return (promo film)

A 90-second, 16:9 motion-graphics film drawn frame by frame on a canvas, with a score and sound design generated with Web Audio.

| File | What it is |
| --- | --- |
| `br-film.html` | Self-contained film player (fonts and logos embedded). Open it in a browser and press play. |
| `film.src.html` | Editable source. Scenes, captions (`CAPS`) and the score (`buildScore`) all live here. |
| `build.py` | Embeds the fonts and logos into `film.src.html` → `br-film.html` + `br-film.render.html`. |
| `render.js` | Renders the MP4 with Playwright + ffmpeg: `node render.js 4k out.mp4` (or `1080 out.mp4`). |
| `BR_voiceover.srt` | Voice-over script with timings, for recording the narrator. |

## Rebuild

```bash
npm i @fontsource/ibm-plex-sans-arabic @fontsource/ibm-plex-mono
python3 build.py
node render.js 4k BR_The_Return_4K.mp4
```

## Timeline

| Time | Scene |
| --- | --- |
| 0:00–0:08 | Opening: light beam reveals the metal BR mark, "مو مجرد تيم. / منظمة." |
| 0:08–0:25 | Timeline: 2022 founding → 2023 work begins → 2024 frozen → 2026 THE RETURN |
| 0:25–0:48 | Systems: BR DATA, AGENT, automation infrastructure, Powered by Pera Services |
| 0:48–1:05 | Structure: operations, intelligence, commerce |
| 1:05–1:17 | Philosophy: "إنت تفيدنا. وإحنا نفيدك." |
| 1:17–1:30 | Finale: EST. 2022 · REORGANIZED 2026, "المرحلة الجديدة بدأت." |
