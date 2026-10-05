"""Add configurable notifications, workflows, and document access policies."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "0003_public_capabilities"
down_revision = "0002_first_batch"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    tables = set(inspect(bind).get_table_names())

    if "notification_rules" not in tables:
        op.create_table(
            "notification_rules",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("event_code", sa.String(length=128), nullable=False),
            sa.Column("display_name", sa.String(length=120), nullable=False),
            sa.Column("enabled", sa.Boolean(), nullable=False),
            sa.Column("channels", sa.JSON(), nullable=False),
            sa.Column("recipient_roles", sa.JSON(), nullable=False),
            sa.Column("recipient_user_ids", sa.JSON(), nullable=False),
            sa.Column("include_related", sa.Boolean(), nullable=False),
            sa.Column("schedule", sa.JSON(), nullable=True),
            sa.Column("updated_by", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["updated_by"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("event_code"),
        )
        op.create_index("ix_notification_rules_id", "notification_rules", ["id"])
        op.create_index("ix_notification_rules_event_code", "notification_rules", ["event_code"])

    if "notifications" not in tables:
        op.create_table(
            "notifications",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("event_key", sa.String(length=64), nullable=False),
            sa.Column("event_code", sa.String(length=128), nullable=False),
            sa.Column("recipient_key", sa.String(length=255), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=True),
            sa.Column("recipient_email", sa.String(length=255), nullable=True),
            sa.Column("title", sa.String(length=255), nullable=False),
            sa.Column("message", sa.Text(), nullable=False),
            sa.Column("link", sa.String(length=512), nullable=True),
            sa.Column("visible_in_app", sa.Boolean(), nullable=False),
            sa.Column("is_read", sa.Boolean(), nullable=False),
            sa.Column("read_at", sa.DateTime(), nullable=True),
            sa.Column("email_status", sa.String(length=32), nullable=False),
            sa.Column("email_attempts", sa.Integer(), nullable=False),
            sa.Column("email_error", sa.Text(), nullable=True),
            sa.Column("emailed_at", sa.DateTime(), nullable=True),
            sa.Column("attributes", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("event_key", "recipient_key", name="uq_notification_event_recipient"),
        )
        op.create_index("ix_notifications_id", "notifications", ["id"])
        op.create_index("ix_notifications_event_key", "notifications", ["event_key"])
        op.create_index("ix_notifications_event_code", "notifications", ["event_code"])
        op.create_index("ix_notifications_user_id", "notifications", ["user_id"])
        op.create_index("ix_notifications_is_read", "notifications", ["is_read"])
        op.create_index("ix_notifications_email_status", "notifications", ["email_status"])
        op.create_index("ix_notifications_created_at", "notifications", ["created_at"])

    if "workflow_definitions" not in tables:
        op.create_table(
            "workflow_definitions",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("workflow_type", sa.String(length=64), nullable=False),
            sa.Column("display_name", sa.String(length=120), nullable=False),
            sa.Column("enabled", sa.Boolean(), nullable=False),
            sa.Column("steps", sa.JSON(), nullable=False),
            sa.Column("version", sa.Integer(), nullable=False),
            sa.Column("updated_by", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["updated_by"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("workflow_type"),
        )
        op.create_index("ix_workflow_definitions_id", "workflow_definitions", ["id"])
        op.create_index("ix_workflow_definitions_workflow_type", "workflow_definitions", ["workflow_type"])

    if "document_access_policies" not in tables:
        op.create_table(
            "document_access_policies",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("document_type", sa.String(length=64), nullable=False),
            sa.Column("display_name", sa.String(length=120), nullable=False),
            sa.Column("allowed_roles", sa.JSON(), nullable=False),
            sa.Column("owner_access", sa.Boolean(), nullable=False),
            sa.Column("related_access", sa.Boolean(), nullable=False),
            sa.Column("updated_by", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["updated_by"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("document_type"),
        )
        op.create_index("ix_document_access_policies_id", "document_access_policies", ["id"])
        op.create_index("ix_document_access_policies_document_type", "document_access_policies", ["document_type"])


def downgrade() -> None:
    bind = op.get_bind()
    tables = set(inspect(bind).get_table_names())
    for table in ["document_access_policies", "workflow_definitions", "notifications", "notification_rules"]:
        if table in tables:
            op.drop_table(table)
