from contextlib import asynccontextmanager
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
import logging
from uuid import uuid4

from fastapi import Depends, FastAPI, Header, Query, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, text, update
from sqlalchemy.orm import Session, joinedload

from .config import get_settings
from .database import SessionLocal, get_db
from .errors import AppError, install_error_handlers
from .models import Order, OrderItem, OrderStatus, Product, SeatReservation, ServiceCircuit, Showtime, ShowtimeSeat, TicketType
from .schemas import OrderCreate, OrderOut, PaymentIn, ProductOut, ReservationCreate, ReservationOut, SeatOut, ShowtimeOut, TicketTypeOut
from .security import abandon_idempotency, acquire_lock, begin_idempotency, complete_idempotency, release_lock, security_middleware
from .seed import seed_database
from .services.payment import payment_gateway
from .services.customer_data import protect_customer


settings = get_settings()
logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO), format="%(asctime)s level=%(levelname)s logger=%(name)s message=%(message)s")


def utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


@asynccontextmanager
async def lifespan(_: FastAPI):
    with SessionLocal() as db:
        if settings.database_url.startswith("postgresql"):
            db.execute(text("SELECT pg_advisory_xact_lock(847291)"))
        seed_database(db)
    yield


app = FastAPI(title=settings.app_name, version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=settings.origins, allow_credentials=True, allow_methods=["GET", "POST"], allow_headers=["Content-Type", "Idempotency-Key", "X-Device-ID", "X-Trace-ID"])
app.middleware("http")(security_middleware)
app.state.session_factory = SessionLocal
install_error_handlers(app)


def expire_orders(db: Session) -> None:
    now = utc_now()
    orders = db.scalars(select(Order).where(Order.status == OrderStatus.pending, Order.expires_at <= now)).all()
    for order in orders:
        order.status = OrderStatus.expired
        for seat in db.scalars(select(ShowtimeSeat).where(ShowtimeSeat.order_id == order.id)):
            seat.order_id = None
    if orders:
        db.commit()


def expire_reservations(db: Session) -> None:
    now = utc_now()
    reservations = db.scalars(select(SeatReservation).where(SeatReservation.status == "active", SeatReservation.expires_at <= now)).all()
    for reservation in reservations:
        reservation.status = "expired"
        db.execute(update(ShowtimeSeat).where(ShowtimeSeat.reservation_id == reservation.id).values(reservation_id=None))
    if reservations:
        db.commit()


def order_response(db: Session, order: Order) -> OrderOut:
    seats = list(db.scalars(select(ShowtimeSeat.code).where(ShowtimeSeat.order_id == order.id).order_by(ShowtimeSeat.code)))
    result = OrderOut.model_validate(order, from_attributes=True).model_copy(update={"seats": seats})
    return result


@app.get("/health", tags=["system"])
def health(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        database = "up"
    except Exception:
        database = "down"
    circuit = db.get(ServiceCircuit, payment_gateway.service_name) if database == "up" else None
    gateway = "up" if not circuit or circuit.state != "open" else "degraded"
    result = {"status": "ok" if database == "up" else "unavailable", "dependencies": {"database": database, "payment_gateway": gateway}}
    if database != "up":
        raise AppError(503, "SERVICO_INDISPONIVEL", "Serviço temporariamente indisponível.")
    return result


@app.get("/api/v1/showtimes", response_model=list[ShowtimeOut], tags=["catalog"])
def list_showtimes(on: date = Query(default_factory=date.today), db: Session = Depends(get_db)):
    start = datetime.combine(on, datetime.min.time())
    end = start + timedelta(days=1)
    return db.scalars(select(Showtime).options(joinedload(Showtime.movie)).where(Showtime.starts_at >= start, Showtime.starts_at < end).order_by(Showtime.starts_at)).all()


@app.get("/api/v1/showtimes/{showtime_id}/seats", response_model=list[SeatOut], tags=["catalog"])
def list_seats(showtime_id: str, db: Session = Depends(get_db)):
    if not db.get(Showtime, showtime_id):
        raise AppError(404, "SESSAO_NAO_ENCONTRADA", "Sessão não encontrada.")
    expire_orders(db)
    expire_reservations(db)
    seats = db.scalars(select(ShowtimeSeat).where(ShowtimeSeat.showtime_id == showtime_id).order_by(ShowtimeSeat.code)).all()
    result = []
    for seat in seats:
        seat_status = "available"
        if seat.order_id:
            order = db.get(Order, seat.order_id)
            seat_status = "occupied" if order and order.status == OrderStatus.paid else "reserved"
        elif seat.reservation_id:
            seat_status = "reserved"
        result.append(SeatOut(code=seat.code, accessible=seat.accessible, status=seat_status))
    return result


@app.get("/api/v1/ticket-types", response_model=list[TicketTypeOut], tags=["catalog"])
def list_ticket_types(db: Session = Depends(get_db)):
    return db.scalars(select(TicketType).where(TicketType.active).order_by(TicketType.price.desc())).all()


@app.get("/api/v1/products", response_model=list[ProductOut], tags=["catalog"])
def list_products(category: str | None = Query(None, min_length=1, max_length=40), db: Session = Depends(get_db)):
    query = select(Product).where(Product.active)
    if category:
        query = query.where(Product.category == category)
    return db.scalars(query.order_by(Product.name)).all()


@app.post("/api/v1/reservations", response_model=ReservationOut, status_code=201, tags=["reservations"])
def reserve_seats(request: Request, payload: ReservationCreate, idempotency_key: str | None = Header(None, alias="Idempotency-Key"), device_id: str | None = Header(None, alias="X-Device-ID"), db: Session = Depends(get_db)):
    idem = begin_idempotency(db, idempotency_key, request.method, request.url.path, payload.model_dump(mode="json"))
    if isinstance(idem, JSONResponse):
        return idem
    if not device_id or not 3 <= len(device_id) <= 80:
        abandon_idempotency(db, idem)
        raise AppError(400, "DISPOSITIVO_INVALIDO", "Envie um X-Device-ID válido.")
    expire_reservations(db)
    if not db.get(Showtime, payload.showtime_id):
        abandon_idempotency(db, idem)
        raise AppError(404, "SESSAO_NAO_ENCONTRADA", "Sessão não encontrada.")

    reservation = db.get(SeatReservation, payload.reservation_id) if payload.reservation_id else None
    if payload.reservation_id and (not reservation or reservation.status != "active"):
        abandon_idempotency(db, idem)
        raise AppError(409, "RESERVA_INVALIDA", "A reserva não está mais ativa.")
    if reservation and (reservation.device_id != device_id or reservation.showtime_id != payload.showtime_id):
        abandon_idempotency(db, idem)
        raise AppError(403, "RESERVA_NAO_AUTORIZADA", "Esta reserva pertence a outro terminal.")
    if not reservation:
        reservation = SeatReservation(id=str(uuid4()), showtime_id=payload.showtime_id, device_id=device_id, expires_at=utc_now())
        db.add(reservation)
        db.flush()

    requested = set(payload.seats)
    seats = db.scalars(select(ShowtimeSeat).where(ShowtimeSeat.showtime_id == payload.showtime_id, ShowtimeSeat.code.in_(requested))).all()
    if len(seats) != len(requested):
        db.rollback()
        abandon_idempotency(db, idem)
        raise AppError(422, "ASSENTO_INVALIDO", "Um ou mais assentos são inválidos.")
    for seat in seats:
        if seat.order_id or (seat.reservation_id and seat.reservation_id != reservation.id):
            db.rollback()
            abandon_idempotency(db, idem)
            raise AppError(409, "ASSENTO_INDISPONIVEL", "Um ou mais assentos foram reservados por outro terminal.")
        claimed = db.execute(update(ShowtimeSeat).where(ShowtimeSeat.id == seat.id, ShowtimeSeat.order_id.is_(None), (ShowtimeSeat.reservation_id.is_(None)) | (ShowtimeSeat.reservation_id == reservation.id)).values(reservation_id=reservation.id))
        if claimed.rowcount != 1:
            db.rollback()
            abandon_idempotency(db, idem)
            raise AppError(409, "ASSENTO_INDISPONIVEL", "Um ou mais assentos foram reservados por outro terminal.")
    db.execute(update(ShowtimeSeat).where(ShowtimeSeat.reservation_id == reservation.id, ShowtimeSeat.code.not_in(requested)).values(reservation_id=None))
    reservation.expires_at = utc_now() + timedelta(minutes=settings.reservation_minutes)
    response = ReservationOut(id=reservation.id, showtime_id=reservation.showtime_id, seats=sorted(requested), expires_at=reservation.expires_at).model_dump(mode="json")
    complete_idempotency(idem, 201, response)
    db.commit()
    return JSONResponse(response, status_code=201)


@app.post("/api/v1/reservations/{reservation_id}/cancel", response_model=ReservationOut, tags=["reservations"])
def cancel_reservation(request: Request, reservation_id: str, idempotency_key: str | None = Header(None, alias="Idempotency-Key"), device_id: str | None = Header(None, alias="X-Device-ID"), db: Session = Depends(get_db)):
    idem = begin_idempotency(db, idempotency_key, request.method, request.url.path, {})
    if isinstance(idem, JSONResponse):
        return idem
    reservation = db.get(SeatReservation, reservation_id)
    if not reservation:
        abandon_idempotency(db, idem)
        raise AppError(404, "RESERVA_NAO_ENCONTRADA", "Reserva não encontrada.")
    if reservation.device_id != device_id:
        abandon_idempotency(db, idem)
        raise AppError(403, "RESERVA_NAO_AUTORIZADA", "Esta reserva pertence a outro terminal.")
    if reservation.status == "active":
        db.execute(update(ShowtimeSeat).where(ShowtimeSeat.reservation_id == reservation.id).values(reservation_id=None))
        reservation.status = "cancelled"
    response = ReservationOut(id=reservation.id, showtime_id=reservation.showtime_id, seats=[], expires_at=reservation.expires_at).model_dump(mode="json")
    complete_idempotency(idem, 200, response)
    db.commit()
    return response


@app.post("/api/v1/orders", response_model=OrderOut, status_code=status.HTTP_201_CREATED, tags=["orders"])
def create_order(request: Request, payload: OrderCreate, idempotency_key: str | None = Header(None, alias="Idempotency-Key"), db: Session = Depends(get_db)):
    idem = begin_idempotency(db, idempotency_key, request.method, request.url.path, payload.model_dump(mode="json"))
    if isinstance(idem, JSONResponse):
        return idem
    expire_orders(db)
    expire_reservations(db)
    showtime = db.get(Showtime, payload.showtime_id)
    if not showtime:
        abandon_idempotency(db, idem)
        raise AppError(404, "SESSAO_NAO_ENCONTRADA", "Sessão não encontrada.")
    requested = {code.upper() for code in payload.seats}
    seats = db.scalars(select(ShowtimeSeat).where(ShowtimeSeat.showtime_id == payload.showtime_id, ShowtimeSeat.code.in_(requested))).all()
    if len(seats) != len(requested):
        abandon_idempotency(db, idem)
        raise AppError(422, "ASSENTO_INVALIDO", "Um ou mais assentos são inválidos.")
    reservation = db.get(SeatReservation, payload.reservation_id) if payload.reservation_id else None
    if payload.reservation_id and (not reservation or reservation.status != "active" or reservation.showtime_id != payload.showtime_id):
        abandon_idempotency(db, idem)
        raise AppError(409, "RESERVA_INVALIDA", "A reserva não está mais ativa.")
    if reservation:
        held = set(db.scalars(select(ShowtimeSeat.code).where(ShowtimeSeat.reservation_id == reservation.id)))
        if held != requested:
            abandon_idempotency(db, idem)
            raise AppError(409, "RESERVA_DIVERGENTE", "Os assentos do pedido são diferentes dos reservados.")
    if any(seat.order_id or (seat.reservation_id and (not reservation or seat.reservation_id != reservation.id)) for seat in seats):
        abandon_idempotency(db, idem)
        raise AppError(409, "ASSENTO_INDISPONIVEL", "Um ou mais assentos não estão disponíveis.")

    ticket_ids = [item.id for item in payload.tickets]
    product_ids = [item.id for item in payload.products]
    tickets = {item.id: item for item in db.scalars(select(TicketType).where(TicketType.id.in_(ticket_ids), TicketType.active))}
    products = {item.id: item for item in db.scalars(select(Product).where(Product.id.in_(product_ids), Product.active))} if product_ids else {}
    if len(tickets) != len(ticket_ids) or len(products) != len(product_ids):
        abandon_idempotency(db, idem)
        raise AppError(422, "ITEM_INVALIDO", "Um ou mais itens não existem.")

    customer_value, customer_lookup_hash = protect_customer(payload.customer.kind, payload.customer.value)
    order = Order(id=str(uuid4()), code=uuid4().hex[:8].upper(), showtime_id=showtime.id, customer_kind=payload.customer.kind, customer_value=customer_value, customer_lookup_hash=customer_lookup_hash, total=Decimal("0"), expires_at=utc_now() + timedelta(minutes=settings.reservation_minutes), reservation_id=reservation.id if reservation else None)
    total = Decimal("0")
    for requested_item, source, kind in [*((item, tickets[item.id], "ticket") for item in payload.tickets), *((item, products[item.id], "product") for item in payload.products)]:
        order.items.append(OrderItem(kind=kind, reference_id=source.id, name=source.name, quantity=requested_item.quantity, unit_price=source.price))
        total += source.price * requested_item.quantity
    order.total = total
    db.add(order)
    db.flush()
    for seat in seats:
        seat_filter = ShowtimeSeat.reservation_id == reservation.id if reservation else ShowtimeSeat.reservation_id.is_(None)
        claimed = db.execute(update(ShowtimeSeat).where(ShowtimeSeat.id == seat.id, ShowtimeSeat.order_id.is_(None), seat_filter).values(order_id=order.id, reservation_id=None))
        if claimed.rowcount != 1:
            db.rollback()
            abandon_idempotency(db, idem)
            raise AppError(409, "ASSENTO_INDISPONIVEL", "Um ou mais assentos não estão disponíveis.")
    if reservation:
        reservation.status = "converted"
    try:
        response = order_response(db, order).model_dump(mode="json")
        complete_idempotency(idem, 201, response)
        db.commit()
    except AppError:
        db.rollback()
        abandon_idempotency(db, idem)
        raise
    return JSONResponse(response, status_code=201)


@app.get("/api/v1/orders/{order_id}", response_model=OrderOut, tags=["orders"])
def get_order(order_id: str, db: Session = Depends(get_db)):
    expire_orders(db)
    order = db.execute(select(Order).options(joinedload(Order.items)).where(Order.id == order_id)).unique().scalar_one_or_none()
    if not order:
        raise AppError(404, "PEDIDO_NAO_ENCONTRADO", "Pedido não encontrado.")
    return order_response(db, order)


@app.get("/api/v1/orders/{order_id}/status", tags=["orders"])
def get_order_status(order_id: str, db: Session = Depends(get_db)):
    expire_orders(db)
    order = db.get(Order, order_id)
    if not order:
        raise AppError(404, "PEDIDO_NAO_ENCONTRADO", "Pedido não encontrado.")
    return {"id": order.id, "code": order.code, "status": order.status, "payment_method": order.payment_method, "paid_at": order.paid_at, "expires_at": order.expires_at}


@app.post("/api/v1/orders/{order_id}/payment", response_model=OrderOut, tags=["orders"])
def pay_order(request: Request, order_id: str, payload: PaymentIn, idempotency_key: str | None = Header(None, alias="Idempotency-Key"), db: Session = Depends(get_db)):
    idem = begin_idempotency(db, idempotency_key, request.method, request.url.path, payload.model_dump(mode="json"))
    if isinstance(idem, JSONResponse):
        return idem
    lock = acquire_lock(db, f"payment:{order_id}", idempotency_key or "")
    expire_orders(db)
    order = db.execute(select(Order).options(joinedload(Order.items)).where(Order.id == order_id)).unique().scalar_one_or_none()
    if not order:
        release_lock(db, lock.resource, lock.owner)
        abandon_idempotency(db, idem)
        raise AppError(404, "PEDIDO_NAO_ENCONTRADO", "Pedido não encontrado.")
    if order.status != OrderStatus.pending:
        release_lock(db, lock.resource, lock.owner)
        abandon_idempotency(db, idem)
        db.commit()
        raise AppError(409, "PEDIDO_JA_PROCESSADO", "Este pedido já foi processado anteriormente.")
    payment_gateway.charge(db, order.id, str(order.total), payload.method)
    order.status = OrderStatus.paid
    order.payment_method = payload.method
    order.paid_at = utc_now()
    response = order_response(db, order).model_dump(mode="json")
    complete_idempotency(idem, 200, response)
    release_lock(db, lock.resource, lock.owner)
    db.commit()
    return response


@app.post("/api/v1/orders/{order_id}/cancel", response_model=OrderOut, tags=["orders"])
def cancel_order(request: Request, order_id: str, idempotency_key: str | None = Header(None, alias="Idempotency-Key"), db: Session = Depends(get_db)):
    idem = begin_idempotency(db, idempotency_key, request.method, request.url.path, {})
    if isinstance(idem, JSONResponse):
        return idem
    order = db.execute(select(Order).options(joinedload(Order.items)).where(Order.id == order_id)).unique().scalar_one_or_none()
    if not order:
        abandon_idempotency(db, idem)
        raise AppError(404, "PEDIDO_NAO_ENCONTRADO", "Pedido não encontrado.")
    if order.status != OrderStatus.pending:
        abandon_idempotency(db, idem)
        raise AppError(409, "PEDIDO_JA_PROCESSADO", "Somente pedidos pendentes podem ser cancelados.")
    order.status = OrderStatus.cancelled
    for seat in db.scalars(select(ShowtimeSeat).where(ShowtimeSeat.order_id == order.id)):
        seat.order_id = None
    response = order_response(db, order).model_dump(mode="json")
    complete_idempotency(idem, 200, response)
    db.commit()
    return response
