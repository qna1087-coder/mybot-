import { clamp, easeOut, lerp, smooth } from './core.js';

// DOM overlay: cinematic titles, HUD tags and synchronized Arabic captions.
// Everything is a pure function of time so any frame can be rendered in isolation.

export class Overlay {
  constructor(cues) {
    this.cues = cues;
    this.root = document.getElementById('titles');
    this.cap = document.querySelector('#captions .cap');
    this.fade = document.getElementById('fade');
    this.flash = document.getElementById('flash');
    this.items = cues.titles.map((ti) => {
      const el = document.createElement('div');
      const arabic = /[؀-ۿ]/.test(ti.text);
      el.className = `t ${ti.cls} ${arabic && ti.cls !== 'div' ? 'ar' : 'en'}`;
      if (ti.cls === 'div') {
        const [num, name] = ti.text.split('|');
        el.innerHTML = `<span class="num">${num}</span><span class="name">${name}</span><span class="rule"></span>`;
      } else if (['en-xl', 'side-l', 'side-r'].includes(ti.cls)) {
        el.innerHTML = `<span class="txt"></span><span class="rule"></span>`;
        el.querySelector('.txt').textContent = ti.text;
      } else el.textContent = ti.text;
      if (ti.cls === 'hud') el.style.top = `${13 + ti.slot * 7.2}%`;
      this.root.appendChild(el);
      return { ...ti, el, rule: el.querySelector('.rule') };
    });
    this.lastCap = null;
  }

  update(t, fx) {
    for (const it of this.items) {
      const { el, start, end, cls } = it;
      if (t < start - 0.05 || t > end + 0.05) {
        if (el.style.opacity !== '0') el.style.opacity = '0';
        continue;
      }
      const u = t - start;
      const d = end - start;
      const inA = smooth(u / 0.7);
      const outA = smooth((end - t) / 0.6);
      const a = Math.min(inA, outA);
      let transform = '';
      let filter = `blur(${((1 - inA) * 10 + (1 - outA) * 6).toFixed(2)}px)`;
      if (cls === 'en-xl') {
        const sp = lerp(0.55, 0.32, easeOut(u / d));
        el.style.letterSpacing = `${sp}em`;
        el.style.paddingLeft = `${sp}em`;
        if (it.rule) it.rule.style.width = `${easeOut((u - 0.3) / 1.2) * 220}px`;
      } else if (cls === 'side-l' || cls === 'side-r') {
        if (it.rule) it.rule.style.width = `${easeOut((u - 0.3) / 1.0) * 160}px`;
        transform = `translateY(${(1 - inA) * 16}px)`;
      } else if (cls.startsWith('ar-')) {
        transform = `translateY(${(1 - inA) * 24}px) scale(${lerp(1.04, 1, easeOut(u / d))})`;
      } else if (cls === 'hud') {
        const reveal = clamp(u / 0.8);
        el.style.clipPath = `inset(0 ${(1 - reveal) * 100}% 0 0)`;
        filter = 'none';
      } else if (cls === 'div') {
        transform = `translateX(${(1 - inA) * 60}px)`;
        if (it.rule) it.rule.style.width = `${easeOut((u - 0.4) / 1.0) * 160}px`;
      } else if (cls === 'en-num') {
        transform = `scale(${lerp(1.18, 1, easeOut(u / 1.2))})`;
      } else if (cls.startsWith('en-lg') || cls === 'recap' || cls === 'hud-c') {
        const sp = lerp(cls === 'hud-c' ? 0.7 : 0.5, cls === 'hud-c' ? 0.5 : 0.3, easeOut(u / d));
        el.style.letterSpacing = `${sp}em`;
        el.style.paddingLeft = `${sp}em`;
      } else if (cls.startsWith('trio') || cls.startsWith('end') || cls === 'mark') {
        transform = `translateY(${(1 - inA) * 18}px)`;
      }
      el.style.opacity = a.toFixed(3);
      el.style.transform = transform;
      el.style.filter = filter;
    }

    // Captions
    const c = this.cues.captions.find((x) => t >= x.start - 0.1 && t <= x.end + 0.1);
    if (c) {
      if (this.lastCap !== c) {
        this.cap.textContent = c.text;
        this.lastCap = c;
      }
      const a = Math.min(smooth((t - c.start + 0.1) / 0.2), smooth((c.end + 0.1 - t) / 0.2));
      this.cap.style.opacity = a.toFixed(3);
    } else this.cap.style.opacity = '0';

    this.fade.style.opacity = clamp(fx.fade).toFixed(3);
    this.flash.style.opacity = clamp(fx.flash).toFixed(3);
  }
}
