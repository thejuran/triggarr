"""Regression test pinning Triggarr's startup against FastAPI's OpenTelemetry
auto-configure environment variables (TELEM-01).

FastAPI intercepts the ASGI ``"lifespan"`` scope inside its own ``__call__``
method before delegating to Triggarr's own lifespan function, so this test
must drive the app through FastAPI's ``TestClient`` acting as a context
manager rather than calling the lifespan context manager directly -- the
direct form never reaches that code path. ``FASTAPI_OTEL_AUTO_CONFIGURE`` is
read once, at ``FastAPI()`` construction time, so it has to be set in the
environment before the app object is built.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.testclient import TestClient

from tests.conftest import make_settings
from triggarr.search.scheduler import create_lifespan
from triggarr.web.routes import router


def test_telemetry_env_vars_do_not_crash_startup(tmp_path, monkeypatch, caplog):
    """TELEM-01: FASTAPI_OTEL_AUTO_CONFIGURE + an OTLP endpoint must not crash startup."""
    monkeypatch.setenv("FASTAPI_OTEL_AUTO_CONFIGURE", "true")
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://127.0.0.1:4318")

    settings = make_settings(radarr_enabled=False, sonarr_enabled=False, lidarr_enabled=False)
    lifespan_fn = create_lifespan(settings, tmp_path / "state.json", tmp_path / "triggarr.toml")
    app = FastAPI(lifespan=lifespan_fn)
    app.include_router(router)

    with caplog.at_level(logging.WARNING, logger="fastapi"), TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    # Prove the auto-configure path actually ran and its failure was absorbed,
    # so this test cannot stay green if FastAPI renames or drops the variable.
    assert "automatic telemetry configuration failed" in caplog.text
