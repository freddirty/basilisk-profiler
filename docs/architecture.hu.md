# Architektúra

[English](architecture.md) · **Magyar**

Állapot: jóváhagyva (2026-11-01), a v0.2.3 állapotára frissítve (2026-11-04). Ez a dokumentum a megvalósítás alapja; ami a jóváhagyott tervtől eltér, azt a „Változások a jóváhagyott tervhez képest” rész sorolja fel.

Egy könnyű, nyílt forráskódú profilkezelő Windowsra és Linux Mintre (Cinnamon, X11). A Synapse nélkül kezeli a Basilisk V3 Pro gombkiosztását, DPI-jét és profiljait, és az aktív ablak alapján vált profilt. Linuxon ezen felül profilonként egyedi, nagy kurzort mutathat (pl. ARPG játékokhoz), és kezeli a Mouse Dock Pro akkuszint-világítását.

## Kiadások

| Verzió | Platform | Tartalom |
| --- | --- | --- |
| v0.1.0 | Windows (telepítő) | Protokoll, CLI, háttérszolgáltatás, grafikus felület, beépített helyek, Synapse-import |
| v0.2.0 | csak Linux (.deb) | Linux port (hidraw, X11 ablakfigyelés, autostart, udev a csomagban), élő állapot: profilbetű a tálcaikonon, DPI/fokozat/akku a tooltipben, saját DPI-kijelző |
| v0.2.1 | csak Linux (.deb) | Tálcamenü-kapcsoló a dokk gyári akkuszint-effektjéhez |
| v0.2.2 | csak Linux (.deb) | Egyedi kurzor profilonként (YoloMouse-szerű nagy kurzor), Last Epoch alatt kipróbálva |
| v0.2.3 | csak Linux (.deb) | Angol és magyar felület (Nyelv almenü a tálcán), a profilgomb követése |

A Windows-telepítő a v0.2.0 óta nem része a kiadásoknak: a Windows-os élő állapot (DPI-jelzés) még nincs megoldva lekérdezés nélkül, és valódi Windows-gépen sincs kipróbálva. A CI a telepítőt pull requesteken továbbra is megépíti.

## Cél és hatókör

| Benne van | Kívül esik |
| --- | --- |
| Gomb → billentyű (módosítókkal), egérgomb, multimédia, DPI- és profilfunkció, letiltás | Hypershift (második réteg) |
| DPI-fokozatok profilonként | Az egér RGB / Chroma effektjei (OpenRazer, OpenRGB kezeli) |
| Profilok mentése az egér 4 beépített helyére | Makrók (később bővíthető) |
| Automatikus váltás az aktív ablak alapján | Firmware-frissítés, Razer-fiók, felhő |
| Grafikus felület az egér képével, tálcás háttérszolgáltatás, konfigfájl | Más Razer-eszközök |
| Élő állapot: aktív profil, DPI, fokozat, akku (eseményvezérelten) | Wayland (csak X11) |
| A dokk gyári akkuszint-effektjének be- és kikapcsolása | Saját színátmenet számítása a dokkra (a firmware maga csinálja) |
| Egyedi kurzor profilonként (csak Linux, X11) | Kurzorképek terjesztése a programmal |
| Magyar és angol felület | További nyelvek (a szótárral könnyen hozzáadhatók) |

Céleszköz: Basilisk V3 Pro (USB PID 0x00AA, vezeték nélkül 0x00AB) a Mouse Dock Pro-n keresztül (PID 0x00A4).

## Alapelvek

Ezeket a felhasználó szabta meg, minden új funkcióra érvényesek:

- **Nincs rendszeres lekérdezés.** Az egeret és a dokkot nem kérdezzük le időzítve (másodpercenként sem). Az állapot az eszköz eseményeiből jön, és csak meglévő eseményekhez kötve olvasunk (profilváltás, DPI-gomb, újracsatlakozás). A szolgáltatás belső 100 ms-os ciklusa (`tick`) csak sorokat ürít, eszközhöz nem nyúl, ha nincs teendő.
- **Előbb a terv.** Új funkció kódolása csak a terv egyeztetése után indul.
- **Hardveres próba mentéssel.** Próba előtt mentés (`cli backup`), utána visszaállítás és bájtra egyező visszaolvasás.
- **Beolvasztás és kiadás csak kifejezett jóváhagyással**, PR-onként és kiadásonként külön.
- **Flash kímélése.** A beépített helyekre csak változáskor írunk (`onboard-state.json` tárolja, mi van kiírva); a dokk effektjét csak akkor írjuk, ha eltér a felhasználó választásától.

## Amit a visszafejtésből tudunk

A gombkiosztást maga az egér végzi, ezért egyik rendszeren sem kell szoftveres billentyű-szimuláció. Elég a beállításokat HID-parancsokkal beírni az egérbe. Részletek: [basilisk-v3-pro-protocol.hu.md](basilisk-v3-pro-protocol.hu.md).

- **Keret:** 90 bájtos HID feature report a dock 0. interfészén (SET_REPORT, utána GET_REPORT visszaolvasás), OpenRazer-féle felépítéssel és XOR-ellenőrzőösszeggel. Válasz: 0x02 = OK, 0x01 = foglalt. A transaction id 0x1F: a parancs az egérhez megy; **0xFF: a dokk maga válaszol** (a dokk saját világítása).

| Funkció | Class/cmd | Megjegyzés |
| --- | --- | --- |
| Gombkiosztás írása / olvasása | 02/0C · 02/8C | Az OpenRazerben nincs. Arg.: hely, gomb ID, hypershift, típus, hossz, adat |
| DPI-fokozatok írása / olvasása | 04/06 · 04/86 | Hely, aktív fokozat, darab, fokozatonként X/Y (16 bit, big-endian) |
| Aktuális DPI | 04/05 · 04/85 | Hely, X, Y |
| Aktív hely kiválasztása / lekérdezése | 05/04 · 05/84 | `[hely, 0]`; Synapse nélkül, normal mode-ban kipróbálva |
| Helyek listája | 05/81 | → `05 01 02 03 04 05` |
| Eszközmód | 00/04 · 00/84 | 0x03 = driver mode (Synapse), egyébként normal mode |
| Akku / töltés | 07/80 · 07/84 | Olvasás |
| Dokk effekt (0xFF tid, LED 0x0F) | 0F/02 · 0F/82 | 1-es hely = tartós, 0-s = éppen látható szín; 0x0D = gyári akkuszint-effekt |
| Profilhely írásakor futó parancsok | 02/14, 02/16, 02/17, 05/02, 05/03, 05/08, 00/C0 | A Synapse küldi; a mi írásainkhoz nem kellenek, jelentésük részben nyitott |

- **Kimenettípusok (02/0C):** 0x00 letiltva, 0x01 egérgomb (9 = görgetés fel), 0x02 billentyű [módosító, HID usage], 0x06 DPI-funkció (fel, körbe, clutch), 0x07 profilfunkció, 0x0A multimédia, 0x0E ismétlődő görgetés, 0x12 görgő mód.
- **Gomb ID-k:** 0x03 görgőkattintás, 0x04 Button4, 0x05 Button5, 0x0E profilgomb, 0x0F hüvelykujj (clutch), 0x34 / 0x35 görgődöntés, 0x60 DPI-gomb, 0x6A görgő mód. A bal és jobb klikket szándékosan nem kezeljük.
- **Tárolóhelyek:** 0x01 = élő hely (fehér LED), 0x02–0x05 = a 4 beépített hely (piros, zöld, kék, cián). Az egér egyszerre pontosan egy helyet használ, a nem aktív helyre írás nem látszik.
- **Események (dock 1. interfész, report ID 5):** `05 02` DPI megváltozott, `05 31` akkuszint, `05 09` kapcsolat/ébredés. Linuxon hidraw-on olvassuk; a kernel minden olvasónak saját másolatot ad.
- **Profilgomb:** normal mode-ban az egér maga lép a helyek között (fehér → piros → zöld → kék → cián). Driver mode-ban csak jelez (report ID 4, kód 0x50), és a hostnak kell váltania.
- **Synapse-profilok:** a Synapse 4 Chromium IndexedDB-ben tárolja őket JSON-dokumentumként; a `core/leveldb.py` és a `core/synapse_import.py` kicsomagolja és importálja őket (Linuxon egy Windowsról átmásolt mappából).

## Profilváltási stratégia

A program normal mode-ban hagyja az egeret, driver mode-ot nem használ.

1. A felhasználó legfeljebb 4 profilt rendel beépített helyhez (`onboard_slot = 1..4`). Ezeket a szolgáltatás a 0x02–0x05 helyekre írja, de csak ha a tartalmuk megváltozott.
2. Ablakváltáskor (0,4 mp-es csillapítás után):
   - ha a profil beépített helyen van és naprakész, a szolgáltatás csak kiválasztja a helyet (05/04);
   - különben kiírja az élő helyre (0x01, ~15 parancs, ~1 mp), és azt teszi aktívvá.
3. A profilgombot az egér maga kezeli. A gombbal választott hely a következő profilváltásig marad érvényben.
4. Kilépéskor a szolgáltatás visszaállítja az induláskor aktív helyet, és normal mode-ot hagy.

Ezért az egér program nélkül, más gépen is a beépített profilokkal működik, a program futása alatt pedig korlátlan számú profil használható.

## Komponensek

```
 Beállítóablak (Qt) --ír--> config.toml <--figyeli (mtime)--+
   | ablaklista, Synapse-import                            |
   |                                                       |
   +-- ugyanabban a folyamatban, ha a tálcáról nyílik --> Háttérszolgáltatás (Service)
                                                          | szabálymotor, beépített helyek,
   Ablakfigyelő (szál) ----- aktív ablak --------------->  | élő állapot, dokk, kurzor
   Eseményolvasó (szál, Linux) - DPI / akku ------------>  |
                                                          v
                         core: protokoll, eszköz, profilmodell, konfig, kurzor, Synapse-import
                                                          v
                         HID-adapter (Windows: hidapi vagy hid.dll · Linux: hidraw + udev)
                                                          v
                         Mouse Dock Pro → egér

   Tálca (Qt): ikon a profil kezdőbetűjével, tooltip, DPI-kijelző, menü
   Kurzorréteg (szál, Linux/X11): rejtett rendszerkurzor + kattintásáteresztő ARGB ablak
```

- Egy folyamat fut: a tálcás alkalmazás (`basilisk-profiler`, illetve `python -m basilisk_profiler.daemon`). Ebben él a szolgáltatás, a tálca, és innen nyílik a beállítóablak is. Külön IPC nincs: a beállítóablak csak a konfigfájlt írja, a szolgáltatás a fájl változására újratölt. A beállítóablak önállóan is indítható (`python -m basilisk_profiler.gui`), ekkor sem nyúl az eszközhöz.
- Az eszközt csak a szolgáltatás éri el; egy zárfájl (`daemon.lock`) biztosítja, hogy csak egy példány fusson.
- A szálak (ablakfigyelő, eseményolvasó) csak sorba tesznek; minden eszközművelet a szolgáltatás `tick()` hívásában, a Qt időzítőjén fut.
- Alvó egérnél a dokk hibát vagy időtúllépést ad; ilyenkor a szolgáltatás 5 mp múlva próbálja újra megnyitni az eszközt, és a régi állapotot mutatja.

### Élő állapot

Profilváltáskor és DPI-eseménykor a szolgáltatás egyszer kiolvassa az aktív hely DPI-tábláját (fokozat sorszáma), az akkuszintet az eseményekből veszi. A tálcaikonon az aktív profil kezdőbetűje látszik (zöld = fut, szürke = szünetel, piros = konfighiba), a tooltipben a profil, a DPI a fokozattal és az akku. DPI-váltáskor egy saját, fókuszt el nem vevő felirat jelenik meg az egérmutató mellett 1,2 mp-re (kikapcsolható). A beállítóablak alsó sávja ugyanezt mutatja.

### Dokk akkuszint-világítás

A dokk firmware-e maga számolja a színt az akkuszintből (0x0D effekt, piros → sárga → zöld), ehhez program nem kell. A tálcamenü „Dokk: akkuszint-effekt” kapcsolója:

- induláskor és újracsatlakozáskor egyszer kiolvassa a dokk effektjét, és csak akkor ír, ha eltér a választástól;
- bekapcsoláskor beállítja a 0x0D effektet, és a következő akkujelzésig az utolsó ismert akkuértékből becsült színt mutatja;
- kikapcsoláskor visszaállítja a korábbi effektet (`dock-state.json`), vagy ha az nem ismert, statikus fehéret.

### Egyedi kurzor (Linux)

A profilban megadható egy `.cur` fájl és egy nagyítás (`cursor`, `cursor_scale`). Amikor az ilyen profil ablaka aktív, a kurzorréteg XFixes-szel elrejti a rendszerkurzort, és egy mindig felül lévő, kattintásáteresztő, override-redirect ARGB ablakban mutatja a képet. A réteg az XInput2 nyers mozgáseseményeire mozdul, lekérdezés nincs benne. A játék folyamatához nem nyúl (anti-cheat szempontból semleges). Ha a program leáll, az X szerver magától visszaadja a normál kurzort.

Feltétele, hogy a kompozitor teljes képernyős ablaknál is bekapcsolva maradjon (Cinnamon: `unredirect-fullscreen-windows=false`), és hogy a játék rendszerkurzort használjon. Last Epoch (Steam, Proton) alatt kipróbálva: nem késik, pontosan céloz.

A YoloMouse kurzorfájljainak nincs licence, ezért a program nem tartalmaz kurzorképet: a felhasználó a saját gépén lévő fájlt választja ki (a relatív útvonal a `<konfigmappa>/cursors/` alá mutat).

### A felület nyelve

A felület magyarul és angolul érhető el. Alapból a rendszer nyelvét követi (magyar rendszeren magyar, minden más nyelven angol), és a tálcamenü „Nyelv / Language” almenüjében átállítható; a választás a `tray.json`-ba kerül, és a különálló beállítóablak is ezt használja.

- A kódban a szövegek angolul vannak. A `tr('…')` a választott nyelvre fordít, a `N_('…')` csak megjelöli a modulszintű táblák szövegeit, amelyeket a megjelenítéskor fordítunk. A magyar szövegek az `i18n/hu.py` szótárában vannak, az angol szöveg a kulcs; ha egy fordítás hiányzik, az angol látszik.
- Fordítási lépés (Qt `.ts`/`.qm`, gettext) nincs. A `tests/test_i18n.py` ellenőrzi, hogy minden megjelölt szövegnek van magyar párja, nincs elavult bejegyzés, a `{mezők}` egyeznek, és a kódban nem maradt magyar szöveg.
- A Qt saját szövegeit (OK/Mégse, fájlválasztó) a PySide6-tal érkező `qtbase_hu.qm` adja.
- A tálcamenü azonnal átvált; egy már nyitott beállítóablak a következő megnyitáskor, hogy a mentetlen szerkesztés ne vesszen el.
- Angol marad: a napló, a konfig- és kurzorhibák szövege és a CLI.

## Konfiguráció és állapotfájlok

```toml
[default]
profile = "general"

[[profile]]
name = "general"
dpi_stages = [400, 800, 1600, 3200, 6400]
dpi_active = 3
[profile.buttons]
button4 = "mouse:4"
button5 = "mouse:5"

[[profile]]
name = "browser"
onboard_slot = 4            # opcionális: beírva az egérbe is (1 piros … 4 cián)
[profile.buttons]
button5 = "ctrl+t"
side_bottom = "ctrl+w"

[[profile]]
name = "last epoch"
cursor = "yolomouse-pink.cur"   # saját .cur fájl; relatív = <konfigmappa>/cursors/
cursor_scale = 2.0

[[rule]]
match_process = "brave"     # vagy match_class / match_title (regex); az első találat nyer
profile = "browser"
```

A konfigmappában (Windows: `%APPDATA%\basilisk-profiler\`, Linux: `~/.config/basilisk-profiler/`):

| Fájl | Tartalom |
| --- | --- |
| `config.toml` | Profilok és szabályok; kézzel is szerkeszthető, első indításkor példafájl jön létre |
| `onboard-state.json` | Melyik beépített helyre mi van kiírva (hash), hogy újraindításkor ne írjuk újra a flash-t |
| `dock-state.json` | A dokk effektje az akkuszint-effekt bekapcsolása előtt |
| `tray.json` | Tálcabeállítások (DPI-kijelző, dokk-kapcsoló, nyelv) |
| `cursors/` | A felhasználó kurzorfájljai |
| `daemon.lock`, `basilisk-profiler.log` | Egypéldányos zár, napló |

## Platformspecifikus részek

| Terület | Windows | Linux Mint (Cinnamon, X11) |
| --- | --- | --- |
| Eszközelérés | hidapi, ha telepítve van, különben beépített ctypes-os `hid.dll`-burkoló (`platform/win/hid.py`) | a cython-hidapi `hidraw` modulja → /dev/hidrawN (soha a libusb-s `hid` modul, mert az leválasztja az egér kernel-driverét); udev-szabály a 1532:00A4 / 00AA / 00AB eszközökre, a .deb telepíti |
| Eszközesemények (DPI, akku) | **Még nincs**: a DPI csak profilváltáskor frissül | `platform/linux/events.py`: a dock 1. interfészének report 5 eseményei, `select`-tel, lekérdezés nélkül |
| Aktív ablak | SetWinEventHook(EVENT_SYSTEM_FOREGROUND) → folyamatnév, ablakcím | python-xlib: _NET_ACTIVE_WINDOW figyelése → WM_CLASS, _NET_WM_PID → folyamatnév, cím (Flatpaknál a WM_CLASS) |
| Ablaklista a szabályszerkesztőhöz | EnumWindows | _NET_CLIENT_LIST |
| Egyedi kurzor | **Még nincs** | `platform/linux/cursor.py`: XFixes + ARGB réteg + XInput2 |
| Tálca | Qt QSystemTrayIcon | Qt QSystemTrayIcon |
| Automatikus indítás | HKCU\...\Run | ~/.config/autostart .desktop |
| Ütközés | A Synapse-t le kell állítani, különben felülírja a beállításokat | Ha az OpenRazer `razermouse` drivere vagy az `openrazer-daemon` fut, a CLI és a szolgáltatás figyelmeztet |

## Technológia és repo-szerkezet

Python 3.11+ és PySide6 (Qt 6).

| Réteg | Választás |
| --- | --- |
| HID | cython-hidapi `hidraw` (Linux), hidapi vagy `hid.dll` (Windows) |
| Konfig | TOML (`tomllib` olvasás, `tomli-w` írás) |
| GUI | PySide6, az egér képe (PNG) kattintható gombterületekkel; magyar és angol felület (saját szótár, `i18n/`) |
| Ablakfigyelés, kurzor | `pywin32` (Windows), `python-xlib` XFixes / XInput2 / Shape kiterjesztésekkel (Linux) |
| Csomagolás | PyInstaller + Inno Setup (Windows), PyInstaller + .deb (Linux, Qt a csomagban) |

```
src/basilisk_profiler/
  core/        protocol.py, device.py, model.py, config.py, keys.py, events.py,
               cursor.py (.cur betöltés), leveldb.py, synapse_import.py,
               ui_settings.py (tray.json)
  i18n/        __init__.py (tr, N_, nyelvválasztás), hu.py (magyar szövegek)
  platform/    __init__.py (platformválasztás)
               win/   hid.py, foreground.py, autostart.py
               linux/ x11.py, events.py, cursor.py, autostart.py, conflicts.py
  daemon/      service.py (szabálymotor is), tray.py, __main__.py
  gui/         main_window.py, mouse_view.py, draft.py, keymap.py, errors.py, language.py,
               assets/basilisk_v3_pro_ink.png
  cli.py       info, dpi, button, mode, query, backup, restore
tools/         razer_cmds.py, extract_frames.py, ldb.py, prepare_drawing.py,
               cursor_overlay_probe.py
docs/          architecture.md, basilisk-v3-pro-protocol.md (angol),
               *.hu.md (magyar pár), capture-2-plan.md (régi munkaterv, magyarul)
data/          session1/, session2/ (dekódolt rögzítések)
packaging/     windows/ (spec, Inno Setup), linux/ (spec, build-deb.sh, udev-szabály, .desktop)
tests/         pytest, a hardvert hamis eszköz helyettesíti
```

Kiadás: verziócímke (pl. `v0.2.2`) feltöltésekor a GitHub Actions megépíti a .deb csomagot (ubuntu-24.04, a Mint 22 alapja), lefuttat rajta egy füstpróbát, és GitHub Release-ként közzéteszi. A Windows-telepítő címkére jelenleg nem készül (lásd Kiadások). Minden pull requesten lefutnak a tesztek (pytest, Windows és Ubuntu, Python 3.11 és 3.12) és a lint (ruff).

Licenc: GPL-2.0-or-later.

## Változások a jóváhagyott tervhez képest

| Eredeti terv | Ami lett | Miért |
| --- | --- | --- |
| A program driver mode-ban kezeli a profilgombot | Normal mode marad, az egér maga lép a helyek között | Normal mode-ban a beépített helyek önállóan működnek, és a hely kiválasztása (05/04) is ismert lett |
| Beépített profilnál is az élő helyre írás | Beépített profilnál csak hely-kiválasztás | A 2. rögzítés és a hardveres próba megmutatta a 05/04-et; a nem aktív helyre írás amúgy sem látszik |
| GUI ↔ szolgáltatás IPC-vel | Nincs IPC: egy folyamat, a konfigfájl a közös felület | Egyszerűbb, és a beállítóablak úgysem nyúl az eszközhöz |
| `[device] dpi_stages` közösen | `dpi_stages` / `dpi_active` profilonként | Minden helynek saját DPI-táblája van |
| hidapi Windowson | hidapi, ha telepítve van, különben saját `hid.dll`-burkoló | Nem kell hozzá külön csomag, és nulla hozzáférési joggal is megnyitható az a gyűjtemény, amit a Windows magának tart |
| RGB teljesen kívül esik | A dokk gyári akkuszint-effektje be- és kikapcsolható | Felhasználói igény; a firmware számolja a színt |
| – | Élő állapot és DPI-kijelző | Felhasználói igény a Linux port próbája közben |
| – | Egyedi kurzor profilonként (Linux) | Felhasználói igény (YoloMouse-pótlás Linuxon) |
| Magyar felület és dokumentáció | Választható magyar vagy angol felület; angol az elsődleges dokumentáció, magyar párral | Felhasználói igény (2026-11-04) |
| `packaging/debian/`, SVG egérkép, `daemon/rules.py` | `packaging/linux/`, PNG egérkép, a szabályok a `core/model.py`-ban | Megvalósítás közbeni egyszerűsítés |

## Nyitott kérdések

Protokoll:

- [x] Melyik paranccsal választható ki az aktív beépített hely? `05/04 [hely, 0]`, lekérdezés: `05/84`.
- [x] Hány beépített hely van? 4 (0x02–0x05), plusz az élő hely (0x01).
- [x] A gomb ID-lista és a kimenettípusok: a 2. rögzítés megadta (lásd fent).
- [x] Normal mode-ban működik-e a profilgomb? Igen, az egér maga vált; a jelzést csak driver mode-ban küldi.
- [x] Linuxon az OpenRazer mellett elérhető-e a hidraw? Igen, de a razermouse driver és a daemon felülírhatja a beállításokat, ezért figyelmeztetünk.
- [ ] A 02/14, 02/16, 02/17, 05/02, 05/03 és 00/C0 pontos jelentése (a mi írásainkhoz eddig nem kellett).
- [ ] DPI-fokozat le (valószínűleg `06 02`) és görgetés le (valószínűleg egérgomb 10): nem láttuk, a program nem kínálja.
- [ ] A többi Razer-billentyűkód (report 4) és a `05 09`, `05 0c` események pontos jelentése.
- [ ] Töltés közben felülírja-e a dokk firmware-e a beállított effektet?

Windows:

- [ ] DPI- és akkuesemények olvasása Windowson lekérdezés nélkül (a dokk 1. interfészének input reportjai, pl. átfedéses `ReadFile`-lal), utána hardveres próba és Windows-kiadás. *Döntés (2026-11-04): így marad, a Windows-gépen folytatjuk.*
- [x] Kell-e egyedi kurzor Windowson? *Döntés (2026-11-04): kell.* Terv: „Tervek jóváhagyásra”.

Működés:

- [x] A profilgombbal választott hely követése. *Kész (2026-11-04), Linuxon:* a `05 39` eseményből tudja meg a szolgáltatás, lásd „A profilgombos váltás követése”. Windowson az eseményolvasóval együtt jön.
- [ ] Wayland-támogatás: a Mint Cinnamon egyelőre X11, de a kurzorréteg és az ablakfigyelés Waylanden más megoldást kívánna.
- [ ] A kurzorréteg olyan játéknál, amely saját kurzort rajzol, vagy kizárólagos teljes képernyőt használ (kompozitor nélkül): ott a réteg nem látszik, vagy két kurzor lesz. Kell-e profilonként jelezni vagy tesztelni?

## A profilgombos váltás követése

Normal mode-ban az egér maga lépteti a helyeket a profilgombbal, ezért a szolgáltatásnak erről értesülnie kell.

- Minden helyváltáskor jön egy `05 39` esemény a dokk 1. interfészén, a gombnyomáskor és a program saját választásakor is. Az esemény nem tartalmazza a helyet.
- Az eseményre a szolgáltatás egyszer kiolvassa az aktív helyet (`05/84`). Ha ez nem az, amit ő választott, az kézi váltás (`manual_store`). Időzített lekérdezés nincs.
- A tálcaikon ilyenkor narancssárga, és a szöveg a kézi helyet mutatja: `Profil: arpg (kézi, kék hely)`, vagy `Profil: kézi, kék hely`, ha a hely tartalmát a program nem ismeri (ekkor az ikonon `K` betű van). A DPI-t is újraolvassa, mert minden helynek saját fokozatai vannak.
- A kézi váltás a következő ablakváltásig érvényes. Akkor újra a szabály dönt, akkor is, ha a profil ugyanaz, mint a gombnyomás előtt. Ilyenkor nem ír, csak kiválasztja a helyet. Ugyanarra az ablakra érkező ismételt jelzés nem számít ablakváltásnak.
- A driver mode-ot nem használjuk: akkor az egér program nélkül nem váltana helyet.

## Tervek jóváhagyásra

Kódolás csak jóváhagyás után.

### Egyedi kurzor Windowson

**Javaslat: a rendszerkurzor ideiglenes cseréje** (`SetSystemCursor`), réteg nélkül.

- Amikor a kurzoros profil ablaka aktív lesz, a program a felhasználó `.cur` fájlját a megadott nagyítással betölti (`CreateIconIndirect`), és lecseréli vele a nyíl kurzort (OCR_NORMAL, igény szerint a kéz- és szöveges kurzort is).
- Más ablakra váltáskor és kilépéskor visszaállítja a rendszer kurzorait (`SystemParametersInfo(SPI_SETCURSORS)`).
- Előny: nincs késés, mert maga a Windows rajzolja, és kizárólagos teljes képernyőn is működik, ahol egy rétegablak nem látszana. A játékhoz nem nyúl (nincs DLL-injektálás, mint a YoloMouse-nál), anti-cheat szempontból semleges.
- Kockázat: ha a program összeomlik, a nagy kurzor a rendszerben marad. Ezért induláskor mindig visszaállítjuk a rendszer kurzorait, és a tálcamenübe kerül egy „Kurzor visszaállítása” pont. Kijelentkezés is visszaállítja.
- Korlát: ha a játék saját kurzort rajzol vagy saját kurzorképet állít be, a csere nem látszik. Unity-játékoknál (Last Epoch) a rendszer nyilát használják, ott működnie kell. Ezt csak Windows-gépen lehet kipróbálni.
- A konfig ugyanaz marad (`cursor`, `cursor_scale`), csak a megvalósítás platformfüggő: `platform/win/cursor.py`, ugyanazzal a `show()` / `hide()` felülettel, mint Linuxon.

Alternatíva: egy rétegablak, mint Linuxon (`WS_EX_LAYERED | WS_EX_TRANSPARENT`, nyers egéresemények, a rendszerkurzor elrejtése). Ezt csak akkor javaslom, ha a csere valamelyik játékban nem működik.

## Mérföldkövek

1. ✓ **M1 – protokoll-könyvtár:** projektváz, `core/protocol.py`, egységtesztek a `data/session1` alapján.
2. ✓ **M2 – parancssoros prototípus:** DPI, akku, gombkiosztás az élő helyen; 2. rögzítés.
3. ✓ **M3 – háttérszolgáltatás:** ablakfigyelő, szabálymotor, tálcaikon, TOML-konfig, Synapse-import, beépített helyek.
4. ✓ **M4 – grafikus felület és Windows-telepítő:** v0.1.0.
5. ✓ **L1–L3 – Linux port:** hidraw, OpenRazer-figyelmeztetés, X11 ablakfigyelés, autostart, .deb, élő állapot; v0.2.0.
6. ✓ **Dokk akkuszint-kapcsoló** (v0.2.1) és **egyedi kurzor** (v0.2.2), csak Linux.
7. ✓ **A profilgombos váltás követése**, Linuxon.
8. ✓ **Kétnyelvű felület** (magyar, angol) és angol dokumentáció magyar párral.
9. **Következő – Windows utolérése:** eseményolvasó lekérdezés nélkül (ezzel a profilgomb követése is), egyedi kurzor, a dokk-kapcsoló és az élő állapot kipróbálása Windowson, Windows-kiadás.
