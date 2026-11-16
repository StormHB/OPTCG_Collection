# Korak 11A — Ruff cleanup nakon revizije backenda

## Razlog

Nakon početnog `ruff check .` pronađeno je 266 upozorenja. Koraci `ruff check . --fix` i `ruff format .` smanjili su broj na **30**, a `ruff format --check .` prikazao je **84 formatirane datoteke**.

## Preostale vrste grešaka i rješenja

| Pravilo | Zašto se pojavljuje | Rješenje |
|---|---|---|
| `F821` | Modeli s odgođenim anotacijama spominju povezane ORM klase bez definiranih uvoza | `TYPE_CHECKING` importi (nema cikličkih runtime uvoza) |
| `E402` | `collection_import` i `card_loans` routeri uvezeni su na dnu `collections.py` | Uvozi premješteni na vrh, `router.include_router` ostaje na kraju |
| `E501` | Dijelovi poruka, ispisâ i docstringova prelaze 88 znakova | Tekst podijeljen u susjedne string literale s jednakom konačnom porukom |
| `F841` | U Excel testu definirana je neiskorištena varijabla `data` | Uklonjena nepotrebna dodjela |

Ispravci su ograničeni na ukupno 13 datoteka u modelima, routerima, servisima, repozitorijima i testovima. Ne mijenjaju API rute, HTTP kodove, bazu, migracije niti vlasničke količine. Nisu korišteni `--unsafe-fixes` ni globalni `noqa` ili ignoriranje Ruff pravila.

## Obavezne provjere

Iz `api/`:

```powershell
python -m ruff check .
python -m ruff format --check .
python -m pytest tests -q
alembic current
```

Cilj: oba Ruff prolaze; svi testovi prolaze; `004 (head)`. Za uklanjanje `F821` potvrđeno je i da SQLAlchemy može konfigurirati odnose između ORM modela. Posebno je važno ponoviti testove za katalog, Excel import, osobne kolekcije i posudbe.

## Sljedeći posao

Nakon commita nastavljamo s validacijskim rubnim slučajevima i standardizacijom pogrešaka, bez frontenda do sljedećeg dijela nastave.
