# Korak 11B.2A — autentikacija, autorizacija i vlasništvo kolekcije

Datum: 16. 11. 2026. Branch: `fix/backend-validation`. Migracija nije potrebna; Alembic ostaje `004 (head)`.

## Cilj i opseg

Regresijski su provjereni registracija i prijava, namjena i valjanost JWT tokena, aktualno stanje korisnika i uloge u bazi, administratorske rute, vlasništvo osobne kolekcije te JWT identitet osobnih kataloških filtera. Testovi koriste mockove ili izolirane SQLite podatke; ne čitaju niti mijenjaju stvarne korisnike i osobne kolekcije.

## Što je već bilo pokriveno

- Osnovno stvaranje i dekodiranje access/refresh tokena te odbijanje neispravnog JWT-a.
- Validacija registracijske sheme, bcrypt granica od 72 bajta i zabrana slanja uloge `admin`.
- `401` bez tokena, `403` za običnog korisnika na `/admin/users` i dopušten pristup administratoru.
- Čitanje aktualne uloge iz baze umjesto vjerovanja ulozi spremljenoj u JWT-u.
- Vlasnik smije pristupiti svojoj kolekciji, drugi korisnik ne smije, a administrator nema automatsko pravo nad tuđom kolekcijom.
- CRUD odgovori `404`, `409` i `422`, uz provjeru da nevaljani zahtjevi ne pozivaju repository.
- Javni `/cards` bez prijave, `401` za osobni filter bez valjanog JWT-a i korištenje identiteta prijavljenog korisnika umjesto query parametra `user_id`.
- Strogo odbijanje nepoznatih JSON polja u auth i kolekcijskim zahtjevima.
- Ujednačen oblik kontroliranih grešaka te siguran generički `500` bez tracebacka i internih detalja.

## Nove regresijske provjere

Nova datoteka `api/tests/test_auth_authorization_matrix_11b2a.py` dodaje 32 slučaja:

### Registracija i prijava

- Valjana registracija uvijek stvara običnog korisnika i ne vraća lozinku ni hash.
- Prekratko/neispravno korisničko ime, kratka lozinka, pogrešan tip i pokušaj slanja uloge završavaju s `422` prije servisa.
- Duplicirano korisničko ime vraća `409` / `username_taken` bez pokušaja upisa.
- Pogrešna lozinka, nepostojeći korisnik i deaktivirani korisnik vraćaju isti sigurni `401` odgovor bez tokena ili osjetljivih podataka.
- Uspješna prijava vraća različite access i refresh tokene s ispravnom `type` namjenom.

### JWT životni ciklus

- Refresh token ne može pristupiti `/auth/me`, a access token ne može se koristiti na `/auth/refresh`.
- Istekli, sintaktički neispravni i izmijenjeni tokeni vraćaju `401` prije dohvata korisnika.
- Nepostojeći i deaktivirani korisnik odbijaju se i za access i za refresh tok.
- Valjani refresh aktivnog korisnika izdaje valjani access/refresh par. Trenutačna stateless JWT implementacija nema pohranu ni opoziv prethodnog refresh tokena, pa test ne tvrdi da postoji stvarna rotacija tokena.
- Tijela grešaka ne sadrže poslani JWT, lozinku ni hash.

### Uloge, vlasništvo i osobni filteri

- Uloga iz aktualnog zapisa baze ima prednost pred zastarjelom ili izmijenjenom ulogom iz JWT-a u oba smjera.
- Promjena `user_id` u GET/POST/PATCH/DELETE URL-u ne zaobilazi vlasništvo, čak ni kada je prijavljeni korisnik administrator.
- Zabranjeni pokušaji završavaju prije čitanja ili izmjene zapisa kolekcije.
- `collection_status=owned` koristi isključivo ID iz validiranog JWT-a i ignorira proizvoljni `user_id` query parametar.
- Javni kataloški zahtjev ne validira nepovezani zastarjeli bearer token i ostaje dostupan bez prijave.

## Rezultat pregleda

Nije pronađena nova produkcijska greška. Jedini početni pad bio je nepotpun testni mock koji nije simulirao SQLAlchemy default `is_active=True`; ispravljen je testni adapter, bez promjene aplikacijskog koda ili poslovnih pravila.

Sigurnosno bitne postojeće odluke potvrđene su:

- `get_current_user` provjerava potpis, issuer, istek, namjenu tokena, postojanje i aktivnost korisnika.
- `require_role` koristi aktualnu ulogu iz baze.
- `ensure_collection_owner` uspoređuje JWT korisnika s vlasnikom iz URL-a i ne daje administratorski bypass.
- Osobni kataloški filter ne prihvaća korisnički ID iz zahtjeva.

## HTTP ugovor

| Status | Provjereni primjer |
| --- | --- |
| `401` | Nedostaje, istekao je, izmijenjen je ili ima pogrešnu namjenu token; korisnik ne postoji ili je deaktiviran |
| `403` | Običan korisnik na admin ruti; bilo koji korisnik, uključujući admina, nad tuđom kolekcijom |
| `404` | Nepostojeće izdanje ili zapis vlastite kolekcije |
| `409` | Zauzeto korisničko ime ili duplikat izdanja u kolekciji |
| `422` | Neispravna registracija, nepoznata JSON polja, pogrešni tipovi i nevaljani putni/query parametri |

Kontrolirane greške imaju neprazne `code` i `message`; validacijske greške dodatno imaju `errors`. Odgovori grešaka ne smiju sadržavati lozinke, JWT tokene, hash vrijednosti ili interne tracebackove.

## Pokretanje

Iz `api/`:

```powershell
python -m pytest tests/test_auth_authorization_matrix_11b2a.py -q
python -m pytest tests/test_auth_authorization_matrix_11b2a.py tests/test_jtw.py tests/test_auth_schemas.py tests/test_admin_api.py tests/test_permissions.py tests/test_collections_api.py tests/test_collection_crud_api.py tests/test_collection_filters_api.py tests/test_request_body_validation.py tests/test_http_error_contract.py -q
python -m pytest tests -q
python -m ruff check .
python -m ruff format --check .
```

Ciljana nova matrica: `32 passed`. Šira sigurnosna cjelina: `176 passed`. Puni backend suite: `425 passed`. `ruff check .` i `ruff format --check .` prolaze bez grešaka nakon formatiranja nove testne datoteke.

## Izvan opsega

Nisu mijenjani JWT rokovi, poslovna pravila, baza, migracije, `.env`, stvarni korisnici, osobni podaci ni Vue frontend. Nisu rađeni commit, push ili merge.
