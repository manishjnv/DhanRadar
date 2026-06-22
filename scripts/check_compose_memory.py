#!/usr/bin/env python3
"""
DhanRadar — docker-compose memory-budget CI guard.

Fails (exit 1) if the sum of `deploy.resources.limits.memory` across the
DhanRadar services exceeds the architecture §A6 footprint cap (~3 GB on the
KVM4 shared box). Catches a Phase-7-style budget regression in CI instead of
re-auditing by hand.

Only `M`/`G`-suffixed values are summed (the compose uses `M`). The cap is the
stated ~3 GB target; the box has ~6 GB headroom, so this is a budget discipline
gate, not a hard ceiling — raise CAP_MB deliberately (with a note) if the
footprint legitimately grows.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COMPOSE = ROOT / "docker-compose.yml"
# ~3 GB band (architecture §A6). Raised 3072 -> 3200 on 2026-06-20 to absorb the
# celery-mood limit restore 128M -> 192M (#269) — 128M OOM-killed the worker on
# every mood snapshot, so the +64M is a legitimate, OOM-proven footprint growth,
# not creep. Raised 3200 -> 3456 on 2026-06-22 to absorb celery-mood 192M -> 384M
# (#315): activating Upstox added the ~1800-row /option/contract parse + the AI
# commentary path (now ≥7 signals), so a full 11-signal snapshot OOM-killed the
# 192M worker (RCA 2026-06-22). +192M is OOM-proven, founder-approved footprint
# growth. Current footprint 3328M; 3456M keeps a small headroom and stays well
# inside the KVM4 box's ~6 GB. Raise again only deliberately, with a note.
CAP_MB = 3456


def _to_mb(value: str, unit: str) -> int:
    n = int(value)
    return n * 1024 if unit.upper() == "G" else n


def main() -> int:
    if not COMPOSE.exists():
        print(f"compose file not found: {COMPOSE}")
        return 1
    text = COMPOSE.read_text(encoding="utf-8")
    matches = re.findall(r"memory:\s*(\d+)\s*([MG])", text)
    if not matches:
        print("no memory limits found in docker-compose.yml")
        return 1
    total = sum(_to_mb(v, u) for v, u in matches)
    services = len(matches)
    print(f"compose memory: {total}M across {services} services (cap {CAP_MB}M)")
    if total > CAP_MB:
        print(f"COMPOSE MEMORY BUDGET FAILED: {total}M > {CAP_MB}M (§A6 ~3 GB target)")
        return 1
    print("compose memory budget passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
