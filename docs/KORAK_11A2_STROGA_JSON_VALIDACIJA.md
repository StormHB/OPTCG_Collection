# Korak 11A.2 — stroga validacija JSON zahtjeva

**Namjena:** nakon backend revizije onemogućiti tiho ignoriranje pogrešno napisanih JSON polja te spriječiti nehotične Pydantic pretvorbe tipova. **Nema nove Alembic migracije.**

## Što je promijenjeno

- `app/schemas/collection.py`: `CollectionEntryCreate` i `CollectionEntryUpdate` koriste `extra="forbid"`. `printing_id` i `quantity` zahtijevaju stvarni JSON cijeli broj (`strict=True`). Prazne i samo razmacima ispunjene napomene nisu dopuštene.
- `app/schemas/card_loan.py`: `CardLoanCreate` i `CardLoanReturn` koriste `extra="forbid"`; `printing_id` i `quantity` strogo su cijeli brojevi. Ime osobe mora biti neprazan tekst (postojeće uklanjanje rubnih razmaka ostaje); napomena mora sadržavati barem jedan znak različit od razmaka. JSON datumi prihvaćaju ISO 8601 tekst s vremenskom zonom, ali ne Unix timestamp kao broj. Interna Python uporaba `datetime` ostaje dopuštena.
- `app/schemas/auth.py`: i `LoginRequest` i `RefreshRequest` koriste `extra="forbid"`, kao što ga je `RegisterRequest` već koristio.
- `tests/test_request_body_validation.py`: HTTP regresijski testovi provjeravaju da neispravni zahtjevi završe sa `422`, imaju `code="validation_error"` i uopće ne pozovu servis. Dodani su i pozitivni testovi očuvanja djelomičnog PATCH-a, vremenskih zona i null vrijednosti.

## Ugovor JSON zahtjeva

| Zahtjev | Pravilo | Primjer rezultata |
| --- | --- | --- |
| `POST /collections/{user_id}/entries` | Samo `printing_id`, `quantity`, `note`; cijeli brojevi, bez neočekivanih polja | `"quantity": "3"` → 422, `"quantity": 3` → prolazi validaciju |
| `PATCH /collections/{user_id}/entries/{printing_id}` | Samo `quantity` i/ili `note`; barem jedno polje; `quantity` nije `null` | `{"note": null}` → briše napomenu, `{"quantity": null}` → 422 |
| `POST /collections/{user_id}/loans` | Točno definirana polja; `direction` je `lent`/`borrowed`; ime nije prazno | `{"quantity": true}` → 422 |
| `POST /collections/{user_id}/loans/{loan_id}/returns` | Samo `quantity` i opcionalni `returned_at` | `returnned_at` (tipfeler) → 422 |
| `POST /auth/register`, `/auth/login`, `/auth/refresh` | Bez dodatnih JSON polja | `"role": "admin"` u login/register → 422 |

### Datumi

```json
{
  "quantity": 1,
  "returned_at": "2026-11-16T12:00:00+01:00"
}
```

Za datum bez vremenske zone (`"2026-11-16T12:00:00"`) i brojčani timestamp (`1794830400`) vraća se `422`. Postojeća logika normaliziranja datuma na UTC u servisima ostaje nepromijenjena. Kada je datum opcionalan, izostanak ili `null` i dalje su dopušteni.

### Napomene

- `note=null` i izostavljeno `note` i dalje su dopušteni.
- Kod `PATCH` `note=null` briše napomenu, a izostavljeno `note` je ne mijenja.
- `note=""` i `note="   "` sada vraćaju `422` — za brisanje se koristi `null`.
- Neprazan tekst ostaje sačuvan bez automatskog uklanjanja rubnih razmaka.

### Standardni 422 odgovor

```json
{
  "code": "validation_error",
  "message": "Neispravni podaci u zahtjevu",
  "errors": [
    {"field": "quantitty", "message": "Extra inputs are not permitted"}
  ]
}
```

`errors[].message` dolazi iz Pydantica i može se razlikovati prema verziji. Središnji HTTP exception handler nije mijenjan: potpuna revizija kodova i poruka dolazi u **11A.3**.

## Lokalna provjera

Iz `api/`:

```powershell
python -m pytest tests/test_request_body_validation.py -q
python -m pytest tests -q
python -m ruff check .
python -m ruff format --check .
alembic current
```

**Izolirana provjera** (s testnim zamjenama za nedostupne PostgreSQL/bcrypt ovisnosti u autorovu okruženju): `306 passed`, od čega su **63 nova parametrizirana testa** iz 11A.2. To ne zamjenjuje lokalnu provjeru sa stvarnim PostgreSQL-om.

## Što se namjerno nije mijenjalo

- Odgovori API-ja i SQLAlchemy modeli; sigurnost vlasništva; poslovna pravila količina i posudbi; obrada Excela; status kodovi poslovnih grešaka.
- Za `GET /cards` query filtere vrijede pravila iz 11A.1; nisu JSON request-body sheme.
- Nema promjene tablica, migracija ni postojećih podataka u bazi.

## Sljedeće

**11A.3 — HTTP greške i poruke:** ujednačiti odgovore servisnih i neočekivanih grešaka, dokumentirati status kodove te dopuniti testove po rutama.
