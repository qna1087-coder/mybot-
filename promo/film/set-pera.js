import * as THREE from 'three';
import {
  C,
  beamMaterial,
  clamp,
  easeOut,
  extrudeLogo,
  glowMat,
  holoPanel,
  label,
  logoOutline,
  metal,
  pointCloud,
  ramp,
  rng,
  smooth,
  window01,
} from './core.js';

export const PS = new THREE.Vector3(-220, 0, 0);
export const PERA_LOGO = new THREE.Vector3(-220, 3.8, -58);

// A long server corridor ending at the Pera emblem.
export function buildPera(ctx) {
  const { M, logos, sprite } = ctx;
  const g = new THREE.Group();
  const r = rng(99);

  const floor = new THREE.Mesh(
    new THREE.PlaneGeometry(14, 130),
    new THREE.MeshPhysicalMaterial({ color: 0x07080a, metalness: 0.9, roughness: 0.16, clearcoat: 1 }),
  );
  floor.rotation.x = -Math.PI / 2;
  floor.position.set(PS.x, 0, PS.z - 10);
  g.add(floor);
  const lane = new THREE.Mesh(new THREE.PlaneGeometry(0.06, 120), glowMat(C.redHot, 0.7));
  lane.rotation.x = -Math.PI / 2;
  lane.position.set(PS.x, 0.01, PS.z - 10);
  g.add(lane);

  // racks: instanced bodies + LED fronts (canvas texture, scrolled for blinking)
  const ledTex = ledTexture(r);
  const RACKS = 2 * 44;
  const body = new THREE.InstancedMesh(new THREE.BoxGeometry(1.3, 3.4, 1.1), metal(0x131418, 0.32), RACKS);
  const fronts = new THREE.InstancedMesh(
    new THREE.PlaneGeometry(1.1, 3.1),
    new THREE.MeshBasicMaterial({ map: ledTex, transparent: true, blending: THREE.AdditiveBlending, depthWrite: false, toneMapped: false }),
    RACKS,
  );
  const d = new THREE.Object3D();
  let k = 0;
  for (const side of [-1, 1])
    for (let i = 0; i < 44; i++) {
      const z = 44 - i * 2.35;
      d.position.set(PS.x + side * 3.4, 1.7, z);
      d.rotation.set(0, (-side * Math.PI) / 2, 0);
      d.updateMatrix();
      body.setMatrixAt(k, d.matrix);
      d.position.x = PS.x + side * 2.74;
      d.updateMatrix();
      fronts.setMatrixAt(k, d.matrix);
      k++;
    }
  g.add(body, fronts);

  // ceiling light strips + cable trays
  for (const x of [-1.8, 1.8]) {
    const s = new THREE.Mesh(new THREE.BoxGeometry(0.08, 0.04, 110), glowMat(0xffffff, 0.8));
    s.position.set(PS.x + x, 4.6, PS.z - 10);
    g.add(s);
    const tray = new THREE.Mesh(new THREE.BoxGeometry(0.6, 0.12, 110), metal(0x1c1d22, 0.4));
    tray.position.set(PS.x + x * 1.6, 4.1, PS.z - 10);
    g.add(tray);
  }
  const shafts = [];
  for (let i = 0; i < 8; i++) {
    const m = new THREE.Mesh(new THREE.CylinderGeometry(0.15, 1.6, 4.6, 32, 1, true), beamMaterial(0xdfe6ff, 0.7));
    m.position.set(PS.x + (i % 2 ? 2.3 : -2.3), 2.3, 36 - i * 12);
    g.add(m);
    shafts.push(m);
  }

  // monitoring dashboards floating above the racks (fictional)
  const dashes = [];
  const names = ['UPTIME', 'LOAD', 'NETWORK', 'STORAGE', 'SECURE LINK', 'MONITOR'];
  names.forEach((n, i) => {
    const side = i % 2 ? 1 : -1;
    const p = holoPanel(700 + i, 2.6, 1.6, n);
    p.position.set(PS.x + side * 2.2, 4.9, 30 - i * 13);
    p.rotation.y = (-side * Math.PI) / 5;
    g.add(p);
    dashes.push(p);
  });

  // Pera emblem at the end of the corridor
  const wall = new THREE.Mesh(new THREE.PlaneGeometry(14, 9), new THREE.MeshPhysicalMaterial({ color: 0x0a0b0e, metalness: 0.8, roughness: 0.35 }));
  wall.position.set(PERA_LOGO.x, 4.5, PERA_LOGO.z - 1.6);
  g.add(wall);
  const logo = extrudeLogo(logos.pera, 3.6, 0.45, metal(0xd6d9e0, 0.15, { clearcoat: 1 }));
  logo.position.copy(PERA_LOGO);
  g.add(logo);
  const halo = new THREE.Mesh(new THREE.PlaneGeometry(12, 12), new THREE.MeshBasicMaterial({ map: sprite, transparent: true, blending: THREE.AdditiveBlending, depthWrite: false, color: 0x9aa6c0, toneMapped: false }));
  halo.position.copy(PERA_LOGO).add(new THREE.Vector3(0, 0, -1.4));
  g.add(halo);
  const peraKey = new THREE.SpotLight(0xffffff, 0, 0, 0.4, 0.6, 0);
  peraKey.position.copy(PERA_LOGO).add(new THREE.Vector3(3, 4, 9));
  peraKey.target.position.copy(PERA_LOGO);
  g.add(peraKey, peraKey.target);
  const outline = logoOutline(logos.pera, 3.6, 0xffffff, 0);
  outline.position.copy(PERA_LOGO).add(new THREE.Vector3(0, 0, -1.2));
  outline.scale.setScalar(1.12);
  g.add(outline);
  const name = label('PERA SERVICES', 0.34, { weight: 600, glow: 10 });
  name.position.copy(PERA_LOGO).add(new THREE.Vector3(0, -2.5, 0.2));
  g.add(name);

  const words = ['INFRASTRUCTURE', 'HOSTING', 'SYSTEMS', 'SUPPORT'].map((w, i) => {
    const lb = label(w, 0.36, { weight: 600, glow: 12, tint: i === 1 ? 0xff5a66 : 0xffffff });
    const side = i % 2 ? 1 : -1;
    lb.position.set(PERA_LOGO.x + side * 3.6, 5.6 - Math.floor(i / 2) * 2.4, PERA_LOGO.z + 3);
    lb.rotation.y = (-side * Math.PI) / 9;
    g.add(lb);
    return lb;
  });

  const NH = 700;
  const haze = pointCloud(NH, sprite, 0.08);
  const hs = Array.from({ length: NH }, () => [(r() - 0.5) * 5, r() * 4.5, 46 - r() * 108, r() * 6]);
  g.add(haze);

  function update(t) {
    const on = smooth(ramp(t, M.s11 - 0.6, M.s11 + 0.8));
    ledTex.offset.y = Math.floor(t * 6) * 0.137;
    fronts.material.opacity = on;
    shafts.forEach((s) => (s.material.uniforms.uStrength.value = on * 0.7));
    dashes.forEach((p, i) => {
      p.material.opacity = on * 0.8 * smooth(clamp((t - M.s11 - 0.3 - i * 0.25) / 0.6));
      p.position.y = 4.9 + Math.sin(t * 0.8 + i) * 0.06;
    });
    const lk = t - M.peraLogo;
    logo.material.envMapIntensity = 0.3 + 1.2 * smooth(clamp(lk / 1));
    logo.rotation.y = Math.sin(t * 0.3) * 0.12;
    peraKey.intensity = on * (1.5 + 5 * smooth(clamp(lk / 1)));
    halo.material.opacity = on * (0.25 + 0.35 * smooth(clamp(lk / 1)));
    outline.userData.mat.opacity = window01(t, M.peraLogo - 0.2, M.s12, 0.2, 1) * (0.5 + 0.5 * Math.exp(-lk * 2));
    name.material.opacity = smooth(clamp((lk - 0.5) / 0.8));
    words.forEach((w, i) => {
      const k = easeOut(clamp((t - M.peraWords - i * 0.45) / 0.7));
      w.material.opacity = k;
      w.position.y += Math.sin(t + i) * 0.002;
    });
    const hp = haze.geometry.attributes.position;
    const hc = haze.geometry.attributes.color;
    hs.forEach(([x, y, z, ph], i) => {
      hp.setXYZ(i, PS.x + x, (y + t * 0.05) % 4.5, z);
      const v = on * (0.18 + 0.15 * Math.sin(t * 1.4 + ph));
      hc.setXYZ(i, v, v, v);
    });
    hp.needsUpdate = hc.needsUpdate = true;
  }

  return { group: g, update };
}

function ledTexture(r) {
  const c = document.createElement('canvas');
  c.width = 64;
  c.height = 256;
  const g = c.getContext('2d');
  g.fillStyle = 'rgba(0,0,0,0)';
  g.fillRect(0, 0, 64, 256);
  for (let y = 6; y < 256; y += 9)
    for (let x = 8; x < 60; x += 11) {
      const v = r();
      if (v < 0.45) continue;
      g.fillStyle = v > 0.93 ? '#ff2a3a' : `rgba(225,232,255,${0.35 + v * 0.6})`;
      g.fillRect(x, y, 5, 2);
    }
  g.fillStyle = 'rgba(200,210,230,0.25)';
  for (let y = 0; y < 256; y += 32) g.fillRect(2, y, 60, 1);
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  t.wrapS = t.wrapT = THREE.RepeatWrapping;
  return t;
}
