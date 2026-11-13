# One Piece TCG — Collection Tracker

Studentski projekt za kolegij **Programiranje za web**. Aplikacija omogućuje pregled i filtriranje zajedničkog kataloga One Piece TCG karata te vođenje **osobne kolekcije za svakog korisnika**. Backend se razvija postupno uz FastAPI, PostgreSQL i automatizirane testove; Vue frontend slijedi kasnije.

> **Stanje: 13. 11. 2026. — Korak 10B u provjeri.** Autentikacija, katalog, Excel import i posudbe završeni su; Korak 10A potvrđen je na stvarnoj kolekciji (2.133 primjerka, 662 izdanja, 285 playsetova). Korak 10B dodaje osobne filtere na javni katalog. Nakon lokalnih testova, Swagger provjere, commita i pusha slijedi PR za `feat/collection-stats`.

## Napredak

| Korak | Funkcionalnost | Status |
| --- | --- | --- |
| 01–02 | FastAPI, Docker/PostgreSQL, SQLAlchemy, Alembic `001`, seed | ✅ |
| 03–04 | JWT autentikacija, uloge i provjera vlasništva, migracija `002` | ✅ |
| 05–06 | Katalog, rječnici, M:N veze, filteri i migracija `003` | ✅ |
| 07 | Dopuna metapodataka kataloga | ✅ |
| 08A | CRUD osobne kolekcije | ✅ |
| 08B | Excel import (`preview` / `apply`) | ✅ |
| 09A | Model posudbi i migracija `004` | ✅ |
| 09B | API posudbi, dostupnost i djelomična vraćanja | ✅ 180 testova i ručne provjere |
| 10A | Statistika kolekcije i playsetova (read-only API) | ✅ SQL i Swagger provjereni |
| 10B | Filteri `owned`, `missing`, `playset` | Implementirano; testovi i Swagger na lokalnom projektu prije commita |
| Dalje | DON!!/varijante, Vue frontend, završno testiranje i objava | Planirano |

## Tehnologije

- **Backend:** Python, FastAPI, Pydantic, Uvicorn
- **Baza:** PostgreSQL 16 (Docker), SQLAlchemy 2.0, Alembic
- **Autentikacija:** bcrypt, JWT access/refresh tokeni
- **Uvoz podataka:** CSV, `openpyxl`, `python-multipart`
- **Testiranje:** pytest, Ruff, Swagger UI
- **Frontend (plan):** Vue 3, Vite, TypeScript

## Lokalno pokretanje (Windows PowerShell)

Preduvjeti: Docker Desktop, Python, `uv` i pripremljen `.env` (prema `.env.example`). **Ne prepisivati postojeći `.env`.**

**Terminal 1 — Docker i API:**

```powershell
cd C:\Users\admin\OPTCG_Collection
docker compose up -d db
docker compose ps
cd api
.\.venv\Scripts\Activate.ps1
python -m uvicorn app.main:app --reload
```

- Swagger: <http://127.0.0.1:8000/docs>
- Health: <http://127.0.0.1:8000/health>
- PostgreSQL: `127.0.0.1:5433` (kontejner koristi `5432`)

**Terminal 2 — testovi i migracije:**

```powershell
cd C:\Users\admin\OPTCG_Collection\api
.\.venv\Scripts\Activate.ps1
python -m pytest tests -q
alembic current
```

Za novo postavljanje okruženja (ne za svaki restart): u mapi `api/` napraviti `uv venv` te instalirati `uv pip install -r requirements.txt` i `uv pip install -r requirements-dev.txt`. `alembic upgrade head` izvršava se kada postoji nova migracija; seed se pokreće prema potrebi (`python -m app.seed`).

Zaustavljanje: `Ctrl+C` za Uvicorn; iz korijena projekta `docker compose stop` za bazu. **Ne koristiti `docker compose down -v`** za uobičajeno zaustavljanje jer briše podatkovne volumene.

## Baza podataka

| Tablica/skup tablica | Namjena |
| --- | --- |
| `users` | Korisnici, uloge i aktivnost računa |
| `card_sets`, `cards`, `card_printings` | Setovi, osnovne karte i konkretna izdanja |
| `collection_entries` | Osobne količine i napomene po `user_id` + `printing_id` |
| `colors`, `attributes`, `archetypes`, `keywords` | Rječnici vrijednosti filtera |
| `card_colors`, `card_attributes`, `card_archetypes`, `card_keywords` | M:N veze karata i rječnika |
| `printing_external_ids` | Vanjski identifikatori izdanja |
| `card_loans` | Posudbe po korisniku i točnom izdanju; aktivne i vraćene količine |

Migracije:

- `001` — početna struktura baze
- `002` — `users.is_active`
- `003` — rječnici, M:N veze, vanjski identifikatori i dodatna polja kataloga
- `004` — `card_loans` (primijenjena)

`card_loans` sadrži vlasnika evidencije (`user_id`), točno izdanje (`printing_id`), smjer `lent`/`borrowed`, osobu, početnu i vraćenu količinu, datume i napomenu. Baza provjerava pozitivan broj posuđenih karata, dozvoljen smjer i da vraćena količina ne prelazi početnu. Datumi su tipa `timestamp with time zone`. API koristi `AwareDatetime`, a sve datume na backendu normalizira na UTC.

## API

Za popis ruta i primjere zahtjeva koristi Swagger. Trenutačno su implementirane:

| Metoda | Ruta | Namjena |
| --- | --- | --- |
| `GET` | `/health` | Provjera rada |
| `POST` | `/auth/register`, `/auth/login`, `/auth/refresh` | Autentikacija |
| `GET` | `/auth/me` | Prijavljeni korisnik |
| `GET` | `/admin/users` | Administratorski pregled |
| `GET` | `/cards`, `/cards/filters`, `/cards/{id}` | Katalog, filteri i detalji |
| `GET` | `/collections/{user_id}` | Osobna kolekcija |
| `GET` | `/collections/{user_id}/stats` | Statistika: ukupno, različita izdanja, playsetovi |
| `POST` | `/collections/{user_id}/entries` | Dodavanje izdanja |
| `PATCH` | `/collections/{user_id}/entries/{printing_id}` | Djelomična izmjena |
| `DELETE` | `/collections/{user_id}/entries/{printing_id}` | Brisanje |
| `POST` | `/collections/{user_id}/import/preview` | Provjera Excela bez upisa |
| `POST` | `/collections/{user_id}/import/apply` | Potvrda pregledanog uvoza |
| `GET` | `/collections/{user_id}/loans` | Posudbe, s filterima `direction` i `active_only` |
| `POST` | `/collections/{user_id}/loans` | Nova posudba (`lent` / `borrowed`) |
| `GET` | `/collections/{user_id}/loans/{loan_id}` | Detalji posudbe |
| `POST` | `/collections/{user_id}/loans/{loan_id}/returns` | Djelomično ili potpuno vraćanje |

**Autorizacija:** osobnu kolekciju može čitati i mijenjati njezin vlasnik; administratorska uloga sama po sebi ne dopušta uređivanje tuđe kolekcije. Za zaštićene rute koristi se JWT access token.

**Filtriranje:** više vrijednosti unutar iste kategorije kombinira se s **OR**, a različite kategorije s **AND**. Primjer:

```http
GET /cards?colors=red&colors=yellow&sets=op01&limit=20&offset=0
```

Dostupni su filteri za boju, tip, cijenu, snagu, atribut, counter, blok, keyword, archetype, set, rijetkost i varijantu. Izdanje/set/rarity/variant/block moraju se podudarati na istom printingu. `counter_values=none` označava odsutnu tiskanu Counter vrijednost, ne broj `0` ili keyword `[Counter]`.

**Alias za oznake setova (10B):** filter `sets` i tekstualna pretraga `search` prihvaćaju `OP01` i `OP-01` (uključujući `op01`, `op-01` i rubne razmake). Isto vrijedi za `EB`, `ST` i `PRB` (`EB-03` = `EB03`). Baza ostaje u kanonskom formatu bez dodatne crtice, a puni kod karte poput `OP01-016` ostaje nepromijenjen.

### Osobni filteri u katalogu — Korak 10B

Postojeći `GET /cards` podržava ponovljeni query parametar `collection_status`:

| Vrijednost | Značenje |
| --- | --- |
| `owned` | Karta ima barem jedno **pozitivno** vlasničko izdanje koje odgovara odabranim filterima izdanja. |
| `missing` | Karta ima odgovarajuće izdanje, ali **nijedno takvo izdanje** nema pozitivnu vlasničku količinu. |
| `playset` | Barem jedno odgovarajuće izdanje doseže prag: Leader ≥1, DON!! ≥10, ostali ≥4. |

```http
GET /cards?collection_status=owned&search=OP01-016
GET /cards?collection_status=missing&sets=OP01
GET /cards?collection_status=playset&colors=Red&sets=OP01
GET /cards?collection_status=missing&collection_status=playset&limit=20
```

**Sigurnost:** bez osobnog filtera `GET /cards` ostaje javan. Osobni filter zahtijeva valjan JWT access token (Swagger `Authorize`) i uvijek koristi **isključivo korisnika iz JWT-a**, nikada proizvoljni `user_id` iz URL-a. Više `collection_status` vrijednosti je **OR**; kombinacija s bojama, setovima i ostalim kategorijama je **AND**. Za set, rarity, variant i block osobni status mora odgovarati **istom fizičkom izdanju**, uključujući reprintove.

**Razlika u brojkama:** `GET /cards` vraća **osnovne karte** (`cards`) bez duplikata, a `/collections/{user_id}/stats` broji **izdanja** (`printing_id`). Zato `total` za `collection_status=playset` **ne mora biti 285** čak ni kad je statistika 285, ako više dovršenih izdanja pripada istoj karti. Posudbe se ne računaju u vlasničke količine.

Detalji i ručni testovi: `docs/KORAK_10B_FILTERI_KOLEKCIJE.md`.

**CRUD kolekcije:** zapis pripada konkretnom `printing_id`. `PATCH` mijenja samo izričito poslana polja (`{"quantity": 4}` ne mijenja napomenu; `{"note": null}` briše napomenu). Nije moguće kreirati duplikat istog izdanja za istog korisnika.

### Excel import — Korak 8B

Uvoz prima `.xlsx` (najviše **6 MB**) i mijenja samo osobnu kolekciju, nikada zajednički katalog. Oba poziva zahtijevaju autorizaciju i istu datoteku.

1. `POST /collections/{user_id}/import/preview?mode=replace` provjerava izdanja i količine **bez upisa**.
2. Provjeravaju se `matched`, `create`, `update`, `error_count`, `warning_count`, `issues` i `can_apply`.
3. `POST /collections/{user_id}/import/apply?mode=replace&plan_token=...` potvrđuje isti plan. `plan_token` **nije JWT access token**.

Načini uvoza:

- `replace` — postavlja količine za izdanja iz Excela, bez brisanja ostalih zapisa.
- `add` — dodaje Excel količine postojećima; ponavljanje uvoza može dodatno povećati količine.

Za uparivanje se koriste sheet, broj karte i konkretno izdanje. Nejasne varijante i DON!! ne povezuju se nasumično. Retci s napomenom bez količine preskaču se uz upozorenje. Promijenjena datoteka ili relevantno stanje kolekcije između pregleda i potvrde uzrokuje odbijanje plana.

Detaljnije u: `docs/KORAK_08B_EXCEL_IMPORT.md`.

### Statistika kolekcije — Korak 10A

`GET /collections/{user_id}/stats` dostupan je **isključivo vlasniku** kolekcije uz JWT access token; admin nema automatski pravo pristupa tuđoj statistici. Endpoint je samo za čitanje i ne zahtijeva novu migraciju (`004` ostaje `head`). Odgovor sadrži:

- `total_cards`: zbroj pozitivnih količina iz `collection_entries`.
- `distinct_printings`: broj različitih **fizičkih izdanja** (`printing_id`) s količinom većom od nule; reprint je zasebno izdanje.
- `playsets`: broj izdanja koja su dosegla prag (najviše **jedan playset po izdanju**, čak i uz osam kopija iste obične karte).
- `playsets_by_type`: podjela playsetova na `leader`, `don` i `other` radi lakše provjere.

Pragovi: **Leader ≥1, DON!! ≥10, ostali ≥4**. Ako metapodatak `card_type` nedostaje, Leader se prepoznaje i po rijetkosti `L`, a DON!! po tipu, oznaci seta `DON` ili kodu koji počinje `DON-`. Količine `0` ne povećavaju nijednu statistiku. Posudbe (`lent` ili `borrowed`) **ne mijenjaju vlasničku statistiku**.

Detaljne provjere, SQL upit i testni scenariji: `docs/KORAK_10A_STATISTIKA_KOLEKCIJE.md`.

## Podaci kataloga i kolekcije

**Zajednički katalog:** početni CSV uvoz sadržavao je **2.847 osnovnih karata** i **3.111 izdanja**; za **2.785 karata** dopunjeni su metapodaci iz provjerenog Koala Kollect snapshota (22. 10. 2026.). Njih 62 nisu bila obuhvaćena tom dopunom. Potpunost novijih setova, Alt/Manga i DON!! izdanja još treba provjeriti.

**Osobni Excel — referentno stanje nakon uvoza:**

| Metrika | Vrijednost |
| --- | ---: |
| Ukupno primjeraka | **2.133** |
| Različitih izdanja | **662** |
| Playsetova prema Excelu (staro pravilo ≥4 za sve) | **243** |
| Playsetova prema backendu (Leader ≥1, DON!! ≥10, ostali ≥4) | **285** |

Excel preview je prepoznao svih 662 unosa bez grešaka; upozorenja su se odnosila na napomene bez količine (OP15 i OP18). `apply` s `mode=replace` uspješno je proveden. **Backend je kasnije potvrdio 285 playsetova prema pravilima aplikacije: 44 Leader, 0 DON!!, 241 ostalih.** Excelovih 243 potječe od starijeg praga ≥4 za sve vrste karata.

Provjera količina u PostgreSQL-u:

```sql
SELECT user_id,
       COUNT(*) AS razlicitih_izdanja,
       COALESCE(SUM(quantity), 0) AS ukupno_primjeraka
FROM collection_entries
GROUP BY user_id
ORDER BY user_id;
```

Uvoznici kataloga (iz mape `api/`; pregled bez upisa pa potvrda):

```powershell
python -m app.import_catalog --file ..\data\catalog_from_excel.csv
python -m app.import_catalog --file ..\data\catalog_from_excel.csv --apply

python -m app.enrich_catalog --download
python -m app.enrich_catalog
python -m app.enrich_catalog --apply
```

Prije većeg upisa preporučuje se sigurnosna kopija baze. Privatne Excel datoteke i backupovi ne ulaze u repozitorij.

## Poslovna pravila i sljedeći koraci

**Playset** (izračun implementiran u 10A, API filtri u 10B; vizualni prikaz planiran u Vueu):

| Vrsta | Prag |
| --- | ---: |
| Leader | `quantity >= 1` |
| DON!! | `quantity >= 10` |
| Ostale karte | `quantity >= 4` |

**Korak 9B — API posudbi:** omogućeni su pregled, unos i djelomični/potpuni povrat. Ne može se posuditi više vlastitih primjeraka nego što je raspoloživo; aktivne posudbe štite od smanjivanja količine kroz PATCH, brisanje ili Excel `replace`. Posudba **ne mijenja vlasničku količinu** u `collection_entries`; tuđe posuđene karte **ne povećavaju vlastite playsetove**. Odgovori uključuju točan `printing_id`, kod, set i URL ilustracije za budući Vue prikaz. Dokumentacija: `docs/KORAK_09B_API_POSUDBI.md`.

**Dalje:** lokalna provjera 10B, commit/push i PR `feat/collection-stats` → `main`; zatim DON!!/alternativna izdanja i Vue sučelje.

Za nove datumsko-vremenske API podatke koristimo Pydantic `AwareDatetime`, normalizaciju na UTC (`datetime.now(timezone.utc)` i `.astimezone(timezone.utc)`), a lokalnu zonu samo za prikaz.

U kasnijim koracima slijede dopuna DON!!/varijanti, Vue frontend (katalog, filteri, kolekcija, Excel upload i kompaktna lista posudbi) te završno testiranje i objava. Za javno prikazivanje Bandai ilustracija i tekstova potrebno je prethodno provjeriti prava korištenja.

## Testiranje i Git

```powershell
# Iz api/
python -m pytest tests -q
python -m ruff check .
python -m ruff format --check .
alembic current
```

Na kraju svakog testiranog koraka ažuriramo dokumentaciju te radimo **commit i push**. Pull Request u `main` radimo po završetku funkcionalne cjeline. Koraci 10A i 10B razvijaju se na branchu `feat/collection-stats`, nastalom nakon mergea `feat/card-loans` u `main`.

Prije commita provjeriti `git status`, `git diff --cached --stat` i `git diff --cached --check`; nikad ne commitati `.env`, tajne, osobne `.xlsx`, `backups/`, preuzete snapshotove ni `.venv/`.

Detalji posudbi: `docs/KORAK_09A_MODEL_POSUDBI.md` i `docs/KORAK_09B_API_POSUDBI.md`. Korak 10A: `docs/KORAK_10A_STATISTIKA_KOLEKCIJE.md`. Korak 10B: `docs/KORAK_10B_FILTERI_KOLEKCIJE.md`.
