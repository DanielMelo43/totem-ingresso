from datetime import date, timedelta

from sqlalchemy import func, select

from app.models import Showtime, ShowtimeSeat
from app import seed


def test_catalog_rolls_forward_without_changing_existing_seats(client, monkeypatch):
    from app import main
    app = main.app

    old_sessions = client.get("/api/v1/showtimes").json()
    old_id = old_sessions[0]["id"]
    with app.state.session_factory() as db:
        seat = db.scalar(select(ShowtimeSeat).where(
            ShowtimeSeat.showtime_id == old_id, ShowtimeSeat.code == "A1"))
        seat.accessible = True
        db.commit()

    future = date.today() + timedelta(days=10)

    class FutureDate(date):
        @classmethod
        def today(cls):
            return future

    monkeypatch.setattr(seed, "date", FutureDate)
    monkeypatch.setattr(main, "date", FutureDate)
    # The same running instance must renew the schedule without a restart.
    response = client.get(f"/api/v1/showtimes?on={future}")
    assert response.status_code == 200
    assert len(response.json()) == 14
    with app.state.session_factory() as db:
        seed.seed_database(db)
        first_count = db.scalar(select(func.count()).select_from(Showtime))
        seed.ensure_upcoming_showtimes(db)
        assert db.scalar(select(func.count()).select_from(Showtime)) == first_count
        assert db.scalar(select(ShowtimeSeat).where(
            ShowtimeSeat.showtime_id == old_id, ShowtimeSeat.code == "A1")).accessible

    for offset in range(5):
        response = client.get(f"/api/v1/showtimes?on={future + timedelta(days=offset)}")
        assert response.status_code == 200
        assert len(response.json()) == 14
        for session in response.json():
            seats = client.get(f"/api/v1/showtimes/{session['id']}/seats").json()
            assert len(seats) == 80
