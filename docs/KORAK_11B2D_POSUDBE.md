# Korak 11B.2D — potpuna regresijska provjera posudbi

Datum: 16. 11. 2026. Branch: `fix/backend-validation`. Migracija ostaje `004 (head)`.

## Cilj i opseg

Pregledani su model i migracija `card_loans`, Pydantic sheme, privatne HTTP rute, servisna pravila, repository upiti te zaštita kolekcije i Excel importa. Testovi koriste mockove i izoliranu SQLite bazu; stvarni korisnici, osobna kolekcija i postojeća PostgreSQL baza nisu korišteni.

## Prethodno postojeća pokrivenost

### Autorizacija i vlasništvo

- Sve rute zahtijevaju prijavljenog vlasnika kolekcije.
- Običan korisnik i administrator dobivaju `403` za tuđi `user_id` prije repository upita.
- Tuđi ili nepostojeći `loan_id` ne može se dohvatiti kroz vlasnički ograničen upit.
- Neautorizirani i validacijski neuspješni zahtjevi ne pozivaju create/flush operacije.

### Stvaranje posudbi

- Uspješan `lent` vraća `201` i koristi točan `printing_id`.
- Raspoloživost je `owned - outstanding_lent`; prekoračenje vraća `409 / insufficient_quantity` bez upisa.
- `borrowed` ne provjerava vlasničku količinu i ne ulazi u zbroj odlaznih posudbi.
- Nepostojeći printing vraća `404 / printing_not_found`.
- Sheme odbijaju količinu nula/negativnu/preveliku, nepoznat smjer, praznu osobu, praznu/predugu napomenu, dodatna polja i datume bez vremenske zone.
- `due_at` prije `loaned_at` vraća kontrolirani `422 / invalid_loan_dates`.
- Ulazni datumi normaliziraju se na UTC.

### Pregled i filtri

- Popis podržava `direction` i `active_only`; nepoznat smjer vraća `422`.
- Detalj posudbe vraća `404 / loan_not_found` kada vlasnički zapis ne postoji.
- Odgovor sadrži ID printinga, kod i ime karte, set, varijantu, URL slike, količine i datume.
- SQL `active_only` isključuje potpuno vraćene posudbe.

### Povrati

- Djelomični povrat povećava `quantity_returned`, smanjuje `outstanding_quantity` i ne postavlja datum zatvaranja.
- Potpuni povrat postavlja UTC `returned_at` i zatvara posudbu.
- Prevelik povrat vraća `409 / return_exceeds_outstanding`, a povrat zatvorene posudbe `409 / loan_already_returned`.
- Datum povrata prije posudbe vraća `422 / invalid_return_date`; nevaljana količina ili datum bez zone završavaju validacijom prije repositoryja.

### Zaštita kolekcije

- Aktivni `lent` zapisi sprječavaju PATCH ispod posuđene količine i DELETE kolekcijskog zapisa.
- Excel preview i apply ponovno provjeravaju minimalnu količinu, uključujući posudbu nastalu nakon previewa.
- `borrowed` ne štiti vlasničku količinu od smanjivanja jer nije dio vlastite zalihe.

## Nove regresijske provjere

Datoteka `api/tests/test_card_loans_matrix_11b2d.py` dodaje sedam testova:

1. Više aktivnih `lent` zapisa istog printinga zbraja se u jedan limit; novi zahtjev preko zajednički raspoložive količine vraća `409` bez novog zapisa.
2. Djelomični povrat ponovno oslobađa raspoložive primjerke pa se nova valjana posudba može kreirati, bez promjene `collection_entries.quantity`.
3. Novi `borrowed` zapis ne mijenja vlasničku količinu ni `outstanding_lent`, pa ne može povećati vlasništvo ili playsetove.
4. Stvarni repository upit ograničava isti `loan_id` na vlasnika; drugi korisnik dobiva `None`.
5. Više uzastopnih povrata ne može prijeći početnu količinu i ne mijenja vlasnički broj primjeraka.
6. Potpuni povrat zatvara posudbu, a sljedeći pokušaj vraća `loan_already_returned`.
7. Povrat koristi PostgreSQL `FOR UPDATE OF card_loans` nad točnim `user_id` i `loan_id`.

Prvi test dodatno bilježi redoslijed stvaranja `lent` posudbe: zaključavanje `collection_entries` retka izvršava se prije zbrajanja aktivnih odlaznih posudbi (`owned_lock → outstanding`).

## Konkurentnost i zaključavanje

Aktualni dizajn koristi dva različita zaključana resursa:

- stvaranje `lent` posudbe zaključava vlasnički `collection_entries` redak, zatim zbraja sve aktivne `lent` zapise i tek potom stvara novi zapis;
- povrat zaključava točan `card_loans` redak prije provjere preostale količine i povećanja `quantity_returned`.

To sprječava da dvije transakcije koje poštuju isti zaključani redak istodobno potroše istu zalihu ili vrate više od preostale količine. SQLite ignorira stvarnu semantiku `FOR UPDATE`; testovi potvrđuju poslovna pravila, generirani PostgreSQL SQL i redoslijed operacija, ali ne dokazuju stvarno blokiranje paralelnih transakcija.

## Obavezna PostgreSQL testna baza

Prije završnog PR-a treba postaviti zasebnu, trajnu PostgreSQL testnu bazu bez osobnih podataka. Na njoj treba pokrenuti najmanje:

- dvije paralelne `lent` transakcije koje zajedno prelaze raspoloživu količinu — samo dopušteni ukupni broj smije uspjeti;
- dva paralelna povrata istog loan retka — drugi mora vidjeti zaključano, ažurirano stanje i ne smije prekoračiti ukupnu količinu;
- povrat nasuprot novom `lent` zahtjevu istog printinga;
- stvaranje posudbe nasuprot PATCH-u, DELETE-u i Excel `replace` applyju;
- prisilni kasni DB konflikt uz potvrdu rollbacka cijelog HTTP zahtjeva;
- potvrdu stvarnog redoslijeda čekanja i odsutnosti deadlocka za definirane kombinacije.

Postojeća baza s osobnom kolekcijom ne smije se koristiti za te testove.

## Nalaz

Nije pronađena nova produkcijska greška. Postojeći model zaključavanja, vlasničko ograničenje i poslovna pravila odgovaraju aktualnom API ugovoru. Produkcijski kod i migracija nisu mijenjani.

## Pokretanje

Iz `api/`:

```powershell
python -m pytest tests/test_card_loans_matrix_11b2d.py tests/test_card_loans_api.py tests/test_card_loans_collection_safety.py tests/test_card_loans_model.py tests/test_request_body_validation.py -q
python -m pytest tests -q
python -m ruff check .
python -m ruff format --check .
```

Ciljana cjelina posudbi, modela, validacije i zaštite kolekcije: `116 passed`. Dodano je sedam testova. Puni backend suite: `448 passed`. `ruff check .` i `ruff format --check .` prolaze; Ruff potvrđuje 90 pravilno formatiranih Python datoteka.

## Izvan opsega

Nisu mijenjani modeli, migracije, poslovna pravila, `.env`, stvarna baza ni Vue frontend. Nisu izvedeni commit, push ili merge.
