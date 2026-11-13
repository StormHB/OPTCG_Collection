# Korak 9B — API za posudbe i vraćanja

**Branch:** `feat/card-loans`
**Preduvjet:** Korak 9A; migracija `004` i `card_loans` već postoje. **Za 9B ne stvaramo novu migraciju.**

## Datoteke

- `api/app/schemas/card_loan.py` — Pydantic sheme, `AwareDatetime`, valjane količine i smjerovi.
- `api/app/repositories/card_loan_repo.py` — SQLAlchemy upiti, zaključavanje redaka i eager loading izdanja.
- `api/app/services/card_loan_service.py` — poslovna pravila, dostupnost, povrati i UTC.
- `api/app/routers/card_loans.py` — FastAPI endpointovi.
- `api/app/routers/collections.py` — uključuje novi router **uz postojeći Excel import**.
- `api/app/repositories/collection_repo.py` — štiti vlasničke količine pri PATCH-u i brisanju.
- `api/app/services/collection_excel_import.py` — provjerava aktivne posudbe pri previewu i ponovno pri applyu.
- `api/tests/test_card_loans_api.py` — HTTP, validacije, ovlasti, statusi i vraćanja.
- `api/tests/test_card_loans_collection_safety.py` — regresija CRUD-a i Excel importa.
- `README.md` — ažuriran pregled projekta.

## API

Sve su rute privatne i zahtijevaju JWT **access token** i ispravni `user_id`; čak ni admin ne može čitati tuđe posudbe.

| Metoda | Ruta | Rezultat |
| --- | --- | --- |
| `GET` | `/collections/{user_id}/loans` | `200`, popis; opcionalno `?direction=lent&active_only=true` |
| `POST` | `/collections/{user_id}/loans` | `201`, nova posudba |
| `GET` | `/collections/{user_id}/loans/{loan_id}` | `200`, jedna posudba |
| `POST` | `/collections/{user_id}/loans/{loan_id}/returns` | `200`, ažurirana posudba |

Primjer nove posudbe u Swaggeru (koristi stvarni `printing_id` iz baze):

```json
{
  "printing_id": 16,
  "direction": "lent",
  "person_name": "Ivan",
  "quantity": 2,
  "loaned_at": "2026-11-12T20:00:00+01:00",
  "due_at": "2026-11-25T20:00:00+01:00",
  "note": "Posuđeno za turnir"
}
```

`loaned_at`, `due_at` i `note` su neobavezni. `loaned_at` bez vrijednosti znači trenutačni UTC datum. Za slanje datuma uvijek napiši vremensku zonu (`Z`, `+01:00` ili `+02:00`). U bazi se datumi normaliziraju na UTC.

Primjer djelomičnog vraćanja (zamijeni `loan_id` stvarnim ID-jem iz odgovora):

```http
POST /collections/7/loans/77/returns
```

```json
{"quantity": 1, "returned_at": "2026-11-13T18:30:00+01:00"}
```

`quantity_returned` raste, a `outstanding_quantity = quantity - quantity_returned`. Dok postoji dug, `returned_at` u zapisu je `null`. Nakon **potpunog** vraćanja pohranjuje se datum potpunog zatvaranja posudbe. Povijest ostaje sačuvana, ne brišemo je automatski.

Odgovor uključuje `printing_id`, `card_code`, `card_name`, `set_code`, `variant_code` i `image_url` za prikaz točnog izdanja, bez potrebe za zasebnim dohvatom svake slike.

## Poslovna pravila

1. **`lent`**: korisnik mora posjedovati izdanje i imati dovoljno fizički dostupnih kopija. `available = owned - SUM(quantity - quantity_returned)` za njegove **aktivne odlazne** posudbe tog izdanja.
2. **`borrowed`**: evidentira se dug prema drugoj osobi, ali ne mijenja `collection_entries` i ne povećava vlastite playsetove.
3. Više paralelnih odlaznih posudbi istog izdanja serijalizirano je PostgreSQL zaključavanjem retka `collection_entries` (`SELECT ... FOR UPDATE`). Povrati zaključavaju odgovarajući redak `card_loans`.
4. **PATCH, DELETE i Excel replace** odbijaju smanjenje vlasničkog broja primjeraka ispod još posuđene količine. Excel preview odmah prijavljuje problem; apply ga ponovno provjerava pod lockom čak i ako se posudba dogodila nakon previewa.
5. Djelomični povrat ne smije biti veći od preostale količine; povrat već zatvorene posudbe je sukob.
6. `due_at` ne može biti prije `loaned_at`, a datum vraćanja ne može biti prije posudbe. Datumska polja u JSON-u zahtijevaju vremensku zonu.
7. Kod posudbe ne smanjujemo `collection_entries.quantity`. Svaki zapis evidencije vezan je na konkretni `printing_id` (alt/reprint ostaju različiti).

## HTTP statusi i poruke

Sve domenske pogreške prate postojeći oblik API-ja:

```json
{"code": "insufficient_quantity", "message": "Nije moguce posuditi 3 primjeraka; dostupno je 2"}
```

- `201` — nova posudba; `200` — čitanje/povrat.
- `401` — nema valjanog JWT access tokena.
- `403` (`forbidden`) — pristup tuđoj kolekciji/posudbi.
- `404` (`printing_not_found`, `loan_not_found`) — nepoznato izdanje/posudba.
- `409` (`insufficient_quantity`, `return_exceeds_outstanding`, `loan_already_returned`, `active_loans_exceed_owned`) — sukob s poslovnim pravilima.
- `422` (`validation_error`, `invalid_loan_dates`, `invalid_return_date`) — nevaljani podaci ili datumi.

## Testovi

U terminalu iz `api/`:

```powershell
python -m pytest tests/test_card_loans_api.py tests/test_card_loans_collection_safety.py -q
python -m pytest tests -q
alembic current
```

Ako je `004 (head)` i testovi prolaze, u Swaggeru provjeri unos te djelomično/potpuno vraćanje kontrolne posudbe. Možeš iskoristiti izdanje koje stvarno posjeduješ, uz jasno prepoznatljivo ime/napomenu. Testna posudba ostaje u povijesti i nakon povrata.

Za 9B **nema `alembic upgrade`**, jer nema nove sheme ni migracije. README treba commitati tek nakon stvarne provjere.

## Poznate granice

- Nema brisanja ili uređivanja povijesnog zapisa posudbe. Ako bude potrebno, dodat ćemo odvojene, kontrolirane operacije, bez gubitka povijesti.
- Nema automatskih notifikacija o rokovima niti Vue prikaza (kasniji koraci).
- Raspoloživost štiti PostgreSQL transakcija i `FOR UPDATE`; SQLite testovi provjeravaju pravila, ali paralelne transakcije najbolje je provjeriti i na PostgreSQL-u prije javne objave.
- Ne koristiti osobnu Excel datoteku kao testni fixture u javnom repozitoriju.
