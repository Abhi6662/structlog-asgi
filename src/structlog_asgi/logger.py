"""Logger configuration for structlog-asgi."""

import logging
import sys
from typing import Optional

import structlog


def configure_logging(
    json_logs: bool = True,
    log_level: str = "INFO",
    sensitive_headers: Optional[list] = None,
) -> None:
    """Configure structlog with JSON output for ASGI applications.

    Args:
        json_logs: Emit JSON-formatted logs (default True)
        log_level: Minimum log level (default INFO)
        sensitive_headers: Header names to redact in log output
    """
    if sensitive_headers is None:
        sensitive_headers = ["authorization", "cookie", "x-api-key", "x-auth-token"]

    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.format_exc_info,
    ]

    if json_logs:
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer())

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, log_level.upper(), logging.INFO)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=False,
    )


def get_logger(name: str = "structlog-asgi"):
    """Get a structlog logger instance."""
    return structlog.get_logger(name)
