# SPDX-License-Identifier: GPL-2.0-or-later
"""Razer 90-byte HID feature report: framing and the commands used by the Basilisk V3 Pro.

Layout (same as openrazer's ``struct razer_report``):

    0      status
    1      transaction id
    2..3   remaining packets (big endian)
    4      protocol type
    5      data size (number of meaningful argument bytes)
    6      command class
    7      command id (bit 0x80 set = query)
    8..87  arguments (80 bytes)
    88     CRC: XOR of bytes 2..87
    89     reserved

See docs/basilisk-v3-pro-protocol.md for how each command was identified.
"""
from __future__ import annotations

import enum
from dataclasses import dataclass, field

REPORT_LEN = 90
ARGS_LEN = 80
DEFAULT_TRANSACTION_ID = 0x1F

# Storage slot (first argument of most commands). 0x01 is the live profile; 0x02..0x05 are
# the four onboard slots (Synapse's On-Board Memory list, top to bottom; capture 2).
STORE_LIVE = 0x01
ONBOARD_STORES = (0x02, 0x03, 0x04, 0x05)

MAX_DPI_STAGES = 5
DPI_MIN = 100
DPI_MAX = 30000


class ProtocolError(ValueError):
    """A frame or response could not be built or parsed."""


class Status(enum.IntEnum):
    NEW = 0x00
    BUSY = 0x01
    SUCCESS = 0x02
    FAILURE = 0x03
    TIMEOUT = 0x04
    NOT_SUPPORTED = 0x05


class DeviceMode(enum.IntEnum):
    NORMAL = 0x00
    DRIVER = 0x03


class ActionType(enum.IntEnum):
    DISABLED = 0x00
    MOUSE_BUTTON = 0x01  # also wheel: 9 = scroll up (capture 2)
    KEYBOARD = 0x02
    DPI = 0x06
    PROFILE = 0x07
    CONSUMER = 0x0A  # HID consumer page usage (media keys)
    REPEAT_SCROLL = 0x0E  # factory action of the wheel tilts; not modelled further
    SCROLL_MODE = 0x12  # 01 = toggle tactile / free spin (factory action of button 0x6A)


class DpiFunction(enum.IntEnum):
    STAGE_UP = 0x01
    CLUTCH = 0x05  # hold for a fixed DPI; payload carries x, y
    CYCLE_UP = 0x06  # factory action of the DPI button


class ProfileFunction(enum.IntEnum):
    CYCLE_UP = 0x04  # factory action of the profile button


class ButtonId(enum.IntEnum):
    """Device button ids (02/0C, 02/8C). Left/right click are not mapped here on purpose."""
    WHEEL_CLICK = 0x03
    BUTTON4 = 0x04  # rear side button
    BUTTON5 = 0x05  # front side button
    PROFILE = 0x0E  # underside
    CLUTCH = 0x0F  # sensitivity clutch (thumb), Synapse DKM_SB_02
    TILT_LEFT = 0x34
    TILT_RIGHT = 0x35
    DPI_CYCLE = 0x60
    SCROLL_MODE = 0x6A


def crc(frame: bytes) -> int:
    """XOR of bytes 2..87 of a 90-byte frame."""
    value = 0
    for b in frame[2:88]:
        value ^= b
    return value


@dataclass(frozen=True)
class Report:
    command_class: int
    command_id: int
    args: bytes = b''
    data_size: int | None = None
    transaction_id: int = DEFAULT_TRANSACTION_ID
    status: int = Status.NEW
    remaining: int = 0
    protocol: int = 0

    @property
    def size(self) -> int:
        return len(self.args) if self.data_size is None else self.data_size

    def to_bytes(self) -> bytes:
        if len(self.args) > ARGS_LEN:
            raise ProtocolError(f'arguments too long: {len(self.args)} > {ARGS_LEN}')
        frame = bytearray(REPORT_LEN)
        frame[0] = self.status
        frame[1] = self.transaction_id
        frame[2:4] = self.remaining.to_bytes(2, 'big')
        frame[4] = self.protocol
        frame[5] = self.size
        frame[6] = self.command_class
        frame[7] = self.command_id
        frame[8:8 + len(self.args)] = self.args
        frame[88] = crc(frame)
        return bytes(frame)

    @classmethod
    def from_bytes(cls, frame: bytes, *, check_crc: bool = True) -> Report:
        if len(frame) != REPORT_LEN:
            raise ProtocolError(f'expected {REPORT_LEN} bytes, got {len(frame)}')
        if check_crc and crc(frame) != frame[88]:
            raise ProtocolError(f'bad CRC: {frame[88]:#04x} != {crc(frame):#04x}')
        return cls(
            command_class=frame[6],
            command_id=frame[7],
            args=bytes(frame[8:88]),
            data_size=frame[5],
            transaction_id=frame[1],
            status=frame[0],
            remaining=int.from_bytes(frame[2:4], 'big'),
            protocol=frame[4],
        )

    @property
    def command(self) -> tuple[int, int]:
        return self.command_class, self.command_id

    def matches(self, request: Report) -> bool:
        """True if this response answers ``request``."""
        return self.command == request.command and self.transaction_id == request.transaction_id


def _args(*values: int, size: int) -> bytes:
    data = bytes(values)
    return data + bytes(size - len(data))


# --- device mode (00/04, 00/84) -------------------------------------------------

def set_device_mode(mode: DeviceMode, **kw) -> Report:
    return Report(0x00, 0x04, _args(mode, 0x00, size=2), **kw)


def get_device_mode(**kw) -> Report:
    return Report(0x00, 0x84, _args(size=2), **kw)


def parse_device_mode(response: Report) -> int:
    return response.args[0]


def get_firmware_version(**kw) -> Report:
    return Report(0x00, 0x81, _args(size=2), **kw)


def parse_firmware_version(response: Report) -> str:
    return f'{response.args[0]}.{response.args[1]:02d}'


def get_slot_info(store: int, **kw) -> Report:
    """Query 00/C0. Answers 0x08 for stores 0x01..0x05 and 0x00 beyond; meaning not settled."""
    return Report(0x00, 0xC0, _args(store, size=2), **kw)


# --- power (07/80, 07/84) -------------------------------------------------------

def get_battery_level(**kw) -> Report:
    return Report(0x07, 0x80, _args(size=2), **kw)


def get_charging_status(**kw) -> Report:
    return Report(0x07, 0x84, _args(size=2), **kw)


def parse_battery_percent(response: Report) -> int:
    """Battery level as 0..100 (the device reports 0..255)."""
    return round(response.args[1] * 100 / 255)


def parse_charging(response: Report) -> bool:
    return bool(response.args[1])


# --- Mouse Dock Pro lighting (0F/02, 0F/82) ----------------------------------------
# The dock answers commands sent with transaction id 0xFF itself; with 0x1F they reach the
# mouse (its LED zones 0x01 / 0x04 / 0x0A). The dock has a single LED zone, 0x0F.
# Store 0x01 holds the persistent effect; store 0x00 holds the colour shown right now,
# which the battery effect overwrites at the next battery report (e.g. when the mouse wakes).
DOCK_TRANSACTION_ID = 0xFF
DOCK_LED = 0x0F
DOCK_STORE = 0x01
DOCK_STORE_NOW = 0x00
EFFECT_STATIC = 0x01
EFFECT_BATTERY = 0x0D  # Synapse's battery level effect: red -> yellow -> green


@dataclass(frozen=True)
class DockEffect:
    effect: int
    params: bytes = b''  # the bytes after the effect id, as the dock reports them

    def to_json(self) -> str:
        return bytes([self.effect, *self.params]).hex()

    @classmethod
    def from_json(cls, text: str) -> DockEffect:
        data = bytes.fromhex(text)
        if not data:
            raise ProtocolError('empty dock effect')
        return cls(data[0], data[1:])


BATTERY_EFFECT = DockEffect(EFFECT_BATTERY, b'\x01')


def static_effect(r: int, g: int, b: int) -> DockEffect:
    return DockEffect(EFFECT_STATIC, bytes([0x00, 0x00, 0x01, r, g, b]))


def battery_color(percent: int) -> tuple[int, int, int]:
    """Our estimate of the battery effect's colour: hue 0 (red) .. 120 (green) degrees."""
    hue = 120 * min(max(percent, 0), 100) / 100
    if hue < 60:
        return 0xFF, round(hue / 60 * 0xFF), 0
    return round((120 - hue) / 60 * 0xFF), 0xFF, 0


def get_dock_effect(store: int = DOCK_STORE) -> Report:
    return Report(0x0F, 0x82, _args(store, DOCK_LED, size=12),
                  transaction_id=DOCK_TRANSACTION_ID)


def parse_dock_effect(response: Report) -> DockEffect:
    return DockEffect(response.args[2], bytes(response.args[3:response.size]))


def set_dock_effect(effect: DockEffect, store: int = DOCK_STORE) -> Report:
    return Report(0x0F, 0x02, bytes([store, DOCK_LED, effect.effect, *effect.params]),
                  transaction_id=DOCK_TRANSACTION_ID)


# --- DPI stages (04/06, 04/86) --------------------------------------------------

@dataclass(frozen=True)
class DpiStage:
    x: int
    y: int

    def __post_init__(self):
        for v in (self.x, self.y):
            if not DPI_MIN <= v <= DPI_MAX:
                raise ProtocolError(f'DPI {v} out of range {DPI_MIN}..{DPI_MAX}')


@dataclass(frozen=True)
class DpiStages:
    stages: tuple[DpiStage, ...]
    active: int  # 1-based
    store: int = STORE_LIVE

    def __post_init__(self):
        if not 1 <= len(self.stages) <= MAX_DPI_STAGES:
            raise ProtocolError(f'need 1..{MAX_DPI_STAGES} DPI stages, got {len(self.stages)}')
        if not 1 <= self.active <= len(self.stages):
            raise ProtocolError(f'active stage {self.active} out of range')


def set_dpi_stages(stages: DpiStages, **kw) -> Report:
    # Synapse numbers stages from 0 when writing; the device answers 04/86 from 1.
    body = bytearray([stages.store, stages.active, len(stages.stages)])
    for i, s in enumerate(stages.stages):
        body += bytes([i]) + s.x.to_bytes(2, 'big') + s.y.to_bytes(2, 'big') + b'\x00\x00'
    return Report(0x04, 0x06, bytes(body), **kw)


def set_dpi_xy(x: int, y: int | None = None, store: int = STORE_LIVE, **kw) -> Report:
    """04/05: the current DPI (Synapse writes it next to the stage table)."""
    y = x if y is None else y
    return Report(0x04, 0x05, bytes([store]) + x.to_bytes(2, 'big') + y.to_bytes(2, 'big')
                  + b'\x00\x00', **kw)


def get_dpi_stages(store: int = STORE_LIVE, **kw) -> Report:
    return Report(0x04, 0x86, _args(store, size=ARGS_LEN), **kw)


def parse_dpi_stages(response: Report) -> DpiStages:
    a = response.args
    count = a[2]
    if not 1 <= count <= MAX_DPI_STAGES:
        raise ProtocolError(f'bad DPI stage count {count}')
    stages = []
    for i in range(count):
        e = a[3 + 7 * i:10 + 7 * i]
        stages.append(DpiStage(int.from_bytes(e[1:3], 'big'), int.from_bytes(e[3:5], 'big')))
    return DpiStages(tuple(stages), active=a[1], store=a[0])


# --- button mapping (02/0C) -----------------------------------------------------

BUTTON_MAPPING_SIZE = 10


@dataclass(frozen=True)
class MouseButtonAction:
    button: int  # 1 = left ... 5 = forward side button

    action_type = ActionType.MOUSE_BUTTON

    def payload(self) -> bytes:
        return bytes([self.button])


@dataclass(frozen=True)
class KeyAction:
    usage: int  # HID keyboard usage id, see core.keys
    modifiers: int = 0  # HID modifier bitmask, see core.keys.Modifier

    action_type = ActionType.KEYBOARD

    def payload(self) -> bytes:
        return bytes([self.modifiers, self.usage])


@dataclass(frozen=True)
class DisabledAction:
    action_type = ActionType.DISABLED

    def payload(self) -> bytes:
        return b''


@dataclass(frozen=True)
class ConsumerAction:
    usage: int  # HID consumer page, e.g. 0xCD play/pause

    action_type = ActionType.CONSUMER

    def payload(self) -> bytes:
        return self.usage.to_bytes(2, 'big')


@dataclass(frozen=True)
class DpiAction:
    function: int  # DpiFunction
    dpi: int | None = None  # CLUTCH only; same value for x and y

    action_type = ActionType.DPI

    def payload(self) -> bytes:
        if self.function == DpiFunction.CLUTCH:
            value = (self.dpi or 400).to_bytes(2, 'big')
            return bytes([self.function]) + value + value
        return bytes([self.function])


@dataclass(frozen=True)
class ProfileAction:
    function: int  # ProfileFunction

    action_type = ActionType.PROFILE

    def payload(self) -> bytes:
        return bytes([self.function])


@dataclass(frozen=True)
class ScrollModeAction:
    action_type = ActionType.SCROLL_MODE

    def payload(self) -> bytes:
        return b''


@dataclass(frozen=True)
class RawAction:
    """An action type this module does not model yet; kept so it round-trips."""
    type: int
    data: bytes = field(default=b'')

    @property
    def action_type(self) -> int:
        return self.type

    def payload(self) -> bytes:
        return self.data


Action = (MouseButtonAction | KeyAction | DisabledAction | ConsumerAction | DpiAction
          | ProfileAction | ScrollModeAction | RawAction)


@dataclass(frozen=True)
class ButtonMapping:
    button: int  # device button id, e.g. 0x04 / 0x05 side buttons
    action: Action
    store: int = STORE_LIVE
    hypershift: bool = False


def set_button_mapping(mapping: ButtonMapping, **kw) -> Report:
    payload = mapping.action.payload()
    body = bytes([mapping.store, mapping.button, int(mapping.hypershift),
                  mapping.action.action_type, len(payload)]) + payload
    if len(body) > BUTTON_MAPPING_SIZE:
        raise ProtocolError('button action payload too long')
    return Report(0x02, 0x0C, body + bytes(BUTTON_MAPPING_SIZE - len(body)), **kw)


def get_button_mapping(button: int, store: int = STORE_LIVE, hypershift: bool = False,
                       **kw) -> Report:
    """Query (02/8C); the answer has the same layout as 02/0C."""
    return Report(0x02, 0x8C, _args(store, button, int(hypershift), size=BUTTON_MAPPING_SIZE),
                  **kw)


def parse_button_mapping(report: Report) -> ButtonMapping:
    a = report.args
    store, button, hypershift, action_type, length = a[:5]
    data = bytes(a[5:5 + length])
    action: Action
    if action_type == ActionType.MOUSE_BUTTON and length == 1:
        action = MouseButtonAction(data[0])
    elif action_type == ActionType.KEYBOARD and length == 2:
        action = KeyAction(usage=data[1], modifiers=data[0])
    elif action_type == ActionType.DISABLED and length == 0:
        action = DisabledAction()
    elif action_type == ActionType.CONSUMER and length == 2:
        action = ConsumerAction(int.from_bytes(data, 'big'))
    elif action_type == ActionType.DPI and length == 1 and data[0] != DpiFunction.CLUTCH:
        action = DpiAction(data[0])
    elif (action_type == ActionType.DPI and length == 5 and data[0] == DpiFunction.CLUTCH
          and data[1:3] == data[3:5]):
        action = DpiAction(DpiFunction.CLUTCH, int.from_bytes(data[1:3], 'big'))
    elif action_type == ActionType.PROFILE and length == 1:
        action = ProfileAction(data[0])
    elif action_type == ActionType.SCROLL_MODE and data == b'':
        action = ScrollModeAction()
    else:
        action = RawAction(action_type, data)
    return ButtonMapping(button, action, store=store, hypershift=bool(hypershift))


# --- onboard memory (06/8E) -----------------------------------------------------

@dataclass(frozen=True)
class MemoryInfo:
    total: int  # bytes
    free: int

    @property
    def free_percent(self) -> float:
        return 100 * self.free / self.total if self.total else 0.0


def get_memory_info(**kw) -> Report:
    return Report(0x06, 0x8E, _args(size=14), **kw)


def parse_memory_info(response: Report) -> MemoryInfo:
    """Answer layout ``00 64 | total (4 BE) | free (4 BE) | 00 01 00``, e.g. Synapse's
    "Available 99.67%" = 0x4BC00 of 0x4C000."""
    a = response.args
    return MemoryInfo(total=int.from_bytes(a[2:6], 'big'), free=int.from_bytes(a[6:10], 'big'))


# --- active profile slot (05/04, 05/84, 05/81) -----------------------------------
# The mouse uses exactly one store at a time: the live slot 0x01 (LED white) or an onboard
# slot (0x02 red .. 0x05 cyan). The profile button steps through them; writes to a store
# that is not active have no visible effect until it is selected.

def get_active_profile(**kw) -> Report:
    return Report(0x05, 0x84, _args(size=2), **kw)


def parse_active_profile(response: Report) -> int:
    return response.args[0]


def set_active_profile(store: int, **kw) -> Report:
    return Report(0x05, 0x04, _args(store, size=2), **kw)


def get_profile_list(**kw) -> Report:
    """05/81 -> ``count, store ids...`` e.g. ``05 01 02 03 04 05``."""
    return Report(0x05, 0x81, _args(size=2), **kw)


def parse_profile_list(response: Report) -> list[int]:
    count = response.args[0]
    return list(response.args[1:1 + count])
