"""Aplica as migrations em um PostgreSQL remoto com trava entre deploys."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

from app.config import get_settings


MIGRATION_LOCK_ID = 847290


def main() -> None:
    settings = get_settings()
    alembic_config = Config(ROOT / "alembic.ini")
    engine = create_engine(settings.database_url, pool_pre_ping=True)

    with engine.connect() as lock_connection:
        lock_connection.execute(
            text("SELECT pg_advisory_lock(:lock_id)"),
            {"lock_id": MIGRATION_LOCK_ID},
        )
        try:
            command.upgrade(alembic_config, "head")
        finally:
            lock_connection.execute(
                text("SELECT pg_advisory_unlock(:lock_id)"),
                {"lock_id": MIGRATION_LOCK_ID},
            )

    engine.dispose()


if __name__ == "__main__":
    main()
