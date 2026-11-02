# One Piece TCG — Collection Tracker

Studentski projekt za kolegij **Programiranje za web**. Cilj: zajednicki katalog
One Piece TCG karata, osobne kolekcije, slike, filteri i statistika playsetova.

## Razvoj po predavanjima

- [x] 01: kostur FastAPI-ja i PostgreSQL kontejner
- [ ] 02: SQLAlchemy modeli, Alembic migracije, seed kataloga
- [ ] 03: prijava, JWT access/refresh tokeni
- [ ] 04: uloge (admin/user) i provjera vlasnistva
- [ ] 05–06: CRUD, filtriranje, poslovna pravila, testovi
- [ ] 07–10: Vue frontend
- [ ] 11–12: testiranje i objava

## Struktura

```text
api/                  FastAPI backend
  app/
    core/             konfiguracija, logiranje, obrada gresaka
    routers/          HTTP rute
    schemas/          Pydantic sheme (kasnije)
    services/         poslovna pravila (kasnije)
    repositories/     upiti nad bazom (kasnije)
    models/           SQLAlchemy modeli (od predavanja 2)
web/                  Vue frontend (od predavanja 7)
docker-compose.yml    PostgreSQL baza za lokalni razvoj
.env.example          primjer lokalne konfiguracije
```

## Pokretanje (Windows PowerShell)

Preduvjeti: Git, Python 3.11+, Docker Desktop i `uv`.

```powershell
Copy-Item .env.example .env
docker compose up -d db
cd api
uv venv
uv pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Otvoriti http://127.0.0.1:8000/health (ocekuje se `{"status":"ok"}`) i
http://127.0.0.1:8000/docs (Swagger UI).

## Provjera koda

```powershell
cd api
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
```

## Napomene

U predavanju 1 baza se samo pokrece; modeli i migracije dolaze tek u
predavanju 2. Niti jedan `.env` ni stvarne pristupne podatke ne commitamo.
Za produkciju trebaju posebne lozinke i JWT tajni kljuc.
