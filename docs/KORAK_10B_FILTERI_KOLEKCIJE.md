# Korak 10B — Osobni filteri kataloga (`owned`, `missing`, `playset`)

**Branch:** `feat/collection-stats`
**Datum:** 13. 11. 2026.
**Preduvjet:** završeni 10A (`GET /collections/{user_id}/stats`) i migracija `004`.

## 1. Cilj i odluke

Želimo filtrirati zajednički katalog karata prema stanju **vlastite** kolekcije, bez zasebnog kataloga i bez mijenjanja postojećih odgovora za javne upite.

Postojeći endpoint **`GET /cards`** dobiva opcionalni query parametar **`collection_status`**. Dopuštene su samo vrijednosti `owned`, `missing`, `playset`. Ponovljene vrijednosti kombiniraju se s **OR**, a ostali filteri s **AND**, kao i dosad.

- **`owned`** — postoji barem jedan `card_printings` red koji odgovara filterima izdanja i za koji prijavljeni korisnik ima `collection_entries.quantity > 0`.
- **`missing`** — postoji barem jedan odgovarajući printing, ali prijavljeni korisnik ne posjeduje **nijedan** odgovarajući printing u pozitivnoj količini. Upis s količinom 0 je missing.
- **`playset`** — postoji barem jedan odgovarajući printing za koji korisnik doseže prag **Leader ≥1, DON!! ≥10, ostali ≥4**. Broji se po **točnom izdanju** (`printing_id`), ne zbrajaju se različiti reprintovi ili varijante.

**Primjer razlike:** korisnik posjeduje 4 primjerka PRB01 reprinta, ali nema nijedan OP01 regular print iste karte. `collection_status=owned&sets=PRB01` prikazuje tu osnovnu kartu, `collection_status=missing&sets=OP01` također je prikazuje, a `collection_status=owned&sets=OP01` je ne prikazuje.

## 2. Sigurnost

Samo kada je prisutan `collection_status`, API provjerava JWT access token. Bez filtera `/cards`, `/cards/filters` i `/cards/{id}` ostaju javni, čak i ako klijent u pozadini ima zastarjeli token. Kod nedostatka ili nevaljanog tokena osobni filter vraća **401** u postojećem obliku `{ "code": ..., "message": ... }`.

**ID korisnika nikada ne dolazi iz query parametra.** Čita se isključivo iz validiranog JWT-a, a aktualni status aktivnosti provjerava postojeća autentikacijska ovisnost. Tako nije moguće izlistati tuđu kolekciju dodavanjem `user_id`.

## 3. Pravila queryja i primjeri

Swagger: <http://127.0.0.1:8000/docs> → `GET /cards` → `Authorize`.

```http
GET /cards?collection_status=owned
GET /cards?collection_status=missing&sets=OP01
GET /cards?collection_status=playset&search=OP01-016
GET /cards?collection_status=owned&collection_status=playset
GET /cards?collection_status=missing&collection_status=playset&colors=Red&limit=20
```

`collection_status=missing,playset` **nije dozvoljeno** (422); parametar je potrebno ponoviti. `colors=Red` je primjer postojećeg filtera; koristimo točne ponuđene vrijednosti iz `/cards/filters`.

**Varijante zapisa seta:** u `sets` prihvaćamo `OP01`, `OP-01`, `op01`, `op-01` i rubne razmake. Za prefikse `EB`, `ST` i `PRB` podržan je isti princip (`EB03`/`EB-03`, `ST01`/`ST-01`, `PRB01`/`PRB-01`). Pri filtriranju normaliziramo **samo korisnički unos**; kodovi u PostgreSQL-u se ne mijenjaju. Tekstualni `search=OP-01` također prepoznaje karte s kodom `OP01-...`, a pretraga po imenu i puni kodovi poput `OP01-016` i dalje rade. Promotivni kartični kodovi poput `P-001` ne prepisuju se.

```http
GET /cards?sets=OP-01&collection_status=owned&search=OP01-016
GET /cards?sets=op01&collection_status=owned&search=OP01-016
GET /cards?search=OP-01
```

Filteri `sets`, `rarities`, `variants` i `block_icons` moraju se poklopiti **s istim izdanjem kao vlasništvo ili playset**. `owned` na PRB01 reprintu ne smije se greškom pretvoriti u `owned` za OP01 original. Ostali kriteriji (boja, cijena, power, keyword itd.) primjenjuju se nad osnovnom kartom.

`total`, `limit`, `offset` i `items` ne mijenjaju format. `total` je broj odgovarajućih **osnovnih karata** prije paginacije. Katalog se vraća bez duplikata čak i kad karta ima nekoliko izdanja. Kod `playset` filtriranja `total` se **ne mora podudarati** s 10A statistikom od **285 playsetova**, koja broji **fizička izdanja**. Primjerice, dvije regular/alt verzije iste karte mogu biti dva playseta u statistici, ali samo jedan rezultat `/cards`.

Posudbe ne ulaze u račun: `lent` ne smanjuje vlasništvo, `borrowed` ga ne povećava.

## 4. Struktura izmjena

| Datoteka | Svrha |
| --- | --- |
| `api/app/routers/cards.py` | Novi query parametar i provjera autentikacije. |
| `api/app/core/optional_auth.py` | JWT samo za osobni filter; javni zahtjevi ostaju javni. |
| `api/app/schemas/card_search.py` | Statusi i pouzdani vlasnički ID u filteru. |
| `api/app/repositories/card_repo.py` | SQL `EXISTS`, `NOT EXISTS`, kombiniranje s postojećim kriterijima. |
| `api/app/services/card_service.py` | Dodatna obrana od pozivanja privatnog filtera bez identiteta. |
| `api/app/services/playset_service.py` | SQL ekvivalent 10A pravila za pragove, bez novog modela. |
| `api/tests/test_collection_filters_api.py` | API/SQL testovi, izolirani SQLite podaci, aliasi kodova setova. |
| `README.md` | Sažetak i trenutno stanje. |

**Ne treba nova migracija**; `004 (head)` ostaje. Postojeći podaci, modeli i `/collections/{user_id}/stats` nisu promijenjeni.

## 5. Automatski testovi

Iz aktiviranog virtualnog okruženja u mapi `api`:

```powershell
python -m pytest tests/test_collection_filters_api.py -q
python -m pytest tests -q
alembic current
```

Dodatni regresijski testovi za alias setova provjeravaju javni i privatni API (`owned`/`missing`), isti printing, `sets` i `search` u različitim zapisima i nepromijenjene promotivne kodove.

Testovima provjeravamo: javni katalog bez JWT-a, 401 za osobni filter bez JWT-a, 401 za nevaljan token, 422 za nedopuštene vrijednosti, zabranu korištenja tuđih količina, pozitivne/0 količine, Leader/L fallback, DON!! prag 10, dvije varijante po 2 (nije playset), PRB/OP01 razdvajanje, spajanje statusa s OR, povezivanje s bojama uz AND, paginaciju bez duplikata i nepromijenjene količine nakon čitanja.

## 6. Ručni Swagger test (korisnik ID 3)

Prijavi se u Swaggeru preko `Authorize` sa svojim **access tokenom**.

1. `GET /cards?collection_status=owned&search=OP01-016` → **200**, karta Nami postoji među rezultatima.
2. `GET /cards?collection_status=playset&search=OP01-016` → **200**, karta Nami postoji; poznato je da korisnik ima 5 primjeraka regularnog izdanja.
3. `GET /cards?collection_status=missing&search=OP01-016` → **200**, rezultat treba biti prazan **ako nijedan dodatni matching printing nije u kolekciji**; bez filtera seta, vlasništvo barem jednog Nami printinga isključuje missing.
4. `GET /cards?collection_status=owned&sets=OP01&search=OP01-016` → **200** s Nami, ako joj je vlasnički printing doista u OP01.
5. Bez `Authorize`, `GET /cards?collection_status=owned` → **401**.
6. Bez `Authorize`, obični `GET /cards?limit=2` → **200**.
7. `GET /cards?collection_status=garbage` → **422**.
8. `GET /collections/3/stats` → **2.133 / 662 / 285**, dok se ne promijeni kolekcija.

U Swagger UI `Authorize` ostaje pohranjen za sve rute; za test bez tokena odjavi se putem gumba `Authorize` → `Logout`, ili koristi novi privatni prozor. Za test ponavljanih statusa u URL-u koristi više istih parametara (možeš kroz Swagger unijeti više vrijednosti ako ih UI dopušta).

Nakon testiranja iz baze se ništa ne briše i nema nove Excel migracije. Za provjeru SQL-a nad vlastitom kolekcijom:

```sql
SELECT user_id,
       COUNT(*) FILTER (WHERE quantity > 0) AS distinct_printings,
       COALESCE(SUM(quantity), 0) AS total_cards
FROM collection_entries
WHERE user_id = 3
GROUP BY user_id;
```

Očekivano: `distinct_printings = 662`, `total_cards = 2133`. Pregled 10B je read-only.

## 7. Commit, push, Pull Request

Provjeri `git status` i sadržaj ZIP-a prije kopiranja; raspakiravanje treba raditi na `feat/collection-stats`, nakon commita 10A. Iz mape `api` pokreni puni `pytest`, zatim (po potrebi) `python -m ruff check .` i `python -m ruff format --check .`.

Iz korijena repozitorija:

```powershell
git status
git add README.md docs/KORAK_10B_FILTERI_KOLEKCIJE.md `
  api/app/core/optional_auth.py `
  api/app/routers/cards.py `
  api/app/schemas/card_search.py `
  api/app/repositories/card_repo.py `
  api/app/services/card_service.py `
  api/app/services/playset_service.py `
  api/tests/test_collection_filters_api.py

git diff --cached --check
git diff --cached --stat
git commit -m "feat: add personal owned missing playset catalog filters"
git push
```

Tek nakon toga: GitHub Pull Request `feat/collection-stats` → `main` i merge. Novi branch otvaramo nakon ažuriranja `main`.
