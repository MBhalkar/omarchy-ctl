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
        sql = "SELECT f.* FROM files f"
        params: list = []
        joins: list[str] = []
        where: list[str] = []

        if query.tags:
            joins.append("JOIN file_tags ft ON f.id = ft.file_id")
            joins.append("JOIN tags t ON ft.tag_id = t.id")
            placeholders = ",".join("?" * len(query.tags))
            where.append(f"t.name IN ({placeholders})")
            params.extend(query.tags)

        if query.text:
            where.append("files_fts MATCH ?")
            params.append(query.text)

        sql += " " + " ".join(joins)
        if where:
            sql += " WHERE " + " AND ".join(where)

        count_sql = f"SELECT COUNT(*) FROM ({sql})"
        cur = await conn.execute(count_sql, params)
        total_row = await cur.fetchone()
        total = total_row[0] if total_row else 0

        sql += " ORDER BY f.modified_at DESC LIMIT ? OFFSET ?"
        params.extend([query.limit, query.offset])
        cur = await conn.execute(sql, params)
        rows = await cur.fetchall()
        files = [dict(r) for r in rows]
        return SearchResult(files=files, total=total, query=query)

    async def index_file(self, file_id: str) -> None:
        conn = await self.db.get_connection()
        await conn.execute("INSERT OR IGNORE INTO files_fts(rowid, filename, extension, path) SELECT rowid, filename, extension, path FROM files WHERE id = ?", (file_id,))
        await conn.commit()

    async def remove_file(self, file_id: str) -> None:
        conn = await self.db.get_connection()
        await conn.execute("DELETE FROM files_fts WHERE rowid = (SELECT rowid FROM files WHERE id = ?)", (file_id,))
        await conn.commit()

    async def rebuild(self) -> None:
        conn = await self.db.get_connection()
        await conn.execute("INSERT INTO files_fts(rowid, filename, extension, path) SELECT rowid, filename, extension, path FROM files")
        await conn.commit()
