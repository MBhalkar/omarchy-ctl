"""Search index module."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class SearchQuery:
    text: str | None = None
    tags: list[str] | None = None
    relations: list[str] | None = None
    limit: int = 50
    offset: int = 0


@dataclass(frozen=True)
class SearchResult:
    files: list[dict]
    total: int
    query: SearchQuery


class SearchIndexProtocol(Protocol):
    async def query(self, query: SearchQuery) -> SearchResult: ...
    async def index_file(self, file_id: str) -> None: ...
    async def remove_file(self, file_id: str) -> None: ...
    async def rebuild(self) -> None: ...


class SearchIndex:
    def __init__(self, db) -> None:
        self.db = db

    async def query(self, query: SearchQuery) -> SearchResult:
        conn = await self.db.get_connection()
        params: list = []
        results: list[dict] = []

        if query.text and query.tags:
            text_params = [query.text]
            tag_params = list(query.tags)
            text_sql = "SELECT f.* FROM files f JOIN files_fts ON files_fts.rowid = f.rowid WHERE files_fts MATCH ?"
            tag_sql = "SELECT f.* FROM files f JOIN file_tags ft ON f.id = ft.file_id JOIN tags t ON ft.tag_id = t.id WHERE t.name IN (" + ",".join("?" * len(query.tags)) + ")"
            sql = f"SELECT * FROM ({text_sql} UNION {tag_sql}) GROUP BY id ORDER BY modified_at DESC LIMIT ? OFFSET ?"
            params = text_params + tag_params + [query.limit, query.offset]
            cur = await conn.execute(sql, params)
            results = [dict(r) for r in await cur.fetchall()]
            count_sql = f"SELECT COUNT(DISTINCT id) FROM ({text_sql} UNION {tag_sql})"
            cur = await conn.execute(count_sql, text_params + tag_params)
        elif query.text:
            sql = "SELECT f.* FROM files f JOIN files_fts ON files_fts.rowid = f.rowid WHERE files_fts MATCH ? ORDER BY f.modified_at DESC LIMIT ? OFFSET ?"
            params = [query.text, query.limit, query.offset]
            cur = await conn.execute(sql, params)
            results = [dict(r) for r in await cur.fetchall()]
            cur = await conn.execute("SELECT COUNT(*) FROM files f JOIN files_fts ON files_fts.rowid = f.rowid WHERE files_fts MATCH ?", (query.text,))
        elif query.tags:
            sql = "SELECT f.* FROM files f JOIN file_tags ft ON f.id = ft.file_id JOIN tags t ON ft.tag_id = t.id WHERE t.name IN (" + ",".join("?" * len(query.tags)) + ") GROUP BY f.id ORDER BY f.modified_at DESC LIMIT ? OFFSET ?"
            params = list(query.tags) + [query.limit, query.offset]
            cur = await conn.execute(sql, params)
            results = [dict(r) for r in await cur.fetchall()]
            count_sql = "SELECT COUNT(DISTINCT f.id) FROM files f JOIN file_tags ft ON f.id = ft.file_id JOIN tags t ON ft.tag_id = t.id WHERE t.name IN (" + ",".join("?" * len(query.tags)) + ")"
            cur = await conn.execute(count_sql, query.tags)
        else:
            sql = "SELECT * FROM files ORDER BY modified_at DESC LIMIT ? OFFSET ?"
            params = [query.limit, query.offset]
            cur = await conn.execute(sql, params)
            results = [dict(r) for r in await cur.fetchall()]
            cur = await conn.execute("SELECT COUNT(*) FROM files")

        total_row = await cur.fetchone()
        total = total_row[0] if total_row else 0
        return SearchResult(files=results, total=total, query=query)

    async def index_file(self, file_id: str) -> None:
        conn = await self.db.get_connection()
        await conn.execute("INSERT OR IGNORE INTO files_fts(rowid, filename, extension, path, content) SELECT rowid, filename, extension, path, COALESCE(content, '') FROM files WHERE id = ?", (file_id,))
        await conn.commit()

    async def remove_file(self, file_id: str) -> None:
        conn = await self.db.get_connection()
        await conn.execute("DELETE FROM files_fts WHERE rowid = (SELECT rowid FROM files WHERE id = ?)", (file_id,))
        await conn.commit()

    async def rebuild(self) -> None:
        conn = await self.db.get_connection()
        await conn.execute("INSERT OR REPLACE INTO files_fts(rowid, filename, extension, path, content) SELECT rowid, filename, extension, path, COALESCE(content, '') FROM files")
        await conn.commit()
