if __name__ == "__main__":
    from pathlib import Path
    import sys

    import pytest

    test_file = Path(__file__).resolve()
    project_root = test_file.parents[2]
    raise SystemExit(pytest.main([
        "-c", str(project_root / "config" / "pytest.ini"),
        str(test_file),
        *sys.argv[1:],
    ]))


from fastapi.testclient import TestClient

from app.services.customer_data import decrypt_cpf, encrypt_cpf, lookup_hash


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


def test_catalog_order_and_payment_flow(client):
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


def test_cannot_reserve_an_occupied_seat(client):
    showtime_id = client.get("/api/v1/showtimes").json()[0]["id"]
    created = client.post(
        "/api/v1/orders", json=create_payload(showtime_id), headers=headers("occupied-setup-order-01")
    )
    assert created.status_code == 201
    paid = client.post(
        f"/api/v1/orders/{created.json()['id']}/payment",
        json={"method": "pix"},
        headers=headers("occupied-setup-payment-01"),
    )
    assert paid.status_code == 200
    assert paid.json()["status"] == "paid"
    response = client.post("/api/v1/orders", json=create_payload(showtime_id), headers=headers("occupied-test-00001"))
    assert response.json()["erro"]["codigo"] == "ASSENTO_INDISPONIVEL"
    assert response.status_code == 409


def test_ticket_count_must_match_seat_count(client):
    showtime_id = client.get("/api/v1/showtimes").json()[0]["id"]
    payload = create_payload(showtime_id, "A2")
    payload["tickets"][0]["quantity"] = 2
    response = client.post("/api/v1/orders", json=payload, headers=headers("invalid-count-test1"))
    assert response.status_code == 422
    assert set(response.json()["erro"]) == {"codigo", "mensagem", "status", "timestamp", "traceId"}


def test_write_requires_idempotency_key(client):
    showtime_id = client.get("/api/v1/showtimes").json()[0]["id"]
    response = client.post("/api/v1/orders", json=create_payload(showtime_id, "A3"), headers={"X-Device-ID": "totem-test-02"})
    assert response.status_code == 400
    assert response.json()["erro"]["codigo"] == "CHAVE_IDEMPOTENCIA_INVALIDA"


def test_requests_are_not_rate_limited(client):
    for _ in range(125):
        assert client.get("/api/v1/products").status_code == 200


def test_total_is_calculated_from_database_prices(client):
    showtime_id = client.get("/api/v1/showtimes").json()[0]["id"]
    payload = create_payload(showtime_id, "B1")
    payload["total"] = "0.01"
    payload["tickets"][0]["unit_price"] = "0.01"
    response = client.post("/api/v1/orders", json=payload, headers=headers("server-prices-test-01"))
    assert response.status_code == 201
    assert response.json()["total"] == "74.90"


def test_unexpected_error_does_not_expose_secrets():
    from fastapi import FastAPI
    from app.errors import install_error_handlers

    error_app = FastAPI()
    install_error_handlers(error_app)

    @error_app.get("/failure")
    def failure():
        raise RuntimeError("API_KEY=test-secret-do-not-expose")

    response = TestClient(error_app, raise_server_exceptions=False).get("/failure")
    assert response.status_code == 500
    assert "test-secret-do-not-expose" not in response.text
    assert "RuntimeError" not in response.text


def test_seat_is_locked_immediately_and_released_on_cancel(client):
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


def test_reserved_seat_is_converted_to_paid_order(client):
    device_headers = {"Idempotency-Key": "conversion-reserve-01", "X-Device-ID": "conversion-totem"}
    showtime_id = client.get("/api/v1/showtimes").json()[0]["id"]
    reserved = client.post(
        "/api/v1/reservations",
        json={"showtime_id": showtime_id, "seats": ["A6"], "reservation_id": None},
        headers=device_headers,
    )
    assert reserved.status_code == 201

    payload = create_payload(showtime_id, "A6")
    payload["reservation_id"] = reserved.json()["id"]
    created = client.post(
        "/api/v1/orders",
        json=payload,
        headers={"Idempotency-Key": "conversion-order-001", "X-Device-ID": "conversion-totem"},
    )
    assert created.status_code == 201
    paid = client.post(
        f"/api/v1/orders/{created.json()['id']}/payment",
        json={"method": "credit"},
        headers={"Idempotency-Key": "conversion-payment1", "X-Device-ID": "conversion-totem"},
    )
    assert paid.status_code == 200
    seats = client.get(f"/api/v1/showtimes/{showtime_id}/seats").json()
    assert next(seat for seat in seats if seat["code"] == "A6")["status"] == "occupied"


def test_cpf_is_encrypted_and_has_blind_lookup_hash():
    cpf = "52998224725"
    first = encrypt_cpf(cpf)
    second = encrypt_cpf(cpf)
    assert first.startswith("enc:v1:")
    assert cpf not in first
    assert first != second
    assert decrypt_cpf(first) == cpf
    hashed = lookup_hash(cpf)
    assert len(hashed) == 64
    assert all(character in "0123456789abcdef" for character in hashed)
    assert hashed != cpf
    assert lookup_hash(f"  {cpf}  ") == hashed
    assert lookup_hash("11144477735") != hashed
