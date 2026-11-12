# Korak 7 — obogaćivanje kataloga

**Branch:** `feat/catalog-enrichment`
**Izvor:** [Koala Kollect Data](https://github.com/hotavocado/koala-kollect-data), engleska opažanja službenog kartičnog popisa.
**Status:** kod pripremljen i lokalno testiran; primjenu na PostgreSQL-u potvrđuje korisnik.

## Što se dodaje

Samo **postojećim** zapisima u `cards` popunjavamo prazne vrijednosti:

- `card_type` (Leader, Character, Event, Stage), `cost`, `power`, `counter`, `life`;
- `effect_text` (efekt i tekst triggera, trenutno kao dva dijela jednog polja);
- `attributes` i `archetypes` kroz M:N povezničke tablice;
- `keywords` iz eksplicitnih oznaka efekata i posebnih pojmova (K.O., Trash);
- postojeće `colors` veze samo ako su prazne i izvor je provjerljiv;
- `card_printings.block_icon` **samo kada** postoji jedan nedvosmislen službeni osnovni (base) print i njegov URL slike odgovara lokalnoj slici iste regularne verzije.

**Razlika Countera:** numerički `counter` (+1000, +2000 itd.) dolazi iz numeričkog polja. Keyword `Counter` povezuje se samo ako u efektu piše `[Counter]`. Ne miješamo dvije stvari.

Ne mijenjamo identitete (`cards.id`, `card_printings.id`), kartične brojeve, imena, setove, slike, rarity, postojeće podatke ni osobne `collection_entries` (quantity, note). **Ne stvaramo DON!! karte** jer trebaju provjerene vanjske ID-jeve i izdvojeni korak. Novi setovi koji još nisu u lokalnom katalogu prijavljuju se kao `unmatched` i preskaču.

## Odakle dolaze podaci

Preuzimamo `manifest.json` i tri JSONL datoteke:

```text
data/cards.jsonl
data/card_observations/en.jsonl
data/printings/en.jsonl
```

- `cards.jsonl` daje stabilan Koala `key` i službeni `number` (npr. OP01-016).
- `card_observations/en.jsonl` daje engleski opis, vrstu, numeričke podatke, boje, atribute, skupine, efekt i trigger. Preskačemo stare opažaje (`superseded_at`).
- `printings/en.jsonl` koristimo **samo** za strogu provjeru podudarnog base printa i oznake bloka.
- Svaku datoteku prije uporabe uspoređujemo sa SHA-256 i brojem redaka iz manifesta. Nepodudaranje znači **prekid**, ne djelomičan uvoz.

Izvorne preuzete datoteke drži lokalno u `data/koala_snapshot/`. Mapa treba biti u `.gitignore`; **ne commitamo** preuzeti snapshot koji se često mijenja.

## Postupak (PowerShell)

Iz korijena projekta jednom dodaj u `.gitignore`:

```gitignore
data/koala_snapshot/
```

Otvori Docker Desktop i pokreni bazu ako već nije pokrenuta:

```powershell
cd C:\Users\admin\OPTCG_Collection
docker compose up -d db
cd api
.\.venv\Scripts\Activate.ps1
```

**1. Testovi**

```powershell
python -m pytest tests/test_enrich_catalog.py -q
python -m pytest tests -q
```

**2. Preuzmi i provjeri trenutni JSONL snapshot** (ne dira DB):

```powershell
python -m app.enrich_catalog --download
```

Ako su raw.githubusercontent.com ili jsDelivr blokirani, preuzmi manifest i datoteke iz repozitorija ručno u istu lokalnu mapu te pokreni sljedeći korak. Skripta će svejedno provjeriti SHA-256 i broj redaka.

**3. Pregled / dry-run** (čita DB, ništa ne zapisuje):

```powershell
alembic current
python -m app.enrich_catalog
```

Treba pisati `003 (head)`. U izlazu ćeš vidjeti koliko je karata prepoznato, koliko polja i veza bi se dopunilo te upozorenja o neslaganjima. Ne očekujemo točan fiksni broj jer izvorni katalog može biti ažuriran.

**4. Provjeri upozorenja.** Ako se pojavi puno neočekivanih vrijednosti ili `Greška`, nemoj koristiti `--apply`. Pošalji ispis za provjeru.

**5. Sigurnosna kopija baze i primjena:**

```powershell
python -m app.enrich_catalog --apply
```

Svi se upisi izvršavaju unutar jedne transakcije. Ako nastane pogreška, promjene se poništavaju. **Ponovni prolaz** nad istim podacima ne bi smio dodavati nove veze niti polja koja su već popunjena.

## Provjera u TablePlusu

```sql
SELECT COUNT(*) AS sve_karte,
       COUNT(cost) AS s_cost,
       COUNT(power) AS s_power,
       COUNT(counter) AS s_counter,
       COUNT(life) AS s_life,
       COUNT(effect_text) AS s_efektom
FROM cards;

SELECT 'attributes' AS tablica, COUNT(*) AS broj FROM card_attributes
UNION ALL SELECT 'archetypes', COUNT(*) FROM card_archetypes
UNION ALL SELECT 'keywords', COUNT(*) FROM card_keywords;

SELECT code, name, card_type, cost, power, counter, life,
       LEFT(effect_text, 100) AS efekt
FROM cards WHERE code IN ('OP01-001', 'OP01-016');
```

U Swaggeru `GET /cards/filters` sada bi trebao nuditi više stvarnih cost/power vrijednosti i preuzete archetypeove; `GET /cards?costs=1` više ne bi trebao vraćati samo prazne rezultate.

## Ograničenja i sljedeći korak

Ovaj uvoz **nije** konačna sinkronizacija svih fizičkih izdanja. Dodatne Alt Art, Manga, DON!!, foil i stamped verzije moramo povezivati po stabilnom identifikatoru pojedinog printa i pravilno mapirati na `printing_external_ids`. Nećemo pretpostavljati da jedan broj karte označava jedinstvenu sliku. Isto tako, podaci iz vanjske baze ne zamjenjuju postojeće ručno upisane vrijednosti: neslaganja se prijavljuju za kasniju provjeru.

Slijedi Excel import i upravljanje korisničkim količinama, a zatim `card_loans` i prikaz posudbi sa slikama.

## Licenca

Koala Kollect svoje ključeve i strukturu podataka objavljuje kao **CC BY 4.0**. Za ponovno korištenje navesti izvor i poveznicu. **Ta licenca ne daje dopuštenje za javno ponovno objavljivanje Bandai slika ni tekstova karata.** Prije javnog hostanja dodatno provjeriti prava uporabe. https://github.com/hotavocado/koala-kollect-data

## Git nakon potvrđenog Koraka 7

Iz korijena projekta, tek nakon što testovi i `--apply` prođu:

```powershell
cd C:\Users\admin\OPTCG_Collection
git status
git add .gitignore api/app/enrich_catalog.py api/tests/test_enrich_catalog.py docs/KORAK_07_OBOGACIVANJE_KATALOGA.md
git diff --cached --check
git diff --cached --stat
git commit -m "feat: enrich card metadata from validated Koala snapshot"
git push -u origin feat/catalog-enrichment
```

I dalje ostajemo na ovom branchu za iduću cjelinu. Pull Request radimo na kraju cijele funkcionalnosti.
