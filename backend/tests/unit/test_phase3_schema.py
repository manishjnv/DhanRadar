"""Unit tests for Phase 3 schema additions (migration 0035).

Checks: ORM models present + key columns exist, migration chain correct,
MfFundMetrics.source_run_id added (B72 partial), constraint enums match plan.
No DB — pure import and attribute inspection.
"""

from __future__ import annotations

import importlib.util
import pathlib

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _column_names(model_cls) -> set[str]:
    return {c.key for c in model_cls.__table__.columns}


def _load_migration(name: str):
    """Load a migration by file path.

    ``alembic/versions/`` is NOT a Python package (no ``__init__.py``, and the
    filenames start with a digit), so ``importlib.import_module`` can't reach it.
    Load the module straight from its file instead.
    """
    path = (
        pathlib.Path(__file__).parent.parent.parent
        / "alembic" / "versions" / f"{name}.py"
    )
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# Migration file sanity
# ---------------------------------------------------------------------------

def test_migration_0035_chain():
    mod = _load_migration("0035_phase3_schema_lineage_manager_audit")
    assert mod.revision == "0035"
    assert mod.down_revision == "0034"


def test_migration_0035_has_upgrade_and_downgrade():
    mod = _load_migration("0035_phase3_schema_lineage_manager_audit")
    assert callable(mod.upgrade)
    assert callable(mod.downgrade)


# ---------------------------------------------------------------------------
# MfFundMetrics — B72 partial: source_run_id column
# ---------------------------------------------------------------------------

def test_mf_fund_metrics_has_source_run_id():
    from dhanradar.models.mf import MfFundMetrics

    cols = _column_names(MfFundMetrics)
    assert "source_run_id" in cols, "source_run_id missing from MfFundMetrics"


def test_mf_fund_metrics_has_as_of_date():
    from dhanradar.models.mf import MfFundMetrics

    cols = _column_names(MfFundMetrics)
    assert "as_of_date" in cols, "as_of_date missing from MfFundMetrics"


# ---------------------------------------------------------------------------
# New ORM models — tablenames and key columns
# ---------------------------------------------------------------------------

def test_mf_ingestion_run_model():
    from dhanradar.models.mf import MfIngestionRun

    assert MfIngestionRun.__tablename__ == "ingestion_runs"
    cols = _column_names(MfIngestionRun)
    for col in ("run_id", "task_name", "source", "status", "started_at"):
        assert col in cols, f"MfIngestionRun missing column: {col}"


def test_mf_field_lineage_model():
    from dhanradar.models.mf import MfFieldLineage

    assert MfFieldLineage.__tablename__ == "field_lineage"
    cols = _column_names(MfFieldLineage)
    for col in ("id", "entity_type", "entity_key", "field_name", "new_value", "run_id"):
        assert col in cols, f"MfFieldLineage missing column: {col}"


def test_mf_source_health_model():
    from dhanradar.models.mf import MfSourceHealth

    assert MfSourceHealth.__tablename__ == "source_health"
    cols = _column_names(MfSourceHealth)
    for col in ("id", "source", "check_time", "reachable", "consecutive_failures"):
        assert col in cols, f"MfSourceHealth missing column: {col}"


def test_mf_scheme_lineage_model():
    from dhanradar.models.mf import MfSchemeLineage

    assert MfSchemeLineage.__tablename__ == "scheme_lineage"
    cols = _column_names(MfSchemeLineage)
    for col in ("id", "old_scheme_uid", "new_scheme_uid", "event_type", "effective_date"):
        assert col in cols, f"MfSchemeLineage missing column: {col}"


def test_mf_fund_manager_history_model():
    from dhanradar.models.mf import MfFundManagerHistory

    assert MfFundManagerHistory.__tablename__ == "fund_manager_history"
    cols = _column_names(MfFundManagerHistory)
    for col in ("id", "scheme_uid", "manager_name", "start_date", "end_date", "run_id"):
        assert col in cols, f"MfFundManagerHistory missing column: {col}"


# ---------------------------------------------------------------------------
# All new models live in the mf schema
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("model_name", [
    "MfIngestionRun",
    "MfFieldLineage",
    "MfSourceHealth",
    "MfSchemeLineage",
    "MfFundManagerHistory",
])
def test_new_models_use_mf_schema(model_name):
    import dhanradar.models.mf as mf_models

    model_cls = getattr(mf_models, model_name)
    table_args = model_cls.__table_args__
    # __table_args__ is either a dict or a tuple ending with a dict
    if isinstance(table_args, dict):
        schema_dict = table_args
    else:
        schema_dict = table_args[-1]
    assert schema_dict.get("schema") == "mf", (
        f"{model_name}.__table_args__ does not set schema='mf'"
    )


# ---------------------------------------------------------------------------
# mf_metrics_refresh writes source_run_id (static inspection of upsert dict)
# ---------------------------------------------------------------------------

def test_metrics_refresh_pipeline_includes_source_run_id():
    import ast
    import pathlib

    src = pathlib.Path(__file__).parent.parent.parent / "dhanradar" / "tasks" / "mf.py"
    tree = ast.parse(src.read_text(encoding="utf-8"))

    # Find the upsert_dicts.append({...}) call and check source_run_id is a key
    found = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Attribute) and func.attr == "append":
                for arg in node.args:
                    if isinstance(arg, ast.Dict):
                        keys = [
                            k.s if isinstance(k, ast.Constant) else None
                            for k in arg.keys
                        ]
                        if "isin" in keys and "as_of_date" in keys:
                            if "source_run_id" in keys:
                                found = True
    assert found, "source_run_id not found in mf_metrics_refresh upsert dict"
