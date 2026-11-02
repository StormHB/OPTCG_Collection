from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.config import Settings, settings
from app.core.errors import (
    AppError,
    app_error_handler,
    http_exception_handler,
    validation_error_handler,
)
from app.core.logging import setup_logging
from app.routers.auth import router as auth_router
from app.routers.health import router as health_router


def create_app(config: Settings = settings) -> FastAPI:
    setup_logging(debug=config.ENV == "dev")
    app = FastAPI(title=config.APP_NAME, debug=config.ENV == "dev")

    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)

    app.include_router(health_router, prefix="/health", tags=["health"])
    app.include_router(auth_router, prefix="/auth", tags=["auth"])
    return app


app = create_app()
