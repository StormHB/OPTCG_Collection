# Korak 9A — model i migracija posudbi

**Status:** priprema sheme baze (API endpointovi dolaze u 9B).

## Svrha

Svaki korisnik vodi vlastitu evidenciju karata koje je **posudio drugima** (`lent`) i **posudio od drugih** (`borrowed`). Svaka posudba pokazuje na konkretno izdanje (`printing_id`), što je važno za regular/alternate art/manga ilustracije i budući prikaz male karte na listi.

Tablica `card_loans` čuva `user_id`, `printing_id`, `direction`, `person_name`, `quantity`, `quantity_returned`, `loaned_at`, `due_at`, `returned_at` i `note`. Preostalo za vratiti računa se kao `quantity - quantity_returned`.

### Ograničenja baze

- `direction` je `lent` ili `borrowed`.
- `quantity > 0`.
- `0 <= quantity_returned <= quantity`.
- `person_name` nije prazan ili sastavljen samo od razmaka.
- Strani ključevi povezuju vlasnika evidencije i točno izdanje karte.
- Brisanje korisnika briše njegove zapise posudbi, ali izdanje na koje se odnosi posudba ne može se tek tako obrisati ako se koristi u evidenciji (`RESTRICT`).

### Datumi

Koristimo `DateTime(timezone=True)` za vremenske oznake u bazi i `datetime.now(timezone.utc)` za vrijeme iz aplikacije. U Koraku 9B API sheme koriste `AwareDatetime`, provjeravaju zonu i normaliziraju ulaze na UTC; Vue prikazuje korisničku lokalnu zonu. `due_at` i `returned_at` su neobavezni.

### Poslovna pravila za Korak 9B

- Za `lent` treba potvrditi da izdanje postoji u vlastitoj kolekciji i da postoji dovoljna **fizički dostupna** količina: `collection_entries.quantity - SUM(active lent outstanding)`.
- Za `borrowed` ne tražimo da korisnik posjeduje isto izdanje; tuđa posuđena karta ne povećava vlasničku količinu ni broj playsetova.
- Djelomično vraćanje povećava `quantity_returned` uz provjeru raspona. Potpuno vraćanje može postaviti `returned_at` na UTC.
- Kritično: ažuriranje ili brisanje kolekcijskog zapisa i Excel `replace` također moraju provjeravati aktivne posudbe. Inače bi vlasnička količina mogla pasti ispod broja posuđenih primjeraka.
- Za paralelne zahtjeve pri posuđivanju potrebna je transakcijska zaštita/zaključavanje, kako isti primjerci ne bi bili dvaput posuđeni.
- Provjera vlasništva evidencije obavezna je i za `admin` korisnika. Greške moraju vraćati smislen status, stabilan kod/poruku i ne smiju ostaviti djelomične promjene.

### Sljedeće

U Koraku 9B dodajemo Pydantic sheme, repozitorij, servis i API za pregled, dodavanje, vraćanje i zatvaranje posudbi te njihove testove. U kasnijem Vue frontendu dogovoreni su tablični prikaz s malom ilustracijom i veći prikaz slike na hover/tap.
