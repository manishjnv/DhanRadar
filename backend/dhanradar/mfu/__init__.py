"""DhanRadar — MF Utility (MFU) integration: crypto, HTTP client, admin UAT console.

Fully separate from the BSE Star MF rail (module isolation, non-neg #7) — this
package must never import `dhanradar.bse` / `dhanradar.models.bse`, and vice
versa (enforced by scripts/ci_guards.py + tests/unit/test_mfu_isolation.py).
"""

from __future__ import annotations
