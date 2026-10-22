"""create users and service_requests

Revision ID: 0001
Revises:
Create Date: 2026-10-15
"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

SERVICE_TYPES = (
    "website_digital_presence",
    "business_automation",
    "cloud_infrastructure",
    "devops_observability",
    "ai_automation",
)
PRIORITIES = ("low", "medium", "high", "critical")
STATUSES = ("new", "in_review", "in_progress", "completed", "cancelled")


def upgrade() -> None:
    service_type = postgresql.ENUM(*SERVICE_TYPES, name="service_type", create_type=False)
    priority = postgresql.ENUM(*PRIORITIES, name="request_priority", create_type=False)
    status = postgresql.ENUM(*STATUSES, name="request_status", create_type=False)
    for enum_type in (service_type, priority, status):
        enum_type.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(320), nullable=False, unique=True),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(200)),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_table(
        "service_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "reference",
            sa.String(20),
            sa.Computed("'SR-' || lpad(id::text, 5, '0')", persisted=True),
            nullable=False,
            unique=True,
        ),
        sa.Column("client_name", sa.String(200), nullable=False),
        sa.Column("contact_name", sa.String(200), nullable=False),
        sa.Column("service_type", service_type, nullable=False),
        sa.Column("priority", priority, nullable=False, server_default="medium"),
        sa.Column("status", status, nullable=False, server_default="new"),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint("char_length(client_name) BETWEEN 2 AND 200", name="ck_client_name_len"),
        sa.CheckConstraint(
            "char_length(contact_name) BETWEEN 2 AND 200", name="ck_contact_name_len"
        ),
        sa.CheckConstraint(
            "char_length(description) BETWEEN 10 AND 5000", name="ck_description_len"
        ),
    )
    op.create_index("ix_service_requests_status", "service_requests", ["status"])
    op.create_index("ix_service_requests_priority", "service_requests", ["priority"])
    op.create_index("ix_service_requests_created_at", "service_requests", ["created_at"])


def downgrade() -> None:
    op.drop_table("service_requests")
    op.drop_table("users")
    for name in ("request_status", "request_priority", "service_type"):
        postgresql.ENUM(name=name).drop(op.get_bind(), checkfirst=True)
