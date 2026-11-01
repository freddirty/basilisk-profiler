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


def test_unknown_action_round_trips():
    report = p.Report.from_bytes(find('req', (0x02, 0x0C), 0x00))
    mapping = p.parse_button_mapping(report)
    assert isinstance(mapping.action, p.RawAction)
    assert p.set_button_mapping(mapping, transaction_id=0x00).to_bytes() == report.to_bytes()


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
