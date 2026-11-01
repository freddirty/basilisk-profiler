# SPDX-License-Identifier: GPL-2.0-or-later
"""Import Basilisk V3 Pro profiles from Synapse 4's local IndexedDB.

Synapse keeps profiles as remoteStorage JSON documents inside Chromium's IndexedDB
(LevelDB). Values are scanned for ``{"payload": "<profile json>", ...}`` objects in both the
compressed tables (.ldb) and the write-ahead log (.log); later copies of a profile win.
Only what this project models is imported: DPI stages and keyboard mappings of the side
buttons. Hypershift mappings are skipped.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from . import keys
from . import protocol as p
from .leveldb import table_entries
from .model import Profile

# Synapse input ids -> device button ids
INPUT_BUTTONS = {
    ('MouseInput', 'Button4'): 0x04,
    ('MouseInput', 'Button5'): 0x05,
    ('DKMInput', 'DKM_SB_02'): 0x0F,
}
SYNAPSE_MODIFIERS = {
    'KEY_LEFT_CTRL': keys.Modifier.LEFT_CTRL, 'KEY_LEFT_SHIFT': keys.Modifier.LEFT_SHIFT,
    'KEY_LEFT_ALT': keys.Modifier.LEFT_ALT, 'KEY_LEFT_WIN': keys.Modifier.LEFT_GUI,
    'KEY_RIGHT_CTRL': keys.Modifier.RIGHT_CTRL, 'KEY_RIGHT_SHIFT': keys.Modifier.RIGHT_SHIFT,
    'KEY_RIGHT_ALT': keys.Modifier.RIGHT_ALT, 'KEY_RIGHT_WIN': keys.Modifier.RIGHT_GUI,
}


@dataclass
class ImportedProfile:
    guid: str
    profile: Profile
    skipped: list[str] = field(default_factory=list)


def default_db_dir() -> Path | None:
    if sys.platform != 'win32':
        return None
    return (Path(os.environ.get('LOCALAPPDATA', '')) / 'Razer' / 'RazerAppEngine' / 'User Data'
            / 'Default' / 'IndexedDB' / 'https_apps.razer.com_0.indexeddb.leveldb')


def _blobs(db_dir: Path) -> list[bytes]:
    """Copy the database first: Synapse may hold it open and compact it meanwhile."""
    blobs = []
    with tempfile.TemporaryDirectory() as tmp:
        for f in sorted(db_dir.iterdir()):
            if f.suffix not in ('.ldb', '.log'):
                continue
            copy = Path(tmp) / f.name
            try:
                shutil.copyfile(f, copy)
            except OSError:
                continue
            data = copy.read_bytes()
            if f.suffix == '.ldb':
                try:
                    blobs += [value for _, value in table_entries(data)]
                except (IndexError, ValueError):
                    blobs.append(data)
            else:
                blobs.append(data)
    return blobs


def iter_payloads(blobs: list[bytes]):
    decoder = json.JSONDecoder()
    for blob in blobs:
        text = blob.decode('latin-1')
        pos = 0
        while (pos := text.find('{"payload":"', pos)) >= 0:
            try:
                outer, end = decoder.raw_decode(text, pos)
                payload = json.loads(outer['payload'])
            except (ValueError, KeyError, TypeError):
                pos += 1
                continue
            pos = end
            if isinstance(payload, dict):
                yield payload


def convert(payload: dict) -> ImportedProfile:
    skipped = []
    buttons: dict[int, p.Action] = {}
    for m in payload.get('mappings', []):
        where = f"{m.get('inputType')}/{m.get('inputID')}"
        if m.get('isHyperShift'):
            skipped.append(f'{where}: Hypershift')
            continue
        button = INPUT_BUTTONS.get((m.get('inputType'), m.get('inputID')))
        if button is None:
            skipped.append(f'{where}: unsupported button')
            continue
        if m.get('outputType') != 'keyboardGroup':
            skipped.append(f"{where}: unsupported output {m.get('outputType')}")
            continue
        group = m.get('keyboardGroup', {})
        try:
            usage = keys.usage(group.get('key', ''))
            modifiers = 0
            for mod in group.get('modifiers', []):
                modifiers |= SYNAPSE_MODIFIERS[mod]
        except (ValueError, KeyError) as e:
            skipped.append(f'{where}: {e}')
            continue
        buttons[button] = p.KeyAction(usage, modifiers)

    dpi_stages = dpi_active = None
    stages = payload.get('dpiStages') or {}
    if stages.get('enable') and stages.get('stages'):
        values = [s['x'] for s in stages['stages'][:p.MAX_DPI_STAGES]]
        if all(p.DPI_MIN <= v <= p.DPI_MAX for v in values):
            dpi_stages = tuple(values)
            dpi_active = min(max(int(stages.get('active', 1)), 1), len(values))
    profile = Profile(name=str(payload.get('name') or payload['guid']), dpi_stages=dpi_stages,
                      dpi_active=dpi_active, buttons=buttons)
    return ImportedProfile(payload['guid'], profile, skipped)


def read_profiles(db_dir: Path | None = None) -> list[ImportedProfile]:
    db_dir = db_dir or default_db_dir()
    if db_dir is None or not db_dir.is_dir():
        raise FileNotFoundError(f'Synapse database not found: {db_dir}')
    found: dict[str, ImportedProfile] = {}
    for payload in iter_payloads(_blobs(db_dir)):
        if 'guid' in payload and 'mappings' in payload and 'dpiStages' in payload:
            found[payload['guid']] = convert(payload)  # later copies overwrite older ones
    return sorted(found.values(), key=lambda i: i.profile.name.lower())
