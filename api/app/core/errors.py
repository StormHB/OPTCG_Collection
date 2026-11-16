from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class AppError(Exception):
    """Pogreska domene, koja u kasnijim predavanjima dolazi iz services sloja."""

    def __init__(self, code: str, message: str, status_code: int = 400):
        self.code = code
        self.message = message
        self.status_code = status_code


async def app_error_handler(_request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"code": exc.code, "message": exc.message},
        headers={"WWW-Authenticate": "Bearer"} if exc.status_code == 401 else None,
    )


async def validation_error_handler(
    _request: Request, exc: RequestValidationError
) -> JSONResponse:
    errors = []
    for error in exc.errors():
        location = [str(part) for part in error["loc"] if part != "body"]
        errors.append({"field": ".".join(location), "message": error["msg"]})
    return JSONResponse(
        status_code=422,
        content={
            "code": "validation_error",
            "message": "Neispravni podaci u zahtjevu",
            "errors": errors,
        },
    )


async def http_exception_handler(
    _request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    error_codes = {
        400: "bad_request",
        401: "invalid_credentials",
        403: "forbidden",
        404: "not_found",
        405: "method_not_allowed",
        413: "payload_too_large",
    }
    headers = dict(exc.headers or {})
    if exc.status_code == 401:
        headers.setdefault("WWW-Authenticate", "Bearer")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "code": error_codes.get(exc.status_code, "http_error"),
            "message": str(exc.detail),
        },
        headers=headers or None,
    )


async def unexpected_error_handler(request: Request, _exc: Exception) -> JSONResponse:
    """Siguran, dosljedan 500; detalji pogreške ostaju samo u logu."""
    import logging

    logging.getLogger(__name__).exception(
        "Neocekivana API pogreska: %s %s", request.method, request.url.path
    )
    return JSONResponse(
        status_code=500,
        content={
            "code": "internal_server_error",
            "message": "Doslo je do interne pogreske posluzitelja",
        },
    )
