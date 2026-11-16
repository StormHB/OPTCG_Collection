from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.openapi.utils import get_openapi
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.config import Settings, settings
from app.core.errors import (
    AppError,
    app_error_handler,
    http_exception_handler,
    unexpected_error_handler,
    validation_error_handler,
)
from app.core.logging import setup_logging
from app.routers.admin import router as admin_router
from app.routers.auth import router as auth_router
from app.routers.cards import router as cards_router
from app.routers.collections import router as collections_router
from app.routers.health import router as health_router


def create_app(config: Settings = settings) -> FastAPI:
    setup_logging(debug=config.ENV == "dev")
    app = FastAPI(title=config.APP_NAME, debug=False)

    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(Exception, unexpected_error_handler)

    app.include_router(health_router, prefix="/health", tags=["health"])
    app.include_router(auth_router, prefix="/auth", tags=["auth"])

    app.include_router(collections_router, prefix="/collections", tags=["collections"])

    app.include_router(admin_router, prefix="/admin", tags=["admin"])

    app.include_router(cards_router, prefix="/cards", tags=["cards"])

    def custom_openapi() -> dict:
        if app.openapi_schema is None:
            schema = get_openapi(
                title=app.title,
                version=app.version,
                routes=app.routes,
            )
            # GET /cards je javan bez osobnog filtera; bearer je potreban samo
            # kada se trazi collection_status. OpenAPI security lista je OR.
            schema["paths"]["/cards"]["get"]["security"] = [
                {},
                {"HTTPBearer": []},
            ]
            app.openapi_schema = schema
        return app.openapi_schema

    app.openapi = custom_openapi

    return app


app = create_app()
