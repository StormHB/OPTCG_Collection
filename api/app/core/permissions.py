"""Predavanje 4: kontrola uloge korisnika na razini FastAPI ovisnosti."""

from collections.abc import Callable

from fastapi import Depends

from app.core.deps import get_current_user
from app.core.errors import AppError
from app.models.user import User


def require_role(*allowed_roles: str) -> Callable[..., User]:
    """Vrati ovisnost koja prihvaća samo korisnike zadanih uloga.

    Ulogu čitamo iz baze preko get_current_user; ne vjerujemo staroj
    vrijednosti u JWT tokenu. Koristi se u rutama kroz Depends.
    """
    def checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise AppError("forbidden", "Nemate dozvolu za ovu radnju", 403)
        return current_user

    return checker
