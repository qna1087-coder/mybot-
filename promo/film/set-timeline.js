import * as THREE from 'three';
import { TextGeometry } from 'three/addons/geometries/TextGeometry.js';
import {
  C,
  clamp,
  easeIn,
  easeInOut,
  easeOut,
  extrudeLogo,
  glowMat,
  glowTexture,
  holoPanel,
  label,
  lerp,
  logoOutline,
  metal,
  pointCloud,
  ramp,
  rng,
  segments,
  smooth,
  window01,
} from './core.js';

export const TL_Z = -300;
export const YEAR_X = { 2022: -54, 2023: -18, 2024: 18, 2026: 58 };
export const CUBE_POS = new THREE.Vector3(YEAR_X[2024] + 4, 6.2, TL_Z - 9);
export const RETURN_POS = new THREE.Vector3(YEAR_X[2026] + 4, 7.4, TL_Z - 9);
export const FINAL_POS = new THREE.Vector3(0, 25, TL_Z - 95);

export function buildTimeline(ctx) {
  const { M, logos, font, sprite } = ctx;
  const g = new THREE.Group();
  const r = rng(22);

  // ── Walkway: a long glass bridge that *is* the timeline ──
  const walk = new THREE.Mesh(
    new THREE.BoxGeometry(190, 0.14, 3.4),
    new THREE.MeshPhysicalMaterial({ color: 0x0b0c10, metalness: 0.7, roughness: 0.18, clearcoat: 1 }),
  );
  walk.position.set(6, -0.07, TL_Z);
  g.add(walk);
  const edgeMat = glowMat(0xffffff, 0.9);
  for (const z of [-1.72, 1.72]) {
    const e = new THREE.Mesh(new THREE.BoxGeometry(190, 0.05, 0.05), edgeMat);
    e.position.set(6, 0.02, TL_Z + z);
    g.add(e);
  }
  const underMat = glowMat(C.redHot, 0.5);
  const under = new THREE.Mesh(new THREE.BoxGeometry(190, 0.04, 0.04), underMat);
  under.position.set(6, -1.4, TL_Z);
  g.add(under);
  // tick marks (months)
  const ticks = [];
  for (let x = -88; x <= 100; x += 3) ticks.push([new THREE.Vector3(x, 0.03, TL_Z + 1.2), new THREE.Vector3(x, 0.03, TL_Z + 1.7)]);
  const tickLines = segments(ticks, 0xffffff, 0.6);
  g.add(tickLines);

  // Horizon grid far below for depth
  const grid = new THREE.GridHelper(600, 120, 0x2a2d35, 0x15171c);
  grid.position.set(0, -26, TL_Z - 40);
  grid.material.transparent = true;
  grid.material.opacity = 0.5;
  g.add(grid);

  // ── Years ──
  const yearMat = metal(0xdfe2e8, 0.18, { clearcoat: 1 });
  const halo = glowTexture(256);
  const years = {};
  for (const [y, x] of Object.entries(YEAR_X)) {
    const geo = new TextGeometry(y, {
      font,
      size: 3.2,
      depth: 0.55,
      curveSegments: 6,
      bevelEnabled: true,
      bevelThickness: 0.06,
      bevelSize: 0.04,
      bevelSegments: 3,
    });
    geo.computeBoundingBox();
    const bb = geo.boundingBox;
    geo.translate(-(bb.max.x + bb.min.x) / 2, 0, 0);
    const mesh = new THREE.Mesh(geo, yearMat.clone());
    mesh.position.set(x - 3.2, 0.25, TL_Z - 3.6);
    mesh.rotation.y = 0.18;
    g.add(mesh);
    const back = new THREE.Mesh(
      new THREE.PlaneGeometry(22, 12),
      new THREE.MeshBasicMaterial({
        map: halo,
        transparent: true,
        blending: THREE.AdditiveBlending,
        depthWrite: false,
        color: y === '2026' ? 0xff3344 : 0xdfe6ff,
        toneMapped: false,
      }),
    );
    back.position.set(x - 3.2, 2, TL_Z - 6);
    g.add(back);
    const pillar = new THREE.Mesh(new THREE.PlaneGeometry(0.06, 90), glowMat(y === '2026' ? C.redHot : 0xffffff, 0.5));
    pillar.position.set(x + 1.6, 0, TL_Z - 1.9);
    g.add(pillar);
    const ringM = new THREE.Mesh(new THREE.RingGeometry(1.5, 1.58, 96), glowMat(y === '2026' ? C.redHot : 0xffffff, 0.8));
    ringM.rotation.x = -Math.PI / 2;
    ringM.position.set(x + 1.6, 0.02, TL_Z);
    g.add(ringM);
    years[y] = { mesh, back, pillar, ringM };
  }
  const y2025 = label('2025', 0.5, { weight: 300, tint: 0x6d7079 });
  y2025.position.set(38, 0.5, TL_Z - 2.4);
  g.add(y2025);

  // ── 2022: organisational nodes forming a structure ──
  const d22 = new THREE.Group();
  d22.position.set(YEAR_X[2022] + 5, 0, TL_Z - 12);
  const levels = [1, 3, 7, 13];
  const nodes = [];
  levels.forEach((n, li) => {
    for (let k = 0; k < n; k++) {
      const x = (k - (n - 1) / 2) * (16 / Math.max(n, 3)) * (li === 3 ? 1.15 : 1);
      const target = new THREE.Vector3(x, 13 - li * 2.6, (r() - 0.5) * 1.5);
      const start = new THREE.Vector3((r() - 0.5) * 34, r() * 18, (r() - 0.5) * 16);
      nodes.push({ target, start, li, k, delay: r() * 1.8 });
    }
  });
  // parent links
  let idx = 0;
  const offs = levels.map((n) => {
    const o = idx;
    idx += n;
    return o;
  });
  const links = [];
  levels.forEach((n, li) => {
    if (li === 0) return;
    for (let k = 0; k < n; k++) {
      const parent = offs[li - 1] + Math.min(levels[li - 1] - 1, Math.floor((k / n) * levels[li - 1]));
      links.push([parent, offs[li] + k]);
    }
  });
  const nodePts = pointCloud(nodes.length, sprite, 0.9);
  d22.add(nodePts);
  const nodeCore = new THREE.InstancedMesh(new THREE.SphereGeometry(0.16, 12, 10), glowMat(0xffffff), nodes.length);
  d22.add(nodeCore);
  const linkGeo = new THREE.BufferGeometry();
  linkGeo.setAttribute('position', new THREE.BufferAttribute(new Float32Array(links.length * 6), 3));
  const linkLines = new THREE.LineSegments(linkGeo, glowMat(0xdfe6ff, 0));
  d22.add(linkLines);
  const rootLogo = logoOutline(logos.br, 1.4, 0xffffff, 0);
  rootLogo.position.set(0, 14.8, 0);
  d22.add(rootLogo);
  const diag = [];
  for (let i = 0; i < 3; i++) {
    const m = new THREE.Mesh(new THREE.TorusGeometry(7 + i * 2.2, 0.015, 4, 160), glowMat(i === 1 ? C.redHot : 0xffffff, 0));
    m.position.set(0, 8.5, -3);
    diag.push(m);
    d22.add(m);
  }
  g.add(d22);

  // ── 2023: infrastructure switching on ──
  const d23 = new THREE.Group();
  d23.position.set(YEAR_X[2023] + 5, 0, TL_Z - 13);
  const plat = new THREE.Mesh(new THREE.CylinderGeometry(9, 9.3, 0.5, 64), metal(0x111216, 0.35));
  plat.position.y = 2.5;
  d23.add(plat);
  const platRing = new THREE.Mesh(new THREE.TorusGeometry(9.05, 0.04, 6, 160), glowMat(0xffffff, 0));
  platRing.rotation.x = Math.PI / 2;
  platRing.position.y = 2.76;
  d23.add(platRing);
  const blocks = [];
  for (let i = 0; i < 4; i++)
    for (let j = 0; j < 3; j++) {
      const h = 2.8 + r() * 2.8;
      const b = new THREE.Mesh(new THREE.BoxGeometry(1.4, h, 1.4), metal(0x17181d, 0.3));
      b.position.set((i - 1.5) * 3.2, 2.75 + h / 2, (j - 1) * 3.2);
      d23.add(b);
      const s = new THREE.Mesh(new THREE.PlaneGeometry(0.1, h * 0.85), glowMat(j === 1 && i === 2 ? C.redHot : 0xffffff, 0));
      s.position.copy(b.position).add(new THREE.Vector3(0, 0, 0.71));
      d23.add(s);
      blocks.push({ s, order: i * 3 + j });
    }
  const dash23 = [0, 1, 2].map((i) => {
    const p = holoPanel(230 + i, 4.2, 2.6, ['SERVICES', 'SYSTEMS', 'OUTPUT'][i]);
    p.position.set((i - 1) * 4.8, 10.5 + (i === 1 ? 0.8 : 0), 1);
    p.rotation.y = (1 - i) * 0.2;
    d23.add(p);
    return p;
  });
  const depts = [0, 1, 2, 3].map((i) => {
    const a = (i / 4) * Math.PI * 2 + 0.4;
    const m = new THREE.Mesh(new THREE.CylinderGeometry(1.6, 1.6, 0.3, 6), metal(0x1d1e24, 0.3));
    m.position.set(Math.cos(a) * 12.5, 3.6, Math.sin(a) * 6);
    const e = new THREE.LineSegments(new THREE.EdgesGeometry(m.geometry), glowMat(i === 0 ? C.redHot : 0xffffff, 0));
    m.add(e);
    d23.add(m);
    return { m, e, i };
  });
  g.add(d23);

  // ── 2024: the logo suspended in glass ──
  const cube = new THREE.Group();
  cube.position.copy(CUBE_POS);
  const S = 4.4;
  const glassMat = new THREE.MeshPhysicalMaterial({
    color: 0xb9c3d6,
    metalness: 0.1,
    roughness: 0.04,
    transparent: true,
    opacity: 0.16,
    envMapIntensity: 2.2,
    side: THREE.DoubleSide,
    depthWrite: false,
    clearcoat: 1,
  });
  const glass = new THREE.Mesh(new THREE.BoxGeometry(S, S, S), glassMat);
  cube.add(glass);
  const glassEdges = new THREE.LineSegments(new THREE.EdgesGeometry(glass.geometry), glowMat(0xdfe6ff, 0.8));
  cube.add(glassEdges);
  // cracks (random walks on the front face)
  const crackPairs = [];
  for (let k = 0; k < 9; k++) {
    let p = new THREE.Vector3((r() - 0.5) * 0.4, (r() - 0.5) * 0.4, S / 2 + 0.01);
    const ang = (k / 9) * Math.PI * 2 + r() * 0.4;
    for (let s = 0; s < 9; s++) {
      const q = p.clone().add(new THREE.Vector3(Math.cos(ang + (r() - 0.5) * 0.9), Math.sin(ang + (r() - 0.5) * 0.9), 0).multiplyScalar(0.28));
      q.x = clamp(q.x, -S / 2, S / 2);
      q.y = clamp(q.y, -S / 2, S / 2);
      crackPairs.push([p, q]);
      p = q;
    }
  }
  const cracks = segments(crackPairs, 0xffffff, 1);
  cube.add(cracks);
  g.add(cube);
  // frozen logo (separate so it can fly out)
  const frozenMat = metal(0xc8ccd6, 0.2, { emissive: new THREE.Color(0xff1a2a), emissiveIntensity: 0 });
  const heart = extrudeLogo(logos.br, 2.2, 0.38, frozenMat);
  heart.position.copy(CUBE_POS);
  g.add(heart);
  // shards
  const shards = buildShards(S, r);
  const shardMesh = new THREE.Mesh(shards.geo, glassMat.clone());
  shardMesh.material.opacity = 0.35;
  shardMesh.position.copy(CUBE_POS);
  shardMesh.frustumCulled = false;
  g.add(shardMesh);

  // ── Finale: massive logo + convergence ──
  const fin = new THREE.Group();
  fin.position.copy(FINAL_POS);
  const bigMat = metal(0xdadde4, 0.14, { clearcoat: 1, transparent: true, opacity: 0 });
  const big = extrudeLogo(logos.br, 26, 3.6, bigMat, 0.03);
  fin.add(big);
  const bigLine = logoOutline(logos.br, 26, 0xffffff, 0);
  bigLine.position.z = 1.9;
  fin.add(bigLine);
  const NC = 3000;
  const conv = pointCloud(NC, sprite, 0.55);
  const convData = [];
  const targets = sampleLogo(logos.br, 26, NC, r);
  for (let i = 0; i < NC; i++) {
    const dir = new THREE.Vector3(r() - 0.5, r() - 0.5, r() - 0.5).normalize();
    const from = dir.multiplyScalar(90 + r() * 120);
    from.z += 60;
    convData.push({ from, to: targets[i], d: r() * 0.9, red: r() < 0.12 });
  }
  fin.add(conv);
  g.add(fin);

  // ambient dust along the timeline
  const DN = 900;
  const dust = pointCloud(DN, sprite, 0.12);
  for (let i = 0; i < DN; i++)
    dust.geometry.attributes.position.setXYZ(i, -90 + r() * 190, -10 + r() * 30, TL_Z - 30 + r() * 45);
  g.add(dust);

  const lp = linkGeo.attributes.position;
  const dummy = new THREE.Object3D();

  function update(t) {
    // Which year is "live"
    const live = {
      2022: window01(t, M.s2 + 0.8, M.s3 + 0.8, 1.2, 1.4),
      2023: window01(t, M.s3 + 0.6, M.s4 + 0.6, 1, 1.4),
      2024: window01(t, M.s4 + 0.6, M.s5 + 3, 1.6, 1.4) * 0.55,
      2026: smooth(ramp(t, M.y2026 - 0.4, M.y2026 + 0.5)),
    };
    const recap = t > M.s17 - 1;
    if (recap) {
      live[2022] = smooth(ramp(t, M.r2022 - 0.3, M.r2022 + 0.4));
      live[2023] = smooth(ramp(t, M.r2023 - 0.3, M.r2023 + 0.4));
      live[2024] = smooth(ramp(t, M.r2024 - 0.3, M.r2024 + 0.4)) * 0.6;
      live[2026] = smooth(ramp(t, M.r2026 - 0.3, M.r2026 + 0.4));
    }
    // 2024 freeze dims the whole line; the return re-ignites it.
    const freeze = window01(t, M.s4 + 0.5, M.s5 + 0.2, 1.8, 0.3);
    const ignite = recap ? 1 : smooth(ramp(t, M.shatter, M.shatter + 0.8));
    edgeMat.opacity = lerp(0.9, 0.18, freeze) + (t > M.shatter && t < M.shatter + 0.6 ? 0.8 : 0);
    underMat.opacity = lerp(0.5, 0.1, freeze) + ignite * 0.4;
    tickLines.material.opacity = lerp(0.6, 0.15, freeze);
    for (const [y, o] of Object.entries(years)) {
      const v = Math.max(0.12, live[y]);
      o.back.material.opacity = v * (y === '2026' ? 0.9 : 0.55);
      o.pillar.material.opacity = 0.12 + live[y] * 0.7;
      o.ringM.material.opacity = 0.2 + live[y] * 0.8;
      o.mesh.material.envMapIntensity = 0.25 + live[y] * 1.2;
    }

    // 2022 structure
    d22.visible = t < M.s4 + 2 || recap;
    const nk = t - M.nodes2022;
    const sk = t - M.struct2022;
    const npos = nodePts.geometry.attributes.position;
    const ncol = nodePts.geometry.attributes.color;
    nodes.forEach((n, i) => {
      const appear = smooth(clamp((t - M.y2022 - 0.3 - n.delay * 0.6) / 0.8));
      const u = easeInOut(clamp((nk - n.delay) / 2.6));
      const p = n.start.clone().lerp(n.target, recap ? 1 : u);
      if (!recap) p.y += Math.sin(t * 0.8 + i) * 0.15 * (1 - u);
      npos.setXYZ(i, p.x, p.y, p.z);
      const v = (recap ? live[2022] : appear) * (n.li === 0 ? 1 : 0.7);
      ncol.setXYZ(i, v, n.li === 0 ? v * 0.3 : v, n.li === 0 ? v * 0.35 : v);
      dummy.position.copy(p);
      dummy.scale.setScalar(Math.max(0.001, recap ? live[2022] : appear));
      dummy.updateMatrix();
      nodeCore.setMatrixAt(i, dummy.matrix);
    });
    npos.needsUpdate = ncol.needsUpdate = true;
    nodeCore.instanceMatrix.needsUpdate = true;
    const drawn = recap ? links.length : Math.floor(links.length * easeInOut(clamp(sk / 3.2)));
    links.forEach(([a, b], i) => {
      lp.setXYZ(i * 2, npos.getX(a), npos.getY(a), npos.getZ(a));
      lp.setXYZ(i * 2 + 1, npos.getX(b), npos.getY(b), npos.getZ(b));
    });
    lp.needsUpdate = true;
    linkGeo.setDrawRange(0, drawn * 2);
    linkLines.material.opacity = (recap ? live[2022] : window01(t, M.struct2022, M.s4, 0.4, 1.5)) * 0.8;
    rootLogo.userData.mat.opacity = recap ? live[2022] : window01(t, M.struct2022 + 1.5, M.s4, 1, 1.5);
    diag.forEach((m, i) => {
      m.rotation.z = t * (0.05 + i * 0.03) * (i % 2 ? -1 : 1);
      m.rotation.x = 0.3 + i * 0.2;
      m.material.opacity = (recap ? live[2022] * 0.5 : window01(t, M.nodes2022, M.s4, 2, 1.5)) * 0.5;
    });

    // 2023 activation
    d23.visible = (t > M.s2 + 5 && t < M.s5) || recap;
    const on = t - M.online;
    platRing.material.opacity = recap ? live[2023] : smooth(clamp((t - M.y2023) / 1)) * lerp(1, 0.3, freeze);
    blocks.forEach((b) => {
      const k = recap ? live[2023] : smooth(clamp((on - b.order * 0.12) / 0.3));
      b.s.material.opacity = k * lerp(1, 0.2, freeze);
    });
    dash23.forEach((p, i) => {
      const k = recap ? live[2023] : smooth(clamp((on - 1.2 - i * 0.6) / 0.6));
      p.material.opacity = k * 0.85 * lerp(1, 0.15, freeze);
      p.position.y += Math.sin(t + i) * 0.002;
    });
    depts.forEach((d) => {
      const k = recap ? live[2023] : smooth(clamp((on - 3 - d.i * 0.4) / 0.6));
      d.m.visible = k > 0.01;
      d.m.scale.setScalar(Math.max(0.01, k));
      d.e.material.opacity = k * lerp(1, 0.2, freeze);
    });

    // 2024 glass
    const crackK = clamp((t - M.s5) / 1.2);
    const shattered = t >= M.shatter;
    glass.visible = glassEdges.visible = !shattered;
    glass.material.opacity = 0.16 + freeze * 0.1;
    glassEdges.material.opacity = 0.35 + freeze * 0.4;
    cube.rotation.y = 0.35 + Math.sin(t * 0.2) * 0.05;
    cracks.visible = !shattered && t > M.s5;
    cracks.geometry.setDrawRange(0, Math.floor(crackPairs.length * easeOut(crackK)) * 2);
    // shards
    const st = t - M.shatter;
    shardMesh.visible = shattered && st < 5;
    shardMesh.rotation.y = cube.rotation.y;
    if (shardMesh.visible) shards.update(st);
    shardMesh.material.opacity = 0.4 * (1 - clamp(st / 4));
    // the logo: frozen → freed → flies to 2026 → hovers
    const fly = easeInOut(clamp((t - M.shatter - 0.6) / 2.2));
    heart.position.lerpVectors(CUBE_POS, RETURN_POS, fly);
    heart.position.y += Math.sin(fly * Math.PI) * 2.5 + Math.sin(t * 0.8) * 0.06;
    heart.rotation.y = shattered ? (1 - fly) * Math.PI * 2 + Math.sin(t * 0.3) * 0.15 : 0.35;
    heart.scale.setScalar(lerp(1, 1.5, fly));
    heart.material.emissiveIntensity = shattered ? 0.25 * (1 - clamp(st / 2.5)) + 0.04 : 0;
    heart.material.envMapIntensity = lerp(0.35, 1.3, smooth(ramp(t, M.s5, M.shatter + 0.5)));
    heart.visible = !recap && t < M.s6;

    // Final convergence
    fin.visible = t > M.s17 - 0.5;
    const ct = t - M.s18;
    const cpos = conv.geometry.attributes.position;
    const ccol = conv.geometry.attributes.color;
    const landed = clamp((t - M.finalLogo) / 1.2);
    for (let i = 0; i < NC; i++) {
      const c = convData[i];
      const u = easeIn(clamp((ct - c.d) / (M.finalLogo - M.s18 - c.d)));
      const swirl = (1 - u) * 6;
      const x = lerp(c.from.x, c.to.x, u) + Math.sin(u * 9 + i) * swirl;
      const y = lerp(c.from.y, c.to.y, u) + Math.cos(u * 7 + i) * swirl;
      const z = lerp(c.from.z, c.to.z, u);
      cpos.setXYZ(i, x, y, z);
      const vis = ct > c.d - 0.3 ? smooth((ct - c.d + 0.3) / 0.5) : 0;
      const v = vis * (1 - landed * 0.85) * (0.5 + u * 0.8);
      if (c.red) ccol.setXYZ(i, v, v * 0.15, v * 0.2);
      else ccol.setXYZ(i, v, v, v);
    }
    cpos.needsUpdate = ccol.needsUpdate = true;
    conv.visible = ct > -0.2;
    bigMat.opacity = smooth(ramp(t, M.finalLogo - 0.2, M.finalLogo + 0.6));
    bigMat.transparent = bigMat.opacity < 1;
    bigMat.depthWrite = bigMat.opacity > 0.5;
    big.visible = bigMat.opacity > 0.001;
    bigLine.userData.mat.opacity = window01(t, M.finalLogo - 0.3, M.end, 0.2, 4) * (0.6 + 0.4 * Math.exp(-(t - M.finalLogo) * 1.5));
    fin.rotation.y = Math.sin(t * 0.15) * 0.06;

    const dcol = dust.geometry.attributes.color;
    for (let i = 0; i < DN; i++) {
      const v = 0.25 + 0.25 * Math.sin(t * 1.3 + i * 1.7);
      dcol.setXYZ(i, v, v, v * 1.05);
    }
    dcol.needsUpdate = true;
  }

  return { group: g, update };
}

function buildShards(S, r) {
  // Pre-fractured cube faces: each face is split into jittered triangles.
  const tris = [];
  const n = 4;
  const faces = [
    [new THREE.Vector3(0, 0, 1), new THREE.Vector3(1, 0, 0), new THREE.Vector3(0, 1, 0)],
    [new THREE.Vector3(0, 0, -1), new THREE.Vector3(-1, 0, 0), new THREE.Vector3(0, 1, 0)],
    [new THREE.Vector3(1, 0, 0), new THREE.Vector3(0, 0, -1), new THREE.Vector3(0, 1, 0)],
    [new THREE.Vector3(-1, 0, 0), new THREE.Vector3(0, 0, 1), new THREE.Vector3(0, 1, 0)],
    [new THREE.Vector3(0, 1, 0), new THREE.Vector3(1, 0, 0), new THREE.Vector3(0, 0, -1)],
    [new THREE.Vector3(0, -1, 0), new THREE.Vector3(1, 0, 0), new THREE.Vector3(0, 0, 1)],
  ];
  for (const [nrm, u, v] of faces) {
    const pts = [];
    for (let i = 0; i <= n; i++)
      for (let j = 0; j <= n; j++) {
        const edge = i === 0 || j === 0 || i === n || j === n;
        const a = (i / n - 0.5) * S + (edge ? 0 : (r() - 0.5) * 0.5);
        const b = (j / n - 0.5) * S + (edge ? 0 : (r() - 0.5) * 0.5);
        pts.push(nrm.clone().multiplyScalar(S / 2).addScaledVector(u, a).addScaledVector(v, b));
      }
    const at = (i, j) => pts[i * (n + 1) + j];
    for (let i = 0; i < n; i++)
      for (let j = 0; j < n; j++) {
        tris.push([at(i, j), at(i + 1, j), at(i + 1, j + 1)]);
        tris.push([at(i, j), at(i + 1, j + 1), at(i, j + 1)]);
      }
  }
  const pos = new Float32Array(tris.length * 9);
  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  const meta = tris.map((tri) => {
    const c = tri[0].clone().add(tri[1]).add(tri[2]).divideScalar(3);
    const vel = c.clone().normalize().multiplyScalar(4 + r() * 7).add(new THREE.Vector3((r() - 0.5) * 3, r() * 2, 2 + r() * 4));
    const axis = new THREE.Vector3(r() - 0.5, r() - 0.5, r() - 0.5).normalize();
    return { tri: tri.map((p) => p.clone().sub(c)), c, vel, axis, spin: 2 + r() * 8 };
  });
  const q = new THREE.Quaternion();
  const tmp = new THREE.Vector3();
  function update(st) {
    meta.forEach((m, i) => {
      q.setFromAxisAngle(m.axis, m.spin * st);
      const drag = (1 - Math.exp(-st * 1.6)) / 1.6;
      const c = m.c.clone().addScaledVector(m.vel, drag);
      c.y -= 1.2 * st * st * 0.5;
      m.tri.forEach((p, k) => {
        tmp.copy(p).applyQuaternion(q).add(c);
        pos.set([tmp.x, tmp.y, tmp.z], i * 9 + k * 3);
      });
    });
    geo.attributes.position.needsUpdate = true;
    geo.computeVertexNormals();
  }
  update(0);
  return { geo, update };
}

function sampleLogo(polys, height, n, r) {
  // Rejection-sample points inside the traced logo outline.
  const shapes = polys.map((p) => ({
    outer: p.outer.map(([x, y]) => [x * height, y * height]),
    holes: p.holes.map((h) => h.map(([x, y]) => [x * height, y * height])),
  }));
  const inside = (poly, x, y) => {
    let c = false;
    for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
      const [xi, yi] = poly[i];
      const [xj, yj] = poly[j];
      if (yi > y !== yj > y && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) c = !c;
    }
    return c;
  };
  const out = [];
  const W = height * 1.3;
  while (out.length < n) {
    const x = (r() - 0.5) * W;
    const y = (r() - 0.5) * height;
    if (shapes.some((s) => inside(s.outer, x, y) && !s.holes.some((h) => inside(h, x, y))))
      out.push(new THREE.Vector3(x, y, (r() - 0.5) * 3.4));
  }
  return out;
}
