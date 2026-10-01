import * as THREE from 'three';

// ── Palette ─────────────────────────────────────────────────────────────────
export const C = {
  black: 0x030304,
  graphite: 0x1a1b1f,
  steel: 0x3a3c42,
  silver: 0xc9ccd3,
  white: 0xf2f3f5,
  gold: 0xb8913f,
  goldHot: 0xffd27f,
  ice: 0xdfe8ff,
};

// ── Maths / timing ──────────────────────────────────────────────────────────
export const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
export const lerp = (a, b, t) => a + (b - a) * t;
export const smooth = (t) => {
  t = clamp(t);
  return t * t * (3 - 2 * t);
};
export const easeInOut = (t) => {
  t = clamp(t);
  return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
};
export const easeOut = (t) => 1 - Math.pow(1 - clamp(t), 3);
export const easeIn = (t) => Math.pow(clamp(t), 3);
/** 0→1 as t goes a→b */
export const ramp = (t, a, b) => clamp((t - a) / (b - a));
/** fade in over [a, a+fi], hold, fade out over [b-fo, b] */
export const window01 = (t, a, b, fi = 0.5, fo = 0.5) =>
  Math.min(smooth((t - a) / fi), smooth((b - t) / fo));

export function rng(seed) {
  return function () {
    seed |= 0;
    seed = (seed + 0x6d2b79f5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

// ── Textures ────────────────────────────────────────────────────────────────
export function glowTexture(size = 128, hard = 0.0) {
  const c = document.createElement('canvas');
  c.width = c.height = size;
  const g = c.getContext('2d');
  const grd = g.createRadialGradient(size / 2, size / 2, 0, size / 2, size / 2, size / 2);
  grd.addColorStop(0, 'rgba(255,255,255,1)');
  grd.addColorStop(0.12 + hard * 0.5, 'rgba(255,255,255,0.85)');
  grd.addColorStop(0.35, 'rgba(255,255,255,0.22)');
  grd.addColorStop(1, 'rgba(255,255,255,0)');
  g.fillStyle = grd;
  g.fillRect(0, 0, size, size);
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  return t;
}

const FONT_AR = '"Noto Kufi Arabic"';
const FONT_EN = '"Sora"';

/**
 * Render a text label to a texture. Arabic is shaped by the browser's text engine,
 * so it joins and orders correctly (direction is set per label).
 */
export function textTexture(text, opts = {}) {
  const {
    size = 96,
    weight = 300,
    color = '#f2f3f5',
    arabic = /[؀-ۿ]/.test(text),
    tracking = arabic ? 0 : 0.18,
    pad = 0.35,
    glow = 0,
    glowColor = color,
  } = opts;
  const font = `${weight} ${size}px ${arabic ? FONT_AR : FONT_EN}, sans-serif`;
  const probe = document.createElement('canvas').getContext('2d');
  probe.font = font;
  probe.letterSpacing = `${tracking * size}px`;
  const w = Math.ceil(probe.measureText(text).width + size * pad * 2);
  const h = Math.ceil(size * (arabic ? 1.9 : 1.5));
  const c = document.createElement('canvas');
  c.width = w;
  c.height = h;
  const g = c.getContext('2d');
  g.font = font;
  g.letterSpacing = `${tracking * size}px`;
  g.direction = arabic ? 'rtl' : 'ltr';
  g.textAlign = 'center';
  g.textBaseline = 'middle';
  if (glow) {
    g.shadowColor = glowColor;
    g.shadowBlur = glow;
  }
  g.fillStyle = color;
  // letterSpacing adds trailing space after the last glyph; nudge to re-centre.
  g.fillText(text, w / 2 + (arabic ? 0 : (tracking * size) / 2), h / 2 + size * 0.04);
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  t.anisotropy = 4;
  t.userData.aspect = w / h;
  return t;
}

/** A flat label mesh, `height` world units tall (the width follows the text). */
export function label(text, height, opts = {}) {
  const tex = textTexture(text, opts);
  const mat = new THREE.MeshBasicMaterial({
    map: tex,
    transparent: true,
    depthWrite: false,
    blending: opts.additive === false ? THREE.NormalBlending : THREE.AdditiveBlending,
    side: THREE.DoubleSide,
    toneMapped: false,
    color: new THREE.Color(opts.tint ?? 0xffffff),
  });
  const m = new THREE.Mesh(new THREE.PlaneGeometry(height * tex.userData.aspect, height), mat);
  m.renderOrder = 10;
  return m;
}

// ── Materials ───────────────────────────────────────────────────────────────
/** Polished champagne gold, used on logo edges and trims. */
export function gold(rough = 0.2, extra = {}) {
  return metal(0xd9b56a, rough, { clearcoatRoughness: 0.06, ...extra });
}

export function metal(color = C.silver, rough = 0.22, extra = {}) {
  return new THREE.MeshPhysicalMaterial({
    color,
    metalness: 1,
    roughness: rough,
    clearcoat: 0.6,
    clearcoatRoughness: 0.15,
    ...extra,
  });
}

export function glowMat(color, opacity = 1) {
  return new THREE.MeshBasicMaterial({
    color,
    transparent: true,
    opacity,
    blending: THREE.AdditiveBlending,
    depthWrite: false,
    toneMapped: false,
  });
}

/** Soft additive cone used for volumetric light shafts. */
export function beamMaterial(color = 0xffffff, strength = 1) {
  return new THREE.ShaderMaterial({
    transparent: true,
    depthWrite: false,
    blending: THREE.AdditiveBlending,
    side: THREE.DoubleSide,
    uniforms: { uColor: { value: new THREE.Color(color) }, uStrength: { value: strength } },
    vertexShader: /* glsl */ `
      varying float vY; varying vec3 vN; varying vec3 vV;
      void main(){
        vY = uv.y;
        vec4 mv = modelViewMatrix * vec4(position,1.0);
        vN = normalize(normalMatrix * normal);
        vV = normalize(-mv.xyz);
        gl_Position = projectionMatrix * mv;
      }`,
    fragmentShader: /* glsl */ `
      uniform vec3 uColor; uniform float uStrength;
      varying float vY; varying vec3 vN; varying vec3 vV;
      void main(){
        float edge = pow(abs(dot(vN, vV)), 2.2);
        float along = pow(vY, 1.6);
        gl_FragColor = vec4(uColor * edge * along * uStrength * 0.35, 1.0);
      }`,
  });
}

// ── Geometry helpers ────────────────────────────────────────────────────────
/** Build extrudable shapes from traced logo polygons (see tools/trace_logos.py). */
export function logoShapes(polys, scale = 1) {
  return polys.map((p) => {
    const s = new THREE.Shape(p.outer.map(([x, y]) => new THREE.Vector2(x * scale, y * scale)));
    for (const h of p.holes)
      s.holes.push(new THREE.Path(h.map(([x, y]) => new THREE.Vector2(x * scale, y * scale))));
    return s;
  });
}

export function extrudeLogo(polys, height, depth, material, bevel = 0.04) {
  const shapes = logoShapes(polys, height);
  const geo = new THREE.ExtrudeGeometry(shapes, {
    depth,
    bevelEnabled: true,
    bevelThickness: bevel * height,
    bevelSize: bevel * height * 0.6,
    bevelSegments: 4,
    curveSegments: 8,
  });
  geo.translate(0, 0, -depth / 2);
  geo.computeVertexNormals();
  return new THREE.Mesh(geo, material);
}

/** Flat glowing outline of a logo (used for hologram versions). */
export function logoOutline(polys, height, color, opacity = 1) {
  const g = new THREE.Group();
  const mat = new THREE.LineBasicMaterial({
    color,
    transparent: true,
    opacity,
    blending: THREE.AdditiveBlending,
    depthWrite: false,
    toneMapped: false,
  });
  for (const p of polys) {
    for (const ring of [p.outer, ...p.holes]) {
      const pts = ring.map(([x, y]) => new THREE.Vector3(x * height, y * height, 0));
      pts.push(pts[0].clone());
      g.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts), mat));
    }
  }
  g.userData.mat = mat;
  return g;
}

/** Fictional dashboard texture: bars, sparklines, grids. No real data of any kind. */
export function dashboardTexture(seed, opts = {}) {
  const { w = 512, h = 320, accent = '#e3bd72', title = '' } = opts;
  const r = rng(seed);
  const c = document.createElement('canvas');
  c.width = w;
  c.height = h;
  const g = c.getContext('2d');
  g.fillStyle = 'rgba(10,12,16,0.55)';
  g.fillRect(0, 0, w, h);
  g.strokeStyle = 'rgba(220,228,255,0.55)';
  g.lineWidth = 2;
  g.strokeRect(3, 3, w - 6, h - 6);
  // corner ticks
  g.strokeStyle = 'rgba(255,255,255,0.9)';
  for (const [x, y, dx, dy] of [
    [3, 3, 1, 1],
    [w - 3, 3, -1, 1],
    [3, h - 3, 1, -1],
    [w - 3, h - 3, -1, -1],
  ]) {
    g.beginPath();
    g.moveTo(x, y + dy * 18);
    g.lineTo(x, y);
    g.lineTo(x + dx * 18, y);
    g.stroke();
  }
  g.font = '600 18px "Sora"';
  g.letterSpacing = '4px';
  g.fillStyle = 'rgba(235,238,245,0.9)';
  if (title) g.fillText(title, 22, 34);
  g.fillStyle = accent;
  g.fillRect(22, 44, 36, 3);
  const kind = Math.floor(r() * 3);
  if (kind === 0) {
    // bars
    const n = 14;
    for (let i = 0; i < n; i++) {
      const bh = (0.2 + r() * 0.75) * (h - 110);
      g.fillStyle = i === Math.floor(n * 0.6) ? accent : 'rgba(210,218,235,0.7)';
      g.fillRect(24 + i * ((w - 48) / n), h - 30 - bh, (w - 48) / n - 8, bh);
    }
  } else if (kind === 1) {
    // sparklines
    for (let k = 0; k < 3; k++) {
      g.strokeStyle = k === 0 ? accent : `rgba(210,218,235,${0.8 - k * 0.25})`;
      g.lineWidth = k === 0 ? 3 : 2;
      g.beginPath();
      let y = h * (0.45 + k * 0.12);
      for (let x = 22; x < w - 22; x += 12) {
        y += (r() - 0.5) * 22;
        y = Math.min(h - 30, Math.max(70, y));
        if (x === 22) g.moveTo(x, y);
        else g.lineTo(x, y);
      }
      g.stroke();
    }
  } else {
    // grid of cells
    const cols = 10;
    const rows = 5;
    for (let i = 0; i < cols; i++)
      for (let j = 0; j < rows; j++) {
        const v = r();
        g.fillStyle = v > 0.86 ? accent : `rgba(210,218,235,${0.12 + v * 0.5})`;
        g.fillRect(24 + i * ((w - 48) / cols), 70 + j * ((h - 100) / rows), (w - 48) / cols - 6, (h - 100) / rows - 6);
      }
  }
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  return t;
}

/** Semi-transparent hologram panel with a fictional dashboard on it. */
export function holoPanel(seed, w, h, title = '', accent = '#e3bd72') {
  const tex = dashboardTexture(seed, { title, accent });
  const mat = new THREE.MeshBasicMaterial({
    map: tex,
    transparent: true,
    opacity: 0.9,
    blending: THREE.AdditiveBlending,
    depthWrite: false,
    side: THREE.DoubleSide,
    toneMapped: false,
  });
  const m = new THREE.Mesh(new THREE.PlaneGeometry(w, h), mat);
  m.renderOrder = 5;
  return m;
}

/** Straight line segments helper. */
export function segments(pairs, color, opacity = 1) {
  const pos = new Float32Array(pairs.length * 6);
  pairs.forEach(([a, b], i) => {
    pos.set([a.x, a.y, a.z, b.x, b.y, b.z], i * 6);
  });
  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  const mat = new THREE.LineBasicMaterial({
    color,
    transparent: true,
    opacity,
    blending: THREE.AdditiveBlending,
    depthWrite: false,
    toneMapped: false,
  });
  return new THREE.LineSegments(geo, mat);
}

/** Point cloud with per-point size/colour, additive. */
export function pointCloud(n, sprite, size = 0.2) {
  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.BufferAttribute(new Float32Array(n * 3), 3));
  geo.setAttribute('color', new THREE.BufferAttribute(new Float32Array(n * 3).fill(1), 3));
  const mat = new THREE.PointsMaterial({
    size,
    map: sprite,
    vertexColors: true,
    transparent: true,
    depthWrite: false,
    blending: THREE.AdditiveBlending,
    sizeAttenuation: true,
    toneMapped: false,
  });
  const p = new THREE.Points(geo, mat);
  p.frustumCulled = false;
  return p;
}
