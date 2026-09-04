from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.database import Base, get_db
from app.main import app
from app.seed import seed_database
from app.services.customer_data import decrypt_cpf, encrypt_cpf, lookup_hash


engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSession = sessionmaker(bind=engine, expire_on_commit=False)
Base.metadata.create_all(engine)
with TestingSession() as session:
    seed_database(session)


def override_db():
    with TestingSession() as session:
        yield session


app.dependency_overrides[get_db] = override_db
app.state.session_factory = TestingSession
client = TestClient(app)


def headers(key: str) -> dict[str, str]:
    return {"Idempotency-Key": key, "X-Device-ID": "totem-test-01"}


def create_payload(showtime_id: str, seat: str = "A1") -> dict:
    return {
        "showtime_id": showtime_id,
        "seats": [seat],
        "tickets": [{"id": "full", "quantity": 1}],
        "products": [{"id": "p1", "quantity": 1}],
        "customer": {"kind": "email", "value": "cliente@gmail.com"},
    }


def test_catalog_order_and_payment_flow():
    showtimes = client.get("/api/v1/showtimes").json()
    assert showtimes
    showtime_id = showtimes[0]["id"]
    assert len(client.get(f"/api/v1/showtimes/{showtime_id}/seats").json()) == 80

    created = client.post("/api/v1/orders", json=create_payload(showtime_id), headers=headers("order-flow-test-0001"))
    assert created.status_code == 201
    assert created.json()["total"] == "74.90"

    replay = client.post("/api/v1/orders", json=create_payload(showtime_id), headers=headers("order-flow-test-0001"))
    assert replay.status_code == 201
    assert replay.json()["id"] == created.json()["id"]
    assert replay.headers["Idempotency-Replayed"] == "true"

    order_id = created.json()["id"]
    paid = client.post(f"/api/v1/orders/{order_id}/payment", json={"method": "pix"}, headers=headers("payment-flow-test-01"))
    assert paid.status_code == 200
    assert paid.json()["status"] == "paid"


def test_cannot_reserve_an_occupied_seat():
    showtime_id = client.get("/api/v1/showtimes").json()[0]["id"]
    response = client.post("/api/v1/orders", json=create_payload(showtime_id), headers=headers("occupied-test-00001"))
    assert response.status_code == 409


def test_ticket_count_must_match_seat_count():
    showtime_id = client.get("/api/v1/showtimes").json()[0]["id"]
    payload = create_payload(showtime_id, "A2")
    payload["tickets"][0]["quantity"] = 2
    response = client.post("/api/v1/orders", json=payload, headers=headers("invalid-count-test1"))
    assert response.status_code == 422
    assert set(response.json()["erro"]) == {"codigo", "mensagem", "status", "timestamp", "traceId"}


def test_write_requires_idempotency_key():
    showtime_id = client.get("/api/v1/showtimes").json()[0]["id"]
    response = client.post("/api/v1/orders", json=create_payload(showtime_id, "A3"), headers={"X-Device-ID": "totem-test-02"})
    assert response.status_code == 400
    assert response.json()["erro"]["codigo"] == "CHAVE_IDEMPOTENCIA_INVALIDA"


def test_sensitive_endpoint_is_rate_limited():
    showtime_id = client.get("/api/v1/showtimes").json()[0]["id"]
    response = client.post("/api/v1/orders", json=create_payload(showtime_id, "A4"), headers=headers("rate-limit-test-001"))
    assert response.status_code == 429
    assert response.json()["erro"]["codigo"] == "LIMITE_REQUISICOES_EXCEDIDO"
    assert int(response.headers["Retry-After"]) > 0


def test_seat_is_locked_immediately_and_released_on_cancel():
    showtime_id = client.get("/api/v1/showtimes").json()[0]["id"]
    payload = {"showtime_id": showtime_id, "seats": ["A5"], "reservation_id": None}
    first = client.post("/api/v1/reservations", json=payload, headers=headers("reservation-test-001"))
    assert first.status_code == 201

    second = client.post(
        "/api/v1/reservations",
        json=payload,
        headers={"Idempotency-Key": "reservation-test-002", "X-Device-ID": "another-totem"},
    )
    assert second.status_code == 409
    seats = client.get(f"/api/v1/showtimes/{showtime_id}/seats").json()
    assert next(seat for seat in seats if seat["code"] == "A5")["status"] == "reserved"

    reservation_id = first.json()["id"]
    cancelled = client.post(
        f"/api/v1/reservations/{reservation_id}/cancel",
        json={},
        headers=headers("reservation-cancel-01"),
    )
    assert cancelled.status_code == 200
    seats = client.get(f"/api/v1/showtimes/{showtime_id}/seats").json()
    assert next(seat for seat in seats if seat["code"] == "A5")["status"] == "available"


def test_reserved_seat_is_converted_to_paid_order():
    other_client = TestClient(app, client=("conversion-client", 50000))
    device_headers = {"Idempotency-Key": "conversion-reserve-01", "X-Device-ID": "conversion-totem"}
    showtime_id = other_client.get("/api/v1/showtimes").json()[0]["id"]
    reserved = other_client.post(
        "/api/v1/reservations",
        json={"showtime_id": showtime_id, "seats": ["A6"], "reservation_id": None},
        headers=device_headers,
    )
    assert reserved.status_code == 201

    payload = create_payload(showtime_id, "A6")
    payload["reservation_id"] = reserved.json()["id"]
    created = other_client.post(
        "/api/v1/orders",
        json=payload,
        headers={"Idempotency-Key": "conversion-order-001", "X-Device-ID": "conversion-totem"},
    )
    assert created.status_code == 201
    paid = other_client.post(
        f"/api/v1/orders/{created.json()['id']}/payment",
        json={"method": "credit"},
        headers={"Idempotency-Key": "conversion-payment1", "X-Device-ID": "conversion-totem"},
    )
    assert paid.status_code == 200
    seats = other_client.get(f"/api/v1/showtimes/{showtime_id}/seats").json()
    assert next(seat for seat in seats if seat["code"] == "A6")["status"] == "occupied"


def test_cpf_is_encrypted_and_has_blind_lookup_hash():
    cpf = "52998224725"
    first = encrypt_cpf(cpf)
    second = encrypt_cpf(cpf)
    assert first.startswith("enc:v1:")
    assert cpf not in first
    assert first != second
    assert decrypt_cpf(first) == cpf
    assert lookup_hash(cpf) == lookup_hash(cpf)
