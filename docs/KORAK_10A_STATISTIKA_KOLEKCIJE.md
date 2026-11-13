# Korak 10A — Statistika osobne kolekcije i playsetovi

**Branch:** `feat/collection-stats`
**Datum pripreme:** 13. 11. 2026.
**Status:** implementacija i izolirani testovi pripremljeni; lokalni Swagger, puni pytest i commit još se potvrđuju.

## 1. Cilj i opseg

Aplikacija treba samostalno, bez Excela, izračunavati koliko korisnik **posjeduje fizičkih primjeraka**, koliko ima **različitih izdanja** te koliko je **dovršenih playsetova**. Podaci se čitaju iz već postojeće baze (`collection_entries`, `card_printings`, `cards`, `card_sets`). Ovdje ništa ne mijenjamo u bazi i **ne stvaramo migraciju `005`**.

Razvoj je podijeljen:

- **10A (ovaj korak):** statistika i privatni API.
- **10B (sljedeći korak):** filteri `owned`, `missing` i `playset`, uz odabir točnog printinga.

## 2. API endpoint i sigurnost

`GET /collections/{user_id}/stats`

- Potreban je valjan JWT **access token** u Swaggeru (`Authorize`).
- `user_id` mora biti pozitivan cijeli broj.
- Samo vlasnik smije vidjeti svoju statistiku. Ni admin nema automatski pristup tuđim kolekcijama.
- API vraća `200 OK` s Pydantic shemom `CollectionStatsResponse`.
- Bez tokena: `401 invalid_credentials`; tuđi ID: `403 forbidden`; nevaljan ID: `422 validation_error`.
- Endpoint je **isključivo GET**: ne mijenja količine, napomene, posudbe niti katalog.

**Primjer formata odgovora na maloj, izmišljenoj testnoj kolekciji** (nisu tvoje stvarne brojke):

```json
{
  "user_id": 3,
  "total_cards": 26,
  "distinct_printings": 5,
  "playsets": 4,
  "playsets_by_type": {
    "leader": 1,
    "don": 1,
    "other": 2
  }
}
```

`playsets_by_type` je pomoćna dijagnostika; zbroj njezinih vrijednosti jednak je `playsets`.

## 3. Definicije i pravila

| Statistika | Kako je računamo |
| --- | --- |
| `total_cards` | Zbroj svih **vlasničkih** `quantity` većih od nule |
| `distinct_printings` | Broj redaka s `quantity > 0`, po jedinstvenom `(user_id, printing_id)` |
| `playsets` | Broj takvih izdanja koja zadovoljavaju prag; jedan playset po izdanju |
| `playsets_by_type` | Broj zadovoljenih playsetova razvrstan u Leader / DON / ostali |

### Pragovi

- **Leader**: minimalno `1` primjerak. Prepoznavanje po `cards.card_type = 'Leader'`, a ako tip nije pouzdan i po `card_printings.rarity = 'L'` (ili `Leader`).
- **DON!!**: minimalno `10` primjeraka. Prepoznavanje po `card_type`, `card_sets.code = 'DON'` ili kodu karte `DON-...`.
- **Character, Event, Stage i neodređeni tipovi**: minimalno `4` primjerka.

Tekstualne oznake čitamo bez razlikovanja velikih/malih slova i s uklonjenim rubnim razmacima. Prednost ima provjera za Leader pa za DON!!.

**Značajne odluke:**

1. Različite ilustracije i reprintovi brojčano su **različita izdanja** (`printing_id`), iako dijele isti osnovni kod karte.
2. Osam kopija obične karte = **jedan dovršen playset** u ovim statistikama, ne dva. Ne prikazujemo broj grupa od četiri primjerka.
3. `quantity = 0` ne daje ni kartu, ni različito izdanje, ni playset.
4. Posudbe `lent` ne umanjuju vlasništvo, a `borrowed` ga ne uvećavaju. Fizička dostupnost je druga metrika i nije dio ovoga endpointa.
5. Ako u katalogu nedostaju metapodaci, ne izmišljamo tip. Primjenjuje se opisani fallback, a zatim standardni prag 4.

## 4. Arhitektura — zašto ovako

| Datoteka | Uloga |
| --- | --- |
| `app/repositories/collection_stats_repo.py` | Jedan SQLAlchemy `SELECT` uz `JOIN` na printing, card i set; filtrira po vlasniku i pozitivnoj količini |
| `app/services/collection_stats_service.py` | Autorizacija prije upita, zbrojevi i dodjela kategorija playsetova |
| `app/services/playset_service.py` | Zajedničko pravilo pragova i fallbackovi; zadržava staru funkciju `is_playset()` |
| `app/schemas/collection_stats.py` | Oblik i validacija JSON odgovora |
| `app/routers/collections.py` | Nova ruta pod postojećim routerom, bez izmjene `main.py` |
| `tests/test_collection_stats_database.py` | Stvarni SQLAlchemy upiti nad SQLite testnom bazom, vlasništvo, različiti printinzi, nulta količina, posudbe |
| `tests/test_collection_stats_api.py` | Swagger/HTTP pravila bez stvarnog korisničkog tokena ili PostgreSQL-a |

Koristimo **jedan SQL upit bez N+1** dohvaćanja povezanih modela, nakon čega Python računa tri statistike. To je dovoljno učinkovito za osobnu kolekciju veličine nekoliko tisuća izdanja i jednostavno za održavanje. U 10B ćemo proširiti logiku filtriranja, ne ovaj GET endpoint.

## 5. Instalacija na Windowsu

1. U VS Codeu potvrdi da si na branchu `feat/collection-stats` i da nemaš necommitirane osobne promjene.
2. Raspakiraj ZIP u **korijen** `C:\Users\admin\OPTCG_Collection`, uz prepisivanje samo navedenih projektnih datoteka.
3. Pokreni/ostavi Docker i Uvicorn prema glavnom README-u.
4. U drugom terminalu iz `api/` pokreni:

```powershell
python -m pytest tests/test_collection_stats_database.py tests/test_collection_stats_api.py -q
python -m pytest tests -q
alembic current
```

Očekujemo da **novi testovi prođu**, da prethodni skup od 180 testova ne dobije regresije i da Alembic ostane **`004 (head)`**. Nije potreban `alembic upgrade head` ni seed.

## 6. Swagger — ručna provjera

1. Otvori `http://127.0.0.1:8000/docs`.
2. Prijavi se kao i dosad, zatim klikni `Authorize` i unesi JWT access token.
3. Otvori **collection-stats** → `GET /collections/{user_id}/stats`.
4. Postavi `user_id=3` i klikni `Execute`.
5. Očekujemo HTTP `200`, `total_cards=2133` i `distinct_printings=662`, ako se vlasničke količine od Excel uvoza nisu mijenjale. **Broj `playsets` treba usporediti s 243 iz Excela, a ne pretpostaviti da je isti.**
6. Postavi `user_id` drugog korisnika: očekujemo `403` i `code=forbidden`.
7. Pokušaj bez autorizacije: očekujemo `401`.
8. Provjeri `user_id=0`: očekujemo `422`.

Za veću sigurnost usporedi rezultat sa SQL upitom iz idućeg odjeljka.

## 7. PostgreSQL provjera u TablePlusu

Osnovne dvije metrike:

```sql
SELECT
    COUNT(*) FILTER (WHERE quantity > 0) AS distinct_printings,
    COALESCE(SUM(quantity), 0) AS total_cards
FROM collection_entries
WHERE user_id = 3;
```

Ovo je tvoj ranije provjereni SQL: **662 različita izdanja, 2.133 ukupnih primjeraka**.

Za nezavisnu usporedbu broja playsetova i pragova s Python izračunom:

```sql
SELECT
    COUNT(*) AS distinct_printings,
    COALESCE(SUM(ce.quantity), 0) AS total_cards,
    COUNT(*) FILTER (
        WHERE ce.quantity >= CASE
            WHEN LOWER(TRIM(COALESCE(c.card_type, ''))) = 'leader'
              OR LOWER(TRIM(COALESCE(cp.rarity, ''))) IN ('l', 'leader') THEN 1
            WHEN LOWER(TRIM(COALESCE(c.card_type, ''))) IN ('don', 'don!!', 'don!!!')
              OR LOWER(TRIM(cs.code)) = 'don'
              OR LOWER(c.code) LIKE 'don-%' THEN 10
            ELSE 4
        END
    ) AS playsets
FROM collection_entries ce
JOIN card_printings cp ON cp.id = ce.printing_id
JOIN cards c ON c.id = cp.card_id
JOIN card_sets cs ON cs.id = cp.product_set_id
WHERE ce.user_id = 3 AND ce.quantity > 0;
```

Ako rezultat `playsets` nije **243**, uspoređivat ćemo pojedinačne razlike s Excelom; nećemo automatski mijenjati baze ili pragove kako bi se broj „pogodio“. Razlozi mogu biti nepotpuni tip/rarity, razlika među reprintovima ili drukčija Excel formula.

## 8. Testovi i Git workflow

Novi izolirani testovi provjeravaju: HTTP 200/401/403/422, nepokretanje upita za neautorizirane, neprihvaćanje POST/PATCH, zero-quantity, odvojene korisnike, printinge istog card koda, borrowed/lent posudbe i pragove 1/4/10. Provjerava se i to da računanje ne mijenja redove u bazi.

```powershell
cd C:\Users\admin\OPTCG_Collection\api
python -m pytest tests/test_collection_stats_database.py tests/test_collection_stats_api.py -q
python -m pytest tests -q
python -m ruff check .
python -m ruff format --check .
alembic current
```

Nakon uspješne provjere i pregleda staged promjena:

```powershell
cd C:\Users\admin\OPTCG_Collection
git status
git add README.md docs/KORAK_10A_STATISTIKA_KOLEKCIJE.md api/app/routers/collections.py api/app/repositories/collection_stats_repo.py api/app/services/collection_stats_service.py api/app/services/playset_service.py api/app/schemas/collection_stats.py api/tests/test_collection_stats_database.py api/tests/test_collection_stats_api.py
git diff --cached --check
git diff --cached --stat
git commit -m "feat: add personal collection statistics and playsets"
git push -u origin feat/collection-stats
```

**PR u `main` radimo kada završimo cjelinu 10A+10B**, ne sada. Osobni Excel, `.env` i `backups/` nikada ne dodavati u Git.
