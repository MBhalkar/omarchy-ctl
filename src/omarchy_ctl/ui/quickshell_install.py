"""Quickshell widget installer for Omarchy shell integration."""

from __future__ import annotations

import shutil
from pathlib import Path


class QuickshellWidget:
    def __init__(self) -> None:
        self.plugin_dir = Path("~/.config/omarchy/plugins/mbhalkar.ctl").expanduser()
        self.source_dir = Path(__file__).parent / "quickshell"

    def install(self) -> None:
        self.plugin_dir.mkdir(parents=True, exist_ok=True)

        files = [
            "manifest.json",
            "BarWidget.qml",
            "Panel.qml",
            "CtlModel.js",
        ]

        for name in files:
            src = self.source_dir / name
            dst = self.plugin_dir / name
            if src.exists():
                shutil.copy2(src, dst)
