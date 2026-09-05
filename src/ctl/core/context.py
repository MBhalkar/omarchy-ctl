"""Context engine for deriving tags from file metadata and content."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from ctl.core.scanner import FileRef


@dataclass(frozen=True)
class TagCandidate:
    name: str
    category: str | None
    confidence: float
    source: str


class BaseAnalyzer(Protocol):
    async def analyze(self, file: FileRef, content_snippet: str | None = None) -> list[TagCandidate]: ...


class MetadataAnalyzer:
    """Derives tags from file metadata (extension, size, path)."""

    EXTENSION_TAGS = {
        ".pdf": "document-pdf",
        ".md": "document-markdown",
        ".txt": "document-text",
        ".py": "code-python",
        ".js": "code-javascript",
        ".ts": "code-typescript",
        ".rs": "code-rust",
        ".go": "code-go",
        ".json": "data-json",
        ".yaml": "data-yaml",
        ".yml": "data-yaml",
        ".toml": "data-toml",
        ".csv": "data-csv",
        ".sql": "data-sql",
        ".png": "image-png",
        ".jpg": "image-jpeg",
        ".jpeg": "image-jpeg",
        ".gif": "image-gif",
        ".svg": "image-svg",
        ".mp3": "audio-mp3",
        ".wav": "audio-wav",
        ".mp4": "video-mp4",
        ".mkv": "video-mkv",
        ".zip": "archive-zip",
        ".tar": "archive-tar",
        ".gz": "archive-gzip",
    }

    SIZE_TAGS = [
        (10 * 1024 * 1024, "size-small"),
        (100 * 1024 * 1024, "size-medium"),
        (None, "size-large"),
    ]

    def analyze(self, file: FileRef, content_snippet: str | None = None) -> list[TagCandidate]:
        candidates: list[TagCandidate] = []
        ext = "." + (file.extension or "").lower()
        if ext in self.EXTENSION_TAGS:
            candidates.append(TagCandidate(name=self.EXTENSION_TAGS[ext], category="type", confidence=1.0, source="metadata"))
        for threshold, tag in self.SIZE_TAGS:
            if threshold is None or file.size_bytes < threshold:
                candidates.append(TagCandidate(name=tag, category="size", confidence=1.0, source="metadata"))
                break
        parts = file.path.parts
        for part in parts:
            if part.lower() in ("documents", "downloads", "projects", "images", "music", "videos", "desktop"):
                candidates.append(TagCandidate(name=f"location-{part.lower()}", category="location", confidence=0.9, source="metadata"))
        return candidates


class KeywordAnalyzer:
    """Extracts keywords from text content."""

    STOPWORDS = {
        "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
        "have", "has", "had", "do", "does", "did", "will", "would", "could",
        "should", "may", "might", "shall", "can", "to", "of", "in", "for",
        "on", "with", "at", "by", "from", "as", "into", "through", "during",
        "before", "after", "above", "below", "between", "out", "off", "over",
        "under", "again", "further", "then", "once", "and", "but", "or", "nor",
        "not", "so", "very", "just", "because", "but", "and", "if", "or",
    }

    def __init__(self, max_keywords: int = 10, confidence_threshold: float = 0.5) -> None:
        self.max_keywords = max_keywords
        self.confidence_threshold = confidence_threshold

    def _tokenize(self, text: str) -> list[str]:
        words = re.findall(r"[a-zA-Z]{3,}", text.lower())
        return [w for w in words if w not in self.STOPWORDS]

    def _score(self, tokens: list[str]) -> dict[str, float]:
        scores: dict[str, float] = {}
        total = len(tokens)
        for token in tokens:
            scores[token] = scores.get(token, 0.0) + 1.0
        return {k: v / total for k, v in scores.items()}

    def analyze(self, file: FileRef, content_snippet: str | None = None) -> list[TagCandidate]:
        if not content_snippet:
            return []
        tokens = self._tokenize(content_snippet)
        if not tokens:
            return []
        scores = self._score(tokens)
        top = sorted(scores.items(), key=lambda x: x[1], reverse=True)[: self.max_keywords]
        return [
            TagCandidate(name=word, category="keyword", confidence=round(score, 2), source="content")
            for word, score in top
            if score >= self.confidence_threshold
        ]


class ContextEngine:
    def __init__(self, max_keywords: int = 10, confidence_threshold: float = 0.5) -> None:
        self.metadata_analyzer = MetadataAnalyzer()
        self.keyword_analyzer = KeywordAnalyzer(max_keywords, confidence_threshold)
        self._analyzers: list[BaseAnalyzer] = [self.metadata_analyzer, self.keyword_analyzer]

    def register_analyzer(self, analyzer: BaseAnalyzer) -> None:
        self._analyzers.append(analyzer)

    async def analyze(self, file: FileRef, content_snippet: str | None = None) -> list[TagCandidate]:
        results: list[TagCandidate] = []
        for analyzer in self._analyzers:
            try:
                candidates = analyzer.analyze(file, content_snippet)
                results.extend(candidates)
            except Exception:
                continue
        seen: set[str] = set()
        unique: list[TagCandidate] = []
        for c in sorted(results, key=lambda x: x.confidence, reverse=True):
            if c.name not in seen:
                seen.add(c.name)
                unique.append(c)
        return unique

    async def batch_analyze(self, files: list[FileRef]) -> dict[str, list[TagCandidate]]:
        return {str(f.path): await self.analyze(f) for f in files}
