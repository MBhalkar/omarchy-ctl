"""Quickshell widget placeholder for Omarchy shell integration."""

from __future__ import annotations

from pathlib import Path


class QuickshellWidget:
    def __init__(self) -> None:
        self.plugin_dir = Path("~/.config/omarchy/plugins/mbhalkar.ctl").expanduser()

    def install(self) -> None:
        self.plugin_dir.mkdir(parents=True, exist_ok=True)
        metadata = self.plugin_dir / "metadata.json"
        metadata.write_text('{"id": "mbhalkar.ctl", "name": "CTL", "version": "0.1.0"}')
        main = self.plugin_dir / "main.qml"
        main.write_text(
            """
import QtQuick 2.15
import QtQuick.Controls 2.15
import omarchy.extra 1.0

Item {
    width: 40
    height: 20
    Text {
        text: "CTL"
        color: "white"
    }
}
"""
        )
