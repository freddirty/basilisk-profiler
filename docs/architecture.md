# Architecture

**English** · [Magyar](architecture.hu.md)

Status: approved (2026-11-01), updated to the state of v0.2.3 (2026-11-04). This document is the basis of the implementation; whatever differs from the approved plan is listed under "Changes from the approved plan".

A lightweight, open-source profile manager for Windows and Linux Mint (Cinnamon, X11). Without Synapse, it manages the Basilisk V3 Pro's button mapping, DPI and profiles, and switches profiles based on the active window. On Linux it can also show a big custom cursor per profile (e.g. for ARPG games), and it manages the Mouse Dock Pro's battery level lighting.

## Releases

| Version | Platform | Contents |
| --- | --- | --- |
| v0.1.0 | Windows (installer) | Protocol, CLI, background service, graphical interface, onboard slots, Synapse import |
| v0.2.0 | Linux only (.deb) | Linux port (hidraw, X11 window watching, autostart, udev in the package), live status: profile letter on the tray icon, DPI/stage/battery in the tooltip, own DPI display |
| v0.2.1 | Linux only (.deb) | Tray menu switch for the dock's factory battery level effect |
| v0.2.2 | Linux only (.deb) | Custom cursor per profile (YoloMouse-style big cursor), tried in Last Epoch |
| v0.2.3 | Linux only (.deb) | English and Hungarian interface (Language submenu in the tray), profile button tracking |

The Windows installer has not been part of the releases since v0.2.0: the live status on Windows (DPI display) is not solved yet without polling, and it has not been tried on a real Windows machine. CI still builds the installer on pull requests.

## Goal and scope

| In scope | Out of scope |
| --- | --- |
| Button → key (with modifiers), mouse button, multimedia, DPI and profile functions, disabling | Hypershift (second layer) |
| DPI stages per profile | The mouse's RGB / Chroma effects (handled by OpenRazer, OpenRGB) |
| Saving profiles to the mouse's 4 onboard slots | Macros (can be added later) |
| Automatic switching based on the active window | Firmware updates, Razer account, cloud |
| Graphical interface with a picture of the mouse, tray background service, config file | Other Razer devices |
| Live status: active profile, DPI, stage, battery (event-driven) | Wayland (X11 only) |
| Switching the dock's factory battery level effect on and off | Computing our own colour gradient for the dock (the firmware does it) |
| Custom cursor per profile (Linux, X11 only) | Distributing cursor images with the program |
| English and Hungarian interface | Further languages (the catalogue makes them easy to add) |

Target device: Basilisk V3 Pro (USB PID 0x00AA, wireless 0x00AB) through the Mouse Dock Pro (PID 0x00A4).

## Principles

Set by the user; they apply to every new feature:

- **No routine polling.** The mouse and the dock are not queried on a timer (not even once a second). The status comes from the device's events, and reads are only tied to existing events (profile switch, DPI button, reconnect). The service's internal 100 ms loop (`tick`) only drains queues and does not touch the device when there is nothing to do.
- **Plan first.** Coding a new feature only starts after the plan has been agreed.
- **Hardware tests with a backup.** Before a test, a backup (`cli backup`); afterwards a restore and a byte-for-byte matching read-back.
- **Merges and releases only with explicit approval**, separately for each PR and each release.
- **Spare the flash.** The onboard slots are only written on change (`onboard-state.json` records what has been written); the dock's effect is only written when it differs from the user's choice.

## What we know from reverse engineering

The mouse does the button mapping itself, so neither system needs software key simulation. It is enough to write the settings into the mouse with HID commands. Details: [basilisk-v3-pro-protocol.md](basilisk-v3-pro-protocol.md).

- **Frame:** 90-byte HID feature report on the dock's interface 0 (SET_REPORT, then GET_REPORT read-back), with OpenRazer's layout and an XOR checksum. Response: 0x02 = OK, 0x01 = busy. Transaction id 0x1F: the command goes to the mouse; **0xFF: the dock answers itself** (the dock's own lighting).

| Function | Class/cmd | Note |
| --- | --- | --- |
| Write / read button mapping | 02/0C · 02/8C | Not in OpenRazer. Args: slot, button id, hypershift, type, length, data |
| Write / read DPI stages | 04/06 · 04/86 | Slot, active stage, count, X/Y per stage (16 bit, big-endian) |
| Current DPI | 04/05 · 04/85 | Slot, X, Y |
| Select / query the active slot | 05/04 · 05/84 | `[slot, 0]`; tried without Synapse, in normal mode |
| List of slots | 05/81 | → `05 01 02 03 04 05` |
| Device mode | 00/04 · 00/84 | 0x03 = driver mode (Synapse), otherwise normal mode |
| Battery / charging | 07/80 · 07/84 | Read |
| Dock effect (tid 0xFF, LED 0x0F) | 0F/02 · 0F/82 | Slot 1 = persistent, slot 0 = colour shown now; 0x0D = factory battery level effect |
| Commands sent when writing a profile slot | 02/14, 02/16, 02/17, 05/02, 05/03, 05/08, 00/C0 | Sent by Synapse; not needed for our writes, meaning partly open |

- **Output types (02/0C):** 0x00 disabled, 0x01 mouse button (9 = scroll up), 0x02 key [modifier, HID usage], 0x06 DPI function (up, cycle, clutch), 0x07 profile function, 0x0A multimedia, 0x0E repeated scroll, 0x12 scroll mode.
- **Button ids:** 0x03 wheel click, 0x04 Button4, 0x05 Button5, 0x0E profile button, 0x0F thumb (clutch), 0x34 / 0x35 wheel tilt, 0x60 DPI button, 0x6A scroll mode. Left and right click are deliberately not handled.
- **Storage slots:** 0x01 = live slot (white LED), 0x02–0x05 = the 4 onboard slots (red, green, blue, cyan). The mouse uses exactly one slot at a time; writing to an inactive slot has no visible effect.
- **Events (dock interface 1, report ID 5):** `05 02` DPI changed, `05 31` battery level, `05 09` connection/wake. Read through hidraw on Linux; the kernel gives every reader its own copy.
- **Profile button:** in normal mode the mouse steps through the slots itself (white → red → green → blue → cyan). In driver mode it only signals (report ID 4, code 0x50), and the host has to switch.
- **Synapse profiles:** Synapse 4 stores them as JSON documents in a Chromium IndexedDB; `core/leveldb.py` and `core/synapse_import.py` unpack and import them (on Linux from a folder copied over from Windows).

## Profile switching strategy

The program leaves the mouse in normal mode; it does not use driver mode.

1. The user assigns at most 4 profiles to onboard slots (`onboard_slot = 1..4`). The service writes these to slots 0x02–0x05, but only if their contents changed.
2. On a window change (after a 0.4 s debounce):
   - if the profile is in an onboard slot and up to date, the service only selects the slot (05/04);
   - otherwise it writes it to the live slot (0x01, ~15 commands, ~1 s) and makes that active.
3. The mouse handles the profile button itself. A slot chosen with the button holds until the next profile switch.
4. On exit the service restores the slot that was active at start and leaves normal mode.

So the mouse works with its onboard profiles without the program, even on another computer, and while the program runs any number of profiles can be used.

## Components

```
 Settings window (Qt) --writes--> config.toml <--watches (mtime)--+
   | window list, Synapse import                                  |
   |                                                              |
   +-- in the same process when opened from the tray --> Background service (Service)
                                                          | rule engine, onboard slots,
   Window watcher (thread) --- active window ----------->  | live status, dock, cursor
   Event reader (thread, Linux) - DPI / battery -------->  |
                                                          v
                         core: protocol, device, profile model, config, cursor, Synapse import
                                                          v
                         HID adapter (Windows: hidapi or hid.dll · Linux: hidraw + udev)
                                                          v
                         Mouse Dock Pro → mouse

   Tray (Qt): icon with the profile's first letter, tooltip, DPI display, menu
   Cursor layer (thread, Linux/X11): hidden system cursor + click-through ARGB window
```

- One process runs: the tray application (`basilisk-profiler`, or `python -m basilisk_profiler.daemon`). The service and the tray live in it, and the settings window opens from it too. There is no separate IPC: the settings window only writes the config file, and the service reloads when the file changes. The settings window can also be started on its own (`python -m basilisk_profiler.gui`); it does not touch the device then either.
- Only the service accesses the device; a lock file (`daemon.lock`) makes sure only one instance runs.
- The threads (window watcher, event reader) only enqueue; every device operation runs in the service's `tick()` call, on the Qt timer.
- With a sleeping mouse the dock returns an error or times out; the service then tries to reopen the device after 5 s and shows the old status.

### Live status

On a profile switch and on a DPI event the service reads the active slot's DPI table once (stage number); the battery level comes from the events. The tray icon shows the active profile's first letter (green = running, grey = paused, red = config error), the tooltip the profile, the DPI with its stage, and the battery. On a DPI change, a label of our own that does not take focus appears next to the pointer for 1.2 s (can be switched off). The settings window's status bar shows the same.

### Dock battery level lighting

The dock's firmware computes the colour from the battery level itself (effect 0x0D, red → yellow → green); no program is needed for that. The tray menu's "Dock: battery level effect" switch:

- at start and on reconnect reads the dock's effect once, and only writes if it differs from the choice;
- when switched on, sets effect 0x0D and, until the next battery report, shows a colour estimated from the last known battery value;
- when switched off, restores the previous effect (`dock-state.json`), or static white if that is not known.

### Custom cursor (Linux)

A profile can name a `.cur` file and a scale (`cursor`, `cursor_scale`). While a window of such a profile is active, the cursor layer hides the system cursor with XFixes and shows the image in an always-on-top, click-through, override-redirect ARGB window. The layer moves on XInput2 raw motion events; there is no polling in it. It does not touch the game's process (neutral as far as anti-cheat goes). If the program stops, the X server gives back the normal cursor by itself.

It needs the compositor to stay on for full-screen windows too (Cinnamon: `unredirect-fullscreen-windows=false`), and the game to use the system cursor. Tried in Last Epoch (Steam, Proton): no lag, accurate aim.

YoloMouse's cursor files have no licence, so the program comes with no cursor image: the user chooses a file on their own computer (a relative path points under `<config folder>/cursors/`).

### Interface language

The interface is available in English and Hungarian. By default it follows the system language (Hungarian on a Hungarian system, English for every other language), and it can be changed in the tray menu's "Language" submenu; the choice is stored in `tray.json`, and the stand-alone settings window uses it too.

- The texts in the code are English. `tr('…')` translates to the chosen language; `N_('…')` only marks the texts of module-level tables, which are translated when shown. The Hungarian texts are in the `i18n/hu.py` dictionary, keyed by the English text; a missing translation shows the English.
- There is no translation build step (Qt `.ts`/`.qm`, gettext). `tests/test_i18n.py` checks that every marked text has a Hungarian entry, there are no stale entries, the `{fields}` match, and no Hungarian text is left in the code.
- Qt's own texts (OK/Cancel, file dialog) come from the `qtbase_hu.qm` shipped with PySide6.
- The tray menu switches at once; an already open settings window on its next opening, so unsaved edits are not lost.
- Staying English: the log, the texts of config and cursor errors, and the CLI.

## Configuration and state files

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
onboard_slot = 4            # optional: also written to the mouse (1 red … 4 cyan)
[profile.buttons]
button5 = "ctrl+t"
side_bottom = "ctrl+w"

[[profile]]
name = "last epoch"
cursor = "yolomouse-pink.cur"   # own .cur file; relative = <config folder>/cursors/
cursor_scale = 2.0

[[rule]]
match_process = "brave"     # or match_class / match_title (regex); the first match wins
profile = "browser"
```

In the config folder (Windows: `%APPDATA%\basilisk-profiler\`, Linux: `~/.config/basilisk-profiler/`):

| File | Contents |
| --- | --- |
| `config.toml` | Profiles and rules; can be edited by hand, a sample file is created on first start |
| `onboard-state.json` | What has been written to which onboard slot (hash), so the flash is not rewritten on restart |
| `dock-state.json` | The dock's effect before the battery level effect was switched on |
| `tray.json` | Tray settings (DPI display, dock switch, language) |
| `cursors/` | The user's cursor files |
| `daemon.lock`, `basilisk-profiler.log` | Single-instance lock, log |

## Platform-specific parts

| Area | Windows | Linux Mint (Cinnamon, X11) |
| --- | --- | --- |
| Device access | hidapi if installed, otherwise a built-in ctypes `hid.dll` wrapper (`platform/win/hid.py`) | cython-hidapi's `hidraw` module → /dev/hidrawN (never the libusb `hid` module, because it detaches the mouse's kernel driver); udev rule for the 1532:00A4 / 00AA / 00AB devices, installed by the .deb |
| Device events (DPI, battery) | **Not yet**: the DPI only updates on a profile switch | `platform/linux/events.py`: report 5 events of the dock's interface 1, with `select`, without polling |
| Active window | SetWinEventHook(EVENT_SYSTEM_FOREGROUND) → process name, window title | python-xlib: watching _NET_ACTIVE_WINDOW → WM_CLASS, _NET_WM_PID → process name, title (WM_CLASS for Flatpak) |
| Window list for the rule editor | EnumWindows | _NET_CLIENT_LIST |
| Custom cursor | **Not yet** | `platform/linux/cursor.py`: XFixes + ARGB layer + XInput2 |
| Tray | Qt QSystemTrayIcon | Qt QSystemTrayIcon |
| Autostart | HKCU\...\Run | ~/.config/autostart .desktop |
| Conflicts | Synapse has to be stopped, otherwise it overwrites the settings | If OpenRazer's `razermouse` driver or `openrazer-daemon` runs, the CLI and the service warn |

## Technology and repository layout

Python 3.11+ and PySide6 (Qt 6).

| Layer | Choice |
| --- | --- |
| HID | cython-hidapi `hidraw` (Linux), hidapi or `hid.dll` (Windows) |
| Config | TOML (`tomllib` to read, `tomli-w` to write) |
| GUI | PySide6, picture of the mouse (PNG) with clickable button areas; English and Hungarian interface (own catalogue, `i18n/`) |
| Window watching, cursor | `pywin32` (Windows), `python-xlib` with the XFixes / XInput2 / Shape extensions (Linux) |
| Packaging | PyInstaller + Inno Setup (Windows), PyInstaller + .deb (Linux, Qt in the package) |

```
src/basilisk_profiler/
  core/        protocol.py, device.py, model.py, config.py, keys.py, events.py,
               cursor.py (.cur loading), leveldb.py, synapse_import.py,
               ui_settings.py (tray.json)
  i18n/        __init__.py (tr, N_, language choice), hu.py (Hungarian texts)
  platform/    __init__.py (platform selection)
               win/   hid.py, foreground.py, autostart.py
               linux/ x11.py, events.py, cursor.py, autostart.py, conflicts.py
  daemon/      service.py (also the rule engine), tray.py, __main__.py
  gui/         main_window.py, mouse_view.py, draft.py, keymap.py, errors.py, language.py,
               assets/basilisk_v3_pro_ink.png
  cli.py       info, dpi, button, mode, query, backup, restore
tools/         razer_cmds.py, extract_frames.py, ldb.py, prepare_drawing.py,
               cursor_overlay_probe.py
docs/          architecture.md, basilisk-v3-pro-protocol.md (English),
               *.hu.md (Hungarian versions), capture-2-plan.md (old work plan, in Hungarian)
data/          session1/, session2/ (decoded captures)
packaging/     windows/ (spec, Inno Setup), linux/ (spec, build-deb.sh, udev rule, .desktop)
tests/         pytest, a fake device stands in for the hardware
```

Release: when a version tag (e.g. `v0.2.2`) is pushed, GitHub Actions builds the .deb package (ubuntu-24.04, the base of Mint 22), runs a smoke test on it, and publishes it as a GitHub Release. The Windows installer is currently not built for tags (see Releases). Every pull request runs the tests (pytest, Windows and Ubuntu, Python 3.11 and 3.12) and the lint (ruff).

License: GPL-2.0-or-later.

## Changes from the approved plan

| Original plan | What it became | Why |
| --- | --- | --- |
| The program handles the profile button in driver mode | Normal mode stays, the mouse steps through the slots itself | In normal mode the onboard slots work on their own, and slot selection (05/04) became known too |
| Writing to the live slot for onboard profiles too | Only slot selection for onboard profiles | Capture 2 and the hardware test revealed 05/04; writing to an inactive slot has no visible effect anyway |
| GUI ↔ service over IPC | No IPC: one process, the config file is the shared interface | Simpler, and the settings window does not touch the device anyway |
| A shared `[device] dpi_stages` | `dpi_stages` / `dpi_active` per profile | Every slot has its own DPI table |
| hidapi on Windows | hidapi if installed, otherwise our own `hid.dll` wrapper | Needs no extra package, and can open with zero access rights the collection Windows keeps for itself |
| RGB entirely out of scope | The dock's factory battery level effect can be switched on and off | User request; the firmware computes the colour |
| – | Live status and DPI display | User request while trying the Linux port |
| – | Custom cursor per profile (Linux) | User request (YoloMouse replacement on Linux) |
| Hungarian interface and documentation | Selectable English or Hungarian interface; English is the primary documentation, with a Hungarian version | User request (2026-11-04) |
| `packaging/debian/`, SVG mouse picture, `daemon/rules.py` | `packaging/linux/`, PNG mouse picture, the rules in `core/model.py` | Simplification during implementation |

## Open questions

Protocol:

- [x] Which command selects the active onboard slot? `05/04 [slot, 0]`, query: `05/84`.
- [x] How many onboard slots are there? 4 (0x02–0x05), plus the live slot (0x01).
- [x] The button id list and the output types: given by capture 2 (see above).
- [x] Does the profile button work in normal mode? Yes, the mouse switches itself; it only sends the signal in driver mode.
- [x] Is hidraw available on Linux alongside OpenRazer? Yes, but the razermouse driver and the daemon can overwrite the settings, so we warn.
- [ ] The exact meaning of 02/14, 02/16, 02/17, 05/02, 05/03 and 00/C0 (not needed for our writes so far).
- [ ] DPI stage down (probably `06 02`) and scroll down (probably mouse button 10): not seen, the program does not offer them.
- [ ] The exact meaning of the other Razer key codes (report 4) and of the `05 09`, `05 0c` events.
- [ ] Does the dock's firmware overwrite the configured effect while charging?

Windows:

- [ ] Reading DPI and battery events on Windows without polling (input reports of the dock's interface 1, e.g. with overlapped `ReadFile`), then a hardware test and a Windows release. *Decision (2026-11-04): stays like this, to be continued on the Windows machine.*
- [x] Is a custom cursor needed on Windows? *Decision (2026-11-04): yes.* Plan: "Plans for approval".

Operation:

- [x] Tracking the slot chosen with the profile button. *Done (2026-11-04), on Linux:* the service learns it from the `05 39` event, see "Tracking the profile button". On Windows it comes with the event reader.
- [ ] Wayland support: Mint Cinnamon is X11 for now, but the cursor layer and window watching would need a different solution on Wayland.
- [ ] The cursor layer with a game that draws its own cursor or uses exclusive full screen (without a compositor): there the layer does not show, or there will be two cursors. Should this be flagged or tested per profile?

## Tracking the profile button

In normal mode the mouse steps through the slots itself with the profile button, so the service has to learn about it.

- Every slot change produces a `05 39` event on the dock's interface 1, both on a button press and on the program's own selection. The event does not contain the slot.
- On the event the service reads the active slot once (`05/84`). If it is not the one it selected, it is a manual switch (`manual_store`). There is no timed polling.
- The tray icon is then orange, and the text shows the manual slot: `Profile: arpg (manual, blue slot)`, or `Profile: manual, blue slot` if the program does not know the slot's contents (the icon then shows the letter `M`, `K` in Hungarian). It also rereads the DPI, because every slot has its own stages.
- A manual switch holds until the next window change. Then the rule decides again, even if the profile is the same as before the button press. In that case it does not write, it only selects the slot. A repeated signal for the same window does not count as a window change.
- Driver mode is not used: then the mouse would not switch slots without the program.

## Plans for approval

Coding only after approval.

### Custom cursor on Windows

**Proposal: temporarily replacing the system cursor** (`SetSystemCursor`), without a layer.

- When the window of a profile with a cursor becomes active, the program loads the user's `.cur` file at the given scale (`CreateIconIndirect`) and replaces the arrow cursor with it (OCR_NORMAL, optionally the hand and text cursors too).
- On switching to another window and on exit it restores the system cursors (`SystemParametersInfo(SPI_SETCURSORS)`).
- Advantage: no lag, because Windows itself draws it, and it works in exclusive full screen too, where a layer window would not show. It does not touch the game (no DLL injection as with YoloMouse), neutral as far as anti-cheat goes.
- Risk: if the program crashes, the big cursor stays in the system. So at start we always restore the system cursors, and the tray menu gets a "Restore cursor" item. Logging out restores it too.
- Limitation: if the game draws its own cursor or sets its own cursor image, the replacement does not show. Unity games (Last Epoch) use the system arrow, so it should work there. This can only be tried on a Windows machine.
- The config stays the same (`cursor`, `cursor_scale`), only the implementation is platform-specific: `platform/win/cursor.py`, with the same `show()` / `hide()` interface as on Linux.

Alternative: a layer window as on Linux (`WS_EX_LAYERED | WS_EX_TRANSPARENT`, raw mouse events, hiding the system cursor). I only propose this if the replacement does not work in some game.

## Milestones

1. ✓ **M1 – protocol library:** project skeleton, `core/protocol.py`, unit tests based on `data/session1`.
2. ✓ **M2 – command-line prototype:** DPI, battery, button mapping on the live slot; capture 2.
3. ✓ **M3 – background service:** window watcher, rule engine, tray icon, TOML config, Synapse import, onboard slots.
4. ✓ **M4 – graphical interface and Windows installer:** v0.1.0.
5. ✓ **L1–L3 – Linux port:** hidraw, OpenRazer warning, X11 window watching, autostart, .deb, live status; v0.2.0.
6. ✓ **Dock battery level switch** (v0.2.1) and **custom cursor** (v0.2.2), Linux only.
7. ✓ **Tracking the profile button**, on Linux.
8. ✓ **Bilingual interface** (English, Hungarian) and English documentation with a Hungarian version.
9. **Next – Windows catching up:** event reader without polling (with it, profile button tracking too), custom cursor, trying the dock switch and the live status on Windows, Windows release.
