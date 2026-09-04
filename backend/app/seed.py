from datetime import date, datetime, time, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Movie, Product, Showtime, ShowtimeSeat, TicketType


MOVIES = [
    ("m1", "Além do Horizonte", "Ficção científica", 138, "12", "Dublado", "2D", "#635bff", ["14:20", "16:50", "19:30", "22:10"]),
    ("m2", "A Última Missão", "Ação • Aventura", 116, "14", "Dublado", "2D", "#e34d59", ["13:40", "17:10", "20:40"]),
    ("m3", "Amigos para Sempre", "Comédia", 102, "Livre", "Nacional", "2D", "#f1a33c", ["12:50", "15:20", "18:00", "21:20"]),
    ("m4", "Reino Encantado", "Animação • Família", 95, "Livre", "Dublado", "3D", "#1db9a7", ["13:10", "15:40", "18:30"]),
]


def seed_database(db: Session) -> None:
    if db.scalar(select(Movie.id).limit(1)):
        return
    for movie_id, title, genre, duration, rating, language, fmt, color, hours in MOVIES:
        db.add(Movie(id=movie_id, title=title, genre=genre, duration_minutes=duration, rating=rating, language=language, format=fmt, color=color))
        for day_offset in range(5):
            session_date = date.today() + timedelta(days=day_offset)
            for hour in hours:
                starts_at = datetime.combine(session_date, time.fromisoformat(hour))
                showtime_id = f"{movie_id}-{session_date:%Y%m%d}-{hour.replace(':', '')}"
                db.add(Showtime(id=showtime_id, movie_id=movie_id, starts_at=starts_at, room="04"))
                for row in "ABCDEFGH":
                    for number in range(1, 11):
                        db.add(ShowtimeSeat(showtime_id=showtime_id, code=f"{row}{number}", accessible=row == "H" and number in (1, 10)))
    db.add_all([
        TicketType(id="full", name="Inteira", detail="Ingresso padrão", price=Decimal("32.00")),
        TicketType(id="half", name="Meia-entrada", detail="Apresente o comprovante na entrada", price=Decimal("16.00")),
        TicketType(id="club", name="Clube do Cinema", detail="Benefício para assinantes", price=Decimal("14.00")),
    ])
    products = [
        ("p1", "Combo Cinema", "Pipoca grande + 2 refrigerantes", "42.90", "Combos", "🍿"),
        ("p2", "Pipoca Caramelo", "Pipoca doce caramelizada grande", "24.90", "Pipocas", "🍿"),
        ("p3", "Refrigerante", "Copo 700 ml • escolha no balcão", "14.50", "Bebidas", "🥤"),
        ("p4", "Nachos Supreme", "Nachos crocantes com cheddar", "21.90", "Destaques", "🧀"),
        ("p5", "Chocolate", "Barra de chocolate ao leite", "9.90", "Doces", "🍫"),
        ("p6", "Combo Duplo", "2 pipocas médias + 2 bebidas", "49.90", "Combos", "🥤"),
    ]
    db.add_all([Product(id=i, name=n, description=d, price=Decimal(p), category=c, icon=icon) for i, n, d, p, c, icon in products])
    db.commit()

