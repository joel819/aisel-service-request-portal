"""add user roles and audit log

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-15
"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    user_role = postgresql.ENUM("admin", "user", name="user_role", create_type=False)
    audit_action = postgresql.ENUM(
        "create", "update", "delete", name="audit_action", create_type=False
    )
    user_role.create(op.get_bind(), checkfirst=True)
    audit_action.create(op.get_bind(), checkfirst=True)

    op.add_column("users", sa.Column("role", user_role, nullable=False, server_default="user"))
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("action", audit_action, nullable=False),
        sa.Column("request_id", sa.Integer(), nullable=False),
        sa.Column("request_reference", sa.String(20), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_column("users", "role")
    for name in ("audit_action", "user_role"):
        postgresql.ENUM(name=name).drop(op.get_bind(), checkfirst=True)
