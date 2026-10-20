"""Persistent detector, bounded telemetry history and source evidence."""

from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("incidents", sa.Column("open_key", sa.String(160), nullable=True))
    op.add_column(
        "incidents",
        sa.Column("severity", sa.String(16), nullable=False, server_default="warning"),
    )
    op.add_column(
        "incidents",
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
    )
    op.create_index("uq_incidents_open_key", "incidents", ["open_key"], unique=True)
    op.create_table(
        "detection_states",
        sa.Column("id", sa.String(160), primary_key=True),
        sa.Column("consecutive", sa.Integer(), nullable=False),
    )
    op.create_table(
        "telemetry_samples",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "service_id", sa.String(64), sa.ForeignKey("services.id"), nullable=False
        ),
        sa.Column("data", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_telemetry_created", "telemetry_samples", ["created_at"])
    op.create_table(
        "evidence",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "incident_id", sa.String(36), sa.ForeignKey("incidents.id"), nullable=False
        ),
        sa.Column("source", sa.String(240), nullable=False),
        sa.Column("kind", sa.String(40), nullable=False),
        sa.Column("data", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_evidence_incident", "evidence", ["incident_id"])


def downgrade():
    op.drop_table("evidence")
    op.drop_table("telemetry_samples")
    op.drop_table("detection_states")
    op.drop_index("uq_incidents_open_key", table_name="incidents")
    op.drop_column("incidents", "version")
    op.drop_column("incidents", "severity")
    op.drop_column("incidents", "open_key")
