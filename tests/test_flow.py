"""End-to-end: authorize → sync → violation → enforcement → restore → shield, against a fake bot."""

from __future__ import annotations

from datetime import timedelta

from vigil.core.timeutil import utcnow
from vigil.db.repo import admins as admin_repo
from vigil.db.repo import audit as audit_repo
from vigil.db.repo import shield as shield_repo
from vigil.db.repo import snapshots as snap_repo
from vigil.db.repo import violations as vio_repo

from .conftest import CHANNEL_ID, make_post, photo


async def activate(ctx, chat):
    async with ctx.db.session() as s:
        bot_member = await ctx.bot.get_chat_member(CHANNEL_ID, ctx.bot_id)
        ch, is_new = await ctx.channels.register_pending(s, chat, added_by=1, bot_member=bot_member)
        assert is_new and ch.status == "pending"
        ch, sync = await ctx.channels.activate(s, ch.id, by=100)
        assert ch.status == "active" and ch.owner_user_id == 1
        statuses = {a.user_id: a.status for a in sync.admins}
        assert statuses == {1: "owner", 2: "active", 3: "unmanaged"}
        assert ch.bot_rights and ch.bot_rights["can_promote_members"]
    return ch


async def run_post(ctx, message):
    async with ctx.db.session() as s:
        from vigil.db.repo import channels as ch_repo

        ch = await ch_repo.get(s, CHANNEL_ID)
        settings = await ctx.settings.get(s, ch.id)
        attribution = await ctx.attributor.attribute(s, ch, message)
        verdict = await ctx.guard.evaluate(s, ch, message, settings)
        v = None
        if verdict is not None:
            v = await ctx.enforcer.apply(s, ch, message, verdict, attribution, settings)
        return attribution, verdict, v


async def test_link_violation_demotes_and_restores(ctx, channel_chat):
    await activate(ctx, channel_chat)
    bot = ctx.bot

    post = make_post(101, text="join https://t.me/other", entities=[{"type": "url", "offset": 5, "length": 18}], author_signature="Ahmed")
    attribution, verdict, v = await run_post(ctx, post)
    assert attribution.status == "ok" and attribution.admin.user_id == 2
    assert verdict.kind == "link"
    assert v is not None and v.action == "deleted+demoted"
    assert bot.deleted == [(CHANNEL_ID, [101])]
    assert bot.promotions[-1][1] == 2 and not any(bot.promotions[-1][2].values())
    assert bot.sent and "suspended" in bot.sent[-1][1].lower()

    async with ctx.db.session() as s:
        a = await admin_repo.get_by_user(s, CHANNEL_ID, 2)
        assert a.status == "suspended" and a.violations_count == 1
        snap = await snap_repo.get(s, v.snapshot_id)
        assert snap.rights["can_post_messages"] is True
        # duplicate update is ignored
        from vigil.db.repo import channels as ch_repo

        ch = await ch_repo.get(s, CHANNEL_ID)
        settings = await ctx.settings.get(s, ch.id)
        assert await ctx.enforcer.apply(s, ch, post, verdict, attribution, settings) is None

        # restore with the exact snapshot
        outcome = await ctx.admins.restore(s, ch, 2, snap, by=1)
        assert outcome.ok and outcome.dropped_rights == []
        a = await admin_repo.get_by_user(s, CHANNEL_ID, 2)
        assert a.status == "active"
    granted = bot.promotions[-1][2]
    assert granted["can_post_messages"] and granted["can_delete_messages"] and not granted["can_promote_members"]


async def test_unmanaged_admin_is_deleted_but_not_demoted(ctx, channel_chat):
    await activate(ctx, channel_chat)
    post = make_post(102, text="hey @spam", entities=[{"type": "mention", "offset": 4, "length": 5}], author_signature="Editor")
    attribution, verdict, v = await run_post(ctx, post)
    assert attribution.admin.user_id == 3 and verdict.kind == "mention"
    assert v.action == "deleted"
    assert all(p[1] != 3 for p in ctx.bot.promotions)
    assert "outside Vigil" in ctx.bot.sent[-1][1]


async def test_owner_and_unsigned_and_arabic(ctx, channel_chat):
    await activate(ctx, channel_chat)
    owner_post = make_post(103, text="https://example.com", entities=[{"type": "url", "offset": 0, "length": 19}], author_signature="Owner")
    attribution, *_ = await run_post(ctx, owner_post)
    assert attribution.status == "owner"

    unsigned = make_post(104, text="https://example.com", entities=[{"type": "url", "offset": 0, "length": 19}], author_signature=None)
    attribution, verdict, v = await run_post(ctx, unsigned)
    assert attribution.status == "unsigned" and v.action == "deleted"

    arabic = make_post(105, text="مرحبا بالجميع، هذا منشور عادي تمامًا بلا روابط.", author_signature="Ahmed")
    _, verdict, v = await run_post(ctx, arabic)
    assert verdict is None and v is None


async def test_length_rule_deletes_only(ctx, channel_chat):
    await activate(ctx, channel_chat)
    long_en = make_post(106, text="word " * 20, author_signature="Ahmed")  # 80 Latin letters
    _, verdict, v = await run_post(ctx, long_en)
    assert verdict.kind == "length" and v.action == "deleted"
    async with ctx.db.session() as s:
        a = await admin_repo.get_by_user(s, CHANNEL_ID, 2)
        assert a.status == "active"  # length rule never demotes by default


async def test_album_second_photo_triggers(ctx, channel_chat):
    await activate(ctx, channel_chat)
    _, verdict, _ = await run_post(ctx, make_post(107, photo=photo(), media_group_id="alb", author_signature="Ahmed"))
    assert verdict is None
    _, verdict, v = await run_post(ctx, make_post(108, photo=photo(), media_group_id="alb", author_signature="Ahmed"))
    assert verdict.kind == "media" and sorted(ctx.bot.deleted[-1][1]) == [107, 108]


async def test_shield_mode_round_trip(ctx, channel_chat):
    await activate(ctx, channel_chat)
    async with ctx.db.session() as s:
        from vigil.db.repo import channels as ch_repo

        ch = await ch_repo.get(s, CHANNEL_ID)
        outcome = await ctx.shield.start(s, ch, by=1, ends_at=utcnow() - timedelta(seconds=1))
        assert [a.user_id for a in outcome.suspended] == [2]
        a = await admin_repo.get_by_user(s, CHANNEL_ID, 2)
        assert a.status == "shielded"
        assert await ctx.shield.start(s, ch, by=1) is None  # already active
    # scheduler tick ends the expired session and restores
    await ctx.scheduler.tick()
    async with ctx.db.session() as s:
        a = await admin_repo.get_by_user(s, CHANNEL_ID, 2)
        assert a.status == "active"
        sessions = await shield_repo.list_recent_sessions(s, CHANNEL_ID)
        assert sessions[0].status == "ended"
        actions = [e.action for e in await audit_repo.list_entries(s, channel_id=CHANNEL_ID, limit=50)]
        assert "shield.on" in actions and "shield.off" in actions


async def test_shield_restore_failure_is_retried(ctx, channel_chat):
    await activate(ctx, channel_chat)
    async with ctx.db.session() as s:
        from vigil.db.repo import channels as ch_repo

        ch = await ch_repo.get(s, CHANNEL_ID)
        await ctx.shield.start(s, ch, by=1)
        sess = await shield_repo.active_session(s, ch.id)
        ctx.bot.fail_promote_for.add(2)
        outcome = await ctx.shield.end(s, sess, by=1)
        assert len(outcome.failed) == 1 and sess.status == "failed"
        ctx.bot.fail_promote_for.clear()
        restored = await ctx.shield.retry_failed(s, only_fast=True)
        assert restored == 1
        a = await admin_repo.get_by_user(s, CHANNEL_ID, 2)
        assert a.status == "active"


async def test_violations_are_listed(ctx, channel_chat):
    await activate(ctx, channel_chat)
    await run_post(ctx, make_post(109, text="x https://a.b", entities=[{"type": "url", "offset": 2, "length": 11}], author_signature="Ahmed"))
    async with ctx.db.session() as s:
        assert await vio_repo.count_for_channel(s, CHANNEL_ID) == 1
        rows = await vio_repo.list_for_admin(s, CHANNEL_ID, 2)
        assert rows[0].kind == "link" and rows[0].display_name == "Ahmed"
