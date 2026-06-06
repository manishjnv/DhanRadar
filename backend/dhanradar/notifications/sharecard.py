"""
DhanRadar — Pillow share-card service (Phase 6, architecture Global §5).

Renders a 1200×630 (OG dimension) PNG and uploads it to R2, returning a URL:
  * PUBLIC cards (mood/badge) → non-expiring public URL when R2_PUBLIC_BASE_URL is
    set, else a presigned URL;
  * PRIVATE cards (portfolio) → always a presigned (expiring) URL.

Compliance: a card may show a verb-LABEL + the disclosure line, NEVER a numeric
score/weight (non-neg #2) and NEVER an advisory verb (non-neg #1). Pillow is
imported lazily so importing this module never requires Pillow; a Pillow failure
falls back to a plain card (architecture: "Pillow crash → fallback static PNG").
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
from typing import Any, Optional

from dhanradar import storage
from dhanradar.notifications.templates import LABEL_DISPLAY
from dhanradar.scoring.engine.schemas import DISCLOSURE_BUNDLE, NOT_ADVICE

logger = logging.getLogger(__name__)

_W, _H = 1200, 630
_BG = (250, 248, 245)        # warm off-white (brand)
_FG = (28, 25, 23)           # warm near-black
_MUTED = (107, 107, 107)
_CARD_PREFIX = "share-cards/"
_CACHE_PREFIX = "notif:share_card:"
_CACHE_TTL = 3600

# Public card templates get a non-expiring URL; everything else is private/signed.
_PUBLIC_TEMPLATES = {"mood", "badge", "fund_label"}


class ShareCardError(RuntimeError):
    pass


def _card_hash(template: str, data: dict) -> str:
    raw = template + "|" + "|".join(f"{k}={data[k]}" for k in sorted(data))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _render_png(template: str, data: dict) -> bytes:
    """Render the card to PNG bytes. Label-only, no numerics. Falls back to a plain
    card on any drawing error so a render glitch never blocks delivery."""
    from io import BytesIO

    from PIL import Image, ImageDraw  # lazy — only needed at render time

    img = Image.new("RGB", (_W, _H), _BG)
    draw = ImageDraw.Draw(img)
    try:
        title = str(data.get("title", "DhanRadar"))
        label_word = LABEL_DISPLAY.get(str(data.get("label", "")), "")
        subtitle = str(data.get("subtitle", ""))

        draw.text((64, 80), title[:48], fill=_FG)
        if label_word:
            draw.text((64, 200), label_word, fill=_FG)
        if subtitle:
            draw.text((64, 300), subtitle[:80], fill=_MUTED)
        # Mandatory disclosure surface (non-neg #9) — always on the card.
        draw.text((64, _H - 90), f"{DISCLOSURE_BUNDLE} [{NOT_ADVICE}]"[:140], fill=_MUTED)
    except Exception:  # noqa: BLE001 — fall back to a minimal card, still disclosed
        logger.exception("share-card draw failed; using fallback for template=%s", template)
        img = Image.new("RGB", (_W, _H), _BG)
        ImageDraw.Draw(img).text((64, 80), f"DhanRadar — educational [{NOT_ADVICE}]", fill=_FG)

    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


async def generate_share_card(
    template: str, data: dict, *, redis: Optional[Any] = None
) -> str:
    """Render → upload to R2 → return a URL. Caches the URL in Redis (1h) keyed by
    (template, data hash) when a redis client is provided."""
    h = _card_hash(template, data)
    cache_key = f"{_CACHE_PREFIX}{template}:{h}"
    if redis is not None:
        cached = await redis.get(cache_key)
        if cached:
            return cached

    try:
        png = _render_png(template, data)
    except ImportError as exc:  # Pillow not installed
        raise ShareCardError("pillow_unavailable") from exc

    key = f"{_CARD_PREFIX}{template}/{h}.png"
    # boto3 is synchronous — offload so the R2 upload never blocks the event loop.
    await asyncio.to_thread(storage.put_object, key, png, "image/png")

    if template in _PUBLIC_TEMPLATES:
        url = storage.public_url(key) or storage.presigned_url(key, _CACHE_TTL)
    else:
        url = storage.presigned_url(key, _CACHE_TTL)

    if redis is not None:
        await redis.set(cache_key, url, ex=_CACHE_TTL)
    return url
