from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum

from sqlalchemy import CheckConstraint, DateTime, Enum as SqlEnum, ForeignKey, JSON, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


def utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class OrderStatus(str, Enum):
    pending = "pending"
    paid = "paid"
    expired = "expired"
    cancelled = "cancelled"


class Movie(Base):
    __tablename__ = "movies"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    title: Mapped[str] = mapped_column(String(160))
    genre: Mapped[str] = mapped_column(String(100))
    duration_minutes: Mapped[int]
    rating: Mapped[str] = mapped_column(String(12))
    language: Mapped[str] = mapped_column(String(30))
    format: Mapped[str] = mapped_column(String(10))
    color: Mapped[str] = mapped_column(String(7), default="#635bff")
    sessions: Mapped[list["Showtime"]] = relationship(back_populates="movie")


class Showtime(Base):
    __tablename__ = "showtimes"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    movie_id: Mapped[str] = mapped_column(ForeignKey("movies.id", ondelete="RESTRICT"), index=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    room: Mapped[str] = mapped_column(String(20))
    movie: Mapped[Movie] = relationship(back_populates="sessions")
    seats: Mapped[list["ShowtimeSeat"]] = relationship(back_populates="showtime")


class ShowtimeSeat(Base):
    __tablename__ = "showtime_seats"
    __table_args__ = (UniqueConstraint("showtime_id", "code", name="uq_showtime_seat_code"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    showtime_id: Mapped[str] = mapped_column(ForeignKey("showtimes.id", ondelete="CASCADE"), index=True)
    code: Mapped[str] = mapped_column(String(4))
    accessible: Mapped[bool] = mapped_column(default=False)
    order_id: Mapped[str | None] = mapped_column(ForeignKey("orders.id", ondelete="SET NULL"), nullable=True, index=True)
    reservation_id: Mapped[str | None] = mapped_column(ForeignKey("seat_reservations.id", ondelete="SET NULL"), nullable=True, index=True)
    showtime: Mapped[Showtime] = relationship(back_populates="seats")


class TicketType(Base):
    __tablename__ = "ticket_types"
    __table_args__ = (CheckConstraint("price >= 0", name="ck_ticket_types_price_nonnegative"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    detail: Mapped[str] = mapped_column(String(200))
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    active: Mapped[bool] = mapped_column(default=True)


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (CheckConstraint("price >= 0", name="ck_products_price_nonnegative"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(Text)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    category: Mapped[str] = mapped_column(String(40))
    icon: Mapped[str] = mapped_column(String(10), default="🍿")
    active: Mapped[bool] = mapped_column(default=True)


class Order(Base):
    __tablename__ = "orders"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    code: Mapped[str] = mapped_column(String(12), unique=True, index=True)
    showtime_id: Mapped[str] = mapped_column(ForeignKey("showtimes.id", ondelete="RESTRICT"))
    status: Mapped[OrderStatus] = mapped_column(SqlEnum(OrderStatus), default=OrderStatus.pending)
    customer_kind: Mapped[str] = mapped_column(String(10))
    customer_value: Mapped[str] = mapped_column(String(254))
    customer_lookup_hash: Mapped[str] = mapped_column(String(64), index=True)
    total: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    expires_at: Mapped[datetime]
    created_at: Mapped[datetime] = mapped_column(default=utc_now)
    paid_at: Mapped[datetime | None] = mapped_column(nullable=True)
    payment_method: Mapped[str | None] = mapped_column(String(12), nullable=True)
    reservation_id: Mapped[str | None] = mapped_column(ForeignKey("seat_reservations.id", ondelete="SET NULL"), nullable=True, unique=True)
    showtime: Mapped[Showtime] = relationship()
    items: Mapped[list["OrderItem"]] = relationship(back_populates="order", cascade="all, delete-orphan")


class OrderItem(Base):
    __tablename__ = "order_items"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_order_items_quantity_positive"),
        CheckConstraint("unit_price >= 0", name="ck_order_items_price_nonnegative"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(12))
    reference_id: Mapped[str] = mapped_column(String(36))
    name: Mapped[str] = mapped_column(String(100))
    quantity: Mapped[int]
    unit_price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    order: Mapped[Order] = relationship(back_populates="items")


class IdempotencyRecord(Base):
    __tablename__ = "idempotency_records"
    __table_args__ = (UniqueConstraint("key", "method", "path", name="uq_idempotency_operation"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(128), index=True)
    method: Mapped[str] = mapped_column(String(10))
    path: Mapped[str] = mapped_column(String(300))
    request_hash: Mapped[str] = mapped_column(String(64))
    state: Mapped[str] = mapped_column(String(20), default="processing")
    response_status: Mapped[int | None] = mapped_column(nullable=True)
    response_body: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=utc_now)
    expires_at: Mapped[datetime]


class OperationLock(Base):
    __tablename__ = "operation_locks"
    resource: Mapped[str] = mapped_column(String(200), primary_key=True)
    owner: Mapped[str] = mapped_column(String(128))
    expires_at: Mapped[datetime]


class RateLimitBucket(Base):
    __tablename__ = "rate_limit_buckets"
    __table_args__ = (CheckConstraint("count >= 0", name="ck_rate_limit_count_nonnegative"),)
    key: Mapped[str] = mapped_column(String(300), primary_key=True)
    window_started_at: Mapped[datetime]
    count: Mapped[int] = mapped_column(default=0)


class ServiceCircuit(Base):
    __tablename__ = "service_circuits"
    __table_args__ = (CheckConstraint("failures >= 0", name="ck_service_circuit_failures_nonnegative"),)
    service: Mapped[str] = mapped_column(String(80), primary_key=True)
    state: Mapped[str] = mapped_column(String(20), default="closed")
    failures: Mapped[int] = mapped_column(default=0)
    opened_at: Mapped[datetime | None] = mapped_column(nullable=True)


class SeatReservation(Base):
    __tablename__ = "seat_reservations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    showtime_id: Mapped[str] = mapped_column(ForeignKey("showtimes.id", ondelete="CASCADE"), index=True)
    device_id: Mapped[str] = mapped_column(String(80), index=True)
    status: Mapped[str] = mapped_column(String(20), default="active")
    expires_at: Mapped[datetime]
    created_at: Mapped[datetime] = mapped_column(default=utc_now)
