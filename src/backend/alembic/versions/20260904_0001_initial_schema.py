"""Esquema inicial do totem de ingressos.

Revision ID: 20260904_0001
Revises:
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260904_0001"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


order_status = sa.Enum("pending", "paid", "expired", "cancelled", name="orderstatus")


def upgrade() -> None:
    op.create_table(
        "movies",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("title", sa.String(160), nullable=False),
        sa.Column("genre", sa.String(100), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=False),
        sa.Column("rating", sa.String(12), nullable=False),
        sa.Column("language", sa.String(30), nullable=False),
        sa.Column("format", sa.String(10), nullable=False),
        sa.Column("color", sa.String(7), nullable=False),
    )
    op.create_table(
        "ticket_types",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("detail", sa.String(200), nullable=False),
        sa.Column("price", sa.Numeric(10, 2), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.CheckConstraint("price >= 0", name="ck_ticket_types_price_nonnegative"),
    )
    op.create_table(
        "products",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("price", sa.Numeric(10, 2), nullable=False),
        sa.Column("category", sa.String(40), nullable=False),
        sa.Column("icon", sa.String(10), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.CheckConstraint("price >= 0", name="ck_products_price_nonnegative"),
    )
    op.create_table(
        "idempotency_records",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("key", sa.String(128), nullable=False),
        sa.Column("method", sa.String(10), nullable=False),
        sa.Column("path", sa.String(300), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("state", sa.String(20), nullable=False),
        sa.Column("response_status", sa.Integer(), nullable=True),
        sa.Column("response_body", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("key", "method", "path", name="uq_idempotency_operation"),
    )
    op.create_index("ix_idempotency_records_key", "idempotency_records", ["key"])
    op.create_table(
        "operation_locks",
        sa.Column("resource", sa.String(200), primary_key=True),
        sa.Column("owner", sa.String(128), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "rate_limit_buckets",
        sa.Column("key", sa.String(300), primary_key=True),
        sa.Column("window_started_at", sa.DateTime(), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False),
        sa.CheckConstraint("count >= 0", name="ck_rate_limit_count_nonnegative"),
    )
    op.create_table(
        "service_circuits",
        sa.Column("service", sa.String(80), primary_key=True),
        sa.Column("state", sa.String(20), nullable=False),
        sa.Column("failures", sa.Integer(), nullable=False),
        sa.Column("opened_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint("failures >= 0", name="ck_service_circuit_failures_nonnegative"),
    )
    op.create_table(
        "showtimes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("movie_id", sa.String(36), sa.ForeignKey("movies.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("starts_at", sa.DateTime(), nullable=False),
        sa.Column("room", sa.String(20), nullable=False),
    )
    op.create_index("ix_showtimes_movie_id", "showtimes", ["movie_id"])
    op.create_index("ix_showtimes_starts_at", "showtimes", ["starts_at"])
    op.create_table(
        "seat_reservations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("showtime_id", sa.String(36), sa.ForeignKey("showtimes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("device_id", sa.String(80), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_seat_reservations_showtime_id", "seat_reservations", ["showtime_id"])
    op.create_index("ix_seat_reservations_device_id", "seat_reservations", ["device_id"])
    op.create_table(
        "orders",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("code", sa.String(12), nullable=False),
        sa.Column("showtime_id", sa.String(36), sa.ForeignKey("showtimes.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("status", order_status, nullable=False),
        sa.Column("customer_kind", sa.String(10), nullable=False),
        sa.Column("customer_value", sa.String(254), nullable=False),
        sa.Column("total", sa.Numeric(10, 2), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("paid_at", sa.DateTime(), nullable=True),
        sa.Column("payment_method", sa.String(12), nullable=True),
        sa.Column("reservation_id", sa.String(36), sa.ForeignKey("seat_reservations.id", ondelete="SET NULL"), nullable=True),
        sa.UniqueConstraint("reservation_id", name="uq_orders_reservation_id"),
    )
    op.create_index("ix_orders_code", "orders", ["code"], unique=True)
    op.create_table(
        "showtime_seats",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("showtime_id", sa.String(36), sa.ForeignKey("showtimes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("code", sa.String(4), nullable=False),
        sa.Column("accessible", sa.Boolean(), nullable=False),
        sa.Column("order_id", sa.String(36), sa.ForeignKey("orders.id", ondelete="SET NULL"), nullable=True),
        sa.Column("reservation_id", sa.String(36), sa.ForeignKey("seat_reservations.id", ondelete="SET NULL"), nullable=True),
        sa.UniqueConstraint("showtime_id", "code", name="uq_showtime_seat_code"),
    )
    op.create_index("ix_showtime_seats_showtime_id", "showtime_seats", ["showtime_id"])
    op.create_index("ix_showtime_seats_order_id", "showtime_seats", ["order_id"])
    op.create_index("ix_showtime_seats_reservation_id", "showtime_seats", ["reservation_id"])
    op.create_table(
        "order_items",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("order_id", sa.String(36), sa.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(12), nullable=False),
        sa.Column("reference_id", sa.String(36), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_price", sa.Numeric(10, 2), nullable=False),
        sa.CheckConstraint("quantity > 0", name="ck_order_items_quantity_positive"),
        sa.CheckConstraint("unit_price >= 0", name="ck_order_items_price_nonnegative"),
    )
    op.create_index("ix_order_items_order_id", "order_items", ["order_id"])


def downgrade() -> None:
    op.drop_table("order_items")
    op.drop_table("showtime_seats")
    op.drop_table("orders")
    op.drop_table("seat_reservations")
    op.drop_table("showtimes")
    op.drop_table("service_circuits")
    op.drop_table("rate_limit_buckets")
    op.drop_table("operation_locks")
    op.drop_table("idempotency_records")
    op.drop_table("products")
    op.drop_table("ticket_types")
    op.drop_table("movies")
    order_status.drop(op.get_bind(), checkfirst=True)

