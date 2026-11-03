# Architektúra

Állapot: jóváhagyva (2026-11-01). Ez a dokumentum a megvalósítás alapja.

Egy könnyű, nyílt forráskódú profilkezelő készül Windowsra és Linux Mintre (Cinnamon, X11). A Synapse nélkül kezeli a Basilisk V3 Pro gombkiosztását, DPI-jét és profiljait, és az aktív ablak alapján vált profilt.

## Cél és hatókör

| Benne van | Kívül esik |
| --- | --- |
| Gomb → billentyű (módosítókkal), gomb → egérgomb | Hypershift (második réteg) |
| DPI és DPI-fokozatok | RGB / Chroma (OpenRazer, OpenRGB kezeli) |
| Profilok mentése az egér beépített helyeire | Makrók (később bővíthető) |
| Automatikus váltás az aktív ablak alapján | Firmware-frissítés, Razer-fiók, felhő |
| Grafikus felület az egér képével, tálcás háttérszolgáltatás, konfigfájl | Más Razer-eszközök (az első verzióban) |

Céleszköz: Basilisk V3 Pro (USB PID 0x00AA, vezeték nélkül 0x00AB) a Mouse Dock Pro-n keresztül (PID 0x00A4).

## Amit a visszafejtésből tudunk

A gombkiosztást maga az egér végzi, ezért egyik rendszeren sem kell szoftveres billentyű-szimuláció. Elég a beállításokat HID-parancsokkal beírni az egérbe. Részletek: [basilisk-v3-pro-protocol.md](basilisk-v3-pro-protocol.md).

- **Keret:** 90 bájtos HID feature report a dock 0. interfészén (SET_REPORT, utána GET_REPORT visszaolvasás), OpenRazer-féle felépítéssel és XOR-ellenőrzőösszeggel. Válasz: 0x02 = OK, 0x01 = foglalt.

| Funkció | Class/cmd | Megjegyzés |
| --- | --- | --- |
| Gombkiosztás írása | 02/0C | Új, az OpenRazerben nincs. Arg.: hely, gomb ID, hypershift, típus, hossz, adat |
| DPI-fokozatok írása / olvasása | 04/06 · 04/86 | Hely, aktív fokozat, darab, fokozatonként X/Y (16 bit, big-endian) |
| Eszközmód | 00/04 · 00/84 | 0x03 = driver mode (Synapse), egyébként normal mode |
| Akku / töltés | 07/80 · 07/84 | Olvasás |
| Profilváltáskor futó parancsok | 02/14, 02/16, 02/17, 00/C0 | Jelentésük még nyitott |

- **Kimenettípusok (02/0C):** 0x01 = egérgomb, 0x02 = billentyű [módosító, HID usage], 0x06 = DPI-funkció. Példa: Button5 → 8-as billentyű = `01 05 00 02 02 00 25`.
- **Gomb ID-k eddig:** 0x04 = Button4, 0x05 = Button5, 0x0F = alsó oldalsó gomb, 0x34 = még azonosítatlan.
- **Tárolóhelyek:** 0x01 = élő beállítás; 0x02–0x05 körül beépített profilhelyek (a rögzítésben 0x03 és 0x05 látszott). Egy teljes profil kb. 15 parancs, kb. 1 másodperc.
- **Profilgomb:** driver mode-ban az egér csak jelez (interrupt végpont, report ID 4, kód 0x50), a váltást a host végzi. Normal mode-ban az egér maga lép a beépített helyek között.
- **Synapse-profilok:** a Synapse 4 Chromium IndexedDB-ben tárolja őket JSON-dokumentumként; a `tools/ldb.py` kicsomagolja őket, így importálhatók.

## Profilváltási stratégia: hibrid

A program a profilokat a beépített helyekre is kiírja, így az egér program nélkül is működik. Ablakváltáskor az élő helyre (0x01) írja a teljes profilt.

| | A) Beépített helyek | B) Élő hely (0x01) |
| --- | --- | --- |
| Hogyan vált | Csak kiválasztja a helyet | A teljes profilt újraírja (~1 mp) |
| Profilok száma | A helyek száma (kb. 4–5) | Korlátlan |
| Program nélkül | Működik, más gépen is | Az utolsó írt beállítás marad |
| Ismert-e a parancs | A hely kiválasztása még nem | Igen, a Synapse is így csinálja |

1. A felhasználó legfeljebb annyi profilt jelöl meg „az egérbe”, ahány beépített hely van; ezeket a program szinkronizálja a helyekre.
2. Ablakváltáskor a háttérszolgáltatás az élő helyre írja a szabály szerinti profilt. Ha kiderül a hely-kiválasztó parancs, a beépített profiloknál elég lesz azt kiadni.
3. Profilgomb: ha a program fut, ő kezeli a jelzést (driver mode); ha nem fut, az egér maga lép a helyek között (normal mode). Kilépéskor a program visszaállítja a normal mode-ot.

## Komponensek

```
 Grafikus felület --ír--> config.toml          Ablakfigyelő
        |                     | olvassa, figyeli     | aktív ablak
        +--- IPC -------> Háttérszolgáltatás <-------+
                              | (szabálymotor, tálcaikon, profilgomb)
                              v
                         core könyvtár (protokoll, profilmodell, Synapse-import)
                              v
                         HID-adapter (Windows: hidapi · Linux: hidraw + udev)
                          |   ^ profilgomb-esemény
     90 bájtos parancsok  v   |
                         Mouse Dock Pro → egér
```

A grafikus felület csak a konfigot szerkeszti; minden eszközműveletet a háttérszolgáltatás végez a közös `core` könyvtáron keresztül. A konfig kézzel is szerkeszthető, a háttérszolgáltatás a fájl változására újratölt. Az eszközt egyszerre csak a háttérszolgáltatás éri el.

Konfigfájl vázlata:

```toml
[device]
dpi_stages = [400, 800, 1600, 3200, 6400]

[[profile]]
name = "browser"
onboard_slot = 2          # opcionális: beírva az egérbe is
dpi_active = 3
[profile.buttons]
button4 = "ctrl+w"
button5 = "key:8"

[[rule]]
match_process = "firefox"   # vagy match_class / match_title (regex)
profile = "browser"

[default]
profile = "general"
```

## Platformspecifikus részek

| Terület | Windows | Linux Mint (Cinnamon, X11) |
| --- | --- | --- |
| Eszközelérés | hidapi → HidD_SetFeature / GetFeature a dock interfészén | a cython-hidapi `hidraw` modulja → /dev/hidrawN (soha a libusb-s `hid` modul, mert az leválasztja az egér kernel-driverét); udev-szabály (`packaging/linux/70-basilisk-profiler.rules`) a 1532:00A4 / 00AA / 00AB eszközökre |
| Profilgomb-esemény | HID input report olvasása (report ID 4) | Ugyanez hidraw-on |
| Aktív ablak | SetWinEventHook(EVENT_SYSTEM_FOREGROUND) → folyamatnév, ablakcím | python-xlib: _NET_ACTIVE_WINDOW figyelése → WM_CLASS, _NET_WM_PID → folyamatnév, cím |
| Tálca | Qt QSystemTrayIcon | Qt QSystemTrayIcon |
| Automatikus indítás | HKCU\...\Run | ~/.config/autostart .desktop |
| Konfig helye | %APPDATA%\basilisk-profiler\ | ~/.config/basilisk-profiler/ |
| Ütközés | A Synapse-t le kell állítani, különben felülírja a beállításokat | Ha az OpenRazer `razermouse` drivere vagy az `openrazer-daemon` fut, a CLI és a szolgáltatás figyelmeztet |

## Technológia és repo-szerkezet

Python 3.11+ és PySide6 (Qt 6). A mag később átírható Rustra, ha szükséges.

| Réteg | Választás |
| --- | --- |
| HID | `hidapi` (cython-hidapi) |
| Konfig | TOML (`tomllib` olvasás, `tomli-w` írás) |
| GUI | PySide6, az egér SVG-képe kattintható gombterületekkel |
| Ablakfigyelés | `pywin32` (Windows), `python-xlib` (Linux) |
| Csomagolás | PyInstaller + Inno Setup (Windows), .deb (Linux) |

```
basilisk-profiler/
  core/        protocol.py, device.py, model.py, config.py, synapse_import.py
  platform/    win/ (hid, foreground, autostart), linux/ (hidraw, x11, autostart, udev)
  daemon/      service.py, rules.py, tray.py
  gui/         main_window.py, mouse_view.py, assets/basilisk_v3_pro.svg
  tools/       razer_cmds.py, ldb.py
  docs/        basilisk-v3-pro-protocol.md, architecture.md
  packaging/   windows/, debian/
```

Kiadás: verziócímke (pl. `v0.1.0`) feltöltésekor a GitHub Actions megépíti a Windows-telepítőt (windows-latest) és a .deb csomagot (ubuntu-24.04, a Mint 22 alapja), majd GitHub Release-ként közzéteszi őket. Minden pull requesten lefutnak a tesztek (pytest) és a lint (ruff).

Licenc: GPL-2.0-or-later.

## Nyitott kérdések

- [ ] Melyik paranccsal választható ki kívülről az aktív beépített profilhely (00/C0 vagy más)?
- [ ] Hány beépített profilhely van, és mely ID-k?
- [ ] A teljes gomb ID-lista és a többi kimenettípus (multimédia, DPI-funkciók, scroll)
- [ ] A 02/14, 02/16, 02/17 és 00/C0 parancsok jelentése
- [x] Linuxon az OpenRazer mellett elérhető-e a hidraw? A hidraw mindig elérhető, de a razermouse driver és a daemon felülírhatja a beállításokat, ezért figyelmeztetünk.
- [ ] Normal mode-ban is olvasható-e a profilgomb eseménye?

## Mérföldkövek

1. **M1 – protokoll-könyvtár:** projektváz (pyproject, CI), `core/protocol.py` (keret építése/elemzése, CRC, ismert parancsok) egységtesztekkel a `data/session1` alapján.
2. **M2 – parancssoros prototípus:** DPI-fokozatok és akku olvasása, DPI írása, egy gomb átírása az élő helyen; mindkét rendszeren. Második rögzítés a nyitott kérdésekhez.
3. **M3 – háttérszolgáltatás:** ablakfigyelő, szabálymotor, tálcaikon, TOML-konfig, Synapse-import, beépített helyek szinkronizálása.
4. **M4 – grafikus felület és telepítők:** egérkép kattintható gombokkal, profil- és szabályszerkesztő; .deb és Windows-telepítő, GitHub Release.
