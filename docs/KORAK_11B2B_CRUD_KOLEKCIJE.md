# Korak 11B.2B — regresijska provjera CRUD-a osobne kolekcije

Datum: 16. 11. 2026. Branch: `fix/backend-validation`. Alembic ostaje `004 (head)`.

## Cilj i opseg

Pregledani su model `CollectionEntry`, CRUD rute, servis i repository, zaštita aktivnih posudbi te postojeći API, SQLite i validacijski testovi. Nisu korišteni stvarni korisnici, osobna kolekcija ni PostgreSQL podaci.

## Prethodno postojeća pokrivenost

### POST

- Uspješno dodavanje izdanja i odgovor `201`.
- Početna količina `0`.
- Servisna provjera duplikata i odgovor `409`.
- Nepostojeći `printing_id` i odgovor `404`.
- Negativna, `null`, prevelika i tipno neispravna količina te preduga/prazna napomena završavaju s `422` prije upisa.

### GET i vlasništvo

- Vlasnik vidi samo svoje zapise, a prazna kolekcija vraća prazan popis.
- Tuđi `user_id` vraća `403` prije repository upita; bez autentikacije odgovor je `401`.
- Administrator nema automatski pristup tuđoj kolekciji.
- Autentificirani korisnik mora postojati i biti aktivan, pa vlastiti URL ne predstavlja nepostojećeg korisnika. Tuđi/nepoznati ID namjerno vraća `403` bez otkrivanja postoji li korisnik.

### PATCH

- Mijenjaju se samo izričito poslana polja.
- `note=null` briše napomenu, a izostavljena napomena ostaje nepromijenjena.
- `quantity=0` je dopušten; prazan JSON, `quantity=null`, negativne/prevelike vrijednosti, bool, decimalni broj, string i nepoznata polja vraćaju `422`.
- Nepostojeći zapis vraća `404`.

### DELETE i integritet

- Postojeći zapis vraća `204` bez tijela; nepostojeći vraća `404`.
- Brisanje kolekcijskog zapisa ne briše kartu ni printing iz kataloga.
- Aktivne `lent` posudbe sprječavaju smanjivanje količine ispod nevraćenog broja i sprječavaju DELETE; `borrowed` posudbe ne smanjuju vlasničku količinu.
- Neuspješna validacija, tuđe vlasništvo i aktivna posudba ne mijenjaju zapis.

## Novi regresijski testovi

Datoteka `api/tests/test_collection_crud_matrix_11b2b.py` dodaje sedam testova:

1. Gornja dopuštena granica `quantity=999999` prolazi kroz POST i dolazi do repositoryja bez promjene vrijednosti.
2. Nepoznati tuđi `user_id` vraća `403` prije čitanja kolekcije.
3. Baza provodi unique constraint `(user_id, printing_id)` i nakon neuspjelog duplikata zadržava izvorni zapis.
4. Race fallback u servisu pretvara `IntegrityError` pri stvaranju u siguran `409 / conflict`, bez curenja detalja baze.
5. PATCH količine generira PostgreSQL `SELECT ... FOR UPDATE` prije provjere aktivno posuđenih primjeraka.
6. DELETE generira PostgreSQL `SELECT ... FOR UPDATE` prije provjere aktivnih posudbi.
7. Ako zapis nestane između servisnog čitanja i DELETE zaključavanja, repository vraća `404 / not_found` prije loan upita i bez pokušaja brisanja.

## Konkurentnost — što je potvrđeno

- Unique constraint onemogućuje dva zapisa istog printinga za istog korisnika čak i ako oba zahtjeva prođu prethodnu servisnu provjeru.
- Servis hvata race `IntegrityError`; transakcijska ovisnost `get_db` zatim radi rollback cijelog neuspjelog zahtjeva.
- PATCH količine i DELETE zaključavaju odgovarajući `collection_entries` redak prije provjere `outstanding_lent`; testovi bilježe redoslijed poziva `lock → loans`, ne samo prisutnost oba poziva.
- Stvaranje `lent` posudbe koristi isti zaključani redak, pa je redoslijed zaključavanja usklađen sa zaštitom CRUD-a.

SQLite prihvaća unique constraint, ali ignorira stvarnu semantiku `FOR UPDATE`. Testovi zato potvrđuju generirani PostgreSQL SQL i poslovna pravila, ali **ne simuliraju dvije stvarne paralelne PostgreSQL transakcije**.

Za potpunu integracijsku potvrdu potrebna je zasebna prazna PostgreSQL testna baza i najmanje ovi paralelni scenariji:

- dva istodobna POST-a istog `(user_id, printing_id)` — jedan uspjeh i jedan `409`;
- PATCH smanjenja nasuprot stvaranju `lent` posudbe — bez količine manje od aktivno posuđene;
- DELETE nasuprot stvaranju posudbe — bez posudbe koja ostaje bez vlasničkog zapisa;
- dva istodobna PATCH-a istog polja — dokumentirati postojeću semantiku zadnjeg potvrđenog apsolutnog zapisa.

Trenutačni API nema version/ETag optimističko zaključavanje. Dva valjana PATCH-a istog polja zato imaju uobičajenu semantiku “zadnji commit pobjeđuje”. To nije promijenjeno jer projekt nema poslovno pravilo za odbijanje zastarjelog PATCH-a. Note-only PATCH također nema poseban row lock. Ako bude potrebna detekcija izgubljenih ažuriranja, to je zasebna funkcionalna odluka, a ne regresijski ispravak ovog koraka.

## Nalaz

Pronađen je race rubni slučaj u DELETE-u: rezultat zaključavajućeg upita bio je zanemaren. Ako bi drugi zahtjev u međuvremenu obrisao zapis, kod bi nepotrebno provjeravao posudbe i pokušao obrisati zastarjeli ORM objekt. Minimalni ispravak provjerava rezultat `SELECT ... FOR UPDATE` i odmah vraća kontrolirani `404 / not_found` kada retka više nema.

## Pokretanje

Iz `api/`:

```powershell
python -m pytest tests/test_collection_crud_matrix_11b2b.py tests/test_collection_crud_api.py tests/test_collection_crud_database.py tests/test_collections_api.py tests/test_card_loans_collection_safety.py tests/test_request_body_validation.py -q
python -m pytest tests -q
python -m ruff check .
python -m ruff format --check .
```

Ciljana CRUD cjelina: `99 passed`. Nova matrica: sedam testova. Puni backend suite: `432 passed`. `ruff check .` i `ruff format --check .` prolaze; Ruff potvrđuje 89 pravilno formatiranih Python datoteka.

## Izvan opsega

Nisu mijenjani modeli, migracije, poslovna pravila, `.env`, stvarna baza, osobne datoteke ni Vue frontend. Nisu izvedeni commit, push ili merge.
