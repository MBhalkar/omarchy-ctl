"""Tag manager module."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from omarchy_ctl.core.context import TagCandidate


@dataclass(frozen=True)
class Tag:
    id: str
    name: str
    category: str | None
    confidence: float
    source: str
    created_at: str


@dataclass(frozen=True)
class TagResult:
    applied: list[Tag]
    skipped: list[str]


class TagManagerProtocol(Protocol):
    async def suggest(self, candidates: list[TagCandidate]) -> list[Tag]: ...
    async def apply(self, file_id: str, tags: list[Tag]) -> TagResult: ...
    async def merge(self, source_tag: str, target_tag: str) -> Tag: ...
    async def list(self, query: str | None = None) -> list[Tag]: ...
    async def delete(self, tag_id: str) -> bool: ...


class TagManager:
    def __init__(self, db) -> None:
        self.db = db

    async def _ensure_tags(self, names: list[str]) -> dict[str, Tag]:
        conn = await self.db.get_connection()
        result: dict[str, Tag] = {}
        for name in names:
            tag = await conn.execute("SELECT * FROM tags WHERE name = ?", (name,))
            row = await tag.fetchone()
            if row:
                result[name] = Tag(
                    id=row["id"],
                    name=row["name"],
                    category=row["category"],
                    confidence=row["confidence"],
                    source=row["source"],
                    created_at=row["created_at"],
                )
            else:
                tag_id = str(uuid.uuid4())
                await conn.execute(
                    "INSERT INTO tags (id, name, category, confidence, source) VALUES (?, ?, ?, ?, ?)",
                    (tag_id, name, None, 1.0, "manual"),
                )
                await conn.commit()
                result[name] = Tag(id=tag_id, name=name, category=None, confidence=1.0, source="manual", created_at=datetime.utcnow().isoformat())
        return result

    async def suggest(self, candidates: list[TagCandidate]) -> list[Tag]:
        names = [c.name for c in candidates]
        tags = await self._ensure_tags(names)
        return [tags[n] for n in names if n in tags]

    async def apply(self, file_id: str, tags: list[Tag]) -> TagResult:
        conn = await self.db.get_connection()
        applied: list[Tag] = []
        skipped: list[str] = []
        for tag in tags:
            try:
                await conn.execute("INSERT OR IGNORE INTO file_tags (file_id, tag_id) VALUES (?, ?)", (file_id, tag.id))
                applied.append(tag)
            except Exception:
                skipped.append(tag.name)
        await conn.commit()
        return TagResult(applied=applied, skipped=skipped)

    async def merge(self, source_tag: str, target_tag: str) -> Tag:
        conn = await self.db.get_connection()
        src = await conn.execute("SELECT id FROM tags WHERE name = ?", (source_tag,))
        src_row = await src.fetchone()
        tgt = await conn.execute("SELECT id FROM tags WHERE name = ?", (target_tag,))
        tgt_row = await tgt.fetchone()
        if not src_row or not tgt_row:
            raise ValueError("Tag not found")
        await conn.execute("UPDATE file_tags SET tag_id = ? WHERE tag_id = ?", (tgt_row["id"], src_row["id"]))
        await conn.execute("DELETE FROM tags WHERE id = ?", (src_row["id"],))
        await conn.commit()
        return Tag(
            id=tgt_row["id"], name=target_tag, category=None, confidence=1.0, source="manual", created_at=datetime.utcnow().isoformat()
        )

    async def list(self, query: str | None = None) -> list[Tag]:
        conn = await self.db.get_connection()
        if query:
            cur = await conn.execute("SELECT * FROM tags WHERE name LIKE ?", (f"%{query}%",))
        else:
            cur = await conn.execute("SELECT * FROM tags")
        rows = await cur.fetchall()
        return [
            Tag(id=r["id"], name=r["name"], category=r["category"], confidence=r["confidence"], source=r["source"], created_at=r["created_at"])
            for r in rows
        ]

    async def delete(self, tag_id: str) -> bool:
        conn = await self.db.get_connection()
        await conn.execute("DELETE FROM file_tags WHERE tag_id = ?", (tag_id,))
        await conn.execute("DELETE FROM tags WHERE id = ?", (tag_id,))
        await conn.commit()
        return True
