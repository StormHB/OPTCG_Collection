# Korak 11B.3 — završna revizija Swagger/OpenAPI i HTTP ugovora

Datum: 16. 11. 2026. Branch: `fix/backend-validation`. Migracija ostaje `004 (head)`.

## Cilj i postupak

Stvarna OpenAPI shema generirana je pozivom `create_app().openapi()` i uspoređena s registriranim FastAPI rutama, Pydantic shemama, ovisnostima autentikacije te ponašanjem koje već pokrivaju koraci 11B.1–11B.2D. Ovaj korak ne ponavlja poslovne testove; provjerava dokumentirani HTTP ugovor.

Pregledano je 20 aplikacijskih operacija za health, autentikaciju, administraciju, katalog, kolekcije, statistiku, Excel import i posudbe.

## Zatečena usklađenost

- Metode, putanje, path parametri i glavni success response modeli odgovarali su implementaciji.
- Numeričke granice filtera bile su vidljive u shemi: cost `0–10`, power `0–13000`.
- Counter dropdown već je bio ograničen na `0`, `1000` i `2000`, uz zaseban `counter_missing` boolean za SQL `NULL`.
- Osobni filtri `owned`, `missing` i `playset` imali su enum i opis da zahtijevaju JWT access token te koriste prijavljenog korisnika.
- Excel `mode` imao je enum `replace`/`add`, a `plan_token` duljinu 64 i heksadekadski uzorak.
- Posudbe su dokumentirale smjer `lent`/`borrowed`, granice količina, filtre i response podatke o printingu.

## Potvrđene nedosljednosti i minimalni ispravci

1. **Javni katalog bio je prikazan kao obavezno zaštićen.** Optional-auth dependency uzrokovao je da OpenAPI označi `GET /cards` samo bearer zaštitom, iako je ruta javna bez osobnih filtera. Generirana shema sada koristi OpenAPI OR zapis `[{}, {"HTTPBearer": []}]`: anonimni pristup je dopušten, a bearer se može poslati za osobne filtre.
2. **Poslovni statusni kodovi nisu bili deklarirani.** Rute su uglavnom prikazivale samo success i FastAPI 422. Dodani su zajednički OpenAPI response modeli i deklaracije za stvarno korištene `401`, `403`, `404`, `409`, `413` i `422` odgovore.
3. **Autogenerirani 422 nije odgovarao stvarnom handleru.** Dokumentacija sada prikazuje kontrolirani oblik s `code` i `message`, odnosno validacijski oblik s dodatnim poljem `errors` koje sadrži `field` i `message`.
4. **Excel success odgovori nisu imali shemu.** Preview i apply dobili su eksplicitne response modele sa sažetkom, problemima, uzorcima i tokenom; apply dodatno dokumentira status `applied`.
5. **Nedostajali su praktični primjeri i precizan opis vremena.** Dodani su primjeri auth, collection i loan request bodyja. Datumi posudbi izričito navode ISO 8601 i obaveznu vremensku zonu.
6. **Opis `plan_tokena` bio je nepotpun.** Swagger sada navodi vezanost uz datoteku, način, korisnika i relevantno stanje kolekcije te jasno kaže da token nije JWT i nema vremenski rok u postojećem ugovoru.

Promjene ne mijenjaju autentikaciju, poslovna pravila, bazu ni runtime sadržaj uspješnih odgovora.

## Novi regresijski testovi

`api/tests/test_openapi_contract_11b3.py` dodaje osam testova:

1. točan inventar svih metoda i ruta;
2. HTTP bearer scheme te javne, privatne i uvjetno autentificirane operacije;
3. success i poslovni error statusi;
4. JSON modeli kontroliranih i validacijskih pogrešaka;
5. enum vrijednosti, numeričke granice, Counter i osobni filtri;
6. multipart Excel ugovor, mode, `plan_token` i preview/apply response modeli;
7. request primjeri, granice količina te ISO 8601 datumi s vremenskom zonom;
8. filtri i ugovoreni identifikatori u odgovorima posudbi.

## Rezultat provjera

Iz direktorija `api/`:

```powershell
python -m pytest tests/test_openapi_contract_11b3.py -q
python -m pytest tests -q
python -m ruff check .
python -m ruff format --check .
```

- ciljani OpenAPI testovi: `8 passed`;
- puni backend suite: `456 passed`;
- `ruff check .`: bez grešaka;
- `ruff format --check .`: sve Python datoteke pravilno formatirane.

## Sljedeći obavezni korak: 11C

Prije PR-a u `main` mora se postaviti zasebna, trajna PostgreSQL testna baza bez osobnih podataka, testna konfiguracija i automatsko postavljanje sheme. Na njoj se moraju izvesti stvarni integracijski testovi paralelnih transakcija, `SELECT ... FOR UPDATE` blokiranja, utrka nad kolekcijama/importom/posudbama i potpunog rollbacka.

Postojeća PostgreSQL baza s osobnom kolekcijom nije korištena i ne smije se koristiti za te provjere.

Nisu napravljeni commit, push, merge ni migracija.
