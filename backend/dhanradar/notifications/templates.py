"""
DhanRadar — Notification message templates (Phase 6).

THIS is the compliance boundary for delivered copy. Every rendered message:
  * carries the SEBI disclosure bundle + NOT_ADVICE marker (non-neg #9);
  * shows the verb-label as plain educational English, NEVER a numeric score,
    factor weight, or fair value (non-neg #2);
  * uses NO advisory vocabulary (buy/sell/hold/switch/avoid/caution) — labels
    describe category-relative *form*, not an action (non-neg #1).

`render(template_id, data)` returns a `RenderedMessage`. An unknown template_id
raises `UnknownTemplate` so the drain logs a failure and delivers NOTHING — a
missing template must never produce a malformed message (architecture §5 failure
modes: "template missing → no malformed message + alert").
"""

from __future__ import annotations

from dataclasses import dataclass

from dhanradar.scoring.engine.schemas import (
    DISCLAIMER_VERSION,
    DISCLOSURE_BUNDLE,
    NOT_ADVICE,
)

# Educational, action-free phrasing for each engine label. Deliberately avoids the
# rejected advisory verbs; mirrors the public label taxonomy (non-neg #1/#4).
LABEL_DISPLAY: dict[str, str] = {
    "in_form": "In form",
    "on_track": "On track",
    "off_track": "Off track",
    "out_of_form": "Out of form",
    "insufficient_data": "Insufficient data",
}

# Confidence is surfaced only as a band word, never a number (non-neg #2/#4).
BAND_DISPLAY: dict[str, str] = {
    "high": "high confidence",
    "medium": "medium confidence",
    "low": "low confidence",
    "insufficient_data": "insufficient data",
}

# One-line footer appended to every channel (the delivered disclosure surface).
# Carries the in-force DISCLAIMER_VERSION so a delivered label is provably tied to
# the disclosure version recorded in the audit table (non-neg #9 / B26).
_FOOTER_TEXT = f"\n\n— {DISCLOSURE_BUNDLE} [{NOT_ADVICE}] (disclaimer {DISCLAIMER_VERSION})"
_FOOTER_HTML = (
    f'<p style="font-size:12px;color:#6b6b6b;margin-top:16px">'
    f"{DISCLOSURE_BUNDLE} [{NOT_ADVICE}] "
    f'<span style="color:#9a9a9a">(disclaimer {DISCLAIMER_VERSION})</span></p>'
)


class UnknownTemplate(KeyError):
    """Raised when render() is asked for a template_id it does not know."""


@dataclass(frozen=True)
class RenderedMessage:
    subject: str          # email subject (Telegram ignores it)
    text: str             # Telegram body / email plain-text part
    html: str             # email HTML part


def _label_word(data: dict, key: str) -> str:
    return LABEL_DISPLAY.get(str(data.get(key, "")), "Insufficient data")


def _esc(s: object) -> str:
    """Minimal HTML escape for interpolated, possibly user-influenced strings
    (scheme names, user-named portfolios) so they can never inject markup into the email."""
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


# ---------------------------------------------------------------------------
# Individual template renderers — each returns (subject, text, html) WITHOUT the
# footer; render() appends the disclosure footer uniformly so it can never be
# forgotten in a new template.
# ---------------------------------------------------------------------------

def _t_test_ping(data: dict) -> tuple[str, str, str]:
    subject = "DhanRadar — test notification"
    text = (
        "This is a test notification from DhanRadar. "
        "If you received it, your delivery channel is configured correctly."
    )
    html = f"<p>{text}</p>"
    return subject, text, html


def _t_mf_report_ready(data: dict) -> tuple[str, str, str]:
    n = data.get("fund_count")
    count_phrase = f"{int(n)} schemes" if isinstance(n, int) else "your schemes"
    # The `text` part is rendered by Telegram with parse_mode=HTML, so dynamic
    # values must be HTML-escaped there too (not only in the email html part).
    url = _esc(data.get("report_url", ""))
    subject = "Your DhanRadar fund report is ready"
    text = (
        f"Your educational fund report is ready — {count_phrase} analysed with "
        f"category-relative form labels. View it here: {url}"
    )
    link = f'<a href="{url}">View your report</a>' if url else "View it in the app"
    html = (
        f"<p>Your educational fund report is ready — {count_phrase} analysed with "
        f"category-relative form labels.</p><p>{link}</p>"
    )
    return subject, text, html


def _t_mf_label_change(data: dict) -> tuple[str, str, str]:
    scheme = _esc(data.get("scheme_name", "A fund in your portfolio"))
    # portfolio_name is user-supplied → must be escaped in BOTH text (Telegram-HTML)
    # and html parts (RCA: Telegram-HTML injection guard).
    portfolio = _esc(str(data.get("portfolio_name", ""))).strip()
    prior = _label_word(data, "prior_label")
    new = _label_word(data, "new_label")
    where = f" in your “{portfolio}” portfolio" if portfolio else ""
    subject = "A fund's form label changed"
    # `text` is Telegram-HTML-parsed → escape all user-influenced strings.
    text = (
        f"{scheme}{where}: its category-relative form label moved from {prior} to {new}. "
        f"This describes recent relative performance only — it is educational "
        f"context, not an action to take."
    )
    html = (
        f"<p><strong>{scheme}</strong>{where}: its category-relative form label moved from "
        # _esc the label words too (defence-in-depth: LABEL_DISPLAY is plain ASCII
        # today, but escaping keeps the HTML safe if a label is ever localised).
        f"<em>{_esc(prior)}</em> to <em>{_esc(new)}</em>.</p>"
        f"<p>This describes recent relative performance only — educational context, "
        f"not an action to take.</p>"
    )
    return subject, text, html


def _t_weekly_digest(data: dict) -> tuple[str, str, str]:
    subject = "Your DhanRadar weekly digest"
    text = (
        "Here is your weekly educational digest of category-relative form labels "
        "across the funds you track."
    )
    html = f"<p>{text}</p>"
    return subject, text, html


_RENDERERS = {
    "test_ping": _t_test_ping,
    "mf_report_ready": _t_mf_report_ready,
    "mf_label_change": _t_mf_label_change,
    "weekly_digest": _t_weekly_digest,
}


def render(template_id: str, data: dict) -> RenderedMessage:
    """Render a known template with the disclosure footer always appended."""
    fn = _RENDERERS.get(template_id)
    if fn is None:
        raise UnknownTemplate(template_id)
    subject, text, html = fn(data or {})
    return RenderedMessage(
        subject=subject,
        text=text + _FOOTER_TEXT,
        html=html + _FOOTER_HTML,
    )
