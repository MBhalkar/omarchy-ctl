"""Link manager module."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True)
class Link:
    id: str
    source_id: str
    target_id: str
    relation: str
    metadata: dict | None
    created_at: str


@dataclass(frozen=True)
class RelationshipGraph:
    nodes: list[str]
    edges: list[Link]


class LinkManagerProtocol(Protocol):
    async def create(self, source_id: str, target_id: str, relation: str, metadata: dict | None = None) -> Link: ...
    async def resolve(self, file_id: str, direction: str = "both") -> list[Link]: ...
    async def graph(self, file_ids: list[str], depth: int = 2) -> RelationshipGraph: ...
    async def delete(self, link_id: str) -> bool: ...


class LinkManager:
    def __init__(self, db) -> None:
        self.db = db

    async def create(self, source_id: str, target_id: str, relation: str, metadata: dict | None = None) -> Link:
        conn = await self.db.get_connection()
        link_id = str(uuid.uuid4())
        meta = str(metadata) if metadata else None
        await conn.execute(
            "INSERT INTO links (id, source_id, target_id, relation, metadata) VALUES (?, ?, ?, ?, ?)",
            (link_id, source_id, target_id, relation, meta),
        )
        await conn.commit()
        return Link(id=link_id, source_id=source_id, target_id=target_id, relation=relation, metadata=metadata, created_at=datetime.utcnow().isoformat())

    async def resolve(self, file_id: str, direction: str = "both") -> list[Link]:
        conn = await self.db.get_connection()
        links: list[Link] = []
        if direction in ("both", "outbound"):
            cur = await conn.execute("SELECT * FROM links WHERE source_id = ?", (file_id,))
            for row in await cur.fetchall():
                links.append(self._row_to_link(row))
        if direction in ("both", "inbound"):
            cur = await conn.execute("SELECT * FROM links WHERE target_id = ?", (file_id,))
            for row in await cur.fetchall():
                links.append(self._row_to_link(row))
        return links

    async def graph(self, file_ids: list[str], depth: int = 2) -> RelationshipGraph:
        nodes = set(file_ids)
        edges: list[Link] = []
        frontier = list(file_ids)
        for _ in range(depth):
            next_frontier: list[str] = []
            for fid in frontier:
                related = await self.resolve(fid, "both")
                for link in related:
                    nodes.add(link.source_id)
                    nodes.add(link.target_id)
                    edges.append(link)
                    next_frontier.append(link.source_id)
                    next_frontier.append(link.target_id)
            frontier = list(set(next_frontier))
        return RelationshipGraph(nodes=list(nodes), edges=edges)

    async def delete(self, link_id: str) -> bool:
        conn = await self.db.get_connection()
        await conn.execute("DELETE FROM links WHERE id = ?", (link_id,))
        await conn.commit()
        return True

    def _row_to_link(self, row) -> Link:
        import ast
        meta = ast.literal_eval(row["metadata"]) if row["metadata"] else None
        return Link(
            id=row["id"],
            source_id=row["source_id"],
            target_id=row["target_id"],
            relation=row["relation"],
            metadata=meta,
            created_at=row["created_at"],
        )
