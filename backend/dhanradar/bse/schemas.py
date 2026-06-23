"""
DhanRadar — BSE Star MF 2.0 webhook schemas.

`WebhookAck` is the response BSE expects on a consumed webhook (API doc §7.3.72):

    { "status": "success", "data": { "id": "YYYYMMDD-XXXXXXXX" }, "messages": [] }

`ParsedEvent` is the normalized view of the decrypted event envelope (all modules
share the `member / request_id / investor / action` shape — webhook doc §5).
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class WebhookAckData(BaseModel):
    id: str  # YYYYMMDD-[A-Za-z0-9]{8}


class WebhookAck(BaseModel):
    """The webhook_ack body. `status="success"` signals app-level consumption;
    BSE treats any HTTP 2xx as delivered (§6.1.2 conv. 15)."""

    status: str = "success"
    data: WebhookAckData
    messages: list[Any] = Field(default_factory=list)


class ParsedEvent(BaseModel):
    """Normalized decrypted BSE webhook event. Only `request_id`, `event_type`
    and `event` are guaranteed; identifier fields are per-module optional."""

    request_id: str
    event_type: str          # action.event_type — UCC / ORDER / SXP / MANDATES / PAYMENT GATEWAY
    event: str               # action.event — e.g. match_pending, ACTIVE, reg
    member_id: str | None = None
    client_code: str | None = None
    at: str | None = None    # action.at (ISO/Go timestamp string, as BSE sends it)
    order_id: str | None = None
    sxp_reg_num: str | None = None
    mandate_id: str | None = None

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> ParsedEvent:
        """Extract the normalized fields from a decrypted BSE webhook payload.

        Tolerant of missing optional keys; raises KeyError/TypeError only if the
        mandatory envelope (request_id + action.event_type + action.event) is absent
        — the router treats that as a malformed (post-verification) payload."""
        action = payload.get("action") or {}
        investor = payload.get("investor") or {}
        member = payload.get("member") or {}
        # request_id is the idempotency key — it MUST be a scalar, never a
        # dict/list (whose str() would become a junk unique key).
        rid = payload["request_id"]
        if not isinstance(rid, (str, int)):
            raise TypeError(f"request_id must be a scalar, got {type(rid).__name__}")
        return cls(
            request_id=str(rid),
            event_type=str(action["event_type"]),
            event=str(action["event"]),
            member_id=(str(member["member_id"]) if member.get("member_id") else None),
            client_code=(str(investor["client_code"]) if investor.get("client_code") else None),
            at=(str(action["at"]) if action.get("at") else None),
            order_id=(str(action["order_id"]) if action.get("order_id") else None),
            sxp_reg_num=(str(action["sxp_reg_num"]) if action.get("sxp_reg_num") else None),
            mandate_id=(str(action["mandate_id"]) if action.get("mandate_id") else None),
        )
