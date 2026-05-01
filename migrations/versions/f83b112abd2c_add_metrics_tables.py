"""add metrics tables

Revision ID: f83b112abd2c
Revises: f4fa128de1d0
Create Date: 2026-05-01 12:10:15.988062

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "f83b112abd2c"
down_revision = "f4fa128de1d0"
branch_labels = None
depends_on = None

event_category_enum = postgresql.ENUM(
    "api",
    "domain",
    "ui",
    name="event_category_enum",
    create_type=False,
)


def upgrade():
    # Create the enum type once, idempotent on re-run via checkfirst.
    # ``create_type=False`` on the postgresql.ENUM above prevents implicit
    # CREATE TYPE during op.create_table, which would otherwise duplicate the
    # type and raise DuplicateObject because it does not honor checkfirst.
    bind = op.get_bind()
    event_category_enum.create(bind, checkfirst=True)

    op.create_table(
        "EventRegistry",
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("category", event_category_enum, nullable=False),
        sa.Column("description", sa.String(length=500), nullable=False),
        sa.Column(
            "addedAt",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("name"),
    )
    op.create_table(
        "AnonymousMetrics",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("eventName", sa.String(length=100), nullable=False),
        sa.Column("endpoint", sa.String(length=255), nullable=True),
        sa.Column("method", sa.String(length=10), nullable=True),
        sa.Column("statusCode", sa.Integer(), nullable=True),
        sa.Column("bucketStart", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "dimensions",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("count", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(
            ["eventName"], ["EventRegistry.name"], onupdate="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "bucketStart", "eventName", "dimensions", name="unique_metric_bucket"
        ),
    )


def downgrade():
    op.drop_table(
        "AnonymousMetrics"
    )  # must drop before EventRegistry: FK on EventRegistry.name
    op.drop_table("EventRegistry")  # must drop before the enum type it references
    # Both tables must be gone before the enum type they reference can be dropped
    op.execute("""DROP TYPE event_category_enum""")
