import * as THREE from 'three';
import { Reflector } from 'three/addons/objects/Reflector.js';
import {
  C,
  beamMaterial,
  clamp,
  easeInOut,
  easeOut,
  extrudeLogo,
  glowMat,
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

export const LOGO_POS = new THREE.Vector3(0, 3.7, -5.5);

// The command center: an open circular platform floating in the void.
export function buildHQ(ctx) {
  const { M, logos, sprite } = ctx;
  const g = new THREE.Group();
  const r = rng(7);

  // ── Floor: mirror + dark patterned overlay (reads as polished black stone) ──
  const mirror = new Reflector(new THREE.CircleGeometry(30, 96), {
    textureWidth: 960,
    textureHeight: 540,
    color: 0x8a8a8a,
    clipBias: 0.003,
  });
  mirror.rotation.x = -Math.PI / 2;
  g.add(mirror);
  const floorU = { uPower: { value: 0 }, uPulse: { value: 0 }, uTime: { value: 0 } };
  const floor = new THREE.Mesh(
    new THREE.CircleGeometry(30.2, 128),
    new THREE.ShaderMaterial({
      transparent: true,
      uniforms: floorU,
      vertexShader: `varying vec2 vP; void main(){ vP = position.xy; gl_Position = projectionMatrix*modelViewMatrix*vec4(position,1.); }`,
      fragmentShader: /* glsl */ `
        uniform float uPower, uPulse, uTime; varying vec2 vP;
        float ring(float d, float r, float w){ return smoothstep(w, 0., abs(d-r)); }
        void main(){
          float d = length(vP);
          float a = atan(vP.y, vP.x);
          float lines = ring(d,4.6,.03)+ring(d,5.,.012)+ring(d,9.,.02)+ring(d,13.5,.03)+ring(d,20.5,.05)+ring(d,21.2,.012);
          float spokes = smoothstep(.012,.0,abs(sin(a*24.)))*step(5.,d)*step(d,20.5)*.35;
          float grid = (smoothstep(.02,.0,abs(fract(vP.x*.5)-.5)-.48)+smoothstep(.02,.0,abs(fract(vP.y*.5)-.5)-.48))*.0;
          float pulse = ring(d, uPulse*30., 1.2) * (1.-uPulse);
          vec3 col = vec3(.85,.87,.92)*(lines*.5+spokes*.25)*uPower + vec3(1.,.12,.16)*pulse*1.2;
          col += vec3(1.,.1,.14)*ring(d,4.6,.05)*uPower*.8;
          float alpha = mix(.78, 1., smoothstep(18.,30.,d));
          gl_FragColor = vec4(col + vec3(.006,.006,.008), alpha);
        }`,
    }),
  );
  floor.rotation.x = -Math.PI / 2;
  floor.position.y = 0.01;
  g.add(floor);

  // ── Central dais under the logo ──
  const dais = new THREE.Mesh(new THREE.CylinderGeometry(4.3, 4.6, 0.35, 96), metal(C.graphite, 0.35));
  dais.position.set(LOGO_POS.x, 0.17, LOGO_POS.z);
  g.add(dais);
  const daisRing = new THREE.Mesh(new THREE.TorusGeometry(4.35, 0.03, 8, 160), glowMat(C.redHot));
  daisRing.rotation.x = Math.PI / 2;
  daisRing.position.set(LOGO_POS.x, 0.36, LOGO_POS.z);
  g.add(daisRing);

  // ── Pillars with light strips ──
  const pillarMat = metal(0x15161a, 0.3);
  const stripMat = glowMat(0xffffff, 1);
  const pillars = [];
  for (let i = 0; i < 16; i++) {
    const a = (i / 16) * Math.PI * 2;
    const p = new THREE.Group();
    const body = new THREE.Mesh(new THREE.BoxGeometry(0.8, 17, 0.8), pillarMat);
    body.position.y = 8.5;
    p.add(body);
    const strip = new THREE.Mesh(new THREE.PlaneGeometry(0.07, 15.5), stripMat.clone());
    strip.position.set(0, 8.4, 0.41);
    p.add(strip);
    p.position.set(Math.sin(a) * 22, 0, Math.cos(a) * 22);
    p.lookAt(0, 0, 0);
    p.userData = { strip, i };
    g.add(p);
    pillars.push(p);
  }
  // ceiling rings
  const ringOuter = new THREE.Mesh(new THREE.TorusGeometry(22, 0.09, 8, 200), glowMat(0xffffff));
  ringOuter.rotation.x = Math.PI / 2;
  ringOuter.position.y = 17;
  g.add(ringOuter);
  const ringInner = new THREE.Mesh(new THREE.TorusGeometry(13, 0.05, 8, 200), glowMat(0xffffff));
  ringInner.rotation.x = Math.PI / 2;
  ringInner.position.y = 14.5;
  g.add(ringInner);

  // ── Light shafts ──
  const beams = [];
  for (let i = 0; i < 6; i++) {
    const a = (i / 6) * Math.PI * 2 + 0.5;
    const m = new THREE.Mesh(new THREE.CylinderGeometry(0.2, 2.8, 15, 40, 1, true), beamMaterial(0xe8ecff, 0));
    m.position.set(Math.sin(a) * 12, 7, Math.cos(a) * 12);
    g.add(m);
    beams.push(m);
  }
  const hero = new THREE.Mesh(new THREE.CylinderGeometry(0.25, 3.2, 16, 48, 1, true), beamMaterial(0xffffff, 0));
  hero.position.set(0, 8, 0);
  g.add(hero);

  // ── Screens ring (fictional dashboards) ──
  const screens = [];
  const titles = ['SYSTEM STATUS', 'NETWORK', 'OPERATIONS', 'ANALYTICS', 'SERVICES', 'MONITOR', 'CORE', 'RESOURCES', 'INDEX', 'UPLINK'];
  for (let i = 0; i < 10; i++) {
    const a = THREE.MathUtils.degToRad(70 + i * 22);
    const s = holoPanel(100 + i, 5.2, 3.25, titles[i]);
    s.position.set(Math.sin(a) * 17, 4.6 + (i % 2) * 0.6, Math.cos(a) * 17);
    s.lookAt(0, 4.6, 0);
    s.userData.i = i;
    g.add(s);
    screens.push(s);
  }

  // ── Hero logo (metal) ──
  const logoMat = metal(0xd8dbe2, 0.16, { clearcoat: 1 });
  const logo = extrudeLogo(logos.br, 2.6, 0.42, logoMat);
  logo.position.copy(LOGO_POS);
  g.add(logo);
  const logoGlow = logoOutline(logos.br, 2.6, 0xffffff, 0);
  logoGlow.position.copy(LOGO_POS).add(new THREE.Vector3(0, 0, 0.27));
  g.add(logoGlow);

  // ── Dust / metallic particles ──
  const N = 1400;
  const dust = pointCloud(N, sprite, 0.07);
  const seeds = [];
  for (let i = 0; i < N; i++) {
    const rad = Math.sqrt(r()) * 24;
    const a = r() * Math.PI * 2;
    seeds.push([Math.sin(a) * rad, r() * 16, Math.cos(a) * rad, r() * 10, r()]);
  }
  g.add(dust);

  // ── Expansion sectors (2026) ──
  const sectors = [];
  for (let i = 0; i < 6; i++) {
    const a = (i / 6) * Math.PI * 2 + Math.PI / 6;
    const sg = new THREE.Group();
    const base = new THREE.Mesh(new THREE.CylinderGeometry(8, 8.4, 0.8, 6), metal(0x121317, 0.3));
    sg.add(base);
    const edge = new THREE.LineSegments(
      new THREE.EdgesGeometry(new THREE.CylinderGeometry(8.05, 8.05, 0.02, 6)),
      glowMat(i % 2 ? 0xffffff : C.redHot),
    );
    edge.position.y = 0.42;
    sg.add(edge);
    for (let k = 0; k < 5; k++) {
      const h = 2 + r() * 9;
      const tw = new THREE.Mesh(new THREE.BoxGeometry(1.2 + r() * 1.5, h, 1.2 + r() * 1.5), metal(0x1b1c21, 0.35));
      tw.position.set((r() - 0.5) * 9, h / 2 + 0.4, (r() - 0.5) * 9);
      sg.add(tw);
      const st = new THREE.Mesh(new THREE.BoxGeometry(0.06, h * 0.9, 0.06), glowMat(0xffffff, 0.8));
      st.position.copy(tw.position).add(new THREE.Vector3(0, 0, 0.8));
      sg.add(st);
    }
    const bridge = new THREE.Mesh(new THREE.BoxGeometry(0.5, 0.12, 1), glowMat(0xffffff, 0.8));
    const dist = 52;
    sg.position.set(Math.sin(a) * dist, -0.6, Math.cos(a) * dist);
    sg.userData = { a, dist, bridge, i };
    bridge.rotation.y = a;
    g.add(bridge);
    g.add(sg);
    sectors.push(sg);
  }

  // ── Scene 6: technology holograms around the presenter ──
  const tech = new THREE.Group();
  tech.position.set(6, 0, 3);
  const techWords = ['TECHNOLOGY', 'AUTOMATION', 'AI', 'DATA', 'INFRASTRUCTURE'];
  const techItems = techWords.map((w, i) => {
    const grp = new THREE.Group();
    const a = THREE.MathUtils.degToRad(-70 + i * 35);
    const panel = holoPanel(300 + i, 2.6, 1.6, '');
    grp.add(panel);
    const lb = label(w, 0.36, { weight: 600, glow: 12 });
    lb.position.y = 1.15;
    grp.add(lb);
    grp.position.set(Math.sin(a) * 3.6, 2.4 + (i % 2) * 0.9, -Math.cos(a) * 3.6);
    grp.rotation.y = Math.atan2(-grp.position.x, -grp.position.z);
    grp.userData = { panel, lb };
    tech.add(grp);
    return grp;
  });
  const techRing = new THREE.Mesh(new THREE.TorusGeometry(3.6, 0.02, 6, 160), glowMat(0xffffff, 0.6));
  techRing.rotation.x = Math.PI / 2;
  techRing.position.y = 0.05;
  tech.add(techRing);
  g.add(tech);

  // ── Scene 12: member profiles flowing into departments ──
  const prof = new THREE.Group();
  const deptPos = [new THREE.Vector3(-8, 0.05, -4), new THREE.Vector3(0, 0.05, -9), new THREE.Vector3(8, 0.05, -4)];
  const deptRings = deptPos.map((p, i) => {
    const m = new THREE.Mesh(new THREE.RingGeometry(1.9, 2.0, 96), glowMat(i === 1 ? 0xffffff : C.redHot, 0));
    m.rotation.x = -Math.PI / 2;
    m.position.copy(p);
    prof.add(m);
    return m;
  });
  const badgeTex = profileTexture();
  const badges = [];
  for (let i = 0; i < 15; i++) {
    const m = new THREE.Mesh(
      new THREE.PlaneGeometry(0.9, 0.9),
      new THREE.MeshBasicMaterial({
        map: badgeTex,
        transparent: true,
        depthWrite: false,
        blending: THREE.AdditiveBlending,
        toneMapped: false,
      }),
    );
    const dept = i % 3;
    const start = new THREE.Vector3((r() - 0.5) * 30, 1 + r() * 3, 10 + r() * 8);
    const end = deptPos[dept].clone().add(new THREE.Vector3(Math.cos(i) * 1.1, 1.3 + (i % 2) * 0.5, Math.sin(i) * 1.1));
    m.userData = { start, end, delay: r() * 2.2 };
    prof.add(m);
    badges.push(m);
  }
  g.add(prof);

  // ── Scene 13: holographic logo splitting into three divisions ──
  const struct = new THREE.Group();
  const holoLogo = logoOutline(logos.br, 2.2, 0xffffff, 0);
  holoLogo.position.set(0, 6.4, -8);
  struct.add(holoLogo);
  const divAnchors = [new THREE.Vector3(-9.5, 5.2, -11), new THREE.Vector3(0, 10.8, -15), new THREE.Vector3(9.5, 5.2, -11)];
  const divTitles = ['OPERATIONS', 'INTELLIGENCE', 'COMMERCE'];
  const divs = divAnchors.map((p, i) => {
    const d = new THREE.Group();
    d.position.copy(p);
    const panels = [];
    for (let k = 0; k < 3; k++) {
      const pn = holoPanel(500 + i * 10 + k, 3.2, 2, k === 0 ? divTitles[i] : '', i === 2 ? '#e9ecf2' : '#ff2a3a');
      pn.position.set((k - 1) * 3.4, k === 1 ? 0.5 : -0.2, k === 1 ? 0.3 : 0);
      pn.rotation.y = (1 - k) * 0.25;
      d.add(pn);
      panels.push(pn);
    }
    const num = label(`0${i + 1}`, 1.3, { weight: 200, size: 160 });
    num.position.set(0, 2.2, 0.2);
    d.add(num);
    d.rotation.y = Math.atan2(-p.x, 6 - p.z);
    d.userData = { panels, num };
    struct.add(d);
    return d;
  });
  const branchLines = divAnchors.map((p) => {
    const curve = new THREE.QuadraticBezierCurve3(
      new THREE.Vector3(0, 6.4, -8),
      new THREE.Vector3(p.x * 0.5, p.y + 2.5, (p.z - 8) / 2),
      p,
    );
    const geo = new THREE.TubeGeometry(curve, 64, 0.035, 6);
    const m = new THREE.Mesh(geo, glowMat(0xffffff, 0.9));
    geo.setDrawRange(0, 0);
    struct.add(m);
    return m;
  });
  g.add(struct);

  // ── Scene 14: value flowing both ways ──
  const flow = new THREE.Group();
  flow.position.set(0, 5.2, -9);
  const brNode = new THREE.Mesh(new THREE.SphereGeometry(0.7, 32, 24), glowMat(0xffffff, 0.9));
  brNode.position.x = -5.5;
  flow.add(brNode);
  const brLab = label('BR', 0.5, { weight: 600 });
  brLab.position.set(-5.5, 1.3, 0);
  flow.add(brLab);
  const memNode = new THREE.Mesh(new THREE.SphereGeometry(0.7, 32, 24), glowMat(C.redHot, 0.9));
  memNode.position.x = 5.5;
  flow.add(memNode);
  const memLab = label('MEMBERS', 0.42, { weight: 600 });
  memLab.position.set(5.5, 1.3, 0);
  flow.add(memLab);
  const flowPts = pointCloud(260, sprite, 0.28);
  flow.add(flowPts);
  const flowSeeds = Array.from({ length: 260 }, () => [r(), r(), r()]);
  // wall of connected BR nodes behind
  const wallN = 90;
  const wallPos = [];
  for (let i = 0; i < wallN; i++) wallPos.push(new THREE.Vector3((r() - 0.5) * 34, r() * 12 - 3, -6 - r() * 8));
  const wallPairs = [];
  for (let i = 0; i < wallN; i++)
    for (let j = i + 1; j < wallN; j++) if (wallPos[i].distanceTo(wallPos[j]) < 4.2) wallPairs.push([wallPos[i], wallPos[j]]);
  const wallLines = segments(wallPairs, 0xcfd6ea, 0);
  flow.add(wallLines);
  const wallPts = pointCloud(wallN, sprite, 0.5);
  wallPos.forEach((p, i) => wallPts.geometry.attributes.position.setXYZ(i, p.x, p.y, p.z));
  flow.add(wallPts);
  g.add(flow);

  // ── Scene 15: ecosystem ring ──
  const eco = new THREE.Group();
  eco.position.set(0, 5.5, -7);
  const ecoLogo = logoOutline(logos.br, 1.8, 0xffffff, 0);
  eco.add(ecoLogo);
  const ecoWords = ['AI', 'DATA', 'AUTOMATION', 'INFRASTRUCTURE', 'OPERATIONS', 'INTELLIGENCE', 'COMMERCE', 'PERA SERVICES'];
  const ecoItems = ecoWords.map((w, i) => {
    const lb = label(w, 0.42, { weight: 600, glow: 10, tint: i === 7 ? 0xff5a66 : 0xffffff });
    const node = new THREE.Mesh(new THREE.SphereGeometry(0.16, 16, 12), glowMat(i === 7 ? C.redHot : 0xffffff));
    eco.add(lb, node);
    return { lb, node, a: (i / ecoWords.length) * Math.PI * 2 };
  });
  const ecoLinks = segments(
    ecoItems.map(() => [new THREE.Vector3(), new THREE.Vector3()]),
    0xffffff,
    0,
  );
  eco.add(ecoLinks);
  const ecoRing = new THREE.Mesh(new THREE.TorusGeometry(6.2, 0.02, 6, 200), glowMat(0xffffff, 0));
  ecoRing.rotation.x = Math.PI / 2;
  eco.add(ecoRing);
  g.add(eco);

  const dustPos = dust.geometry.attributes.position;
  const dustCol = dust.geometry.attributes.color;

  function update(t) {
    // Power: dark intro, lights up at hqReveal, dims for the calm section.
    let power = smooth(ramp(t, M.hqReveal, M.hqReveal + 2.6));
    if (t > M.s12 - 1) power = lerp(1, 0.55, smooth(ramp(t, M.s12 - 1, M.s12 + 1.5)));
    if (t > M.s13) power = lerp(0.55, 0.9, smooth(ramp(t, M.s13, M.s13 + 2)));
    if (t > M.s16) power = lerp(0.9, 0.6, smooth(ramp(t, M.s16, M.s16 + 1.5)));
    floorU.uPower.value = power;
    floorU.uPulse.value = clamp((t - M.hqReveal) / 2.2);
    if (t > M.hqExpand) floorU.uPulse.value = clamp((t - M.hqExpand - 1.4) / 2.2);

    daisRing.material.opacity = power;
    for (const p of pillars) {
      const on = smooth(ramp(t, M.hqReveal + 0.15 * (p.userData.i % 8), M.hqReveal + 0.15 * (p.userData.i % 8) + 0.4));
      p.userData.strip.material.opacity = on * (0.35 + 0.65 * power);
    }
    ringOuter.material.opacity = power * 0.9;
    ringInner.material.opacity = power * 0.7;
    beams.forEach((b, i) => {
      b.material.uniforms.uStrength.value = power * (0.55 + 0.25 * Math.sin(t * 0.4 + i));
    });
    // hero spot on presenter during the calm section
    hero.material.uniforms.uStrength.value =
      window01(t, M.s12 - 0.5, M.s13 + 1, 1.5, 1.5) * 1.6 + window01(t, M.s16 - 0.5, M.s17, 1.5, 0.5) * 1.1;
    screens.forEach((s) => {
      const on = smooth(ramp(t, M.hqReveal + 0.8 + s.userData.i * 0.12, M.hqReveal + 1.2 + s.userData.i * 0.12));
      const flick = on < 1 ? (Math.sin(t * 90 + s.userData.i) > 0 ? 1 : 0.3) : 1;
      s.material.opacity = on * flick * (0.35 + 0.5 * power);
      s.position.y += Math.sin(t * 0.6 + s.userData.i) * 0.002;
    });

    // Logo: the intro beam reveal, then quiet presence.
    const reveal = smooth(ramp(t, M.beam, M.logo + 0.4));
    logo.material.envMapIntensity = 0.05 + reveal * 1.1;
    logo.rotation.y = Math.sin(t * 0.25) * 0.12 + (1 - smooth(ramp(t, 0, M.logo + 2))) * 0.5;
    logo.position.y = LOGO_POS.y + Math.sin(t * 0.7) * 0.05;
    logoGlow.rotation.copy(logo.rotation);
    logoGlow.position.y = logo.position.y;
    logoGlow.userData.mat.opacity = window01(t, M.logo - 0.1, M.logo + 1.6, 0.1, 1.3) * 0.9;
    logo.visible = !(t > M.s13 - 0.6 && t < M.s16 + 0.5);

    // Dust
    const sparkle = smooth(ramp(t, 0.3, 3.2));
    for (let i = 0; i < N; i++) {
      const [x, y, z, ph, b] = seeds[i];
      const yy = (y + t * 0.08 + ph) % 16;
      dustPos.setXYZ(i, x + Math.sin(t * 0.2 + ph) * 0.4, yy, z + Math.cos(t * 0.17 + ph) * 0.4);
      const tw = 0.5 + 0.5 * Math.sin(t * 2 + ph * 7);
      const v = (0.15 + 0.35 * power) * (0.4 + 0.6 * b) + sparkle * (1 - power) * tw * b * 0.8;
      dustCol.setXYZ(i, v, v, v * 1.05);
    }
    dustPos.needsUpdate = true;
    dustCol.needsUpdate = true;

    // Sectors (2026 expansion)
    const ex = t - M.hqExpand;
    sectors.forEach((s) => {
      const k = easeOut(clamp((ex - 0.8 - s.userData.i * 0.25) / 1.8));
      s.visible = k > 0.001;
      s.position.y = lerp(-26, -0.6, k);
      s.scale.setScalar(lerp(0.3, 1, k));
      const b = s.userData.bridge;
      const bk = easeInOut(clamp((ex - 1.6 - s.userData.i * 0.25) / 1.2));
      b.visible = bk > 0.01;
      b.scale.z = 14 * bk;
      const d = 30 + 7 * bk;
      b.position.set(Math.sin(s.userData.a) * d, -0.1, Math.cos(s.userData.a) * d);
    });

    // Tech holograms
    const tw0 = M.techWords;
    tech.visible = t > M.s6 - 0.5 && t < M.s7 + 1;
    techItems.forEach((it, i) => {
      const k = easeOut(clamp((t - tw0 - i * 0.55) / 0.8));
      const out = smooth(clamp((M.s7 + 0.6 - t) / 0.6));
      it.scale.setScalar(Math.max(0.001, k));
      it.userData.panel.material.opacity = k * out * 0.85;
      it.userData.lb.material.opacity = k * out;
      it.position.y += Math.sin(t * 0.9 + i) * 0.002;
    });
    techRing.material.opacity = smooth(ramp(t, M.s6, M.s6 + 1)) * 0.7;

    // Profiles
    prof.visible = t > M.s12 && t < M.s13 + 2;
    const pk = t - M.profiles;
    deptRings.forEach((m, i) => (m.material.opacity = smooth(clamp((pk - i * 0.3) / 1)) * 0.9 * smooth((M.s13 + 1.5 - t) / 1)));
    badges.forEach((b) => {
      const u = easeInOut(clamp((pk - b.userData.delay) / 3.2));
      b.position.lerpVectors(b.userData.start, b.userData.end, u);
      b.position.y += Math.sin(u * Math.PI) * 1.5;
      b.lookAt(ctx.camera.position);
      b.material.opacity = smooth(clamp((pk - b.userData.delay) / 0.6)) * smooth((M.s13 + 1.5 - t) / 1);
    });

    // Structure
    struct.visible = t > M.s13 - 0.5 && t < M.s14 + 1;
    holoLogo.userData.mat.opacity = window01(t, M.s13, M.s14 + 0.8, 1, 0.8);
    holoLogo.rotation.y = Math.sin(t * 0.5) * 0.2;
    const sp = t - M.split;
    branchLines.forEach((m, i) => {
      const k = easeInOut(clamp((sp - i * 0.15) / 1.2));
      m.geometry.setDrawRange(0, Math.floor(k * m.geometry.index.count / 3) * 3);
      m.material.opacity = 0.9 * smooth((M.s14 + 0.8 - t) / 0.8);
    });
    const divStart = [M.div1, M.div2, M.div3];
    divs.forEach((d, i) => {
      const k = easeOut(clamp((sp - 0.8 - i * 0.2) / 1.0));
      const focus = t > divStart[i] && (i === 2 || t < divStart[i + 1]) ? 1 : 0.35;
      const fk = lerp(0.35, 1, focus);
      d.scale.setScalar(Math.max(0.001, k));
      d.userData.panels.forEach((p) => (p.material.opacity = k * 0.85 * fk * smooth((M.s14 + 0.8 - t) / 0.8)));
      d.userData.num.material.opacity = k * fk * smooth((M.s14 + 0.8 - t) / 0.8);
    });

    // Flow
    flow.visible = t > M.s14 - 0.5 && t < M.s15 + 1;
    const fv = window01(t, M.s14 + 0.2, M.s15 + 0.6, 1.2, 0.6);
    wallLines.material.opacity = fv * 0.28;
    const wc = wallPts.geometry.attributes.color;
    for (let i = 0; i < wallN; i++) {
      const v = fv * (0.35 + 0.35 * Math.sin(t * 1.5 + i));
      wc.setXYZ(i, v, v, v);
    }
    wc.needsUpdate = true;
    const flowOn = window01(t, M.flow - 0.3, M.s15 + 0.6, 1, 0.6);
    brNode.material.opacity = memNode.material.opacity = flowOn * 0.9;
    brLab.material.opacity = memLab.material.opacity = flowOn;
    const fp = flowPts.geometry.attributes.position;
    const fc = flowPts.geometry.attributes.color;
    flowSeeds.forEach(([a, b, c], i) => {
      const dir = i % 2 ? 1 : -1;
      const u = (a + t * (0.22 + c * 0.1)) % 1;
      const x = dir > 0 ? lerp(-5, 5, u) : lerp(5, -5, u);
      const lane = dir > 0 ? 0.55 : -0.55;
      const y = lane + Math.sin(u * Math.PI) * lane * 1.6 + (b - 0.5) * 0.3;
      fp.setXYZ(i, x, y, (c - 0.5) * 0.5);
      const v = flowOn * Math.sin(u * Math.PI);
      if (dir > 0) fc.setXYZ(i, v, v, v);
      else fc.setXYZ(i, v, v * 0.2, v * 0.25);
    });
    fp.needsUpdate = fc.needsUpdate = true;

    // Ecosystem
    eco.visible = t > M.s15 - 0.5 && t < M.s16 + 1;
    const ev = window01(t, M.s15, M.s16 + 0.8, 1, 0.8);
    ecoLogo.userData.mat.opacity = ev;
    ecoRing.material.opacity = ev * 0.5;
    const ea = t * 0.12;
    const lp = ecoLinks.geometry.attributes.position;
    ecoItems.forEach((it, i) => {
      const a = it.a + ea;
      const x = Math.cos(a) * 6.2;
      const z = Math.sin(a) * 6.2;
      it.node.position.set(x, 0, z);
      it.lb.position.set(x, 0.55, z);
      it.lb.quaternion.copy(ctx.camera.quaternion);
      const lit = t > M.ecoWords + i * 0.65 ? 1 : 0.35;
      it.lb.material.opacity = ev * lit;
      it.node.material.opacity = ev * lit;
      lp.setXYZ(i * 2, 0, 0, 0);
      lp.setXYZ(i * 2 + 1, x, 0, z);
    });
    lp.needsUpdate = true;
    ecoLinks.material.opacity = ev * 0.45;
  }

  return { group: g, update, mirror };
}

function profileTexture() {
  // Abstract member badge: hexagon with a neutral silhouette. No names, no data.
  const c = document.createElement('canvas');
  c.width = c.height = 256;
  const g = c.getContext('2d');
  g.translate(128, 128);
  g.strokeStyle = 'rgba(255,255,255,0.95)';
  g.lineWidth = 6;
  g.beginPath();
  for (let i = 0; i < 6; i++) {
    const a = (i / 6) * Math.PI * 2 + Math.PI / 6;
    g.lineTo(Math.cos(a) * 110, Math.sin(a) * 110);
  }
  g.closePath();
  g.stroke();
  g.fillStyle = 'rgba(255,255,255,0.85)';
  g.beginPath();
  g.arc(0, -22, 30, 0, Math.PI * 2);
  g.fill();
  g.beginPath();
  g.ellipse(0, 52, 56, 34, 0, Math.PI, 0);
  g.fill();
  g.fillStyle = '#ff2a3a';
  g.fillRect(-18, 80, 36, 5);
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  return t;
}
