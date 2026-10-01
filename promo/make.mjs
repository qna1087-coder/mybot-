// One command for the whole film: timing → soundtrack → parallel render → final MP4.
//
//   node make.mjs --gpu              (on a PC with a graphics card)
//   node make.mjs --workers 4        (software rendering, e.g. on a server)
//
// Needs Node 18+, ffmpeg on PATH, Python 3 with numpy + scipy, and `npm install`.
// Output: release/BR_promo_1080p.mp4 plus stems, captions and the cue sheet.

import { spawn, spawnSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = path.dirname(fileURLToPath(import.meta.url));
process.chdir(ROOT);
const argv = process.argv.slice(2);
const gpu = argv.includes('--gpu');
const wi = argv.indexOf('--workers');
const workers = wi >= 0 ? Number(argv[wi + 1]) : gpu ? 3 : 4;
const extra = gpu ? ['--gpu'] : [];

const run = (cmd, a) => {
  console.log(`\n$ ${cmd} ${a.join(' ')}`);
  const r = spawnSync(cmd, a, { stdio: 'inherit', shell: process.platform === 'win32' });
  if (r.status !== 0) throw new Error(`${cmd} failed`);
};
const python = ['python3', 'python', 'py'].find(
  (p) => spawnSync(p, ['--version'], { shell: process.platform === 'win32' }).status === 0,
);
if (!python) throw new Error('Python 3 not found');

fs.mkdirSync('out/chunks', { recursive: true });
fs.mkdirSync('release', { recursive: true });

run('node', ['render.mjs', '--cues', 'out/cues.json', ...extra]);
run(python, ['tools/soundtrack.py', 'out/cues.json', 'out']);

const { duration } = JSON.parse(fs.readFileSync('out/cues.json', 'utf8'));
const t0 = Date.now();
await Promise.all(
  Array.from({ length: workers }, (_, i) => {
    const from = ((i * duration) / workers).toFixed(4);
    const to = (((i + 1) * duration) / workers).toFixed(4);
    const out = `out/chunks/c${i}.mp4`;
    return new Promise((resolve, reject) => {
      const p = spawn('node', ['render.mjs', '--from', from, '--to', to, '--out', out, ...extra], {
        stdio: ['ignore', 'pipe', 'inherit'],
      });
      p.stdout.on('data', (d) => process.stdout.write(`[${i}] ${d}`));
      p.on('close', (code) => (code === 0 ? resolve() : reject(new Error(`worker ${i} failed`))));
    });
  }),
);
console.log(`\nrendered in ${((Date.now() - t0) / 60000).toFixed(1)} min`);

const list = Array.from({ length: workers }, (_, i) => `file 'c${i}.mp4'`).join('\n');
fs.writeFileSync('out/chunks/list.txt', `${list}\n`);
run('ffmpeg', ['-y', '-loglevel', 'error', '-f', 'concat', '-safe', '0', '-i', 'out/chunks/list.txt', '-c', 'copy', 'out/video_only.mp4']);
run('ffmpeg', ['-y', '-loglevel', 'error', '-i', 'out/video_only.mp4', '-i', 'out/mix.wav', '-i', 'out/captions.srt',
  '-map', '0:v', '-map', '1:a', '-map', '2:s', '-c:v', 'libx264', '-preset', 'slow', '-crf', '21', '-pix_fmt', 'yuv420p',
  '-movflags', '+faststart', '-c:a', 'aac', '-b:a', '256k', '-c:s', 'mov_text',
  '-metadata:s:a:0', 'title=Arabic voice-over + music & FX', '-metadata:s:s:0', 'language=ara',
  'release/BR_promo_1080p.mp4']);
for (const [src, dst] of [['mix.wav', 'BR_full_mix.wav'], ['voice.wav', 'BR_voice_stem.wav'],
  ['music_fx.wav', 'BR_music_fx_no_voice.wav'], ['music.wav', 'BR_music_stem.wav'], ['sfx.wav', 'BR_sfx_stem.wav'],
  ['captions.srt', 'BR_captions_ar.srt'], ['vo_cue_sheet.txt', 'BR_vo_cue_sheet.txt']])
  fs.copyFileSync(path.join('out', src), path.join('release', dst));
console.log('\ndone → release/BR_promo_1080p.mp4');
