"""Tests for structlog-asgi middleware."""

import io
import json
import logging

import pytest
from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from structlog_asgi import LoggingMiddleware, RequestIDMiddleware, configure_logging


def _homepage(request):
    return PlainTextResponse("OK")


def _error_endpoint(request):
    raise RuntimeError("boom")


def _capture_logs():
    """Capture structlog JSON output as a list of dicts."""
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setLevel(logging.DEBUG)

    import structlog

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.DEBUG),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=stream),
        cache_logger_on_first_use=False,
    )

    return stream


def parse_captured_logs(stream):
    """Parse captured JSON log lines into list of dicts."""
    records = []
    for line in stream.getvalue().strip().split("\n"):
        line = line.strip()
        if line:
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return records


# --- Request ID Tests ---


def test_request_id_generated_when_missing():
    """X-Request-ID header should be generated when not provided."""
    app = Starlette(routes=[Route("/", _homepage, methods=["GET"])])
    app.add_middleware(RequestIDMiddleware)

    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200
    assert "x-request-id" in response.headers
    assert response.headers["x-request-id"]


def test_request_id_propagated_when_present():
    """X-Request-ID header should be echoed back when provided."""
    app = Starlette(routes=[Route("/", _homepage, methods=["GET"])])
    app.add_middleware(RequestIDMiddleware)

    client = TestClient(app)
    response = client.get("/", headers={"x-request-id": "custom-id-123"})
    assert response.status_code == 200
    assert response.headers["x-request-id"] == "custom-id-123"


# --- LoggingMiddleware Tests ---


def test_logging_middleware_records_request():
    """LoggingMiddleware should emit request.started and request.completed events."""
    stream = _capture_logs()

    app = Starlette(routes=[Route("/", _homepage, methods=["GET"])])
    app.add_middleware(LoggingMiddleware)

    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200

    records = parse_captured_logs(stream)
    events = [r.get("event") for r in records]
    assert "request.started" in events
    assert "request.completed" in events

    completed = [r for r in records if r.get("event") == "request.completed"][0]
    assert completed["status_code"] == 200
    assert "latency_ms" in completed
    assert completed["method"] == "GET"
    assert completed["path"] == "/"


def test_logging_middleware_records_latency_ms():
    """Completed log should include latency_ms as a number."""
    stream = _capture_logs()

    app = Starlette(routes=[Route("/", _homepage, methods=["GET"])])
    app.add_middleware(LoggingMiddleware)

    client = TestClient(app)
    client.get("/")

    records = parse_captured_logs(stream)
    completed = [r for r in records if r.get("event") == "request.completed"][0]
    assert isinstance(completed["latency_ms"], (int, float))
    assert completed["latency_ms"] >= 0


def test_logging_middleware_redacts_sensitive_headers():
    """Authorization and Cookie headers should be redacted in logs."""
    stream = _capture_logs()

    app = Starlette(routes=[Route("/", _homepage, methods=["GET"])])
    app.add_middleware(LoggingMiddleware)

    client = TestClient(app)
    client.get(
        "/",
        headers={
            "authorization": "Bearer secret-token",
            "cookie": "session=abc123",
            "x-custom-header": "visible",
        },
    )

    records = parse_captured_logs(stream)
    started = [r for r in records if r.get("event") == "request.started"][0]
    headers = started.get("headers", {})

    assert headers.get("authorization") == "***REDACTED***"
    assert headers.get("cookie") == "***REDACTED***"
    assert headers.get("x-custom-header") == "visible"


def test_logging_middleware_records_exception():
    """Failed requests should log request.failed with exception info."""
    stream = _capture_logs()

    app = Starlette(routes=[Route("/", _error_endpoint, methods=["GET"])])
    app.add_middleware(LoggingMiddleware)

    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/")
    assert response.status_code == 500

    records = parse_captured_logs(stream)
    events = [r.get("event") for r in records]
    assert "request.failed" in events


def test_request_id_in_response_header():
    """X-Request-ID should appear in response header when both middlewares used."""
    app = Starlette(routes=[Route("/", _homepage, methods=["GET"])])
    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(LoggingMiddleware)

    client = TestClient(app)
    response = client.get("/", headers={"x-request-id": "trace-id-999"})
    assert response.status_code == 200
    assert response.headers["x-request-id"] == "trace-id-999"


def test_client_ip_captured():
    """Client IP should be captured in request.started logs."""
    stream = _capture_logs()

    app = Starlette(routes=[Route("/", _homepage, methods=["GET"])])
    app.add_middleware(LoggingMiddleware)

    client = TestClient(app)
    client.get("/")

    records = parse_captured_logs(stream)
    started = [r for r in records if r.get("event") == "request.started"][0]
    assert "client_ip" in started


def test_configure_logging_defaults():
    """configure_logging should not raise with default args."""
    configure_logging(json_logs=True, log_level="INFO")
    assert True
