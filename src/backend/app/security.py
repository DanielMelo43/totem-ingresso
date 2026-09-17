import hashlib
import json
from datetime import timedelta

from fastapi.responses import JSONResponse
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .config import get_settings
from .errors import AppError
from .models import IdempotencyRecord, OperationLock, utc_now


settings = get_settings()


def request_fingerprint(payload: object) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str).encode()
    return hashlib.sha256(encoded).hexdigest()


def begin_idempotency(db: Session, key: str | None, method: str, path: str, payload: object) -> IdempotencyRecord | JSONResponse:
    if not key or not 16 <= len(key) <= 128 or any(not (char.isalnum() or char in "-_.:") for char in key):
        raise AppError(400, "CHAVE_IDEMPOTENCIA_INVALIDA", "Envie uma Idempotency-Key válida entre 16 e 128 caracteres.")
    fingerprint = request_fingerprint(payload)
    now = utc_now()
    existing = db.scalar(select(IdempotencyRecord).where(IdempotencyRecord.key == key, IdempotencyRecord.method == method, IdempotencyRecord.path == path))
    if existing:
        if existing.request_hash != fingerprint:
            raise AppError(409, "CHAVE_IDEMPOTENCIA_REUTILIZADA", "Esta chave já foi usada com dados diferentes.")
        if existing.state == "completed" and existing.response_body is not None:
            return JSONResponse(existing.response_body, status_code=existing.response_status or 200, headers={"Idempotency-Replayed": "true"})
        if existing.expires_at > now:
            raise AppError(409, "OPERACAO_EM_ANDAMENTO", "Esta operação já está em andamento.", {"Retry-After": "2"})
        db.delete(existing)
        db.commit()
    record = IdempotencyRecord(key=key, method=method, path=path, request_hash=fingerprint, expires_at=now + timedelta(seconds=settings.operation_lock_seconds))
    db.add(record)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise AppError(409, "OPERACAO_EM_ANDAMENTO", "Esta operação já está em andamento.", {"Retry-After": "2"})
    db.refresh(record)
    return record


def complete_idempotency(record: IdempotencyRecord, response_status: int, response_body: dict) -> None:
    record.state = "completed"
    record.response_status = response_status
    record.response_body = response_body
    record.expires_at = utc_now() + timedelta(hours=settings.idempotency_ttl_hours)


def abandon_idempotency(db: Session, record: IdempotencyRecord) -> None:
    if record.id:
        db.execute(delete(IdempotencyRecord).where(IdempotencyRecord.id == record.id, IdempotencyRecord.state == "processing"))
        db.commit()


def acquire_lock(db: Session, resource: str, owner: str) -> OperationLock:
    now = utc_now()
    existing = db.get(OperationLock, resource)
    if existing and existing.expires_at > now and existing.owner != owner:
        raise AppError(409, "RECURSO_BLOQUEADO", "Já existe uma operação em andamento para este pedido.", {"Retry-After": "2"})
    if existing:
        db.delete(existing)
        db.flush()
    lock = OperationLock(resource=resource, owner=owner, expires_at=now + timedelta(seconds=settings.operation_lock_seconds))
    db.add(lock)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise AppError(409, "RECURSO_BLOQUEADO", "Já existe uma operação em andamento para este pedido.", {"Retry-After": "2"})
    return lock


def release_lock(db: Session, resource: str, owner: str) -> None:
    db.execute(delete(OperationLock).where(OperationLock.resource == resource, OperationLock.owner == owner))

