from functools import lru_cache
import base64
import hashlib
from urllib.parse import quote_plus

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Totem Ingresso API"
    database_url: str | None = None
    database_host: str = "localhost"
    database_port: int = 5432
    database_name: str = "totem_ingresso"
    database_user: str = "totem"
    database_password: str = ""
    database_echo: bool = False
    cpf_encryption_key: str = ""
    frontend_origins: str = "http://localhost:5173"
    reservation_minutes: int = 10
    idempotency_ttl_hours: int = 24
    operation_lock_seconds: int = 30
    request_timeout_seconds: float = 15.0
    max_request_bytes: int = 65536
    payment_timeout_seconds: float = 5.0
    circuit_failure_threshold: int = 3
    circuit_recovery_seconds: int = 30
    log_level: str = "INFO"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @model_validator(mode="after")
    def build_database_url(self):
        if not self.database_url:
            if not self.database_password:
                raise ValueError("DATABASE_PASSWORD é obrigatória quando DATABASE_URL não é informada")
            user = quote_plus(self.database_user)
            password = quote_plus(self.database_password)
            host = self.database_host.strip()
            name = self.database_name.strip()
            self.database_url = f"postgresql+psycopg://{user}:{password}@{host}:{self.database_port}/{name}"
        if not self.cpf_encryption_key:
            if not self.database_password:
                raise ValueError("CPF_ENCRYPTION_KEY é obrigatória quando não há DATABASE_PASSWORD")
            derived = hashlib.sha256(f"totem-cpf-v1:{self.database_password}".encode()).digest()
            self.cpf_encryption_key = base64.urlsafe_b64encode(derived).decode()
        return self

    @property
    def origins(self) -> list[str]:
        return [origin.strip() for origin in self.frontend_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
