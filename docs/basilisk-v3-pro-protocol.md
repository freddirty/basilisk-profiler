# Razer Basilisk V3 Pro + Mouse Dock Pro – USB protocol (capture 1)

**English** · [Magyar](basilisk-v3-pro-protocol.hu.md)

Source: `captures/session1.pcap` (USBPcap5, device 3 = Mouse Dock Pro, VID 0x1532, PID 0x00A4), 2026-11-01 14:28–14:31.
Synapse 4.0.827 was writing; the mouse was connected wirelessly to the dock. The decoded lists: `captures/session1_cmds.txt` (requests), `captures/session1_rsp.txt` (responses). The decoder: `tools/razer_cmds.py`.
Hypershift is out of scope.

## Transport

- HID feature report on the dock's **interface 0** (wIndex 0, report ID 0).
  - Write: `SET_REPORT` – bmRequestType 0x21, bRequest 0x09, wValue 0x0300.
  - Read back: `GET_REPORT` – 0xA1 / 0x01 / 0x0300.
  - Synapse reads the response back immediately after every write.
- The report is 90 bytes, exactly openrazer's `razer_report` layout:

| byte | field | observation |
|---|---|---|
| 0 | status | 0x00 in requests; in responses 0x02 = OK, 0x01 = busy (read again) |
| 1 | transaction id | Synapse uses a rolling counter (0x00–0x1E), openrazer a fixed 0x1F; the dock accepts both |
| 2–3 | remaining packets | 0x0000 |
| 4 | protocol type | 0x00 |
| 5 | data size | length of the arguments |
| 6 | command class | |
| 7 | command id | bit 0x80 = query (GET) |
| 8–87 | arguments (80 B) | |
| 88 | CRC | XOR of bytes 2–87 (checked on all 65 requests and responses) |
| 89 | reserved | 0x00 |

## Storage slot (argument 1)

The first argument of many commands is a storage slot id:

- `0x01` = the active (live) settings. Every change is written here and takes effect at once.
- `0x02`–`0x05` = the **4 onboard profile slots** in the mouse's memory (capture 2). In Synapse's "On-Board Memory" list, in order: slot 1 red = 0x02, 2 green = 0x03, 3 blue = 0x04, 4 cyan = 0x05. When switching profiles, Synapse writes the profile to its slot **and** to 0x01.
- In openrazer the same byte is `VARSTORE` (0x01).

## Identified commands

| class/id | meaning | arguments | openrazer |
|---|---|---|---|
| 04/06 | write DPI stages | `store, active_stage(from 1), count, {idx(from 0), X_hi, X_lo, Y_hi, Y_lo, 0, 0} × count` | same (`set_dpi_stages`) |
| 04/86 | read DPI stages | `store` → the same layout, but in the response idx starts at 1 | same |
| 02/0C | **button mapping** | `store, button_id, hypershift(0), type, length, data…` (see below) | **not there** (new) |
| 02/14, 02/17, 02/16 | per profile slot, before writing the buttons: `14 [store,0]`, `17 [store, 0/1, 0…]`, `16 [store,0]` | probably start / clear / close of a block (e.g. macro table) – **to be clarified** | no |
| 0F/04 | brightness | `store, led(0x00), value` – 0x54 = 84/255 ≈ 33% (33 in the profile) | same (extended matrix) |
| 0F/84 | read brightness | | same |
| 0F/02 | set effect | `00 00 08 00 00 00` | extended matrix effect, details later |
| 0F/03 | Chroma custom frame (per row) | continuous, belongs to the software effect – can be ignored | same |
| 0F/80 | read LED zones/effect | response: `01 19 03 01 01 04 19 03 01 01 0a 19 03 01 0b` | – |
| 07/80 | battery level | response `00 ff` = 100% | same |
| 07/84 | charging state | response `00 00` = not charging | same |
| 00/84 | read device mode | response `03 00` = **driver mode** | same (00/04 = write) |
| 00/C0 | profile slot info (query) | `[store,0]` → `[store,08]` for slots 0x01–0x05, `00` for 0x06 | its meaning is not needed for operation |
| 04/05 | current DPI | `store, X(2), Y(2), 0, 0` – Synapse writes it to the onboard slot next to the stage table | same (`set_dpi_xy`) |
| 05/02, 05/03 | prepare profile slot (when writing an onboard slot) | `[store]` | – |
| 05/08 | the profile's name/id in the onboard slot | `store, offset(2), 00, FA, 64 bytes of data` – Synapse writes a GUID, the profile name and a hash here | – (not needed for operation) |
| 05/04 · 05/84 | select / query the active slot | `[store, 0]` – see "The active slot" | – |
| 05/81 | list of slots | → `05 01 02 03 04 05` | – |
| 06/8E | onboard memory usage | response `00 64 | total(4) | free(4) | 00 01 00`, e.g. 0x4C000 / 0x4BC00 = "Available 99.67%" | – |
| 00/BF | device paired with the dock | response `02 01 00 ab 00 ff ff` – contains 0x00AB (wireless Basilisk V3 Pro PID) | – |

### Button mapping (02/0C) in detail

`store, button, hypershift, type, length, data[length], 0…` (data size = 10)

| type | meaning | data |
|---|---|---|
| 0x01 | mouse button | `[mouse button number]` – e.g. `01 05` = Mouse Button 5 (factory) |
| 0x02 | key | `[modifier bitmask, HID usage]` – the modifier is the usual HID bitmask (0x01 = left Ctrl) |
| 0x00 | disabled | – (length 0) |
| 0x06 | DPI function | `01` = stage up; `06` = cycle stages (factory function of the DPI button); `05 X(2) Y(2)` = sensitivity clutch at that DPI (factory function of the thumb button, 400 DPI) |
| 0x07 | profile function | `04` = next profile (factory function of the profile button) |
| 0x0A | multimedia | `[HID consumer usage, 2 bytes BE]`, e.g. `00 CD` = play/pause |
| 0x0E | repeated scroll | `68 00 14` left, `69 00 14` right – factory function of the wheel tilt |
| 0x12 | toggle scroll mode | `01` – factory function of the scroll mode button (0x6A) (read with 02/8C) |

In the mouse button type, number 9 is scroll up ("Scroll Up").

Button ids from the captures:

| button id | button | evidence |
|---|---|---|
| 0x03 | wheel click | capture 2, B1 → KEY_1; factory: mouse button 3 |
| 0x04 | Button4 (back side button) | KEY_R (0x15) in the "general" profile |
| 0x05 | Button5 (front side button) | **14:30:27 → `01 05 00 02 02 00 25` = KEY_8 (HID 0x25)** |
| 0x0E | profile button (bottom) | B6 → KEY_6; factory: profile function `04` |
| 0x0F | sensitivity clutch (thumb, Synapse: DKM_SB_02) | KEY_E (0x08); Ctrl+W (`01 1a`) in the browser profile |
| 0x34 | wheel tilt left | B2 → KEY_2; factory: `0E 68 00 14` |
| 0x35 | wheel tilt right | B3 → KEY_3; factory: `0E 69 00 14` |
| 0x60 | DPI stage button | B5 → KEY_5; factory: DPI function `06` |
| 0x6A | scroll mode button (tactile/free) | B4 → KEY_4; its factory function was not seen yet |

The ids of the left and right click are deliberately not handled, so no profile can take away the primary buttons.

The key codes are standard HID Usage IDs (0x04 = A … 0x1D = Z, 0x1E = 1 … 0x27 = 0).

## The steps in the capture

| time | action | commands |
|---|---|---|
| 14:28:35 | stages created (400/1600/1800/3200/6400) | `04/06 01 02 05 …` + `04/86` |
| 14:28:36 | stage 3 (1800) became active | `04/06 01 03 05 …` |
| 14:29:39 | stage 2 (1600) became active | `04/06 01 02 05 …` – changing the active stage also rewrites the whole table |
| 14:30:27 | Button5 → KEY_8 | `02/0C 01 05 00 02 02 00 25` – only to the live (0x01) slot |
| 14:31:07 | profile switch (browser) | button reset, `02/14-17-16`, DPI table, effect, buttons to slots 0x05 and 0x01 (Ctrl+W, Ctrl+T) |
| 14:31:27.8 | the user pressed the "Cycle Up Profile" button on the bottom of the mouse | interrupt IN, EP 0x82: `04 50 00…` (press), then at 14:31:28.0 `04 00…` (release) – report ID 4 = `razerKeyReportID`, Razer key code 0x50 |
| 14:31:28 | Synapse then switched to the "fps1" profile (E/F/R/G buttons, slot 0x03) | the same command sequence as a manual switch |

**Important:** with the profile button it is not the mouse that switches profiles. The mouse only sends a Razer key event (report 4, code 0x50); Synapse does the switch on the host side by writing the profile. The other `razerKey` type inputs work the same way (in the factory mappings of `main.json`, e.g. key 84 = 0x54). Our own program therefore has to listen for these events on EP 0x82.

Step 1a (changing the value of stage 3 to 1600) did not happen, so changing a stage value was not seen separately. However, every stage change sends the whole `04/06` table, so the format is known.

## Capture 2 (2026-11-01 19:28–19:37, USBPcap2, device 7)

Raw capture: local only (`captures/`). Decoded: `data/session2/`.

| time | step | observation |
|---|---|---|
| 19:29:30 | "Teszt" profile created | write to the live slot (0x01) |
| 19:30:10 | A1: "Teszt" to onboard slot 2 (green) | `05/03`, `02/14`, `00/C0`, `02/17`, `06/8E`, `05/02`, 4× `05/08` (name, GUID, hash), `04/05`, `04/06`, `0F/04`, `06/8E` – all to slot **0x03** |
| 19:31:01 | A4: profile button (1st) | EP 0x82: `04 50` → Synapse writes the contents of slot 0x04 (blue, ARPG 1) to 0x04 and 0x01 |
| 19:31:19 | A4: profile button (2nd) | the same with 0x05 (cyan, Browser) |
| 19:32:45–19:33:35 | B1–B6: button ids | see the button table (Synapse rewrites every mapped button to slots 0x03 and 0x01) |
| 19:34:30–19:36:53 | C1–C6: output types (on the thumb button) | mouse button 4, multimedia `00CD`, DPI stage up, scroll up (mouse button 9), disabled, back to clutch |

**The active slot (hardware test, 19:00, without Synapse, normal mode):**

- The mouse uses exactly one slot at a time: the live slot (0x01, the LED is **white**) or an onboard one (0x02 red, 0x03 green, 0x04 blue, 0x05 cyan). The profile button steps through them in a loop: white → red → green → blue → cyan → white.
- Writing to a slot that is **not active** has no visible effect. If, say, the cyan slot is active, the mouse ignores a mapping written to the live slot (0x01). The earlier (M3) test only worked because the white slot happened to be active.
- `05/84` → `[store]` the active slot; after pressing the profile button it went from 05 to 01.
- `05/04 [store, 0]` selects the active slot. Tried: 05 → cyan LED, the button sent the cyan slot's mapping; 01 → white LED, the live slot's mapping.
- `05/81` → `05 01 02 03 04 05` (the number and list of slots). `05/80` and `05/8A` respond with `05`; their meaning is not needed.
- In driver mode (Synapse) the mouse only sends the profile button event, and Synapse copies the next slot's contents to the live slot.

**So our program:**
- Writes the profiles assigned to onboard slots to slots 0x02–0x05, but only when they change.
- On a window change, if the profile is in an onboard slot, only selects that slot (05/04).
- If the profile is not in an onboard slot, writes it to the live slot and makes the white slot active.
- A manual switch with the profile button holds until the next window change. On the `05 39` event it reads the active slot once (`05/84`), so it knows a manual switch happened; on the next window change it selects the slot the rules choose, even if the profile is the same as before the press.
- On exit it restores the slot that was active at start and leaves normal mode.

## Events on the dock's interface 1 (Linux, hidraw, 2026-11-03)

Watched in normal mode, without Synapse. The dock's interface 1 (`/dev/hidraw3` on Linux) reports with report ID 5. The kernel gives every hidraw reader its own copy, so watching does not take the input away from the desktop.

| Report | Meaning | Example |
| --- | --- | --- |
| `05 02 XX XX YY YY` | DPI changed (X/Y big-endian), on every DPI button press | `05 02 0c 80 0c 80` = 3200 |
| `05 31 LL …` | battery level, 0–255 | `05 31 cd` ≈ 80% |
| `05 09 SS 01` | connection / wake state | `05 09 02 01`, `05 09 03 01` |
| `05 39 00 …` | the active slot changed; it does not contain the new slot, `05/84` gives it | `05 39 00 00 …` |
| `05 0c …` | unknown, on wake | |

**Slot change (test, 2026-11-04, normal mode):** every press of the profile button gives this sequence: two all-zero reports on `/dev/hidraw4`, an all-zero `04 00 …` on `/dev/hidraw3`, then about 0.2 s later `05 39 00 …`. `05/84` already gives the new slot before the `05 39`. The same sequence comes when the host selects a slot (`05/04`), so after the event the slot read has to be compared with the expected one. Over six presses the order was 01 → 02 → 03 → 04 → 05 → 01 → 02.

Additional queries: `04/85` (arg.: slot) gives the current DPI (`slot, X(2), Y(2)`), byte 1 of `04/86` is the number of the active stage (from 1). While the mouse sleeps the dock answers with `FAILURE` or times out until the mouse is moved.

## Consequences for the design

1. The basic protocol (frame, CRC, DPI, brightness, battery, device mode) is the same as openrazer's, so on Linux the code can write directly through hidraw.
2. Button mapping (02/0C) is new but simple, and the **hardware** does it: the mouse/dock sends the key itself on the keyboard interface. So simple key mappings need no software injection (uinput / SendInput).
3. For application-dependent automatic switching it is enough to write the live slot (0x01): a whole profile (DPI table + about 10 buttons) is about 15 reports, ~1 s. The onboard slots can optionally be used too.
4. The mouse is in driver mode (`00/84 → 03`) while Synapse runs. With our own tool we have to check whether the mappings also stay in normal mode.

## Open questions

- The exact meaning of 02/14–17–16 (probably handling of the macro/Hypershift table; not needed for our writes so far).
- ~~Factory function of the scroll mode button (0x6A)~~: type 0x12, data `01` (read back).
- DPI stage down (probably `06 02`) and scroll down (probably mouse button 10): not seen, so the program does not offer them yet.
- The other Razer key codes (report 4) and the contents of report 5 (`hardwareEventReportID`, e.g. `05 31 fa 00 00 01`).
- ~~The full list of button ids~~, ~~other output types~~, ~~how many onboard slots there are~~: answered by capture 2.
- ~~Without driver mode (normal mode), does the profile button switch between the onboard slots by itself?~~ **Yes**: according to the user, on Linux without Synapse the mouse's button switches profiles. So the onboard profile slots work on their own; driver mode only redirects the button to the host.
- ~~How can the active onboard profile slot be selected by command?~~ `05/04 [slot, 0]` (see "The active slot"). ~~How many slots are there?~~ 4 + the live slot. Still open: does a slot store a name (Synapse writes here with 05/08), and do we need to write it too.

## The dock's own lighting (Linux, 2026-11-03)

- The dock itself answers commands sent with transaction id **0xFF**; with 0x1F the command goes to the mouse (LED zones 0x01/0x04/0x0A). 0x3F and 0x9F time out.
- The dock's only LED zone is **0x0F** (`0F/80` response: `0f 19 03 01 01`), its brightness `0F/84 [slot, 0f]` = 0xFF.
- `0F/82 [slot, 0f]` gives the effect: slot 1 is the persistent setting (Synapse "battery level": `01 0f 0d 01`, i.e. effect **0x0D**), slot 0 is the colour shown right now (static: `00 0f 01 00 00 01 R G B`; `70 ff 00` at 80% battery).
- `0F/02` writes in the same form. A static colour written to slot 0 shows at once; effect 0x0D overwrites it with its own colour at the next battery report (e.g. when the mouse wakes up).
