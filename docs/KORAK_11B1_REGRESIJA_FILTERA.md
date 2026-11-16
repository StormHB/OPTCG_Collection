# Korak 11B.1 — Potpuna regresijska provjera filtera kataloga

Datum: 16. 11. 2026. Branch: `fix/backend-validation`.

## Cilj

Sustavno provjeriti `GET /cards`, javne opcije `GET /cards/filters`, osobne statuse iz JWT-a i SQL upite. Nema promjene strukture baze i Alembic ostaje `004 (head)`.

## Potvrđena nedosljednost i ispravak

U prethodnom kodu HTTP `counter_values` prihvaća samo `0`, `1000`, `2000`, dok je `/cards/filters` mogao vratiti `[null, 0, 1000, 2000]` ili dodatne vrijednosti. To bi klijentu ponudilo opciju koju API kasnije odbija.

- **Sada `GET /cards/filters` vraća točno `[0, 1000, 2000]` za `counter_values`.**
- Nedostajući tiskani Counter (`SQL NULL`) odabire se zasebno s `counter_missing=true`.
- `counter_values=none` je namjerno **422**, a `counter_values=0` nije isto što i `counter_missing=true`.
- `CardFilterOptionsResponse.counter_values` sada je `list[int]`, a stari test je usklađen s API ugovorom.

## Matrica validacije

| Parametar | Dopušteno / pravilo | Neispravno / rubni slučajevi |
|---|---|---|
| `colors`, `attributes`, `keywords`, `archetypes` | Ponavljanje vrijednosti = OR; različita slova i rubni razmaci zanemaruju se; podudaranje putem M:N | Nepoznata vrijednost = `200` s praznim rezultatom |
| `card_types` | OR; bez razlikovanja velikih/malih slova | Nepoznata vrijednost = `200` s praznim rezultatom |
| `costs` | Cijeli brojevi `0..10`; OR | Negativni, decimalni, tekst i vrijednosti > 10 = `422` |
| `powers` | Cijeli brojevi `0..13000`; OR | Negativni, decimalni, tekst i vrijednosti > 13000 = `422` |
| `counter_values` | Multi-select `0`, `1000`, `2000` | `none`, `3000`, decimalni broj, tekst = `422` |
| `counter_missing` | Bool `true`/`false`; zajedno s numeričkim Counterima = OR | Nevaljani bool = `422` |
| `block_icons`, `rarities`, `variants`, `sets` | Isti konkretni printing mora zadovoljiti sve ove filtere; OR unutar jedne kategorije | Kombinacija pronađena samo na **različitim** printinzima = nema rezultata |
| `sets` i `search` | Podržani `OP-01`/`OP01`, `EB-03`/`EB03`, `ST-01`/`ST01`, `PRB-01`/`PRB01` | Nepoznat set = `200` i prazan popis |
| `search` | Pretraga teksta bez razlikovanja veličine slova; `%` i `_` su doslovni znakovi, ne SQL wildcardi | Duljina >120 = `422` |
| `collection_status` | Samo `owned`, `missing`, `playset`; OR među statusima; vlasnik iz JWT-a | Nepoznat status = `422`; bez valjanog JWT-a za osobni filter = `401` |
| `limit`, `offset` | `1<=limit<=100`, `offset>=0`; stabilan poredak | Nedopuštene granice = `422` |

**Napomena o dizajnu:** Neprimjenjiva/nepostojeća **tekstualna vrijednost filtera** vraća prazni rezultat i `200`, a **neispravni tipovi/rangovi i nepoznate enum vrijednosti** vraćaju `422`. Za tražilicu je takvo ponašanje predvidljivo i nije isto što i validacija upisnih JSON zahtjeva.

## Regresijski testovi

Nova datoteka: `api/tests/test_catalog_filter_matrix_11b1.py`.

- 71 dodatni test (parametrizirani slučajevi), na umjetnom katalogu s OP01/OP02/EB03/ST01/PRB01/DON setovima i višebojnim kartama.
- Tekstualni filteri, rubni razmaci i case-insensitive ponašanje.
- OR unutar kategorije / AND između kategorija; bez dupliciranja osnovnih karata.
- Više fizičkih izdanja iste karte i zabrana miješanja uvjeta s različitih printinga.
- Alias setova i escapiranje `%` i `_` u `search`.
- Razlika `NULL`, `0`, `1000`, `2000`.
- Osobni `owned` / `missing` / `playset`, usporedba više korisnika i filter po odgovarajućem printingu.
- Stabilna paginacija i ukupan broj podudaranja.
- HTTP `422` prije pozivanja repozitorija za nevaljane query parametre.
- Jednakost numeričkog Counter dropdowna i dopuštenih vrijednosti u OpenAPI-ju.

Postojeći test `test_cards_filters_api.py` ažuriran je samo za novi ugovor Counter dropdowna.

**Lokalna provjera:** ciljana matrica ima `71 passed`, povezani testovi numeričkih granica i opcija filtera `31 passed`, a puni skup `393 passed`. `ruff check .` i `ruff format --check .` prolaze bez grešaka. Testovi koriste izolirane/mokirane baze gdje je tako navedeno i nisu dokaz da podaci u stvarnom katalogu pokrivaju sve setove ili varijante.

## Lokalna provjera (PowerShell)

Pokrenuti iz `api/`:

```powershell
python -m ruff format app/services/card_service.py app/schemas/card.py tests/test_cards_filters_api.py tests/test_catalog_filter_matrix_11b1.py
python -m ruff check .
python -m ruff format --check .
python -m pytest tests/test_catalog_filter_matrix_11b1.py -q
python -m pytest tests -q
alembic current
```

Potvrđeno: 71 test u ciljanoj matrici, 393 ukupno i Ruff bez grešaka. Alembic ostaje `004 (head)`; ovaj korak ne uvodi migraciju.

## Swagger: ručna provjera

- `GET /cards/filters` → `counter_values` mora biti `[0, 1000, 2000]`.
- `GET /cards?counter_values=1000&counter_values=2000` → `200`, samo odgovarajući Counteri.
- `GET /cards?counter_values=none` → `422` s `code=validation_error`.
- `GET /cards?counter_missing=true` → `200`, karte s SQL `NULL` Counterom.
- `GET /cards?sets=OP-01` i `GET /cards?sets=op01` → isti broj rezultata (za identične uvjete).
- `GET /cards?sets=PRB01&variants=manga` → samo izdanje koje u istom printingu odgovara objema vrijednostima.
- `GET /cards?colors=red&colors=yellow&costs=1` → OR za boje, AND za cost.
- Osobni `collection_status=owned` bez JWT-a → `401`; s JWT-om samo vlastita kolekcija.

## Sljedeći korak

**11B.2** — sigurnost, CRUD kolekcija, Excel import i posudbe (rubni i konkurentni zahtjevi). Nakon 11B.3 završna revizija Swaggera i HTTP dokumentacije, pa PR u `main`.
