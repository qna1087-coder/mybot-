# Vigil — Protection System for Telegram Channel Administrators

> وثيقة التحليل والتصميم (المرحلة 18 قبل الكود).
> اللغة: عربية مع المصطلحات التقنية بالإنجليزية كما وردت في الطلب.

---

## 0. هوية المنتج

**الاسم:** Vigil — من *vigilance* (اليقظة الهادئة). قصير، محايد، يُقرأ بسهولة بالعربية والإنجليزية، ولا يتعارض مع اسم الميزة الأساسية (Shield Mode).

**الجملة التعريفية:**
`Vigil · Protection System`
`Calm, continuous protection for channel administrators.`

**الشخصية:** نظام تحكم صامت، دقيق، لا يرفع صوته. يخبرك بما حدث ولماذا، ويعطيك زرًا واحدًا لتصحيحه.

---

## 1. تحليل المشروع

المشكلة التي يحلّها النظام: مالك قناة يملك عدة مشرفين، ويريد ضمانة آلية أن أي مشرف يخرج عن سياسة النشر (روابط، منشن، وسائط، إيموجي مدفوع خارج الحزمة، محتوى إنجليزي مخالف، لغات أجنبية) يفقد صلاحياته فورًا — مع إمكانية استرجاعها بضغطة واحدة، ومع "وضع احتماء" يُنزّل المشرفين مؤقتًا في أوقات محددة ثم يُعيدهم تلقائيًا.

النظام يتكوّن من أربع طبقات مستقلة:

| الطبقة | المسؤولية |
|---|---|
| **Authorization** | من يحق له استخدام النظام وعلى أي قناة |
| **Guard** | تحليل كل منشور وفق طبقات حماية متدرّجة (الأرخص أولًا) |
| **Enforcement** | تنفيذ السياسة: حذف، تنزيل مع Snapshot للصلاحيات، إشعار، استرجاع |
| **Control Surface** | واجهة الخاص: Screens تُحرَّر في مكانها، أزرار سياقية، تأكيدات |

المبدأ الحاكم: **لا فعل بدون سجل، ولا تنزيل بدون Snapshot، ولا Snapshot بدون زر استرجاع.**

---

## 2. Architecture

```
vigil/
├── __main__.py                 python -m vigil
├── app.py                      bootstrap: config → db → bot → services → dispatcher → recovery → scheduler
├── config.py                   pydantic-settings (كل الأسرار من Environment Variables)
├── core/
│   ├── glyphs.py               النظام البصري الموحّد (● ○ ◉ ◇ ! ✦ ↻ ↗ ⌁ ─)
│   ├── errors.py               أخطاء المجال (NotAuthorized, NotManaged, RightsMissing …)
│   ├── retry.py                غلاف استدعاءات Telegram: RetryAfter / Network / Server مع backoff
│   ├── timeutil.py             zoneinfo, now(), تنسيق "2m ago"
│   └── rights.py               قائمة Admin Rights الرسمية + snapshot/restore helpers
├── db/
│   ├── engine.py               async engine + session factory (SQLite افتراضيًا، PostgreSQL عبر DATABASE_URL)
│   ├── models.py               SQLAlchemy 2.0 models (13 جدول)
│   └── repo/                   مستودعات صغيرة لكل مجال (لا SQL داخل الـ handlers)
├── services/
│   ├── authorization.py        تصريح القنوات + أدوار المستخدمين (system owner / system admin / channel owner / manager)
│   ├── channels.py             حياة القناة: pending → active → suspended/revoked/detached
│   ├── admins.py               promote / demote / snapshot / restore / adopt / sync
│   ├── settings.py             إعدادات per-channel فوق defaults + typed accessors
│   ├── audit.py                Audit Log مركزي
│   ├── notifications.py        إشعارات المالك/مالك النظام + زر ↻ Restore
│   ├── enforcement.py          تطبيق السياسة على Verdict (delete / demote / notify) بـ per-channel lock
│   ├── guard/
│   │   ├── pipeline.py         ترتيب الطبقات + short-circuit
│   │   ├── language.py         اكتشاف Script محلي (Arabic / Latin / Other) بدون API
│   │   ├── length.py           حد 75 حرفًا لاتينيًا → حذف بدون فحص
│   │   ├── links.py            Entities: url / text_link / mention / text_mention / email / phone + forwards + preview
│   │   ├── media.py            Media Policy لكل نوع + Allowed Image Count + media_group aggregation
│   │   ├── emoji.py            Custom Emoji Allowlist (IDs + Packs) عبر entities
│   │   ├── wordlist.py         Fast-path محلي لألفاظ إنجليزية صريحة (يوفّر استدعاءات API)
│   │   ├── moderation.py       OpenRouter client: fallback chain، cooldowns، cache، daily budget، fail-open
│   │   └── verdict.py          Dataclasses: Verdict / Violation kinds
│   ├── shield/
│   │   ├── sessions.py         بدء/إنهاء Session مع Snapshots + استثناءات
│   │   ├── schedules.py        حساب النوافذ اليومية/الأسبوعية بالـ timezone (تعبر منتصف الليل)
│   │   └── scheduler.py        حلقة tick كل 30 ثانية تقرأ من DB (restart-safe)
│   └── recovery.py             عند الإقلاع: sessions منتهية → استرجاع؛ restores فاشلة → إعادة محاولة؛ تحقق صلاحيات البوت
├── telegram/
│   ├── middlewares/            db session per update، user context، permission gate، throttle
│   ├── callbacks.py            CallbackData factories مضغوطة (< 64 byte)
│   ├── handlers/
│   │   ├── private/            start, home, channels, admins, guard, emoji, shield, audit, system
│   │   └── channel/            channel_post, edited_channel_post, my_chat_member, chat_member
│   └── ui/
│       ├── texts/              i18n: en.py, ar.py — كل الـ microcopy في مكان واحد
│       ├── screens.py          مُركّب الشاشات (title / divider / status rows / footer)
│       └── keyboards.py        بُناة الأزرار السياقية
└── tests/
```

قواعد المعمارية:
- الـ handlers لا تحتوي منطقًا؛ تستدعي services وتعرض screens.
- الـ services لا تعرف Telegram UI؛ تعيد نتائج/أخطاء مجال.
- كل استدعاء Telegram يمر عبر `tg()` (retry + تصنيف الأخطاء).
- كل عملية حساسة (تنزيل، Shield، تصريح) داخل Transaction واحدة + Audit row.

---

## 3. Telegram Limitations التي تؤثر على الفكرة (وكيف نتعامل معها بصدق)

تم التحقق من هذه النقاط في Bot API 10.3 (أغسطس 2026) عبر نماذج aiogram 3.31 الرسمية:

### 3.1 منشورات القناة لا تحمل هوية الكاتب
`Message.from` — *"may be empty for messages sent to channels"*. الحقل الوحيد المتاح هو `author_signature`: *"Signature of the post author for messages in channels"*، ولا يظهر إلا إذا فعّل المالك **Sign messages** في إعدادات القناة.

**الأثر:** لا يمكن للبوت أن يعرف من نشر إلا عبر التوقيع.
**الحل المعتمد:**
- Vigil يبني **Signature Registry** لكل قناة من `getChatAdministrators`: مفتاح التطابق = `custom_title` إن وُجد وإلا الاسم الكامل.
- المنشور بلا توقيع → **Unattributed**: لا عقاب، يُسجَّل، ويُنبَّه المالك مرة واحدة (rate-limited) أن التوقيعات مطفأة.
- توقيعان متطابقان لمشرفَين → **Ambiguous**: لا عقاب، تنبيه للمالك بضرورة عناوين مميزة.
- البوت **لا يستطيع** تفعيل التوقيعات (لا يوجد method في Bot API) — يظهر ذلك في Onboarding Checklist.
- لا يوجد حقل في `ChatFullInfo` يخبرنا هل التوقيعات مفعّلة؛ نستنتج ذلك من أول منشور.

### 3.2 البوت يُنزّل فقط من رفعه هو
`can_promote_members`: *"demote administrators that they have promoted, directly or indirectly"*. تنزيل مشرف رفعه المالك مباشرة يعيد `CHAT_ADMIN_REQUIRED`.

**الأثر:** الحماية لا تعمل على مشرفين رُفعوا خارج النظام.
**الحل المعتمد:**
- كل مشرف محمي يُرفع **من خلال Vigil** ("Add administrator" → البوت يرفعه بـ preset صلاحيات).
- المشرفون الحاليون يظهرون بحالة `! Unmanaged` مع تعليمات "Adopt": المالك يزيل صلاحياتهم يدويًا ثم يضغط "Promote via Vigil".
- المالك (creator) لا يمكن تنزيله بأي طريقة → مستثنى دائمًا.
- عند فشل تنزيل أثناء مخالفة → تُسجَّل المخالفة، تُحذف الرسالة، ويُنبَّه المالك بأن التنزيل لم يكن ممكنًا.

### 3.3 لا يمكن للبوت ضبط Custom Title في القنوات
`setChatAdministratorCustomTitle`: *"in a supergroup promoted by the bot"* — القنوات غير مشمولة.
**الأثر:** عند الاسترجاع يعود كل الـ 19 حقًا بدقة، أما العنوان المخصص فيجب أن يعيده المالك يدويًا. Vigil يحفظه في الـ Snapshot ويذكّر به في رسالة الاسترجاع.

### 3.4 البوت يمنح فقط ما يملكه
الصلاحيات الممنوحة يجب أن تكون subset من صلاحيات البوت. عند الاسترجاع نُقاطع الـ Snapshot مع صلاحيات البوت الحالية ونذكر ما لم يمكن إعادته.

### 3.5 Media Groups تصل كرسائل منفصلة
الألبوم = عدة `channel_post` بنفس `media_group_id`. نُجمّعها في ذاكرة بنافذة قصيرة؛ الصورة رقم N+1 تتجاوز `allowed_image_count` تُطلق المخالفة مباشرة.

### 3.6 Callback data ≤ 64 bytes
معرّفات القنوات (14 حرفًا) وإيموجي (20 رقمًا) تفرض تشفيرًا مضغوطًا؛ لا نضع بيانات حساسة فيها، ونتحقق من الصلاحية على الخادم في كل ضغطة.

### 3.7 Edited posts
`edited_channel_post` يصل لتعديلات الرسائل الحديثة فقط (Telegram لا يرسل تعديلات الرسائل القديمة جدًا للبوتات). نعيد فحص كل تعديل يصل.

### 3.8 Anonymous admins / Channel posts / Scheduled
- في القنوات كل المنشورات "مجهولة" بطبيعتها → نفس معالجة 3.1.
- المنشورات المجدولة تصل كـ `channel_post` عند نشرها فعليًا → تُفحص عاديًا.
- الرسائل المحذوفة قبل تنفيذ الإجراء → خطأ `message to delete not found` يُعامل كنجاح.

### 3.9 Rate limits
`TelegramRetryAfter` يُحترم بدقة (sleep بقدر `retry_after`)، مع حد أقصى للمحاولات؛ عمليات Shield الجماعية تُنفَّذ تسلسليًا مع فواصل صغيرة.

### 3.10 حدود OpenRouter المجانية (مهم جدًا)
- كل نموذج `:free`: **20 request/min**.
- **الحد اليومي على مستوى الحساب كله** (ليس لكل نموذج): **50 request/day**، يرتفع إلى **1000/day** بعد شراء رصيد 10$ **مرة واحدة** (unlock دائم).
- لذلك تعدد النماذج يحمي من تعطّل نموذج أو RPM، **ولا يضاعف الحد اليومي**. Vigil يقلّل الاستدعاءات بـ: تجاهل العربي محليًا، حد الـ 75 حرفًا، wordlist محلي، cache للنص المكرر، وميزانية يومية مع تنبيه.

---

## 4. الصلاحيات المطلوبة للبوت داخل القناة

| الحق | ضروري؟ | لماذا |
|---|---|---|
| **Add new admins** (`can_promote_members`) | نعم | رفع/تنزيل/استرجاع المشرفين، Shield Mode |
| **Delete messages** (`can_delete_messages`) | نعم | حذف الرسالة المخالفة |
| `can_manage_chat` | تلقائي | قراءة قائمة المشرفين والأحداث |
| **Post messages** (`can_post_messages`) | اختياري | رسالة "غير مفعّلة" داخل القناة إن لم نستطع مراسلة من أضاف البوت |
| `can_invite_users` | اختياري | رفع مستخدم غير مشترك (Telegram يضيفه) |
| بقية الحقوق | لا | لا تُطلب. أقل امتياز ممكن |

**مطلب إعدادات القناة (يفعّله المالك يدويًا):** *Sign messages* = ON.

---

## 5. Events التي نراقبها (`allowed_updates`)

| Update | الاستخدام |
|---|---|
| `message` (private) | أوامر، FSM (إدخال مستخدم/ID/pack)، `users_shared` |
| `callback_query` | كل الأزرار — مع تحقق صلاحية على الخادم |
| `channel_post` | Content Guard |
| `edited_channel_post` | إعادة فحص التعديلات |
| `my_chat_member` | إضافة/إزالة البوت، تغيّر صلاحياته (يُفعّل تنبيه + إعادة تقييم Shield) |
| `chat_member` | رفع/تنزيل مشرفين من غير البوت → تحديث السجل، اكتشاف تدخل يدوي أثناء Shield |

---

## 6. Database Schema

| Table | الحقول الأساسية |
|---|---|
| `users` | id(tg), username, first_name, last_name, lang, role(owner/admin/user), dm_ok, created_at, last_seen_at |
| `channels` | id(tg), title, username, status(pending/active/suspended/revoked/detached), owner_user_id, added_by, authorized_by, authorized_at, timezone, bot_rights(JSON), signatures_state(unknown/on/off), created_at |
| `channel_permissions` | channel_id, user_id, role(owner/manager), granted_by, granted_at |
| `admins` | id, channel_id, user_id, username, full_name, custom_title, status(active/suspended/shielded/unmanaged/removed), managed_by_bot, rights(JSON), promoted_at, demoted_at, demote_reason, violations_count, shield_exempt, updated_at |
| `admin_snapshots` | id, channel_id, user_id, admin_id, rights(JSON), custom_title, reason(violation/shield/manual), taken_at, restored_at, restore_error |
| `violations` | id, channel_id, admin_id, user_id, username, kind, rule, message_id, excerpt, message_json, api_result(JSON), action(deleted/demoted/…), created_at, restored_at, restored_by |
| `settings` | channel_id(nullable=global), key, value(JSON), updated_by, updated_at |
| `shield_schedules` | id, channel_id, kind(daily/weekly), start_time, end_time, weekdays(mask), timezone, enabled, created_by |
| `shield_sessions` | id, channel_id, trigger(manual/schedule), schedule_id, started_by, started_at, ends_at, ended_at, status(active/ended/failed) |
| `shield_members` | id, session_id, channel_id, user_id, snapshot_id, status(suspended/restored/failed/skipped), error, restored_at |
| `emoji_allowlist` | id, channel_id(nullable=global), custom_emoji_id, set_name, emoji, source(manual/pack), added_by, added_at |
| `emoji_packs` | id, channel_id(nullable), set_name, title, emoji_count, synced_at |
| `audit_logs` | id, channel_id, actor_user_id, action, target_type, target_id, details(JSON), created_at |

Transactions: تنزيل مشرف = (snapshot + admins.status + violation + audit) في transaction واحدة قبل استدعاء Telegram؛ عند فشل Telegram تُحدَّث الحالة بـ `failed` بدل التراجع (كي يبقى الأثر مسجَّلًا).

---

## 7. User Flows

### 7.1 التصريح (Authorization)
1. مالك القناة يرفع البوت مشرفًا → `my_chat_member`.
2. القناة غير مصرّحة → تُسجَّل `pending` + audit `unauthorized_attempt`.
3. يُراسَل من أضاف البوت (إن كان قد بدأ البوت): "This channel isn't activated in Vigil yet." وإلا رسالة قصيرة داخل القناة (إن كان للبوت حق النشر).
4. مالك النظام يستقبل بطاقة: القناة، من أضافها، المالك المكتشف، زر **Activate** / **Decline**.
5. Activate → `active`، owner = creator، manager = من أضاف البوت (إن اختلف) → المالك يستقبل Onboarding Checklist: صلاحيات البوت، التوقيعات، تبنّي المشرفين.

### 7.2 إدارة المشرفين
Home → Administrators → قائمة بحالات (● Active / ◉ Shielded / ○ Suspended / ! Unmanaged) → صفحة مشرف: الصلاحيات، آخر مخالفة، أزرار سياقية (Suspend / Restore / Exempt from Shield / Reset / Remove).
Add administrator → اختيار المستخدم (زر Telegram الأصلي `request_users` أو forward أو ID) → preset صلاحيات (Publisher / Editor / Moderator / Custom) → Confirm → promote.

### 7.3 المخالفة
منشور → Pipeline → Verdict → Enforcement (حذف، Snapshot، تنزيل) → إشعار للمالك:
```
! Administrator access suspended
Ahmed · @ahmed

Reason
Link detected in post

Rule · Link Guard    Post · #4821    12:40
[↻ Restore as administrator]  [◇ Details]
```
Restore → نفس الصلاحيات من الـ Snapshot → تُحرَّر البطاقة: `● Restored · by You · 12:52`.

### 7.4 Shield Mode
Shield → حالة (○ Offline / ◉ Shielded until 06:00) → Start now (مدة أو حتى إيقاف يدوي) / Schedules (daily/weekly) / Exemptions.
البدء: لكل مشرف managed غير مستثنى: snapshot → demote → shield_members.
الانتهاء (يدوي/زمني/بعد restart): استرجاع تسلسلي؛ الفاشل يُعاد بعد دقيقة، ويُنبَّه المالك مع زر Retry.

### 7.5 Premium Emoji
Premium Emoji → الحزمة (packs) + المفردات → Add pack (اسم أو رابط `t.me/addemoji/…`) → `getStickerSet` → إضافة كل الـ IDs. Add single: إرسال الإيموجي نفسه أو الـ ID. Check ID → `getCustomEmojiStickers`.

### 7.6 Activity
Activity Log → آخر 10 عمليات مع pagination وفلتر نوع.

---

## 8. الهوية البصرية

### 8.1 المبادئ
- **Whitespace كعنصر تصميم:** سطر فارغ بين الأقسام دائمًا.
- **Hierarchy بثلاث درجات فقط:** عنوان الشاشة (bold)، اسم القسم (bold قصير)، القيمة (عادي).
- **لا جداول بأعمدة** (خط Telegram غير ثابت العرض) — كل معلومة في سطرها.
- **الإيموجي = لغة حالة، ليس زينة.** الأزرار بلا إيموجي إلا رمز فعل واحد (↻ ↗ ◇).

### 8.2 نظام الحالة الموحّد (Glyph System)
| Glyph | الدلالة | أمثلة |
|---|---|---|
| `●` | Active / On / Protected | Content Guard active, Admin active |
| `○` | Off / Offline / Suspended | Shield offline, Admin suspended |
| `◉` | Shielded (مؤقت بفعل النظام) | Admin under Shield Mode |
| `◇` | Waiting / Scheduled / Pending | Channel pending, next schedule |
| `!` | Attention (يحتاج فعل بشري) | Unmanaged admin, missing bot right |
| `✦` | Highlight (نادر) | عنوان الشاشة الرئيسية فقط |
| `↻` | Restore / Retry / Refresh | أزرار |
| `↗` | Open / External | رابط لقناة أو رسالة |
| `⌁` | Live signal / آخر حدث | سطر "Last event" |
| `─` | فاصل | تحت عنوان الشاشة |

### 8.3 تكوين الشاشة القياسي
```
✦ Vigil · Tech Daily
────────────────

Channel
● Protected

Administrators
●  6 active   ◉ 2 shielded   ! 1 attention

Shield Mode
○ Offline  ·  Next  Fri 22:00 → 06:00

Content Guard
● Active  ·  Links  Mentions  Media  Emoji  Language

⌁ 2m ago · Administrator access suspended — link detected
```
الأزرار في صفَّين من عمودَين + صف تنقّل واحد أسفل: `[‹ Back]  [↻]`.

### 8.4 Microcopy Voice
- جمل قصيرة، مبنى خبري، بلا علامات تعجب.
- الفعل أولًا ثم السبب في سطر مستقل.
- نجاح: `Protection is active.` / `Administrator restored.`
- انتباه: `Signatures are off.` + سطر شرح + الفعل المطلوب.
- خطأ: ما حدث، ثم ما يمكنك فعله. لا أكواد أخطاء في الوجه الأمامي (تذهب للـ Audit).
- Toasts (answerCallbackQuery): كلمة أو كلمتان — `Saved.` `Restored.` `Not permitted.`

### 8.5 اللغة
EN افتراضيًا، AR كاملة قابلة للتبديل من Settings (يُختار تلقائيًا من `language_code` عند أول /start).

---

## 9. Edge Cases (وقرار كلٍّ منها)

| الحالة | القرار |
|---|---|
| منشور بلا توقيع | لا عقاب؛ سجل `unattributed`؛ تنبيه المالك مرة/24h |
| توقيعان متطابقان | لا عقاب؛ تنبيه بضرورة custom titles مميزة |
| منشور من المالك | مستثنى دائمًا (لا يمكن تنزيله أصلًا) |
| منشور من البوت نفسه | يُتجاهل |
| مشرف Unmanaged يخالف | حذف الرسالة + إشعار "Could not suspend — promoted outside Vigil" |
| فشل API (timeout/429/5xx) لكل النماذج | `fail_open` افتراضيًا + audit `api_failure` + تنبيه مالك النظام (rate-limited)؛ قابل للتبديل إلى `fail_closed` |
| تجاوز الميزانية اليومية | نفس سلوك الفشل + تنبيه واحد يوميًا |
| النص عربي + إنجليزي | يُفحص الجزء اللاتيني فقط (العربي لا يُرسل أبدًا) |
| نص لاتيني بلغة غير الإنجليزية (فرنسية…) | النموذج يعيد `language`؛ إن لم تكن `en` والإعداد مفعّل → مخالفة "foreign language" |
| نص بـ script آخر (Cyrillic/CJK…) | مخالفة محلية فورية بلا API |
| أرقام/رموز/إيموجي فقط | تمرير |
| Album أكثر من صورة | الصورة N+1 تُطلق المخالفة؛ الحذف يشمل كل رسائل الألبوم المعروفة |
| Restart أثناء Shield | recovery يقرأ الـ sessions النشطة؛ المنتهي زمنيًا يُسترجع فورًا |
| البوت فقد `can_promote_members` أثناء Shield | تنبيه `!` للمالك؛ recovery يعيد المحاولة كل دقيقة حتى تعود الصلاحية |
| المالك رفع مشرفًا يدويًا أثناء Shield | `chat_member` → يُسجَّل، لا يُنزَّل تلقائيًا (فعل بشري صريح)، يُذكَر في الملخص |
| مستخدم غادر القناة أثناء Shield | استرجاع يفشل → `failed` + زر Retry؛ لا يُحذف السجل |
| البوت أُزيل من القناة | القناة `detached`؛ sessions تُعلَّم `failed`؛ تنبيه قوي للمالك: "Administrators under Shield cannot be restored until Vigil is re-added" |
| رسالة حُذفت قبل الإجراء | يُعامل كنجاح صامت |
| Update مكرَّر من Telegram | idempotency عبر (channel_id, message_id, rule) |
| DST / جدول يعبر منتصف الليل | zoneinfo + منطق نافذة يحسب البداية/النهاية على يومَين |
| نص أطول من حد التخزين | excerpt 500 حرف + hash |
| ضغط زر من مستخدم غير مخوّل | `Not permitted.` + audit |

---

## 10. قرارات التقنية

- **Python 3.11+, aiogram 3.31 (Bot API 10.3), SQLAlchemy 2.0 async, httpx, pydantic-settings.**
- **SQLite** افتراضيًا (ملف واحد، Transactions حقيقية) و**PostgreSQL** بتغيير `DATABASE_URL`.
- **Polling** افتراضيًا (لا يحتاج دومين)، **Webhook** اختياري عبر متغيرات البيئة.
- **Scheduler** داخلي يقرأ من DB كل 30 ثانية بدل APScheduler — أبسط وأكثر مقاومة لإعادة التشغيل.
- **لا أسرار في الكود**: `BOT_TOKEN`, `OPENROUTER_API_KEY`, `SYSTEM_OWNER_ID` من البيئة فقط.

### سلسلة النماذج الافتراضية (كلها مجانية، مرتبة: الأذكى أولًا ثم الأكثر استقرارًا)
| # | Model | لماذا |
|---|---|---|
| 1 | `nvidia/nemotron-3-ultra-550b-a55b:free` | أعلى نموذج مفتوح مجاني على مؤشر Artificial Analysis (48) — الأساسي |
| 2 | `qwen/qwen3.8-27b:free` | الأعلى على مؤشر ZeroOptimize للمجاني؛ قوي في التصنيف |
| 3 | `nvidia/nemotron-3-super-120b-a12b:free` | أفضل uptime/latency في قياسات المتعقّبين المستقلة |
| 4 | `google/gemma-4-31b-it:free` | احتياط مستقر من مزوّد مختلف |
| 5 | `nvidia/nemotron-3.5-lightning:free` | سريع، 1M context |
| 6 | `inclusionai/ling-3.0-flash-fin:free` | احتياط إضافي |
| 7 | `openrouter/free` | موجّه OpenRouter لأي نموذج مجاني متاح — الملاذ الأخير |

القائمة قابلة للتعديل من `MODERATION_MODELS` بدون تغيير كود، ويوجد سكربت `scripts/free_models.py` يطبع القائمة الحية.

---

## 11. ما بعد هذه الوثيقة
تنفيذ الكود وفق الهيكل أعلاه، ثم اختبارات وحدة لطبقات الـ Guard ومنطق الجداول، ثم README تشغيلي.
