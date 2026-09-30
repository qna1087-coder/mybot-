import * as THREE from 'three';
import { C, clamp, lerp, smooth } from './core.js';

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
  constructor(gltf) {
    this.root = new THREE.Group();
    this.model = gltf.scene;
    this.root.add(this.model);
    this.bones = {};
    this.model.traverse((o) => {
      if (o.isBone) this.bones[o.name.replace('mixamorig:', '')] = o;
      if (o.isMesh) {
        o.castShadow = true;
        o.frustumCulled = false;
      }
    });
    // Restyle: glossy black suit shell, graphite-metal joints.
    const suit = new THREE.MeshPhysicalMaterial({
      color: 0x0c0c0f,
      metalness: 0.55,
      roughness: 0.26,
      clearcoat: 1,
      clearcoatRoughness: 0.12,
      sheen: 0.4,
      sheenColor: new THREE.Color(0x6a6f7a),
    });
    const joints = new THREE.MeshPhysicalMaterial({
      color: 0x55575e,
      metalness: 1,
      roughness: 0.22,
      clearcoat: 0.8,
    });
    this.model.traverse((o) => {
      if (!o.isMesh) return;
      o.material = o.name.includes('Joints') ? joints : suit;
    });
    this._addAccents();

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

  _addAccents() {
    // Thin dark-red chest line + silver collar ring: reads as a tailored tech suit.
    const spine = this.bones.Spine2;
    const neck = this.bones.Neck;
    const red = new THREE.MeshBasicMaterial({ color: C.redHot, toneMapped: false });
    const line = new THREE.Mesh(new THREE.BoxGeometry(1.2, 22, 1.2), red);
    // bone space is in centimetres (armature is scaled 0.01)
    line.position.set(0, 4, 13.2);
    line.rotation.x = -0.12;
    spine.add(line);
    const pin = new THREE.Mesh(new THREE.SphereGeometry(1.4, 16, 12), red);
    pin.position.set(-7.5, 10, 12.2);
    spine.add(pin);
    this.pin = pin;
    const collar = new THREE.Mesh(
      new THREE.TorusGeometry(6.4, 0.7, 10, 40),
      new THREE.MeshPhysicalMaterial({ color: C.silver, metalness: 1, roughness: 0.15 }),
    );
    collar.rotation.x = Math.PI / 2;
    collar.position.set(0, 2, 0.5);
    neck.add(collar);
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
