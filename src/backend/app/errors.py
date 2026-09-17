import logging
from datetime import UTC, datetime
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import DBAPIError


logger = logging.getLogger("totem.errors")


class AppError(Exception):
    def __init__(self, status_code: int, code: str, message: str, headers: dict[str, str] | None = None):
        self.status_code = status_code
        self.code = code
        self.message = message
        self.headers = headers or {}


def trace_id(request: Request) -> str:
    return getattr(request.state, "trace_id", uuid4().hex[:16])


def error_response(request: Request, status_code: int, code: str, message: str, headers: dict[str, str] | None = None) -> JSONResponse:
    body = {
        "erro": {
            "codigo": code,
            "mensagem": message,
            "status": status_code,
            "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "traceId": trace_id(request),
        }
    }
    response_headers = {"X-Trace-ID": trace_id(request), **(headers or {})}
    return JSONResponse(status_code=status_code, content=body, headers=response_headers)


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError):
        logger.warning("business_error trace_id=%s method=%s path=%s code=%s status=%s", trace_id(request), request.method, request.url.path, exc.code, exc.status_code)
        return error_response(request, exc.status_code, exc.code, exc.message, exc.headers)

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError):
        fields = [".".join(str(part) for part in error["loc"] if part != "body") for error in exc.errors()]
        logger.warning("validation_error trace_id=%s method=%s path=%s fields=%s", trace_id(request), request.method, request.url.path, fields)
        field_message = ", ".join(fields[:5]) or "requisição"
        return error_response(request, 422, "DADOS_INVALIDOS", f"Dados inválidos nos campos: {field_message}.")

    @app.exception_handler(HTTPException)
    async def http_error_handler(request: Request, exc: HTTPException):
        codes = {400: "REQUISICAO_INVALIDA", 401: "NAO_AUTENTICADO", 403: "NAO_AUTORIZADO", 404: "RECURSO_NAO_ENCONTRADO", 408: "TIMEOUT_REQUISICAO", 409: "CONFLITO", 422: "REGRA_NEGOCIO_INVALIDA", 429: "LIMITE_EXCEDIDO", 503: "SERVICO_INDISPONIVEL", 504: "TIMEOUT_SERVICO_EXTERNO"}
        public_message = exc.detail if isinstance(exc.detail, str) and exc.status_code < 500 else "Não foi possível concluir sua operação. Tente novamente."
        logger.warning("http_error trace_id=%s method=%s path=%s status=%s", trace_id(request), request.method, request.url.path, exc.status_code)
        return error_response(request, exc.status_code, codes.get(exc.status_code, "ERRO_REQUISICAO"), public_message, exc.headers)

    @app.exception_handler(DBAPIError)
    async def database_error_handler(request: Request, exc: DBAPIError):
        logger.critical("database_error trace_id=%s method=%s path=%s", trace_id(request), request.method, request.url.path, exc_info=exc)
        return error_response(request, 503, "BANCO_INDISPONIVEL", "Serviço temporariamente indisponível. Tente novamente.")

    @app.exception_handler(Exception)
    async def unexpected_error_handler(request: Request, exc: Exception):
        logger.critical("unexpected_error trace_id=%s method=%s path=%s", trace_id(request), request.method, request.url.path, exc_info=exc)
        return error_response(request, 500, "ERRO_INTERNO", "Não foi possível concluir sua operação. Tente novamente.")
