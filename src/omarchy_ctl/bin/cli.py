"""CLI entry point for CTL."""

from __future__ import annotations

import asyncio
import sys
import uuid
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from omarchy_ctl.core.context import ContextEngine
from omarchy_ctl.core.links import LinkManager
from omarchy_ctl.core.scanner import Scanner
from omarchy_ctl.core.search import SearchQuery, SearchIndex
from omarchy_ctl.core.tags import TagManager
from omarchy_ctl.logging import get_logger, setup_logging
from omarchy_ctl.storage.crypto import CryptoService
from omarchy_ctl.storage.database import get_storage, close_storage

app = typer.Typer(name="omarchy-ctl", help="Contextual Tagging & Linking for Omarchy")
console = Console()

log = get_logger("omarchy-ctl.cli")

setup_logging()


@app.command()
def scan(paths: list[str] = typer.Argument(..., help="Paths to scan")) -> None:
    """Scan files and generate tags."""
    asyncio.run(_scan(paths))


async def _scan(paths: list[str]) -> None:
    crypto = CryptoService(Path("~/.config/omarchy-ctl/encryption.key").expanduser())
    try:
        crypto.load("default")
    except Exception:
        crypto.initialize("default")
    db = await get_storage("~/.local/share/omarchy-ctl/omarchy-ctl.db", crypto)
    try:
        scanner = Scanner()
        engine = ContextEngine()
        tag_mgr = TagManager(db)
        search_idx = SearchIndex(db)
        conn = await db.get_connection()
        file_id_map: dict[str, str] = {}
        for p in paths:
            log.info("scan_start", path=p)
            files = await scanner.scan_path(p)
            console.print(f"Scanned [bold]{len(files)}[/bold] files from {p}")

            content_map: dict[str, str] = {}
            for f in files:
                if f.mime_type and f.mime_type.startswith("text"):
                    try:
                        text = f.path.read_text(errors="ignore")[:2000]
                        content_map[str(f.path)] = text
                    except Exception:
                        pass

            for f in files:
                fpath = str(f.path)
                content = content_map.get(fpath, "")
                await conn.execute(
                    """INSERT INTO files
                           (id, path, filename, extension, mime_type, size_bytes,
                            created_at, modified_at, content_hash, content, last_scanned)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                       ON CONFLICT(path) DO UPDATE SET
                           filename    = excluded.filename,
                           extension   = excluded.extension,
                           mime_type   = excluded.mime_type,
                           size_bytes  = excluded.size_bytes,
                           created_at  = excluded.created_at,
                           modified_at = excluded.modified_at,
                           content_hash = excluded.content_hash,
                           content     = excluded.content,
                           last_scanned = excluded.last_scanned""",
                    (
                        str(uuid.uuid4()),
                        fpath,
                        f.filename,
                        f.extension,
                        f.mime_type,
                        f.size_bytes,
                        f.created_at,
                        f.modified_at,
                        f.content_hash,
                        content,
                        f.modified_at,
                    ),
                )
                await conn.commit()
                cur = await conn.execute("SELECT id FROM files WHERE path = ?", (fpath,))
                row = await cur.fetchone()
                file_id_map[fpath] = row[0]

            await search_idx.rebuild()

            for f in files:
                fpath = str(f.path)
                candidates = await engine.analyze(f, content_map.get(fpath))
                tags = await tag_mgr.suggest(candidates)
                file_id = file_id_map.get(fpath)
                if tags and file_id:
                    await tag_mgr.apply(file_id, tags)
                if tags:
                    console.print(f"  [green]✓[/green] {fpath}: {len(tags)} tags")
            log.info("scan_done", path=p, files=len(files))
    finally:
        await close_storage()


@app.command()
def search(
    query: str = typer.Argument(..., help="Search query"),
    json: bool = typer.Option(False, "--json", help="Output JSON"),
    limit: int = typer.Option(50, "--limit", "-n", min=1, max=10000, help="Maximum results to return"),
    offset: int = typer.Option(0, "--offset", min=0, help="Number of results to skip"),
) -> None:
    """Search files by tags or content."""
    asyncio.run(_search(query, json, limit, offset))


async def _search(query: str, json_output: bool = False, limit: int = 50, offset: int = 0) -> None:
    log.info("search_start", query=query)
    crypto = CryptoService(Path("~/.config/omarchy-ctl/encryption.key").expanduser())
    try:
        crypto.load("default")
    except Exception:
        return
    db = await get_storage("~/.local/share/omarchy-ctl/omarchy-ctl.db", crypto)
    try:
        idx = SearchIndex(db)
        result = await idx.query(SearchQuery(text=query, tags=[query], limit=limit, offset=offset))
        log.info("search_done", query=query, total=result.total)
        if json_output:
            import json as _json
            sys.stdout.write(_json.dumps({
                "query": query,
                "total": result.total,
                "files": result.files
            }))
            sys.stdout.write("\n")
            return
        table = Table(title=f"Results for '{query}'")
        table.add_column("Path", style="cyan")
        table.add_column("Filename", style="green")
        table.add_column("Extension")
        for f in result.files:
            table.add_row(f.get("path", ""), f.get("filename", ""), f.get("extension", ""))
        if not result.files:
            table.add_row("", "No results", "")
        console.print(table)
    except Exception as e:
        log.error("search_failed", query=query, error=str(e))
        raise
    finally:
        await close_storage()


@app.command()
def tags(json: bool = typer.Option(False, "--json", help="Output JSON")) -> None:
    """List all tags."""
    asyncio.run(_tags(json))


async def _tags(json_output: bool = False) -> None:
    crypto = CryptoService(Path("~/.config/omarchy-ctl/encryption.key").expanduser())
    try:
        crypto.load("default")
    except Exception:
        return
    db = await get_storage("~/.local/share/omarchy-ctl/omarchy-ctl.db", crypto)
    try:
        tag_mgr = TagManager(db)
        tags = await tag_mgr.list()
        if json_output:
            import json as _json
            sys.stdout.write(_json.dumps([{"name": t.name, "category": t.category or "", "source": t.source} for t in tags]))
            sys.stdout.write("\n")
            return
        table = Table(title="Tags")
        table.add_column("Name", style="cyan")
        table.add_column("Category")
        table.add_column("Source")
        for t in tags:
            table.add_row(t.name, t.category or "", t.source)
        console.print(table)
    finally:
        await close_storage()


@app.command()
def link(source: str, target: str, relation: str = "related_to") -> None:
    """Create a link between two files."""
    asyncio.run(_link(source, target, relation))


async def _link(source: str, target: str, relation: str) -> None:
    crypto = CryptoService(Path("~/.config/omarchy-ctl/encryption.key").expanduser())
    try:
        crypto.load("default")
    except Exception:
        return
    db = await get_storage("~/.local/share/omarchy-ctl/omarchy-ctl.db", crypto)
    try:
        link_mgr = LinkManager(db)
        link = await link_mgr.create(source, target, relation)
        console.print(f"Created link: [bold]{link.source_id}[/bold] -> [bold]{link.target_id}[/bold] ({relation})")
    finally:
        await close_storage()


@app.command()
def status() -> None:
    """Show CTL daemon status."""
    console.print("[bold green]CTL[/bold green] is ready")
    crypto = CryptoService(Path("~/.config/omarchy-ctl/encryption.key").expanduser())
    if crypto.key_path.exists():
        console.print(f"Key: [green]present[/green] at {crypto.key_path}")
    else:
        console.print("Key: [yellow]not initialized[/yellow]")


if __name__ == "__main__":
    app()
