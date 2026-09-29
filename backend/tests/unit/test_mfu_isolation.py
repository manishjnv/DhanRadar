"""Module-isolation invariants for the MFU rail (non-neg #7).

(a) No table in schema `mfu` has an FK into another schema, and no table in
    schema `bse` has an FK into `mfu` — MFU/BSE identifiers are each their own.
(b) Every Redis key constant in dhanradar.mfu.client is namespaced `mfu_uat:`.
"""

from __future__ import annotations

import dhanradar.mfu.client as mfu_client

# Import every model module so Base.metadata is fully populated.
import dhanradar.models.bse  # noqa: F401
import dhanradar.models.mfu  # noqa: F401
from dhanradar.models.base import Base


def test_mfu_tables_have_no_cross_schema_fk() -> None:
    for table in Base.metadata.tables.values():
        if table.schema != "mfu":
            continue
        for fk in table.foreign_keys:
            target_schema = fk.column.table.schema
            assert target_schema == "mfu", (
                f"{table.schema}.{table.name} has an FK into schema "
                f"{target_schema!r} (non-neg #7: mfu must not FK out of its own schema)"
            )


def test_bse_tables_have_no_fk_into_mfu() -> None:
    for table in Base.metadata.tables.values():
        if table.schema != "bse":
            continue
        for fk in table.foreign_keys:
            target_schema = fk.column.table.schema
            assert target_schema != "mfu", (
                f"{table.schema}.{table.name} has an FK into schema mfu "
                "(non-neg #7: bse/mfu module isolation)"
            )


def test_mfu_client_redis_keys_are_namespaced() -> None:
    key_constants = [name for name in dir(mfu_client) if name.endswith("_KEY") and name.isupper()]
    assert key_constants, "expected at least one _KEY constant in dhanradar.mfu.client"
    for name in key_constants:
        value = getattr(mfu_client, name)
        assert isinstance(value, str) and value.startswith("mfu_uat:"), (
            f"{name} = {value!r} does not start with 'mfu_uat:' (non-neg #7 namespacing)"
        )
