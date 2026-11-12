# OPTCG — Predavanje 5, Korak 8A: CRUD osobne kolekcije

**Branch:** `feat/catalog-enrichment` (nastavljamo postojeći branch, bez PR-a zasad)

## Cilj

Dosadašnji `GET /collections/{user_id}` proširujemo tako da prijavljeni korisnik može **dodati, ažurirati i ukloniti** jedno fizičko izdanje karte iz svoje kolekcije.

- `GET /collections/{user_id}` — postojeći popis, **bez promjene JSON oblika**
- `POST /collections/{user_id}/entries` — **201 Created**, zahtjev s `printing_id`, `quantity` i opcionalnim `note`
- `PATCH /collections/{user_id}/entries/{printing_id}` — **200 OK**, promijeni samo navedena polja
- `DELETE /collections/{user_id}/entries/{printing_id}` — **204 No Content**, ukloni samo svoj kolekcijski zapis

**Važno:** `printing_id` nije isto što i `card_id`. Ako jedna karta ima regular, Manga ili alt-art izdanje, svako ima svoj `printing_id`.

### Pravila

- Vlasnik smije mijenjati **samo svoju** kolekciju; administratorska uloga ne zaobilazi vlasništvo.
- Jedno izdanje smije biti samo jednom u korisnikovoj kolekciji (unique u bazi, dodatna provjera u servisu).
- `quantity` je cijeli broj od 0 do 999.999. `0` je dopušten, ali **nije playset**.
- `note` je opcionalan tekst do 1000 znakova. `PATCH {"note": null}` briše napomenu.
- `PATCH` ne mijenja polje koje nije navedeno. `PATCH {}` ili `{"quantity": null}` vraćaju 422.
- Nepostojeće izdanje ili zapis kolekcije vraća 404; duplikat pri `POST` vraća 409; pristup tuđoj kolekciji 403; bez prijave 401.
- Brisanje kolekcijskog zapisa **ne briše kartu iz zajedničkog kataloga**.

## 1. Kopiranje datoteka

Raspakiraj ZIP u **korijen** `C:\Users\admin\OPTCG_Collection`, uz zamjenu ovih datoteka:

```text
api/app/routers/collections.py
api/app/repositories/collection_repo.py
api/app/services/collection_service.py
api/app/schemas/collection.py
```

Dodaju se dva testa i ovaj dokument (u `docs/`). **Ne zamjenjuj `api/app/main.py`** — već imaš registriran `collections_router` iz ranijeg koraka. Nema promjene modela, `alembic upgrade` nije potreban.

Ako si neku od ovih datoteka u međuvremenu ručno mijenjao, prvo usporedi razlike u VS Codeu.

## 2. Testiranje

```powershell
cd C:\Users\admin\OPTCG_Collection\api
python -m pytest tests/test_collection_crud_api.py tests/test_collection_crud_database.py -q
python -m pytest tests -q
```

Lokalno su prošla **21 nova testa** i **30/30** kada se uključe prijašnji testovi pristupa kolekciji i vlasništva. Kompletni testovi tvoje stvarne aplikacije trebaju se potvrditi lokalno.

## 3. Swagger: ručna provjera

Pokreni `python -m uvicorn app.main:app --reload` i otvori http://127.0.0.1:8000/docs.

1. `POST /auth/login` s vlastitim računom. Kopiraj samo `access_token` u Swagger **Authorize** (token nemoj dijeliti u porukama).
2. `GET /auth/me` — pronađi svoj `id` (npr. `7`).
3. `GET /cards` — pronađi karticu. Zatim `GET /cards/{card_id}` i u `printings` pronađi **točan `id` izdanja** (npr. `13`).
4. Dodaj izdanje u vlastitu kolekciju:

   `POST /collections/7/entries`

   ```json
   {"printing_id": 13, "quantity": 3, "note": "Za deck"}
   ```

5. Provjeri `GET /collections/7`. Novi zapis mora biti vidljiv.
6. Promijeni samo količinu:

   `PATCH /collections/7/entries/13`

   ```json
   {"quantity": 4}
   ```

   `note` treba ostati `"Za deck"`.
7. Ukloni napomenu: `PATCH /collections/7/entries/13` s `{"note": null}`.
8. Pokušaj ponovno dodati isto izdanje — očekuje se 409. Pokušaj tuđi `user_id` — očekuje se 403.
9. `DELETE /collections/7/entries/13` vraća 204; karta ostaje u katalogu.

**Brojevi 7 i 13 su primjeri.** Koristi stvarni korisnički ID i `printing_id` iz svoje baze. Radi testiranja upotrijebi količinu koju želiš ili testni zapis, a ne izmišljeni ID.

## 4. README (dodaj nakon uspješne provjere)

U README-ov odjeljak o osobnim kolekcijama dodaj:

```markdown
### CRUD osobne kolekcije (Korak 8A)

Prijavljeni vlasnik može dodavati, mijenjati i brisati zapise za točno
fizičko izdanje karte (`printing_id`) putem `POST`, `PATCH` i `DELETE`
ruta pod `/collections/{user_id}/entries`. `quantity >= 0`; `quantity = 0`
se ne označava kao playset. `PATCH` mijenja samo navedena polja.
Duplikati se odbijaju s 409, nepostojeći zapisi s 404, tuđa kolekcija
s 403. U bazi se ne brišu zajedničke karte niti korisnički računi.
Excel import i uvoz vlastitih količina slijede u Koraku 8B.
```

## 5. Commit i push na kraju Koraka 8A

Iz korijena repozitorija:

```powershell
cd C:\Users\admin\OPTCG_Collection
git status
git add README.md api/app/routers/collections.py api/app/repositories/collection_repo.py api/app/services/collection_service.py api/app/schemas/collection.py api/tests/test_collection_crud_api.py api/tests/test_collection_crud_database.py docs/KORAK_08A_CRUD_KOLEKCIJE.md
git diff --cached --check
git diff --cached --stat
git commit -m "feat: add personal collection CRUD endpoints"
git push
```

Nemoj raditi commit ako testovi ne prolaze. `git push` je dovoljan jer si već postavio upstream za `feat/catalog-enrichment`.

## 6. Sljedeći korak

**Korak 8B — uvoz osobne kolekcije iz `.xlsx`:** parsiranje količina i napomena, prepoznavanje `printing_id`, pregled prije primjene, izbor **zamijeni** ili **zbroji**, transakcijski upis uz kontrolu duplikata. Nećemo automatski zamjenjivati kriva ili dvosmislena izdanja.
