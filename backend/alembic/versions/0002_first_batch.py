"""Add first-batch contract storage and durable idempotency."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "0002_first_batch"
down_revision = "0001_baseline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())

    if "contracts" in tables:
        columns = {column["name"] for column in inspector.get_columns("contracts")}
        if "pdf_path" not in columns:
            op.add_column("contracts", sa.Column("pdf_path", sa.String(length=1024), nullable=True))

    if "idempotency_records" not in tables:
        op.create_table(
            "idempotency_records",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("actor_key", sa.String(length=128), nullable=False),
            sa.Column("method", sa.String(length=16), nullable=False),
            sa.Column("path", sa.String(length=384), nullable=False),
            sa.Column("idempotency_key", sa.String(length=64), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False),
            sa.Column("status_code", sa.Integer(), nullable=True),
            sa.Column("expires_at", sa.DateTime(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("actor_key", "method", "path", "idempotency_key", name="uq_idempotency_request"),
        )
        op.create_index("ix_idempotency_records_id", "idempotency_records", ["id"], unique=False)
        op.create_index("ix_idempotency_records_actor_key", "idempotency_records", ["actor_key"], unique=False)
        op.create_index("ix_idempotency_records_expires_at", "idempotency_records", ["expires_at"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())
    if "idempotency_records" in tables:
        op.drop_table("idempotency_records")
    if "contracts" in tables:
        columns = {column["name"] for column in inspector.get_columns("contracts")}
        if "pdf_path" in columns:
            op.drop_column("contracts", "pdf_path")
