#!/usr/bin/env python3
"""Fetch NAVI's mutual-fund monthly portfolio disclosure files — LOCAL ONLY.

Why this exists: NAVI's CDN (public-assets.prod.navi-tech.in) 403s every
download from the KVM4 box IP specifically (confirmed twice, 20/20 files),
while a real dev IP reaches the same URLs fine. NAVI is marked
`manual_only` in dhanradar.tasks.mf._AMC_DISCLOSURE_ROOTS (skipped by the
nightly scheduled scraper) — this script is the replacement: run it from a
non-box machine, then ship the downloaded files to the manual-ingest inbox
(`incoming/NAVI/` — the folder channel gives amc_hint="NAVI" for free).

Discovery logic is REPLICATED (not imported) from
dhanradar.tasks.mf._process_amc_nonce_api — importing that module pulls in
the full Celery/Settings/DB stack (dhanradar.config.Settings needs real
POSTGRES_PASSWORD/JWT/Razorpay env vars just to construct), which is the
opposite of what a minimal standalone script needs. Keep the two in sync by
hand if NAVI's nonce/API shape ever changes.

stdlib + httpx only. Never touches the box, Celery, or the DB.

Usage:
    python scripts/fetch_navi_local.py                    # previous month, downloads
    python scripts/fetch_navi_local.py --month 6 --year 2026
    python scripts/fetch_navi_local.py --dry-run           # discovery only, no download
    python scripts/fetch_navi_local.py --out some/dir
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import date
from pathlib import Path

import httpx

NONCE_PAGE_URL = "https://navi.com/mutual-fund/downloads/portfolio"
NONCE_API_URL = "https://navi.com/wp-json/nv/v1/documents"
NONCE_API_CATEGORY = "884"
USER_AGENT = "DhanRadar/1.0 (research; contact@dhanradar.com)"

# Repo root is this script's parent's parent (scripts/ -> repo root).
DEFAULT_OUT_DIR = (
    Path(__file__).resolve().parent.parent / "docs" / "Sample" / "amc-data" / "NAVI"
)


def discover_file_urls(client: httpx.Client, month: int, year: int) -> list[str]:
    """Returns NAVI's reported file URLs for one month — the SAME 2-step
    plain-httpx flow as _process_amc_nonce_api: (1) GET the page, pull the
    wp-nonce out of its plain (no-JS) HTML; (2) POST the real query with
    that nonce as a header."""
    page_resp = client.get(NONCE_PAGE_URL, headers={"User-Agent": USER_AGENT})
    page_resp.raise_for_status()

    nonce_m = re.search(r'"nonce"\s*:\s*"([a-f0-9]+)"', page_resp.text)
    if not nonce_m:
        raise RuntimeError(
            "could not find wp-nonce in NAVI page HTML — site markup may have changed"
        )
    nonce = nonce_m.group(1)

    target = date(year, month, 1)
    financial_year = (
        f"{target.year}-{target.year + 1}"
        if target.month >= 4
        else f"{target.year - 1}-{target.year}"
    )
    api_resp = client.post(
        NONCE_API_URL,
        data={
            "financial_year": financial_year,
            "value": target.strftime("%B"),
            "category": NONCE_API_CATEGORY,
            "type": "Monthly",
            "order": "DESC",
        },
        headers={
            "User-Agent": USER_AGENT,
            "wp-nonce": nonce,
            "X-Requested-With": "XMLHttpRequest",
        },
    )
    api_resp.raise_for_status()
    payload = api_resp.json()
    if not payload.get("success"):
        raise RuntimeError(f"NAVI API returned success=false: {payload}")
    return [d["url"] for d in payload.get("data", []) if d.get("url")]


def download_files(
    client: httpx.Client, urls: list[str], out_dir: Path, referer: str
) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    saved: list[Path] = []
    for url in urls:
        name = url.rsplit("/", 1)[-1].split("?", 1)[0]
        dest = out_dir / name
        if dest.exists():
            print(f"  skip (already present): {name}")
            saved.append(dest)
            continue
        resp = client.get(url, headers={"User-Agent": USER_AGENT, "Referer": referer})
        resp.raise_for_status()
        dest.write_bytes(resp.content)
        saved.append(dest)
        print(f"  saved: {name} ({len(resp.content):,} bytes)")
    return saved


def _previous_month() -> tuple[int, int]:
    today = date.today()
    if today.month == 1:
        return 12, today.year - 1
    return today.month - 1, today.year


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    default_month, default_year = _previous_month()
    parser.add_argument(
        "--month",
        type=int,
        default=default_month,
        help="1-12 (default: previous month)",
    )
    parser.add_argument("--year", type=int, default=default_year)
    parser.add_argument(
        "--out", type=Path, default=DEFAULT_OUT_DIR, help=f"default: {DEFAULT_OUT_DIR}"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="discover file URLs only, skip downloading",
    )
    args = parser.parse_args(argv)

    with httpx.Client(timeout=60.0, follow_redirects=True) as client:
        try:
            urls = discover_file_urls(client, args.month, args.year)
        except Exception as e:  # noqa: BLE001 — top-level CLI error path, print + exit
            print(f"discovery failed: {e}", file=sys.stderr)
            return 1

        print(
            f"NAVI {date(args.year, args.month, 1):%B %Y}: {len(urls)} files discovered"
        )
        for u in urls:
            print(f"  {u}")

        if args.dry_run or not urls:
            return 0

        saved = download_files(client, urls, args.out, referer=NONCE_PAGE_URL)
        print(f"\nsaved {len(saved)} files to {args.out}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
