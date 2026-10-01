import * as THREE from 'three';
import { clamp, lerp, ramp, smooth, window01 } from './core.js';

// Camera moves, presenter blocking and screen effects, all keyed to cue marks.

export function direction(M) {
  const L = [0, 3.7, -5.5]; // hero logo
  const cam = [
    // S1 — darkness → logo → command center
    { t: 0, p: [0, 3.7, 0.9], l: L, f: 34, s: 1 },
    { t: M.logo, p: [0.35, 3.62, 1.5], l: L, f: 34 },
    { t: M.hqReveal, p: [0.7, 3.5, 2.5], l: L, f: 35 },
    { t: M.hqReveal + 3.6, p: [3.6, 2.7, 10.5], l: [-0.6, 2.6, -3], f: 40 },
    { t: M.s2 - 5, p: [2.2, 2.3, 7.5], l: [-1.3, 2.1, -2], f: 38 },
    { t: M.s2 - 0.4, p: [1.4, 2.4, 6.4], l: [-0.8, 2.3, -2], f: 38, s: 1 },
    // S2 — fly out to the timeline
    { t: M.s2 + 1.1, p: [-18, 14, -140], l: [-45, 6, -300], f: 44 },
    { t: M.y2022, p: [-55, 3, -281], l: [-52, 4.6, -305], f: 40, s: 1 },
    { t: M.nodes2022, p: [-50.5, 4.8, -284.5], l: [-49, 8, -310], f: 41 },
    { t: M.struct2022, p: [-47.5, 6.6, -282.5], l: [-49, 9.4, -312], f: 42 },
    { t: M.s3, p: [-48, 4.2, -282], l: [-50, 5.4, -305], f: 41, s: 1 },
    // S3 — 2023
    { t: M.y2023, p: [-19, 3, -281], l: [-16, 4.6, -305], f: 40, s: 1 },
    { t: M.online, p: [-17, 5.6, -282.5], l: [-13, 6.6, -313], f: 42 },
    { t: M.s4, p: [-14.5, 6.8, -280.5], l: [-13, 7.2, -313], f: 42, s: 1 },
    // S4 — 2024, slow
    { t: M.y2024, p: [15.5, 3.4, -283], l: [20, 4.8, -306], f: 38, s: 1 },
    { t: M.s5, p: [20.6, 5.3, -294.5], l: [22, 6.1, -309], f: 36 },
    // S5 — shatter and the return
    { t: M.shatter, p: [21.2, 5.7, -296.5], l: [22, 6.2, -309], f: 36, s: 1 },
    { t: M.shatter + 1.1, p: [25, 6.5, -295], l: [27, 8.5, -309], f: 40 },
    { t: M.y2026, p: [56, 3.8, -282], l: [60, 6, -306], f: 40, s: 1 },
    { t: M.hqExpand, p: [58.5, 5, -283], l: [62, 7.2, -306], f: 40, s: 1 },
    { t: M.hqExpand + 1.3, p: [34, 42, -110], l: [0, 0, -20], f: 44 },
    { t: M.hqExpand + 2.8, p: [0, 46, 92], l: [0, 0, 0], f: 45 },
    { t: M.s6 - 0.6, p: [-14, 30, 62], l: [0, 0, 0], f: 45 },
    // S6 — technology hall
    { t: M.s6 + 1.6, p: [8.6, 2.3, 11.2], l: [6, 2.4, 1], f: 40 },
    { t: M.s11 - 0.4, p: [7.4, 2.5, 9.4], l: [6, 2.6, 1], f: 40, s: 1 },
    // S11 — Pera corridor
    { t: M.s11 + 1.2, p: [-219.4, 2.1, -16], l: [-220, 2.2, -58], f: 42, s: 1 },
    { t: M.peraLogo, p: [-220.3, 2.2, -28], l: [-220, 3, -58], f: 40 },
    { t: M.peraWords, p: [-220.2, 2.4, -33], l: [-220, 3.6, -58], f: 40 },
    { t: M.s12 - 0.3, p: [-220.1, 2.6, -37.5], l: [-220, 3.6, -58], f: 40, s: 1 },
    // S12 — alone in the command room
    { t: M.s12 + 1.4, p: [0, 2.9, 12], l: [0, 2, 0], f: 36, s: 1 },
    { t: M.profiles, p: [0, 4.4, 16], l: [0, 2.2, -4], f: 40 },
    { t: M.s13 - 0.3, p: [0, 5, 17], l: [0, 3, -5], f: 40 },
    // S13 — three divisions
    { t: M.s13 + 1.2, p: [0, 4, 14], l: [0, 6, -8], f: 40 },
    { t: M.split, p: [0, 5, 18.5], l: [0, 7, -10], f: 44 },
    { t: M.div1 + 1.4, p: [-3.8, 4.4, 3.4], l: [-9.5, 5.4, -11], f: 42 },
    { t: M.div2 - 0.2, p: [-3, 4.6, 3.6], l: [-9, 5.6, -11], f: 42 },
    { t: M.div2 + 1.4, p: [1.4, 5, 3.4], l: [0, 10, -15], f: 42 },
    { t: M.div3 - 0.2, p: [1, 5.2, 3.6], l: [0, 10.4, -15], f: 42 },
    { t: M.div3 + 1.4, p: [4, 4.4, 3.4], l: [9.5, 5.4, -11], f: 42 },
    { t: M.s14 - 0.3, p: [3.4, 4.5, 3.8], l: [9, 5.6, -11], f: 42 },
    // S14 — philosophy
    { t: M.s14 + 1, p: [0, 2.2, 13], l: [0, 3.4, -6], f: 40 },
    { t: M.flow, p: [0, 2.6, 15], l: [0, 4.5, -8], f: 42 },
    { t: M.s15 - 0.3, p: [0, 2.8, 15.5], l: [0, 4.8, -8], f: 42 },
    // S15 — ecosystem
    { t: M.s15 + 1.3, p: [9, 11, 8], l: [0, 5, -7], f: 44 },
    { t: M.ecoWords, p: [-6, 10, 10], l: [0, 5, -7], f: 44 },
    { t: M.s16 - 0.3, p: [-9, 8.5, 6], l: [0, 5, -7], f: 44 },
    // S16 — identity close-up
    { t: M.s16 + 1.1, p: [0.6, 1.75, 8.7], l: [0, 1.55, 6], f: 30 },
    { t: M.s17 - 0.3, p: [0.15, 1.8, 8], l: [0, 1.6, 6], f: 30, s: 1 },
    // S17 — final timeline sweep
    { t: M.r2022, p: [-54, 3.2, -279], l: [-51, 3.6, -305], f: 42 },
    { t: M.r2023, p: [-18, 3.2, -279], l: [-15, 3.6, -305], f: 42 },
    { t: M.r2024, p: [18, 3.2, -279], l: [21, 3.8, -305], f: 42 },
    { t: M.r2026, p: [56, 3.4, -279], l: [59, 4.2, -305], f: 42 },
    { t: M.s18, p: [40, 7, -276], l: [10, 20, -395], f: 44 },
    // S18 — convergence, slow pull back
    { t: M.finalLogo, p: [4, 19, -322], l: [0, 19.5, -395], f: 42 },
    { t: M.end, p: [0, 18, -288], l: [0, 18.5, -395], f: 42 },
  ];

  const path = [
    { t: 0, x: -9, z: 1.5, yaw: 90 },
    { t: M.hqReveal + 0.6, x: -9, z: 1.5, yaw: 90 },
    { t: M.hqReveal + 5.4, x: -2.3, z: 0.4, yaw: 12 },
    { t: M.s2 + 1, x: -51, z: -300, yaw: -8, cut: 1 },
    { t: M.s3 + 0.9, x: -15, z: -300, yaw: -10, cut: 1 },
    { t: M.s4 + 1.1, x: 17, z: -300, yaw: -12, cut: 1 },
    { t: M.shatter + 1, x: 61, z: -300, yaw: -14, cut: 1 },
    { t: M.hqExpand + 1.6, x: 1, z: 7, yaw: 120, cut: 1 },
    { t: M.s6 + 0.2, x: 1, z: 7, yaw: 120 },
    { t: M.s6 + 3.2, x: 6, z: 3.4, yaw: 8 },
    { t: M.s11 + 0.6, x: -220.6, z: -30, yaw: 180, cut: 1 },
    { t: M.s11 + 1.2, x: -220.6, z: -30, yaw: 180 },
    { t: M.s12 - 0.4, x: -220.6, z: -43.5, yaw: 180 },
    { t: M.s12 + 0.8, x: 0, z: 1, yaw: 0, cut: 1 },
    { t: M.div1 + 0.5, x: 0, z: 1, yaw: -18 },
    { t: M.div2 + 0.5, x: 0, z: 1, yaw: 0 },
    { t: M.div3 + 0.5, x: 0, z: 1, yaw: 18 },
    { t: M.s14 + 0.5, x: 0, z: 1, yaw: 0 },
    { t: M.s14 + 4.6, x: 0, z: 5.8, yaw: 0 },
    { t: M.s17 + 0.8, x: 60, z: -300, yaw: -10, cut: 1 },
  ];

  const gest = [];
  const G = (name, a, b, w = 1, r = 0.6) =>
    gest.push({ t: a, name, w: 0 }, { t: a + r, name, w }, { t: b - r, name, w }, { t: b, name, w: 0 });
  G('presentL', M.hqReveal + 5.6, M.vo1 + 3.4, 0.85);
  G('open', M.vo1 + 12.4, M.s2 - 0.2, 0.8);
  G('presentL', M.nodes2022, M.struct2022 + 3, 0.8);
  G('lookL', M.nodes2022 + 0.5, M.struct2022 + 3, 0.5);
  G('presentL', M.online, M.online + 4, 0.8);
  G('lookL', M.y2024 + 1, M.s5 - 0.5, 0.6);
  G('presentL', M.y2024 + 3, M.y2024 + 7, 0.7);
  G('open', M.y2026 + 0.5, M.y2026 + 4, 0.9);
  G('present', M.techWords + 0.4, M.techWords + 4.2, 0.9);
  G('lookUp', M.techWords + 0.8, M.techWords + 4, 0.6);
  G('open', M.techWords + 4.6, M.s11 - 0.5, 0.8);
  G('open', M.profiles + 0.2, M.profiles + 4.4, 0.8);
  G('present', M.div1 + 0.6, M.div2 - 0.3, 0.9);
  G('point', M.div2 + 0.6, M.div3 - 0.3, 0.75);
  G('lookUp', M.div2 + 0.6, M.div3 - 0.3, 0.7);
  G('presentL', M.div3 + 0.6, M.s14 - 0.3, 0.9);
  G('point', M.s14 + 4.6, M.flow + 0.2, 0.7);
  G('open', M.flow + 0.4, M.s15 + 2, 0.85);
  G('open', M.ecoWords, M.s16 - 0.2, 0.7);
  G('explain', M.build - 0.2, M.s17 - 0.4, 0.7);
  G('present', M.r2026 - 0.4, M.s18 + 0.5, 0.8);

  function fx(t) {
    const fade = smooth(ramp(t, M.fade, M.fade + 2));
    const pulse = (at, k, d = 0.6) => (t >= at ? k * Math.exp(-(t - at) / d * 3) : 0);
    const flash =
      pulse(M.logo, 0.28, 0.5) + pulse(M.shatter, 0.55, 0.5) + pulse(M.y2026, 0.25) + pulse(M.finalLogo, 0.5, 0.8) + pulse(M.split, 0.15);
    const freeze = window01(t, M.s4 + 0.5, M.shatter, 1.8, 0.2);
    const exposure = lerp(1, 0.72, freeze) * lerp(0.35, 1, smooth(ramp(t, M.beam, M.logo + 0.6)));
    return { fade, flash, cold: freeze, exposure };
  }

  return { cam, path, gest, fx };
}

// Time-parameterised Hermite spline; keys with s:1 are held (zero velocity).
export function evalCamera(keys, t) {
  let i = 0;
  while (i < keys.length - 2 && keys[i + 1].t <= t) i++;
  const k0 = keys[i];
  const k1 = keys[i + 1];
  const u = clamp((t - k0.t) / (k1.t - k0.t));
  const tan = (j, prop) => {
    const k = keys[j];
    if (k.s || j === 0 || j === keys.length - 1) return [0, 0, 0];
    const a = keys[j - 1];
    const b = keys[j + 1];
    const dt = b.t - a.t;
    return [0, 1, 2].map((c) => ((b[prop][c] - a[prop][c]) / dt) * 0.85);
  };
  const dt = k1.t - k0.t;
  const h = (prop) => {
    const m0 = tan(i, prop);
    const m1 = tan(i + 1, prop);
    const u2 = u * u;
    const u3 = u2 * u;
    const h00 = 2 * u3 - 3 * u2 + 1;
    const h10 = u3 - 2 * u2 + u;
    const h01 = -2 * u3 + 3 * u2;
    const h11 = u3 - u2;
    return new THREE.Vector3(
      ...[0, 1, 2].map((c) => h00 * k0[prop][c] + h10 * dt * m0[c] + h01 * k1[prop][c] + h11 * dt * m1[c]),
    );
  };
  return { pos: h('p'), look: h('l'), fov: lerp(k0.f, k1.f, smooth(u)) };
}
