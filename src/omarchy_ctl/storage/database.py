"""Async SQLite storage backend with FTS5 and encryption."""

from __future__ import annotations

import aiosqlite
from pathlib import Path
from typing import Any

from omarchy_ctl.storage.crypto import CryptoService


SCHEMA = """
CREATE TABLE IF NOT EXISTS files (
    id TEXT PRIMARY KEY,
    path TEXT NOT NULL UNIQUE,
    filename TEXT NOT NULL,
    extension TEXT,
    mime_type TEXT,
    size_bytes INTEGER,
    created_at TEXT,
    modified_at TEXT,
    content_hash TEXT,
    content TEXT,
    scan_status TEXT DEFAULT 'pending',
    last_scanned TEXT
);
CREATE TABLE IF NOT EXISTS tags (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    category TEXT,
    confidence REAL DEFAULT 1.0,
    source TEXT DEFAULT 'auto',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS file_tags (
    file_id TEXT NOT NULL,
    tag_id TEXT NOT NULL,
    PRIMARY KEY (file_id, tag_id),
    FOREIGN KEY (file_id) REFERENCES files(id) ON DELETE CASCADE,
    FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS links (
    id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL,
    target_id TEXT NOT NULL,
    relation TEXT NOT NULL,
    metadata TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (source_id) REFERENCES files(id) ON DELETE CASCADE,
    FOREIGN KEY (target_id) REFERENCES files(id) ON DELETE CASCADE
);
CREATE VIRTUAL TABLE IF NOT EXISTS files_fts USING fts5(
    filename,
    extension,
    path,
    content
);
CREATE TRIGGER IF NOT EXISTS files_ai AFTER INSERT ON files BEGIN
    INSERT INTO files_fts(rowid, filename, extension, path, content)
    VALUES (new.rowid, new.filename, new.extension, new.path, COALESCE(new.content, ''));
END;
CREATE TRIGGER IF NOT EXISTS files_ad AFTER DELETE ON files BEGIN
    INSERT INTO files_fts(files_fts, rowid, filename, extension, path, content)
    VALUES ('delete', old.rowid, old.filename, old.extension, old.path, COALESCE(old.content, ''));
END;
"""


class StorageProtocol:
    async def init_db(self) -> None: ...
    async def get_connection(self) -> aiosqlite.Connection: ...
    def get_crypto(self) -> CryptoService: ...


class Database:
    def __init__(self, db_path: str | Path, crypto: CryptoService) -> None:
        self.db_path = Path(db_path).expanduser()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.crypto = crypto
        self._conn: aiosqlite.Connection | None = None

    async def init_db(self) -> None:
        self._conn = await aiosqlite.connect(self.db_path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.executescript(SCHEMA)
        await self._conn.commit()
        await self._migrate()

    async def _migrate(self) -> None:
        conn = await self.get_connection()
        cur = await conn.execute("PRAGMA table_info(files)")
        cols = await cur.fetchall()
        col_names = {r["name"] for r in cols}
        if "content" not in col_names:
            await conn.execute("ALTER TABLE files ADD COLUMN content TEXT")

        cur = await conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='files_fts'")
        if await cur.fetchone():
            cur = await conn.execute("PRAGMA table_info(files_fts)")
            cols = await cur.fetchall()
            col_names = {r["name"] for r in cols}
            if "content" not in col_names:
                await conn.execute("DROP TRIGGER IF EXISTS files_ai")
                await conn.execute("DROP TRIGGER IF EXISTS files_ad")
                await conn.execute("CREATE VIRTUAL TABLE files_fts_new USING fts5(filename, extension, path, content)")
                await conn.execute("INSERT INTO files_fts_new(rowid, filename, extension, path, content) SELECT rowid, filename, extension, path, '' FROM files_fts")
                await conn.execute("DROP TABLE files_fts")
                await conn.execute("ALTER TABLE files_fts_new RENAME TO files_fts")
                await conn.execute("""CREATE TRIGGER files_ai AFTER INSERT ON files BEGIN
                    INSERT INTO files_fts(rowid, filename, extension, path, content)
                    VALUES (new.rowid, new.filename, new.extension, new.path, COALESCE(new.content, ''));
                END""")
                await conn.execute("""CREATE TRIGGER files_ad AFTER DELETE ON files BEGIN
                    INSERT INTO files_fts(files_fts, rowid, filename, extension, path, content)
                    VALUES ('delete', old.rowid, old.filename, old.extension, old.path, COALESCE(old.content, ''));
                END""")
                await conn.commit()

    async def get_connection(self) -> aiosqlite.Connection:
        if self._conn is None:
            await self.init_db()
        return self._conn

    async def close(self) -> None:
        if self._conn:
            await self._conn.close()
            self._conn = None


_storage: Database | None = None


async def get_storage(db_path: str, crypto: CryptoService) -> Database:
    global _storage
    if _storage is None:
        _storage = Database(db_path, crypto)
        await _storage.init_db()
    return _storage


async def close_storage() -> None:
    """Close the cached storage connection so the process can exit cleanly."""
    global _storage
    if _storage is not None:
        await _storage.close()
        _storage = None
