"""IPC REST service for UI integration."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from aiohttp import web
from aiohttp.web import Request, Response

from ctl.core.context import ContextEngine
from ctl.core.links import LinkManager
from ctl.core.scanner import Scanner
from ctl.core.search import SearchIndex, SearchQuery
from ctl.core.tags import TagManager
from ctl.storage.crypto import CryptoService
from ctl.storage.database import get_storage


class IPCService:
    def __init__(self, socket_path: str = "~/.local/share/ctl/ctl.sock") -> None:
        self.socket_path = Path(socket_path).expanduser()
        self.socket_path.parent.mkdir(parents=True, exist_ok=True)
        self.app = web.Application()
        self._setup_routes()
        self.runner: web.AppRunner | None = None

    def _setup_routes(self) -> None:
        self.app.router.add_get("/status", self.handle_status)
        self.app.router.add_post("/scan", self.handle_scan)
        self.app.router.add_get("/tags", self.handle_tags)
        self.app.router.add_post("/links", self.handle_create_link)
        self.app.router.add_get("/search", self.handle_search)

    async def _get_services(self):
        crypto = CryptoService(Path("~/.config/ctl/encryption.key").expanduser())
        crypto.load("default")
        db = await get_storage("~/.local/share/ctl/ctl.db", crypto)
        return {
            "scanner": Scanner(),
            "engine": ContextEngine(),
            "tags": TagManager(db),
            "links": LinkManager(db),
            "search": SearchIndex(db),
        }

    async def handle_status(self, request: Request) -> Response:
        return web.json_response({"status": "ok"})

    async def handle_scan(self, request: Request) -> Response:
        data = await request.json()
        paths = data.get("paths", [])
        svc = await self._get_services()
        results = await svc["engine"].batch_analyze(await svc["scanner"].scan_path(paths[0]) if paths else [])
        return web.json_response({"scanned": len(results)})

    async def handle_tags(self, request: Request) -> Response:
        svc = await self._get_services()
        tags = await svc["tags"].list()
        return web.json_response([{"name": t.name, "category": t.category, "source": t.source} for t in tags])

    async def handle_create_link(self, request: Request) -> Response:
        data = await request.json()
        svc = await self._get_services()
        link = await svc["links"].create(data["source"], data["target"], data.get("relation", "related_to"))
        return web.json_response({"id": link.id, "relation": link.relation})

    async def handle_search(self, request: Request) -> Response:
        q = request.query.get("q", "")
        svc = await self._get_services()
        result = await svc["search"].query(SearchQuery(text=q))
        return web.json_response({"files": result.files, "total": result.total})

    async def start(self) -> None:
        if self.socket_path.exists():
            self.socket_path.unlink()
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        site = web.UnixSite(self.runner, str(self.socket_path))
        await site.start()

    async def stop(self) -> None:
        if self.runner:
            await self.runner.cleanup()


def run_ipc() -> None:
    service = IPCService()
    try:
        asyncio.run(service.start())
        asyncio.get_event_loop().run_forever()
    except KeyboardInterrupt:
        asyncio.run(service.stop())
