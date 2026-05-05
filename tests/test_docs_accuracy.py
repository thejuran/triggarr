"""Documentation accuracy tests for auth, proxy, and config examples."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

import pytest
from pydantic import ValidationError

from triggarr.models.config import Settings

PROJECT_ROOT = Path(__file__).resolve().parent.parent
README = PROJECT_ROOT / "README.md"
SECURITY = PROJECT_ROOT / "SECURITY.md"
TODO = PROJECT_ROOT / "TODO.md"
TRACKED_DOCS = (README, SECURITY, TODO)


def _read(path: Path) -> str:
    """Read a tracked repository documentation file."""
    relative = path.relative_to(PROJECT_ROOT)
    assert not relative.parts[0].startswith("."), f"docs test must not read ignored/local artifact: {relative}"
    return path.read_text(encoding="utf-8")


def _normalized(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower())


def test_external_auth_docs_require_upstream_authz_and_blocked_direct_access() -> None:
    """External auth docs must describe the upstream trust boundary, not just a bypass switch."""
    for path in (README, SECURITY):
        text = _normalized(_read(path))
        assert "external" in text, f"{path.name} must document External auth mode"
        assert "authentication" in text, f"{path.name} must require upstream authentication for External auth"
        assert "authorization" in text, f"{path.name} must require upstream authorization for External auth"
        assert "direct access" in text, f"{path.name} must warn about direct access to port 8484"
        assert "blocked" in text or "firewalled" in text, f"{path.name} must say direct access is blocked/firewalled"


def test_secure_cookie_docs_use_asgi_scheme_not_direct_forwarded_proto_trust() -> None:
    """Docs may mention X-Forwarded-Proto, but cookie trust must flow through Uvicorn/ASGI scheme."""
    security = _normalized(_read(SECURITY))
    readme = _normalized(_read(README))

    for path, text in ((SECURITY, security), (README, readme)):
        assert "x-forwarded-proto" in text, f"{path.name} should document the forwarded-proto proxy boundary"
        assert "asgi request scheme" in text, f"{path.name} should tie proxy proto handling to ASGI scheme"
        assert "uvicorn" in text, f"{path.name} should identify Uvicorn as the forwarded-header boundary"
        assert "trusted_proxy_ips" in text, f"{path.name} should document the trusted proxy allow-list"

    forbidden_claims = (
        "triggarr trusts the `x-forwarded-proto`",
        "triggarr trusts x-forwarded-proto",
        "carries `x-forwarded-proto: https`",
        "route-level `x-forwarded-proto`",
        "routes trust `x-forwarded-proto`",
        "app route code directly trusts",
        "directly trusts `x-forwarded-proto`",
    )
    combined = f"{security}\n{readme}"
    for claim in forbidden_claims:
        assert claim not in combined, f"docs must not describe direct app-layer forwarded-proto trust: {claim}"


def test_tracked_docs_do_not_reintroduce_stale_auth_or_config_dir_claims() -> None:
    """Known stale docs claims should stay retired."""
    combined = "\n".join(_normalized(_read(path)) for path in TRACKED_DOCS)
    stale_claims = (
        "triggarr has no built-in authentication",
        "no authentication is provided",
        "authentication is not implemented",
        "no authentication / authorization",
        "make config directory configurable",
        "config directory is not configurable",
        "todo: configurable config",
        "todo - configurable config",
    )
    for claim in stale_claims:
        assert claim not in combined, f"stale documentation claim is present: {claim}"


def test_readme_toml_examples_parse_and_validate_as_settings() -> None:
    """README TOML examples should be real Triggarr Settings-shaped TOML."""
    readme = _read(README)
    toml_blocks = re.findall(r"```toml\n(.*?)\n```", readme, flags=re.DOTALL)
    assert toml_blocks, "README should include at least one TOML configuration example"

    for index, block in enumerate(toml_blocks, start=1):
        try:
            data = tomllib.loads(block)
        except tomllib.TOMLDecodeError as exc:
            pytest.fail(f"README TOML block #{index} is invalid TOML: {exc}")

        try:
            Settings.model_validate(data)
        except ValidationError as exc:
            pytest.fail(f"README TOML block #{index} does not validate as Triggarr Settings: {exc}")
