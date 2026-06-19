"""ai_prompt_templates_budget_caps: compliance.prompt_templates + compliance.ai_budget_caps.

Adds two append-only tables to the `compliance` schema (AI governance concern):

  - prompt_templates   : versioned prompt template registry (one active version per key)
  - ai_budget_caps     : append-only admin override history for AI budget caps

NOTE: the prompt_templates registry is not yet consumed by the AI gateway at request
time.  The gateway still accepts prompts from callers.  These tables are the admin CRUD
surface only (Phase 5).  Wiring the gateway to consume active templates is a future
Phase 6 step.

Revision ID: 0039
Revises: 0038
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from alembic import op

revision: str = "0039"
down_revision: str | None = "0038"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # -------------------------------------------------------------------------
    # compliance.prompt_templates
    # -------------------------------------------------------------------------
    op.create_table(
        "prompt_templates",
        sa.Column(
            "id",
            PG_UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("template_key", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("created_by", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "template_key",
            "version",
            name="uq_prompt_templates_key_version",
        ),
        sa.PrimaryKeyConstraint("id"),
        schema="compliance",
    )
    # Partial unique index: at most one active version per template_key.
    # Enforced at the DB level so the admin activate endpoint can rely on it.
    op.create_index(
        "uq_prompt_active_per_key",
        "prompt_templates",
        ["template_key"],
        unique=True,
        schema="compliance",
        postgresql_where=sa.text("is_active"),
    )
    op.create_index(
        "ix_compliance_prompt_templates_key",
        "prompt_templates",
        ["template_key"],
        schema="compliance",
    )

    # -------------------------------------------------------------------------
    # compliance.ai_budget_caps
    # Append-only history.  Effective caps = most-recent row.
    # -------------------------------------------------------------------------
    op.create_table(
        "ai_budget_caps",
        sa.Column(
            "id",
            PG_UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("free_cap", sa.Integer(), nullable=False),
        sa.Column("premium_soft_usd", sa.Numeric(10, 4), nullable=False),
        sa.Column("premium_hard_usd", sa.Numeric(10, 4), nullable=False),
        sa.Column("updated_by", sa.Text(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        schema="compliance",
    )
    op.create_index(
        "ix_compliance_ai_budget_caps_updated_at",
        "ai_budget_caps",
        ["updated_at"],
        schema="compliance",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_compliance_ai_budget_caps_updated_at",
        table_name="ai_budget_caps",
        schema="compliance",
    )
    op.drop_table("ai_budget_caps", schema="compliance")

    op.drop_index(
        "ix_compliance_prompt_templates_key",
        table_name="prompt_templates",
        schema="compliance",
    )
    op.drop_index(
        "uq_prompt_active_per_key",
        table_name="prompt_templates",
        schema="compliance",
    )
    op.drop_table("prompt_templates", schema="compliance")
