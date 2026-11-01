# basilisk-profiler

Nyílt forráskódú profilkezelő a **Razer Basilisk V3 Pro** egérhez (Mouse Dock Pro-val is), **Windows** és **Linux** (X11) alá:

- billentyűzet-funkciók kiosztása az egér gombjaira,
- profilok tárolása az egér beépített profilhelyein,
- automatikus profilváltás az aktív (előtérben lévő) ablak alapján.

> **Állapot:** az architektúra jóváhagyva, a fejlesztés elindult (M1: protokoll-könyvtár).

## Tartalom

| mappa | leírás |
|---|---|
| [`docs/basilisk-v3-pro-protocol.md`](docs/basilisk-v3-pro-protocol.md) | a USB HID protokoll a Synapse 4 forgalmának visszafejtéséből (DPI, gombkiosztás, profilhelyek, Razer-billentyű események) |
| [`docs/architecture.md`](docs/architecture.md) | a jóváhagyott architektúra és a mérföldkövek |
| [`data/session1/`](data/session1/) | dekódolt parancs- és válaszlisták az első USB-rögzítésből (a nyers pcap nem része a repónak) |
| [`tools/razer_cmds.py`](tools/razer_cmds.py) | `tshark` mezőkimenetből listázza a 90 bájtos Razer feature reportokat |
| [`tools/ldb.py`](tools/ldb.py) | a Synapse 4 IndexedDB (LevelDB `.ldb`, Snappy) táblájának kicsomagolója, tiszta Pythonban |

## Használat (fejlesztői állapot)

A Synapse-ból előbb ki kell lépni, mert ő is írja az egeret.

```
python -m basilisk_profiler.cli info              # firmware, mód, akku, DPI-fokozatok
python -m basilisk_profiler.cli button 0x05 ctrl+t
python -m basilisk_profiler.daemon                # háttérszolgáltatás tálcaikonnal
```

A háttérszolgáltatás konfigja: `%APPDATA%\basilisk-profiler\config.toml` (Windows), illetve `~/.config/basilisk-profiler/config.toml` (Linux). Első indításkor egy példafájl jön létre. A fájlt a szolgáltatás a változás után automatikusan újratölti. A gombnevek: `button4`, `button5`, `side_bottom`, vagy hexában, pl. `0x34`. A műveletek formája: `mouse:4`, `key:8`, `ctrl+w`, `ctrl+shift+t`.

## Eszköz-azonosítók

| eszköz | VID:PID |
|---|---|
| Razer Mouse Dock Pro | 1532:00A4 |
| Basilisk V3 Pro (vezetékes) | 1532:00AA |
| Basilisk V3 Pro (vezeték nélküli) | 1532:00AB |

## Licenc

GPL-2.0-or-later – lásd: [LICENSE](LICENSE). A protokoll keretformátuma megegyezik az [openrazer](https://github.com/openrazer/openrazer) projektével.

A projekt nem kapcsolódik a Razer Inc.-hez. A „Razer”, a „Basilisk” és a „Synapse” a Razer Inc. védjegyei.
