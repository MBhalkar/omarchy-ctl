# Contextual Tagging & Linking (CTL) for Omarchy OS

## Overview

CTL is an intelligent file organization plugin for Omarchy OS that automatically derives meaningful tags and links for files based on their content, metadata, and relationships. It moves beyond simple folder-based organization by providing contextual tagging, relational linking, and advanced search capabilities.

## Quick Install

```bash
omarchy plugin add https://github.com/MBhalkar/omarchy-ctl.git
```

---

# 1. Architectural Design Document

## 1.1 System Overview

CTL is architected as a set of decoupled, asynchronous services that run independently of the main OS interface. The system follows a pipeline architecture: **Ingest → Analyze → Index → Serve**.

```
┌─────────────────────────────────────────────────────────────────┐
│                     CTL Plugin Architecture                     │
├─────────────┬──────────────┬────────────┬──────────────────────┤
│   CLI /     │  Rest API /  │   TUI /    │  Desktop             │
│  Desktop    │  IPC Socket  │  Widget    │  Integration         │
│  Entry      │  Server      │  Interface │  Hooks               │
└──────┬──────┴──────┬───────┴─────┬──────┴──────────┬───────────┘
       │             │             │                 │
       ▼             ▼             ▼                 ▼
┌──────────────────────────────────────────────────────────────────┐
│                     CTL Service Layer                            │
│  ┌──────────────┐  ┌──────────────┐  ┌─────────────────────┐   │
│  │   Command    │  │     API      │  │      Widget         │   │
│  │   Router     │  │   Server     │  │     Provider        │   │
│  └──────────────┘  └──────────────┘  └─────────────────────┘   │
└──────────────────────────────────────────────────────────────────┘
       │             │             │                 │
       ▼             ▼             ▼                 ▼
┌──────────────────────────────────────────────────────────────────┐
│                     Core Engine Layer                            │
│  ┌──────────────┐  ┌──────────────┐  ┌─────────────────────┐   │
│  │ File Scanner │  │   Context    │  │    Link Manager     │   │
│  │   Module     │  │   Engine     │  │      Module         │   │
│  └──────────────┘  └──────────────┘  └─────────────────────┘   │
│  ┌──────────────┐  ┌──────────────┐  ┌─────────────────────┐   │
│  │   Tag        │  │   Search     │  │   Encryption        │   │
│  │   Manager    │  │   Index      │  │   Service           │   │
│  └──────────────┘  └──────────────┘  └─────────────────────┘   │
└──────────────────────────────────────────────────────────────────┘
       │             │             │                 │
       ▼             ▼             ▼                 ▼
┌──────────────────────────────────────────────────────────────────┐
│                     Data Layer                                   │
│  ┌──────────────────────────┐  ┌──────────────────────────┐    │
│  │  Encrypted Metadata DB   │  │     File System          │    │
│  │  (SQLite + AES-256)      │  │   (Read-Only Access)     │    │
│  └──────────────────────────┘  └──────────────────────────┘    │
└──────────────────────────────────────────────────────────────────┘
```

## 1.2 Module Specifications

### 1.2.1 File Scanner Module
- **Purpose:** Recursively monitor and ingest files from user-specified directories
- **Interface:** `ScannerProtocol`
- **Responsibilities:**
  - Directory traversal with configurable depth limits
  - File change detection (mtime/inode hashing)
  - MIME type detection via `libmagic` bindings
  - Incremental scan state management
  - Debounced event emission to Context Engine

### 1.2.2 Context Engine Module
- **Purpose:** Extract contextual signals from file metadata and content
- **Interface:** `ContextEngineProtocol`
- **Responsibilities:**
  - Metadata analysis (extension, size, dates, parent paths)
  - Keyword extraction (RAKE, YAKE, or TF-IDF on first N lines)
  - Tag suggestion scoring and ranking
  - LLM integration interface (Phase 2)
  - Emit structured tag candidates

### 1.2.3 Tag Manager Module
- **Purpose:** Persist, validate, and manage tag taxonomy
- **Interface:** `TagManagerProtocol`
- **Responsibilities:**
  - Tag CRUD operations
  - Tag merging/synonym resolution
  - Tag suggestion acceptance/rejection
  - Tag hierarchy management
  - Encryption/decryption of stored tags

### 1.2.4 Link Manager Module
- **Purpose:** Manage relational metadata between files
- **Interface:** `LinkManagerProtocol`
- **Responsibilities:**
  - Link CRUD (create, read, update, delete)
  - Relationship typing (related_to, references, supersedes, etc.)
  - Bidirectional link resolution
  - Circular reference detection
  - Graph traversal primitives

### 1.2.5 Search Index Module
- **Purpose:** Provide fast, complex querying across file metadata, tags, and links
- **Interface:** `SearchIndexProtocol`
- **Responsibilities:**
  - Full-text search across tags and file content
  - Graph-aware query language (tag + link filters)
  - Result ranking and pagination
  - Incremental index updates
  - FTS5-backed SQLite queries

### 1.2.6 UI Interface Module
- **Purpose:** Provide user-facing interfaces for CTL interaction
- **Components:**
  - CLI (`ctl` command with subcommands)
  - IPC REST server (localhost-only, Unix socket)
  - Quickshell widget (for bar integration)
  - Notification daemon hooks

## 1.3 Data Flow

```
File System Change
        │
        ▼
[File Scanner] ──metadata──▶ [Context Engine]
        │                       │
        │                  tag candidates
        │                       │
        ▼                       ▼
   [Incremental            [Tag Manager]
    Scan Queue]              │
        │                store/merge
        │                       │
        ▼                       ▼
   [Link Manager] ◀─────user-defined links
        │
        ▼
[Search Index + Encrypted SQLite]
        │
        ▼
[UI Layer: CLI / IPC / Widget]
```

## 1.4 API Contracts

### Scanner API
```python
class ScannerProtocol:
    async def scan(self, paths: list[str], recursive: bool = True) -> ScanResult
    async def watch(self, paths: list[str], callback: Callable[[FileEvent], None]) -> WatchHandle
    def stop_watch(self, handle: WatchHandle) -> None
```

### Context Engine API
```python
class ContextEngineProtocol:
    async def analyze(self, file_path: str, metadata: FileMetadata) -> TagCandidates
    async def batch_analyze(self, files: list[FileRef]) -> list[TagCandidates]
    def register_analyzer(self, analyzer: BaseAnalyzer) -> None
```

### Tag Manager API
```python
class TagManagerProtocol:
    async def suggest(self, candidates: TagCandidates) -> list[Tag]
    async def apply(self, file_id: str, tags: list[Tag]) -> TagResult
    async def merge(self, source_tag: str, target_tag: str) -> Tag
    async def list(self, query: TagQuery) -> list[Tag]
    async def delete(self, tag_id: str) -> bool
```

### Link Manager API
```python
class LinkManagerProtocol:
    async def create(self, source_id: str, target_id: str, relation: str, metadata: dict) -> Link
    async def resolve(self, file_id: str, direction: str = "both") -> list[Link]
    async def graph(self, file_ids: list[str], depth: int = 2) -> RelationshipGraph
    async def delete(self, link_id: str) -> bool
```

### Search Index API
```python
class SearchIndexProtocol:
    async def query(self, query: SearchQuery) -> SearchResult
    async def index_file(self, file_id: str) -> None
    async def remove_file(self, file_id: str) -> None
    async def rebuild(self) -> None
```

### Storage API
```python
class StorageProtocol:
    async def init_db(self) -> None
    async def migrate(self) -> None
    async def get_connection(self) -> aiosqlite.Connection
    def get_crypto(self) -> CryptoService
```

## 1.5 Data Model

### Files Table
```sql
CREATE TABLE files (
    id          TEXT PRIMARY KEY,
    path        TEXT NOT NULL UNIQUE,
    filename    TEXT NOT NULL,
    extension   TEXT,
    mime_type   TEXT,
    size_bytes  INTEGER,
    created_at  TEXT,
    modified_at TEXT,
    content_hash TEXT,
    scan_status TEXT DEFAULT 'pending',
    last_scanned TEXT
);
```

### Tags Table
```sql
CREATE TABLE tags (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL UNIQUE,
    category    TEXT,
    confidence  REAL DEFAULT 1.0,
    source      TEXT DEFAULT 'auto',
    created_at  TEXT DEFAULT CURRENT_TIMESTAMP
);
```

### File Tags Join Table
```sql
CREATE TABLE file_tags (
    file_id TEXT NOT NULL,
    tag_id  TEXT NOT NULL,
    PRIMARY KEY (file_id, tag_id),
    FOREIGN KEY (file_id) REFERENCES files(id) ON DELETE CASCADE,
    FOREIGN KEY (tag_id)  REFERENCES tags(id)  ON DELETE CASCADE
);
```

### Links Table
```sql
CREATE TABLE links (
    id          TEXT PRIMARY KEY,
    source_id   TEXT NOT NULL,
    target_id   TEXT NOT NULL,
    relation    TEXT NOT NULL,
    metadata    TEXT,
    created_at  TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (source_id) REFERENCES files(id) ON DELETE CASCADE,
    FOREIGN KEY (target_id) REFERENCES files(id) ON DELETE CASCADE
);
```

## 1.6 Security Model

- **At Rest:** All tag and link metadata encrypted with AES-256-GCM using a user-derived key (from `~/.config/ctl/key`)
- **In Transit:** IPC communication over Unix socket with filesystem permissions (600)
- **Access Control:** CTL daemon runs as user process; no root required
- **Key Derivation:** Argon2id from user password or system keyring integration

---

# 2. Technology Stack Justification

## 2.1 Core Language: Python 3.11+

### Rationale
Python is selected as the primary implementation language for the following reasons:

| Factor | Justification |
|--------|---------------|
| **NLP Ecosystem** | Python has the richest NLP libraries: `spaCy`, `NLTK`, `scikit-learn`, `keybert`, `rake-nltk`. Critical for Phase 1 keyword extraction and Phase 2 LLM integration. |
| **Rapid Prototyping** | The plugin requires iterative development of tagging heuristics. Python's dynamic typing and REPL accelerate experimentation. |
| **Async Support** | `asyncio` and `aiofiles` provide robust asynchronous I/O, meeting the non-blocking requirement. |
| **Encryption Libraries** | `cryptography` package offers production-grade AES-256-GCM and Argon2id key derivation. |
| **SQLite Bindings** | `aiosqlite` and `sqlalchemy` provide async database access with FTS5 full-text search support. |
| **Packaging** | `pyproject.toml` and `pip` allow clean packaging for distribution via `omarchy plugin add`. |
| **Cross-Platform** | POSIX compliance is straightforward; the code will run natively on Omarchy's Arch Linux base. |

### Trade-offs Accepted
- **Performance:** Python is slower than Go for raw I/O. However, the bottleneck is NLP/ML processing (where Python excels) and disk I/O (where async mitigates the GIL). A Go scanner wrapper could be introduced in Phase 2 if profiling shows the scanner is the bottleneck.
- **Memory:** Higher baseline memory. Mitigated by running as a daemon with configurable batch sizes.

## 2.2 Alternative Considered: Go

| Factor | Assessment |
|--------|-----------|
| **Concurrency** | Go's goroutines are ideal for the scanner. |
| **Deployment** | Single static binary with no runtime dependency. |
| **NLP Ecosystem** | Significantly weaker. `go-nlp` libraries are immature compared to Python. Integrating LLM APIs requires more boilerplate. |
| **Decision** | **Rejected for core engine.** Could be reconsidered for a scanner-only microservice in Phase 2 if needed. |

## 2.3 Selected Libraries (MVP)

| Purpose | Library | Justification |
|---------|---------|---------------|
| **Async Runtime** | `asyncio` (stdlib) | No external dependency; mature event loop |
| **File Watching** | `watchfiles` | Fast, async-native Rust-backed file watcher |
| **NLP / Keyword Extraction** | `keybert` + `scikit-learn` | Lightweight BERT-based keyword extraction; fallback to RAKE |
| **Database** | `aiosqlite` + FTS5 | Async SQLite with full-text search |
| **Encryption** | `cryptography` | AES-256-GCM, Argon2id key derivation |
| **CLI** | `typer` | Modern, type-safe CLI with auto-generated help |
| **IPC Server** | `aiohttp` (Unix socket only) | Lightweight async HTTP for local IPC |
| **Config** | `pydantic-settings` | Type-safe config with env var support |
| **Logging** | `structlog` | Structured logging for debugging |

## 2.4 Phase 2 Technology Additions

| Feature | Technology | Rationale |
|---------|-----------|-----------|
| **Deep NLP** | Ollama local LLM API or OpenAI-compatible API | Pluggable interface allows switching between local and cloud models |
| **Graph Queries** | `networkx` or custom graph traversal | Relationship graph querying |
| **Vector Search** | `chromadb` or `faiss-cpu` | Semantic similarity search over file content |
| **Daemonization** | `systemd` user service | Standard Linux service management |

---

# 3. Implementation Roadmap (MVP)

## Phase 1: Foundation (Weeks 1-2)

### Step 1: Project Scaffolding
- Initialize `pyproject.toml` with dependencies and entry points
- Create module structure (`ctl/` package layout)
- Set up logging, config, and error handling frameworks
- Implement `CryptoService` (AES-256-GCM + Argon2id)

### Step 2: Storage Layer
- Implement `StorageProtocol` with `aiosqlite`
- Create database migrations for `files`, `tags`, `file_tags`, `links` tables
- Enable FTS5 virtual table for full-text search
- Implement encryption layer for sensitive metadata

### Step 3: File Scanner
- Implement recursive directory traversal with `aiofiles` + `watchfiles`
- Add MIME type detection (via `python-magic`)
- Build incremental scan state (track `content_hash` and `mtime`)
- Emit `FileEvent` objects to async queue

### Step 4: Context Engine (MVP)
- Implement metadata-based tag extraction (extension, size, parent dir)
- Integrate `keybert` for keyword extraction on first 200 lines of text files
- Build `TagCandidate` scoring pipeline
- Add fallback RAKE extractor for dependency-light environments

### Step 5: Tag Manager
- Implement tag CRUD with deduplication and merge logic
- Wire Context Engine output to Tag Manager
- Add tag suggestion queue (pending user confirmation)

### Step 6: Link Manager (MVP)
- Implement link CRUD with relation types
- Add bidirectional link resolution
- Implement circular reference detection

### Step 7: Search Index
- Build FTS5-backed search queries
- Implement tag + link filter composition
- Add result ranking by relevance and recency

### Step 8: CLI Interface
- Build `ctl` CLI with `typer`
- Subcommands: `scan`, `tags`, `links`, `search`, `status`
- Add `--json` output for scripting

### Step 9: IPC Server
- Expose REST endpoints over Unix socket for UI integration
- Endpoints: `/scan`, `/tags`, `/links`, `/search`, `/status`

### Step 10: Testing & Packaging
- Write unit tests for each module (`pytest`)
- Create `omarchy plugin` packaging manifest
- Add installation script for systemd user service
- Document configuration options in `config/ctl.toml`

## Phase 2: Enhancement (Post-MVP)

| Feature | Effort | Description |
|---------|--------|-------------|
| **Quickshell Widget** | Medium | Bar widget showing tag cloud and recent links |
| **Deep NLP** | High | LLM integration via Ollama for semantic tagging |
| **Vector Index** | Medium | ChromaDB for semantic similarity search |
| **Relationship Graph** | Medium | Graphviz/HTML visualization of file relationships |
| **Desktop Hooks** | Low | inotify-based auto-tagging on file save |
| **Tag Suggestions UI** | Medium | Interactive tag review in TUI or widget |

## Configuration Schema

```toml
[scanner]
paths = ["~/Documents", "~/Projects"]
ignore_dirs = [".git", "node_modules", "__pycache__"]
max_file_size_mb = 50
batch_size = 100

[nlp]
model = "all-MiniLM-L6-v2"
max_keywords = 10
confidence_threshold = 0.5
scan_lines = 200

[storage]
db_path = "~/.local/share/ctl/ctl.db"
key_path = "~/.config/ctl/encryption.key"

[server]
socket_path = "~/.local/share/ctl/ctl.sock"
enable = true

[ui]
notifications = true
auto_scan = false
```

---

## License

MIT License - see [LICENSE](LICENSE) for details.
