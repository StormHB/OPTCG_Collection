# OPTCG Collection — dogovorena pravila i buduće funkcionalnosti

> **Status:** dokument zahtjeva, ne tvrdnja da su sve funkcionalnosti već implementirane.
>
> **Namjena:** trajna referenca u GitHub repozitoriju kako dogovori ne bi ovisili o povijesti razgovora. Ažurirati pri svakoj promjeni zahtjeva.

## 1. Svrha aplikacije

- Javni katalog One Piece TCG karata sa slikama i pretragom.
- Svaki registrirani korisnik vodi *vlastitu* kolekciju: količina fizičkog izdanja karte i osobna napomena.
- Zajednički podaci o karti ne kopiraju se za svakog korisnika.
- Razlikujemo karticu (`cards`) od fizičkog izdanja (`card_printings`) kako bismo mogli posebno pratiti regular, Alt Art, Manga i PRB/reprint izdanja.
- Uloge: `user` i `admin`; obični korisnik nema pristup tuđim privatnim podacima ni promjenama tuđe kolekcije. Admin upravlja katalogom; adminov pristup tuđim kolekcijama treba eksplicitno definirati i testirati.

## 2. Pravilo playseta — dogovoreno

| Tip karte | Minimalna količina za playset |
| --- | ---: |
| Leader (`card_type == "Leader"`, u pravilu rarity `L`) | 1 |
| Character | 4 |
| Event | 4 |
| Stage | 4 |
| Ostali tipovi, ako se pojave | 4, do izričite izmjene zahtjeva |

- Uvjet uključuje granicu: `>= 1` za Leader, `>= 4` za ostale.
- Računa se **po korisniku i konkretnom izdanju** (`collection_entries` + `card_printings`).
- Jedno izdanje koje zadovoljava prag računa se kao **jedan kompletiran playset** u pregledu, a ne kao `quantity // 4` zasebnih playsetova. To vrijedi dok se ne dogovori drugačija statistika.
- Ista poslovna funkcija mora određivati: status u API-ju, filter `Playset`, statistiku u pregledu i zeleno označavanje u UI-ju.
- Količina = 0 ili nepostojeći zapis znači da karta nije posjedovana (`Missing`).
- Prilikom uvoza karata treba normalizirati `card_type` (Leader vs. ostale oznake), ne oslanjati se samo na tekst rijetkosti.

Primjeri:

```text
Leader, 0 -> nema playseta
Leader, 1 -> playset
Character, 3 -> nema playseta
Character, 4 -> playset
Character, 8 -> i dalje jedno kompletirano izdanje/playset u broju različitih playsetova
```

## 3. Pravilo kombiniranja filtera — dogovoreno

**OR unutar jedne kategorije, AND između različitih kategorija.**

Primjer:

```text
(Color je Red ILI Yellow)
  I
(Cost = 3)
  I
(Affiliation je Whitebeard Pirates ILI Straw Hat Crew)
```

- Dvobojna karta odgovara filteru `Red` i filteru `Yellow` (dovoljna je podudarnost jedne od izabranih boja).
- Karta s više pripadnosti (`affiliations`) odgovara ako ima **barem jednu** od odabranih pripadnosti.
- Jedna karta u rezultatima prikazuje se **samo jednom**, bez dupliciranja zbog više odgovarajućih boja/pripadnosti.
- Višestruki odabir dopušten je za: set, boju, tip, rijetkost, affiliation, attribute; druge kategorije po potrebi.
- Numerički filteri (`cost`, `power`, `counter`) podržavat će točnu vrijednost i/ili raspon te se kombinirati s ostalim aktivnim kategorijama preko AND.
- Filteri vlasništva: `Owned`, `Missing`, `Playset`, s gornjim pragovima po tipu karte.
- Filtriranje po setu/izdanju mora jasno razlikovati izvorni broj karte i proizvod u kojem je tiskana, kako PRB/reprint ne bi bili zamijenjeni s originalnim izdanjima.

## 4. Korisničko sučelje filtera — dogovoreno

- Searchable dropdown / combobox s višestrukim odabirom, uklanjanjem odabranih vrijednosti i jasnim resetiranjem.
- Rezultati unutar dropdowna osvježavaju se **tijekom tipkanja**, bez Entera ili čekanja da polje izgubi fokus.
- Primjer: `Affiliation` + unos `whit` odmah prikazuje `Whitebeard Pirates` i sve druge stvarne vrijednosti koje sadrže `whit`.
- Izbori dolaze iz kontroliranog popisa/baze, a ne iz slobodnog proizvoljnog unosa.
- Za veće podatkovne skupove može se uvesti debouncing mrežnih zahtjeva, ali UI ostaje responzivan tijekom tipkanja.
- Rezultati kataloga trebaju prikazivati slike karata i količine samo trenutačno prijavljenog korisnika.

## 5. Normalizacija i kontrolirane vrijednosti — plan

- Fiksni mali skupovi (npr. `card_type`) mogu biti Python `Enum` i validirani Pydanticom.
- Boja može biti kontrolirana vrijednost, ali jedna karta može imati **više boja**; ne tretirati `Red/Yellow` kao treću neovisnu boju.
- `affiliations` kao zasebna tablica + `card_affiliations` kao many-to-many spojna tablica; karta može pripadati većem broju skupina.
- `attribute` također treba normalizirati na kontrolirane vrijednosti (provjeriti pojavljuje li se više atributa po karti prije izbora modela).
- Setovi već imaju svoju tablicu `card_sets`.
- Pretraživanje se validira na backendu; UI dropdown sam po sebi nije sigurnosna provjera.

## 6. Redoslijed rada i migracije

1. Predavanja 1–3: kostur, modeli, Alembic `001`, `002` i autentikacija — već izrađeno.
2. Predavanje 4: autorizacija po ulozi (`require_role`) i vlasništvu (`ensure_collection_owner`), testovi za tuđe zapise. **Bez nove migracije**, jer potrebni atributi već postoje.
3. Predavanja 5–6: korisničke kolekcije i katalog, API CRUD, validacija poslovnih pravila, indeksiranje i početni uvoz karata; dodatne migracije prema potrebi.
4. Predavanja 7–10: Vue 3 frontend, prikaz slika, dinamički višestruki dropdowni, filtriranje i korisnički pregled.
5. Predavanja 11–12: automatski testovi, deploy, CI i produkcijska provjera.

**Pravila za migracije:** ne prepravljati `001` ni `002` nakon što su već primijenjene; svaka promjena sheme dobiva novu Alembic migraciju s pregledanim `upgrade` i `downgrade` postupkom.

## 7. Testni slučajevi za kasnije

- `Leader quantity=1` -> playset; `Character quantity=3` -> nije; `Character quantity=4` -> playset.
- `colors=[Red, Yellow]` i `cost=3` -> vrati sve crvene ili žute karte s Cost 3; ostale isključi.
- Dvobojna karta uključena je ako ima barem jednu od odabranih boja.
- `affiliations=[Whitebeard Pirates, Straw Hat Crew]` -> karta s jednom ili objema pripadnostima ulazi jednom.
- Neprijavljeni poziv zaštićenoj ruti -> `401`.
- Korisnik bez administratorske uloge na admin ruti -> `403`.
- Korisnik ne može čitati ili mijenjati tuđu kolekciju -> `403` (ili svjesno `404` ako odlučimo sakriti postojanje zapisa).
- Osobna kolekcija se uvijek veže uz ID korisnika iz potvrđenog tokena, a ne na korisnički ID koji klijent samostalno pošalje kao dokaz vlasništva.

## 8. Još nije implementirano

- Normalizirani odnosi `card_colors`, `affiliations` i `card_affiliations`.
- Novi filtri, prijenos vrijednosti u UI, dinamički dropdowni i prikaz slika u frontend aplikaciji.
- Jedinstveni servisni obračun playseta za API, statistike i UI.
- Potpuni katalog karata iz izvora i svi detalji o izdanjima.

_Ovaj dokument predstavlja prihvaćenu specifikaciju za kasnije faze, ne popis dovršenih funkcionalnosti._
