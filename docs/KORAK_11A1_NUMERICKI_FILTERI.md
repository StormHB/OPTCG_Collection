# Korak 11A.1 — brojčani filteri i razvojne ovisnosti

## Kontekst

Prilikom pregleda aktualnog backenda uočena su dva problema:

1. `api/requirements-dev.txt` završava nepostojećom/suvišnom stavkom `httpx2`.
2. `GET /cards` prihvaća proizvoljno velike brojčane vrijednosti. Osobito `counter_values` s više tisuća znamenki može proći osnovni regex i pri `int()` pretvorbi završiti neobrađenom iznimkom.

## Promjene

- Uklonjen `httpx2`; zadržan `httpx>=0.27`.
- `costs` prihvaća **0–10**, a `powers` **0–13 000**, u skladu s dogovorenim filterima aplikacije.
- U Koraku 11A.1 `counter_values` bio je ograničen na PostgreSQL `integer` raspon. Korak 11B.1 dodatno je uskladio HTTP ugovor s dogovorenim dropdownom: dopušteni su samo `0`, `1000` i `2000`, a SQL `NULL` bira se zasebno s `counter_missing=true`.
- Neispravne vrijednosti vraćaju HTTP **422** i postojeći oblik `{"code":"validation_error","message":...,"errors":[...]}`.
- Ponavljanje `counter_values` parametra ostaje OR; `counter_missing=true` također se OR-kombinira s odabranim brojčanim Counterima i ostaje zaseban od vrijednosti `0`.

Nisu promijenjeni ORM modeli, migracije, podaci u bazi ni poslovna pravila osobnih filtera.

## Testovi

Dodani su `api/tests/test_numeric_filter_boundaries.py` s testovima za:

- Negativne, decimalne, tekstualne i izvanrasponske vrijednosti.
- Counter s 4400 znamenki, vrijednostima izvan dropdowna i stari zapis `none`.
- Rubne dopuštene vrijednosti 0, 10, 13000 te `counter_missing=true`.
- Očuvanje više vrijednosti istog parametra (OR).
- Provjeru da nevaljan HTTP zahtjev ne poziva repozitorij.

Pokretanje iz `api/`:

```powershell
python -m pytest tests/test_numeric_filter_boundaries.py -q
python -m pytest tests -q
python -m ruff check .
python -m ruff format --check .
```

U Swaggeru `GET /cards`: `costs=10`, `powers=13000`, `counter_values=2000` i `counter_missing=true` trebaju vratiti 200, a `costs=11`, `powers=13001`, `counter_values=none` i `counter_values=3000` trebaju 422. Kod 200 nije nužno da postoji karta s tim vrijednostima; to samo znači da je oblik zahtjeva valjan.

## Sljedeći dio revizije

Korak 11A.2: odbijanje nepoznatih polja u JSON tijelima zahtjeva za upis, zajedno s odgovarajućim regresijskim testovima. Nakon toga 11A.3: semantika nepoznatih tekstualnih filtera i 413 za prevelike Excel datoteke.
