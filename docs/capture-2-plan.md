# 2. USB-rögzítés – terv (beépített profilhelyek, gomb ID-k, kimenettípusok)

**Cél.** A hibrid profilváltáshoz és a teljes gombszerkesztőhöz hiányzó adatok:

1. Melyik parancs választja ki az aktív beépített profilhelyet (0x02–0x05), és hogyan kerül egy profil egy helyre (02/14, 02/16, 02/17, 00/C0).
2. A többi gomb azonosítója (görgőkattintás, görgődöntés balra/jobbra, a görgő mögötti két gomb, profilgomb, bal/jobb klikk).
3. További kimenettípusok: egérgomb, multimédia, DPI-funkciók, görgetés, letiltás.

**Előfeltétel.** A Synapse fut, a mi szolgáltatásunk nem. A rögzítés a USBPcap5-ön fut, csak a dockra (3-as eszköz) szűrve, ugyanúgy, mint az első alkalommal. Minden lépés után kb. 10 mp szünet kell. Az időpontokat a te üzeneteid alapján párosítom.

Hogy a rögzítés ne keveredjen a meglévő profilokkal, előtte egy **„Teszt”** profilt hozol létre a Synapse-ban; a lépések ezen történnek.

## A) Beépített profilhelyek (kb. 3 perc)

1. A Synapse-ban: Basilisk V3 Pro → Profilok → a beépített memória (On-Board Profiles). Húzd a „Teszt” profilt a **2. helyre**. Várj.
2. Húzd a „Browser” profilt a **3. helyre**. Várj.
3. A Synapse-ban válaszd ki aktív beépítettnek a **2. helyet**, majd várj. Utána a **3. helyet**, és megint várj.
4. Nyomd meg kétszer az egér alján a profilgombot, 10 mp szünettel.

## B) Gomb ID-k (a „Teszt” profilban, kb. 4 perc)

Mindegyik gombra rakj egy billentyűt, egyenként, 10 mp szünetekkel:

| gomb | billentyű |
|---|---|
| görgőkattintás | 1 |
| görgő döntése balra | 2 |
| görgő döntése jobbra | 3 |
| a görgő mögötti első gomb | 4 |
| a görgő mögötti második gomb | 5 |
| profilgomb (alul) | 6 |

A bal és a jobb klikket ne írd át; azok ID-ja valószínűleg 0x01 és 0x02, ezt majd olvasással ellenőrzöm.

## C) Kimenettípusok (az elülső oldalgombon, kb. 3 perc)

Egymás után, 10 mp szünetekkel:

1. Egérgomb → „Mouse Button 4”
2. Multimédia → „Play/Pause”
3. Érzékenység → „Sensitivity Stage Up”
4. Görgetés → „Scroll Up”
5. Letiltás („Disable”)
6. Vissza az alapértelmezettre.

## D) Befejezés

A „Teszt” profilt törölheted. A beépített helyek tartalmát a következő lépésben a mi programunk írja.

**Utána nálam:** a rögzítést összevetem a lépésekkel, és bővítem a `docs/basilisk-v3-pro-protocol.md` dokumentumot és a `core/protocol.py` modult. Ezután jöhet a „profil szinkronizálása a 2–5. helyre” funkció és a profilgomb kezelése driver mode-ban.
