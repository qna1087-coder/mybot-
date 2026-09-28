from __future__ import annotations

from vigil.services.guard import emoji as emoji_guard
from vigil.services.guard import language as L
from vigil.services.guard import length, links, media, wordlist
from vigil.services.guard.textutil import entity_text, strip_entities
from vigil.services.settings import DEFAULTS, ChannelSettings

from .conftest import make_post, photo


def test_script_classification():
    assert L.analyze("مرحبا بكم في القناة").classification == "arabic"
    assert L.analyze("Hello everyone").classification == "latin"
    assert L.analyze("مرحبا everyone").classification == "mixed"
    assert L.analyze("Привет как дела").classification == "other"
    assert L.analyze("こんにちは世界").classification == "other"
    assert L.analyze("123 😀 …").classification == "none"
    # Iraqi dialect letters are Arabic script, never "other"
    assert L.analyze("گ چ ڤ شكو ماكو").classification == "arabic"
    # A stray accented Latin letter does not make a foreign script
    assert L.analyze("café is open").classification == "latin"


def test_latin_extraction_from_mixed_text():
    p = L.analyze("اليوم نتحدث عن Machine Learning و Python")
    assert p.latin_text == "Machine Learning Python"
    assert p.latin == 21


def test_length_rule_boundary():
    assert length.check("a" * 75, 75) is None
    v = length.check("a" * 76, 75)
    assert v is not None and v.kind == "length" and v.detail == "76/75"
    # Arabic letters never count
    assert length.check("ب" * 500 + "abc", 75) is None
    assert length.check("x" * 100, 0) is None


def test_entity_text_respects_utf16():
    text = "😀😀 @ahmed hi"
    ent = type("E", (), {"offset": 5, "length": 6, "type": "mention"})()
    assert entity_text(text, ent) == "@ahmed"
    stripped = strip_entities(text, [ent], {"mention"})
    assert "@ahmed" not in stripped and "hi" in stripped


def test_link_detection_by_entities():
    m = make_post(1, text="see https://t.me/other now", entities=[{"type": "url", "offset": 4, "length": 18}])
    v = links.check_links(m, links=True, mentions=True)
    assert v and v.kind == "link" and v.rule == "link_guard:url"

    m = make_post(2, text="click here", entities=[{"type": "text_link", "offset": 0, "length": 10, "url": "https://x.y"}])
    v = links.check_links(m, links=True, mentions=True)
    assert v and v.rule == "link_guard:hidden_link" and v.detail == "https://x.y"

    m = make_post(3, text="hi @someone", entities=[{"type": "mention", "offset": 3, "length": 8}])
    v = links.check_links(m, links=True, mentions=True)
    assert v and v.kind == "mention" and v.detail == "@someone"
    assert links.check_links(m, links=True, mentions=False) is None

    m = make_post(4, text="plain text without anything")
    assert links.check_links(m, links=True, mentions=True) is None

    m = make_post(5, text="join t.me/xyz")  # no entity supplied → regex backup
    v = links.check_links(m, links=True, mentions=True)
    assert v and v.rule == "link_guard:pattern"


def test_forward_detection():
    m = make_post(6, text="fwd", forward_origin={"type": "channel", "date": 1, "chat": {"id": -100, "type": "channel", "title": "Other"}, "message_id": 5})
    v = links.check_forward(m)
    assert v and v.kind == "forward" and v.detail == "Other"
    m2 = make_post(7, text="auto", forward_origin={"type": "channel", "date": 1, "chat": {"id": -100, "type": "channel", "title": "Other"}, "message_id": 5}, is_automatic_forward=True)
    assert links.check_forward(m2) is None


def test_media_policy_and_album_count():
    st = ChannelSettings(dict(DEFAULTS))
    tracker = media.MediaGroupTracker()
    single = make_post(10, caption="pic", photo=photo())
    assert media.check(single, st, tracker) is None  # one photo allowed
    a1 = make_post(11, photo=photo(), media_group_id="g1")
    a2 = make_post(12, photo=photo(), media_group_id="g1")
    assert media.check(a1, st, tracker) is None
    v = media.check(a2, st, tracker)
    assert v and v.rule == "media_guard:photo_count" and v.related_message_ids == [11, 12]
    vid = make_post(13, video={"file_id": "v", "file_unique_id": "vu", "width": 1, "height": 1, "duration": 1})
    v = media.check(vid, st, tracker)
    assert v and v.rule == "media_guard:video"
    doc_img = make_post(14, document={"file_id": "d", "file_unique_id": "du", "mime_type": "image/png"})
    assert media.classify_media(doc_img) == "document_image"
    st2 = ChannelSettings({**DEFAULTS, "allowed_image_count": 0})
    assert media.check(single, st2, media.MediaGroupTracker()) is not None


def test_custom_emoji_allowlist():
    m = make_post(20, text="hi ✦ ok", entities=[{"type": "custom_emoji", "offset": 3, "length": 1, "custom_emoji_id": "5000000000000000001"}])
    assert emoji_guard.check(m, {"5000000000000000001"}) is None
    v = emoji_guard.check(m, set())
    assert v and v.kind == "emoji" and "5000000000000000001" in v.detail
    assert emoji_guard.extract_custom_emoji(m) == [("5000000000000000001", "✦")]


def test_wordlist_fast_path():
    assert wordlist.check("buy cocaine here", {"drugs"}) is not None
    assert wordlist.check("buy cocaine here", {"sexual"}) is None
    assert wordlist.check("a normal sentence", {"drugs", "sexual"}) is None
