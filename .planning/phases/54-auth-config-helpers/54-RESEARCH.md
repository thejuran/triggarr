# Phase 54: Auth Config & Helpers - Research

**Researched:** 2026-04-14
**Domain:** Python authentication primitives (bcrypt, itsdangerous, Pydantic config modeling)
**Confidence:** HIGH

## Summary

Phase 54 establishes the foundational auth primitives for Triggarr's v2.6 Built-In Authentication milestone. The scope is deliberately narrow: a Pydantic `AuthConfig` model added to the existing `Settings` class, a flat `triggarr/auth.py` helper module (~60-80 lines) containing bcrypt password hashing, itsdangerous cookie signing, and API key generation, plus extending the secret redaction system. No routes, no middleware, no templates.

The standard stack is simple and well-proven: `bcrypt` 5.0.0 for password hashing and `itsdangerous` 2.2.0 for signed cookies. Both are small, stable libraries with minimal APIs. The existing codebase patterns (SecretStr discipline, atomic TOML writes, Pydantic model validators) map directly onto the new auth config requirements with no architectural novelty.

**Primary recommendation:** Add `bcrypt` and `itsdangerous` as explicit dependencies in pyproject.toml, create `AuthConfig` model with SecretStr fields following the established `InstanceConfig` pattern, and implement four pure helper functions in `triggarr/auth.py`.

<user_constraints>

## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Omit `[auth]` section from `DEFAULT_CONFIG` template in `triggarr/config.py`. Pydantic defaults create a valid `AuthConfig()` when the section is missing from TOML. The setup page (Phase 56) writes the `[auth]` section on first-run credential creation.
- **D-02:** `ensure_config()` behavior unchanged -- still exits with code 1 when no config file exists. Auth setup only triggers when config exists but `auth.username` is empty (handled by middleware in Phase 55). Separation of concerns: config file setup vs auth credential setup.
- **D-03:** No config migration needed for v2.5 -> v2.6 upgrade. Existing installs without `[auth]` section get Pydantic defaults (empty username = needs-setup state).
- **D-04:** All auth helpers in a single flat file `triggarr/auth.py`. Functions: password hashing (bcrypt hash + verify), cookie signing (itsdangerous sign + validate with 30-day expiry), API key generation (`secrets.token_hex(16)`), session secret generation (`secrets.token_hex(32)`). ~60-80 lines total.
- **D-05:** All three sensitive `AuthConfig` fields use `SecretStr`: `password_hash`, `api_key`, `session_secret`. Consistent with project convention (instance API keys already use SecretStr).
- **D-06:** TOML serialization follows existing pattern -- call `.get_secret_value()` at write time before `_atomic_toml_write()`, same as instance API key handling in `routes.py` settings save path.
- **D-07:** `collect_secrets()` in `triggarr/startup.py` updated to also gather auth secrets (`api_key`, `session_secret`) for log redaction. `password_hash` included too for completeness.

### Claude's Discretion
- Bcrypt work factor (design spec says 12 rounds default -- follow it)
- Exact function signatures and docstring style (follow existing codebase conventions)
- Whether to add `@property` helpers on `AuthConfig` (e.g., `needs_setup`, `is_disabled`) -- Claude decides based on downstream consumer needs

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope

</user_constraints>

<phase_requirements>

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SETUP-03 | User sees an auto-generated API key with copy button after completing setup | API key generation via `secrets.token_hex(16)` producing 32-char hex string; `api_key` field on AuthConfig with SecretStr |
| LOGIN-02 | User session persists via signed cookie with 30-day expiry across browser restarts | `itsdangerous.TimestampSigner` with `max_age=2592000`; `session_secret` field stored in config |
| LOGIN-05 | User can disable auth via config file only (not UI), with startup warning logged every 60s | `auth_method` field as `Literal["Forms", "Basic", "External", "Disabled"]` with "Forms" default; config round-trip verified |

</phase_requirements>

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Auth config model (AuthConfig) | Config / Models | -- | Pydantic model living alongside existing Settings, no runtime behavior |
| Password hashing | Helper / Library | -- | Pure functions wrapping bcrypt, called by route handlers (Phase 56) |
| Cookie signing | Helper / Library | -- | Pure functions wrapping itsdangerous, called by middleware (Phase 55) |
| API key generation | Helper / Library | -- | Pure function wrapping secrets module, called by setup route (Phase 56) |
| Secret redaction | Startup | -- | Extension of existing `collect_secrets()` pattern |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| bcrypt | 5.0.0 | Password hashing (hash + verify) | Industry standard for password storage; constant-time comparison prevents timing attacks [VERIFIED: pip index] |
| itsdangerous | 2.2.0 | Signed cookie creation and validation with timestamps | Pallets project (Flask ecosystem); stateless session tokens without DB [VERIFIED: pip index] |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| secrets (stdlib) | Python 3.11+ | CSPRNG for API key and session secret generation | Any time a cryptographically random token is needed |
| pydantic | (existing) | AuthConfig model with SecretStr fields | Config validation -- already in project |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| bcrypt | argon2-cffi | Argon2 is newer/stronger but bcrypt is the *arr ecosystem standard; design spec locked bcrypt |
| itsdangerous | PyJWT | JWT is overkill for single-user signed cookies; itsdangerous is simpler and already a Starlette optional dep |

**Installation:**
```bash
uv add bcrypt itsdangerous
```

**CRITICAL FINDING:** `itsdangerous` is NOT available as a transitive dependency of Starlette in this project. It is gated behind `starlette[full]` which is not installed. It MUST be added as an explicit dependency in pyproject.toml alongside bcrypt. [VERIFIED: `importlib.util.find_spec('itsdangerous')` returns None in the project venv]

**Version verification:**
- bcrypt 5.0.0 -- latest on PyPI [VERIFIED: pip index 2026-04-14]
- itsdangerous 2.2.0 -- latest on PyPI [VERIFIED: pip index 2026-04-14]

## Architecture Patterns

### System Architecture Diagram

```
triggarr.toml [auth] section
        |
        v
  Settings.auth: AuthConfig (Pydantic model)
        |
        +--- password_hash: SecretStr ----> auth.hash_password() / auth.verify_password()
        |                                        (bcrypt.hashpw / bcrypt.checkpw)
        |
        +--- api_key: SecretStr ----------> auth.generate_api_key()
        |                                        (secrets.token_hex(16))
        |
        +--- session_secret: SecretStr ---> auth.sign_session() / auth.validate_session()
        |                                        (itsdangerous.TimestampSigner)
        |
        +--- method: Literal[...] -------> Consumed by middleware (Phase 55)
        |
        v
  collect_secrets() --> log redaction filter
```

### Recommended Project Structure
```
triggarr/
  models/
    config.py          # MODIFY: add AuthConfig, add auth field to Settings
  auth.py              # NEW: hash_password, verify_password, sign_session,
                       #       validate_session, generate_api_key, generate_session_secret
  config.py            # READ-ONLY: no changes per D-01 (no [auth] in DEFAULT_CONFIG)
  startup.py           # MODIFY: extend collect_secrets() per D-07
tests/
  test_auth.py         # NEW: unit tests for all auth helpers + AuthConfig model
```

### Pattern 1: SecretStr Field with TOML Round-Trip
**What:** Pydantic SecretStr fields that serialize safely to TOML
**When to use:** Any config field containing sensitive data
**Example:**
```python
# Source: existing pattern in triggarr/models/config.py + triggarr/web/routes.py
from pydantic import BaseModel, SecretStr

class AuthConfig(BaseModel):
    method: Literal["Forms", "Basic", "External", "Disabled"] = "Forms"
    username: str = ""
    password_hash: SecretStr = SecretStr("")
    api_key: SecretStr = SecretStr("")
    session_secret: SecretStr = SecretStr("")

# TOML serialization (at write time only):
d = auth_config.model_dump()
d["password_hash"] = auth_config.password_hash.get_secret_value()
d["api_key"] = auth_config.api_key.get_secret_value()
d["session_secret"] = auth_config.session_secret.get_secret_value()
```

### Pattern 2: Pure Helper Functions
**What:** Stateless functions that wrap cryptographic libraries
**When to use:** Auth operations called from multiple consumers (routes, middleware)
**Example:**
```python
# Source: bcrypt PyPI docs + itsdangerous docs
import bcrypt
import secrets
from itsdangerous import TimestampSigner, SignatureExpired, BadSignature

def hash_password(plaintext: str) -> str:
    """Hash a plaintext password with bcrypt (12 rounds)."""
    return bcrypt.hashpw(plaintext.encode(), bcrypt.gensalt(rounds=12)).decode()

def verify_password(plaintext: str, hashed: str) -> bool:
    """Verify a plaintext password against a bcrypt hash."""
    return bcrypt.checkpw(plaintext.encode(), hashed.encode())

def generate_api_key() -> str:
    """Generate a 32-character hex API key."""
    return secrets.token_hex(16)

def generate_session_secret() -> str:
    """Generate a 64-character hex session secret."""
    return secrets.token_hex(32)

COOKIE_MAX_AGE = 30 * 24 * 60 * 60  # 30 days in seconds

def sign_session(username: str, secret: str) -> str:
    """Create a signed session cookie value."""
    signer = TimestampSigner(secret)
    return signer.sign(username).decode()

def validate_session(cookie_value: str, secret: str) -> str | None:
    """Validate a signed session cookie, returns username or None."""
    signer = TimestampSigner(secret)
    try:
        return signer.unsign(cookie_value, max_age=COOKIE_MAX_AGE).decode()
    except (SignatureExpired, BadSignature):
        return None
```

### Anti-Patterns to Avoid
- **Storing plaintext passwords:** Always hash before writing to config. The `password_hash` field name makes this explicit.
- **Creating TimestampSigner once at module level:** The signer needs the session_secret from config, which isn't available at import time. Create per-call.
- **Using `get_secret_value()` in log messages or string formatting:** Only call at HTTP client init, TOML write, or crypto operation. The redacting sink is a safety net, not primary defense.
- **Importing bcrypt at module level without try/except in tests:** bcrypt has native extensions; ensure it's in dev dependencies too.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Password hashing | Custom SHA/PBKDF2 wrapper | bcrypt.hashpw + bcrypt.checkpw | Constant-time comparison, salt management, work factor all handled |
| Signed cookies | Custom HMAC + base64 | itsdangerous.TimestampSigner | Timestamp handling, expiry checking, safe serialization all built-in |
| Random token generation | `random.choice(hex_chars)` | `secrets.token_hex()` | CSPRNG vs PRNG; `random` module is NOT cryptographically secure |
| Config validation | Manual TOML parsing + type checking | Pydantic BaseModel | Already the project standard; handles SecretStr, defaults, validators |

**Key insight:** Every function in `auth.py` is a thin wrapper around a battle-tested library. The value is in the consistent interface and keeping crypto calls out of route/middleware code.

## Common Pitfalls

### Pitfall 1: bcrypt 72-byte password limit
**What goes wrong:** bcrypt 5.0.0 raises ValueError if password exceeds 72 bytes (previous versions silently truncated)
**Why it happens:** bcrypt algorithm specification limits input to 72 bytes
**How to avoid:** For a single-user homelab app this is extremely unlikely. If defensive: check `len(password.encode()) <= 72` before hashing and return an error. The design spec does not include password complexity rules, so a simple length check at the route level (Phase 56) is sufficient.
**Warning signs:** ValueError exception from `bcrypt.hashpw()`

### Pitfall 2: itsdangerous is NOT a transitive dependency
**What goes wrong:** Import fails at runtime because itsdangerous is not installed
**Why it happens:** The CONTEXT.md and design spec state itsdangerous is "available as Starlette transitive dependency" -- but Starlette only includes it with the `[full]` extra, which is not used in this project
**How to avoid:** Add `itsdangerous` as an explicit dependency in pyproject.toml [VERIFIED: find_spec returns None]
**Warning signs:** `ModuleNotFoundError: No module named 'itsdangerous'`

### Pitfall 3: SecretStr TOML deserialization
**What goes wrong:** Pydantic can't load SecretStr from TOML string values automatically
**Why it happens:** pydantic-settings TOML loader passes raw strings; SecretStr constructor accepts strings, so this actually works. But `model_dump()` returns SecretStr objects, not strings.
**How to avoid:** When serializing for TOML write, extract values: `cfg.api_key.get_secret_value()`. The existing codebase already does this for instance API keys (see `routes.py` line 152). [VERIFIED: codebase grep]
**Warning signs:** `tomli_w` raises TypeError on SecretStr objects

### Pitfall 4: Config round-trip with missing [auth] section
**What goes wrong:** Saving config might drop the auth section or writing config without auth might fail validation
**Why it happens:** `load_settings()` reads raw TOML dict and passes to `Settings(**data)`. If `[auth]` is absent, Pydantic uses defaults. When saving back, the auth section must be explicitly included.
**How to avoid:** Per D-01, Pydantic defaults handle missing section on load. Write path (Phase 56) must include auth dict in TOML output. Test the round-trip: load config without `[auth]` -> verify defaults -> save with `[auth]` -> reload -> verify values.
**Warning signs:** Auth config lost after save/reload cycle

### Pitfall 5: bcrypt bytes vs strings
**What goes wrong:** TypeError because bcrypt functions require bytes, not str
**Why it happens:** `bcrypt.hashpw()` and `bcrypt.checkpw()` both accept bytes. The hash is also returned as bytes.
**How to avoid:** Encode input: `password.encode()`. Decode output: `.decode()` for string storage. The helper functions handle this conversion so callers work with strings only.
**Warning signs:** `TypeError: Unicode-objects must be encoded before hashing`

## Code Examples

### AuthConfig Model (following existing patterns)
```python
# Source: existing InstanceConfig pattern in triggarr/models/config.py
from typing import Literal
from pydantic import BaseModel, SecretStr

class AuthConfig(BaseModel):
    """Authentication configuration for Triggarr.

    When username is empty, the app is in 'needs setup' state.
    When method is 'Disabled', all endpoints are accessible without auth.
    """

    method: Literal["Forms", "Basic", "External", "Disabled"] = "Forms"
    username: str = ""
    password_hash: SecretStr = SecretStr("")
    api_key: SecretStr = SecretStr("")
    session_secret: SecretStr = SecretStr("")

    @property
    def needs_setup(self) -> bool:
        """True when credentials have not been configured yet."""
        return not self.username

    @property
    def is_disabled(self) -> bool:
        """True when auth is explicitly disabled via config."""
        return self.method == "Disabled"
```

### Extending collect_secrets() (D-07)
```python
# Source: existing pattern in triggarr/startup.py lines 49-68
def collect_secrets(settings: Settings) -> list[str]:
    secrets: list[str] = []
    # Existing: instance API keys
    for app_type in APP_TYPES:
        for cfg in getattr(settings, app_type).values():
            value = cfg.api_key.get_secret_value()
            if value:
                secrets.append(value)
    # New: auth secrets (D-07)
    auth = settings.auth
    for field in (auth.password_hash, auth.api_key, auth.session_secret):
        value = field.get_secret_value()
        if value:
            secrets.append(value)
    return secrets
```

### Test Pattern (following existing test_config.py style)
```python
# Source: existing test patterns in tests/test_config.py
import tomli_w
import tomllib

def test_auth_config_defaults():
    """AuthConfig with no args produces needs-setup state."""
    settings = Settings()
    assert settings.auth.needs_setup is True
    assert settings.auth.method == "Forms"
    assert settings.auth.api_key.get_secret_value() == ""

def test_auth_disabled_round_trip(tmp_path):
    """Disabled auth method persists through TOML save/load."""
    config_path = tmp_path / "triggarr.toml"
    data = {
        "general": {"log_level": "info"},
        "auth": {"method": "Disabled", "username": "admin",
                 "password_hash": "hash", "api_key": "key",
                 "session_secret": "secret"},
    }
    _atomic_toml_write(config_path, data)
    loaded = load_settings(config_path)
    assert loaded.auth.method == "Disabled"
    assert loaded.auth.is_disabled is True
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| bcrypt silent 72-byte truncation | ValueError on >72 bytes | bcrypt 5.0.0 (Sep 2025) | Must handle or prevent long passwords |
| bcrypt C implementation | bcrypt Rust implementation | bcrypt 4.0.0 | Build requires Rust compiler (handled by prebuilt wheels) |
| itsdangerous as Starlette core dep | itsdangerous gated behind starlette[full] | Starlette ~0.28+ | Must add as explicit dependency |

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `@property` helpers (`needs_setup`, `is_disabled`) on AuthConfig will simplify downstream middleware logic | Code Examples | LOW -- trivial to add/remove later; Claude's Discretion area |
| A2 | bcrypt 5.0.0 prebuilt wheels available for all project target platforms (amd64 Linux Docker, macOS dev) | Standard Stack | LOW -- bcrypt has broad wheel coverage; verified version exists on PyPI |

## Open Questions

1. **bcrypt in Docker build**
   - What we know: bcrypt 5.0.0 uses Rust backend, ships prebuilt wheels for common platforms
   - What's unclear: Whether the project's Docker base image (likely python:3.11-slim) has compatible wheels or needs build tools
   - Recommendation: Test `uv add bcrypt` in Docker build during implementation; if wheel unavailable, add `--only-binary bcrypt` constraint

## Project Constraints (from CLAUDE.md)

- Python 3.11+, ruff linting (E, F, I, UP, B, SIM), line length 120
- SecretStr for all API keys -- call `.get_secret_value()` only at HTTP client init or TOML write
- Loguru for logging with custom redacting sink (never print/logging module)
- Atomic file writes (write-then-rename) for config and state
- pytest-asyncio with asyncio_mode=auto
- Deep code review before push: security, correctness, resilience, Docker, config checks

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | All | Yes | 3.11+ | -- |
| uv | Dependency management | Yes | (installed) | -- |
| pytest | Tests | Yes | >=9.0.3 (dev dep) | -- |
| bcrypt | Password hashing | No (not yet installed) | 5.0.0 target | `uv add bcrypt` |
| itsdangerous | Cookie signing | No (not installed, NOT transitive) | 2.2.0 target | `uv add itsdangerous` |

**Missing dependencies with no fallback:**
- `bcrypt` and `itsdangerous` must be added to pyproject.toml dependencies

**Missing dependencies with fallback:**
- None

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest >= 9.0.3 + pytest-asyncio |
| Config file | pyproject.toml `[tool.pytest.ini_options]` |
| Quick run command | `uv run pytest tests/test_auth.py -x -q` |
| Full suite command | `uv run pytest tests/ -x -q` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SETUP-03 | API key generation produces 32-char hex | unit | `uv run pytest tests/test_auth.py::test_generate_api_key -x` | No -- Wave 0 |
| LOGIN-02 | Cookie sign/validate with 30-day expiry | unit | `uv run pytest tests/test_auth.py::test_sign_validate_session -x` | No -- Wave 0 |
| LOGIN-02 | Expired cookie rejected | unit | `uv run pytest tests/test_auth.py::test_expired_session_rejected -x` | No -- Wave 0 |
| LOGIN-05 | Disabled mode accepted by AuthConfig | unit | `uv run pytest tests/test_auth.py::test_auth_disabled_config -x` | No -- Wave 0 |
| LOGIN-05 | Disabled mode round-trips through TOML | unit | `uv run pytest tests/test_auth.py::test_disabled_round_trip -x` | No -- Wave 0 |
| D-05 | SecretStr fields mask in repr/str | unit | `uv run pytest tests/test_auth.py::test_secretstr_masking -x` | No -- Wave 0 |
| D-07 | collect_secrets includes auth secrets | unit | `uv run pytest tests/test_auth.py::test_collect_secrets_auth -x` | No -- Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/test_auth.py -x -q`
- **Per wave merge:** `uv run pytest tests/ -x -q`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/test_auth.py` -- covers SETUP-03, LOGIN-02, LOGIN-05, D-05, D-07
- [ ] Framework install: `uv add bcrypt itsdangerous` -- dependencies not yet available

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | Yes | bcrypt (12 rounds) for password hashing; constant-time checkpw |
| V3 Session Management | Yes | itsdangerous TimestampSigner with 30-day max_age |
| V4 Access Control | No | Handled by middleware in Phase 55 |
| V5 Input Validation | Yes | Pydantic model validation for AuthConfig fields |
| V6 Cryptography | Yes | secrets.token_hex (CSPRNG) for API key and session secret; bcrypt for password storage -- never hand-roll |

### Known Threat Patterns for Auth Primitives

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Plaintext password storage | Information Disclosure | bcrypt hash before any persistence |
| Timing attack on password comparison | Information Disclosure | bcrypt.checkpw is constant-time by design |
| Weak random token generation | Spoofing | secrets module (CSPRNG), not random module |
| Cookie tampering | Tampering | HMAC signing via itsdangerous |
| Session secret in logs | Information Disclosure | SecretStr + collect_secrets() redaction |

## Sources

### Primary (HIGH confidence)
- bcrypt 5.0.0 PyPI page and changelog -- API, version, breaking changes [VERIFIED: pip index, PyPI page, GitHub changelog]
- itsdangerous 2.2.0 -- TimestampSigner API, sign/unsign/max_age [CITED: itsdangerous.palletsprojects.com/en/stable/timed/]
- Existing codebase: `triggarr/models/config.py`, `triggarr/config.py`, `triggarr/startup.py`, `triggarr/web/routes.py` -- patterns for SecretStr, atomic writes, collect_secrets [VERIFIED: codebase read]
- Design spec: `docs/superpowers/specs/2026-04-14-built-in-auth-design.md` [VERIFIED: file read]

### Secondary (MEDIUM confidence)
- Starlette itsdangerous dependency gating -- confirmed via `importlib.metadata.requires('starlette')` showing `itsdangerous; extra == 'full'` [VERIFIED: runtime check]

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - both libraries verified on PyPI, APIs confirmed via docs
- Architecture: HIGH - follows established codebase patterns exactly, all reference files read
- Pitfalls: HIGH - itsdangerous transitive dep issue verified empirically; bcrypt 5.0 breaking change confirmed via changelog

**Research date:** 2026-04-14
**Valid until:** 2026-05-14 (stable libraries, unlikely to change)
