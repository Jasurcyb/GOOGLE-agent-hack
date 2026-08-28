"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-08-01
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto"')

    op.create_table(
        "pull_requests",
        sa.Column("id", sa.UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("github_installation_id", sa.String(64), nullable=False),
        sa.Column("repository_full_name", sa.String(256), nullable=False),
        sa.Column("pr_number", sa.Integer, nullable=False),
        sa.Column("head_sha", sa.String(40), nullable=False),
        sa.Column("base_sha", sa.String(40), nullable=False),
        sa.Column("author_login", sa.String(128), nullable=False),
        sa.Column("state", sa.String(16), nullable=False, server_default="open"),
        sa.UniqueConstraint("repository_full_name", "pr_number", "head_sha", name="uq_pr_repo_num_sha"),
    )

    op.create_table(
        "analysis_runs",
        sa.Column("id", sa.UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("pr_id", sa.UUID, sa.ForeignKey("pull_requests.id"), nullable=False),
        sa.Column("run_key", sa.String(256), nullable=False, unique=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("trigger", sa.String(32), nullable=False, server_default="webhook"),
        sa.Column("policy_version", sa.String(16), nullable=False, server_default="v1"),
        sa.Column("source_snapshot_uri", sa.String(512)),
        sa.Column("started_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
        sa.Column("completed_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("failure_code", sa.String(64)),
    )
    op.create_index("ix_runs_pr_id", "analysis_runs", ["pr_id"])
    op.create_index("ix_runs_status", "analysis_runs", ["status"])

    op.create_table(
        "symbol_changes",
        sa.Column("id", sa.UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("run_id", sa.UUID, sa.ForeignKey("analysis_runs.id"), nullable=False),
        sa.Column("symbol_id", sa.String(512), nullable=False),
        sa.Column("language", sa.String(32), nullable=False),
        sa.Column("change_type", sa.String(16), nullable=False),
        sa.Column("old_signature", sa.Text),
        sa.Column("new_signature", sa.Text),
        sa.Column("file_path", sa.String(512), nullable=False),
        sa.Column("start_line", sa.Integer, nullable=False),
        sa.Column("end_line", sa.Integer, nullable=False),
        sa.Column("semantic_delta", sa.JSONB, server_default=sa.text("'{}'")),
        sa.Column("analyzer_confidence", sa.Float, server_default="1.0"),
    )
    op.create_index("ix_sc_run_id", "symbol_changes", ["run_id"])

    op.create_table(
        "code_edges",
        sa.Column("run_id", sa.UUID, sa.ForeignKey("analysis_runs.id"), nullable=False),
        sa.Column("from_symbol_id", sa.String(512), nullable=False),
        sa.Column("to_symbol_id", sa.String(512), nullable=False),
        sa.Column("edge_type", sa.String(32), nullable=False),
        sa.Column("resolution", sa.String(16), server_default="exact"),
        sa.Column("confidence", sa.Float, server_default="1.0"),
        sa.UniqueConstraint("run_id", "from_symbol_id", "to_symbol_id", "edge_type", name="uq_code_edge"),
    )

    op.create_table(
        "asset_bindings",
        sa.Column("id", sa.UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("run_id", sa.UUID, sa.ForeignKey("analysis_runs.id"), nullable=False),
        sa.Column("symbol_id", sa.String(512), nullable=False),
        sa.Column("datahub_urn", sa.String(512), nullable=False),
        sa.Column("binding_type", sa.String(16), nullable=False),
        sa.Column("evidence_uri", sa.String(512)),
        sa.Column("confidence", sa.Float, server_default="1.0"),
        sa.Column("is_authoritative", sa.Boolean, server_default="false"),
    )
    op.create_index("ix_ab_run_id", "asset_bindings", ["run_id"])

    op.create_table(
        "impact_nodes",
        sa.Column("id", sa.UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("run_id", sa.UUID, sa.ForeignKey("analysis_runs.id"), nullable=False),
        sa.Column("node_key", sa.String(512), nullable=False),
        sa.Column("node_kind", sa.String(32), nullable=False),
        sa.Column("datahub_urn", sa.String(512)),
        sa.Column("distance", sa.Integer, server_default="0"),
        sa.Column("criticality", sa.Float, server_default="0.0"),
        sa.Column("owners", sa.JSONB, server_default=sa.text("'[]'")),
        sa.Column("evidence", sa.JSONB, server_default=sa.text("'{}'")),
        sa.UniqueConstraint("run_id", "node_key", name="uq_impact_node"),
    )
    op.create_index("ix_in_run_id", "impact_nodes", ["run_id"])

    op.create_table(
        "impact_edges",
        sa.Column("id", sa.UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("run_id", sa.UUID, sa.ForeignKey("analysis_runs.id"), nullable=False),
        sa.Column("from_node", sa.String(512), nullable=False),
        sa.Column("to_node", sa.String(512), nullable=False),
        sa.Column("edge_kind", sa.String(32), nullable=False),
        sa.Column("hop", sa.Integer, nullable=False),
        sa.Column("evidence", sa.JSONB, server_default=sa.text("'{}'")),
    )
    op.create_index("ix_ie_run_from", "impact_edges", ["run_id", "from_node"])
    op.create_index("ix_ie_run_to", "impact_edges", ["run_id", "to_node"])

    op.create_table(
        "risk_assessments",
        sa.Column("id", sa.UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("run_id", sa.UUID, sa.ForeignKey("analysis_runs.id"), nullable=False, unique=True),
        sa.Column("risk_score", sa.Integer, nullable=False),
        sa.Column("risk_level", sa.String(16), nullable=False),
        sa.Column("regression_probability", sa.Float, nullable=False),
        sa.Column("impact_severity", sa.Float, nullable=False),
        sa.Column("confidence", sa.Integer, nullable=False),
        sa.Column("model_version", sa.String(16), server_default="v1"),
        sa.Column("decision", sa.JSONB, server_default=sa.text("'{}'")),
        sa.Column("requires_review", sa.Boolean, server_default="false"),
    )

    op.create_table(
        "risk_factors",
        sa.Column("id", sa.UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("assessment_id", sa.UUID, sa.ForeignKey("risk_assessments.id"), nullable=False),
        sa.Column("factor_code", sa.String(64), nullable=False),
        sa.Column("feature_value", sa.Float, nullable=False),
        sa.Column("points", sa.Float, nullable=False),
        sa.Column("evidence_refs", sa.JSONB, server_default=sa.text("'[]'")),
    )

    op.create_table(
        "recommendations",
        sa.Column("id", sa.UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("assessment_id", sa.UUID, sa.ForeignKey("risk_assessments.id"), nullable=False),
        sa.Column("kind", sa.String(64), nullable=False),
        sa.Column("priority", sa.Integer, server_default="0"),
        sa.Column("title", sa.String(256), nullable=False),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column("target_path", sa.String(512)),
        sa.Column("target_urn", sa.String(512)),
        sa.Column("status", sa.String(32), server_default="proposed"),
        sa.Column("evidence_refs", sa.JSONB, server_default=sa.text("'[]'")),
        sa.Column("approval_required", sa.Boolean, server_default="true"),
    )

    op.create_table(
        "generated_artifacts",
        sa.Column("id", sa.UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("recommendation_id", sa.UUID, sa.ForeignKey("recommendations.id"), nullable=False),
        sa.Column("artifact_type", sa.String(64), nullable=False),
        sa.Column("sha256", sa.String(64)),
        sa.Column("object_uri", sa.String(512)),
        sa.Column("validation", sa.JSONB, server_default=sa.text("'{}'")),
        sa.Column("status", sa.String(32), server_default="pending"),
    )

    op.create_table(
        "llm_invocations",
        sa.Column("id", sa.UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("run_id", sa.UUID, sa.ForeignKey("analysis_runs.id"), nullable=False),
        sa.Column("purpose", sa.String(64), nullable=False),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("model", sa.String(128), nullable=False),
        sa.Column("prompt_template_version", sa.String(16)),
        sa.Column("input_hash", sa.String(64)),
        sa.Column("output_hash", sa.String(64)),
        sa.Column("token_usage", sa.JSONB, server_default=sa.text("'{}'")),
        sa.Column("latency_ms", sa.Integer),
        sa.Column("trace_uri", sa.String(512)),
        sa.Column("redaction_report", sa.JSONB, server_default=sa.text("'{}'")),
    )
    op.create_index("ix_li_run_id", "llm_invocations", ["run_id"])

    op.create_table(
        "deliveries",
        sa.Column("id", sa.UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("run_id", sa.UUID, sa.ForeignKey("analysis_runs.id"), nullable=False),
        sa.Column("destination", sa.String(64), nullable=False),
        sa.Column("idempotency_key", sa.String(256), nullable=False, unique=True),
        sa.Column("external_id", sa.String(256)),
        sa.Column("payload_hash", sa.String(64)),
        sa.Column("status", sa.String(32), server_default="pending"),
        sa.Column("attempt_count", sa.Integer, server_default="0"),
        sa.Column("last_error", sa.Text),
    )

    op.create_table(
        "outbox_events",
        sa.Column("id", sa.UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("aggregate_type", sa.String(64), nullable=False),
        sa.Column("aggregate_id", sa.UUID, nullable=False),
        sa.Column("event_type", sa.String(128), nullable=False),
        sa.Column("schema_version", sa.String(16), server_default="1.0"),
        sa.Column("payload", sa.JSONB, nullable=False),
        sa.Column("occurred_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
        sa.Column("published_at", sa.TIMESTAMP(timezone=True)),
        sa.UniqueConstraint(
            "event_type", "aggregate_id",
            sa.text("(payload->>'event_id')"),
            name="uq_outbox_event",
        ),
    )
    op.create_index("ix_outbox_published", "outbox_events", ["published_at"])


def downgrade() -> None:
    op.drop_table("outbox_events")
    op.drop_table("deliveries")
    op.drop_table("llm_invocations")
    op.drop_table("generated_artifacts")
    op.drop_table("recommendations")
    op.drop_table("risk_factors")
    op.drop_table("risk_assessments")
    op.drop_table("impact_edges")
    op.drop_table("impact_nodes")
    op.drop_table("asset_bindings")
    op.drop_table("code_edges")
    op.drop_table("symbol_changes")
    op.drop_table("analysis_runs")
    op.drop_table("pull_requests")
