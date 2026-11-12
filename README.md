# One Piece TCG — Collection Tracker

Studentski projekt za kolegij **Programiranje za web**. Cilj aplikacije je omogućiti pregled zajedničkog kataloga One Piece TCG karata, pretraživanje i filtriranje te vođenje **zasebne osobne kolekcije za svakog korisnika**. Projekt se razvija postupno, prema predavanjima, uz FastAPI, PostgreSQL, automatizirane testove i Git feature brancheve. Vue frontend slijedi u kasnijoj fazi.

> **Stanje: 12. 11. 2026. — nakon Koraka 8B.** Implementirani su autentikacija, autorizacija, javni API kataloga, višestruki filteri, CSV uvoz, dopunjavanje metapodataka, **CRUD osobne kolekcije (8A)** i **uvoz osobnog Excela s pregledom prije upisa (8B)**. U lokalnoj bazi nalazi se **2.847 jedinstvenih karata i 3.111 izdanja**; metapodaci za **2.785 karata** dopunjeni su iz Koala Kollect snapshota. Korisnički Excel uspješno je pregledan i primijenjen; njegovo referentno stanje je **2.133 primjerka, 662 različita izdanja i 243 playseta prema Excelu**. **Posudbe, potpuni DON!! katalog i Vue frontend još nisu implementirani.**

## Razvoj po predavanjima

- [x] **01 — Kostur aplikacije:** FastAPI, Uvicorn, konfiguracija, PostgreSQL u Dockeru, `/health` i Swagger UI.
- [x] **02 — Baza i migracije:** SQLAlchemy modeli, Alembic `001`, početni seed setova.
- [x] **03 — Autentikacija:** Alembic `002`, bcrypt, JWT access/refresh, registracija i prijava.
- [x] **04 — Autorizacija:** uloge `admin`/`user`, provjera vlasništva i zaštićene rute.
- [ ] **05–06 — Katalog, CRUD i poslovna pravila (u tijeku):** migracija `003`, rječnici, M:N veze, API kataloga, filtriranje, CSV uvoz, dopuna metapodataka, CRUD kolekcije **(8A)** i Excel import **(8B) odrađeni**; posudbe, DON!! i dio poslovnih pravila **preostaju**.
- [ ] **07–10 — Vue frontend:** vizualni katalog, pretraživanje, filteri, osobna kolekcija, Excel upload i posudbe.
- [ ] **11–12 — Završno testiranje i objava:** end-to-end provjere, produkcijska konfiguracija i hosting.

## Trenutačno implementirano

- JWT autentikacija i autorizacija; obični korisnik može pristupiti samo vlastitoj kolekciji, a administratorska ruta ograničena je na ulogu `admin`.
- Javni `GET /cards` s paginacijom, pretragom i kombiniranjem filtera; `GET /cards/{id}` s detaljima i izdanjima; `GET /cards/filters` s ponuđenim vrijednostima.
- **OR unutar kategorije, AND između kategorija**, pretraga bez razlikovanja velikih i malih slova te uklanjanje duplikata kod višestrukih podudaranja.
- Zajednički katalog iz CSV-a te dopunjavanje karakteristika karata iz provjerenog Koala Kollect snapshota, bez mijenjanja korisničkih količina.
- **Osobna kolekcija — Korak 8A:** dodavanje, pregled, djelomično uređivanje (`PATCH`) i brisanje zapisa za konkretno izdanje (`printing_id`); provjere pristupa, validacije i duplikata.
- **Excel import — Korak 8B:** autorizirani `.xlsx` upload, `preview` bez upisa, kontrolirani `apply` s `plan_token`, načini `replace` i `add`, prepoznavanje izdanja, prijava grešaka i upozorenja prije uvoza.
- Automatizirani testovi za katalog, filtriranje, ponovljivi uvoz, korisničke ovlasti i CRUD.

**Ograničenja:** lokalni katalog još nije potpuno ažuran ni ujednačen za sve buduće setove i sve varijante ilustracija; **62 početne karte nisu obuhvaćene zadnjom dopunom**. Službena izdanja i vanjske identifikatore dodatno ćemo provjeravati. Korisnički Excel uvezen je putem API-ja, ali **samostalan Vue ekran za upload**, **DON!! izdavanja** i **evidencija posudbi** još ne postoje. Broj playsetova iz Excela potrebno je zasebno usporediti s pravilima backend aplikacije.

## Tehnologije

| Dio | Tehnologije |
| --- | --- |
| Backend | Python, FastAPI, Pydantic, Uvicorn |
| Baza | PostgreSQL 16, SQLAlchemy 2.0, Alembic, Docker Compose |
| Sigurnost | bcrypt; JWT access i refresh tokeni |
| Excel upload | openpyxl, python-multipart |
| Testiranje i kvaliteta | pytest, Ruff, Swagger UI |
| Verzije koda | Git, GitHub, feature branchevi, Pull Requestovi |
| Frontend (planirano) | Vue 3, Vite, TypeScript |
| Hosting (planirano) | Odvojeni frontend i backend/baza; konačan odabir naknadno |

## Struktura projekta

```text
OPTCG_Collection/
├── api/
│   ├── alembic/
│   │   └── versions/           # Migracije 001, 002, 003
│   ├── app/
│   │   ├── core/              # Konfiguracija, JWT, sigurnost i ovisnosti
│   │   ├── models/            # SQLAlchemy modeli i M:N veze
│   │   ├── repositories/      # Upiti nad bazom
│   │   ├── routers/           # HTTP rute, uključujući collection_import.py
│   │   ├── schemas/           # Pydantic sheme
│   │   ├── services/          # Poslovna pravila, uključujući collection_excel_import.py
│   │   ├── main.py            # FastAPI aplikacija
│   │   ├── seed.py            # Početni setovi i rječnici
│   │   ├── import_catalog.py  # Početni uvoz CSV kataloga
│   │   └── enrich_catalog.py  # Dopuna karakteristika iz Koala snapshota
│   ├── tests/
│   ├── requirements.txt
│   └── requirements-dev.txt
├── data/
│   └── catalog_from_excel.csv # Zajednički katalog bez osobnih količina
├── docs/                      # Projektne odluke i upute po koracima
├── web/                       # Vue frontend (planirano)
├── docker-compose.yml
├── .env.example
└── README.md
```

Mape `data/koala_snapshot/` (preuzeti podaci), `backups/` (dumpovi baze), `.env`, osobni `.xlsx` dokumenti i lokalni virtualni okoliš **ne smiju se commitati**. Provjeriti `.gitignore` i staged datoteke prije svakog commita.

## Baza podataka

### Glavne tablice

| Tablica | Namjena |
| --- | --- |
| `users` | Korisnički račun, hash lozinke, uloga i status aktivnosti |
| `card_sets` | Setovi i proizvodi te redoslijed prikaza |
| `cards` | Jedinstvena karta identificirana brojem, s osnovnim karakteristikama |
| `card_printings` | Konkretno izdanje/varijanta (regular, reprint, alt art, manga itd.) |
| `collection_entries` | Osobna količina i napomena povezane s `user_id` i `printing_id` |

Jedna karta može postojati u više izdanja. Zato se osobna kolekcija veže na **konkretan `printing_id`**, a ne samo na broj karte. Kombinacija `(user_id, printing_id)` mora biti jedinstvena; `quantity` ne može biti negativan.

### Rječnici i veze M:N

| Rječnik | Povezna tablica |
| --- | --- |
| `colors` | `card_colors` |
| `attributes` | `card_attributes` |
| `archetypes` | `card_archetypes` |
| `keywords` | `card_keywords` |

M:N (*many-to-many*, više-prema-više) znači da jedna karta može imati više pripadajućih vrijednosti (npr. više boja ili archetypeova), a ista vrijednost može pripadati mnogim kartama.

Tablica `printing_external_ids` pohranjuje izvor, vanjski ID, jezik i završnu obradu izdanja, odvojeno od našeg internog `card_printings.id`. Posebno će biti korisna pri usklađivanju DON!! i alternativnih izdanja.

### Migracije i seed

- `001` — početne tablice, strani ključevi i ograničenja.
- `002` — dodavanje `users.is_active`.
- `003` — rječnici, M:N veze, vanjski identifikatori, `cards.life` i `card_printings.block_icon`.
- `004` — **planirano** za `card_loans`; nije implementirano.

Već primijenjene migracije ne mijenjamo naknadno. Novu strukturu uvodimo novom Alembic migracijom i pregledavamo `upgrade()` prije primjene.

```powershell
# Iz mape api/
alembic current
alembic history
alembic upgrade head
python -m app.seed
```

Seed je ponovljiv (*idempotentan*). Nakon migracije `003` početne vrijednosti bile su: **64 seta** (uključujući `DON`), **6 boja**, **6 atributa** i **24 keywordsa**. `archetypes` se ne održavaju ručno: prilikom dopunjavanja kataloga uvezeno je **170 različitih archetypeova**.

## Pokretanje lokalno — Windows PowerShell

**Preduvjeti:** Git, Python 3.11+, Docker Desktop i `uv`.

Iz korijena repozitorija:

```powershell
# Samo prvi put, ako .env još ne postoji:
Copy-Item .env.example .env
# U .env postaviti vlastite razvojne vrijednosti i JWT_SECRET.

docker compose up -d db
docker compose ps
```

Naš PostgreSQL lokalno je dostupan na `127.0.0.1:5433` (unutar kontejnera port `5432`). **Ne prepisivati postojeći `.env`.**

Iz mape `api/`:

```powershell
cd api
uv venv                              # samo prvi put
.\.venv\Scripts\Activate.ps1
uv pip install -r requirements.txt
uv pip install -r requirements-dev.txt

alembic upgrade head
python -m app.seed
python -m uvicorn app.main:app --reload
```

Ako je virtualno okruženje već postavljeno, nije ga potrebno ponovno stvarati. Uvicorn terminal ostaje otvoren. Korisne adrese:

- Health check: <http://127.0.0.1:8000/health>
- Swagger UI: <http://127.0.0.1:8000/docs>

Zaustavljanje Uvicorna: `Ctrl+C`. Zaustavljanje PostgreSQL-a iz korijena projekta: `docker compose stop` (podaci u volumenu ostaju sačuvani).

## API rute

| Metoda | Ruta | Svrha | Pristup |
| --- | --- | --- | --- |
| `GET` | `/health` | Provjera rada API-ja | Javno |
| `POST` | `/auth/register` | Registracija korisnika | Javno |
| `POST` | `/auth/login` | Prijava i izdavanje tokena | Javno |
| `POST` | `/auth/refresh` | Obnova tokena | Refresh token |
| `GET` | `/auth/me` | Podaci prijavljenog korisnika | Access token |
| `GET` | `/admin/users` | Pregled korisnika | Samo `admin` |
| `GET` | `/cards` | Popis, paginacija, pretraga, filtriranje | Javno |
| `GET` | `/cards/filters` | Dostupne vrijednosti filtera | Javno |
| `GET` | `/cards/{id}` | Detalji karte i izdanja | Javno |
| `GET` | `/collections/{user_id}` | Pregled osobne kolekcije | Vlasnik |
| `POST` | `/collections/{user_id}/entries` | Dodavanje izdanja u kolekciju | Vlasnik |
| `PATCH` | `/collections/{user_id}/entries/{printing_id}` | Izmjena količine i/ili napomene | Vlasnik |
| `DELETE` | `/collections/{user_id}/entries/{printing_id}` | Uklanjanje izdanja iz kolekcije | Vlasnik |
| `POST` | `/collections/{user_id}/import/preview` | Validacija Excel datoteke i pregled promjena bez upisa | Vlasnik |
| `POST` | `/collections/{user_id}/import/apply` | Potvrda pregledanog Excel uvoza | Vlasnik |

### Filtriranje kataloga

Primjer:

```http
GET /cards?colors=red&colors=yellow&sets=op01&limit=20&offset=0
```

U našem lokalnom katalogu taj je zahtjev vratio **31 pogodak**; zbog `limit=20` prikazuje prvih 20. Pravila:

- **OR unutar kategorije:** `colors=Red&colors=Yellow` znači crvene **ili** žute karte.
- **AND između kategorija:** `(Red OR Yellow) AND (Cost 1 OR 2) AND Power 6000`.
- Više vrijednosti šalje se **ponavljanjem istog parametra**, a ne nizom odvojenim zarezima.
- Tekstualni filteri ne razlikuju velika/mala slova; rubni razmaci se zanemaruju.
- Set, rarity, variant i block moraju odgovarati **istom fizičkom izdanju** karte.
- `counter_values=none` znači da nema tiskane Counter vrijednosti (`NULL`), a nije isto što i brojčana nula. Efekt `[Counter]` zasebno je pretraživ putem keyworda.
- `total` je broj svih pogodaka prije primjene `limit` i `offset`.

Parametri: `colors`, `card_types`, `costs`, `powers`, `attributes`, `counter_values`, `block_icons`, `keywords`, `archetypes`, `sets`, `rarities`, `variants`, `search`, `limit`, `offset`.

`GET /cards` trenutačno vraća **osnovne karte**; fizička izdanja prikazuju se u detaljima i koriste za osobne kolekcije.

### CRUD osobne kolekcije — Korak 8A

Zahtjevi za promjenu kolekcije zahtijevaju valjani JWT access token. Korisnik može mijenjati **samo svoju kolekciju**; sam status administratora ne daje automatski pravo uređivanja tuđih zapisa.

Dodavanje:

```http
POST /collections/{user_id}/entries
Content-Type: application/json
```

```json
{
  "printing_id": 13,
  "quantity": 3,
  "note": "Za deck"
}
```

`printing_id` u primjeru služi samo za ilustraciju; u stvarnom zahtjevu mora postojati u bazi. ID izdanja moguće je pronaći u `GET /cards/{id}`.

Djelomična izmjena:

```http
PATCH /collections/{user_id}/entries/{printing_id}
Content-Type: application/json
```

```json
{"quantity": 4}
```

`PATCH` koristi samo **izričito poslana polja**. Ako pošaljemo samo `quantity`, `note` ostaje nepromijenjena; ako pošaljemo samo `note`, količina ostaje ista. `"note": null` služi za brisanje napomene. Zahtjev bez polja (`{}`) nije valjan. Swaggerov automatski primjer `"note": "string"` **nije** prazna vrijednost: ako ga pošaljemo, stvarno će zamijeniti postojeću napomenu.

Potvrđena ponašanja: `201` nakon dodavanja, `200` kod čitanja i izmjene, `409` pri pokušaju dodavanja istog izdanja drugi put, `204` pri brisanju i `404` pri ponovnom brisanju istog zapisa. Nevaljane i negativne količine odbijaju se validacijom; pristup tuđim kolekcijama je zabranjen. Količina `0` dopuštena je, ali ne predstavlja playset.

**Nije još implementirano:** Vue sučelje za upload i upravljanje posudbama. Excel upload već postoji putem FastAPI/Swagger endpointova.

### Uvoz osobne kolekcije iz Excela — Korak 8B

Podržan je `.xlsx` upload putem Swaggera i autentificiranog API-ja. Uvoz **ne mijenja** zajednički katalog karata, nego samo `collection_entries` **prijavljenog vlasnika**. Nije potrebna nova Alembic migracija. Koriste se `openpyxl` i `python-multipart` (u `api/requirements.txt`).

**Endpointovi:**

```http
POST /collections/{user_id}/import/preview?mode=replace
POST /collections/{user_id}/import/apply?mode=replace&plan_token=...
```

Za oba poziva potrebno je autorizirati se JWT access tokenom i priložiti `.xlsx` pod multipart poljem `file`. Maksimalna dopuštena veličina je **6 MB**.

**Načini rada:**

| Način | Ponašanje |
| --- | --- |
| `replace` | Postavlja količinu za **izdanja navedena u Excelu**; ne briše ostale zapise. Prazna napomena ne briše postojeću. |
| `add` | Dodaje količinu iz Excela na postojeću; ne mijenja postojeće napomene. Ponovljena potvrda novog plana može ponovno povećati količine. |

**Pregled i primjena:**

1. Pozovi `preview` s Excelom i odabranim `mode`. **Ne mijenja bazu**.
2. Provjeri `matched`, `create`, `update`, `unchanged`, `error_count`, `warning_count`, `can_apply`, `issues` i `samples`.
3. Kada je `can_apply=true` i sve odgovara očekivanjima, napravi sigurnosnu kopiju baze po potrebi.
4. Pozovi `apply` s **istom datotekom, korisnikom i načinom rada**, koristeći `plan_token` iz prethodnog odgovora.
5. Ako se datoteka ili relevantno stanje kolekcije promijeni između pregleda i potvrde, primjena se odbija s `409`; potreban je novi pregled. Neispravni redci blokiraju uvoz (`422`).

`plan_token` je **kontrolna vrijednost plana uvoza**, a **nije JWT access token**. JWT se koristi u Swaggerovu `Authorize` dijelu.

**Mapiranje izdanja:** regularna izdanja traže se prema kombinaciji **sheet + broj karte + izdanje**, čime npr. `OP01-016` iz `OP01` ostaje različit od PRB reprinta. Sheet `PREGLED` preskače se. Za `VARIJANTE` i budući `DON` sheet potreban je **točan `ID izdanja`**, inače se ne radi nesigurno automatsko uparivanje. Retci s napomenom, ali bez količine, preskaču se uz upozorenje.

**Naš stvarni pregled i uvoz (12. 11. 2026.):**

| Provjera | Rezultat |
| --- | ---: |
| Pročitanih sheetova | 63 |
| Redaka s količinom | 662 |
| Prepoznatih izdanja | 662/662 |
| Novih zapisa planiranih prije uvoza | 662 |
| Grešaka | 0 |
| Upozorenja | 2 |

Upozorenja: **OP15** — jedna napomena bez količine; **OP18** — 119 napomena bez količine. Primjena u načinu `replace` potvrđena je kao uspješna. Prema korisničkom Excelu referentno stanje kolekcije iznosi **2.133 primjerka**, **662 različita izdanja** i **243 playseta**; potpunu potvrdu ukupnih količina i računanje playsetova prema pravilima aplikacije provjeravamo SQL upitom i zasebnom statistikom.

U TablePlusu:

```sql
SELECT user_id,
       COUNT(*) AS razlicitih_izdanja,
       COALESCE(SUM(quantity), 0) AS ukupno_primjeraka
FROM collection_entries
GROUP BY user_id
ORDER BY user_id;
```

Osobnu Excel datoteku **ne spremamo na GitHub** i ne dodajemo u zajednički kataloški CSV. Upload s web-stranice kroz Vue predviđen je u kasnijoj fazi; API već radi.

## Uvoz podataka

### 1. Početni katalog iz CSV-a — Korak 6

Ulaz: `data/catalog_from_excel.csv`, pripremljen iz ranijeg Excela **bez osobnih količina i napomena**. Obuhvaća **3.111 izdanja i 2.847 različitih kartičnih kodova**, raspoređenih u 61 sheet/set. U tom početnom uvozu izostavljeno je 119 najavljenih OP18 zapisa te sheetovi `PREGLED`, `VARIJANTE` i DON!! izdanja.

```powershell
# Iz mape api/
python -m app.import_catalog --file ..\data\catalog_from_excel.csv
python -m app.import_catalog --file ..\data\catalog_from_excel.csv --apply
```

Prva naredba izvodi pregled bez upisa (*dry-run*); druga primjenjuje promjene. U prvom uspješnom lokalnom uvozu dodano je **2.847 karata**, **3.111 izdanja** i **2.916 veza s bojama**. Uvoz je ponovljiv te ne mijenja `collection_entries` ni korisničke napomene.

### 2. Dopuna metapodataka — Korak 7

Izvor je [Koala Kollect Data](https://github.com/hotavocado/koala-kollect-data), uz zasebna engleska opažanja. Snapshot koji smo lokalno primijenili nosi datum **22. 10. 2026.** Pri preuzimanju provjerene su SHA-256 kontrolne vrijednosti.

```powershell
# Iz mape api/
python -m app.enrich_catalog --download  # preuzimanje i provjera
python -m app.enrich_catalog             # pregled bez promjene baze
python -m app.enrich_catalog --apply     # upis nakon pregleda i backupa
```

Dopunjuju se polja i veze kada su dostupni pouzdani podaci: Type, Cost, Power, Counter, Life, Attribute, Archetype, Keywords, Effect i Block icon. Uvoznik pronalazi odgovarajuće postojeće karte prema broju; **ne stvara nova izdanja i ne mijenja osobne količine**.

Rezultat uspješnog lokalnog uvoza:

| Provjera | Rezultat |
| --- | ---: |
| Postojećih karata u bazi | 2.847 |
| Dopunjenih karata | 2.785 |
| Dopunjenih polja | 16.895 |
| Novih M:N veza | 12.073 |
| Novih archetypeova | 170 |
| Dopunjenih block oznaka | 2.784 |

Nakon uvoza TablePlus je prikazao:

| Polje | Popunjenih zapisa |
| --- | ---: |
| `card_type` | 2.786 |
| `cost` | 2.620 |
| `power` | 2.175 |
| `counter` | 1.697 |
| `life` | 142 |

Ne trebaju sve vrste karata imati sve navedene vrijednosti. Primjerice, `OP01-016` (Nami) sada ima tip Character, Cost 1, Power 2000, Counter 1000 i tekst efekta. **Ponovljeni dry-run prijavio je 0 polja, 0 veza i 0 block oznaka za dopunu**, što potvrđuje ponovljivost na istom snapshotu i stanju baze.

**Izvori i kvaliteta:** početni CSV nastao je iz našeg Excela, prethodno sastavljenog uz službeni [Bandai Card List](https://en.onepiece-cardgame.com/cardlist/) i strukturirane izvore poput Koala Kollecta. Nijedan pojedini zapis ne smatramo provjerenim samo zato što je uvezen; nepotpuni i noviji setovi te Alt/Manga/DON!! izdanja traže dodatno usklađivanje.

### Sigurnosna kopija prije većeg uvoza

Iz korijena projekta, uz pokrenut Docker:

```powershell
New-Item -ItemType Directory -Force -Path .\backups
docker compose exec db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc -f /tmp/optcg_backup.dump'
docker compose cp db:/tmp/optcg_backup.dump .\backups\optcg_before_enrichment.dump
docker compose exec db pg_restore -l /tmp/optcg_backup.dump
```

`pg_restore -l` provjerava čitljivost arhive i popis objekata, ali **potpunu obnovljivost potvrđuje tek probni restore u zasebnu bazu**. Dumpovi ostaju lokalno u `backups/`, nikada na GitHubu.

## Testiranje i provjera

Iz mape `api/` s aktivnim virtualnim okruženjem:

```powershell
python -m pytest tests -q
python -m ruff check .
python -m ruff format --check .
alembic current
```

Poslije Koraka 7 potvrđeno je **85 prolaznih automatiziranih testova**. Korak 8A prošao je dodatne CRUD testove i Swagger provjere, a za Korak 8B u pripremi su prošla **22 nova izolirana testa**; stvarni Excel preview i apply također su potvrđeni. **Puni lokalni `pytest tests -q` treba ponovno pokrenuti prije commita 8B** i koristiti njegov stvarni rezultat umjesto zbrajanja testova napamet.

Testiramo uspješne i neuspješne scenarije (401/403/404/409/422), pristup samo vlastitoj kolekciji, paginaciju, OR/AND filtere, ponovljivi CSV i metadata uvoz, djelomični PATCH, Excel preview/apply i odbijanje zastarjelog plana. Za poslovna pravila provjeravamo **HTTP status + jasnu poruku/stabilan kod greške** te da odbijeni zahtjevi ne mijenjaju stanje baze. Isti status smije pokrivati više smisleno povezanih grešaka. Pri većim izmjenama baze provjeravamo i Alembic te SQL podatke u TablePlusu.

### Datumi i vremenske zone — pravilo za nove funkcionalnosti

Za datumsko-vremenska polja koja moraju nositi vremensku zonu koristimo **`AwareDatetime`** (Pydantic). Na backendu radimo s **timezone-aware** vrijednostima, normaliziramo ih na **UTC** (`datetime.now(timezone.utc)` i `.astimezone(timezone.utc)` kada ulaz ima vremensku zonu), a u Vueu ih prikazujemo u lokalnoj vremenskoj zoni korisnika. Ne koristimo naivne datume ni `datetime.utcnow()`. Ovo je projektni standard za buduće posudbe i rokove, a **ne tvrdnja da je već uvedeno u sve stare modele**.

## Sigurnost, privatnost i autorska prava

- Lozinke se čuvaju isključivo kao bcrypt hash. JWT razlikuje `access` i `refresh` tip tokena.
- Registracijom se ne može samostalno dobiti uloga `admin`; osobne kolekcije i buduće posudbe dostupne su samo vlasniku.
- **Ne commitati** `.env`, JWT tajne, lozinke, dumpove baze, preuzete snapshotove ili lokalni virtualni okoliš.
- Prije javne objave provjeriti prava za Bandai ilustracije i tekstove. Dostupnost slikovnog URL-a ili licenca na strukturirane podatke ne znači automatsko dopuštenje za javno posluživanje zaštićenih slika.
- Produkcija će zahtijevati zasebne tajne, konfiguraciju i sigurnosne provjere.

## Dogovorena pravila i planirane funkcionalnosti

### Playsetovi

| Tip karte | Uvjet |
| --- | --- |
| Leader | `quantity >= 1` |
| DON!! | `quantity >= 10` |
| Character, Event, Stage i ostale | `quantity >= 4` |

Pragovi su implementirani u pomoćnoj funkciji; zeleni prikaz i statistike u Vue sučelju tek su planirani. **Označavamo samo ispunjene playsetove.** Količina `0` ili `3` na običnoj karti ne zadovoljava prag.

### DON!! katalog

Planiran je poseban DON!! sheet **bez stupca boja**, s brojem/vanjskim ID-jem, nazivom, količinom, rijetkošću, slikom i napomenom. Izvore i stabilne identifikatore provjeravat ćemo prije masovnog uvoza; najveća oznaka u vanjskom katalogu nije nužno broj njegovih zapisa.

### Posudbe — `card_loans`, planirana migracija `004`

Predviđena je jedna tablica s dva smjera: **posuđeno drugima** i **posuđeno od drugih**. Evidentirat ćemo korisnika, točno izdanje (`printing_id`), ime druge osobe, izdanu i vraćenu količinu, datum te neobavezni rok i napomenu. Podržat ćemo djelomično i potpuno vraćanje te zabranu posuđivanja više vlastitih primjeraka nego što je fizički dostupno.

**Vlasništvo i dostupnost nisu isto:** tuđe posuđene karte ne povećavaju vlastite playsetove. Planirani Vue prikaz je **kompaktna lista s malom slikom točnog izdanja**, imenom osobe, količinom i datumom; velika čitljiva slika pojavljuje se na mouseover, a na mobitelu dodirom, bez tekstualnog tooltipa preko slike. API i migracija za posudbe još nisu napravljeni.

### Vue frontend

Planirane su pretražive višestruke padajuće liste (*searchable multi-select*) koje se filtriraju tijekom tipkanja, pregled izdanja sa slikama, osobni filteri (owned/missing/playset), Excel upload i stranica posudbi. Prikaz ilustracija u javnoj verziji ovisit će o pravima korištenja.

## Git workflow — commit nakon svakog koraka

Na kraju svakog **uspješno testiranog koraka** ažuriramo relevantnu dokumentaciju te radimo **commit + push**. Pull Request i merge u `main` radimo kada završimo smislenu funkcionalnu cjelinu ili feature branch.

```powershell
# Iz korijena repozitorija
git branch --show-current
git status

# Dodati samo pregledane datoteke; paziti na lokalne i privatne podatke
git add README.md
# git add api/app/... api/tests/... docs/...  # prema stvarnim promjenama

git diff --cached --stat
git diff --cached --check
git commit -m "feat: add validated Excel import for personal collections"
git push
```

Za **Korak 8B**, osim README-a treba dodati i stvarno izmijenjene datoteke, osobito `api/app/routers/collections.py`, `api/app/routers/collection_import.py`, `api/app/services/collection_excel_import.py`, `api/tests/test_collection_excel_import.py`, `api/requirements.txt` i `docs/KORAK_08B_EXCEL_IMPORT.md`. Prije commita provjeriti da staged promjene ne uključuju osobnu Excel datoteku, `.env`, backup ili snapshot. Na već povezanom branchu `feat/catalog-enrichment` dovoljan je obični `git push`.

## Sljedeći koraci

1. **Zatvoriti Korak 8B:** pokrenuti puni `pytest`, provjeriti import i README, pregledati staged datoteke te napraviti commit i push na `feat/catalog-enrichment`.
2. **Provjera statistike kolekcije:** usporediti SQL zbroj količina s Excelom i izračunati playsetove po pravilima (Leader ≥1, DON!! ≥10, ostali ≥4).
3. **Posudbe — Korak 9:** migracija `004`, tablica `card_loans`, API s poslovnim pravilima za posuđivanje i djelomično/potpuno vraćanje, odgovarajući statusi i poruke; UTC/AwareDatetime.
4. **Nastavak kataloga:** provjera nepokrivenih/novih kartičnih podataka, varijanti i DON!! izdanja.
5. **Vue i objava:** vizualni katalog, filteri, Excel upload, kolekcije, posudbe, testiranje i produkcijska priprema.

Prioritet su funkcionalnosti potrebne za studentski projekt i sigurnost korisničkih podataka; potpunost kataloga i podršku za nova izdanja možemo nadograđivati postupno.
