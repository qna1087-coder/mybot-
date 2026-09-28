# Vigil · Protection System

<p align="center"><b>✦ Vigil</b><br/>Calm, continuous protection for Telegram channel administrators.<br/><i>حماية هادئة ومستمرة لمشرفي قنوات Telegram.</i></p>

---

## العربية

### ما هو Vigil؟

نظام ذكي لإدارة وحماية مشرفي قناة Telegram. يُرفع البوت مشرفًا في القناة، ويُدار كل شيء من المحادثة الخاصة عبر لوحة تحكم بأزرار سياقية تُحرَّر في مكانها.

كل منشور من مشرف يمر عبر طبقات حماية بالترتيب (الأرخص أولًا):

| الطبقة | ماذا تفعل |
|---|---|
| **Media Guard** | سياسة لكل نوع وسائط. الصور «محدودة» بعدد افتراضي 1 لكل منشور/ألبوم. الفيديو والملصقات وGIF والملفات ممنوعة افتراضيًا |
| **Premium Emoji Guard** | أي `custom_emoji` خارج الحزمة المسموحة = مخالفة (عبر Entities و`custom_emoji_id`، لا عبر النص) |
| **Forward Guard** | إعادة التوجيه من قنوات/مستخدمين آخرين |
| **Link & Mention Guard** | `url` · `text_link` (رابط مخفي) · `mention` · `text_mention` · معاينة الرابط · أزرار URL · نمط `t.me` احتياطي |
| **Language Guard** | اكتشاف Script محلي: العربي لا يُرسل لأي API أبدًا؛ أي كتابة غير عربية/لاتينية = مخالفة فورية |
| **Length Guard** | أكثر من **75 حرفًا إنجليزيًا** → تُحذف الرسالة ولا تُرسل للفحص |
| **Wordlist** | ألفاظ إنجليزية صريحة تُرصد محليًا بلا API |
| **English Moderation** | النص اللاتيني فقط يُرسل إلى OpenRouter (سلسلة نماذج مجانية مع احتياطات) لرصد: الإباحي، القاصرين، المخدرات، العنف، الكراهية، التحرش، إيذاء النفس، الأسلحة، التطرف، الاحتيال |

عند المخالفة: حذف المنشور → **Snapshot** لكامل صلاحيات المشرف → تنزيله → إشعار المالك ببطاقة تحمل زر **↻ إعادته مشرفًا** يعيد نفس الصلاحيات بدقة.

**Shield Mode / وضع الاحتماء:** تنزيل كل المشرفين المُدارين مؤقتًا (فوري أو بجدول يومي/أسبوعي يعبر منتصف الليل) ثم استعادتهم تلقائيًا. الحالة في قاعدة البيانات، فتصمد أمام إعادة التشغيل، وتُعاد المحاولة عند الفشل.

### حقيقتان عن Telegram يجب معرفتهما قبل التشغيل

1. **منشورات القناة لا تحمل اسم الكاتب.** Bot API يعطي فقط `author_signature` عند تفعيل **Sign messages**. Vigil يطابق التوقيع مع اللقب المخصص (custom title) أو اسم المشرف. لذلك: فعّل التوقيعات، واجعل الألقاب مميزة. منشور بلا توقيع لا يُعاقَب عليه أحد (يُحذف إن كان مخالفًا، ويُنبَّه المالك).
2. **البوت يُنزّل فقط من رفعه هو.** قاعدة Telegram: `can_promote_members` تسمح بتنزيل من رفعتهم أنت مباشرة أو بشكل غير مباشر. المشرفون الذين رفعهم المالك بنفسه يظهرون بحالة `! Unmanaged`. لحمايتهم: أزل صلاحياتهم يدويًا ثم اضغط **رفع عبر Vigil**، أو أضف المشرفين الجدد من البوت مباشرة.

(التفاصيل الكاملة والقيود الأخرى في [`docs/DESIGN.md`](docs/DESIGN.md).)

### التشغيل

```bash
git clone <repo> vigil && cd vigil
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # ثم ضع القيم
python -m vigil
```

أو عبر Docker:

```bash
cp .env.example .env && docker compose up -d --build
```

**`.env` الأساسي:**

```
BOT_TOKEN=            # من @BotFather
SYSTEM_OWNER_ID=      # معرّفك الرقمي (مالك النظام)
OPENROUTER_API_KEY=   # من https://openrouter.ai/keys
```

> لا تضع التوكن أو المفتاح في أي ملف داخل Git. ملف `.env` مستثنى عبر `.gitignore`.

### التنصيب على سيرفر بأمر واحد (Debian/Ubuntu، كـ root)

```bash
curl -fsSL https://raw.githubusercontent.com/qna1087-coder/mybot-/claude/telegram-protection-system-fl5j6k/deploy/install.sh | bash
```

السكربت يثبّت المتطلبات، ينسخ الكود إلى `/opt/vigil`، يسألك عن القيم الثلاث (التوكن، معرّفك، مفتاح OpenRouter)، ينشئ خدمة `systemd` باسم `vigil` تعمل تلقائيًا بعد إعادة التشغيل، ويعرض السجل. إعادة تشغيل السكربت لاحقًا = تحديث الكود وإعادة التشغيل.

**إن كان المستودع خاصًا** (الأمر أعلاه يعيد 404): أنشئ Token للقراءة من GitHub (Settings → Developer settings → Fine-grained tokens → هذا المستودع → Contents: Read) ثم:

```bash
export GH_TOKEN=ghp_xxxxxxxx
curl -fsSL -H "Authorization: token $GH_TOKEN" \
  https://raw.githubusercontent.com/qna1087-coder/mybot-/claude/telegram-protection-system-fl5j6k/deploy/install.sh \
  | REPO_URL="https://$GH_TOKEN@github.com/qna1087-coder/mybot-.git" bash
```

### خطوات التفعيل لأول قناة

1. أرسل `/start` للبوت من حسابك (مالك النظام) ومن حساب مالك القناة.
2. أضف البوت مشرفًا في القناة بصلاحيتَي **Add new admins** و**Delete messages** (و**Post messages** اختياريًا).
3. ستصلك بطاقة «قناة جديدة بانتظار التفعيل» → **● تفعيل**.
4. يستلم مالك القناة قائمة تحقق: صلاحيات البوت، تفعيل **Sign messages**، وتبنّي المشرفين الحاليين.
5. من **Administrators → Add administrator** أضف المشرفين (اختيار من جهات الاتصال، أو توجيه رسالة، أو ID) مع مجموعة صلاحيات (Publisher / Editor / Moderator / Full).
6. من **Premium Emoji → Add pack** أضف الحزمة المسموحة (رابط `t.me/addemoji/…`).

### OpenRouter والحدود المجانية (مهم)

- كل نموذج `:free` محدود بـ **20 طلب/دقيقة**.
- الحد اليومي **على مستوى الحساب كله**: **50 طلب/يوم**، ويرتفع إلى **1000/يوم** بعد شراء رصيد **10$ مرة واحدة** (لا يُستهلك، مجرد unlock). تعدد النماذج يحمي من تعطّل نموذج، لكنه **لا يضاعف** الحد اليومي.
- لذلك يوجد `MODERATION_DAILY_BUDGET=45` (ارفعه إلى ~950 بعد الشراء)، وcache للنص المكرر، وفلاتر محلية تقلّل الاستدعاءات. عند نفاد الميزانية أو تعطّل كل النماذج: السلوك الافتراضي `MODERATION_FAIL_MODE=open` (يُسمح بالنص الإنجليزي مع تنبيه)؛ اختر `closed` إن أردت اعتباره مخالفة.
- السلسلة الافتراضية (كلها مجانية، الأذكى أولًا): `nemotron-3-ultra-550b` → `qwen3.8-27b` → `nemotron-3-super-120b` → `gemma-4-31b` → `nemotron-3.5-lightning` → `ling-3.0-flash-fin` → `openrouter/free`. لتحديثها من القائمة الحية:

```bash
python scripts/free_models.py
```

### هيكل المشروع

```
vigil/
  core/        glyphs · errors · retry (RetryAfter/backoff) · rights · timeutil
  db/          SQLAlchemy 2.0 async models + repositories (13 جدول)
  services/    authorization · channels · admins · settings · notifications · enforcement
               guard/ (language, length, links, media, emoji, wordlist, moderation, pipeline)
               shield/ (schedules, sessions, scheduler) · recovery · attribution
  telegram/    middlewares · callbacks · handlers/private · handlers/channel · ui/(screens, cards, texts en/ar)
tests/         25 اختبارًا: طبقات الحماية، الفحص مع fallback، الجداول، وتدفق كامل ببوت وهمي
docs/DESIGN.md وثيقة التحليل والتصميم
```

### الأوامر

`/start` الرئيسية · `/id` معرّفك · `/cancel` إلغاء الإدخال · `/help` مساعدة. كل ما عدا ذلك أزرار.

### الاختبارات

```bash
pip install -r requirements-dev.txt
pytest -q && ruff check .
```

---

## English

### What it is

Vigil is a protection system for Telegram channel administrators. The bot sits in the channel as an administrator; everything is controlled from the private chat through a panel of context-aware inline buttons that edit in place.

Every administrator post passes through layered guards, cheapest first: **media policy** (photos limited to 1 per post/album by default; video, stickers, GIFs, files blocked), **premium emoji allowlist** (by `custom_emoji_id`, from entities), **forwards**, **links & mentions** (`url`, `text_link`, `mention`, `text_mention`, link previews, URL buttons), **script detection** (Arabic never leaves the server; non-Arabic/non-Latin scripts are an immediate violation), the **75-English-letter rule** (delete without analysis), a **local wordlist**, and finally **English moderation** through OpenRouter with a chain of free models.

A violation deletes the post, snapshots the administrator's full rights, demotes them, and sends the owner a card with **↻ Restore as administrator**, which re-applies exactly the saved rights.

**Shield Mode** suspends all managed administrators for a period or on a daily/weekly schedule (windows may cross midnight), then restores them automatically. State lives in the database, survives restarts, and failed restores are retried.

### Two Telegram facts

1. **Channel posts have no author.** Bot API exposes only `author_signature`, present when *Sign messages* is on. Vigil matches it against custom titles / names. Keep signatures on and titles unique.
2. **A bot can only demote administrators it promoted.** Admins promoted by the owner directly show as `! Unmanaged`; remove their rights manually and tap *Promote via Vigil*, or add new admins through the bot.

Full analysis, schema, flows and edge cases: [`docs/DESIGN.md`](docs/DESIGN.md).

### Run

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # BOT_TOKEN, SYSTEM_OWNER_ID, OPENROUTER_API_KEY
python -m vigil        # or: docker compose up -d --build
```

### One-command server install (Debian/Ubuntu, as root)

```bash
curl -fsSL https://raw.githubusercontent.com/qna1087-coder/mybot-/claude/telegram-protection-system-fl5j6k/deploy/install.sh | bash
```

Installs prerequisites, clones into `/opt/vigil`, asks for the three secrets, creates a `vigil` systemd service, and shows the log. Falls back to Docker when Python ≥ 3.11 is not available. Re-run to update.

Private repository: fetch the script with a read-only token and pass `REPO_URL="https://$GH_TOKEN@github.com/qna1087-coder/mybot-.git"` (see the Arabic section for the exact two lines).

Bot rights needed in the channel: **Add new admins**, **Delete messages** (optional: Post messages). Channel setting: **Sign messages** on.

### OpenRouter free-tier limits

20 requests/min per `:free` model; **50 requests/day per account**, 1000/day after a one-time $10 credit purchase. The model chain protects against outages and per-minute limits, not against the daily cap — hence `MODERATION_DAILY_BUDGET`, caching, local pre-filters, and `MODERATION_FAIL_MODE=open|closed`. Refresh the chain with `python scripts/free_models.py`.

### Tests

```bash
pip install -r requirements-dev.txt && pytest -q && ruff check .
```

MIT © Vigil contributors
