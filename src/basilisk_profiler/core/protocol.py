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

# Storage slot (first argument of most commands). 0x01 is the live profile; 00/C0
# answers for 0x01..0x05, so 0x02..0x05 are taken to be the onboard profile slots.
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
    MOUSE_BUTTON = 0x01
    KEYBOARD = 0x02
    DPI = 0x06


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
class RawAction:
    """An action type this module does not model yet; kept so it round-trips."""
    type: int
    data: bytes = field(default=b'')

    @property
    def action_type(self) -> int:
        return self.type

    def payload(self) -> bytes:
        return self.data


Action = MouseButtonAction | KeyAction | RawAction


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
    else:
        action = RawAction(action_type, data)
    return ButtonMapping(button, action, store=store, hypershift=bool(hypershift))
