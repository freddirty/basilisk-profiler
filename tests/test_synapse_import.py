# SPDX-License-Identifier: GPL-2.0-or-later
import json

from basilisk_profiler.core import keys
from basilisk_profiler.core import protocol as p
from basilisk_profiler.core import synapse_import as si


def payload(name, guid, mappings, active=3, enable=True):
    body = {
        'guid': guid, 'name': name, 'dpi': {'x': 1600, 'y': 1600}, 'mappings': mappings,
        'dpiStages': {'stages': [{'x': v, 'y': v} for v in (400, 800, 1600, 3200, 6400)],
                      'active': active, 'enable': enable, 'count': 5},
    }
    outer = {'payload': json.dumps(body), '@context': 'http://remotestorage.io/spec/modules/x/profile'}
    return json.dumps(outer, separators=(',', ':')).encode()


def kb(input_type, input_id, key, mods=(), hypershift=False):
    return {'outputType': 'keyboardGroup', 'isHyperShift': hypershift, 'inputType': input_type,
            'inputID': input_id, 'keyboardGroup': {'keyGroup': 0, 'key': key,
                                                   'modifiers': list(mods)}}


def write_db(tmp_path, *chunks):
    db = tmp_path / 'db'
    db.mkdir()
    (db / '000001.log').write_bytes(b'\x00junk'.join(chunks))
    return db


def test_reads_profiles_and_mappings(tmp_path):
    db = write_db(tmp_path, payload('Browser', 'g1', [
        kb('MouseInput', 'Button5', 'KEY_T', ['KEY_LEFT_CTRL']),
        kb('DKMInput', 'DKM_SB_02', 'KEY_W', ['KEY_LEFT_CTRL']),
        kb('MouseInput', 'Button4', 'KEY_R', hypershift=True),
        kb('MouseInput', 'RepeatScrollLeft', 'KEY_A'),
    ]))
    (imported,) = si.read_profiles(db)
    prof = imported.profile
    assert prof.name == 'Browser'
    assert prof.buttons == {
        0x05: p.KeyAction(keys.usage('KEY_T'), keys.Modifier.LEFT_CTRL),
        0x0F: p.KeyAction(keys.usage('KEY_W'), keys.Modifier.LEFT_CTRL),
    }
    assert prof.dpi_stages == (400, 800, 1600, 3200, 6400) and prof.dpi_active == 3
    assert len(imported.skipped) == 2


def test_later_copy_wins_and_sorted(tmp_path):
    db = write_db(tmp_path,
                  payload('old name', 'g1', []),
                  payload('Zeta', 'g2', []),
                  payload('alpha', 'g1', [kb('MouseInput', 'Button5', 'KEY_8')]))
    names = [i.profile.name for i in si.read_profiles(db)]
    assert names == ['alpha', 'Zeta']


def test_disabled_stages_and_unknown_key(tmp_path):
    db = write_db(tmp_path, payload('x', 'g', [kb('MouseInput', 'Button5', 'KEY_WEIRD')],
                                    enable=False))
    (imported,) = si.read_profiles(db)
    assert imported.profile.dpi_stages is None
    assert imported.profile.buttons == {}
    assert 'KEY_WEIRD' in imported.skipped[0]


def test_ignores_macros_and_garbage(tmp_path):
    macro = json.dumps({'payload': json.dumps({'name': 'Macro 1', 'guid': 'm'})}).encode()
    db = write_db(tmp_path, b'{"payload":"broken', macro)
    assert si.read_profiles(db) == []
