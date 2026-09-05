"""CLI entry point for CTL."""

from __future__ import annotations

import asyncio
import uuid
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from ctl.core.context import ContextEngine
from ctl.core.links import LinkManager
from ctl.core.scanner import Scanner
from ctl.core.search import SearchQuery, SearchIndex
from ctl.core.tags import TagManager
from ctl.storage.crypto import CryptoService
from ctl.storage.database import get_storage

app = typer.Typer(name="ctl", help="Contextual Tagging & Linking for Omarchy")
console = Console()


@app.command()
def scan(paths: list[str] = typer.Argument(..., help="Paths to scan")) -> None:
    """Scan files and generate tags."""
    asyncio.run(_scan(paths))


async def _scan(paths: list[str]) -> None:
    crypto = CryptoService(Path("~/.config/ctl/encryption.key").expanduser())
    try:
        crypto.load("default")
    except Exception:
        crypto.initialize("default")
    db = await get_storage("~/.local/share/ctl/ctl.db", crypto)
    scanner = Scanner()
    engine = ContextEngine()
    tag_mgr = TagManager(db)
    search_idx = SearchIndex(db)
    conn = await db.get_connection()
    file_id_map: dict[str, str] = {}
    for p in paths:
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
            import uuid
            file_id = str(uuid.uuid4())
            await conn.execute(
                "INSERT INTO files (id, path, filename, extension, mime_type, size_bytes, created_at, modified_at, content_hash, last_scanned) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (file_id, str(f.path), f.filename, f.extension, f.mime_type, f.size_bytes, f.created_at, f.modified_at, f.content_hash, f.modified_at),
            )
            await conn.commit()
            file_id_map[str(f.path)] = file_id

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


@app.command()
def search(query: str = typer.Argument(..., help="Search query")) -> None:
    """Search files by tags or content."""
    asyncio.run(_search(query))


async def _search(query: str) -> None:
    crypto = CryptoService(Path("~/.config/ctl/encryption.key").expanduser())
    try:
        crypto.load("default")
    except Exception:
        return
    db = await get_storage("~/.local/share/ctl/ctl.db", crypto)
    idx = SearchIndex(db)
    result = await idx.query(SearchQuery(text=query, tags=[query]))
    table = Table(title=f"Results for '{query}'")
    table.add_column("Path", style="cyan")
    table.add_column("Filename", style="green")
    table.add_column("Extension")
    for f in result.files:
        table.add_row(f.get("path", ""), f.get("filename", ""), f.get("extension", ""))
    if not result.files:
        table.add_row("", "No results", "")
    console.print(table)


@app.command()
def tags() -> None:
    """List all tags."""
    asyncio.run(_tags())


async def _tags() -> None:
    crypto = CryptoService(Path("~/.config/ctl/encryption.key").expanduser())
    try:
        crypto.load("default")
    except Exception:
        return
    db = await get_storage("~/.local/share/ctl/ctl.db", crypto)
    tag_mgr = TagManager(db)
    tags = await tag_mgr.list()
    table = Table(title="Tags")
    table.add_column("Name", style="cyan")
    table.add_column("Category")
    table.add_column("Source")
    for t in tags:
        table.add_row(t.name, t.category or "", t.source)
    console.print(table)


@app.command()
def link(source: str, target: str, relation: str = "related_to") -> None:
    """Create a link between two files."""
    asyncio.run(_link(source, target, relation))


async def _link(source: str, target: str, relation: str) -> None:
    crypto = CryptoService(Path("~/.config/ctl/encryption.key").expanduser())
    try:
        crypto.load("default")
    except Exception:
        return
    db = await get_storage("~/.local/share/ctl/ctl.db", crypto)
    link_mgr = LinkManager(db)
    link = await link_mgr.create(source, target, relation)
    console.print(f"Created link: [bold]{link.source_id}[/bold] -> [bold]{link.target_id}[/bold] ({relation})")


@app.command()
def status() -> None:
    """Show CTL daemon status."""
    console.print("[bold green]CTL[/bold green] is ready")
    crypto = CryptoService(Path("~/.config/ctl/encryption.key").expanduser())
    if crypto.key_path.exists():
        console.print(f"Key: [green]present[/green] at {crypto.key_path}")
    else:
        console.print("Key: [yellow]not initialized[/yellow]")


if __name__ == "__main__":
    app()
