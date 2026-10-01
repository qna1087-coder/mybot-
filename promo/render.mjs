// Render the film frame-by-frame in headless Chromium and encode with ffmpeg.
//
//   node render.mjs --stills 5,30,60         → out/stills/t005.00.png …
//   node render.mjs --from 0 --to 30 --out out/chunk0.mp4
//   node render.mjs --cues out/cues.json     → dump timing (captions, titles, sfx)
//   add --gpu to any of these to render on the graphics card
//
// Each frame is a pure function of time, so ranges can be rendered in parallel.

import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { createRequire } from 'node:module';

const ROOT = path.dirname(fileURLToPath(import.meta.url));
const require = createRequire(import.meta.url);
let chromium;
try {
  ({ chromium } = require('playwright'));
} catch {
  ({ chromium } = require('/opt/node22/lib/node_modules/playwright'));
}

const args = Object.fromEntries(
  process.argv.slice(2).reduce((acc, a, i, all) => {
    if (a.startsWith('--')) acc.push([a.slice(2), all[i + 1] && !all[i + 1].startsWith('--') ? all[i + 1] : true]);
    return acc;
  }, []),
);
const FPS = Number(args.fps || 30);

const TYPES = { '.html': 'text/html', '.js': 'text/javascript', '.json': 'application/json', '.ttf': 'font/ttf', '.glb': 'model/gltf-binary', '.png': 'image/png', '.jpg': 'image/jpeg' };
const server = http.createServer((req, res) => {
  const p = path.join(ROOT, decodeURIComponent(new URL(req.url, 'http://x').pathname));
  if (!p.startsWith(ROOT) || !fs.existsSync(p) || fs.statSync(p).isDirectory()) {
    res.writeHead(404).end();
    return;
  }
  res.writeHead(200, { 'content-type': TYPES[path.extname(p)] || 'application/octet-stream' });
  fs.createReadStream(p).pipe(res);
});
await new Promise((r) => server.listen(0, '127.0.0.1', r));
const port = server.address().port;

// --gpu renders on the machine's graphics card (much faster); the default is the
// software rasterizer, which works anywhere, including servers without a GPU.
const browser = await chromium.launch({
  executablePath: process.env.CHROMIUM || undefined,
  channel: args.gpu ? 'chromium' : undefined,
  args: args.gpu
    ? ['--ignore-gpu-blocklist', '--enable-gpu', '--disable-gpu-vsync']
    : ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist', '--disable-gpu-vsync'],
});
const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
page.setDefaultTimeout(300000);
page.on('console', (m) => m.type() === 'error' && console.error('[page]', m.text()));
page.on('pageerror', (e) => console.error('[page]', e.message));
await page.goto(`http://127.0.0.1:${port}/film/index.html?t=0${process.env.QS || ""}`);
await page.waitForFunction(() => window.film || window.filmError, null, { timeout: 180000 });
const err = await page.evaluate(() => window.filmError);
if (err) throw new Error(err);
const duration = await page.evaluate(() => window.film.duration);

const shot = async (t) => {
  await page.evaluate((tt) => window.film.renderFrame(tt), t);
  return page.screenshot({ type: 'jpeg', quality: 94, clip: { x: 0, y: 0, width: 1920, height: 1080 } });
};

if (args.cues) {
  const cues = await page.evaluate(() => window.film.cues);
  fs.mkdirSync(path.dirname(path.resolve(args.cues)), { recursive: true });
  fs.writeFileSync(args.cues, JSON.stringify(cues, null, 1));
  console.log(`cues → ${args.cues} (${duration.toFixed(2)} s)`);
} else if (args.stills) {
  const dir = path.join(ROOT, 'out/stills');
  fs.mkdirSync(dir, { recursive: true });
  for (const s of String(args.stills).split(',')) {
    const t = Number(s);
    const t0 = Date.now();
    // warm the motion trail with the previous few frames
    for (let k = 3; k > 0; k--) await page.evaluate((tt) => window.film.renderFrame(tt), Math.max(0, t - k / FPS));
    const buf = await shot(t);
    const f = path.join(dir, `t${t.toFixed(2).padStart(6, '0')}.jpg`);
    fs.writeFileSync(f, buf);
    console.log(f, `${Date.now() - t0} ms`);
  }
} else {
  const from = Number(args.from || 0);
  const to = Math.min(Number(args.to || duration), duration);
  const out = path.resolve(args.out || path.join(ROOT, 'out/film_video.mp4'));
  fs.mkdirSync(path.dirname(out), { recursive: true });
  const ff = spawn('ffmpeg', ['-y', '-loglevel', 'error', '-f', 'image2pipe', '-framerate', String(FPS), '-c:v', 'mjpeg', '-i', '-',
    '-c:v', 'libx264', '-preset', 'medium', '-crf', '17', '-pix_fmt', 'yuv420p', '-r', String(FPS), out], { stdio: ['pipe', 'inherit', 'inherit'] });
  const f0 = Math.round(from * FPS);
  const f1 = Math.round(to * FPS);
  for (let k = 3; k > 0; k--) await page.evaluate((tt) => window.film.renderFrame(tt), Math.max(0, (f0 - k) / FPS));
  const t0 = Date.now();
  for (let f = f0; f < f1; f++) {
    const buf = await shot(f / FPS);
    if (!ff.stdin.write(buf)) await new Promise((r) => ff.stdin.once('drain', r));
    if ((f - f0) % 60 === 0) {
      const done = f - f0 + 1;
      const eta = ((Date.now() - t0) / done) * (f1 - f) / 1000;
      console.log(`${path.basename(out)} frame ${f}/${f1} (${(f / FPS).toFixed(1)} s) eta ${eta.toFixed(0)} s`);
    }
  }
  ff.stdin.end();
  await new Promise((r) => ff.on('close', r));
  console.log(`done → ${out}`);
}

await browser.close();
server.close();
