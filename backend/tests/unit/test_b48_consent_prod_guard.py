"""B48 — production consent-enforcement boot guard (config-level).

These tests pin the mechanism that makes ``ENV=production`` ALWAYS enforce DPDP
consent, regardless of the ``DPDP_CONSENT_ENFORCED`` flag value:

  * ``consent_bypassed`` is True ONLY in an allowlisted dev/test/ci env AND only
    when enforcement is explicitly disabled. Any other env (production / staging
    / preview / unknown / mis-cased) keeps the gate ON.
  * ``model_post_init`` is a fail-closed boot guard: a disabled flag in a
    non-allowlisted env (e.g. a leaked dev ``DPDP_CONSENT_ENFORCED=false`` on a
    prod box) is converted into a hard crash at construction time, not a silent
    consent bypass.

Every ``Settings(...)`` call passes the flag explicitly so the assertions are
hermetic against any ambient ``.env`` / process env.

See: dhanradar/config.py (consent_bypassed, model_post_init,
_CONSENT_BYPASS_ALLOWED_ENVS) and BLOCKERS.md (B48).
"""

from __future__ import annotations

import pytest

from dhanradar.config import Settings


def test_shipped_default_is_enforced():
    """The class default must be enforcement-ON, so the gate is on unless an
    operator explicitly (and legitimately, in a dev env) turns it off."""
    assert Settings.model_fields["DPDP_CONSENT_ENFORCED"].default is True


def test_production_rejects_disabled_flag_at_boot():
    """ENV=production + DPDP_CONSENT_ENFORCED=false → hard boot failure.

    This is the core B48 guarantee: a leaked dev kill-switch can never silently
    disable consent on production — the process refuses to start."""
    with pytest.raises(ValueError, match="not permitted in ENV"):
        Settings(ENV="production", DPDP_CONSENT_ENFORCED=False)


def test_staging_also_rejects_disabled_flag_at_boot():
    """The allowlist is dev/test/ci ONLY — staging is treated like production."""
    with pytest.raises(ValueError, match="not permitted in ENV"):
        Settings(ENV="staging", DPDP_CONSENT_ENFORCED=False)


def test_unknown_env_rejects_disabled_flag_at_boot():
    """An unknown / mis-cased ENV is NOT in the allowlist → fail-closed crash."""
    with pytest.raises(ValueError, match="not permitted in ENV"):
        Settings(ENV="PRODUCTION", DPDP_CONSENT_ENFORCED=False)


def test_production_with_flag_enabled_keeps_gate_enforced():
    """Production with the flag ON: gate enforced, never bypassed."""
    s = Settings(ENV="production", DPDP_CONSENT_ENFORCED=True)
    assert s.consent_bypassed is False


def test_dev_may_legitimately_bypass():
    """The pre-launch kill-switch IS allowed in development (allowlisted)."""
    s = Settings(ENV="development", DPDP_CONSENT_ENFORCED=False)
    assert s.consent_bypassed is True
