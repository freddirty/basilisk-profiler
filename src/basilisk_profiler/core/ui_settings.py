# SPDX-License-Identifier: GPL-2.0-or-later
"""Small per-user preferences of the tray and the settings window (not part of the profiles).

Stored as ``tray.json`` next to config.toml: the DPI pop-up, the dock effect, the language.
"""
from __future__ import annotations

import json
from pathlib import Path


def ui_settings_path(config_path: Path) -> Path:
    return config_path.with_name('tray.json')


class UiSettings:
    def __init__(self, path: Path):
        self.path = path
        try:
            self.data = json.loads(path.read_text())
        except (OSError, ValueError):
            self.data = {}
        if not isinstance(self.data, dict):
            self.data = {}

    def get(self, key: str, default):
        return self.data.get(key, default)

    def set(self, key: str, value) -> None:
        self.data[key] = value
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(self.data, indent=2))
        except OSError:
            pass
