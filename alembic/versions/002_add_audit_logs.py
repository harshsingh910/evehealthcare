"""Add audit_logs table

Revision ID: 002_add_audit_logs
Revises: 001_initial
Create Date: 2026-09-27
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision: str = "002_add_audit_logs"
down_revision: Union[str, None] = "001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

audit_event_type_enum = sa.Enum(
    "USER_SIGNUP",
    "LOGIN_SUCCESS",
    "LOGIN_FAILURE",
    "SESSION_CREATED",
    "SESSION_REVOKED",
    "BOOKING_CREATED",
    "BOOKING_CANCELLED",
    "PAYMENT_SUCCESS",
    "PAYMENT_FAILED",
    "WEBHOOK_PROCESSED",
    "WEBHOOK_DUPLICATE",
    name="audit_event_type",
)


def upgrade() -> None:
    op.create_table(
        "audit_logs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "actor_user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("event_type", audit_event_type_enum, nullable=False),
        sa.Column("entity_type", sa.String(100), nullable=True),
        sa.Column("entity_id", sa.String(255), nullable=True),
        sa.Column("request_id", sa.String(255), nullable=True),
        sa.Column(
            "metadata",
            sa.JSON().with_variant(JSONB, "postgresql"),
            nullable=True,
        ),

        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_audit_logs_actor_user_id", "audit_logs", ["actor_user_id"])
    op.create_index("ix_audit_logs_event_type", "audit_logs", ["event_type"])
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_audit_logs_created_at", table_name="audit_logs")
    op.drop_index("ix_audit_logs_event_type", table_name="audit_logs")
    op.drop_index("ix_audit_logs_actor_user_id", table_name="audit_logs")
    op.drop_table("audit_logs")
    audit_event_type_enum.drop(op.get_bind(), checkfirst=True)
