"""File scanner module."""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, Awaitable

import aiofiles
import magic
from watchfiles import awatch, Change


@dataclass(frozen=True)
class FileRef:
    path: Path
    filename: str
    extension: str | None
    mime_type: str | None
    size_bytes: int
    created_at: str
    modified_at: str
    content_hash: str
    scan_status: str = "pending"
    last_scanned: str | None = None


@dataclass(frozen=True)
class FileEvent:
    change: str
    file: FileRef


EventCallback = Callable[[FileEvent], Awaitable[None]]


class Scanner:
    def __init__(self, max_file_size_mb: int = 50, batch_size: int = 100) -> None:
        self.max_file_size = max_file_size_mb * 1024 * 1024
        self.batch_size = batch_size
        self._callbacks: list[EventCallback] = []

    def register_callback(self, cb: EventCallback) -> None:
        self._callbacks.append(cb)

    async def _emit(self, event: FileEvent) -> None:
        for cb in self._callbacks:
            await cb(event)

    def _file_hash(self, path: Path) -> str:
        h = hashlib.sha256()
        h.update(str(path).encode())
        h.update(str(path.stat().st_mtime_ns).encode())
        return h.hexdigest()[:16]

    async def _analyze_file(self, path: Path) -> FileRef | None:
        try:
            stat = path.stat()
            if stat.st_size > self.max_file_size:
                return None
            mime = magic.from_file(str(path), mime=True)
            ext = path.suffix.lower().lstrip(".") or None
            created = datetime.fromtimestamp(stat.st_ctime).isoformat()
            modified = datetime.fromtimestamp(stat.st_mtime).isoformat()
            return FileRef(
                path=path,
                filename=path.name,
                extension=ext,
                mime_type=mime,
                size_bytes=stat.st_size,
                created_at=created,
                modified_at=modified,
                content_hash=self._file_hash(path),
            )
        except (OSError, PermissionError):
            return None

    async def scan_path(self, path: str | Path, recursive: bool = True) -> list[FileRef]:
        root = Path(path).expanduser().resolve()
        results: list[FileRef] = []
        if root.is_file():
            f = await self._analyze_file(root)
            if f:
                results.append(f)
            return results
        if recursive:
            for p in root.rglob("*"):
                if p.is_file():
                    f = await self._analyze_file(p)
                    if f:
                        results.append(f)
        else:
            for p in root.iterdir():
                if p.is_file():
                    f = await self._analyze_file(p)
                    if f:
                        results.append(f)
        return results

    async def watch(self, paths: list[str | Path]) -> None:
        expanded = [str(Path(p).expanduser().resolve()) for p in paths]
        async for changes in awatch(*expanded, watch_filter=lambda c, p: True):
            for change_type, changed_path in changes:
                p = Path(changed_path)
                if not p.is_file():
                    continue
                f = await self._analyze_file(p)
                if not f:
                    continue
                change_str = {Change.added: "add", Change.modified: "modify", Change.deleted: "delete"}.get(change_type, "unknown")
                await self._emit(FileEvent(change=change_str, file=f))
