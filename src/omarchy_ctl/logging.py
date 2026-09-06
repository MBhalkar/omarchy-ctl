"""Logging setup for CTL."""

from __future__ import annotations

import logging
import sys

import structlog

_configured = False


def setup_logging(level: str = "INFO") -> None:
    """Configure structlog to write structured logs to stderr.

    Logs go to stderr so they never pollute stdout, which is reserved for
    machine-readable output (e.g. ``--json`` consumed by the Quickshell panel).
    """
    global _configured
    if _configured:
        return

    numeric = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stderr,
        level=numeric,
        force=True,
    )
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.dev.ConsoleRenderer(colors=False),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(numeric),
        cache_logger_on_first_use=True,
        logger_factory=structlog.PrintLoggerFactory(sys.stderr),
    )
    _configured = True


def get_logger(name: str | None = None):
    return structlog.get_logger(name or "omarchy-ctl")
