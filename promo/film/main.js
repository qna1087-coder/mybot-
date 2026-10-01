import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { TTFLoader } from 'three/addons/loaders/TTFLoader.js';
import { Font } from 'three/addons/loaders/FontLoader.js';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js';
import { AfterimagePass } from 'three/addons/postprocessing/AfterimagePass.js';
import { ShaderPass } from 'three/addons/postprocessing/ShaderPass.js';
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js';

import { buildCues } from './cues.js';
import { beamMaterial, clamp, glowTexture, ramp, smooth, window01 } from './core.js';
import { Overlay } from './overlay.js';
import { Presenter, evalPresenter } from './presenter.js';
import { LOGO_POS, buildHQ } from './set-hq.js';
import { FINAL_POS, buildTimeline } from './set-timeline.js';
import { buildPera } from './set-pera.js';
import { direction, evalCamera } from './direction.js';

const W = 1920;
const H = 1080;
const params = new URLSearchParams(location.search);
const scale = Number(params.get('scale') || 1);

async function init() {
  await Promise.all(
    ['300', '500', '700', '900'].map((w) => document.fonts.load(`${w} 40px "Noto Kufi Arabic"`, 'عربي')),
  );
  await Promise.all(['200', '300', '600', '800'].map((w) => document.fonts.load(`${w} 40px "Sora"`, 'BR')));

  const [logos, gltf, fontJson] = await Promise.all([
    fetch('../assets/logos.json').then((r) => r.json()),
    new GLTFLoader().loadAsync('../assets/presenter.glb'),
    new TTFLoader().loadAsync('../assets/fonts/Sora-800.ttf'),
  ]);
  const font = new Font(fontJson);

  const cues = buildCues();
  const M = cues.marks;
  const dir = direction(M);

  const stage = document.getElementById('stage');
  stage.style.transform = `scale(${scale})`;
  const renderer = new THREE.WebGLRenderer({ antialias: false, preserveDrawingBuffer: true, powerPreference: 'high-performance' });
  renderer.setPixelRatio(1);
  renderer.setSize(W, H, false);
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.0;
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  stage.insertBefore(renderer.domElement, stage.firstChild);

  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0x020203);
  scene.fog = new THREE.FogExp2(0x020203, 0.0065);
  scene.environment = studioEnvironment(renderer);
  scene.environmentIntensity = 0.9;

  const camera = new THREE.PerspectiveCamera(40, W / H, 0.1, 1500);
  const sprite = glowTexture(64);
  const ctx = { M, logos, font, sprite, camera, scene, noReflect: [] };

  const hq = buildHQ(ctx);
  const tl = buildTimeline(ctx);
  const pera = buildPera(ctx);
  scene.add(hq.group, tl.group, pera.group);

  const presenter = new Presenter(gltf);
  scene.add(presenter.root);
  const shadow = new THREE.Mesh(
    new THREE.PlaneGeometry(2.4, 2.4),
    new THREE.MeshBasicMaterial({ map: shadowTexture(), transparent: true, depthWrite: false }),
  );
  shadow.rotation.x = -Math.PI / 2;
  scene.add(shadow);

  // Lighting: key + two rims follow the presenter wherever he stands.
  scene.add(new THREE.AmbientLight(0xffffff, 0.05));
  const key = new THREE.SpotLight(0xf4f6ff, 2.4, 0, 0.3, 0.6, 0);
  const rimR = new THREE.SpotLight(0xff2a3a, 3.5, 0, 0.35, 0.6, 0);
  const rimW = new THREE.SpotLight(0xdfe6ff, 4, 0, 0.35, 0.6, 0);
  for (const l of [key, rimR, rimW]) scene.add(l, l.target);
  // Intro beam on the logo
  const logoSpot = new THREE.SpotLight(0xffffff, 0, 0, 0.18, 0.5, 0);
  scene.add(logoSpot, logoSpot.target);
  logoSpot.target.position.copy(LOGO_POS);
  const beam = new THREE.Mesh(new THREE.CylinderGeometry(0.02, 0.5, 12, 24, 1, true), beamMaterial(0xffffff, 0));
  beam.geometry.translate(0, -6, 0);
  scene.add(beam);
  ctx.noReflect.push(beam);

  // Finale key light
  const finalKey = new THREE.SpotLight(0xffffff, 0, 0, 0.35, 0.6, 0);
  finalKey.position.copy(FINAL_POS).add(new THREE.Vector3(-55, 40, 45));
  finalKey.target.position.copy(FINAL_POS);
  scene.add(finalKey, finalKey.target);

  // Post
  const composer = new EffectComposer(renderer, new THREE.WebGLRenderTarget(W, H, { type: THREE.HalfFloatType, samples: 4 }));
  composer.addPass(new RenderPass(scene, camera));
  const bloom = new UnrealBloomPass(new THREE.Vector2(W / 2, H / 2), 0.7, 0.5, 0.72);
  composer.addPass(bloom);
  const trail = new AfterimagePass(0);
  composer.addPass(trail);
  const grade = new ShaderPass(GradeShader);
  composer.addPass(grade);
  composer.addPass(new OutputPass());

  const overlay = new Overlay(cues);
  const prevCam = new THREE.Vector3();

  function renderFrame(t) {
    const fx = dir.fx(t);
    // sets
    const hqOn = t < M.s2 + 2.2 || (t > M.hqExpand && t < M.s11 + 1.4) || (t > M.s12 && t < M.s17 + 1.4);
    const tlOn = (t > M.s2 - 0.5 && t < M.hqExpand + 3.2) || t > M.s17 - 0.5;
    const peraOn = t > M.s11 - 0.5 && t < M.s12 + 1.6;
    hq.group.visible = hqOn;
    tl.group.visible = tlOn;
    pera.group.visible = peraOn;

    // camera
    const c = evalCamera(dir.cam, t);
    const c0 = evalCamera(dir.cam, Math.max(0, t - 1 / 30));
    camera.position.copy(c.pos);
    camera.lookAt(c.look);
    camera.fov = c.fov;
    camera.updateProjectionMatrix();
    const speed = c.pos.distanceTo(c0.pos) * 30;
    trail.uniforms.damp.value = clamp((speed - 12) / 70) * 0.72;
    prevCam.copy(c.pos);

    if (hqOn) hq.update(t);
    if (tlOn) tl.update(t);
    if (peraOn) pera.update(t);

    // presenter
    const cap = cues.captions.find((x) => t >= x.start && t <= x.end);
    const speech = cap ? Math.min(smooth((t - cap.start) / 0.4), smooth((cap.end - t) / 0.4)) : 0;
    const ps = evalPresenter(dir.path, dir.gest, t, speech);
    presenter.apply(ps);
    shadow.position.set(ps.pos.x, ps.pos.y + 0.015, ps.pos.z);
    const fwd = new THREE.Vector3().subVectors(camera.position, ps.pos).setY(0).normalize();
    const side = new THREE.Vector3(fwd.z, 0, -fwd.x);
    key.position.copy(ps.pos).addScaledVector(fwd, 5).addScaledVector(side, 2.5).setY(ps.pos.y + 5.5);
    key.target.position.copy(ps.pos).setY(ps.pos.y + 1.2);
    rimR.position.copy(ps.pos).addScaledVector(fwd, -4).addScaledVector(side, -3).setY(ps.pos.y + 3.2);
    rimR.target.position.copy(ps.pos).setY(ps.pos.y + 1.3);
    rimW.position.copy(ps.pos).addScaledVector(fwd, -4).addScaledVector(side, 3).setY(ps.pos.y + 3.6);
    rimW.target.position.copy(ps.pos).setY(ps.pos.y + 1.3);
    const presence = t < M.hqReveal ? 0 : smooth(ramp(t, M.hqReveal, M.hqReveal + 1.5));
    key.intensity = 2.4 * presence * (1 - fx.cold * 0.35);
    rimR.intensity = 3.5 * presence;
    rimW.intensity = 4 * presence;

    // intro beam
    const bk = window01(t, M.beam, M.hqReveal + 1.5, 0.3, 1.5);
    const sweep = smooth(ramp(t, M.beam, M.logo));
    beam.position.set(-4 + sweep * 3.2, 11, -3.5);
    beam.lookAt(LOGO_POS);
    beam.rotateX(-Math.PI / 2);
    beam.material.uniforms.uStrength.value = bk * 1.6;
    logoSpot.position.copy(beam.position);
    logoSpot.intensity = bk * 16 * sweep + (t > M.hqReveal ? 6 : 0);
    beam.visible = hqOn;

    scene.environmentIntensity = (0.12 + 0.78 * smooth(ramp(t, M.beam, M.hqReveal + 2))) * (1 - fx.cold * 0.4);

    renderer.toneMappingExposure = fx.exposure;
    grade.uniforms.uTime.value = t;
    grade.uniforms.uCold.value = fx.cold;
    bloom.strength = 0.7 + fx.flash * 1.2;
    scene.fog.density = t > M.s17 + 3 ? 0.0022 : 0.0065;
    finalKey.intensity = smooth(ramp(t, M.finalLogo - 0.4, M.finalLogo + 1)) * 5;
    finalKey.visible = t > M.s17;
    composer.render();
    overlay.update(t, fx);
  }

  window.film = { renderFrame, duration: cues.duration, cues, fps: 30, scene, hq, tl, pera, presenter };

  if (params.has('play')) {
    const t0 = performance.now() - Number(params.get('t') || 0) * 1000;
    const loop = () => {
      renderFrame(((performance.now() - t0) / 1000) % cues.duration);
      requestAnimationFrame(loop);
    };
    loop();
  } else renderFrame(Number(params.get('t') || 0));
}

function studioEnvironment(renderer) {
  // Dark studio with a few soft panels: elegant highlights on the metal.
  const env = new THREE.Scene();
  env.background = new THREE.Color(0x050506);
  const panel = (w, h, color, pos, rot) => {
    const m = new THREE.Mesh(new THREE.PlaneGeometry(w, h), new THREE.MeshBasicMaterial({ color, side: THREE.DoubleSide }));
    m.position.set(...pos);
    m.rotation.set(...rot);
    env.add(m);
  };
  panel(12, 3, 0xffffff, [0, 9, 0], [Math.PI / 2, 0, 0]);
  panel(1.2, 10, 0xd8deea, [-9, 2, 2], [0, Math.PI / 2, 0]);
  panel(1.2, 10, 0xd8deea, [9, 2, -2], [0, -Math.PI / 2, 0]);
  panel(8, 1.2, 0xffffff, [0, 3, -9], [0, 0, 0]);
  panel(16, 6, 0x2c2f36, [0, 3, 9], [0, Math.PI, 0]);
  panel(0.8, 4, 0x8a0e18, [-7, 1, 7], [0, Math.PI * 0.75, 0]);
  const pm = new THREE.PMREMGenerator(renderer);
  const rt = pm.fromScene(env, 0.02);
  return rt.texture;
}

function shadowTexture() {
  const c = document.createElement('canvas');
  c.width = c.height = 128;
  const g = c.getContext('2d');
  const grd = g.createRadialGradient(64, 64, 0, 64, 64, 64);
  grd.addColorStop(0, 'rgba(0,0,0,0.75)');
  grd.addColorStop(0.5, 'rgba(0,0,0,0.35)');
  grd.addColorStop(1, 'rgba(0,0,0,0)');
  g.fillStyle = grd;
  g.fillRect(0, 0, 128, 128);
  return new THREE.CanvasTexture(c);
}

const GradeShader = {
  uniforms: { tDiffuse: { value: null }, uTime: { value: 0 }, uCold: { value: 0 } },
  vertexShader: `varying vec2 vUv; void main(){ vUv = uv; gl_Position = projectionMatrix*modelViewMatrix*vec4(position,1.); }`,
  fragmentShader: /* glsl */ `
    uniform sampler2D tDiffuse; uniform float uTime, uCold; varying vec2 vUv;
    float hash(vec2 p){ return fract(sin(dot(p, vec2(12.9898,78.233)) + uTime*61.7) * 43758.5453); }
    void main(){
      vec2 d = vUv - .5;
      float r2 = dot(d,d);
      vec2 off = d * r2 * .012;
      vec3 col;
      col.r = texture2D(tDiffuse, vUv - off).r;
      col.g = texture2D(tDiffuse, vUv).g;
      col.b = texture2D(tDiffuse, vUv + off).b;
      // cool, slightly desaturated look for the 2024 freeze
      float l = dot(col, vec3(.2126,.7152,.0722));
      col = mix(col, vec3(l)*vec3(.86,.93,1.08), uCold*.75);
      col *= 1. - smoothstep(.18, .75, r2*1.6) * .55;
      col += (hash(vUv*1000.) - .5) * .025;
      gl_FragColor = vec4(col, 1.);
    }`,
};

init().catch((e) => {
  console.error(e);
  window.filmError = String(e && e.stack ? e.stack : e);
});
