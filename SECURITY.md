# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 0.1.0   | ✅        |

## Reporting a Vulnerability

Please report security vulnerabilities via GitHub Issues. Do not create public
issues for security concerns. Include details of the affected version, steps to
reproduce, and potential impact.

## Scope

This middleware logs HTTP request/response metadata as structured JSON.
Sensitive header values (Authorization, Cookie, API keys, etc.) are redacted
by default. However, request bodies, query parameters, and non-sensitive
headers are logged in plaintext — ensure sensitive data is not sent in
query strings or unprotected headers.
