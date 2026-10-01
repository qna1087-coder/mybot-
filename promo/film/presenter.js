import * as THREE from 'three';
import { clamp, lerp, logoShapes, smooth } from './core.js';

// The presenter: a rigged figure restyled as a sleek black-suited host, driven by
// keyframed paths and layered procedural gestures on top of idle / walk cycles.

const GESTURES = {
  // bone: [x, y, z] euler offsets in radians (bone-local)
  present: {
    RightArm: [0.15, 0.2, -1.05],
    RightForeArm: [0, 0, -0.45],
    RightHand: [0.3, 0, -0.2],
    Spine2: [0, -0.12, 0],
    Head: [0, -0.2, 0],
  },
  presentL: {
    LeftArm: [0.15, -0.2, 1.05],
    LeftForeArm: [0, 0, 0.45],
    LeftHand: [0.3, 0, 0.2],
    Spine2: [0, 0.12, 0],
    Head: [0, 0.2, 0],
  },
  explain: {
    RightArm: [0.55, 0.35, -0.35],
    RightForeArm: [0.0, 0.0, -0.95],
    LeftArm: [0.55, -0.35, 0.35],
    LeftForeArm: [0.0, 0.0, 0.95],
  },
  open: {
    RightArm: [0.35, 0.55, -0.7],
    RightForeArm: [0, 0.2, -0.35],
    LeftArm: [0.35, -0.55, 0.7],
    LeftForeArm: [0, -0.2, 0.35],
    Spine2: [-0.05, 0, 0],
  },
  point: {
    RightArm: [0.9, 0.35, -0.95],
    RightForeArm: [0, 0, -0.1],
    Head: [0, -0.1, 0],
  },
  lookUp: {
    Neck: [-0.18, 0, 0],
    Head: [-0.22, 0, 0],
  },
  lookL: { Neck: [0, 0.35, 0], Head: [0, 0.4, 0], Spine2: [0, 0.12, 0] },
  lookR: { Neck: [0, -0.35, 0], Head: [0, -0.4, 0], Spine2: [0, -0.12, 0] },
};

export class Presenter {
  constructor(gltf, logos) {
    this.root = new THREE.Group();
    this.model = gltf.scene;
    this.root.add(this.model);
    this.bones = {};
    this.model.traverse((o) => {
      if (o.isBone) this.bones[o.name.replace(/^mixamorig:?/, '')] = o;
      if (o.isMesh) {
        o.castShadow = true;
        o.frustumCulled = false;
      }
    });
    // Restyle: a tailored black suit painted onto the figure by body region.
    const suit = suitMaterial(logos);
    this.model.traverse((o) => {
      if (o.isMesh) o.material = suit;
    });

    this.mixer = new THREE.AnimationMixer(this.model);
    const clip = (n) => gltf.animations.find((a) => a.name === n);
    this.idle = this.mixer.clipAction(clip('idle'));
    this.walk = this.mixer.clipAction(clip('walk'));
    for (const a of [this.idle, this.walk]) {
      a.play();
      a.setEffectiveWeight(1);
    }
    this.walkDur = clip('walk').duration;
    this.idleDur = clip('idle').duration;
    this._q = new THREE.Quaternion();
    this._e = new THREE.Euler();
  }

  /**
   * @param {object} s  {pos: Vector3, yaw, walk: 0..1, walkPhase, idleTime, gestures: {name: w}}
   */
  apply(s) {
    this.root.position.copy(s.pos);
    this.root.rotation.y = s.yaw;
    const w = clamp(s.walk);
    this.walk.setEffectiveWeight(w);
    this.idle.setEffectiveWeight(1 - w);
    this.walk.time = (s.walkPhase * this.walkDur) % this.walkDur;
    this.idle.time = s.idleTime % this.idleDur;
    this.mixer.update(0);

    for (const [name, weight] of Object.entries(s.gestures || {})) {
      if (weight <= 0.001) continue;
      const g = GESTURES[name];
      if (!g) continue;
      for (const [bone, [x, y, z]] of Object.entries(g)) {
        const b = this.bones[bone];
        if (!b) continue;
        const k = weight * (1 - w * 0.6);
        this._e.set(x * k, y * k, z * k);
        this._q.setFromEuler(this._e);
        b.quaternion.multiply(this._q);
      }
    }
  }
}

/**
 * Evaluate a presenter track.
 * path: [{t, x, z, yaw, y?, cut?}]  (yaw in degrees; 0 faces +z)
 * gest: [{t, name, w}] piecewise-linear weights per gesture (hold between keys)
 */
export function evalPresenter(path, gest, t, speech) {
  let i = 0;
  while (i < path.length - 1 && path[i + 1].t <= t) i++;
  const a = path[i];
  const b = path[Math.min(i + 1, path.length - 1)];
  const pos = new THREE.Vector3(a.x, a.y || 0, a.z);
  let yaw = THREE.MathUtils.degToRad(a.yaw ?? 0);
  let walk = 0;
  let dist = 0;
  // cumulative walked distance gives a foot-locked walk phase
  let walked = 0;
  for (let k = 0; k < i; k++) {
    const p = path[k];
    const q = path[k + 1];
    if (!q.cut) walked += Math.hypot(q.x - p.x, q.z - p.z);
  }
  if (b !== a && t >= a.t && !b.cut) {
    dist = Math.hypot(b.x - a.x, b.z - a.z);
    const u = clamp((t - a.t) / (b.t - a.t));
    if (dist > 0.05) {
      // ease in/out of the walk
      const e = smooth(u);
      pos.set(lerp(a.x, b.x, e), lerp(a.y || 0, b.y || 0, e), lerp(a.z, b.z, e));
      walked += dist * e;
      const dir = Math.atan2(b.x - a.x, b.z - a.z);
      const inW = smooth(u / 0.12);
      const outW = smooth((1 - u) / 0.18);
      walk = Math.min(inW, outW);
      const endYaw = THREE.MathUtils.degToRad(b.yaw ?? 0);
      const startYaw = THREE.MathUtils.degToRad(a.yaw ?? 0);
      yaw = angleLerp(angleLerp(startYaw, dir, inW), endYaw, 1 - outW);
    } else {
      const u2 = smooth(u);
      yaw = angleLerp(yaw, THREE.MathUtils.degToRad(b.yaw ?? 0), u2);
    }
  }
  const STRIDE = 1.55; // metres per walk cycle
  const gestures = {};
  const names = [...new Set(gest.map((g) => g.name))];
  for (const n of names) {
    const ks = gest.filter((g) => g.name === n);
    let v = 0;
    if (t <= ks[0].t) v = 0;
    else if (t >= ks[ks.length - 1].t) v = ks[ks.length - 1].w;
    else
      for (let k = 0; k < ks.length - 1; k++) {
        if (t >= ks[k].t && t < ks[k + 1].t) {
          v = lerp(ks[k].w, ks[k + 1].w, smooth((t - ks[k].t) / (ks[k + 1].t - ks[k].t)));
          break;
        }
      }
    gestures[n] = v;
  }
  // Subtle "talking" motion while narration plays.
  if (speech > 0) {
    const osc = Math.sin(t * 2.3) * 0.5 + Math.sin(t * 3.7 + 1) * 0.3;
    gestures.explain = Math.max(gestures.explain || 0, 0) + speech * (0.18 + osc * 0.08);
  }
  return { pos, yaw, walk, walkPhase: walked / STRIDE, idleTime: t, gestures };
}

function angleLerp(a, b, u) {
  let d = b - a;
  while (d > Math.PI) d -= 2 * Math.PI;
  while (d < -Math.PI) d += 2 * Math.PI;
  return a + d * u;
}

// ── Suit ─────────────────────────────────────────────────────────────────────
// Regions are decided from the bind-pose (T-pose) position of each vertex, in metres:
// feet at y=0, neck ≈ 1.50, arms along ±x with the wrists at |x| ≈ 0.69, front = +z.
function suitMaterial(logos) {
  const mat = new THREE.MeshPhysicalMaterial({
    color: 0xffffff,
    roughness: 0.6,
    metalness: 0,
    sheen: 0.35,
    sheenRoughness: 0.6,
    sheenColor: new THREE.Color(0x3a3d44),
    envMapIntensity: 0.55,
  });
  const emblem = emblemTexture(logos);
  mat.onBeforeCompile = (shader) => {
    shader.uniforms.uEmblem = { value: emblem };
    shader.vertexShader = 'varying vec3 vBind;\n' + shader.vertexShader.replace(
      '#include <begin_vertex>',
      '#include <begin_vertex>\n  vBind = position;',
    );
    shader.fragmentShader =
      'varying vec3 vBind;\nuniform sampler2D uEmblem;\n' +
      SUIT_GLSL +
      shader.fragmentShader
        .replace(
          '#include <color_fragment>',
          '#include <color_fragment>\n  vec3 sCol; float sRough; float sMetal; float sGlow;\n  suit(vBind, sCol, sRough, sMetal, sGlow);\n  diffuseColor.rgb = sCol;',
        )
        .replace('#include <roughnessmap_fragment>', '#include <roughnessmap_fragment>\n  roughnessFactor = sRough;')
        .replace('#include <metalnessmap_fragment>', '#include <metalnessmap_fragment>\n  metalnessFactor = sMetal;')
        .replace('#include <emissivemap_fragment>', '#include <emissivemap_fragment>\n  totalEmissiveRadiance += sCol * sGlow;');
  };
  return mat;
}

const SUIT_GLSL = /* glsl */ `
const vec3 GOLD = vec3(0.62, 0.42, 0.14);
const vec3 SHIRT = vec3(0.78, 0.79, 0.82);
float h3(vec3 p) { return fract(sin(dot(p, vec3(127.1, 311.7, 74.7))) * 43758.5453); }
void suit(vec3 p, out vec3 col, out float rough, out float metal, out float glow) {
  float ax = abs(p.x);
  bool front = p.z > 0.02;
  // black wool twill
  float tw = sin((p.x * 0.7 + p.y) * 950.0) * 0.5 + 0.5;
  float n = h3(floor(p * 420.0));
  vec3 wool = vec3(0.010, 0.010, 0.012) * (0.8 + 0.3 * tw + 0.25 * n);
  col = wool; rough = 0.66 + 0.1 * tw; metal = 0.0; glow = 0.0;

  if (p.y < 0.105) { col = vec3(0.005); rough = 0.16; return; }                         // patent shoes
  if (p.y > 1.515 && ax < 0.14) { col = vec3(0.006, 0.006, 0.007); rough = 0.09; metal = 0.5; return; } // obsidian head
  if (ax > 0.695 && p.y > 1.3) { col = vec3(0.007); rough = 0.36; return; }            // leather gloves
  if (ax > 0.665 && p.y > 1.3) { col = SHIRT; rough = 0.55; return; }                   // shirt cuffs
  if (p.y < 0.86 && ax < 0.26) {                                                        // trousers
    float crease = smoothstep(0.005, 0.0, abs(ax - 0.1)) * step(0.0, p.z);
    col = wool * 1.08 + crease * 0.008;
    return;
  }
  if (p.y > 1.455 && ax < 0.075) {                                                      // collar + knot
    col = SHIRT; rough = 0.55;
    if (front && ax < 0.021 && p.y < 1.49) { col = vec3(0.008); rough = 0.3; }
    return;
  }
  if (front && p.y > 1.21 && ax < 0.3) {
    float v = min((p.y - 1.21) * 0.2, 0.046);                                           // V opening
    if (ax < v) {
      col = SHIRT; rough = 0.55;
      float tieW = 0.011 + (1.45 - p.y) * 0.035;
      if (ax < tieW) {
        float stripe = step(0.82, fract((p.y + p.x) * 55.0));
        col = mix(vec3(0.009, 0.009, 0.011), GOLD * 0.35, stripe); rough = 0.28;
      }
      if (abs(p.y - 1.31) < 0.004 && ax < 0.028) { col = GOLD; metal = 1.0; rough = 0.22; } // tie clip
      return;
    }
    if (ax < v + 0.034 && p.y > 1.23) {                                                 // satin lapels
      col = vec3(0.014, 0.014, 0.016); rough = 0.24;
      if (abs(ax - v - 0.034) < 0.0025) { col = GOLD * 0.5; metal = 1.0; rough = 0.3; } // gold piping
      return;
    }
  }
  if (front) {
    float b1 = length(vec2(p.x, p.y - 1.12));
    float b2 = length(vec2(p.x, p.y - 1.03));
    if (min(b1, b2) < 0.011) { col = GOLD; metal = 1.0; rough = 0.25; return; }        // buttons
    vec2 uv = (p.xy - vec2(0.097, 1.335)) / 0.062 + 0.5;                                // BR emblem, wearer's left
    if (uv.x > 0.0 && uv.x < 1.0 && uv.y > 0.0 && uv.y < 1.0 && p.x > 0.0) {
      float e = texture2D(uEmblem, uv).a;
      col = mix(col, GOLD * (0.85 + 0.3 * n), e);
      metal = mix(metal, 1.0, e);
      rough = mix(rough, 0.32, e);
      glow = e * 0.35;
    }
  }
}
`;

function emblemTexture(logos) {
  // Gold-thread BR emblem, drawn from the traced logo outline.
  const c = document.createElement('canvas');
  c.width = c.height = 256;
  const g = c.getContext('2d');
  g.translate(128, 120);
  g.scale(1, -1);
  g.fillStyle = '#fff';
  for (const sh of logoShapes(logos.br, 150)) {
    g.beginPath();
    for (const ring of [sh.getPoints(), ...sh.holes.map((h) => h.getPoints())]) {
      ring.forEach((pt, i) => (i ? g.lineTo(pt.x, pt.y) : g.moveTo(pt.x, pt.y)));
      g.closePath();
    }
    g.fill('evenodd');
  }
  g.setTransform(1, 0, 0, 1, 0, 0);
  g.fillRect(78, 222, 100, 8);
  const t = new THREE.CanvasTexture(c);
  t.anisotropy = 4;
  return t;
}
