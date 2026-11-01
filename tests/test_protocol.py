# SPDX-License-Identifier: GPL-2.0-or-later
from pathlib import Path

import pytest

from basilisk_profiler.core import keys
from basilisk_profiler.core import protocol as p

FIXTURES = Path(__file__).parents[1] / 'data' / 'session1' / 'frames.txt'


def load_frames():
    frames = []
    for line in FIXTURES.read_text().splitlines():
        direction, data = line.split()
        frames.append((direction, bytes.fromhex(data)))
    return frames


FRAMES = load_frames()


def find(direction, command, tid):
    for d, frame in FRAMES:
        if d == direction and (frame[6], frame[7]) == command and frame[1] == tid:
            return frame
    raise LookupError(f'no {direction} frame {command} tid={tid:#x}')


def test_fixtures_present():
    assert len(FRAMES) > 100


@pytest.mark.parametrize('direction,frame', FRAMES)
def test_every_captured_frame_round_trips(direction, frame):
    report = p.Report.from_bytes(frame)
    assert report.to_bytes() == frame


def test_bad_crc_is_rejected():
    frame = bytearray(FRAMES[0][1])
    frame[88] ^= 0xFF
    with pytest.raises(p.ProtocolError):
        p.Report.from_bytes(bytes(frame))


def test_wrong_length_is_rejected():
    with pytest.raises(p.ProtocolError):
        p.Report.from_bytes(bytes(89))


def test_set_dpi_stages_matches_synapse():
    # 14:28:35: stages 400/1600/1800/3200/6400, stage 2 active, live slot
    stages = p.DpiStages(
        tuple(p.DpiStage(v, v) for v in (400, 1600, 1800, 3200, 6400)), active=2)
    built = p.set_dpi_stages(stages, transaction_id=0x06).to_bytes()
    assert built == find('req', (0x04, 0x06), 0x06)


def test_parse_dpi_stages_response():
    response = p.Report.from_bytes(find('rsp', (0x04, 0x86), 0x07))
    stages = p.parse_dpi_stages(response)
    assert stages.store == p.STORE_LIVE
    assert stages.active == 2
    assert [s.x for s in stages.stages] == [400, 1600, 1800, 3200, 6400]


def test_get_dpi_stages_matches_synapse():
    assert p.get_dpi_stages(transaction_id=0x07).to_bytes() == find('req', (0x04, 0x86), 0x07)


def test_set_button_key_8_matches_synapse():
    # 14:30:27: Button5 (id 0x05) -> KEY_8 on the live slot
    mapping = p.ButtonMapping(0x05, p.KeyAction(keys.usage('KEY_8')))
    built = p.set_button_mapping(mapping, transaction_id=0x0E).to_bytes()
    assert built == find('req', (0x02, 0x0C), 0x0E)


def test_parse_button_mapping_ctrl_w():
    report = p.Report.from_bytes(find('req', (0x02, 0x0C), 0x16))
    mapping = p.parse_button_mapping(report)
    assert mapping.store == 0x05
    assert mapping.button == 0x0F
    assert mapping.action == p.KeyAction(keys.usage('KEY_W'), keys.Modifier.LEFT_CTRL)


def test_mouse_button_mapping_round_trips():
    report = p.Report.from_bytes(find('req', (0x02, 0x0C), 0x11))
    mapping = p.parse_button_mapping(report)
    assert mapping.action == p.MouseButtonAction(5)
    assert p.set_button_mapping(mapping, transaction_id=0x11).to_bytes() == report.to_bytes()


def test_clutch_action_round_trips():
    # 14:31:28: the thumb button's factory action, sensitivity clutch at 400 DPI
    report = p.Report.from_bytes(find('req', (0x02, 0x0C), 0x00))
    mapping = p.parse_button_mapping(report)
    assert mapping.button == p.ButtonId.CLUTCH
    assert mapping.action == p.DpiAction(p.DpiFunction.CLUTCH, 400)
    assert p.set_button_mapping(mapping, transaction_id=0x00).to_bytes() == report.to_bytes()


# argument bytes of 02/0C writes seen in capture 2 (store, button, hypershift, type, len, data)
CAPTURE2_MAPPINGS = [
    ('030f0001010400000000', p.ButtonId.CLUTCH, p.MouseButtonAction(4)),
    ('030f000a0200cd000000', p.ButtonId.CLUTCH, p.ConsumerAction(0xCD)),
    ('030f0006010100000000', p.ButtonId.CLUTCH, p.DpiAction(p.DpiFunction.STAGE_UP)),
    ('030f0001010900000000', p.ButtonId.CLUTCH, p.MouseButtonAction(9)),
    ('030f0000000000000000', p.ButtonId.CLUTCH, p.DisabledAction()),
    ('0303000202001e000000', p.ButtonId.WHEEL_CLICK, p.KeyAction(0x1E)),
    ('0334000202001f000000', p.ButtonId.TILT_LEFT, p.KeyAction(0x1F)),
    ('03350002020020000000', p.ButtonId.TILT_RIGHT, p.KeyAction(0x20)),
    ('036a0002020021000000', p.ButtonId.SCROLL_MODE, p.KeyAction(0x21)),
    ('03600002020022000000', p.ButtonId.DPI_CYCLE, p.KeyAction(0x22)),
    ('030e0002020023000000', p.ButtonId.PROFILE, p.KeyAction(0x23)),
    ('05600006010600000000', p.ButtonId.DPI_CYCLE, p.DpiAction(p.DpiFunction.CYCLE_UP)),
    ('050e0007010400000000', p.ButtonId.PROFILE, p.ProfileAction(p.ProfileFunction.CYCLE_UP)),
    ('0534000e036800140000', p.ButtonId.TILT_LEFT, p.RawAction(0x0E, bytes.fromhex('680014'))),
]


@pytest.mark.parametrize('args,button,action', CAPTURE2_MAPPINGS)
def test_capture2_mappings(args, button, action):
    report = p.Report(0x02, 0x0C, bytes.fromhex(args))
    mapping = p.parse_button_mapping(report)
    assert (mapping.button, mapping.action) == (button, action)
    assert p.set_button_mapping(mapping).args == report.args


def test_memory_info():
    answer = p.Report(0x06, 0x8E, bytes.fromhex('00640004c0000004bc0000000100'),
                      status=p.Status.SUCCESS)
    info = p.parse_memory_info(answer)
    assert (info.total, info.free) == (0x4C000, 0x4BC00)
    assert round(info.free_percent, 2) == 99.67


def test_set_dpi_xy():
    # 19:30:11: 04/05 03 0640 0640 0000 (slot 3, 1600 DPI)
    assert p.set_dpi_xy(1600, store=0x03).args == bytes.fromhex('03064006400000')


def test_get_button_mapping():
    request = p.get_button_mapping(0x05)
    assert request.command == (0x02, 0x8C)
    assert request.args[:3] == b'\x01\x05\x00' and request.size == 10
    # answer read from the device: live slot Button5 = Ctrl+T
    answer = p.Report(0x02, 0x8C, bytes.fromhex('01050002020117000000'),
                      status=p.Status.SUCCESS)
    mapping = p.parse_button_mapping(answer)
    assert mapping.action == p.KeyAction(keys.usage('KEY_T'), keys.Modifier.LEFT_CTRL)


def test_firmware_version():
    answer = p.Report(0x00, 0x81, bytes.fromhex('0232'), status=p.Status.SUCCESS)
    assert p.parse_firmware_version(answer) == '2.50'


def test_battery_and_charging():
    assert p.parse_battery_percent(p.Report.from_bytes(find('rsp', (0x07, 0x80), 0x05))) == 100
    assert p.parse_charging(p.Report.from_bytes(find('rsp', (0x07, 0x84), 0x04))) is False
    assert p.get_battery_level(transaction_id=0x05).to_bytes() == find('req', (0x07, 0x80), 0x05)


def test_device_mode():
    response = p.Report.from_bytes(find('rsp', (0x00, 0x84), 0x03))
    assert p.parse_device_mode(response) == p.DeviceMode.DRIVER
    assert p.get_device_mode(transaction_id=0x03).to_bytes() == find('req', (0x00, 0x84), 0x03)
    assert p.set_device_mode(p.DeviceMode.NORMAL).args[:2] == b'\x00\x00'


def test_response_matches_request():
    request = p.get_device_mode(transaction_id=0x03)
    response = p.Report.from_bytes(find('rsp', (0x00, 0x84), 0x03))
    assert response.matches(request)
    assert response.status == p.Status.SUCCESS


@pytest.mark.parametrize('bad', [0, 99, 30001])
def test_dpi_range(bad):
    with pytest.raises(p.ProtocolError):
        p.DpiStage(bad, 800)


def test_dpi_stage_count_and_active():
    with pytest.raises(p.ProtocolError):
        p.DpiStages((), active=1)
    with pytest.raises(p.ProtocolError):
        p.DpiStages((p.DpiStage(800, 800),), active=2)


def test_key_names():
    assert keys.usage('key_e') == 0x08
    assert keys.name(0x25) == 'KEY_8'
    with pytest.raises(ValueError):
        keys.usage('KEY_NOPE')


def test_active_profile_commands():
    assert p.set_active_profile(0x05).command == (0x05, 0x04)
    assert p.set_active_profile(0x05).args[:2] == b'\x05\x00'
    answer = p.Report(0x05, 0x84, bytes([0x01, 0x00]), status=p.Status.SUCCESS)
    assert p.parse_active_profile(answer) == p.STORE_LIVE
    listing = p.Report(0x05, 0x81, bytes.fromhex('050102030405'), status=p.Status.SUCCESS)
    assert p.parse_profile_list(listing) == [1, 2, 3, 4, 5]


def test_scroll_mode_action_round_trips():
    report = p.Report(0x02, 0x0C, bytes.fromhex('016a0012010100000000'))
    mapping = p.parse_button_mapping(report)
    assert mapping.button == p.ButtonId.SCROLL_MODE
    assert mapping.action == p.ScrollModeAction()
    assert p.set_button_mapping(mapping).args == report.args
