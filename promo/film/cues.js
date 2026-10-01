// The film's single source of truth for timing.
//
// Events are laid out sequentially on a cursor. Narration lines ("vo") advance the
// cursor by a duration derived from their word count, so the picture, the captions,
// the soundtrack cues and the voice-over cue sheet all stay locked together.
//
//   {m: 'name'}            record marks.name = cursor
//   {gap: s}               advance the cursor by s seconds
//   {vo: 'text'}           narration + caption; advances the cursor
//   {t: 'text', ...}       on-screen title starting at cursor + (o || 0), lasting d seconds
//   {sfx: 'kind', o}       sound-design cue (read by tools/soundtrack.py)

const WORD = 0.3; // seconds per spoken word (calm, authoritative Iraqi narration)
const PAD = 0.35; // breath per line
const BETWEEN = 0.18; // gap between consecutive lines

export const EVENTS = [
  // ── SCENE 1 — INTRODUCTION ────────────────────────────────────────────────
  { m: 's1' },
  { sfx: 'drone', o: 0 },
  { gap: 2.6 },
  { m: 'beam' },
  { sfx: 'beam', o: 0 },
  { gap: 1.6 },
  { m: 'logo' },
  { sfx: 'impact', o: 0 },
  { t: 'BR', cls: 'mark', d: 3.4, o: 0.6 },
  { t: 'الحزب الإصلاحي', cls: 'ar-sub', d: 3.4, o: 1.5 },
  { gap: 4.6 },
  { m: 'hqReveal' },
  { sfx: 'whoosh', o: 0 },
  { gap: 1.6 },
  { m: 'vo1' },
  { vo: 'قبل كلشي… شنو هو الـ BR؟' },
  { t: 'MORE THAN A TEAM', cls: 'en-xl', d: 3.6, o: 0.3 },
  { vo: 'الـ BR مو مجرد تيم.' },
  { t: 'أكثر من مجرد تيم', cls: 'ar-xl', d: 3.2, o: 0.4 },
  { vo: 'مو مجرد مجموعة مؤقتة.' },
  { vo: 'ومو مشروع ينتهي بعد فترة.' },
  { vo: 'من البداية، الفكرة جانت أكبر من هذا.' },
  { t: 'ORGANIZATION', cls: 'en-xl', d: 3.4, o: 0.9 },
  { sfx: 'hit', o: 0.9 },
  { vo: 'BR هو تنظيم مبني على التقنية، الخبرة، والتعاون.' },
  { gap: 0.4 },

  // ── SCENE 2 — THE BEGINNING (2022) ────────────────────────────────────────
  { m: 's2' },
  { sfx: 'whoosh', o: 0.2 },
  { sfx: 'riser', o: -1.2 },
  { gap: 2.2 },
  { sfx: 'impact', o: 0 },
  { m: 'y2022' },
  { t: 'البداية', cls: 'ar-year', d: 4.2, o: 0.5 },
  { gap: 0.6 },
  { vo: 'بنهاية سنة 2022 بدأت فكرة BR.' },
  { vo: 'بالبداية كانت الفكرة عبارة عن تأسيس كيان يجمع الخبرات' },
  { m: 'nodes2022' },
  { vo: 'ويقدم أدوات وتقنيات وخدمات ضمن منظومة واحدة.' },
  { vo: 'الهدف من البداية ما جان مجرد جمع أشخاص.' },
  { m: 'struct2022' },
  { vo: 'الهدف جان بناء شيء منظم… عنده هيكل… عنده خدمات… وعنده رؤية.' },
  { gap: 0.3 },

  // ── SCENE 3 — 2023 ────────────────────────────────────────────────────────
  { m: 's3' },
  { sfx: 'whoosh', o: 0 },
  { gap: 1.8 },
  { m: 'y2023' },
  { sfx: 'hit', o: 0 },
  { t: 'بداية العمل', cls: 'ar-year', d: 3.6, o: 0.4 },
  { gap: 0.5 },
  { vo: 'وبـ 2023 بدأ العمل الفعلي.' },
  { m: 'online' },
  { t: 'SYSTEMS ONLINE', cls: 'hud', d: 5.6, o: 0.1, slot: 0 },
  { sfx: 'power', o: 0 },
  { vo: 'الخدمات اشتغلت.' },
  { t: 'INFRASTRUCTURE ACTIVE', cls: 'hud', d: 4.4, o: 0, slot: 1 },
  { sfx: 'ui', o: 0 },
  { vo: 'الأنظمة بدأت تتطور.' },
  { t: 'ORGANIZATION GROWING', cls: 'hud', d: 3.6, o: 0, slot: 2 },
  { sfx: 'ui', o: 0 },
  { vo: 'والـ BR بدأ يتحول من فكرة إلى منظومة حقيقية.' },
  { gap: 0.4 },

  // ── SCENE 4 — 2024 FREEZE ─────────────────────────────────────────────────
  { m: 's4' },
  { sfx: 'powerdown', o: 0 },
  { gap: 2.2 },
  { m: 'y2024' },
  { t: 'تجميد المشروع', cls: 'ar-year', d: 3.6, o: 0.4 },
  { gap: 0.5 },
  { vo: 'لكن بـ 2024 تم تجميد المشروع.' },
  { t: 'PAUSED', cls: 'en-xl', d: 2.0, o: 0.2 },
  { vo: 'مو نهاية. ومو إلغاء للفكرة.' },
  { t: 'NOT ENDED', cls: 'en-xl', d: 3.0, o: 0.3 },
  { vo: 'كان توقف مؤقت.' },
  { vo: 'الاسم بقى. الفكرة بقت. والخطة بقت موجودة.' },
  { gap: 0.6 },

  // ── SCENE 5 — 2026 RETURN ─────────────────────────────────────────────────
  { m: 's5' },
  { sfx: 'crack', o: 0 },
  { sfx: 'impact', o: 0 },
  { gap: 1.3 },
  { m: 'shatter' },
  { sfx: 'shatter', o: 0 },
  { sfx: 'whoosh', o: 0.3 },
  { gap: 1.8 },
  { m: 'y2026' },
  { sfx: 'impact', o: 0 },
  { t: 'THE RETURN', cls: 'en-xl', d: 2.6, o: 0.2 },
  { t: 'العودة', cls: 'ar-xl', d: 2.4, o: 2.0 },
  { gap: 0.4 },
  { vo: 'وهسه إحنا بـ 2026.' },
  { vo: 'والـ BR يرجع من جديد.' },
  { m: 'hqExpand' },
  { sfx: 'whoosh', o: 0 },
  { vo: 'لكن هالمرة مو كنسخة من الماضي.' },
  { t: 'REORGANIZED 2026', cls: 'hud-c', d: 5.2, o: 1.6 },
  { sfx: 'hit', o: 1.6 },
  { vo: 'هالمرة يرجع مثل ما جان مخطط إله من البداية… كتأسيس تنظيمي كامل.' },
  { gap: 0.4 },

  // ── SCENE 6 — TECHNOLOGY ──────────────────────────────────────────────────
  { m: 's6' },
  { sfx: 'whoosh', o: 0 },
  { gap: 0.8 },
  { m: 'techWords' },
  { vo: 'الـ BR يعتمد بشكل أساسي على التقنية.' },
  { vo: 'الفكرة هي إن الأدوات تشتغل ويانا…' },
  { vo: 'مو إحنا نضيع وقتنا ويا الأدوات.' },
  { gap: 0.3 },

  // ── SCENE 11 — PERA SERVICES ──────────────────────────────────────────────
  { m: 's11' },
  { sfx: 'whoosh', o: 0 },
  { sfx: 'servers', o: 0 },
  { gap: 1.0 },
  { vo: 'وجزء أساسي من هذه البنية يعتمد على خدمات Pera.' },
  { m: 'peraLogo' },
  { sfx: 'impact', o: 0 },
  { t: 'POWERED BY PERA SERVICES', cls: 'en-lg', d: 3.6, o: 0.2 },
  { vo: 'Pera توفر البنية والاستضافة والخدمات التقنية' },
  { m: 'peraWords' },
  { vo: 'اللي يعتمد عليها جزء من أنظمة BR.' },
  { gap: 1.0 },

  // ── SCENE 12 — WHAT BR IS LOOKING FOR ─────────────────────────────────────
  { m: 's12' },
  { sfx: 'calm', o: 0 },
  { gap: 0.8 },
  { vo: 'بس BR ما يبحث عن العدد.' },
  { gap: 0.8 },
  { t: 'WE WANT EXPERIENCE', cls: 'en-xl', d: 3.4, o: 0 },
  { sfx: 'hit', o: 0 },
  { vo: 'ما نريد شخص يدخل فقط حتى يصير اسمه عضو.' },
  { m: 'profiles' },
  { vo: 'نريد شخص عنده خبرة. عنده شيء يضيفه.' },
  { vo: 'عنده مجال يعرف يشتغل بيه.' },
  { vo: 'كل شخص داخل BR يكون عنده دور.' },
  { gap: 0.4 },

  // ── SCENE 13 — THREE DIVISIONS ────────────────────────────────────────────
  { m: 's13' },
  { sfx: 'riser', o: -1.0 },
  { gap: 0.6 },
  { t: 'BR STRUCTURE', cls: 'en-lg', d: 3.4, o: 0 },
  { vo: 'ولهذا، BR راح يكون مقسم إلى ثلاث جهات رئيسية.' },
  { m: 'split' },
  { sfx: 'impact', o: 0 },
  { gap: 0.4 },
  { m: 'div1' },
  { t: '01|جماعة العمليات', cls: 'div', d: 6.2, o: 0 },
  { sfx: 'hit', o: 0 },
  { vo: 'القسم الأول هو جماعة العمليات.' },
  { vo: 'هذا القسم مسؤول عن الأنظمة، التشغيل، الأتمتة،' },
  { vo: 'الإدارة التقنية، ومتابعة البنية.' },
  { m: 'div2' },
  { t: '02|جماعة الاستخبارات', cls: 'div', d: 6.8, o: 0 },
  { sfx: 'hit', o: 0 },
  { vo: 'القسم الثاني هو جماعة الاستخبارات.' },
  { vo: 'يركز على البحث، التحليل، ترتيب المعلومات،' },
  { vo: 'استخدام أدوات البيانات، والاستفادة من الـ Agent.' },
  { m: 'div3' },
  { t: '03|جماعة التجارة', cls: 'div', d: 7.4, o: 0 },
  { sfx: 'hit', o: 0 },
  { vo: 'القسم الثالث هو جماعة التجارة.' },
  { vo: 'يركز على الخدمات، التعاملات، الشراكات، وتنظيم الجانب التجاري.' },
  { gap: 0.4 },

  // ── SCENE 14 — THE PHILOSOPHY ─────────────────────────────────────────────
  { m: 's14' },
  { sfx: 'whoosh', o: 0 },
  { gap: 0.4 },
  { vo: 'وبالنهاية… الفكرة بينا بسيطة.' },
  { t: 'إنت تفيدنا', cls: 'ar-xl-top', d: 5.4, o: 0 },
  { t: 'وإحنا نفيدك', cls: 'ar-xl-bot', d: 4.6, o: 0.9 },
  { sfx: 'hit', o: 0 },
  { sfx: 'hit', o: 0.9 },
  { vo: 'إنت تفيدنا بخبرتك.' },
  { m: 'flow' },
  { vo: 'وإحنا نفيدك بالأدوات، الدعم، البنية، والخدمات اللي متوفرة عدنا.' },
  { t: 'VALUE ↔ VALUE', cls: 'en-xl', d: 5.0, o: 0.2 },
  { vo: 'الفائدة لازم تكون متبادلة.' },
  { vo: 'مو طرف ياخذ… وطرف ثاني ما يحصل شيء.' },
  { gap: 0.3 },

  // ── SCENE 15 — ECOSYSTEM ──────────────────────────────────────────────────
  { m: 's15' },
  { sfx: 'whoosh', o: 0 },
  { gap: 0.6 },
  { vo: 'BR اليوم مو خدمة وحدة. هو منظومة.' },
  { m: 'ecoWords' },
  { vo: 'تقنية. بيانات. أتمتة. ذكاء صناعي. أقسام. وبنية مترابطة.' },
  { gap: 0.6 },

  // ── SCENE 16 — IDENTITY ───────────────────────────────────────────────────
  { m: 's16' },
  { sfx: 'calm', o: 0 },
  { gap: 0.5 },
  { vo: 'هدفنا مو نسوي نسخة من أي تيم ثاني.' },
  { vo: 'ومو نكرر نفس الأدوات الموجودة عند الجميع.' },
  { m: 'build' },
  { t: 'BUILD', cls: 'trio-0', d: 5.0, o: 0 },
  { t: 'DEVELOP', cls: 'trio-1', d: 4.4, o: 0.6 },
  { t: 'ORGANIZE', cls: 'trio-2', d: 3.8, o: 1.2 },
  { sfx: 'hit', o: 0 },
  { sfx: 'hit', o: 0.6 },
  { sfx: 'hit', o: 1.2 },
  { vo: 'الهدف هو نبني منظومة عدها أدواتها،' },
  { vo: 'خدماتها، وطريقتها الخاصة بالشغل.' },
  { gap: 0.4 },

  // ── FINAL TIMELINE ────────────────────────────────────────────────────────
  { m: 's17' },
  { sfx: 'whoosh', o: 0 },
  { sfx: 'build', o: 0 },
  { gap: 1.2 },
  { m: 'r2022' },
  { t: '2022 — FOUNDATION', cls: 'recap', d: 2.8, o: 0 },
  { vo: 'الفكرة بدأت بنهاية 2022.' },
  { m: 'r2023' },
  { t: '2023 — ACTIVATION', cls: 'recap', d: 2.4, o: 0 },
  { vo: 'العمل بدأ بـ 2023.' },
  { m: 'r2024' },
  { t: '2024 — PAUSED', cls: 'recap', d: 2.6, o: 0 },
  { vo: 'المشروع توقف بـ 2024.' },
  { m: 'r2026' },
  { t: '2026 — REORGANIZED', cls: 'recap', d: 3.6, o: 0 },
  { vo: 'وبـ 2026… تبدأ المرحلة الجديدة.' },
  { gap: 0.2 },

  // ── FINAL SCENE ───────────────────────────────────────────────────────────
  { m: 's18' },
  { sfx: 'converge', o: 0 },
  { gap: 2.6 },
  { m: 'finalLogo' },
  { sfx: 'impact', o: 0 },
  { t: 'EST. 2022', cls: 'end-1', d: 13.2, o: 0.8 },
  { t: 'REORGANIZED 2026', cls: 'end-2', d: 12.4, o: 1.6 },
  { t: 'TECHNOLOGY · INTELLIGENCE · COMMERCE', cls: 'end-3', d: 11.4, o: 2.6 },
  { t: 'POWERED BY PERA', cls: 'end-4', d: 10.4, o: 3.6 },
  { gap: 0.4 },
  { vo: 'BR. أكثر من مجرد تيم.' },
  { vo: 'منظمة مبنية على الخبرة، التقنية، والتنظيم.' },
  { gap: 1.4 },
  { m: 'lastLine' },
  { vo: 'العودة بدأت.' },
  { gap: 1.2 },
  { m: 'fade' },
  { gap: 2.2 },
  { m: 'endHit' },
  { sfx: 'final', o: 0 },
  { gap: 3.4 },
  { m: 'end' },
];

function lineDuration(text) {
  const words = text.split(/\s+/).filter(Boolean).length;
  const ellipses = (text.match(/…/g) || []).length;
  return words * WORD + PAD + ellipses * 0.25;
}

export function buildCues() {
  const marks = {};
  const captions = [];
  const titles = [];
  const sfx = [];
  let cursor = 0;
  for (const e of EVENTS) {
    if (e.m) marks[e.m] = cursor;
    else if (e.gap !== undefined) cursor += e.gap;
    else if (e.vo) {
      const d = lineDuration(e.vo);
      captions.push({ start: cursor, end: cursor + d, text: e.vo });
      cursor += d + BETWEEN;
    } else if (e.t) {
      const start = cursor + (e.o || 0);
      titles.push({ start, end: start + e.d, text: e.t, cls: e.cls, slot: e.slot || 0 });
    } else if (e.sfx) sfx.push({ time: cursor + (e.o || 0), kind: e.sfx });
  }
  return { marks, captions, titles, sfx, duration: marks.end };
}
