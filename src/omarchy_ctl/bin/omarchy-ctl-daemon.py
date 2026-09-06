"""Legacy daemon entry point.

The canonical, importable module is ``omarchy_ctl.bin.omarchy_ctl_daemon``
(underscores). This hyphenated file is kept only so the file can be executed
directly (``python omarchy-ctl-daemon.py``); it is not importable by Python
because filenames cannot contain hyphens.
"""

from __future__ import annotations

from omarchy_ctl.bin.omarchy_ctl_daemon import main, run

__all__ = ["main", "run"]

if __name__ == "__main__":
    run()
