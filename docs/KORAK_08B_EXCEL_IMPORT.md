# OPTCG — Korak 8B: uvoz osobne kolekcije iz Excela

**Branch:** `feat/catalog-enrichment`
**Status:** implementacija spremna za lokalnu provjeru
**Tema:** osobna kolekcija, `.xlsx`, pregled prije upisa, zaštita tuđih podataka

## Cilj

Dodajemo mogućnost da prijavljeni korisnik uveze **vlastite količine i napomene** iz više-sheet Excel datoteke u `collection_entries`, bez mijenjanja zajedničkog kataloga `cards` ili `card_printings`.

Naš Excel koristi zaglavlje `Broj karte | Ime karte | Boja | Količina | Rijetkost | Slika | Napomena` i sheetove OP01–OP18, EB01–EB05, ST01–ST36, PRB01–PRB02, P, PREGLED i VARIJANTE. **PREGLED se ignorira.** Sheet OP18 je dopušten, ali pozitivne količine neće biti uvezene dok odgovarajuća izdanja ne postoje u bazi.

Kod PRB reprintova **nije dovoljno** tražiti kartu samo po `OPxx-yyy`: ključ je `(oznaka sheeta, broj karte, regular)`. Zato `OP01-016` iz `OP01` i `OP01-016` iz `PRB01` ostaju zasebna fizička izdanja.

## Nove rute

| Metoda | Ruta | Rezultat |
| --- | --- | --- |
| POST | `/collections/{user_id}/import/preview?mode=replace` | Validira Excel, vraća plan bez promjene baze |
| POST | `/collections/{user_id}/import/apply?mode=replace&plan_token=...` | Ponovno validira i primjenjuje točno pregledani plan |

Obje rute traže JWT access token. I **administrator** smije uvoziti samo u svoju kolekciju, osim ako u budućnosti ne dodamo posebno autoriziranu administratorsku proceduru.

Za oba poziva šalje se isti `.xlsx` u multipart formatu, pod nazivom polja `file`. Nema server-side pohrane osobnih Excel datoteka. Maksimalna veličina uploada: 6 MB.

### Načini uvoza

- `mode=replace`: za izdanja **navedena u Excelu** postavi količine iz Excela. Ostatak postojeće kolekcije ne briše se. Prazna napomena ne briše staru napomenu.
- `mode=add`: dodaj Excel količine na postojeće; nemoj mijenjati postojeće napomene. **Ponovljeni uvoz s novim pregledom može drugi put povećati količine!**
- Prazna količina znači preskoči red. Količina `0` za nepostojeći zapis bez napomene ne stvara nepotrebnu stavku, ali postojeća stavka može se postaviti na `0` pomoću `replace`.
- Napomena bez količine ignorira se uz upozorenje, što je važno za 119 OP18 redaka iz našeg ranijeg Excela.

### Zaštite

- Preview nikada ne mijenja bazu.
- `plan_token` je SHA-256 potpis pregleda koji ovisi o datoteci, načinu uvoza, korisniku i trenutačnom stanju uključenih stavki. Ako se išta od navedenoga promijeni, apply vraća **409** i potrebno je ponoviti preview.
- Ako postoji bilo kakva **greška** (nepoznato izdanje, duplikat, negativna/ne-cjelobrojna količina, nepoznat sheet s podacima), `can_apply=false`; apply vraća **422** i ne upisuje ništa.
- Poznati sheet `VARIJANTE` zahtijeva dodatni stupac `ID izdanja` i **ispravan `printing_id` u svakom popunjenom retku**, jer sam kartični kod nije dovoljan za izbor Alt Art/Manga izdanja.
- I za budući `DON` sheet potreban je `ID izdanja` dok ne povežemo vanjske DON identifikatore; bez odgovarajućih zapisa u katalogu uvoz neće proći.
- Nema novih migracija; koristi se postojeća `collection_entries` iz migracije `001`.

## 1. Kopiranje datoteka

Raspakiraj ZIP u korijen `C:\Users\admin\OPTCG_Collection`, uz očuvanje putanja. Paket **dodaje**:

```text
api/app/routers/collection_import.py
api/app/services/collection_excel_import.py
api/tests/test_collection_excel_import.py
docs/KORAK_08B_EXCEL_IMPORT.md
```

Paket također **nadopunjuje postojeći** `api/app/routers/collections.py` jednom registracijom podroutera na dnu. Ako si tu datoteku u međuvremenu mijenjao, usporedi promjene prije zamjene.

**Ne mijenjaj `main.py` niti postojeće migracije.** `collections_router` već je registriran.

## 2. Dvije Python ovisnosti

U postojeći `api/requirements.txt` **dodaj** (nemoj zamijeniti ostale retke):

```text
openpyxl>=3.1,<4
python-multipart>=0.0.9
```

Zatim u PowerShellu iz `api/` s aktivnim virtualnim okruženjem:

```powershell
uv pip install -r requirements.txt
```

`openpyxl` čita `.xlsx` u read-only načinu. `python-multipart` omogućuje Swaggerov upload datoteke.

## 3. Pokretanje testova

```powershell
cd C:\Users\admin\OPTCG_Collection\api
python -m pytest tests/test_collection_excel_import.py -q
python -m pytest tests -q
```

U izoliranoj lokalnoj provjeri prošla su **22 nova Excel testa** i **43 testa** kada smo dodali prethodne testove CRUD kolekcije. Ukupan broj testova tvog repozitorija provjeri lokalno; ne pretpostavljamo unaprijed točan broj.

## 4. Swagger — obavezno prvo pregled

Pokreni Uvicorn i otvori `http://127.0.0.1:8000/docs`.

1. Prijavi se i klikni **Authorize**, koristi `access_token` (nemoj slati token u razgovor).
2. U `GET /auth/me` pročitaj vlastiti ID (`user_id`).
3. Otvori `POST /collections/{user_id}/import/preview`, upiši svoj `user_id`, ostavi `mode=replace` i odaberi **svoju osobnu** `.xlsx` datoteku.
4. Pogledaj `matched`, `create`, `update`, `error_count`, `warning_count`, `can_apply` i `samples`.
5. **Ne pokreći apply** ako `can_apply=false`, ako broj podudaranja nije očekivan ili ako ima neobjašnjenih upozorenja.
6. Ako plan odgovara očekivanjima, kopiraj **cijeli `plan_token`** iz previewa.
7. Po potrebi napravi novu sigurnosnu kopiju PostgreSQL-a. Zatim otvori `POST /collections/{user_id}/import/apply`, postavi isti `mode`, zalijepi `plan_token` i **ponovno odaberi istu datoteku**.
8. Nakon `200 OK` provjeri `GET /collections/{user_id}` i brojeve u TablePlusu.

**Napomena:** ako si u međuvremenu ručno promijenio količine ili učitao drukčiju Excel datoteku, dobit ćeš 409. Napravi novi preview.

### Naša probna Excel datoteka

Lokalna provjera `OPTCG_Moja_kolekcija(1).xlsx` nad testnom bazom sastavljenom iz našeg prvog kataloškog CSV-a dala je:

```text
590 redaka s upisanom količinom
1.772 ukupno primjeraka
590/590 podudaranja s konkretnim izdanjima
0 grešaka
1 skupno upozorenje: 119 napomena bez količine (preskače se)
```

To je **probni rezultat na kopiji datoteke i testnom katalogu**, ne potvrda da je korisnička kolekcija već uvezena u tvoju PostgreSQL bazu. Ako je tvoj lokalni Excel noviji, brojevi će se razlikovati.

## 5. Provjera u TablePlusu nakon applya

```sql
SELECT user_id, COUNT(*) AS razlicitih_izdanja, SUM(quantity) AS ukupno_komada
FROM collection_entries
GROUP BY user_id
ORDER BY user_id;
```

Za vlastiti račun možeš dodatno pogledati:

```sql
SELECT c.code, p.variant_code, s.code AS product_set,
       e.quantity, e.note
FROM collection_entries AS e
JOIN card_printings AS p ON p.id = e.printing_id
JOIN cards AS c ON c.id = p.card_id
JOIN card_sets AS s ON s.id = p.product_set_id
WHERE e.user_id = 3  -- zamijeni stvarnim ID-jem
ORDER BY s.code, c.code;
```

## 6. README, commit i push na kraju Koraka 8B

Nakon što potvrdiš Swagger i sve testove, dodaj u README novi odjeljak **Excel import osobnih kolekcija** i dva nova endpointa. Navedi `replace`/`add`, `plan_token`, zaštitu vlasništva, način provjere i ograničenja DON/VARIJANTE. Označi Excel import kao testiran tek nakon lokalne potvrde.

U **korijenu projekta**:

```powershell
git status
git add api/app/routers/collections.py api/app/routers/collection_import.py api/app/services/collection_excel_import.py api/tests/test_collection_excel_import.py api/requirements.txt docs/KORAK_08B_EXCEL_IMPORT.md README.md
git diff --cached --check
git diff --cached --stat
git commit -m "feat: add validated Excel import for personal collections"
git push
```

Prije `git add` provjeri da osobne Excel datoteke, `.env`, `backups/` i `data/koala_snapshot/` ne ulaze u commit. Osobnu `.xlsx` kolekciju ne stavljaj u javni GitHub repozitorij.

## Nakon 8B

Nakon provjere previewa i uvoza osobnih količina prelazimo na evidenciju posudbi (`card_loans`, migracija `004`) i kasniju Vue stranicu s malim sličicama karata i većim prikazom na mouseover/dodir.
