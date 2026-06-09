"""DhanRadar — Audit ledger package (B57 P2).

Public entry points::

    from dhanradar.audit.service import (
        record_admin_action,
        record_payment_event,
        record_security_event,
    )

Module isolation: this package imports ONLY from
``dhanradar.core.logging``, ``dhanradar.db``, ``dhanradar.models.audit``,
and stdlib.  It MUST NOT import from auth / billing / admin / compliance /
subscriptions.
"""
