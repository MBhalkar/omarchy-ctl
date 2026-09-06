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
            tag_params = [f"%{t}%" for t in query.tags]
            tag_clauses = " OR ".join(["t.name LIKE ?"] * len(query.tags))
            tag_sql = "SELECT f.* FROM files f JOIN file_tags ft ON f.id = ft.file_id JOIN tags t ON ft.tag_id = t.id WHERE " + tag_clauses

            tag_check = await conn.execute("SELECT 1 FROM tags WHERE name = ? LIMIT 1", (query.text,))
            is_exact_tag = (await tag_check.fetchone()) is not None

            if is_exact_tag:
                sql = f"SELECT f.* FROM files f JOIN file_tags ft ON f.id = ft.file_id JOIN tags t ON ft.tag_id = t.id WHERE t.name = ? GROUP BY f.id ORDER BY f.modified_at DESC LIMIT ? OFFSET ?"
                params = [query.text, query.limit, query.offset]
                cur = await conn.execute(sql, params)
                results = [dict(r) for r in await cur.fetchall()]
                cur = await conn.execute("SELECT COUNT(DISTINCT f.id) FROM files f JOIN file_tags ft ON f.id = ft.file_id JOIN tags t ON ft.tag_id = t.id WHERE t.name = ?", (query.text,))
            else:
                text_params = [query.text]
                text_sql = "SELECT f.* FROM files f JOIN files_fts ON files_fts.rowid = f.rowid WHERE files_fts MATCH ?"
                sql = f"SELECT * FROM ({text_sql} UNION {tag_sql}) GROUP BY id ORDER BY modified_at DESC LIMIT ? OFFSET ?"
                params = text_params + tag_params + [query.limit, query.offset]
                cur = await conn.execute(sql, params)
                results = [dict(r) for r in await cur.fetchall()]
                count_sql = f"SELECT COUNT(DISTINCT id) FROM ({text_sql} UNION {tag_sql})"
                cur = await conn.execute(count_sql, text_params + tag_params)
        elif query.text:
            tag_check = await conn.execute("SELECT 1 FROM tags WHERE name = ? LIMIT 1", (query.text,))
            is_exact_tag = (await tag_check.fetchone()) is not None
            if is_exact_tag:
                sql = "SELECT f.* FROM files f JOIN file_tags ft ON f.id = ft.file_id JOIN tags t ON ft.tag_id = t.id WHERE t.name = ? ORDER BY f.modified_at DESC LIMIT ? OFFSET ?"
                params = [query.text, query.limit, query.offset]
                cur = await conn.execute(sql, params)
                results = [dict(r) for r in await cur.fetchall()]
                cur = await conn.execute("SELECT COUNT(DISTINCT f.id) FROM files f JOIN file_tags ft ON f.id = ft.file_id JOIN tags t ON ft.tag_id = t.id WHERE t.name = ?", (query.text,))
            else:
                try:
                    sql = "SELECT f.* FROM files f JOIN files_fts ON files_fts.rowid = f.rowid WHERE files_fts MATCH ? ORDER BY f.modified_at DESC LIMIT ? OFFSET ?"
                    params = [query.text, query.limit, query.offset]
                    cur = await conn.execute(sql, params)
                    results = [dict(r) for r in await cur.fetchall()]
                    cur = await conn.execute("SELECT COUNT(*) FROM files f JOIN files_fts ON files_fts.rowid = f.rowid WHERE files_fts MATCH ?", (query.text,))
                except Exception:
                    tag_clauses = "t.name LIKE ?"
                    tag_params = [f"%{query.text}%"]
                    sql = f"SELECT f.* FROM files f JOIN file_tags ft ON f.id = ft.file_id JOIN tags t ON ft.tag_id = t.id WHERE {tag_clauses} ORDER BY f.modified_at DESC LIMIT ? OFFSET ?"
                    params = tag_params + [query.limit, query.offset]
                    cur = await conn.execute(sql, params)
                    results = [dict(r) for r in await cur.fetchall()]
                    cur = await conn.execute(f"SELECT COUNT(DISTINCT f.id) FROM files f JOIN file_tags ft ON f.id = ft.file_id JOIN tags t ON ft.tag_id = t.id WHERE {tag_clauses}", tag_params)
        elif query.tags:
            tag_clauses = " OR ".join(["t.name LIKE ?"] * len(query.tags))
            tag_params = [f"%{t}%" for t in query.tags]
            sql = f"SELECT f.* FROM files f JOIN file_tags ft ON f.id = ft.file_id JOIN tags t ON ft.tag_id = t.id WHERE {tag_clauses} GROUP BY f.id ORDER BY f.modified_at DESC LIMIT ? OFFSET ?"
            params = tag_params + [query.limit, query.offset]
            cur = await conn.execute(sql, params)
            results = [dict(r) for r in await cur.fetchall()]
            count_sql = f"SELECT COUNT(DISTINCT f.id) FROM files f JOIN file_tags ft ON f.id = ft.file_id JOIN tags t ON ft.tag_id = t.id WHERE {tag_clauses}"
            cur = await conn.execute(count_sql, tag_params)
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
