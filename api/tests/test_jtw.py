import pytest
from jwt import InvalidTokenError

from app.core.jwt import (
    create_access_token,
    create_refresh_token,
    decode_token
)


def test_access_token():
    token = create_access_token(1, "user")
    payload = decode_token(token)

    assert payload["sub"] == "1"
    assert payload["role"] == "user"
    assert payload["type"] == "access"


def test_refresh_token():
    token = create_refresh_token(1)
    payload = decode_token(token)

    assert payload["sub"] == "1"
    assert payload["type"] == "refresh"
    assert "role" not in payload


def test_invalid_token():
    with pytest.raises(InvalidTokenError):
        decode_token("neispravan.token")