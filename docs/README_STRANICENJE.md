# Straničenje kolekcije i posudbi

Zahtjev za predaju backenda traži `limit` i `offset` na popisima. Oba parametra sada su dostupna u Swaggeru na rutama `GET /collections/{user_id}` i `GET /collections/{user_id}/loans`.

| Parametar | Zadano | Dopuštene vrijednosti |
| --- | ---: | --- |
| `limit` | 50 | 1–100 zapisa |
| `offset` | 0 | 0–2.147.483.647 preskočenih zapisa |

Poziv bez parametara vraća **prvih 50 zapisa** u postojećem formatu JSON niza. Za sljedeću stranicu povećaj `offset` za `limit`. Kad je `offset` iza kraja rezultata, API vraća `200` i `[]`. Nevaljani parametri vraćaju `422` s kodom `validation_error`. Gornja granica za `offset` odgovara PostgreSQL tipu `INTEGER` kojim asyncpg veže taj parametar.

```http
GET /collections/7?limit=20&offset=0
GET /collections/7?limit=20&offset=20
GET /collections/7/loans?direction=lent&active_only=true&limit=20&offset=20
```

Prvo se provjerava vlasništvo. SQL upit ograničava rezultate na vlasnika i, kod posudbi, primjenjuje `direction` i `active_only` prije straničenja. Kolekcija je sortirana po ID-u uzlazno. Posudbe su sortirane po datumu posudbe silazno, pa po ID-u silazno kad je datum isti.

## Provjera

HTTP testovi pokrivaju prosljeđivanje parametara, nevaljane vrijednosti i pristup tuđim zapisima. SQLite testovi pokrivaju dvije uzastopne stranice i prazan rezultat izvan raspona, uz odvajanje vlasnika i primjenu filtera posudbi.

Rezultat provjere je **488 prolaznih testova**, uz 3 izdvojena PostgreSQL testa. Ruff provjera i provjera formatiranja prošle su za svih 10 izmijenjenih Python datoteka.

Iz direktorija `api/` pokreni:

```powershell
python -m pytest -m "not postgres" -q tests
```
