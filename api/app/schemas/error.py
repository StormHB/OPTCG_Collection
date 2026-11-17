"""Zajednicki OpenAPI modeli kontroliranih API pogresaka."""

from pydantic import BaseModel


class ApiErrorResponse(BaseModel):
    code: str
    message: str


class ValidationIssueResponse(BaseModel):
    field: str
    message: str


class ValidationErrorResponse(ApiErrorResponse):
    errors: list[ValidationIssueResponse]


_DESCRIPTIONS = {
    401: "Nedostaje, istekao je ili nije valjan access token.",
    403: "Prijavljeni korisnik nema pravo pristupa trazenom resursu.",
    404: "Trazeni resurs nije pronaden.",
    409: "Zahtjev je u sukobu s trenutnim stanjem resursa.",
    413: "Poslana datoteka prelazi dopustenu velicinu.",
    422: "Neispravni ulazni podaci ili sadrzaj zahtjeva.",
}


def error_responses(*statuses: int) -> dict[int, dict]:
    """Deklaracije stvarnog JSON ugovora za Swagger/OpenAPI."""
    responses = {}
    for status in statuses:
        model = (
            ApiErrorResponse | ValidationErrorResponse
            if status == 422
            else ApiErrorResponse
        )
        responses[status] = {
            "model": model,
            "description": _DESCRIPTIONS[status],
        }
    return responses
