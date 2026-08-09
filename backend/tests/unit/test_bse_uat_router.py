"""Unit tests for the BSE UAT order-rail helpers (admin/bse_uat_router.py).

Pure-function coverage only — the HTTP flows were proven live against the UAT
tenant (2026-07-12 run + 2026-08-06 re-verification); these tests pin the
parsing/extraction contracts those flows depend on.
"""

from __future__ import annotations

from dhanradar.admin.bse_uat_router import (
    _extract_order_id,
    _find_url,
    _parse_2fa_page,
)


def test_parse_2fa_page_extracts_jwt_and_unquoted_lids():
    html = (
        '<head><meta name="jwt-token" content="eyJhbGciOi.test.token"></head>'
        '<body><div class="row-checkbox-ucc" data-id=9b13acf2-1111-4222-8333-abcdefabcdef>'
        '<div class="row-checkbox-elog" data-id=059bd4f9-2222-4333-9444-abcdefabcdef>'
    )
    jwt, lids = _parse_2fa_page(html)
    assert jwt == "eyJhbGciOi.test.token"
    assert lids == [
        "9b13acf2-1111-4222-8333-abcdefabcdef",
        "059bd4f9-2222-4333-9444-abcdefabcdef",
    ]


def test_parse_2fa_page_reversed_meta_attrs_and_dedup():
    html = (
        '<meta content="tok.abc.def" name="jwt-token">'
        "<i data-id=11111111-2222-4333-8444-555555555555>"
        "<i data-id=11111111-2222-4333-8444-555555555555>"
    )
    jwt, lids = _parse_2fa_page(html)
    assert jwt == "tok.abc.def"
    assert lids == ["11111111-2222-4333-8444-555555555555"]


def test_parse_2fa_page_missing_returns_none_empty():
    jwt, lids = _parse_2fa_page("<html><body>WAF block page</body></html>")
    assert jwt is None
    assert lids == []


def test_find_url_nested():
    body = {"data": [{"links": {"2fa_url": "https://demo.example/api/s2/2fa_view_object/orders/abc"}}]}
    assert _find_url(body, "2fa_view_object") == "https://demo.example/api/s2/2fa_view_object/orders/abc"
    assert _find_url(body, "pg_view_object") is None


def test_extract_order_id_shapes():
    assert _extract_order_id({"data": {"id": 5001192870}}) == "5001192870"
    assert _extract_order_id({"data": {"orders": [{"order_id": "5001192871"}]}}) == "5001192871"
    assert _extract_order_id({"data": {"orders": [{}]}}) is None
    assert _extract_order_id({"status": "failed"}) is None
    assert _extract_order_id("not a dict") is None
    # the REAL order_new shape observed live 2026-08-07 (wizard first order)
    assert (
        _extract_order_id(
            {"status": "success",
             "data": {"items": [{"mem_ord_ref_id": "1786301538", "id": 5001212827, "status": "success"}]},
             "messages": []}
        )
        == "5001212827"
    )
