# Korak 11B.2C — regresijska provjera Excel importa

Datum: 16. 11. 2026. Branch: `fix/backend-validation`. Alembic ostaje `004 (head)`.

## Cilj i opseg

Pregledani su endpointi `preview` i `apply`, upload validacija, `.xlsx` parser, planiranje promjena, `plan_token`, načini `replace` i `add`, zaštita aktivnih posudbi te transakcijsko zaključavanje. Testovi koriste generirane Excel datoteke, mockove i SQLite bazu; stvarna korisnička kolekcija i PostgreSQL podaci nisu korišteni.

## Prethodno postojeća pokrivenost

### Autorizacija i upload

- Vlasnik može koristiti preview/apply, a administrator nema automatski pristup tuđoj kolekciji.
- Vlasništvo se provjerava prije čitanja uploada.
- Prazna datoteka, pogrešna ekstenzija i upload veći od 6 MB vraćaju kontrolirani `422` odnosno `413` bez planiranja ili primjene.

### Parser i mapiranje

- Valjani višesheet `.xlsx`, ignoriranje preglednog sheeta i razlikovanje originala od reprinta.
- Neispravne količine, duplikati redaka, nepoznati sheetovi, nepoznata izdanja i pogrešni stupci.
- Nejasne varijante zahtijevaju točan `printing_id`; pogrešan ili nepoznat ID blokira apply.
- Datoteka s bilo kojom greškom ima `can_apply=false`, a apply vraća `422` bez djelomičnog upisa.
- Redak s napomenom bez količine preskače se uz upozorenje; prazna napomena ne briše postojeću.

### Preview, token i načini uvoza

- Preview ne zapisuje u `collection_entries`.
- Token ovisi o sadržaju datoteke, načinu uvoza, korisniku i relevantnom stanju kolekcije.
- Promijenjena datoteka ili `replace`/`add` način uz stari token vraćaju `409 / stale_import_preview`.
- `replace` mijenja samo izdanja navedena u datoteci i ne briše ostale zapise.
- `add` povećava postojeću količinu i ne prepisuje postojeću napomenu.
- Postojeći zapis može se postaviti na nulu u `replace` načinu, dok novi prazan zapis s nulom nije stvoren.

### Posudbe i stale stanje

- Preview odbija `replace` ispod aktivno posuđene količine.
- Apply ponovno provjerava posudbe i odbija novu posudbu nastalu nakon previewa.
- Postojeći redci zaključavaju se s `FOR UPDATE` prije ponovne provjere stanja i aktivnih posudbi.

## Nove regresijske provjere

U `api/tests/test_collection_excel_import.py` dodano je devet testova:

1. Tuđi `apply` završava s `403` prije čitanja datoteke, uključujući administratorskog korisnika.
2. Oštećen `.xlsx` kroz HTTP vraća siguran `422 / invalid_excel`, bez tracebacka, `zipfile` detalja ili poziva apply funkcije.
3. `plan_token` je vezan uz korisnika; plan drugog korisnika ne može potvrditi tuđi preview.
4. Sintaktički valjan, ali izmijenjen 64-znamenkasti token vraća `409` bez upisa.
5. Promjena relevantnog zapisa kolekcije između previewa i applyja vraća `409` i ne prepisuje novije stanje.
6. Drugi `add` nakon novog previewa ponovno povećava količinu, čime je dokumentirana namjerna neidempotentnost.
7. DON!! redak bez točnog `printing_id` blokira cijeli apply s `422` i ne stvara zapis.
8. Apply redoslijed izričito je potvrđen kao `FOR UPDATE` zaključavanje postojećih redaka prije upita aktivnih `lent` posudbi.
9. Izolirani HTTP tok `preview → promjena kolekcije → apply sa starim tokenom` vraća `409 / stale_import_preview` i čuva noviju količinu i napomenu.

## Plan token — stvarni API ugovor

`plan_token` je deterministički SHA-256 sažetak plana, a ne JWT i nije spremljena serverska sesija. Nema vremensku oznaku ni rok valjanosti, pa aktualni API nema zaseban koncept “isteklog” plan tokena. Token prestaje odgovarati kada se promijene datoteka, način, korisnik, relevantno stanje kolekcije ili planirane greške/promjene. Izmijenjeni ili zastarjeli token vraća `409 / stale_import_preview`.

## Integritet, transakcije i konkurentnost

- Sve provjere plana, zaključanog stanja i posudbi izvode se prije promjena ORM objekata kad god je moguće.
- `flush()` je jedan završni korak; `IntegrityError` se pretvara u `409 / import_conflict`.
- FastAPI `get_db` dependency radi commit samo nakon uspjeha, a rollback na svaku iznimku, pa neuspješan HTTP apply ne smije ostaviti djelomične promjene.
- Postojeći zapisi zaključavaju se determinističkim poretkom `printing_id`, što smanjuje rizik deadlocka i usklađeno je sa stvaranjem posudbi.
- Novi zapisi nemaju postojeći redak koji se može zaključati; paralelni create štiti unique constraint `(user_id, printing_id)`, a gubitnik dobiva kontrolirani konflikt i rollback.

SQLite ignorira stvarnu semantiku `FOR UPDATE`. Testovi potvrđuju poslovna pravila, generirani PostgreSQL SQL i redoslijed poziva, ali ne dokazuju raspoređivanje stvarnih paralelnih transakcija.

Za potpunu PostgreSQL integracijsku provjeru potrebna je zasebna prazna testna baza i paralelni scenariji:

- dva istodobna applyja koji stvaraju isti zapis;
- apply nasuprot ručnom PATCH-u istog izdanja;
- apply nasuprot stvaranju nove `lent` posudbe;
- prisilni konflikt na kasnom `flush()` koraku uz potvrdu potpunog rollbacka cijele transakcije.

## Nalaz

Nije pronađena nova produkcijska greška. Aktualni ugovor je dosljedan: token nema vremenski rok, `add` je namjerno neidempotentan uz novi preview, a neuspješni ili zastarjeli planovi završavaju prije djelomičnog upisa.

## Pokretanje

Iz `api/`:

```powershell
python -m pytest tests/test_collection_excel_import.py tests/test_http_error_contract.py tests/test_card_loans_collection_safety.py -q
python -m pytest tests -q
python -m ruff check .
python -m ruff format --check .
```

Ciljana Excel/HTTP/loan-safety cjelina: `61 passed`. Dodano je devet testova. Puni backend suite: `441 passed`. `ruff check .` i `ruff format --check .` prolaze; Ruff potvrđuje 89 pravilno formatiranih Python datoteka.

## Izvan opsega

Nisu mijenjani modeli, migracije, poslovna pravila, `.env`, stvarna baza, osobne Excel datoteke ni Vue frontend. Nisu izvedeni commit, push ili merge.
