"""API sheme za registraciju, prijavu i JWT tokene."""

from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field


def validate_bcrypt_length(value: str) -> str:
    # bcrypt 5 odbija lozinke duze od 72 bajta (nije isto sto i 72 znaka).
    if len(value.encode("utf-8")) > 72:
        raise ValueError("Lozinka smije imati najvise 72 bajta")
    return value


Password = Annotated[str, Field(min_length=1), AfterValidator(validate_bcrypt_length)]
NewPassword = Annotated[str, Field(min_length=8), AfterValidator(validate_bcrypt_length)]


class RegisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str = Field(min_length=3, max_length=30, pattern=r"^[A-Za-z0-9_]+$")
    password: NewPassword


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    password: Password


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=1)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
