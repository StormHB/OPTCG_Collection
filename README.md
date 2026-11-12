# One Piece TCG — Collection Tracker

Studentski projekt za kolegij **Programiranje za web**. Aplikacija je zamišljena kao zajednički katalog One Piece TCG karata, uz **zasebnu kolekciju svakog korisnika**, filtriranje, pregled izdanja, statistiku playsetova te kasnije uvoz/izvoz Excela i evidenciju posudbi.

Projekt razvijamo postupno prema predavanjima, s FastAPI backendom, PostgreSQL bazom, automatiziranim testovima i Git feature branchevima. Vue frontend dolazi u kasnijoj fazi.

> **Stanje: 12. 11. 2026.** Backend za autentikaciju, autorizaciju i **čitanje/filtriranje zajedničkog kataloga** radi. U PostgreSQL je lokalno uvezen **početni katalog od 2.847 jedinstvenih karata i 3.111 izdanja** iz pripremljenog Excela. Uvoz je potvrđen, a primjer `colors=red&colors=yellow&sets=op01` vratio je 31 pogodak. **Potpuni kartični podaci, korisničke količine iz Excela, posudbe i Vue frontend još nisu implementirani.**

## Razvoj po predavanjima

- [x] **01 — Kostur aplikacije:** FastAPI, Uvicorn, konfiguracija, PostgreSQL u Dockeru, `/health`, Swagger UI.
- [x] **02 — Baza i migracije:** SQLAlchemy modeli, Alembic `001`, početni seed setova.
- [x] **03 — Autentikacija:** Alembic `002`, bcrypt, JWT access/refresh, registracija, prijava i obnova tokena.
- [x] **04 — Autorizacija:** uloge `admin`/`user`, provjera vlasništva nad kolekcijom, zaštićene rute.
- [ ] **05–06 — Katalog, CRUD i poslovna pravila (u tijeku):** migracija `003`, rječnici i M:N veze, API kataloga i filtera, lokalni CSV uvoz **odrađeni**; potpuni podaci karata, uređivanje kolekcije, Excel import i ostala poslovna pravila **preostaju**.
- [ ] **07–10 — Vue frontend:** kataloške kartice, pretraživanje, filtre, osobna kolekcija, posudbe, Excel upload.
- [ ] **11–12 — Završno testiranje i objava:** end-to-end provjere i produkcijsko postavljanje.

## Trenutačno implementirano

- Javni API za popis karata s paginacijom, detalje karte i njezina izdanja te opcije filtera.
- Kombiniranje filtera: **OR unutar jedne kategorije**, **AND između kategorija**.
- Pretraga po nazivu/broju i tekstualni filteri **bez razlikovanja velikih i malih slova** (npr. `red` = `Red`, `op01` = `OP01`).
- M:N veze za boje, atribute, archetypeove i keywords; karte s više podudaranja ne dupliciraju se u rezultatima.
- Filteri koji se odnose na izdanje (`set`, `rarity`, `variant`, `block_icon`) primjenjuju se na **isto izdanje** karte, a ne na nekoliko različitih izdanja iste osnovne karte.
- Lokalni, ponovljivi uvoz početnog CSV kataloga, s provjerom bez upisa (*dry-run*) i stvarnim uvozom uz `--apply`.
- Autentikacija i autorizacija korisnika; zaštićen pregled vlastite kolekcije i administratorski pregled korisnika.

**Ograničenje trenutačnog kataloga:** postojeći Excel uglavnom sadrži broj, ime, boju, rijetkost, izdanje i poveznice na slike. Za velik dio karata `cost`, `power`, `counter`, `life`, tip, attribute, keywords, archetype i efekti još nisu dopunjeni. Zato neki filteri zasad neće davati potpune rezultate. Osobne količine i napomene **nisu uvezene**.

## Tehnologije

| Dio | Tehnologije |
| --- | --- |
| Backend | Python, FastAPI, Pydantic, Uvicorn |
| Baza | PostgreSQL 16, SQLAlchemy 2.0, Alembic, Docker Compose |
| Autentikacija | bcrypt, JWT access/refresh tokeni |
| Testovi i kvaliteta | pytest, Ruff |
| Verzije koda | Git, GitHub, feature branchevi i Pull Requestovi |
| Frontend (plan) | Vue 3, Vite, TypeScript |
| Hosting (plan) | Odvojeni frontend i API/baza; konačan odabir naknadno |

## Struktura projekta

```text
OPTCG_Collection/
├── api/
│   ├── alembic/
│   │   └── versions/          # 001, 002, 003 ...
│   ├── app/
│   │   ├── core/             # Konfiguracija, JWT, sigurnost i ovisnosti
│   │   ├── models/           # SQLAlchemy modeli i M:N veze
│   │   ├── repositories/     # SQLAlchemy upiti
│   │   ├── routers/          # HTTP rute
│   │   ├── schemas/          # Pydantic sheme
│   │   ├── services/         # Poslovna pravila i pristup podacima
│   │   ├── main.py           # FastAPI aplikacija
│   │   ├── seed.py           # Početni setovi i rječnici
│   │   └── import_catalog.py # Uvoz osnovnog kataloga iz CSV-a
│   ├── tests/
│   ├── requirements.txt
│   └── requirements-dev.txt
├── data/
│   └── catalog_from_excel.csv  # Početni katalog bez osobnih količina
├── docs/                    # Projektne odluke i specifikacije
├── web/                     # Vue frontend (planirano)
├── docker-compose.yml
├── .env.example
└── README.md
```

## Baza podataka

### Glavne tablice

| Tablica | Namjena |
| --- | --- |
| `users` | Korisnički račun, hash lozinke, uloga, status aktivnosti |
| `card_sets` | Setovi/proizvodi i redoslijed prikaza |
| `cards` | Jedinstveni broj karte i osnovne karakteristike |
| `card_printings` | Fizičko izdanje/varijanta iste karte: regular, reprint, alt art, manga i sl. |
| `collection_entries` | Količina i napomena **određenog korisnika** za određeno izdanje |

Svaka karta (`cards`) postoji jednom prema vlastitom broju, a može imati više izdanja (`card_printings`). Osobna kolekcija povezana je s konkretnim `printing_id`, tako da različite ilustracije iste karte možemo brojiti zasebno.

### Rječnici, M:N veze i vanjski ID-jevi (`003`)

| Rječnik | Povezna tablica |
| --- | --- |
| `colors` | `card_colors` |
| `attributes` | `card_attributes` |
| `archetypes` | `card_archetypes` |
| `keywords` | `card_keywords` |

**M:N** (*many-to-many*) znači da jedna karta može imati više boja, atributa, archetypeova i keywordsa, a svaka od tih vrijednosti može pripadati mnogim kartama.

`printing_external_ids` čuva vanjske identifikatore iz različitih kataloga (izvorni ID, jezik, završna obrada), bez zamjene našeg internog `card_printings.id`. To će biti korisno i za DON!! izdanja. Migracija `003` dodala je i `cards.life` te `card_printings.block_icon`.

**Migracije:**

- `001` — početne tablice i ograničenja.
- `002` — `users.is_active`.
- `003` — rječnici, M:N veze, vanjski ID-jevi, `life` i `block_icon`.
- `004` — **planirana**, za evidenciju posudbi (`card_loans`); još nije izrađena.

Već primijenjene migracije ne prepravljamo. Svaku sljedeću promjenu strukture baze uvodimo novom migracijom i pregledavamo generirani `upgrade()` prije izvršavanja.

### Seed

Naredba `python -m app.seed` može se ponoviti bez dupliciranja zapisa (*idempotentno*). Nakon `003` lokalno smo provjerili:

| Tablica | Broj zapisa |
| --- | ---: |
| `card_sets` | 64 (uključuje oznaku `DON`) |
| `colors` | 6 |
| `attributes` | 6 |
| `keywords` | 24 |
| `archetypes` | 0 neposredno nakon seeda |

Archetypeove ćemo izvlačiti iz stvarnih podataka o kartama, umjesto da ih održavamo ručno. **Seed nije isto što i uvoz svih karata.**

## Pokretanje lokalno — Windows PowerShell

**Preduvjeti:** Git, Python 3.11+, Docker Desktop i `uv`.

Iz korijena repozitorija:

```powershell
# Samo prvi put: pripremi lokalnu konfiguraciju i vlastiti JWT_SECRET
Copy-Item .env.example .env

# Pokreni PostgreSQL
docker compose up -d db
docker compose ps
```

PostgreSQL je lokalno dostupan na `127.0.0.1:5433` (unutar kontejnera port `5432`). Ako je `.env` već postavljen, nemoj ga ponovno prepisivati.

U mapi `api/`:

```powershell
cd api
uv venv                              # samo pri prvom postavljanju
.\.venv\Scripts\Activate.ps1
uv pip install -r requirements.txt
uv pip install -r requirements-dev.txt

alembic upgrade head
python -m app.seed
python -m uvicorn app.main:app --reload
```

Ako je virtualno okruženje već pripremljeno, dovoljno je aktivirati ga i pokrenuti Uvicorn. Terminal s Uvicornom ostaje otvoren.

- Health check: http://127.0.0.1:8000/health
- Swagger UI: http://127.0.0.1:8000/docs

Uvicorn se zaustavlja s `Ctrl+C`. Bazu iz korijena projekta zaustavljamo s `docker compose stop` (podaci u Docker volumenu ostaju sačuvani).

## API rute

| Metoda | Ruta | Svrha | Pristup |
| --- | --- | --- | --- |
| `GET` | `/health` | Provjera rada API-ja | Javno |
| `POST` | `/auth/register` | Registracija običnog korisnika | Javno |
| `POST` | `/auth/login` | Prijava, access/refresh tokeni | Javno |
| `POST` | `/auth/refresh` | Obnova tokena | Refresh token |
| `GET` | `/auth/me` | Prijavljeni korisnik | Access token |
| `GET` | `/collections/{user_id}` | Dohvat vlastite kolekcije | Vlasnik |
| `GET` | `/admin/users` | Pregled korisnika | `admin` |
| `GET` | `/cards` | Popis, paginacija, pretraživanje i filtriranje | Javno |
| `GET` | `/cards/filters` | Dostupne vrijednosti filtera | Javno |
| `GET` | `/cards/{id}` | Detalji karte i povezanih izdanja | Javno |

Katalog se čita javno; **mijenjanje tuđe osobne kolekcije nije dopušteno**. Endpointovi za unos/ažuriranje osobnih količina i za posudbe još nisu implementirani.

### Filteri na `GET /cards`

Primjer:

```http
GET /cards?colors=red&colors=yellow&sets=op01&limit=20&offset=0
```

U našem lokalnom katalogu taj je zahtjev vratio **31 pogodak**, od kojih je prvih 20 u `items` zbog `limit=20`.

Parametri koje API podržava:

`colors`, `card_types`, `costs`, `powers`, `attributes`, `counter_values`, `block_icons`, `keywords`, `archetypes`, `sets`, `rarities`, `variants`, `search`, `limit`, `offset`.

- **OR unutar kategorije:** `colors=Red&colors=Yellow` odgovara crvenim **ili** žutim kartama (i višebojnim kartama koje imaju jednu od njih).
- **AND između kategorija:** `(Red OR Yellow) AND (Cost 1 OR 2) AND Power 6000`.
- Za više vrijednosti **ponavlja se parametar**, ne piše se lista odvojena zarezom.
- Tekstualni filteri ignoriraju velika/mala slova i rubne razmake.
- `sets` se odnosi na **set izdanja**, ne nužno izvorni set karte; set, rijetkost, varijanta i block moraju odgovarati **istom printingu**.
- `counter_values=none` znači da **nema tiskane Counter vrijednosti** (`NULL`), a ne numeričku nulu. Event efekt `[Counter]` zasebna je kategorija keyworda.
- `search` traži broj ili naziv karte, a `total` je ukupni broj pogodaka **prije** paginacije.

`GET /cards/filters` dohvaća rječnike i dostupne opcije za izbornike. Neki izbornici sadrže poznate početne vrijednosti, a neki vrijednosti iz već uvezenih podataka. Prazni ili nepotpuni podaci u katalogu znače i nepotpune rezultate pojedinih filtera.

**Važna razlika:** `GET /cards` trenutačno vraća **osnovne karte**, a ne zaseban red za svako fizičko izdanje. Za budući prikaz kolekcije po slikama/izdanjima koristit ćemo podatke o `card_printings` i osobnim količinama.

## Uvoz početnog kataloga iz CSV-a

Uvoznik je `api/app/import_catalog.py`, a ulazna datoteka `data/catalog_from_excel.csv`. CSV je pripremljen iz **`OPTCG_Prazna_baza(1).xlsx`**, bez osobnih količina i napomena.

Početni uvoz obuhvatio je **3.111 izdanja iz 2.847 jedinstvenih kodova**, iz 61 sheeta/seta. **119 OP18 zapisa privremeno je izostavljeno** do provjere. Nisu uvezeni `PREGLED`, `VARIJANTE` ni DON!! izdanja.

Iz mape `api/`, nakon pokretanja baze i primjene migracije `003`:

```powershell
# Provjera CSV-a bez promjene baze
python -m app.import_catalog --file ..\data\catalog_from_excel.csv

# Stvarni uvoz: preporučena sigurnosna kopija baze prije prvog izvođenja
python -m app.import_catalog --file ..\data\catalog_from_excel.csv --apply
```

Na lokalnoj bazi potvrđen je rezultat:

```text
novih karata=2847
novih izdanja=3111
novih veza s bojama=2916
```

Uvoz je zamišljen kao transakcijski i ponovljiv: ponovno učitavanje istog CSV-a ne treba stvarati duplikate. **Ne mijenja `collection_entries`, osobne količine ni bilješke.** Za izvođenje iz stvarnog Excela putem web-sučelja tek trebamo razviti novu funkcionalnost.

Provjera u TablePlusu:

```sql
SELECT 'cards' AS tablica, COUNT(*) AS broj FROM cards
UNION ALL
SELECT 'card_printings', COUNT(*) FROM card_printings
UNION ALL
SELECT 'card_colors', COUNT(*) FROM card_colors
UNION ALL
SELECT 'collection_entries', COUNT(*) FROM collection_entries;
```

### Izvori i provjera podataka

Početni CSV potječe iz **našeg ranije izrađenog Excela**. Njegovi podaci prethodno su prikupljani iz službenog Bandai kataloga i posrednih izvora, uključujući Koala Kollect; time **nije potvrđena točnost svih pojedinih zapisa**.

- Službeni katalog: https://en.onepiece-cardgame.com/cardlist/
- Koala Kollect (strukturirani podaci): https://github.com/hotavocado/koala-kollect-data

Prije potpunog uvoza moramo provjeriti reprintove, alternate art/manga varijante, izvore i identitete DON!! izdanja te nadopuniti nedostajuće karakteristike karata.

## Testiranje i provjera

Unutar `api/` i s aktivnim virtualnim okruženjem:

```powershell
python -m pytest tests -q
python -m ruff check .
python -m ruff format --check .

alembic current
alembic history
```

Posebno su dodani testovi za katalog, detalje, opcije filtera, OR/AND logiku, više izdanja, `NULL`/`0` Counter vrijednosti, case-insensitive pretragu i ponovljivi CSV uvoz. **Konačan broj prolaznih testova provjerava se lokalno** jer se testni skup proširuje sa svakim korakom.

U Swaggeru smo provjeravali registraciju, JWT, vlasništvo nad kolekcijom, administratorske ovlasti, javne rute i primjer filtriranja koji je nakon ispravka vratio očekivanih 31 pogodak.

## Sigurnost i prava pristupa

- Lozinke se spremaju kao **bcrypt hash**, nikada kao čisti tekst.
- JWT razlikuje **access** i **refresh** token; tip tokena provjerava se pri autorizaciji.
- Registracija ne dopušta samostalno dodjeljivanje uloge `admin`.
- `get_current_user`, `require_role("admin")` i provjere vlasništva štite osobne i administratorske rute.
- `401` znači da prijava nedostaje ili je nevaljana; `403` označava nedostatne ovlasti; `409` konflikt; `422` nevaljan zahtjev.
- Korisničke količine, bilješke i buduće posudbe **privatni su podaci**. Sam status administratora ne bi trebao automatski otvarati privatne kolekcije.
- **Nikada ne commitati `.env`, JWT_SECRET, lozinke, virtualno okruženje ni stvarne pristupne podatke.**

## Dogovorena pravila i planirane funkcionalnosti

### Playsetovi

| Vrsta | Uvjet za playset |
| --- | --- |
| Leader | `quantity >= 1` |
| DON!! | `quantity >= 10` |
| Ostale karte | `quantity >= 4` |

Logika pragova postoji u pomoćnoj funkciji; **prikaz zelenom bojom i statistika po osobnim količinama tek dolaze u frontend**. Ako uvjet nije ispunjen, količinu ne označavamo posebno. Npr. Character ×3 nije playset; DON!! ×9 nije playset.

### Katalog, DON!! i Excel

- Dopuniti karte iz pouzdanih strukturiranih izvora: tip, Cost, Power, Counter, Life, Attribute, Archetype, Keywords, Effect, Block i odgovarajuće ilustracije/izdanja.
- Omogućiti zaseban **DON!!** katalog i Excel sheet **bez stupca boja**. DON!! izdanja identificirati vlastitim ID-jem i provjerenim vanjskim oznakama; ne pretpostavljati da je najveći broj u nekom katalogu jednak broju dostupnih karata.
- Implementirati uređivanje osobnih količina i napomena te uvoz `.xlsx` datoteke na stranicu. Razlikovati **zamjenu postojećeg stanja** i **dodavanje količina**; uvoz najprije validirati i prikazati korisniku za potvrdu.
- Uvesti **osobnu Excel kolekciju** tek nakon što postoje autentificirani unos količina i pouzdano mapiranje na `printing_id`.
- U Vue sučelju ponuditi searchable multi-select dropdownove, koji se sužavaju već tijekom tipkanja, te filtre za **owned / missing / playset**.

### Dopunjavanje kataloga (Korak 7)

Katalog je dopunjen podacima iz Koala Kollect snapshota
od 22.10.2026. Dopunjuju se tip karte, Cost, Power,
Counter, Life, Attribute, Archetype, Keywords, Effect
i Block oznake kada su podaci dostupni.

U bazi je 2847 karata. Uvoznik je prepoznao i obradio
2785 karata s aktivnim engleskim opisima.

Preuzimanje i provjera podataka:

python -m app.enrich_catalog --download

Pregled promjena bez upisa:

python -m app.enrich_catalog

Primjena promjena:

python -m app.enrich_catalog --apply

Ponovljeni uvoz ne stvara duplikate.
Korisničke količine, napomene i postojeća izdanja
ostaju nepromijenjeni.

Provjera: 85 uspješnih automatiziranih testova.

### Posudbe (`card_loans`, planirano)

Jedna nova tablica `card_loans` s dva smjera: **posuđeno drugima** i **posuđeno od drugih**. Za svaku posudbu čuvat ćemo korisnika, `printing_id`, osobu, količinu, vraćenu količinu, datum i neobaveznu napomenu/rok vraćanja.

- Ne smije se posuditi više **vlastitih fizički dostupnih** primjeraka nego što ih korisnik ima.
- Omogućiti djelomično i potpuno vraćanje te pregled aktivnih posudbi.
- Razlikovati **vlasništvo** od **fizičke dostupnosti**. Posuđene tuđe karte ne povećavaju broj vlastitih playsetova.
- Budući Vue prikaz: **kompaktna lista** s malom slikom točnog izdanja karte, ime osobe, količina i datum. Na **mouseover** prikazuje se veća čitljiva slika; na mobitelu povećanje dodirom. Ne prikazivati tekstualni tooltip preko slike.
- API i migracija `004` tek predstoje; nema implementiranih ruta `/loans`.

### Autorska prava na ilustracije

Kod javne objave moramo posebno provjeriti dopuštenja za prikaz službenih Bandai ilustracija i tekstova. Dostupnost slike putem URL-a ili prava na korištenje strukturiranog skupa podataka **ne znače automatski dopuštenje za javno ponovno objavljivanje ilustracija**. Predvidjeti mogućnost isključivanja slika ili korištenja dopuštenog izvora dok se ne riješe prava.

## Git workflow — nakon svakog koraka

**Od sada radimo commit i push nakon svakog uspješno testiranog koraka**, ne samo na kraju cijelog predavanja. **Pull Request i merge** radimo kada završimo smislen feature branch. README dopunjavamo kada uvedemo ili promijenimo funkcionalnost, a obavezno ga pregledamo prije PR-a.

Prije commita:

1. Pokrenuti odgovarajuće testove i puni `pytest`.
2. Po potrebi provjeriti endpoint u Swaggeru i migraciju u Alembicu/TablePlusu.
3. Provjeriti `git status`, promjene i da nema tajni ili lokalnih privremenih datoteka.
4. Ažurirati README/specifikaciju prema stvarno odrađenome.
5. Napraviti commit s opisom **tog konkretnog koraka**, pa push na trenutni branch.

Iz **korijena repozitorija**:

```powershell
git branch --show-current
git status
git add README.md api data docs    # prilagodi stvarno promijenjenim mapama/datotekama
git diff --cached
git commit -m "feat: implement card catalog API and CSV import"
git push -u origin feat/card-catalog
```

Nemoj slijepo koristiti `git add .` ako se u radnoj mapi nalaze `.env`, dumpovi baze ili drugi osjetljivi/nepotrebni podaci. Za sljedeće korake koristit ćemo odgovarajuću zasebnu poruku commita. Nakon PR-a za `feat/card-catalog` nastavljamo u novom feature branchu.

## Sljedeći koraci

1. **Sada:** provjera svih lokalnih testova, ovaj README, commit/push i PR za stabilni dio `feat/card-catalog`.
2. **Obogaćivanje kataloga:** provjeriti izvore i dopuniti sve karakteristike, izdanja i DON!! identifikatore.
3. **Osobne kolekcije i Excel import:** CRUD količina/napomena i siguran `.xlsx` uvoz, pa uvoz vlastite kolekcije.
4. **Posudbe:** migracija `004`, API i poslovna pravila za izdavanje/vraćanje.
5. **Frontend i završna provjera:** vizualni katalog, filteri, korisnički ekran, posudbe i priprema objave.

Prioritet su funkcionalnosti nužne za projekt i pouzdanost korisničkih podataka; potpunost svih budućih setova i ilustracija možemo postupno proširivati.
