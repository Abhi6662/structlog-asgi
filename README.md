# structlog-asgi

Structured JSON logging & X-Request-ID correlation middleware for FastAPI/ASGI.

## Features

- **Structured JSON logs** — every request/response logged as machine-readable JSON
- **X-Request-ID correlation** — unique request ID propagated via contextvars and response header
- **Latency tracking** — response time in milliseconds per request
- **Sensitive header redaction** — Authorization, Cookie, API keys masked automatically
- **Exception trace logging** — full traceback captured when handlers raise
- **ASGI-native** — works with any ASGI framework (Starlette, FastAPI, etc.)

## Installation

```bash
pip install structlog-asgi
```

## Usage

```python
from starlette.applications import Starlette
from starlette.routing import Route
from structlog_asgi import LoggingMiddleware, RequestIDMiddleware, configure_logging

configure_logging(json_logs=True, log_level="INFO")

async def homepage(request):
    return PlainTextResponse("OK")

app = Starlette(routes=[Route("/", homepage, methods=["GET"])])
app.add_middleware(RequestIDMiddleware)
app.add_middleware(LoggingMiddleware)
```

## License

MIT
