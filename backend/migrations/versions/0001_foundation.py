"""Initial service inventory and incident timeline."""

from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "services",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False, unique=True),
    )
    op.create_table(
        "incidents",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "service_id", sa.String(64), sa.ForeignKey("services.id"), nullable=False
        ),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("rule", sa.String(120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_incidents_service_id", "incidents", ["service_id"])
    op.create_table(
        "timeline_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "incident_id", sa.String(36), sa.ForeignKey("incidents.id"), nullable=False
        ),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_timeline_events_incident_id", "timeline_events", ["incident_id"]
    )
    op.bulk_insert(
        sa.table("services", sa.column("id"), sa.column("name")),
        [
            {"id": "checkout", "name": "Demo checkout"},
            {"id": "payment", "name": "Demo payment"},
        ],
    )


def downgrade():
    op.drop_table("timeline_events")
    op.drop_table("incidents")
    op.drop_table("services")
