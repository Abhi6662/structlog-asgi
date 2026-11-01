"""ASGI middleware for structured logging and request ID correlation."""

import time
import uuid
from contextvars import ContextVar
from typing import Callable, Dict, Optional

from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from .logger import get_logger

logger = get_logger("structlog-asgi.middleware")

request_id_var: ContextVar[str] = ContextVar("request_id", default="")

SENSITIVE_HEADERS_DEFAULT = {
    "authorization",
    "cookie",
    "x-api-key",
    "x-auth-token",
    "x-forwarded-for",
}


def _redact_headers(headers: Dict[str, str], sensitive: set) -> Dict[str, str]:
    """Return headers with sensitive values redacted."""
    redacted: Dict[str, str] = {}
    for key, value in headers.items():
        if key.lower() in sensitive:
            redacted[key] = "***REDACTED***"
        else:
            redacted[key] = value
    return redacted


class RequestIDMiddleware:
    """ASGI middleware that generates or propagates an X-Request-ID header.

    Uses Starlette's contextvars to make the request ID available downstream.
    """

    def __init__(self, app: ASGIApp, header_name: str = "x-request-id"):
        self.app = app
        self.header_name = header_name.lower()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers", []))
        request_id = headers.get(
            self.header_name.encode(), str(uuid.uuid4()).encode()
        ).decode()

        token = request_id_var.set(request_id)

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                message.setdefault("headers", [])
                message["headers"].append(
                    (self.header_name.encode(), request_id.encode())
                )
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            request_id_var.reset(token)


class LoggingMiddleware:
    """ASGI middleware that logs requests and responses as structured JSON.

    Logs:
        - Request method, path, client IP, headers (sensitive redacted)
        - Response status code, latency in ms
        - Exception trace if the handler raises
    """

    def __init__(
        self,
        app: ASGIApp,
        sensitive_headers: Optional[set] = None,
        log_request_body: bool = False,
    ):
        self.app = app
        self.sensitive_headers = sensitive_headers or SENSITIVE_HEADERS_DEFAULT
        self.log_request_body = log_request_body

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive=receive)
        start_time = time.time()

        # Extract client IP
        client_ip = "unknown"
        if scope.get("client"):
            client_ip = scope["client"][0]
        forwarded_for = request.headers.get("x-forwarded-for", "")
        if forwarded_for:
            client_ip = forwarded_for.split(",")[0].strip()

        # Get request ID from context (set by RequestIDMiddleware)
        request_id = request_id_var.get()

        # Redact sensitive headers
        raw_headers = dict(request.headers)
        safe_headers = _redact_headers(raw_headers, self.sensitive_headers)

        logger.info(
            "request.started",
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            query=str(request.url.query),
            client_ip=client_ip,
            headers=safe_headers,
        )

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                status_code = message.get("status", 0)
                latency_ms = round((time.time() - start_time) * 1000, 2)
                logger.info(
                    "request.completed",
                    request_id=request_id,
                    method=request.method,
                    path=request.url.path,
                    status_code=status_code,
                    latency_ms=latency_ms,
                )
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception as exc:
            latency_ms = round((time.time() - start_time) * 1000, 2)
            logger.exception(
                "request.failed",
                request_id=request_id,
                method=request.method,
                path=request.url.path,
                latency_ms=latency_ms,
                exc_type=type(exc).__name__,
            )
            raise
