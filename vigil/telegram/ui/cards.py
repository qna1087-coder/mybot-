"""Notification cards: rendered per recipient language. Pure functions → (text, keyboard)."""

from __future__ import annotations

from typing import Any

from aiogram.types import InlineKeyboardMarkup

from vigil.core import glyphs as G
from vigil.core.rights import RIGHT_LABELS_AR, RIGHT_LABELS_EN
from vigil.core.timeutil import fmt_clock, fmt_datetime, humanize_ago
from vigil.telegram.callbacks import (
    A_ACTIVATE,
    A_DECLINE,
    A_RESTORE_VIOLATION,
    A_RETRY_SHIELD,
    S_ADMIN,
    S_ADMINS,
    S_DASH,
    S_SHIELD,
    S_VIOLATION,
    Act,
    Nav,
)
from vigil.telegram.ui.screens import kb
from vigil.telegram.ui.texts import esc, t


def right_labels(lang: str, rights: list[str]) -> str:
    table = RIGHT_LABELS_AR if lang == "ar" else RIGHT_LABELS_EN
    return ", ".join(table.get(r, r) for r in rights) or t(lang, "none")


def violation_card(
    lang: str,
    ch: Any,
    v: Any,
    admin: Any | None,
    *,
    attribution_status: str,
    signature: str | None,
    demoted: bool,
    deleted: bool,
    could_not: str | None,
    restored_by: str | None = None,
) -> tuple[str, InlineKeyboardMarkup]:
    if demoted:
        title = t(lang, "card_suspended")
    elif deleted:
        title = t(lang, "card_deleted")
    else:
        title = t(lang, "card_noticed")

    if admin is not None:
        who = esc(admin.display)
        if admin.username:
            who += f" · @{esc(admin.username)}"
    elif attribution_status == "unsigned":
        who = t(lang, "card_unsigned_name")
    elif attribution_status == "ambiguous":
        who = t(lang, "card_ambiguous_name", sig=esc(signature or ""))
    else:
        who = t(lang, "card_unknown_name", sig=esc(signature or ""))

    reason = t(lang, f"reason_{v.kind}")
    detail = esc(v.detail) if v.detail else ""
    lines = [f"<b>{title}</b>", who, "", f"<b>{t(lang, 'reason')}</b>", reason]
    if detail:
        lines.append(f"<code>{detail}</code>")
    if v.excerpt and v.kind in ("content", "language", "length"):
        lines.append(f"<i>{esc(v.excerpt[:160])}</i>")
    lines.append("")
    lines.append(f"{t(lang, 'card_rule')} · {t(lang, 'kind_' + v.kind)}")
    flag = t(lang, "card_deleted_flag") if deleted else t(lang, "card_kept_flag")
    lines.append(f"{t(lang, 'card_post')} · #{v.message_id} · {flag}")
    lines.append(f"{fmt_clock(v.created_at, ch.timezone)} · {esc(ch.title)}")
    if could_not:
        lines.append("")
        lines.append(t(lang, "card_could_not", why=t(lang, f"why_{could_not}")))
    if restored_by:
        lines.append("")
        lines.append(t(lang, "card_restored_line", by=esc(restored_by), when=fmt_clock(v.restored_at, ch.timezone)))

    rows: list[list[tuple[str, str]]] = []
    if demoted and not restored_by:
        rows.append([(t(lang, "btn_restore_admin"), Act(a=A_RESTORE_VIOLATION, c=ch.id, t=str(v.id)).pack())])
    second: list[tuple[str, str]] = [(t(lang, "btn_view_violation"), Nav(s=S_VIOLATION, c=ch.id, a=str(v.id)).pack())]
    if admin is not None:
        second.append((t(lang, "btn_view_admin"), Nav(s=S_ADMIN, c=ch.id, a=str(admin.id)).pack()))
    rows.append(second)
    return "\n".join(lines), kb(rows)


def shield_on_card(lang: str, ch: Any, outcome: Any) -> tuple[str, InlineKeyboardMarkup]:
    sess = outcome.session
    ends = fmt_datetime(sess.ends_at, ch.timezone) if sess.ends_at else t(lang, "ends_manual")
    text = "\n".join(
        [
            f"<b>{t(lang, 'card_shield_on')}</b>",
            esc(ch.title),
            "",
            t(lang, "card_shield_on_body", n=len(outcome.suspended), skipped=len(outcome.skipped), ends=ends),
        ]
    )
    if outcome.skipped:
        text += "\n" + "\n".join(
            t(lang, "card_shield_failed_row", name=esc(a.display), error=esc(err[:60])) for a, err in outcome.skipped[:5]
        )
    return text, kb([[(t(lang, "btn_shield"), Nav(s=S_SHIELD, c=ch.id).pack())]])


def shield_off_card(lang: str, ch: Any, outcome: Any, names: dict[int, str]) -> tuple[str, InlineKeyboardMarkup]:
    text = "\n".join(
        [
            f"<b>{t(lang, 'card_shield_off')}</b>",
            esc(ch.title),
            "",
            t(lang, "card_shield_off_body", restored=len(outcome.restored), failed=len(outcome.failed)),
        ]
    )
    rows: list[list[tuple[str, str]]] = []
    if outcome.failed:
        text += "\n" + "\n".join(
            t(lang, "card_shield_failed_row", name=esc(names.get(m.user_id, str(m.user_id))), error=esc((err or "")[:60]))
            for m, err in outcome.failed[:6]
        )
        text += "\n\n" + t(lang, "ssp_failed_hint")
        rows.append([(t(lang, "btn_retry_restore"), Act(a=A_RETRY_SHIELD, c=ch.id, t=str(outcome.session.id)).pack())])
    rows.append([(t(lang, "btn_admins"), Nav(s=S_ADMINS, c=ch.id).pack())])
    return text, kb(rows)


def api_failure_card(lang: str, ch: Any, error: str, fail_open: bool) -> tuple[str, InlineKeyboardMarkup]:
    mode = t(lang, "mode_allowed") if fail_open else t(lang, "mode_blocked")
    text = f"<b>{t(lang, 'card_api_failure')}</b>\n{esc(ch.title)}\n\n" + t(
        lang, "card_api_failure_body", mode=mode, error=f"<code>{esc(error[:160])}</code>"
    )
    return text, kb([[(t(lang, "btn_guard"), Nav(s="grd", c=ch.id).pack())]])


def unattributed_card(lang: str, ch: Any) -> tuple[str, InlineKeyboardMarkup]:
    text = f"<b>{t(lang, 'card_unattributed')}</b>\n{esc(ch.title)}\n\n{t(lang, 'card_unattributed_body')}"
    return text, kb([[(t(lang, "btn_admins"), Nav(s=S_ADMINS, c=ch.id).pack())]])


def ambiguous_card(lang: str, ch: Any, sig: str, names: list[str]) -> tuple[str, InlineKeyboardMarkup]:
    text = f"<b>{t(lang, 'card_ambiguous')}</b>\n{esc(ch.title)}\n\n" + t(
        lang, "card_ambiguous_body", sig=esc(sig), names=", ".join(esc(n) for n in names)
    )
    return text, kb([[(t(lang, "btn_admins"), Nav(s=S_ADMINS, c=ch.id).pack())]])


def bot_rights_card(lang: str, ch: Any, missing: list[str]) -> tuple[str, InlineKeyboardMarkup]:
    text = f"<b>{t(lang, 'card_bot_rights')}</b>\n{esc(ch.title)}\n\n" + t(
        lang, "card_bot_rights_body", rights=right_labels(lang, missing)
    )
    return text, kb([[(t(lang, "btn_bot_rights"), Nav(s="brt", c=ch.id).pack())]])


def bot_removed_card(lang: str, ch: Any, shield_members: int) -> tuple[str, InlineKeyboardMarkup | None]:
    text = f"<b>{t(lang, 'card_bot_removed', title=esc(ch.title))}</b>"
    if shield_members:
        text += "\n\n" + t(lang, "card_bot_removed_shield", n=shield_members)
    return text, None


def pending_card(lang: str, ch: Any, added_by: str, owner: str) -> tuple[str, InlineKeyboardMarkup]:
    text = f"<b>{t(lang, 'card_pending')}</b>\n\n" + t(
        lang, "pend_card", title=esc(ch.title), id=ch.id, added_by=esc(added_by), owner=esc(owner)
    )
    return text, kb(
        [
            [
                (t(lang, "btn_activate"), Act(a=A_ACTIVATE, c=ch.id).pack()),
                (t(lang, "btn_decline"), Act(a=A_DECLINE, c=ch.id).pack()),
            ]
        ]
    )


def activated_card(lang: str, ch: Any, *, missing_rights: list[str], managed: int, unmanaged: int) -> tuple[str, InlineKeyboardMarkup]:
    rights_line = t(lang, "chk_rights_ok") if not missing_rights else t(lang, "chk_rights_missing", rights=right_labels(lang, missing_rights))
    admins_line = t(lang, "chk_admins_ok", n=managed)
    if unmanaged:
        admins_line += "\n" + t(lang, "chk_admins_unmanaged", n=unmanaged)
    text = f"<b>{t(lang, 'card_activated', title=esc(ch.title))}</b>\n\n" + t(
        lang, "card_activated_body", rights_line=rights_line, signatures_line=t(lang, "chk_signatures"), admins_line=admins_line
    )
    return text, kb([[(t(lang, "btn_admins"), Nav(s=S_ADMINS, c=ch.id).pack()), (t(lang, "home"), Nav(s=S_DASH, c=ch.id).pack())]])


def unauthorized_card(lang: str, ch: Any) -> str:
    return t(lang, "card_unauthorized", title=esc(ch.title), id=ch.id)


def reattached_card(lang: str, ch: Any) -> tuple[str, InlineKeyboardMarkup]:
    return f"<b>{t(lang, 'card_reattached', title=esc(ch.title))}</b>", kb([[(t(lang, "home"), Nav(s=S_DASH, c=ch.id).pack())]])


def declined_card(lang: str, ch: Any) -> str:
    return t(lang, "card_declined", title=esc(ch.title))


def external_repromote_card(lang: str, ch: Any, name: str) -> str:
    return f"{t(lang, 'card_external_repromote', name=esc(name))}\n{esc(ch.title)}"


def member_restored_card(lang: str, ch: Any, name: str) -> str:
    return f"{G.ACTIVE} {t(lang, 'restored_ok')}\n{esc(name)} · {esc(ch.title)} · {humanize_ago(ch.updated_at, lang)}"
