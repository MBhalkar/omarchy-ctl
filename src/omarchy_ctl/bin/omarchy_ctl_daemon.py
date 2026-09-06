"""Main CTL application entry point (importable module)."""

from __future__ import annotations

import asyncio
import signal
from pathlib import Path

from omarchy_ctl.logging import get_logger, setup_logging
from omarchy_ctl.ui.ipc import IPCService

log = get_logger("omarchy-ctl.daemon")

setup_logging()


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
    log.info("daemon_started", socket=str(service.socket_path))
    print(f"CTL IPC server running at {service.socket_path}")
    await stop.wait()
    await service.stop()
    log.info("daemon_stopped")
    print("CTL stopped.")


def run() -> None:
    asyncio.run(main())


if __name__ == "__main__":
    run()
