import hashlib
import hmac

from cryptography.fernet import Fernet, InvalidToken

from ..config import get_settings


PREFIX = "enc:v1:"
settings = get_settings()
fernet = Fernet(settings.cpf_encryption_key.encode())
lookup_key = hashlib.sha256(settings.cpf_encryption_key.encode() + b":customer-lookup:v1").digest()


def lookup_hash(value: str) -> str:
    normalized = value.strip().lower()
    return hmac.new(lookup_key, normalized.encode(), hashlib.sha256).hexdigest()


def encrypt_cpf(cpf: str) -> str:
    digits = "".join(char for char in cpf if char.isdigit())
    return PREFIX + fernet.encrypt(digits.encode()).decode()


def decrypt_cpf(value: str) -> str:
    if not value.startswith(PREFIX):
        return value
    try:
        return fernet.decrypt(value.removeprefix(PREFIX).encode()).decode()
    except InvalidToken as exc:
        raise ValueError("CPF criptografado com chave inválida") from exc


def protect_customer(kind: str, value: str) -> tuple[str, str]:
    normalized = "".join(char for char in value if char.isdigit()) if kind == "cpf" else value.strip().lower()
    stored = encrypt_cpf(normalized) if kind == "cpf" else normalized
    return stored, lookup_hash(normalized)

