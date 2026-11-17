# Korak 11A.3 — HTTP kodovi i poruke

**Branch:** `fix/backend-validation`. **Migracija:** nema nove; i dalje `004 (head)`.

## Problem

API već koristi `AppError` s dosljednim `{ "code", "message" }` i zaseban odgovor za Pydantic validaciju (`422`). Međutim, prevelik Excel upload dosad je vraćao `422`, jednako kao neispravan Excel; neočekivana `500` greška nije imala ujednačeni sigurni JSON, a razvojni `FastAPI(debug=True)` mogao je vratiti traceback.

## Rješenje

- `api/app/routers/collection_import.py`: prazan/nepodržan `.xlsx` → `422` / `invalid_excel`; datoteka **veća od 6 MB** → `413` / `excel_too_large`. Vrijedi za `preview` i `apply`.
- `api/app/core/errors.py`: ujednačen HTTP JSON za standardne iznimke i za `AppError`, zaglavlje `WWW-Authenticate: Bearer` uz `401`, sigurna generička poruka `500` / `internal_server_error` uz zapis detalja na poslužitelju.
- `api/app/main.py`: registriran handler za neočekivane iznimke; `debug=False` sprječava slanje tracebacka klijentu čak i kada je `ENV=dev`. Razvojno logiranje ostaje uključeno kroz postojeći `setup_logging`.
- Postojeći poslovni kodovi i poruke za `403`, `404`, `409`, `422` nisu preimenovani. `204 No Content` ostaje bez JSON tijela.

## Ugovor o greškama

| HTTP | Kada | Primjer koda |
| --- | --- | --- |
| 400 | Neispravan zahtjev iz poslovne logike | `bad_request` ili specifičan `AppError.code` |
| 401 | Nedostaje/nevaljan access token | `invalid_credentials`, `token_expired` |
| 403 | Nisu dopuštene tuđe kolekcije | `forbidden` |
| 404 | Nema resursa | `not_found`, `loan_not_found`, `printing_not_found` |
| 405 | Pogrešna HTTP metoda | `method_not_allowed` |
| 409 | Konflikt: duplikat ili posudba | `conflict`, `insufficient_quantity`, `return_exceeds_outstanding`, `stale_import_preview` |
| 413 | Excel datoteka preko 6 MB | `excel_too_large` |
| 422 | Neispravna polja, datumi, prazan Excel | `validation_error`, `invalid_excel`, `invalid_loan_dates` |
| 500 | Neočekivana pogreška servera | `internal_server_error` |

Kontrolirana greška: `{"code":"...","message":"..."}`; validacija: dodatno `errors:[{"field":"...","message":"..."}]`. Detalji iznimki ili veze s bazom nikad ne idu u 500 odgovor.

## Testovi

`api/tests/test_http_error_contract.py`: statusi i tijela HTTP iznimki, zaglavlja `401` i `405`, postojeći `AppError`, `422` validacija, `500` bez tracebacka, neispravan i prevelik Excel u `preview` i `apply`, vlasništvo prije obrade datoteke. Ne koristi stvarnu korisničku bazu. Puni testovi i Ruff moraju proći lokalno.

## Otvoreno za Korak 11B

Potpuna endpoint-by-endpoint matrica poslovnih kodova; dokumentiranje `responses` u OpenAPI/Swaggeru; integracijski testovi protiv zasebne PostgreSQL testne baze. Nemoj simulacijom `500` u Swaggeru rušiti stvarni servis; test za to već koristi izolirani `TestClient`.
