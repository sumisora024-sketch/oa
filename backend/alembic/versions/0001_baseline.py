"""Establish the Alembic baseline for the existing OA schema."""

from alembic import op

from app.db import Base
from app import models  # noqa: F401


revision = "0001_baseline"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Existing installations are adopted in place; fresh databases are created
    # from the schema captured by this release.
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    # A baseline downgrade must never drop an adopted production database.
    pass
