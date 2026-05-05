"""Shared web security helpers."""

from __future__ import annotations

from starlette.requests import Request


def is_secure_request(request: Request) -> bool:
    """Return True when the ASGI request scheme is HTTPS.

    Uvicorn/trusted-proxy processing is responsible for translating accepted
    forwarded proto headers into ``request.url.scheme``. Application code must
    not read ``X-Forwarded-Proto`` directly for cookie security decisions.
    """
    return request.url.scheme == "https"
