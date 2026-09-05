"""Main CTL application entry point."""

from __future__ import annotations

import asyncio
import signal
from pathlib import Path

from omarchy_ctl.ui.ipc import IPCService


async def main() -> None:
    service = IPCService()
    loop = asyncio.get_running_loop()
    stop = asyncio.Event()

    def _signal_handler():
        stop.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _signal_handler)
        except NotImplementedError:
            signal.signal(sig, lambda s, f: stop.set())

    await service.start()
    print(f"CTL IPC server running at {service.socket_path}")
    await stop.wait()
    await service.stop()
    print("CTL stopped.")


if __name__ == "__main__":
    asyncio.run(main())


def run() -> None:
    asyncio.run(main())
