"""Brzi testovi shema - ne ovise o pokrenutoj bazi."""

import pytest
from pydantic import ValidationError

from app.schemas.auth import RegisterRequest
from app.schemas.user import UserResponse


def test_register_accepts_valid_input():
    data = RegisterRequest(username="luffy_01", password="sigurna-lozinka")
    assert data.username == "luffy_01"


def test_register_rejects_password_over_72_bytes():
    with pytest.raises(ValidationError):
        RegisterRequest(username="luffy_01", password="č" * 37)


def test_register_rejects_admin_role_from_client():
    with pytest.raises(ValidationError):
        RegisterRequest(username="luffy_01", password="sigurna-lozinka", role="admin")


def test_user_response_does_not_include_password_hash():
    from types import SimpleNamespace
    user = SimpleNamespace(id=1, username="luffy_01", role="user", is_active=True, password_hash="secret")
    result = UserResponse.model_validate(user).model_dump()
    assert "password_hash" not in result
