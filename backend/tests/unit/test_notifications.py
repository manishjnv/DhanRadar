"""
Unit tests for the Phase-6 Notification module — no DB, no network.

Covers:
  templates  — render(), LABEL_DISPLAY, UnknownTemplate, html-escaping, disclosure footer
  service    — publish_notification, in_quiet_hours, rate cap helpers, parse_hhmm
  channels   — _classify_status, deliver_telegram, deliver_email, transport error
  sharecard  — generate_share_card (storage monkeypatched), _render_png PNG magic bytes
"""

from __future__ import annotations

import re
from datetime import time

import httpx
import pytest

from dhanradar.notifications import channels, service
from dhanradar.notifications.schemas import NotificationJob
from dhanradar.notifications.templates import (
    LABEL_DISPLAY,
    UnknownTemplate,
    render,
)

# ---------------------------------------------------------------------------
# 1. templates
# ---------------------------------------------------------------------------

_KNOWN_TEMPLATES = ["test_ping", "mf_report_ready", "mf_label_change", "weekly_digest"]

_LABEL_CHANGE_DATA = {
    "scheme_name": "Acme Flexicap",
    "prior_label": "on_track",
    "new_label": "off_track",
}


def test_mf_label_change_text_contains_expected_fields():
    msg = render("mf_label_change", _LABEL_CHANGE_DATA)
    assert "Acme Flexicap" in msg.text
    assert "On track" in msg.text    # LABEL_DISPLAY["on_track"]
    assert "Off track" in msg.text   # LABEL_DISPLAY["off_track"]
    assert "NOT_ADVICE" in msg.text


def test_all_known_templates_carry_disclosure_in_text_and_html():
    """Every rendered .text AND .html must contain NOT_ADVICE and 'Educational'."""
    min_data = {
        "test_ping": {},
        "mf_report_ready": {"fund_count": 3, "report_url": "https://app.dhanradar.com/report/1"},
        "mf_label_change": _LABEL_CHANGE_DATA,
        "weekly_digest": {},
    }
    for tid in _KNOWN_TEMPLATES:
        msg = render(tid, min_data[tid])
        assert "NOT_ADVICE" in msg.text, f"{tid}: NOT_ADVICE missing from .text"
        assert "Educational" in msg.text, f"{tid}: 'Educational' missing from .text"
        assert "NOT_ADVICE" in msg.html, f"{tid}: NOT_ADVICE missing from .html"
        assert "Educational" in msg.html, f"{tid}: 'Educational' missing from .html"


def test_no_standalone_advisory_verb_in_label_change():
    """The rendered text must NOT contain capitalised standalone 'Buy' or 'Sell'
    as label words.  Lowercase forms inside disclosure prose are fine."""
    msg = render("mf_label_change", _LABEL_CHANGE_DATA)
    assert not re.search(r"\bBuy\b", msg.text), "capitalised 'Buy' found in mf_label_change text"
    assert not re.search(r"\bSell\b", msg.text), "capitalised 'Sell' found in mf_label_change text"


def test_no_standalone_advisory_verb_in_mf_report_ready():
    msg = render(
        "mf_report_ready",
        {"fund_count": 5, "report_url": "https://app.dhanradar.com/report/2"},
    )
    assert not re.search(r"\bBuy\b", msg.text)
    assert not re.search(r"\bSell\b", msg.text)


def test_unknown_template_raises_unknown_template():
    with pytest.raises(UnknownTemplate):
        render("nope", {})


def test_unknown_template_is_subclass_of_key_error():
    with pytest.raises(KeyError):
        render("nope", {})


def test_html_escaping_in_scheme_name():
    """HTML-unsafe scheme names must be escaped in .html but not necessarily .text."""
    msg = render(
        "mf_label_change",
        {"scheme_name": "<b>x</b>", "prior_label": "on_track", "new_label": "off_track"},
    )
    assert "&lt;b&gt;" in msg.html, "html-unsafe scheme name was not escaped in .html"
    assert "<b>" not in msg.html, "raw <b> tag leaked into .html"


def test_label_display_mapping():
    assert LABEL_DISPLAY["in_form"] == "In form"
    assert LABEL_DISPLAY["on_track"] == "On track"
    assert LABEL_DISPLAY["off_track"] == "Off track"
    assert LABEL_DISPLAY["out_of_form"] == "Out of form"
    assert LABEL_DISPLAY["insufficient_data"] == "Insufficient data"


def test_rendered_message_is_frozen():
    msg = render("test_ping", {})
    with pytest.raises((AttributeError, TypeError)):
        msg.subject = "mutated"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# 2. service — pure functions (no Redis)
# ---------------------------------------------------------------------------

_QUIET_CASES = [
    # (current, start_hhmm, end_hhmm, expected) — wrap window 22:00→07:00
    (time(23, 0), "22:00", "07:00", True),
    (time(3, 0),  "22:00", "07:00", True),
    (time(12, 0), "22:00", "07:00", False),
    # non-wrap window 08:00→17:00
    (time(9, 0),  "08:00", "17:00", True),
    (time(18, 0), "08:00", "17:00", False),
    # null / equal
    (time(9, 0),  None,    None,    False),
]


@pytest.mark.parametrize("current,start_s,end_s,expected", _QUIET_CASES)
def test_in_quiet_hours_table(current, start_s, end_s, expected):
    start = service.parse_hhmm(start_s)
    end = service.parse_hhmm(end_s)
    assert service.in_quiet_hours(current, start, end) == expected


def test_in_quiet_hours_equal_start_end_is_false():
    t = service.parse_hhmm("10:00")
    assert service.in_quiet_hours(time(10, 0), t, t) is False


def test_parse_hhmm_valid():
    assert service.parse_hhmm("07:30") == time(7, 30)
    assert service.parse_hhmm("00:00") == time(0, 0)
    assert service.parse_hhmm("23:59") == time(23, 59)


def test_parse_hhmm_none_or_empty():
    assert service.parse_hhmm(None) is None
    assert service.parse_hhmm("") is None


def test_queue_key_format():
    assert service.queue_key("telegram") == "notifications:queue:telegram"
    assert service.queue_key("email") == "notifications:queue:email"


# ---------------------------------------------------------------------------
# 2. service — Redis-backed (fake_redis fixture)
# ---------------------------------------------------------------------------


async def test_publish_notification_lpushes_jobs(fake_redis):
    await service.publish_notification(fake_redis, "u1", "telegram", "test_ping")
    await service.publish_notification(fake_redis, "u1", "telegram", "weekly_digest")

    assert await fake_redis.llen("notifications:queue:telegram") == 2


async def test_publish_notification_job_round_trips(fake_redis):
    job = await service.publish_notification(
        fake_redis, "u2", "telegram", "mf_label_change",
        data={"scheme_name": "Acme", "prior_label": "on_track", "new_label": "off_track"},
        priority="high",
    )
    raw = await fake_redis.lindex("notifications:queue:telegram", 0)
    parsed = NotificationJob.model_validate_json(raw)

    assert parsed.user_id == "u2"
    assert parsed.channel == "telegram"
    assert parsed.template_id == "mf_label_change"
    assert parsed.priority == "high"
    assert parsed.data["scheme_name"] == "Acme"
    # The returned job should have the same content.
    assert job.user_id == parsed.user_id


async def test_rate_cap_telegram(fake_redis):
    """Telegram cap is 3: reached() False until 3rd increment, True after."""
    uid = "rate_user"
    assert await service.rate_cap_reached(fake_redis, uid, "telegram") is False

    for _ in range(3):
        await service.rate_cap_increment(fake_redis, uid, "telegram")

    assert await service.rate_cap_reached(fake_redis, uid, "telegram") is True


async def test_rate_cap_email(fake_redis):
    """Email cap is 1: reached() True after a single increment."""
    uid = "email_user"
    assert await service.rate_cap_reached(fake_redis, uid, "email") is False

    await service.rate_cap_increment(fake_redis, uid, "email")

    assert await service.rate_cap_reached(fake_redis, uid, "email") is True


async def test_rate_cap_unknown_channel_never_reached(fake_redis):
    """Unknown channel has no cap entry → always False."""
    assert await service.rate_cap_reached(fake_redis, "u", "sms") is False


# ---------------------------------------------------------------------------
# 3. channels — _classify_status (pure)
# ---------------------------------------------------------------------------

_STATUS_CASES = [
    (200, True,  False, "ok"),
    (201, True,  False, "ok"),
    (204, True,  False, "ok"),
    (429, False, True,  "http_429"),
    (500, False, True,  "http_500"),
    (503, False, True,  "http_503"),
    (400, False, False, "http_400"),
    (404, False, False, "http_404"),
    (403, False, False, "http_403"),
]


@pytest.mark.parametrize("code,ok,transient,code_str", _STATUS_CASES)
def test_classify_status_table(code, ok, transient, code_str):
    got_ok, got_transient, got_code_str = channels._classify_status(code)
    assert (got_ok, got_transient, got_code_str) == (ok, transient, code_str)


# ---------------------------------------------------------------------------
# 3. channels — fake HTTP client helpers
# ---------------------------------------------------------------------------

class _Resp:
    def __init__(self, sc: int) -> None:
        self.status_code = sc


class _FakeClient:
    def __init__(self, sc: int) -> None:
        self.sc = sc
        self.calls = 0
        self.last: tuple | None = None

    async def post(self, url: str, **kw) -> _Resp:
        self.calls += 1
        self.last = (url, kw)
        return _Resp(self.sc)


class _TimeoutClient:
    """Client that always raises TimeoutException."""
    async def post(self, url: str, **kw) -> _Resp:
        raise httpx.TimeoutException("timed out")


# ---------------------------------------------------------------------------
# 3. channels — deliver_telegram
# ---------------------------------------------------------------------------


async def test_deliver_telegram_200_ok(monkeypatch):
    monkeypatch.setattr(channels.settings, "TELEGRAM_BOT_TOKEN", "tok123")
    client = _FakeClient(200)
    result = await channels.deliver_telegram("123", "hello", client=client)

    assert result.ok is True
    assert client.calls == 1
    url, kw = client.last
    assert "/bot" in url
    assert "/sendMessage" in url
    assert kw["json"]["parse_mode"] == "HTML"
    assert kw["json"]["chat_id"] == "123"


async def test_deliver_telegram_400_permanent(monkeypatch):
    monkeypatch.setattr(channels.settings, "TELEGRAM_BOT_TOKEN", "tok123")
    result = await channels.deliver_telegram("123", "hi", client=_FakeClient(400))
    assert result.ok is False
    assert result.transient is False


async def test_deliver_telegram_500_transient(monkeypatch):
    monkeypatch.setattr(channels.settings, "TELEGRAM_BOT_TOKEN", "tok123")
    result = await channels.deliver_telegram("123", "hi", client=_FakeClient(500))
    assert result.ok is False
    assert result.transient is True


async def test_deliver_telegram_not_configured_no_client_call(monkeypatch):
    monkeypatch.setattr(channels.settings, "TELEGRAM_BOT_TOKEN", "")
    client = _FakeClient(200)
    result = await channels.deliver_telegram("123", "hi", client=client)
    assert result.code == "telegram_not_configured"
    assert client.calls == 0  # client must not be called when disabled


async def test_deliver_telegram_empty_chat_id(monkeypatch):
    monkeypatch.setattr(channels.settings, "TELEGRAM_BOT_TOKEN", "tok123")
    result = await channels.deliver_telegram("", "hi", client=_FakeClient(200))
    assert result.code == "no_chat_id"
    assert result.ok is False


async def test_deliver_telegram_transport_error(monkeypatch):
    monkeypatch.setattr(channels.settings, "TELEGRAM_BOT_TOKEN", "tok123")
    result = await channels.deliver_telegram("123", "hi", client=_TimeoutClient())
    assert result.ok is False
    assert result.transient is True
    assert result.code == "transport_error"


# ---------------------------------------------------------------------------
# 3. channels — deliver_email
# ---------------------------------------------------------------------------


async def test_deliver_email_202_ok(monkeypatch):
    monkeypatch.setattr(channels.settings, "RESEND_API_KEY", "re_x")
    client = _FakeClient(202)
    result = await channels.deliver_email(
        "user@example.com", "Subject", "<p>body</p>", "body", client=client
    )
    assert result.ok is True
    assert client.calls == 1
    _, kw = client.last
    headers = kw["headers"]
    assert "User-Agent" in headers, "User-Agent header missing (Cloudflare 1010 guard)"
    assert "Authorization" in headers, "Authorization header missing"


async def test_deliver_email_not_configured_no_client_call(monkeypatch):
    monkeypatch.setattr(channels.settings, "RESEND_API_KEY", "")
    client = _FakeClient(202)
    result = await channels.deliver_email(
        "user@example.com", "Subject", "<p>body</p>", "body", client=client
    )
    assert result.code == "email_not_configured"
    assert client.calls == 0


async def test_deliver_email_empty_recipient(monkeypatch):
    monkeypatch.setattr(channels.settings, "RESEND_API_KEY", "re_x")
    result = await channels.deliver_email(
        "", "Subject", "<p>body</p>", "body", client=_FakeClient(202)
    )
    assert result.code == "no_recipient"
    assert result.ok is False


async def test_deliver_email_transport_error(monkeypatch):
    monkeypatch.setattr(channels.settings, "RESEND_API_KEY", "re_x")
    result = await channels.deliver_email(
        "user@example.com", "Subject", "<p>body</p>", "body", client=_TimeoutClient()
    )
    assert result.ok is False
    assert result.transient is True
    assert result.code == "transport_error"


# ---------------------------------------------------------------------------
# 4. sharecard
# ---------------------------------------------------------------------------

from dhanradar.notifications import sharecard  # noqa: E402  (after channels imports)


def _patch_storage(monkeypatch, public_url: str | None = "https://cdn/x.png"):
    monkeypatch.setattr(sharecard.storage, "put_object", lambda *a, **k: None)
    monkeypatch.setattr(sharecard.storage, "public_url", lambda key: public_url)
    monkeypatch.setattr(
        sharecard.storage, "presigned_url", lambda key, exp=3600: "https://signed/x.png?sig=1"
    )


async def test_generate_share_card_public_template_returns_cdn_url(monkeypatch):
    _patch_storage(monkeypatch)
    url = await sharecard.generate_share_card("mood", {"title": "Market Mood", "label": "on_track"})
    assert url == "https://cdn/x.png"


async def test_generate_share_card_private_template_returns_presigned(monkeypatch):
    _patch_storage(monkeypatch)
    url = await sharecard.generate_share_card("portfolio", {"title": "My Portfolio"})
    assert url == "https://signed/x.png?sig=1"


async def test_generate_share_card_public_url_none_falls_back_to_presigned(monkeypatch):
    """If public_url returns None the code must fall back to presigned_url."""
    _patch_storage(monkeypatch, public_url=None)
    url = await sharecard.generate_share_card("mood", {"title": "t", "label": "on_track"})
    assert url == "https://signed/x.png?sig=1"


async def test_generate_share_card_caches_url(monkeypatch, fake_redis):
    """After the first call the URL must be stored in Redis under the expected key."""
    _patch_storage(monkeypatch)
    data = {"title": "Market Mood", "label": "on_track"}
    url = await sharecard.generate_share_card("mood", data, redis=fake_redis)
    assert url == "https://cdn/x.png"

    h = sharecard._card_hash("mood", data)
    cache_key = f"notif:share_card:mood:{h}"
    cached = await fake_redis.get(cache_key)
    assert cached == "https://cdn/x.png"


async def test_generate_share_card_second_call_returns_cached(monkeypatch, fake_redis):
    """A second call with the same args must return the cached URL without
    calling put_object again."""
    put_calls = []

    def _put(key, data, content_type=None):
        put_calls.append(key)

    monkeypatch.setattr(sharecard.storage, "put_object", _put)
    monkeypatch.setattr(sharecard.storage, "public_url", lambda key: "https://cdn/x.png")
    monkeypatch.setattr(
        sharecard.storage, "presigned_url", lambda key, exp=3600: "https://signed/x.png?sig=1"
    )

    data = {"title": "Mood", "label": "on_track"}
    await sharecard.generate_share_card("mood", data, redis=fake_redis)
    first_put_count = len(put_calls)

    url2 = await sharecard.generate_share_card("mood", data, redis=fake_redis)
    assert url2 == "https://cdn/x.png"
    assert len(put_calls) == first_put_count, "put_object called again on a cached card"


def test_render_png_returns_png_bytes():
    pytest.importorskip("PIL")  # skip cleanly if Pillow is absent
    png = sharecard._render_png("mood", {"title": "t", "label": "on_track", "subtitle": "s"})
    assert isinstance(png, bytes)
    assert png[:4] == b"\x89PNG", "expected PNG magic bytes"
