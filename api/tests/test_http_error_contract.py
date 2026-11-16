"""Korak 11A.3: dosljedni HTTP statusi, sigurne poruke i excel upload."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.testclient import TestClient
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.deps import get_current_user, get_db
from app.core.errors import (
    AppError,
    app_error_handler,
    http_exception_handler,
    unexpected_error_handler,
    validation_error_handler,
)
from app.main import create_app
from app.routers.collection_import import router as import_router


def minimal_app() -> FastAPI:
    app = FastAPI(debug=False)
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(Exception, unexpected_error_handler)
    return app


@pytest.mark.parametrize(
    "status,code",
    [
        (400, "bad_request"),
        (401, "invalid_credentials"),
        (403, "forbidden"),
        (404, "not_found"),
        (405, "method_not_allowed"),
        (413, "payload_too_large"),
    ],
)
def test_http_exception_has_predictable_body(status, code):
    app = minimal_app()

    @app.get("/raise")
    def throw():
        raise HTTPException(status_code=status, detail="Kontrolirana greska")

    result = TestClient(app).get("/raise")
    assert result.status_code == status
    assert result.json() == {"code": code, "message": "Kontrolirana greska"}
    if status == 401:
        assert result.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize("status", [400, 401, 403, 404, 409, 422])
def test_app_error_preserves_code_message_and_status(status):
    app = minimal_app()

    @app.get("/raise")
    def throw():
        raise AppError("business_rule", "Provjera poslovnog pravila", status)

    result = TestClient(app).get("/raise")
    assert result.status_code == status
    assert result.json() == {
        "code": "business_rule",
        "message": "Provjera poslovnog pravila",
    }
    if status == 401:
        assert result.headers["www-authenticate"] == "Bearer"


def test_unknown_path_and_method_have_json_codes():
    client = TestClient(create_app())
    missing = client.get("/route-that-does-not-exist")
    assert missing.status_code == 404
    assert missing.json()["code"] == "not_found"
    assert isinstance(missing.json()["message"], str)

    wrong_method = client.post("/health")
    assert wrong_method.status_code == 405
    assert wrong_method.json()["code"] == "method_not_allowed"
    assert "GET" in wrong_method.headers["allow"]


def test_validation_error_contains_code_message_and_fields():
    app = minimal_app()

    @app.get("/validate")
    def validate(limit: int):
        return {"limit": limit}

    result = TestClient(app).get("/validate?limit=abc")
    assert result.status_code == 422
    body = result.json()
    assert body["code"] == "validation_error"
    assert isinstance(body["message"], str) and body["message"]
    assert any(item["field"] == "query.limit" for item in body["errors"])


def test_unexpected_500_does_not_expose_internal_error_or_traceback():
    app = create_app()

    @app.get("/audit-crash")
    async def crash():
        raise RuntimeError("DATABASE_URL=postgres://SECRET_SHOULD_NOT_LEAK")

    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/audit-crash")
    assert response.status_code == 500
    assert response.json() == {
        "code": "internal_server_error",
        "message": "Doslo je do interne pogreske posluzitelja",
    }
    assert "SECRET_SHOULD_NOT_LEAK" not in response.text
    assert "Traceback" not in response.text


def import_client() -> TestClient:
    app = minimal_app()
    app.include_router(import_router, prefix="/collections")

    async def fake_db():
        yield object()

    app.dependency_overrides[get_db] = fake_db
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id=7, role="user", is_active=True
    )
    return TestClient(app)


@pytest.mark.parametrize(
    "filename,content,max_bytes,expected_status,expected_code",
    [
        ("collection.xlsx", b"a" * 6, 5, 413, "excel_too_large"),
        ("collection.xlsx", b"", 5, 422, "invalid_excel"),
        ("collection.txt", b"abcd", 5, 422, "invalid_excel"),
    ],
)
def test_excel_upload_errors_are_distinguished_without_writing(
    filename, content, max_bytes, expected_status, expected_code
):
    client = import_client()
    with (
        patch("app.routers.collection_import.MAX_UPLOAD_BYTES", max_bytes),
        patch(
            "app.routers.collection_import.build_plan", new_callable=AsyncMock
        ) as plan,
        patch(
            "app.routers.collection_import.apply_plan", new_callable=AsyncMock
        ) as apply,
    ):
        response = client.post(
            "/collections/7/import/preview",
            files={"file": (filename, content, "application/octet-stream")},
        )
    assert response.status_code == expected_status
    assert response.json()["code"] == expected_code
    assert response.json()["message"]
    plan.assert_not_awaited()
    apply.assert_not_awaited()


def test_oversized_upload_also_rejected_in_apply_before_plan():
    client = import_client()
    with (
        patch("app.routers.collection_import.MAX_UPLOAD_BYTES", 5),
        patch(
            "app.routers.collection_import.build_plan", new_callable=AsyncMock
        ) as plan,
        patch(
            "app.routers.collection_import.apply_plan", new_callable=AsyncMock
        ) as apply,
    ):
        response = client.post(
            "/collections/7/import/apply",
            params={"plan_token": "a" * 64},
            files={"file": ("collection.xlsx", b"a" * 6, "application/octet-stream")},
        )
    assert response.status_code == 413
    assert response.json()["code"] == "excel_too_large"
    plan.assert_not_awaited()
    apply.assert_not_awaited()


def test_unauthorized_excel_upload_does_not_read_uploaded_file():
    app = minimal_app()
    app.include_router(import_router, prefix="/collections")

    async def fake_db():
        yield object()

    app.dependency_overrides[get_db] = fake_db
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id=8, role="admin", is_active=True
    )
    with patch(
        "app.routers.collection_import._read_upload", new_callable=AsyncMock
    ) as read:
        response = TestClient(app).post(
            "/collections/7/import/preview",
            files={"file": ("collection.xlsx", b"abc", "application/octet-stream")},
        )
    assert response.status_code == 403
    assert response.json()["code"] == "forbidden"
    read.assert_not_awaited()
