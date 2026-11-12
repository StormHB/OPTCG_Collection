# OPTCG Collection Tracker — specifikacija kataloga i filtera

**Status:** usuglašeni zahtjevi i prijedlog modela; **nije još implementirano**.
**Datum provjere:** 4. 11. 2026. (DON!! dopuna V3)
**Razvojni kontekst:** nakon predavanja 4; plan za `feat/card-catalog`, Alembic `003` i kasniji Vue frontend.

## 1. Temeljna logika filtriranja

- Unutar svakog filtera: **OR** (`IN` ili `EXISTS` nad bilo kojom od odabranih vrijednosti).
- Između aktivnih filtera: **AND**.
- Neoznačen filter ne ograničava rezultate.
- Jedna karta može imati više boja, atributa i pripadnosti (*archetype/type*). Poklapanje bilo koje od odabranih vrijednosti dovoljno je; rezultat se vraća samo jednom.
- Svi filtri podržavaju višestruki odabir, uklanjanje odabranih stavki i reset.
- Prijedlozi u pretraživim dropdownima osvježavaju se **tijekom tipkanja**; API-pretraga može imati vrlo kratko odgađanje (npr. 150–250 ms) radi izbjegavanja nepotrebnih zahtjeva, ali ne čeka Enter niti gubitak fokusa.

Primjer: `(cost IN (1, 2)) AND (power = 6000) AND (boja = red OR boja = yellow)`.

**Napomena:** pri odabiru dvije boje ne tražimo karticu koja ima *obje*, nego karticu koja ima *barem jednu*. Dvobojna karta odgovara svakom pojedinom svom dijelu boje.

## 2. Filteri i domene vrijednosti

| Filter | Opcije / pravilo | Modeliranje |
|---|---|---|
| `colour` | Red, Green, Blue, Purple, Black, Yellow; dopuštene kombinacije | rječnik + `card_colors` M:N |
| `card_type` | Leader, Character, Event, Stage, DON!! | enum ili kontrolirani rječnik |
| `cost` | 0–10 za sada; vrijednosti preuzimati iz baze i proširivati po potrebi; opcija *Nema cost* | nullable integer |
| `power` | 0–13.000 za sada; vrijednosti preuzimati iz baze i proširivati po potrebi; opcija *Nema power* | nullable integer |
| `attribute` | Slash, Strike, Ranged, Special, Wisdom, `?`; i njihove kombinacije | rječnik + `card_attributes` M:N |
| `rarity` | C, UC, R, SR, SEC, L; također SP, TR, Promo kao oznake proizvoda/izdanja | atribut izdanja i dodatne oznake |
| `variant` | Regular, Alternate Art/Parallel, Manga, SP/Special, Treasure, Promo, posebne DON!! ilustracije | oznaka na `card_printings` |
| `counter` | Nema counter, +1000, +2000. Ostale vrijednosti dodati samo ako su potvrđene kao **tiskana Counter vrijednost**, ne kao Event efekt | nullable integer (NULL = nije tiskan) |
| `block` | 1, 2, 3, 4, 5, X | tiskana oznaka na izdanju (provjeriti pri uvozu) |
| `keyword` | popis ispod | `keywords` + `card_keywords` M:N |
| `archetype` | dinamički iz baze: Whitebeard Pirates, Straw Hat Crew, Big Mom Pirates, Navy itd. | `archetypes` + `card_archetypes` M:N |
| `set` | OP01–OP18, EB01–EB05, ST01–ST36, PRB01/PRB02, P i budući proizvodi | `card_sets` + `card_printings.product_set_id` |
| `search` | broj karte i naziv, kasnije opcionalno puni tekst efekta | SQL filter + indeksi |
| `owned` | Posjedujem, Nedostaje, Playset | filtriranje u kontekstu prijavljenog korisnika; ne označavati negativan status playseta |

### Što znači M:N (many-to-many)?

`M:N` je veza *više-prema-više*. Jedna karta može imati više atributa (npr. Slash i Strike), a jedan atribut može pripadati mnogim kartama. To modeliramo s tri tablice:

- `cards(id, code, ...)` — osnovni zapisi karata;
- `attributes(id, name)` — kontrolirani rječnik mogućih atributa;
- `card_attributes(card_id, attribute_id)` — povezna tablica (složeni `PRIMARY KEY` sprječava dvostruko povezivanje iste karte i atributa).

Primjer: `(card_id=1, attribute_id=Slash)` i `(card_id=1, attribute_id=Strike)` znače da ista karta ima oba atributa. Kod filtriranja s `attribute=[Slash, Strike]` rezultat sadrži kartu ako ima **barem jedan** od njih, i prikazuje je samo jednom. Analogno vrijedi za `card_colors`, `card_archetypes` i `card_keywords`.

### Službene korekcije

- Pravila od 28. 8. 2026. navode **pet kategorija**, uključujući DON!!, ali Bandai web-katalog ima samo četiri opcije `Card type`. To zahtijeva zaseban uvoz DON!! izdanja.
- Pravila navode **šest atributa**; šesti je `?`.
- Službeni web-katalog nudi **Block 1–5 i X**.
- Službeni engleski web-katalog trenutno izlistava obične karte zasebno od nekih kolekcionarskih DON!! izdanja; DON!! pokrivenost vanjskih kataloga razlikuje se. Uvoz treba omogućiti ručno dodavanje i provjeru izvora.
- PRB je ispravan prefiks za *Premium Booster*, ne PBR.
- OP18 je najavljen za 20. 11. 2026.; ST37 i ST38 najavljeni su za prosinac 2026. Popis proizvoda **nije hardkodiran** na trenutni raspon.

### Rarity: dva povezana pojma

*Rarity* (primjerice SR) i *treatment/printing* (primjerice Manga) nisu ista stvar: Manga može naslijediti osnovnu rijetkost SR. U bazi trebaju biti odvojeni, uz jedan praktični UI-filter koji korisniku omogućuje biranje npr. `SR`, `Manga`, `SP`, `TR`, `Promo` bez poznavanja unutarnje strukture. Ako se istodobno biraju vrijednosti istog objedinjenog UI-filtera, između njih vrijedi OR.

Ne gubiti izvorni broj karte pri reprintu: jedan `cards` zapis može imati više `card_printings` (originalno izdanje, reprint iz PRB, alt-art i sl.).

## 3. Keyword rječnik

Razdvojiti **efekte/sposobnosti** od **vremena aktivacije**, **uvjeta** i općeg teksta:

**Sposobnosti:** `Rush`, `Rush: Character`, `Blocker`, `Double Attack`, `Banish`, `Trigger`, `Unblockable`.

**Vrijeme i uvjeti:** `On Play`, `When Attacking`, `On K.O.`, `On Block`, `On Your Opponent's Attack`, `Activate: Main`, `Main`, `Counter` (Event), `Once Per Turn`, `Your Turn`, `Opponent's Turn`, `End of Your Turn`, `End of Your Opponent's Turn`, `DON!! xN`, `DON!! -N`.

**Dodatni tekstualni pojmovi:** `K.O.` i `Trash` mogu se nuditi u zasebnom pretraživanju teksta, a ne nužno kao izravna sposobnost. `[Counter]` na Eventu **nije** isto što i tiskana Counter vrijednost lika (+1000/+2000).

Uvoz ključnih riječi treba normalizirati nazive i razlikovati `Rush` od `Rush: Character`. Prvi jednostavan filter može tražiti doslovnu pojavu oznake u efektu, uz jasno označavanje da spominjanje sposobnosti ne znači uvijek i da je karta trajno ima (npr. „gains [Blocker]”).

## 4. Primjeri očekivanih rezultata i testova

1. `colour=[Red, Yellow]`, `cost=[3]` → crvena **ili** žuta, i cost 3.
2. `cost=[1,2]`, `power=[6000]` → cost 1 **ili** 2, i power 6000.
3. `archetype=[Whitebeard Pirates, Straw Hat Crew]` → pripada barem jednoj skupini; karta s obje ide jednom.
4. `attribute=[Slash, Strike]` → Slash **ili** Strike, uključujući Slash/Strike kombinaciju.
5. `keyword=[Rush, Blocker]`, `colour=[Red]` → red karta s bilo kojom od odabranih oznaka.
6. `set=[PRB01]` → print iz tog proizvoda, ne sve karte s originalnim brojevima OP/ST koji su se pojavili kao reprint.
7. Korisnik može filtrirati `variant=[Manga]` neovisno o osnovnoj rijetkosti.
8. Nijedna kombinacija filtera ne smije duplicirati karticu u rezultatu zbog M:N veza.

### Playset poslovno pravilo (dogovoreni pragovi za kolekciju)

- **Leader:** `quantity >= 1`.
- **DON!!:** `quantity >= 10` — vlastiti prag dovršenosti DON!! skupine; nije tvrdnja o službenom pravilu playseta.
- **Character, Event, Stage i ostalo:** `quantity >= 4`.
- U kolekciji **samo ispunjen uvjet označiti zeleno**; za neispunjene uvjete ne prikazivati poseban status niti boju. Nema zasebne iznimke za `quantity = 0` jer su svi negativni slučajevi obuhvaćeni pragovima (npr. Character ×3 također nije playset).
- Pri uvozu ili filtriranju koristiti `card_type` za određivanje praga, a ne isključivo `rarity`, kako varijante i DON!! izdanja ne bi promijenile pravilo.
- Precizno definirati brojanje playsetova na razini **tiskane verzije** (`printing_id`) i, ako zatreba, zasebno na razini **osnovne karte** (`card_id`), jer regular/Alt/Manga mogu predstavljati istu karta-identitet za igranje, ali različite primjerke za kolekciju.

```python
def is_playset(card_type: str, quantity: int) -> bool:
    if card_type == "Leader":
        return quantity >= 1
    if card_type == "DON!!":
        return quantity >= 10
    return quantity >= 4
```

## 5. Predloženo proširenje modela kroz novu migraciju

Postojeće migracije `001` i `002` **ne mijenjati**. U `003` (po potrebi razlomljeno na sljedeće migracije) razmotriti:

- `colors`, `card_colors`
- `attributes`, `card_attributes`
- `archetypes`, `card_archetypes`
- `keywords`, `card_keywords`
- `card_printings.block_icon` i normalizirano označavanje vrste izdanja
- `cards.life` (Leader)
- `cards.card_type`, `cost`, `power`, `counter` i obavezno zadržavanje `NULL` za neprikladna/nepoznata polja
- indeksiranje `cards.code`, naziva, numeričkih filtera i vanjskih ključeva u pomoćnim tablicama

Izvorna tekstualna polja (`cards.color`, `cards.attribute`, `cards.affiliation_text`) zadržati privremeno za sigurnu migraciju i provjeru prije njihova uklanjanja.

Postojeća struktura (`users`, `card_sets`, `cards`, `card_printings`, `collection_entries`) ostaje temelj. Posebna pažnja za DON!! verzije čiji javni vanjski kodovi nisu standardni OP/ST/EB brojevi: koristiti interno stabilan identifikator i odvojeno spremati kod izvora.

### SQLAlchemy koncept (nakon dodavanja M:N relacija)

```python
from sqlalchemy import select

stmt = select(Card)
if selected_colors:
    stmt = stmt.where(Card.colors.any(Color.name.in_(selected_colors)))
if selected_attributes:
    stmt = stmt.where(Card.attributes.any(Attribute.name.in_(selected_attributes)))
if selected_archetypes:
    stmt = stmt.where(Card.archetypes.any(Archetype.name.in_(selected_archetypes)))
if selected_costs:
    stmt = stmt.where(Card.cost.in_(selected_costs))
if selected_powers:
    stmt = stmt.where(Card.power.in_(selected_powers))
```

Svaki `.any(...in_(...))` provjerava **bilo koju** vrijednost unutar kategorije. Zasebni `.where()` pozivi zajedno daju AND. Relacije prikazane ovdje još nisu dio trenutačnog koda.

## 6. Korisničko sučelje

- Pretraživi višestruki izbor (combobox/multi-select) za svaku kategoriju.
- Odabrane opcije kao uklonjive oznake (chips); pregled aktivnih filtera i `Clear all`.
- Za brojčane filtere opcija višestrukog odabira i po želji raspona.
- Odmah ažurirati **prijedloge** pri svakom znaku; osvježavanje udaljenih rezultata kratko odgoditi kad je korisno.
- Sačuvati filtere u URL-u (`?colors=Red,Yellow&costs=1,2&power=6000`) radi dijeljenja poveznica.
- Razdvojiti katalog i korisničku kolekciju; podaci o tuđim količinama ne smiju biti javni.

## 7. Izvori za provjeru (4. 11. 2026.)

- Bandai Comprehensive Rules v1.2.1 (28. 8. 2026.): https://en.onepiece-cardgame.com/pdf/rule_comprehensive.pdf?20260828=
- Bandai CARD LIST (Block icon i polja): https://en.onepiece-cardgame.com/cardlist/
- Bandai RULES: https://en.onepiece-cardgame.com/rules/
- SLAB-Z Rarities/Pull Rates (sekundarni vodič; ne izvor službenih pull rateova): https://www.slab-z.com/post/one-piece-tcg-rarities-pull-rates-complete-guide-updated-2026
- OnePieceDB, postojeći DON!! zapisi (djelomičan katalog): https://onepiecedb.io/card-database?type=DON%21%21
- OPlayTCG, 167 DON!! unosa s kataloškim oznakama do `DON-238` (preskočeni brojevi): https://oplaytcg.com/en/sets/DON
- Binder Pirates, DON!! katalog EN/JP s vlastitim ID-jevima i nepotvrđenim unosima: https://www.binderpirates.com/don
- Koala Kollect — model za DON!! izdanja i TCGplayer identifikatore: https://github.com/hotavocado/koala-kollect-data/blob/main/CONTRACT.md

## 8. Autorska prava i objavljivanje slika (provjera 4. 11. 2026.)

**Službeni izvor:** https://en.onepiece-cardgame.com/ — u podnožju stoji da se slike, tekst i podaci s te stranice ne smiju reproducirati bez dopuštenja. To nije javna licenca za slike niti za masovni uvoz podataka.

**Dodatna objava Bandaija (10. 7. 2026.):** https://en.onepiece-cardgame.com/news/02_382.html — izričito se odnosi na neovlaštene proizvode koji kopiraju dizajn karata. Ne daje formalno dopuštenje za reprodukciju sadržaja na javnim fanovskim web stranicama.

**Hrvatsko pravo:** Članak 183. Zakona o autorskom pravu i srodnim pravima (https://narodne-novine.nn.hr/clanci/sluzbeni/full/2021_10_111_1941.html) predviđa iznimku za privatno, nekomercijalno umnožavanje iz zakonito objavljenih izvora koje nije namijenjeno ni dostupno javnosti. To samo po sebi **ne pokriva javnu web aplikaciju**, čak ni besplatnu studentsku stranicu.

**Naš razvojni pristup:**

1. Razvijati modele, filtre, količine i korisničke funkcije neovisno o prikazu zaštićenih ilustracija.
2. Čuvati izvore metapodataka i zasebno izvor slike/pravni status slike; vanjska CC ili open-source licenca za JSON katalog ne znači automatski licencu za ilustracije.
3. Prije javnog prikaza punih slika ili sličica zatražiti dopuštenje odnosno provjeriti uvjete nositelja prava. Samo hotlinkanje slika ne daje automatsku dozvolu.
4. U slučaju nejasnog dopuštenja javni prikaz kartičnih ilustracija isključiti ili koristiti samo materijale za koje postoji dozvola. To ne sprječava nastavak razvoja ostatka aplikacije.

*Ovaj odjeljak služi kao projektna napomena, a ne kao pojedinačni pravni savjet.*


## 9. DON!! sheet i identifikacija izdanja (dogovor 4. 11. 2026.)

**DON!! sheet NEMA stupac `Boja`.** U korisničkom Excelu predviđeno je točno šest vidljivih stupaca:

| Stupac | Namjena |
|---|---|
| `Broj / ID` | Kataloška oznaka iz odabranog izvora, npr. `DON-238`; nije nužno službeni Bandai broj |
| `Ime` | Naziv ili opis ilustracije |
| `Količina` | Broj primjeraka u korisničkoj kolekciji |
| `Rijetkost` | `DON!!` |
| `Slika` | URL slike izdanja, ako je dostupan i dopušten za korištenje |
| `Napomena` | Korisnički zapis; po potrebi jezik, izdanje ili izvor |

- **Playset za DON!!:** `quantity >= 10`; zeleno označavanje samo kada prag jest ispunjen.
- DON!! nema `color`/`attributes` u izvornoj Koala Kollect DON shemi; nemojmo izmišljati `Red`/`Blue` za DON!! zato što ilustracija vizualno sadrži tu boju.
- `DON-238` (OPlayTCG) i `DON-EN-001` (Binder Pirates) **vanjski su, izvorno specifični kataloški ID-jevi**, ne službeni univerzalni brojevi. OPlayTCG trenutno objavljuje **167** DON!! unosa, s preskočenim brojevima oznaka; Binder Pirates objavljuje **588** EN/JP unosa, a dio izdanja/obrada/slika označava nepotvrđenima. Brojevi iz različitih kataloga nisu automatski usporedivi.
- Koala Kollect izričito navodi da DON!! nema službeno tiskani broj u dostupnim katalozima koje prati, pa ih povezuje s **TCGplayer `productId`** i završnom obradom (`Normal`/`Foil`). Kombinacija izvora, `productId` i finisha identificira fizičko izdanje mnogo sigurnije od proizvoljnog naziva.
- Interni identitet u PostgreSQL-u treba biti naš `card_printings.id`. Eksterne identifikatore pohraniti odvojeno, npr. `printing_external_ids(printing_id, source, external_id, language, finish)` uz odgovarajući UNIQUE. OPlayTCG, Binder Pirates i Koala Kollect/TCGplayer razlikujemo u `source`. Ne povezivati njihove zapise automatski bez provjere da predstavljaju isto fizičko izdanje.
- Pri automatskom uvozu normalizirati podatke, provjeriti slike i jezik, označiti nejasne duplikate za ručni pregled i **nikad ne prepisati korisničku količinu** prilikom osvježavanja kataloga.
- **Preporučeni izvori:** Koala Kollect (strojno čitljivi JSONL, referenca TCGplayer IDs) za inicijalni uvoz EN podataka, Binder Pirates za dopunu i provjeru EN/JP izdanja, OPlayTCG za oznake i dodatnu kontrolu. Nijedan izvor zasad nije potvrđen kao potpuno autoritativan katalog svih fizičkih DON!! izdanja.

*Ovo je plan i specifikacija, a ne tvrdnja da smo DON!! Excel već popunili ili da je migracija provedena.*
