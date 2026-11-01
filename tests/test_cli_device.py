# SPDX-License-Identifier: GPL-2.0-or-later
import json

import pytest

from basilisk_profiler import cli
from basilisk_profiler.core import keys
from basilisk_profiler.core import protocol as p
from basilisk_profiler.core.device import DeviceError, RazerDevice, find_devices


class FakeHandle:
    """Answers each feature report like the device: echo with a status byte."""

    def __init__(self, busy=0, status=p.Status.SUCCESS, answer=None):
        self.sent = []
        self.busy = busy
        self.status = status
        self.answer = answer
        self.closed = False

    def send_feature_report(self, data):
        self.sent.append(bytes(data))
        return len(data)

    def get_feature_report(self, report_id, length):
        request = p.Report.from_bytes(self.sent[-1][1:])
        if self.busy:
            self.busy -= 1
            status = p.Status.BUSY
        else:
            status = self.status
        args = self.answer if self.answer is not None else request.args
        response = p.Report(request.command_class, request.command_id, args,
                            data_size=request.size, transaction_id=request.transaction_id,
                            status=status)
        return [report_id, *response.to_bytes()]

    def close(self):
        self.closed = True


def device(**kw):
    return RazerDevice(FakeHandle(**kw), sleep=lambda _: None)


def test_transact_sends_report_id_and_frame():
    dev = device()
    response = dev.transact(p.get_device_mode())
    sent = dev.handle.sent[0]
    assert sent[0] == 0x00 and len(sent) == p.REPORT_LEN + 1
    assert response.status == p.Status.SUCCESS


def test_transact_retries_while_busy():
    dev = device(busy=3)
    dev.transact(p.get_battery_level())
    assert len(dev.handle.sent) == 1


def test_transact_reports_failure():
    with pytest.raises(DeviceError, match='NOT_SUPPORTED'):
        device(status=p.Status.NOT_SUPPORTED).transact(p.get_device_mode())


def test_transact_gives_up_when_always_busy():
    with pytest.raises(DeviceError, match='busy'):
        device(busy=100).transact(p.get_device_mode())


def test_dpi_round_trip_through_fake():
    stages = p.DpiStages((p.DpiStage(800, 800), p.DpiStage(1600, 1600)), active=1)
    dev = device()
    dev.set_dpi_stages(stages)
    assert dev.handle.sent[0][1:] == p.set_dpi_stages(stages).to_bytes()


def test_find_devices_prefers_dock_mouse_collection():
    def entry(pid, interface, path, page=1, usage=2):
        return {'product_id': pid, 'interface_number': interface, 'path': path,
                'usage_page': page, 'usage': usage}

    entries = [
        entry(0x00AA, 0, b'wired'),
        entry(0x00A4, 0, b'cc', page=0x0C, usage=1),
        entry(0x00A4, 0, b'mouse'),
        entry(0x00A4, 1, b'kbd', usage=6),
        entry(0x0099, 0, b'other'),
    ]
    paths = [d.path for d in find_devices(lambda vid, pid: entries)]
    assert paths == [b'mouse', b'cc', b'wired']


@pytest.mark.parametrize('text,expected', [
    ('mouse:5', p.MouseButtonAction(5)),
    ('key:8', p.KeyAction(keys.usage('KEY_8'))),
    ('KEY_E', p.KeyAction(keys.usage('KEY_E'))),
    ('ctrl+w', p.KeyAction(keys.usage('KEY_W'), keys.Modifier.LEFT_CTRL)),
    ('Ctrl+Shift+T', p.KeyAction(keys.usage('KEY_T'),
                                 keys.Modifier.LEFT_CTRL | keys.Modifier.LEFT_SHIFT)),
])
def test_parse_action(text, expected):
    assert cli.parse_action(text) == expected


def test_format_action_round_trips():
    for text in ('mouse:5', 'ctrl+w', 'f5', 'ctrl+shift+t'):
        assert cli.format_action(cli.parse_action(text)) == text


def test_parse_action_rejects_unknown():
    with pytest.raises(ValueError):
        cli.parse_action('hyper+w')
    with pytest.raises(ValueError):
        cli.parse_action('KEY_NOPE')


def test_format_stages_marks_active():
    stages = p.DpiStages((p.DpiStage(400, 400), p.DpiStage(800, 800)), active=2)
    assert cli.format_stages(stages) == '400 [800]'


def test_stages_json_round_trip():
    stages = p.DpiStages((p.DpiStage(400, 400), p.DpiStage(1600, 1200)), active=2)
    assert cli.stages_from_json(cli.stages_to_json(stages)) == stages


def test_backup_restore(tmp_path):
    stages = p.DpiStages(tuple(p.DpiStage(v, v) for v in (400, 1600, 1800)), active=3)
    dev = device(answer=p.set_dpi_stages(stages).args.ljust(p.ARGS_LEN, b'\x00'))
    backup = tmp_path / 'backup.json'
    cli.cmd_backup(dev, cli.build_parser().parse_args(['backup', str(backup)]))
    dev.handle.sent.clear()
    data = json.loads(backup.read_text())
    data['buttons'] = {'0x05': 'mouse:5'}
    backup.write_text(json.dumps(data))
    cli.cmd_restore(dev, cli.build_parser().parse_args(['restore', str(backup)]))
    commands = [p.Report.from_bytes(s[1:]).command for s in dev.handle.sent]
    assert commands == [(0x04, 0x06), (0x02, 0x0C), (0x04, 0x86)]
    assert dev.handle.sent[0][1:] == p.set_dpi_stages(stages).to_bytes()
