import hashlib
import json
import logging
import asyncio
from datetime import timedelta

from fastapi import Request
from fastapi.responses import JSONResponse
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .config import get_settings
from .errors import AppError, error_response
from .models import IdempotencyRecord, OperationLock, RateLimitBucket, utc_now


settings = get_settings()
logger = logging.getLogger("totem.security")


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


def rate_limit(request: Request, db: Session) -> None:
    path = request.url.path
    if path in {"/health", "/docs", "/openapi.json"}:
        return
    if request.method == "GET":
        limit, scope = 120, "read"
    elif path.endswith("/payment"):
        limit, scope = 5, "payment"
    elif path == "/api/v1/orders":
        limit, scope = 5, "order"
    else:
        limit, scope = 20, "write"
    device = request.headers.get("X-Device-ID", "anonymous")[:80]
    ip = request.client.host if request.client else "unknown"
    now = utc_now()
    window = now.replace(second=0, microsecond=0)
    for identity in (f"ip:{ip}", f"device:{device}"):
        key = f"{scope}:{identity}"
        bucket = db.scalar(select(RateLimitBucket).where(RateLimitBucket.key == key).with_for_update())
        if not bucket or bucket.window_started_at != window:
            if bucket:
                bucket.window_started_at, bucket.count = window, 1
            else:
                db.add(RateLimitBucket(key=key, window_started_at=window, count=1))
        else:
            if bucket.count >= limit:
                retry = max(1, 60 - now.second)
                raise AppError(429, "LIMITE_REQUISICOES_EXCEDIDO", "Muitas requisições. Aguarde antes de tentar novamente.", {"Retry-After": str(retry)})
            bucket.count += 1
    db.commit()


async def security_middleware(request: Request, call_next):
    request.state.trace_id = request.headers.get("X-Trace-ID", "")[:64] or hashlib.sha256(f"{utc_now().isoformat()}:{id(request)}".encode()).hexdigest()[:16]
    try:
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                if int(content_length) > settings.max_request_bytes:
                    raise AppError(413, "REQUISICAO_MUITO_GRANDE", "A requisição excede o tamanho permitido.")
            except ValueError:
                raise AppError(400, "CONTENT_LENGTH_INVALIDO", "Cabeçalho de tamanho inválido.")
        with request.app.state.session_factory() as db:
            rate_limit(request, db)
        try:
            response = await asyncio.wait_for(call_next(request), timeout=settings.request_timeout_seconds)
        except asyncio.TimeoutError:
            raise AppError(408, "TIMEOUT_REQUISICAO", "A requisição excedeu o tempo permitido.")
    except AppError as exc:
        logger.warning("request_blocked trace_id=%s method=%s path=%s code=%s status=%s", request.state.trace_id, request.method, request.url.path, exc.code, exc.status_code)
        return error_response(request, exc.status_code, exc.code, exc.message, exc.headers)
    except Exception as exc:
        logger.critical("middleware_error trace_id=%s method=%s path=%s", request.state.trace_id, request.method, request.url.path, exc_info=exc)
        return error_response(request, 503, "SERVICO_INDISPONIVEL", "Serviço temporariamente indisponível. Tente novamente.")
    response.headers["X-Trace-ID"] = request.state.trace_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Cache-Control"] = "no-store"
    return response
