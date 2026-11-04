# basilisk-profiler

Nyílt forráskódú profilkezelő a **Razer Basilisk V3 Pro** egérhez (Mouse Dock Pro-val is), **Windows** és **Linux** (X11) alá:

- billentyűzet-funkciók kiosztása az egér gombjaira,
- profilok tárolása az egér beépített profilhelyein,
- automatikus profilváltás az aktív (előtérben lévő) ablak alapján.

> **Állapot:** v0.2.2. Linuxon (.deb) működik: profilváltás ablak szerint, beépített helyek, élő állapot, dokk akkuszint-effekt, egyedi kurzor. Windowsra az utolsó kiadás a v0.1.0; az újabb funkciók Windowson még kipróbálásra várnak.

## Tartalom

| mappa | leírás |
|---|---|
| [`docs/basilisk-v3-pro-protocol.md`](docs/basilisk-v3-pro-protocol.md) | a USB HID protokoll a Synapse 4 forgalmának visszafejtéséből (DPI, gombkiosztás, profilhelyek, Razer-billentyű események) |
| [`docs/architecture.md`](docs/architecture.md) | az architektúra, a tervtől való eltérések, a nyitott kérdések és a mérföldkövek |
| [`data/session1/`](data/session1/) | dekódolt parancs- és válaszlisták az első USB-rögzítésből (a nyers pcap nem része a repónak) |
| [`tools/razer_cmds.py`](tools/razer_cmds.py) | `tshark` mezőkimenetből listázza a 90 bájtos Razer feature reportokat |
| [`tools/ldb.py`](tools/ldb.py) | a Synapse 4 IndexedDB (LevelDB `.ldb`, Snappy) táblájának kicsomagolója, tiszta Pythonban |

## Telepítés

- **Windows:** a [Releases](https://github.com/freddirty/basilisk-profiler/releases) oldalról a `BasiliskProfiler-<verzió>-setup.exe`.
- **Linux Mint 22 / Ubuntu 24.04 (X11):** a `basilisk-profiler_<verzió>_amd64.deb`, telepítés: `sudo apt install ./basilisk-profiler_<verzió>_amd64.deb`. A csomag a udev-szabályt is felteszi, így az egér azonnal, root nélkül elérhető. Indítás a menüből („Basilisk Profiler”); a tálcamenüben bekapcsolható az „Indítás bejelentkezéskor”. Parancssor: `basilisk-profiler cli info`.

## Használat (fejlesztői állapot)

A Synapse-ból előbb ki kell lépni, mert ő is írja az egeret. Linuxon a `/dev/hidraw*` eléréséhez telepíteni kell a udev-szabályt (`sudo cp packaging/linux/70-basilisk-profiler.rules /etc/udev/rules.d/ && sudo udevadm control --reload && sudo udevadm trigger`), és az OpenRazer ne kezelje az egeret.

```
python -m basilisk_profiler.cli info              # firmware, mód, akku, DPI-fokozatok
python -m basilisk_profiler.cli button 0x05 ctrl+t
python -m basilisk_profiler.daemon                # háttérszolgáltatás tálcaikonnal
```

A háttérszolgáltatás konfigja: `%APPDATA%\basilisk-profiler\config.toml` (Windows), illetve `~/.config/basilisk-profiler/config.toml` (Linux). Első indításkor egy példafájl jön létre. A fájlt a szolgáltatás a változás után automatikusan újratölti; a legegyszerűbb a tálcaikon „Beállítások…” ablakában szerkeszteni.

- Gombnevek: `button4`, `button5`, `side_bottom` (érzékenység-clutch), `wheel_click`, `tilt_left`, `tilt_right`, `scroll_mode`, `dpi_cycle`, `profile`, vagy hexában, pl. `0x34`.
- Műveletek: `mouse:4`, `mouse:9` (görgetés fel), `key:8`, `ctrl+w`, `ctrl+shift+t`, `media:play_pause` (`next`, `previous`, `stop`, `volume_up`, `volume_down`, `mute`), `dpi:stage_up`, `dpi:cycle`, `dpi:clutch:400`, `profile:cycle`, `disabled`.
- `onboard_slot = 1..4`: a profil az egér beépített memóriájába is kiíródik (a Synapse színei szerint 1 piros, 2 zöld, 3 kék, 4 cián). Így program nélkül, a profilgombbal is elérhető. A szolgáltatás csak akkor ír, ha a profil megváltozott.

## Eszköz-azonosítók

| eszköz | VID:PID |
|---|---|
| Razer Mouse Dock Pro | 1532:00A4 |
| Basilisk V3 Pro (vezetékes) | 1532:00AA |
| Basilisk V3 Pro (vezeték nélküli) | 1532:00AB |

## Licenc

GPL-2.0-or-later – lásd: [LICENSE](LICENSE). A protokoll keretformátuma megegyezik az [openrazer](https://github.com/openrazer/openrazer) projektével.

A projekt nem kapcsolódik a Razer Inc.-hez. A „Razer”, a „Basilisk” és a „Synapse” a Razer Inc. védjegyei.
