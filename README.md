# basilisk-profiler

**English** · [Magyar](README.hu.md)

Open-source profile manager for the **Razer Basilisk V3 Pro** mouse (also through the Mouse Dock Pro), for **Windows** and **Linux** (X11):

- maps keyboard functions to the mouse buttons,
- stores profiles in the mouse's onboard profile slots,
- switches profiles automatically based on the active (foreground) window.

> **Status:** v0.2.3. Works on Linux (.deb): per-window profile switching, onboard slots, live status, profile button tracking, dock battery effect, custom cursor, English and Hungarian interface. The last Windows release is v0.1.0; the newer features have not been tried on Windows yet.

## Contents

| folder | description |
|---|---|
| [`docs/basilisk-v3-pro-protocol.md`](docs/basilisk-v3-pro-protocol.md) | the USB HID protocol, reverse-engineered from Synapse 4 traffic (DPI, button mapping, profile slots, Razer key events) |
| [`docs/architecture.md`](docs/architecture.md) | the architecture, deviations from the plan, open questions and milestones |
| [`data/session1/`](data/session1/) | decoded command and response lists from the first USB capture (the raw pcap is not in the repository) |
| [`tools/razer_cmds.py`](tools/razer_cmds.py) | lists the 90-byte Razer feature reports from `tshark` field output |
| [`tools/ldb.py`](tools/ldb.py) | unpacker for the Synapse 4 IndexedDB table (LevelDB `.ldb`, Snappy), in pure Python |

## Installation

- **Windows:** `BasiliskProfiler-<version>-setup.exe` from the [Releases](https://github.com/freddirty/basilisk-profiler/releases) page.
- **Linux Mint 22 / Ubuntu 24.04 (X11):** `basilisk-profiler_<version>_amd64.deb`, install with `sudo apt install ./basilisk-profiler_<version>_amd64.deb`. The package also installs the udev rule, so the mouse is available right away, without root. Start it from the menu ("Basilisk Profiler"); "Start at login" can be switched on in the tray menu. Command line: `basilisk-profiler cli info`.

## Language

The interface is available in English and Hungarian. By default it follows the system language; it can be changed in the tray menu under "Language". The documentation is primarily in English (`README.md`, `docs/*.md`); the Hungarian versions are the files ending in `.hu.md`.

## Usage (development state)

Quit Synapse first, because it writes the mouse too. On Linux, access to `/dev/hidraw*` needs the udev rule (`sudo cp packaging/linux/70-basilisk-profiler.rules /etc/udev/rules.d/ && sudo udevadm control --reload && sudo udevadm trigger`), and OpenRazer must not manage the mouse.

```
python -m basilisk_profiler.cli info              # firmware, mode, battery, DPI stages
python -m basilisk_profiler.cli button 0x05 ctrl+t
python -m basilisk_profiler.daemon                # background service with tray icon
```

The background service's config: `%APPDATA%\basilisk-profiler\config.toml` (Windows) or `~/.config/basilisk-profiler/config.toml` (Linux). A sample file is created on first start. The service reloads the file automatically when it changes; the easiest way to edit it is the "Settings…" window from the tray icon.

- Button names: `button4`, `button5`, `side_bottom` (sensitivity clutch), `wheel_click`, `tilt_left`, `tilt_right`, `scroll_mode`, `dpi_cycle`, `profile`, or in hex, e.g. `0x34`.
- Actions: `mouse:4`, `mouse:9` (scroll up), `key:8`, `ctrl+w`, `ctrl+shift+t`, `media:play_pause` (`next`, `previous`, `stop`, `volume_up`, `volume_down`, `mute`), `dpi:stage_up`, `dpi:cycle`, `dpi:clutch:400`, `profile:cycle`, `disabled`.
- `onboard_slot = 1..4`: the profile is also written to the mouse's onboard memory (Synapse's colours: 1 red, 2 green, 3 blue, 4 cyan), so it can be selected with the profile button without the program. The service only writes when the profile has changed.

## Device IDs

| device | VID:PID |
|---|---|
| Razer Mouse Dock Pro | 1532:00A4 |
| Basilisk V3 Pro (wired) | 1532:00AA |
| Basilisk V3 Pro (wireless) | 1532:00AB |

## License

GPL-2.0-or-later, see [LICENSE](LICENSE). The protocol's frame format is the same as in the [openrazer](https://github.com/openrazer/openrazer) project.

This project is not affiliated with Razer Inc. "Razer", "Basilisk" and "Synapse" are trademarks of Razer Inc.
