# One Piece TCG — Collection Tracker

Studentski projekt za kolegij **Programiranje za web**. Aplikacija omogućuje pregled i filtriranje zajedničkog kataloga One Piece TCG karata te vođenje **osobne kolekcije za svakog korisnika**. Backend se razvija postupno uz FastAPI, PostgreSQL i automatizirane testove; Vue frontend slijedi kasnije.

> **Stanje 17. 11. 2026. — predaja backenda.** Revizija backenda spojena je u `main` kroz PR #8. Obuhvaća API validaciju, straničenje kolekcije i posudbi te PostgreSQL provjere migracija, zaključavanja i rollbacka. Prošla su sva 502 testa, uključujući 12 PostgreSQL testova.

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
| 09B | API posudbi, dostupnost i djelomična vraćanja | ✅ |
| 10A | Statistika kolekcije i playsetova (read-only API) | ✅ |
| 10B | Filteri `owned`, `missing`, `playset` i aliasi setova | ✅ Spojeno u `main` |
| 11A.1 | Numerički filteri, Counter dropdown i Ruff cleanup | ✅ Lokalno provjereno; commitano |
| 11A.2 | Stroga validacija JSON zahtjeva | ✅ Lokalno provjereno |
| 11A.3 | Provjera HTTP kodova i poruka | ✅ Lokalno provjereno |
| 11B.1 | Regresijska provjera filtera kataloga | ✅ Lokalno provjereno: 71 ciljani / 393 ukupno |
| 11B.2A | Autentikacija, autorizacija i vlasništvo | ✅ Lokalno provjereno: 32 nova / 425 ukupno |
| 11B.2B | CRUD osobne kolekcije i konkurentnost | ✅ Lokalno provjereno: 7 novih / 432 ukupno |
| 11B.2C | Excel import | ✅ Lokalno provjereno: 9 novih / 441 ukupno |
| 11B.2D | Posudbe | ✅ Lokalno provjereno: 7 novih / 448 ukupno |
| 11B.3 | API rute, Swagger/OpenAPI i HTTP ugovor | ✅ Lokalno provjereno: 8 novih / 456 ukupno |
| 11C.1 | Trajna izolirana PostgreSQL testna baza | ✅ Potvrđene 3 provjere i ciklus `004 → 003 → 004` |
| 11C.2 | Paralelne transakcije, zaključavanje i rollback | ✅ Provjereni planirani scenariji na `db_test` |
| Kasnije | DON!!/varijante, Vue frontend, objava | Planirano |

## Tehnologije

- **Backend:** Python, FastAPI, Pydantic, Uvicorn
- **Baza:** PostgreSQL 16 (Docker), SQLAlchemy 2.0, Alembic
- **Autentikacija:** bcrypt, JWT access/refresh tokeni
- **Uvoz podataka:** CSV, `openpyxl`, `python-multipart`
- **Testiranje:** pytest, Ruff, Swagger UI
- **Frontend (plan):** Vue 3, Vite, TypeScript

## Lokalno pokretanje (Windows PowerShell)

Preduvjeti su Docker Desktop, Python 3.11+ i `uv`. Naredbe za prvo
postavljanje pokreni iz korijena kloniranog repozitorija.

**Prvo postavljanje**

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
docker compose up -d db
docker compose exec db pg_isready
cd api
uv venv
.\.venv\Scripts\Activate.ps1
uv pip install -r requirements-dev.txt
python -m alembic upgrade head
python -m app.seed
python -m pytest -m "not postgres" -q tests
python -m uvicorn app.main:app --reload
```

`pg_isready` treba javiti da PostgreSQL prihvaća veze prije pokretanja
migracija. Seed popunjava početne setove i rječnike. Za popunjen katalog slijedi
upute za [CSV uvoz](#podaci-kataloga-i-kolekcije).

- Swagger: <http://127.0.0.1:8000/docs>
- Health: <http://127.0.0.1:8000/health>
- PostgreSQL: `127.0.0.1:5433` (kontejner koristi `5432`)

**Ponovno pokretanje** iz korijena repozitorija

```powershell
docker compose up -d db
cd api
.\.venv\Scripts\Activate.ps1
python -m uvicorn app.main:app --reload
```

Kad preuzmeš novu migraciju, iz `api/` pokreni `python -m alembic upgrade head`.
Za puni testni prolaz koristi [zasebni PostgreSQL servis](docs/KORAK_11C1_POSTGRES_TEST_BAZA.md).

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

Dostupni su filteri za boju, tip, cijenu (`costs` 0–10), snagu (`powers` 0–13000), atribut, Counter, blok, keyword, archetype, set, rijetkost i varijantu. Filteri za set, rarity, variant i block primjenjuju se na **isto fizičko izdanje**. **Counter dropdown** (`counter_values`) prihvaća samo `0`, `1000` i `2000`; za karte bez tiskane Counter vrijednosti (`NULL`) koristi se zaseban `counter_missing=true`. `counter_values=none` više nije podržan i vraća `422`. Counter `0` nije isto što i `NULL` niti keyword `[Counter]`.

Za više vrijednosti ponovi isti query parametar (npr. `colors=red&colors=yellow`). `GET /cards` vraća osnovne karte, dok osobna statistika broji fizička izdanja.

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
       COUNT(*) FILTER (WHERE quantity > 0) AS razlicitih_izdanja,
       COALESCE(SUM(quantity) FILTER (WHERE quantity > 0), 0) AS ukupno_primjeraka
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

**Dalje:** zasebna prazna PostgreSQL testna baza obavezan je završni dio backend revizije za stvarne paralelne transakcije, zaključavanje i rollback. Postojeća baza s osobnom kolekcijom ne smije se koristiti. Tek nakon backend cjeline planirati Vue frontend; dopune DON!! i alternativnih izdanja ostaju zasebni zadaci.

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

Na kraju svakog testiranog koraka ažuriramo dokumentaciju te radimo **commit i push**. Pull Request u `main` radimo po završetku funkcionalne cjeline. Koraci 10A i 10B završeni su i spojeni u `main`; backend reviziju 11A/11B radimo na branchu `fix/backend-validation`.

Prije commita provjeriti `git status`, `git diff --cached --stat` i `git diff --cached --check`; nikad ne commitati `.env`, tajne, osobne `.xlsx`, `backups/`, preuzete snapshotove ni `.venv/`.

Detalji posudbi: `docs/KORAK_09A_MODEL_POSUDBI.md` i `docs/KORAK_09B_API_POSUDBI.md`. Korak 10A: `docs/KORAK_10A_STATISTIKA_KOLEKCIJE.md`. Korak 10B: `docs/KORAK_10B_FILTERI_KOLEKCIJE.md`. Korak 11A.1: `docs/KORAK_11A1_NUMERICKI_FILTERI.md` i `docs/KORAK_11A_RUFF_CLEANUP.md`.

### Backend revizija — Ruff cleanup

- Provedeno formatiranje i sređivanje Python koda.
- Ispravljeni neiskorišteni importi i varijable.
- Ispravljene tipne reference SQLAlchemy modela pomoću TYPE_CHECKING.
- Ispravljen redoslijed importa i predugački retci.
- Ruff check: 0 grešaka.
- Ruff format: sve datoteke pravilno formatirane.
- Pytest: 243 uspješna testa.

Ruff cleanup završen je prije Koraka 11A.2. Stroga validacija 11A.2 i ugovor HTTP kodova/poruka 11A.3 naknadno su lokalno potvrđeni punim regresijskim skupom.

### Korak 11A.2 — stroga validacija JSON zahtjeva

- Svi request-body modeli za autentikaciju, kolekcije i posudbe odbijaju nepoznata JSON polja (`extra="forbid"`).
- ID-jevi i količine u zahtjevima za kolekciju/posudbe moraju biti stvarni cijeli brojevi; stringovi, decimalni brojevi i `true`/`false` nisu dopušteni kao zamjena.
- Prazne napomene nisu dopuštene: `note=null` služi za brisanje; izostavljeno polje kod `PATCH` ostaje nepromijenjeno.
- JSON datumi posudbi moraju biti ISO 8601 stringovi s vremenskom zonom. Ime osobe ne smije biti prazno.
- Neispravni zahtjevi vraćaju `422` i `code="validation_error"`, bez poziva servisa.
- Regresijski testovi: `api/tests/test_request_body_validation.py`. Detalji: `docs/KORAK_11A2_STROGA_JSON_VALIDACIJA.md`.
- Nema nove migracije; Alembic ostaje na `004 (head)`.

**Stanje provjere 11A.2 i 11A.3:** uključeni su u aktualni puni lokalni regresijski skup; stroga validacija, sigurni HTTP odgovori i Ruff provjere prolaze. Alembic ostaje `004 (head)`.

### Korak 11B.1 — regresija filtera kataloga

- `counter_values` prihvaća samo `0`, `1000` i `2000`; OpenAPI prikazuje isti enum.
- Nedostajući tiskani Counter bira se s `counter_missing=true`; stari `counter_values=none` i vrijednosti izvan dropdowna vraćaju `422` prije repozitorija.
- Potvrđeno lokalno: ciljna matrica 71/71, puni suite 393/393, Ruff check i format check bez grešaka.
- Detalji: `docs/KORAK_11B1_REGRESIJA_FILTERA.md`.

### Korak 11B.2A — autentikacija, autorizacija i vlasništvo

- Proširena je regresijska matrica registracije, prijave, access/refresh tokena, isteka i izmjene JWT-a te nepostojećih i deaktiviranih korisnika.
- Potvrđeno je da se administratorska uloga čita iz aktualnog zapisa baze, a administrator nema automatski pristup tuđoj osobnoj kolekciji.
- Promjena `user_id` u URL-u ili queryju ne može zaobići vlasništvo; osobni filteri koriste samo identitet iz JWT-a.
- Nova matrica ima 32 izolirana testa; puni suite ima 425 prolaznih testova, a Ruff provjere prolaze. Detalji su u `docs/KORAK_11B2A_AUTORIZACIJA.md`.

### Korak 11B.2B — CRUD osobne kolekcije

- Ponovno su provjereni POST, GET, PATCH i DELETE ugovori, granice količine, parcijalne izmjene, vlasništvo i zaštita aktivnih posudbi.
- Dodatno su potvrđeni DB unique constraint i sigurni `409` fallback za istodobno stvaranje duplikata te PostgreSQL `FOR UPDATE` u PATCH/DELETE putu.
- Ispravljen je race pri DELETE-u: ako zapis nestane prije zaključavanja, API vraća kontrolirani `404` bez loan upita ili ponovnog brisanja.
- SQLite/mock testovi ne dokazuju stvarno raspoređivanje paralelnih PostgreSQL transakcija; potrebni scenariji i postojeća “zadnji commit pobjeđuje” PATCH semantika dokumentirani su zasebno.
- Dodano je sedam izoliranih regresijskih testova; ciljna cjelina ima 99, puni suite 432 prolazna testa, a Ruff provjere prolaze. Detalji: `docs/KORAK_11B2B_CRUD_KOLEKCIJE.md`.

### Korak 11B.2C — Excel import

- Ponovno su provjereni vlasništvo, `.xlsx` validacija, preview/apply ugovor, `replace`/`add`, napomene, stale stanje i zaštita aktivnih posudbi.
- `plan_token` je vezan uz datoteku, način, korisnika i relevantno stanje; nije JWT i nema vremenski rok u aktualnom API ugovoru.
- Dodatno su provjereni oštećeni upload bez curenja detalja, izmijenjeni token, promjena kolekcije između previewa i applyja, ponovljeni svježi `add`, DON!! bez ID-a te redoslijed `FOR UPDATE → loan upit`.
- SQLite/mock testovi ne dokazuju stvarno raspoređivanje paralelnih PostgreSQL transakcija; potrebni integracijski scenariji dokumentirani su u `docs/KORAK_11B2C_EXCEL_IMPORT.md`.
- Dodano je devet regresijskih testova, uključujući HTTP tok `preview → promjena kolekcije → apply starim tokenom`; ciljana cjelina ima 61, puni suite 441 prolazni test, a Ruff provjere prolaze.

### Korak 11B.2D — posudbe

- Ponovno su provjereni vlasništvo, `lent`/`borrowed`, raspoloživost, filtri, detalji printinga, UTC datumi te djelomični i potpuni povrati.
- Dodatno su provjereni zajednički limit više aktivnih posudbi, oslobađanje raspoloživosti nakon povrata, owner-scope stvarnog SQL upita i uzastopni povrati bez prekoračenja.
- Potvrđeni su PostgreSQL `FOR UPDATE` upiti za vlasnički redak pri stvaranju i za loan redak pri povratu, uz redoslijed `owned_lock → outstanding`.
- SQLite/mock testovi ne dokazuju stvarno blokiranje paralelnih PostgreSQL transakcija; obavezni scenariji za zasebnu trajnu testnu bazu dokumentirani su u `docs/KORAK_11B2D_POSUDBE.md`.
- Dodano je sedam regresijskih testova; ciljana cjelina ima 116, puni suite 448 prolaznih testova, a Ruff provjere prolaze.

### Korak 11B.3 — API rute, Swagger/OpenAPI i HTTP ugovor

- Generirana OpenAPI shema uspoređena je sa svih 20 registriranih aplikacijskih operacija, njihovim metodama, parametrima, request/response modelima i statusnim kodovima.
- Swagger sada razlikuje potpuno javne rute, privatne bearer rute i uvjetno autentificirani `GET /cards`; `Authorize` koristi JWT bearer access token.
- Dokumentirani su kontrolirani odgovori `401`, `403`, `404`, `409`, `413` i `422`, uključujući stvarni oblik `validation_error` odgovora s poljima `code`, `message` i `errors`.
- Excel preview/apply dobili su eksplicitne response modele, a dokumentirani su i `plan_token`, načini `replace`/`add`, osobni filtri, Counter opcije te vremenske zone posudbi.
- Dodano je osam ciljnih OpenAPI testova; puni suite ima 456 prolaznih testova. Detalji: `docs/KORAK_11B3_OPENAPI_REVIZIJA.md`.

U koraku **11C** uvedeni su zasebna PostgreSQL testna baza, automatsko postavljanje sheme i testovi paralelnih transakcija.

### Korak 11C.1 — izolirana PostgreSQL testna baza

- Compose profil `test` dodaje servis `db_test` na `127.0.0.1:5434`, bazu `optcg_test`, korisnika `optcg_test_user` i zaseban volume `pgdata_test`; postojeći `db` na portu 5433 nije promijenjen.
- PostgreSQL testovi čitaju isključivo eksplicitni `TEST_DATABASE_URL`, bez fallbacka na razvojni `DATABASE_URL`.
- Prije migracije ili upisa provjeravaju se driver, host, port, korisnik i naziv iz URL-a; svi URL query parametri su zabranjeni. Na stvarnoj konekciji dodatno se provjeravaju naziv baze, korisnik, interni port, PostgreSQL verzija i `cluster_name=optcg_test_11c`.
- Alembic u testnom načinu otvara eksplicitnu vanjsku transakciju te na istoj konekciji provjerava identitet i izvršava migracije. Uspjeh commitira cijeli blok, a pogreška ili nevaljan identitet uzrokuju rollback prije djelomične primjene; testne offline migracije nisu dopuštene.
- `python -m app.prepare_test_database` primjenjuje postojeće Alembic migracije do `004 (head)` tek nakon sigurnosnih provjera.
- Obični SQLite/mock testovi ne zahtijevaju Docker. PostgreSQL testovi imaju marker `postgres`; obični suite ih bez testne varijable preskače, dok eksplicitni režim `POSTGRES_TEST_REQUIRED=1` nedostajuću konfiguraciju ili nedostupnu bazu tretira kao failure.
- Na lokalnom `db_test` potvrđen je ciklus migracija `004 → 003 → 004`. Nakon ponovnog upgradea prošla su sva tri početna PostgreSQL testa.
- Nakon 11C.2 puni skup ima `502 passed`, uključujući 12 PostgreSQL testova.
- Potpune naredbe i sigurnosni ugovor opisani su u `docs/KORAK_11C1_POSTGRES_TEST_BAZA.md`.
