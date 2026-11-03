# SPDX-License-Identifier: GPL-2.0-or-later
"""Command-line prototype: ``python -m basilisk_profiler.cli <command>``.

Quit Synapse first: it keeps the mouse in driver mode and overwrites anything written here.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .core import protocol as p
from .core.device import DeviceError, RazerDevice, find_devices
from .core.model import BUTTON_IDS, format_action, parse_action, parse_any_action
from .platform import conflicts


def format_stages(stages: p.DpiStages) -> str:
    parts = []
    for i, s in enumerate(stages.stages, 1):
        value = str(s.x) if s.x == s.y else f'{s.x}x{s.y}'
        parts.append(f'[{value}]' if i == stages.active else value)
    return ' '.join(parts)


def stages_to_json(stages: p.DpiStages) -> dict:
    return {'store': stages.store, 'active': stages.active,
            'stages': [[s.x, s.y] for s in stages.stages]}


def stages_from_json(data: dict) -> p.DpiStages:
    return p.DpiStages(tuple(p.DpiStage(x, y) for x, y in data['stages']),
                       active=data['active'], store=data.get('store', p.STORE_LIVE))


# --- commands -------------------------------------------------------------------

def cmd_list(args) -> None:
    for d in find_devices():
        print(f'{d.product_id:04X} if{d.interface} usage {d.usage_page:04X}/{d.usage:04X} '
              f'{d.product!r} {d.path!r}')


def cmd_info(dev: RazerDevice, args) -> None:
    mode = dev.device_mode()
    print(f'firmware:    {dev.firmware_version()}')
    print(f'device mode: {p.DeviceMode(mode).name if mode in (0, 3) else hex(mode)}')
    print(f'battery:     {dev.battery_percent()}%' + (' (charging)' if dev.charging() else ''))
    print(f'dpi stages:  {format_stages(dev.dpi_stages())}')


def cmd_dpi(dev: RazerDevice, args) -> None:
    if not args.values:
        print(format_stages(dev.dpi_stages(args.store)))
        return
    stages = tuple(p.DpiStage(v, v) for v in args.values)
    active = args.active or min(len(stages), dev.dpi_stages(args.store).active)
    dev.set_dpi_stages(p.DpiStages(stages, active=active, store=args.store))
    print(format_stages(dev.dpi_stages(args.store)))


def cmd_button(dev: RazerDevice, args) -> None:
    if args.action is None:
        mapping = dev.button(args.button, args.store)
        print(f'button 0x{args.button:02X} = {format_action(mapping.action)} '
              f'(slot 0x{args.store:02X})')
        return
    action = parse_action(args.action)
    dev.set_button(p.ButtonMapping(args.button, action, store=args.store))
    print(f'button 0x{args.button:02X} -> {format_action(action)} (slot 0x{args.store:02X})')


def cmd_mode(dev: RazerDevice, args) -> None:
    if args.mode:
        dev.set_device_mode(p.DeviceMode[args.mode.upper()])
    print(p.DeviceMode(dev.device_mode()).name)


def cmd_query(dev: RazerDevice, args) -> None:
    """Read-only probe: only query ids (bit 0x80) are allowed."""
    if not args.command_id & 0x80:
        raise SystemExit('query only sends read commands (command id with bit 0x80 set)')
    request = p.Report(args.command_class, args.command_id,
                       bytes.fromhex(args.args) + bytes(args.size - len(bytes.fromhex(args.args))))
    response = dev.transact(request)
    print(response.args[:response.size].hex(' '))


def _read_store(dev: RazerDevice, store: int, buttons: list[int]) -> dict:
    return {
        'dpi': stages_to_json(dev.dpi_stages(store)),
        'buttons': {f'0x{b:02X}': format_action(dev.button(b, store).action) for b in buttons},
    }


def cmd_backup(dev: RazerDevice, args) -> None:
    stores = [p.STORE_LIVE, *p.ONBOARD_STORES] if args.all else [p.STORE_LIVE]
    buttons = args.button or sorted(BUTTON_IDS.values())
    data = {
        'device_mode': dev.device_mode(),
        'slots': {f'0x{s:02X}': _read_store(dev, s, buttons) for s in stores},
    }
    Path(args.file).write_text(json.dumps(data, indent=2))
    print(f'saved {len(stores)} slot(s) x {len(buttons)} buttons to {args.file}')


def cmd_restore(dev: RazerDevice, args) -> None:
    data = json.loads(Path(args.file).read_text())
    slots = data.get('slots') or {'0x01': {'dpi': data['dpi'], 'buttons': data.get('buttons', {})}}
    for store_text, slot in slots.items():
        store = int(store_text, 16)
        stages = stages_from_json(slot['dpi'])
        dev.set_dpi_stages(p.DpiStages(stages.stages, active=stages.active, store=store))
        for button, action in slot.get('buttons', {}).items():
            dev.set_button(p.ButtonMapping(int(button, 16), parse_any_action(action), store=store))
    print(f'restored {len(slots)} slot(s) from {args.file}; '
          f'live dpi stages: {format_stages(dev.dpi_stages())}')


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog='basilisk-profiler', description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('list', help='list matching HID interfaces')
    sub.add_parser('info', help='device mode, battery, DPI stages')

    dpi = sub.add_parser('dpi', help='show or set DPI stages')
    dpi.add_argument('values', nargs='*', type=int, help='e.g. 400 800 1600 3200 6400')
    dpi.add_argument('--active', type=int, help='active stage, 1-based')
    dpi.add_argument('--store', type=lambda s: int(s, 0), default=p.STORE_LIVE)

    button = sub.add_parser('button', help='show or remap a button')
    button.add_argument('button', type=lambda s: int(s, 0), help='button id, e.g. 0x05')
    button.add_argument('action', nargs='?', help='mouse:5 | key:8 | ctrl+w | KEY_E')
    button.add_argument('--store', type=lambda s: int(s, 0), default=p.STORE_LIVE)

    mode = sub.add_parser('mode', help='show or set device mode')
    mode.add_argument('mode', nargs='?', choices=['normal', 'driver'])

    query = sub.add_parser('query', help='send a read-only command and print the answer')
    query.add_argument('command_class', type=lambda s: int(s, 16))
    query.add_argument('command_id', type=lambda s: int(s, 16))
    query.add_argument('args', nargs='?', default='', help='argument bytes as hex')
    query.add_argument('--size', type=int, default=p.ARGS_LEN)

    backup = sub.add_parser('backup', help='save DPI stages and button mappings')
    backup.add_argument('file')
    backup.add_argument('--all', action='store_true',
                        help='also the four onboard slots, not just the live one')
    backup.add_argument('--button', action='append', type=lambda s: int(s, 0),
                        default=[], help='only these button ids, e.g. 0x05 (repeatable)')

    restore = sub.add_parser('restore', help='write a backup back to the device')
    restore.add_argument('file')
    return parser


COMMANDS = {
    'info': cmd_info, 'dpi': cmd_dpi, 'button': cmd_button, 'mode': cmd_mode,
    'query': cmd_query, 'backup': cmd_backup, 'restore': cmd_restore,
}


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    for warning in conflicts():
        print(f'warning: {warning}', file=sys.stderr)
    try:
        if args.command == 'list':
            cmd_list(args)
            return 0
        with RazerDevice.open() as dev:
            COMMANDS[args.command](dev, args)
    except (DeviceError, ValueError, p.ProtocolError) as e:
        print(f'error: {e}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
