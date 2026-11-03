# Razer Basilisk V3 Pro + Mouse Dock Pro – USB protokoll (1. rögzítés)

Forrás: `captures/session1.pcap` (USBPcap5, 3-as eszköz = Mouse Dock Pro, VID 0x1532, PID 0x00A4), 2026-11-01 14:28–14:31.
Synapse 4.0.827 írt, az egér vezeték nélkül csatlakozott a dockhoz. A dekódolt listák: `captures/session1_cmds.txt` (kérések), `captures/session1_rsp.txt` (válaszok). A dekóder: `tools/razer_cmds.py`.
A Hypershift nincs a scope-ban.

## Szállítás

- HID feature report a dock **0. interfészén** (wIndex 0, report ID 0).
  - Írás: `SET_REPORT` – bmRequestType 0x21, bRequest 0x09, wValue 0x0300.
  - Visszaolvasás: `GET_REPORT` – 0xA1 / 0x01 / 0x0300.
  - Minden írás után a Synapse azonnal visszaolvassa a választ.
- A riport 90 bájtos, pontosan az openrazer `razer_report` felépítése:

| bájt | mező | megfigyelés |
|---|---|---|
| 0 | status | kérésben 0x00; válaszban 0x02 = OK, 0x01 = foglalt (újra kell olvasni) |
| 1 | transaction id | a Synapse körbeforgó számlálót használ (0x00–0x1E), az openrazer fix 0x1F-et; a dock mindkettőt elfogadja |
| 2–3 | remaining packets | 0x0000 |
| 4 | protocol type | 0x00 |
| 5 | data size | az argumentumok hossza |
| 6 | command class | |
| 7 | command id | a 0x80 bit = lekérdezés (GET) |
| 8–87 | argumentumok (80 B) | |
| 88 | CRC | a 2–87. bájtok XOR-ja (mind a 65 kérésnél és válasznál ellenőrizve) |
| 89 | reserved | 0x00 |

## Tárolóhely (1. argumentum)

Sok parancs első argumentuma egy tárolóhely-azonosító:

- `0x01` = az aktív (élő) beállítás. Minden módosítás ide íródik, ez azonnal érvényes.
- `0x02`–`0x05` = a **4 beépített profilhely** az egér memóriájában (2. rögzítés). A Synapse „On-Board Memory” listájában ezek sorrendben: 1. hely piros = 0x02, 2. zöld = 0x03, 3. kék = 0x04, 4. cián = 0x05. Profilváltáskor a Synapse a profilt a hozzá tartozó helyre **és** a 0x01-re is kiírja.
- Az openrazer-ben ugyanez a bájt a `VARSTORE` (0x01).

## Azonosított parancsok

| class/id | jelentés | argumentumok | openrazer |
|---|---|---|---|
| 04/06 | DPI stage-ek írása | `store, aktív_stage(1-től), darab, {idx(0-tól), X_hi, X_lo, Y_hi, Y_lo, 0, 0} × darab` | egyezik (`set_dpi_stages`) |
| 04/86 | DPI stage-ek olvasása | `store` → ugyanaz a felépítés, de a válaszban az idx 1-től indul | egyezik |
| 02/0C | **gomb kiosztása** | `store, gomb_id, hypershift(0), típus, hossz, adat…` (lásd lent) | **nincs benne** (új) |
| 02/14, 02/17, 02/16 | profilhelyenként, a gombok írása előtt: `14 [store,0]`, `17 [store, 0/1, 0…]`, `16 [store,0]` | valószínűleg egy blokk (pl. makrótábla) kezdete / törlése / lezárása – **tisztázandó** | nincs |
| 0F/04 | fényerő | `store, led(0x00), érték` – 0x54 = 84/255 ≈ 33% (a profilban 33) | egyezik (extended matrix) |
| 0F/84 | fényerő olvasása | | egyezik |
| 0F/02 | effekt beállítása | `00 00 08 00 00 00` | extended matrix effekt, részletek később |
| 0F/03 | Chroma egyedi keret (soronként) | folyamatos, a szoftveres effektushoz tartozik – figyelmen kívül hagyható | egyezik |
| 0F/80 | LED-zónák/effekt olvasása | válasz: `01 19 03 01 01 04 19 03 01 01 0a 19 03 01 0b` | – |
| 07/80 | akkuszint | válasz `00 ff` = 100% | egyezik |
| 07/84 | töltés állapota | válasz `00 00` = nem tölt | egyezik |
| 00/84 | eszközmód olvasása | válasz `03 00` = **driver mode** | egyezik (00/04 = írás) |
| 00/C0 | profilhely infó (lekérdezés) | `[store,0]` → `[store,08]` a 0x01–0x05 helyekre, 0x06-ra `00` | jelentése nem kell a működéshez |
| 04/05 | aktuális DPI | `store, X(2), Y(2), 0, 0` – a Synapse a beépített helyre a stage-tábla mellé írja | egyezik (`set_dpi_xy`) |
| 05/02, 05/03 | profilhely előkészítése (beépített helyre íráskor) | `[store]` | – |
| 05/08 | a profil neve/azonosítója a beépített helyen | `store, offset(2), 00, FA, 64 bájt adat` – a Synapse GUID-ot, a profil nevét és hash-t ír ide | – (a működéshez nem kell) |
| 05/04 · 05/84 | aktív hely kiválasztása / lekérdezése | `[store, 0]` – lásd „Az aktív hely” | – |
| 05/81 | a helyek listája | → `05 01 02 03 04 05` | – |
| 06/8E | beépített memória kihasználtsága | válasz `00 64 | összes(4) | szabad(4) | 00 01 00`, pl. 0x4C000 / 0x4BC00 = „Available 99.67%” | – |
| 00/BF | a dockhoz párosított eszköz | válasz `02 01 00 ab 00 ff ff` – benne a 0x00AB (vezeték nélküli Basilisk V3 Pro PID) | – |

### Gombkiosztás (02/0C) – részletesen

`store, gomb, hypershift, típus, hossz, adat[hossz], 0…` (data size = 10)

| típus | jelentés | adat |
|---|---|---|
| 0x01 | egérgomb | `[egérgomb száma]` – pl. `01 05` = Mouse Button 5 (gyári) |
| 0x02 | billentyű | `[módosító bitmaszk, HID usage]` – a módosító a szokásos HID bitmaszk (0x01 = bal Ctrl) |
| 0x00 | letiltva | – (hossz 0) |
| 0x06 | DPI-funkció | `01` = fokozat fel; `06` = fokozatok körbe (a DPI-gomb gyári funkciója); `05 X(2) Y(2)` = érzékenység-clutch az adott DPI-vel (a hüvelykujj-gomb gyári funkciója, 400 DPI) |
| 0x07 | profilfunkció | `04` = következő profil (a profilgomb gyári funkciója) |
| 0x0A | multimédia | `[HID consumer usage, 2 bájt BE]`, pl. `00 CD` = lejátszás/szünet |
| 0x0E | ismétlődő görgetés | `68 00 14` balra, `69 00 14` jobbra – a görgődöntés gyári funkciója |
| 0x12 | görgő mód váltás | `01` – a görgő mód gomb (0x6A) gyári funkciója (02/8C-vel kiolvasva) |

Az egérgomb típusban a 9-es szám a görgetés fel („Scroll Up”).

Gomb-azonosítók a rögzítésből:

| gomb id | gomb | bizonyíték |
|---|---|---|
| 0x03 | görgőkattintás | 2. rögzítés, B1 → KEY_1; gyári: egérgomb 3 |
| 0x04 | Button4 (hátsó oldalgomb) | KEY_R (0x15) a „general” profilban |
| 0x05 | Button5 (elülső oldalgomb) | **14:30:27 → `01 05 00 02 02 00 25` = KEY_8 (HID 0x25)** |
| 0x0E | profilváltó gomb (alul) | B6 → KEY_6; gyári: profilfunkció `04` |
| 0x0F | érzékenység-clutch (hüvelykujj, Synapse: DKM_SB_02) | KEY_E (0x08); a browser profilban Ctrl+W (`01 1a`) |
| 0x34 | görgő döntése balra | B2 → KEY_2; gyári: `0E 68 00 14` |
| 0x35 | görgő döntése jobbra | B3 → KEY_3; gyári: `0E 69 00 14` |
| 0x60 | DPI-fokozat váltó gomb | B5 → KEY_5; gyári: DPI-funkció `06` |
| 0x6A | görgő mód gomb (racsnis/sima) | B4 → KEY_4; gyári funkciója még nem látszott |

A bal és a jobb klikk ID-ját szándékosan nem kezeljük: így egy profil sem veheti el az elsődleges gombokat.

A billentyűkódok szabványos HID Usage ID-k (0x04 = A … 0x1D = Z, 0x1E = 1 … 0x27 = 0).

## Az egyes lépések a rögzítésben

| idő | művelet | parancsok |
|---|---|---|
| 14:28:35 | stage-ek létrehozása (400/1600/1800/3200/6400) | `04/06 01 02 05 …` + `04/86` |
| 14:28:36 | a 3. stage (1800) lett aktív | `04/06 01 03 05 …` |
| 14:29:39 | a 2. stage (1600) lett aktív | `04/06 01 02 05 …` – az aktív stage váltása is a teljes táblát írja újra |
| 14:30:27 | Button5 → KEY_8 | `02/0C 01 05 00 02 02 00 25` – csak az élő (0x01) helyre |
| 14:31:07 | profilváltás (browser) | gomb visszaállítása, `02/14-17-16`, DPI-tábla, effekt, gombok a 0x05-ös és a 0x01-es helyre (Ctrl+W, Ctrl+T) |
| 14:31:27.8 | a felhasználó megnyomta az egér alján lévő „Cycle Up Profile” gombot | interrupt IN, EP 0x82: `04 50 00…` (lenyomás), majd 14:31:28.0-kor `04 00…` (felengedés) – report ID 4 = `razerKeyReportID`, Razer-billentyűkód 0x50 |
| 14:31:28 | a Synapse erre átváltott az „fps1” profilra (E/F/R/G gombok, 0x03-as hely) | ugyanaz a parancssor, mint a kézi váltásnál |

**Fontos:** a profilváltó gomb esetében nem az egér vált profilt. Az egér csak egy Razer-billentyű eseményt küld (report 4, kód 0x50), a váltást a Synapse végzi el a host oldalon, a profil kiírásával. Ugyanígy működik a többi `razerKey` típusú bemenet is (a `main.json` gyári kiosztásaiban pl. key 84 = 0x54). A saját programunknak tehát az EP 0x82-n figyelnie kell ezeket az eseményeket.

Az 1a lépés (a 3. stage értékének átírása 1600-ra) nem történt meg, ezért a stage-érték átírását külön nem láttuk. Ugyanakkor minden stage-módosítás a teljes `04/06` táblát küldi, tehát a formátum ismert.

## 2. rögzítés (2026-11-01 19:28–19:37, USBPcap2, 7-es eszköz)

Nyers rögzítés: csak helyben (`captures/`). Dekódolva: `data/session2/`.

| idő | lépés | megfigyelés |
|---|---|---|
| 19:29:30 | „Teszt” profil létrehozása | írás az élő helyre (0x01) |
| 19:30:10 | A1: „Teszt” a beépített 2. (zöld) helyre | `05/03`, `02/14`, `00/C0`, `02/17`, `06/8E`, `05/02`, 4× `05/08` (név, GUID, hash), `04/05`, `04/06`, `0F/04`, `06/8E` – mind a **0x03** helyre |
| 19:31:01 | A4: profilgomb (1.) | EP 0x82: `04 50` → a Synapse a 0x04 (kék, ARPG 1) hely tartalmát írja a 0x04-re és a 0x01-re |
| 19:31:19 | A4: profilgomb (2.) | ugyanígy a 0x05 (cián, Browser) |
| 19:32:45–19:33:35 | B1–B6: gomb ID-k | lásd a gombtáblát (a Synapse minden kiosztott gombot újraír a 0x03 és a 0x01 helyre) |
| 19:34:30–19:36:53 | C1–C6: kimenettípusok (a hüvelykujj-gombon) | egérgomb 4, multimédia `00CD`, DPI fokozat fel, görgetés fel (egérgomb 9), letiltva, vissza a clutch-ra |

**Az aktív hely (hardveres próba, 19:00, Synapse nélkül, normal mode):**

- Az egér egyszerre pontosan egy helyet használ: az élő helyet (0x01, a LED **fehér**) vagy egy beépítettet (0x02 piros, 0x03 zöld, 0x04 kék, 0x05 cián). A profilgomb ezeken lépked körbe: fehér → piros → zöld → kék → cián → fehér.
- A **nem aktív** helyre írás nem látszik. Ha pl. a cián hely aktív, az élő helyre (0x01) írt kiosztást az egér figyelmen kívül hagyja. A korábbi (M3) próba csak azért működött, mert akkor épp a fehér hely volt aktív.
- `05/84` → `[store]` az aktív hely; a profilgomb megnyomása után 05 → 01 lett.
- `05/04 [store, 0]` kiválasztja az aktív helyet. Kipróbálva: 05 → cián LED, a gomb a cián hely kiosztását küldte; 01 → fehér LED, az élő hely kiosztása.
- `05/81` → `05 01 02 03 04 05` (a helyek száma és listája). A `05/80` és a `05/8A` válasza `05`; a jelentésük nem kell.
- Driver mode-ban (Synapse) az egér csak a profilgomb eseményét küldi, és a Synapse másolja a következő hely tartalmát az élő helyre.

**A mi programunk ezért:**
- A beépített helyhez rendelt profilokat beírja a 0x02–0x05 helyekre, de csak változáskor.
- Ablakváltáskor, ha a profil beépített helyen van, csak kiválasztja azt a helyet (05/04).
- Ha a profil nincs beépített helyen, kiírja az élő helyre, és a fehér helyet teszi aktívvá.
- A profilgombos kézi váltás a következő ablakváltásig érvényes.
- Kilépéskor visszaállítja azt a helyet, ami induláskor aktív volt, és normal mode-ot hagy.

## Események a dock 1. interfészén (Linux, hidraw, 2026-11-03)

Normal mode-ban, Synapse nélkül figyelve. A dock 1. interfésze (Linuxon `/dev/hidraw3`) report ID 5-tel jelez. A kernel minden hidraw-olvasónak saját másolatot ad, így a figyelés nem veszi el a bemenetet az asztaltól.

| Report | Jelentés | Példa |
| --- | --- | --- |
| `05 02 XX XX YY YY` | DPI megváltozott (X/Y big-endian), minden DPI-gombnyomásra | `05 02 0c 80 0c 80` = 3200 |
| `05 31 LL …` | akku szintje, 0–255 | `05 31 cd` ≈ 80% |
| `05 09 SS 01` | kapcsolat / ébredés állapota | `05 09 02 01`, `05 09 03 01` |
| `05 0c …` | ismeretlen, ébredéskor | |

Kiegészítő lekérdezések: a `04/85` (arg.: hely) az aktuális DPI-t adja (`hely, X(2), Y(2)`), a `04/86` 1. bájtja az aktív fokozat sorszáma (1-től). Alvó egérnél a dock `FAILURE` vagy időtúllépés választ ad, amíg az egér meg nem mozdul.

## Következmények a tervezéshez

1. Az alap protokoll (keret, CRC, DPI, fényerő, akku, eszközmód) megegyezik az openrazer-rel, így Linuxon a kód közvetlenül hidraw-on keresztül írható.
2. A gombkiosztás (02/0C) új, de egyszerű, és a **hardver** végzi: a billentyűt az egér/dock maga küldi a billentyűzet-interfészen. Ezért nincs szükség szoftveres injektálásra (uinput / SendInput) az egyszerű billentyű-kiosztásokhoz.
3. Az alkalmazásfüggő automatikus váltáshoz elég a 0x01-es (élő) helyre írni: egy teljes profil (DPI-tábla + kb. 10 gomb) kb. 15 riport, ez ~1 mp. Opcionálisan használhatók a beépített helyek is.
4. Az egér driver mode-ban (`00/84 → 03`) van, amíg a Synapse fut. Saját eszközünkkel meg kell vizsgálni, hogy normal mode-ban is megmaradnak-e a kiosztások.

## Nyitott kérdések

- 02/14–17–16 pontos jelentése (valószínűleg a makró-/Hypershift-tábla kezelése; a mi írásainkhoz eddig nem kellett).
- ~~A görgő mód gomb (0x6A) gyári funkciója~~: típus 0x12, adat `01` (kiolvasva).
- A DPI fokozat le (valószínűleg `06 02`) és a görgetés le (valószínűleg egérgomb 10): nem láttuk, ezért a program még nem kínálja.
- A többi Razer-billentyűkód (report 4) és a report 5 (`hardwareEventReportID`, pl. `05 31 fa 00 00 01`) tartalma.
- ~~A gomb-ID-k teljes listája~~, ~~egyéb kimenettípusok~~, ~~hány beépített hely van~~: a 2. rögzítés megválaszolta.
- ~~Driver mode nélkül (normal mode) a profilgomb vajon a beépített helyek között vált-e magától?~~ **Igen**: a felhasználó szerint Linuxon, Synapse nélkül az egér gombjával lehet profilt váltani. A beépített profilhelyek tehát önállóan is működnek; a driver mode csak átirányítja a gombot a hosthoz.
- Hogyan lehet parancsból kiválasztani az aktív beépített profilhelyet (00/C0? vagy egy még nem látott parancs)? Továbbá: hány hely van, és tárol-e a hely LED-színt/nevet?
