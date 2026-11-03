# One Piece TCG — Collection Tracker

Studentski projekt za kolegij **Programiranje za web**. Cilj aplikacije je omogućiti pregled zajedničkog kataloga One Piece TCG karata i vođenje **zasebne kolekcije za svakog korisnika**. Projekt razvijamo postupno, prema predavanjima, uz vlastite Git brancheve, testove i Alembic migracije.

> **Trenutačno stanje:** backend osnova, modeli baze, JWT autentikacija i autorizacija rade. **Stvarni katalog karata iz Excela, uređivanje količina, filtri i frontend još nisu implementirani.**

## Razvoj po predavanjima

- [x] **01 — Arhitektura i kostur:** FastAPI, Uvicorn, konfiguracija, PostgreSQL u Dockeru, `/health`, Swagger.
- [x] **02 — Modeliranje i migracije:** SQLAlchemy modeli, Alembic migracija `001`, početni `seed` setova, provjere ograničenja.
- [x] **03 — Autentikacija:** migracija `002` (`users.is_active`), bcrypt, JWT access/refresh, registracija, prijava, obnova tokena, `/auth/me`.
- [x] **04 — Autorizacija:** uloge `admin` i `user`, provjera vlasništva nad kolekcijom te zaštićene korisničke i administratorske rute.
- [ ] **05–06 — CRUD i poslovna pravila:** uvoz karata, katalog, upravljanje količinama, filtri, dodatne migracije i testovi.
- [ ] **07–10 — Vue frontend:** pregled karata, slike, pretraga, filtri, prijava, osobna kolekcija i korisničko sučelje.
- [ ] **11–12 — Završno testiranje i objava:** end-to-end testovi i produkcijska konfiguracija.

## Tehnologije

- **Backend:** Python, FastAPI, Pydantic, Uvicorn
- **Baza:** PostgreSQL 16 (Docker Compose), SQLAlchemy 2.0, Alembic
- **Sigurnost:** bcrypt za hashiranje lozinki, JWT access i refresh tokeni
- **Kvaliteta:** pytest, Ruff, Git/GitHub
- **Frontend (planirano):** Vue 3, Vite, TypeScript
- **Hosting (planirano):** odabrat ćemo nakon implementacije, moguće Netlify za frontend i zaseban servis za API/bazu

## Struktura projekta

```text
api/
  alembic/
    versions/          Verzije migracija baze
  app/
    core/              Konfiguracija, ovisnosti, JWT, sigurnost, greške
    models/            SQLAlchemy modeli
    repositories/      Upiti i dohvat podataka iz baze
    routers/           HTTP rute (auth, collections, admin, ...)
    schemas/           Pydantic modeli zahtjeva i odgovora
    services/          Poslovna pravila i provjere pristupa
    main.py            Kreiranje FastAPI aplikacije i registracija ruta
    seed.py            Ponovljiv unos početnih setova
  tests/               Automatizirani testovi
  requirements.txt
  requirements-dev.txt
web/                   Frontend (kasnije)
docs/                  Projektne odluke i bilješke (ako ih dodamo)
docker-compose.yml     Lokalni PostgreSQL
.env.example           Primjer konfiguracije (bez tajni)
README.md
```

## Model baze

| Tablica | Svrha |
| --- | --- |
| `users` | Korisničko ime, hash lozinke, uloga (`user`/`admin`), aktivnost računa |
| `card_sets` | Popis setova i njihov redoslijed |
| `cards` | Jedinstvena karta, izvorni broj, naziv i osnovne karakteristike |
| `card_printings` | Određeno izdanje iste karte (regular, alternate art, reprint i sl.) |
| `collection_entries` | Veza korisnika i izdanja karte; količina i napomena |

**Zašto `card_printings`?** Jedna karta može postojati u više fizičkih izdanja. Korisnička kolekcija zato se povezuje s konkretnim izdanjem, a ne samo s brojem karte.

Važna ograničenja baze uključuju jedinstven `username` i `card_sets.code`, jedinstvenu kombinaciju `(user_id, printing_id)` te `quantity >= 0`. Vlasništvo nad kolekcijom temelji se na `collection_entries.user_id`.

### Migracije

- `001` — početne tablice, strani ključevi i ograničenja.
- `002` — dodavanje `users.is_active`.

Strukturu baze mijenjamo **novom Alembic migracijom**, a ne ručnim prepravljanjem starih migracija nakon što su primijenjene.

Početna skripta `python -m app.seed` unosi setove koji još ne postoje. Može se pokrenuti više puta bez dodavanja duplikata (*idempotentni seed*). **Ne uvozi još sve karte iz Excela.**

## Pokretanje lokalno (Windows PowerShell)

**Preduvjeti:** Git, Python 3.11+, Docker Desktop i `uv`.

U korijenu repozitorija:

```powershell
Copy-Item .env.example .env  # samo prvi put; postavi vlastiti JWT_SECRET

docker compose up -d db
# Provjera kontejnera:
docker compose ps
```

Naša baza dostupna je na `127.0.0.1:5433`; PostgreSQL unutar kontejnera koristi port `5432`.

U mapi `api/`:

```powershell
cd api
uv venv                              # samo pri prvom postavljanju
.\.venv\Scripts\Activate.ps1
uv pip install -r requirements.txt  # ili kada se promijene ovisnosti
uv pip install -r requirements-dev.txt

alembic upgrade head
python -m app.seed
python -m uvicorn app.main:app --reload
```

Ako virtualno okruženje već postoji i ovisnosti su instalirane, dovoljno je **aktivirati `.venv` i pokrenuti Uvicorn**. Terminal s Uvicornom mora ostati otvoren.

- Health check: <http://127.0.0.1:8000/health>
- Swagger UI: <http://127.0.0.1:8000/docs>

Za gašenje Uvicorna pritisni `Ctrl+C`. PostgreSQL zaustavi iz korijena repozitorija naredbom `docker compose stop` (podaci se ne brišu).

## API rute koje trenutačno imamo

| Metoda | Ruta | Svrha | Pristup |
| --- | --- | --- | --- |
| `GET` | `/health` | Provjera rada API-ja | Javno |
| `POST` | `/auth/register` | Registracija s ulogom `user` | Javno |
| `POST` | `/auth/login` | Provjera lozinke i izdavanje tokena | Javno |
| `POST` | `/auth/refresh` | Obnova JWT tokena | Refresh token |
| `GET` | `/auth/me` | Podaci trenutačno prijavljenog korisnika | Access token |
| `GET` | `/collections/{user_id}` | Dohvat vlastite kolekcije | Vlasnik kolekcije |
| `GET` | `/admin/users` | Pregled korisnika | Samo `admin` |

`GET /collections/{user_id}` zasad može vratiti prazan popis `[]`: struktura postoji, ali nismo uvezli katalog ni korisničke količine.

### Sigurnost i ovlasti

- Lozinke se spremaju kao **bcrypt hash**, nikad kao običan tekst.
- JWT tokeni sadrže identitet i tip (`access` ili `refresh`); tip se provjerava pri korištenju.
- `get_current_user` provjerava identitet kroz token i bazu.
- `require_role("admin")` ograničava pristup administratorskim rutama.
- Provjera vlasništva provodi se u **servisnom sloju**, prije čitanja tuđe kolekcije.
- `401` označava nedostajuću/nevaljanu prijavu, `403` nedovoljna prava, `409` konflikt (npr. zauzeto korisničko ime), a `422` neispravne ulazne podatke.
- Registracijom se **ne može** odabrati `admin` uloga. Administratorski račun za lokalni razvoj postavlja se kontrolirano u bazi.

## Testovi i provjera koda

U novom terminalu, unutar `api/`, s aktivnim virtualnim okruženjem:

```powershell
python -m pytest tests -q
python -m ruff check .
python -m ruff format --check .
```

Ručno smo u Swaggeru provjerili registraciju, pokušaj duplicirane registracije (`409`), validaciju (`422`), prijavu, pristup vlastitoj kolekciji (`200`), odbijanje tuđe kolekcije (`403`), odbijanje zahtjeva bez tokena (`401`) i administratorsku rutu (`200` za admina). Automatizirane testove pokrećemo prije commita i mergea.

Za provjeru migracija:

```powershell
alembic current
alembic history
```

## Dogovorena pravila za budući katalog i frontend

> Sljedeće značajke su **specifikacija za kasniju implementaciju**, ne trenutno gotove funkcionalnosti.

- **Playset:** Leader (`L`) ima playset od **1** primjerka; svi drugi tipovi od **4**. Količina koja zadovoljava uvjet bit će označena zeleno.
- **Filtri:** više izbora **unutar iste kategorije** povezuje se s `OR` (npr. Red **ili** Yellow), a **različite kategorije** s `AND` (npr. odabrane boje **i** Cost 3).
- **Višestruke vrijednosti:** karta može imati više boja i affiliationa; svaki rezultat prikazujemo samo jednom.
- **Searchable dropdown / autocomplete:** rezultati se filtriraju tijekom tipkanja, s mogućnošću višestrukog odabira.
- **Kriteriji:** set, naziv/broj, boja, cost, power, counter, tip, rijetkost, attribute, affiliation, posjedovano/nedostaje/playset.
- **Podaci:** za kontrolirane skupove vrijednosti koristit ćemo Enume ili zasebne tablice. Za affiliatione planiramo zasebnu tablicu i vezu više-prema-više.
- **Privatnost:** korisnici smiju mijenjati svoju kolekciju; sama uloga `admin` ne daje automatski pravo čitanja privatnih korisničkih kolekcija.

## Git workflow

Svaku funkcionalnu cjelinu radimo na posebnom branchu (npr. `feat/database-models`, `feat/authentication`, `feat/authorization`). Nakon testiranja slijede commit, push, Pull Request i merge u `main`.

```powershell
git status
git add .
git commit -m "feat: kratak opis promjene"
git push -u origin IME_BRANCHA
```

## Sigurnosne napomene

- **Nikad ne commitati `.env`, JWT tajne, lozinke ni stvarne pristupne podatke.** Za primjer služi `.env.example`.
- Lokalni PostgreSQL podaci ostaju u Docker volumenu. `docker compose stop` ih ne briše; brisanje volumena može ih trajno ukloniti.
- Lokalni administratorski račun **ne postoji automatski** u budućoj produkcijskoj bazi; inicijalizirat ćemo ga sigurnim zasebnim postupkom.

## Sljedeći koraci

Nakon završetka `feat/authorization` prelazimo na katalog karata, CRUD, potrebne migracije, uvoz podataka iz Excela i API filtriranje. Tek zatim implementiramo Vue sučelje. U svakoj fazi zadržavamo jasne commitove i mogućnost objašnjenja koda na obrani.
