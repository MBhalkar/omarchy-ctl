"""Tests for CTL modules."""

import asyncio
import os
import tempfile
from pathlib import Path

import pytest

from omarchy_ctl.core.context import ContextEngine, KeywordAnalyzer, MetadataAnalyzer
from omarchy_ctl.core.links import LinkManager
from omarchy_ctl.core.scanner import Scanner
from omarchy_ctl.core.search import SearchIndex, SearchQuery
from omarchy_ctl.core.tags import TagManager
from omarchy_ctl.storage.crypto import CryptoService
from omarchy_ctl.storage.database import Database


@pytest.fixture
async def tmp_db():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        key_path = Path(tmpdir) / "key"
        crypto = CryptoService(key_path)
        crypto.initialize("testpassword")
        db = Database(db_path, crypto)
        await db.init_db()
        yield db


def test_crypto_service_roundtrip():
    with tempfile.TemporaryDirectory() as tmpdir:
        key_path = Path(tmpdir) / "key"
        crypto = CryptoService(key_path)
        crypto.initialize("password123")
        plaintext = b"hello world"
        encrypted = crypto.encrypt(plaintext)
        decrypted = crypto.decrypt(encrypted)
        assert decrypted == plaintext


def test_metadata_analyzer():
    analyzer = MetadataAnalyzer()
    from omarchy_ctl.core.scanner import FileRef

    f = FileRef(
        path=Path("/home/user/Documents/report.pdf"),
        filename="report.pdf",
        extension="pdf",
        mime_type="application/pdf",
        size_bytes=1024,
        created_at="2024-01-01T00:00:00",
        modified_at="2024-01-01T00:00:00",
        content_hash="abc123",
    )
    tags = analyzer.analyze(f)
    assert any(t.name == "document-pdf" for t in tags)
    assert any(t.name == "size-small" for t in tags)
    assert any(t.name == "location-documents" for t in tags)


def test_keyword_analyzer():
    analyzer = KeywordAnalyzer(max_keywords=3, confidence_threshold=0.1)
    from omarchy_ctl.core.scanner import FileRef

    f = FileRef(
        path=Path("/tmp/test.txt"),
        filename="test.txt",
        extension="txt",
        mime_type="text/plain",
        size_bytes=100,
        created_at="2024-01-01T00:00:00",
        modified_at="2024-01-01T00:00:00",
        content_hash="abc",
    )
    snippet = "Python is great. Python is awesome. Python is powerful."
    tags = analyzer.analyze(f, snippet)
    assert any(t.name == "python" for t in tags)
    assert len(tags) <= 3


@pytest.mark.asyncio
async def test_scanner_ignores_large_files():
    scanner = Scanner(max_file_size_mb=1)
    with tempfile.TemporaryDirectory() as tmpdir:
        small = Path(tmpdir) / "small.txt"
        small.write_text("hello")
        large = Path(tmpdir) / "large.txt"
        large.write_bytes(b"x" * (2 * 1024 * 1024))
        files = await scanner.scan_path(tmpdir, recursive=False)
        assert any(f.filename == "small.txt" for f in files)
        assert not any(f.filename == "large.txt" for f in files)


@pytest.mark.asyncio
async def test_tag_manager_crud(tmp_db):
    mgr = TagManager(tmp_db)
    from omarchy_ctl.core.context import TagCandidate

    tag = await mgr.suggest([TagCandidate(name="alpha", category="keyword", confidence=0.9, source="test")])
    assert len(tag) == 1
    all_tags = await mgr.list()
    assert len(all_tags) == 1
    deleted = await mgr.delete(tag[0].id)
    assert deleted
    all_tags = await mgr.list()
    assert len(all_tags) == 0


@pytest.mark.asyncio
async def test_link_manager_create_and_resolve(tmp_db):
    mgr = LinkManager(tmp_db)
    conn = await tmp_db.get_connection()
    await conn.execute("INSERT INTO files (id, path, filename) VALUES (?, ?, ?)", ("f1", "/a", "a"))
    await conn.execute("INSERT INTO files (id, path, filename) VALUES (?, ?, ?)", ("f2", "/b", "b"))
    await conn.commit()
    link = await mgr.create("f1", "f2", "references")
    assert link.relation == "references"
    outbound = await mgr.resolve("f1", "outbound")
    assert len(outbound) == 1
    inbound = await mgr.resolve("f2", "inbound")
    assert len(inbound) == 1


@pytest.mark.asyncio
async def test_search_index_query(tmp_db):
    mgr = TagManager(tmp_db)
    idx = SearchIndex(tmp_db)
    conn = await tmp_db.get_connection()
    await conn.execute("INSERT INTO files (id, path, filename, extension, content) VALUES (?, ?, ?, ?, ?)", ("f1", "/a/b.txt", "b.txt", "txt", "hello world license test"))
    await conn.commit()
    await idx.rebuild()
    result = await idx.query(SearchQuery(text="license"))
    assert result.total >= 1
    assert any(f["filename"] == "b.txt" for f in result.files)


@pytest.mark.asyncio
async def test_search_exact_hyphenated_tag(tmp_db):
    mgr = TagManager(tmp_db)
    idx = SearchIndex(tmp_db)
    conn = await tmp_db.get_connection()
    await conn.execute("INSERT INTO files (id, path, filename, extension, content) VALUES (?, ?, ?, ?, ?)", ("f1", "/pics/photo.jpg", "photo.jpg", "jpg", ""))
    await conn.commit()
    await idx.rebuild()
    from omarchy_ctl.core.context import TagCandidate
    tags = await mgr.suggest([TagCandidate(name="image-jpeg", category="type", confidence=1.0, source="metadata")])
    await mgr.apply("f1", tags)
    result = await idx.query(SearchQuery(text="image-jpeg", tags=["image-jpeg"]))
    assert result.total == 1
    assert result.files[0]["filename"] == "photo.jpg"
    text_only = await idx.query(SearchQuery(text="image-jpeg"))
    assert text_only.total == 1
    assert text_only.files[0]["filename"] == "photo.jpg"


@pytest.mark.asyncio
async def test_search_content_matches(tmp_db):
    idx = SearchIndex(tmp_db)
    conn = await tmp_db.get_connection()
    await conn.execute("INSERT INTO files (id, path, filename, extension, content) VALUES (?, ?, ?, ?, ?)", ("f1", "/a/b.txt", "b.txt", "txt", "hello world"))
    await conn.execute("INSERT INTO files (id, path, filename, extension, content) VALUES (?, ?, ?, ?, ?)", ("f2", "/a/c.txt", "c.txt", "txt", "goodbye world"))
    await conn.commit()
    await idx.rebuild()
    result = await idx.query(SearchQuery(text="hello"))
    assert result.total == 1
    assert result.files[0]["filename"] == "b.txt"
