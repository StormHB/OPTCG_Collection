# Korak 11C.1 — trajna izolirana PostgreSQL testna baza

Datum: 16. 11. 2026. Branch: `fix/backend-validation`.

## Arhitektura

Razvojni servis ostaje nepromijenjen: `db`, baza `optcg`, host port `5433` i volume `pgdata`. Testna infrastruktura dodaje potpuno odvojeni servis:

| Postavka | Vrijednost |
| --- | --- |
| Compose servis | `db_test` |
| Profil | `test` |
| Slika | `postgres:16` |
| Baza | `optcg_test` |
| Korisnik | `optcg_test_user` |
| PostgreSQL `cluster_name` | `optcg_test_11c` |
| Host adresa | `127.0.0.1:5434` |
| Docker volume | `pgdata_test` |

Profil sprječava pokretanje testne baze pri običnom `docker compose up`. Servis i volume nemaju vezu s razvojnim servisom ili njegovim podacima.

## Fail-closed zaštite

PostgreSQL fixtureovi ne čitaju `DATABASE_URL`. Zahtijevaju zaseban `TEST_DATABASE_URL`. Obični suite bez njega preskače označene PostgreSQL testove, tako da SQLite/mock testovi ne zahtijevaju Docker. Eksplicitni režim postavlja `POSTGRES_TEST_REQUIRED=1`; tada nedostajući URL ili nedostupna baza završavaju jasnim failureom.

Prije spajanja URL mora imati točno:

- driver `postgresql+asyncpg`;
- host `127.0.0.1` ili `localhost`;
- host port `5434`;
- korisnika `optcg_test_user`;
- bazu `optcg_test`.
- bez ijednog URL query parametra; time su zatvoreni overridei poput `?port=5433`, kao i `host`, `database`, SSL i ostali neočekivani parametri.

Nakon read-only spajanja ponovno se provjeravaju stvarni `current_database()`, `current_user`, interni server port `5432`, PostgreSQL verzija 16 ili novija i `cluster_name=optcg_test_11c`. Pogreška prekida pripremu prije migracije. Razvojna konfiguracija `optcg`/`5433` zato ne može proći zaštitu.

Alembic zadržava postojeće ponašanje za razvojni rad. Samo programatski poziv iz sigurnog testnog pripremnog modula može proslijediti `test_database_url`, koji se ponovno validira u `alembic/env.py`. U testnom načinu `do_run_migrations()` otvara eksplicitni `connection.begin()` blok, provjerava identitet i izvršava Alembic na istoj konekciji. Vanjski blok commitira tek nakon uspješnog završetka svih migracija; svaka iznimka ili nevaljan identitet uzrokuju rollback. Testne offline migracije odbijaju se jer ne mogu dokazati identitet konekcije.

Migracije `001`–`004` ne koriste `autocommit_block`, `CREATE INDEX CONCURRENTLY` ni druge pronađene operacije koje bi morale izaći iz transakcije. Unit testovi potvrđuju redoslijed, istu konekciju te commit/rollback ponašanje Python context managera. Stvarnu PostgreSQL DDL transakciju i trajno upisan revision `004` mora potvrditi prvi lokalni integracijski prolaz.

## PowerShell postupak

### 1. Pokretanje samo testne baze

Iz korijena projekta:

```powershell
docker compose --profile test up -d db_test
docker compose --profile test ps db_test
```

Ovo ne pokreće, ne zaustavlja i ne migrira razvojni servis `db`.

### 2. Testna konfiguracija za trenutni terminal

Ne mijenjaj postojeći `.env`. U terminalu postavi zasebnu varijablu:

```powershell
$env:TEST_DATABASE_URL = "postgresql+asyncpg://optcg_test_user:local_optcg_test_only_change_me@127.0.0.1:5434/optcg_test"
$env:POSTGRES_TEST_REQUIRED = "1"
```

Ako je `TEST_POSTGRES_PASSWORD` promijenjen prije prvog stvaranja testnog volumea, ista lozinka mora biti u ovom URL-u.

### 3. Automatska shema i provjera migracija

Iz `api/` direktorija, s aktivnim virtualnim environmentom:

```powershell
python -m app.prepare_test_database
python -m pytest -m postgres tests/postgres -q
```

Prva naredba provjerava identitet baze, a Alembic ga ponovno provjerava na migracijskoj konekciji prije primjene postojećih migracija do `004 (head)`. Integracijski test dodatno čita `alembic_version` i očekuje `004`. Zbog `POSTGRES_TEST_REQUIRED=1` nedostajući URL ili nedostupna baza ne mogu biti prikazani kao skip.

### 4. Obični testovi

```powershell
Remove-Item Env:TEST_DATABASE_URL -ErrorAction SilentlyContinue
Remove-Item Env:POSTGRES_TEST_REQUIRED -ErrorAction SilentlyContinue
python -m pytest tests -q
```

PostgreSQL testovi bit će preskočeni, a postojeći SQLite/mock testovi rade kao prije. Za potpuno isključivanje označenih testova može se koristiti:

```powershell
python -m pytest -m "not postgres" tests -q
```

### 5. Sigurno zaustavljanje

Iz korijena projekta:

```powershell
docker compose --profile test stop db_test
```

`stop` čuva testni volume. Ne koristiti `docker compose down -v`: ta naredba uklanja volumene i nije dio redovnog postupka.

## Početni integracijski testovi

`api/tests/postgres/test_postgres_infrastructure.py` provjerava:

1. stvarnu vezu, PostgreSQL 16+, `optcg_test` i `optcg_test_user`;
2. Alembic revision `004`;
3. izolirani `INSERT`/`SELECT`, rollback i potvrdu da testni red nije ostao u bazi.

`api/tests/test_test_database_safety.py` bez Docker ovisnosti provjerava prihvat točne konfiguracije te odbijanje nedostajućeg URL-a, razvojne baze/porta/korisnika, pogrešnog hosta ili drivera, svih URL query parametara, pogrešnog `cluster_name` i neočekivanog stvarnog identiteta baze. Provjerava i obavezni režim, identifikacijski upit nad točno proslijeđenom migracijskom konekcijom, commit nakon uspjeha, rollback nakon iznimke te zaustavljanje prije migracijskog callbacka kada identitet nije valjan.

## Početna provjera bez Dockera

- sigurnosni unit testovi: `21 passed`;
- PostgreSQL test collection bez `TEST_DATABASE_URL`: `3 skipped`;
- puni standardni backend suite: `477 passed, 3 skipped`;
- `ruff check .` i `ruff format --check .`: prolaze; 98 Python datoteka pravilno je formatirano;
- namjerno zadani razvojni URL `optcg`/`5433` odbijen je prije pokušaja spajanja;
- Docker CLI nije dostupan, pa stvarna veza, migracije i PostgreSQL testovi ovdje nisu izvršeni niti se tvrdi da su prošli;
- portovi 5433 i 5434 u trenutku provjere nisu imali lokalni listening socket.

## Lokalna potvrda 17. 11. 2026.

Na `db_test` prošao je ciklus `004 → 003 → 004` i nakon njega sva tri testa 11C.1. Pet novih testova 11C.2 provjerava dvije paralelne posudbe, dva paralelna povrata te novu posudbu uz istodobni PATCH količine, DELETE ili Excel apply. Testovi potvrđuju čekanje preko `pg_blocking_pids()` i provjeravaju spremljene količine nakon odbijene operacije. Puni skup, uključujući osam PostgreSQL testova, ima **498 prolaznih testova**.

## Završne provjere 11C.2

- PATCH same napomene zaključava redak prije izmjene. Ako je istodobni DELETE već uklonio redak, PATCH vraća `404 not_found`.
- Excel apply vraća `409 stale_import_preview` kad istodobni PATCH promijeni polje iz plana ili DELETE ukloni redak.
- Prisilna PostgreSQL greška nakon dva uspješna upisa povlači i izmjenu količine i kreiranu posudbu.
- Puni skup ima **502 prolazna testa**, uključujući **12 PostgreSQL testova**.

Postojeća razvojna baza s osobnom kolekcijom ne smije se koristiti ni u jednom od tih testova.
