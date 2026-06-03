# Phase 71: Presentation Rewrite - Pattern Map

**Mapped:** 2026-06-02
**Files analyzed:** 9 new/modified files
**Analogs found:** 9 / 9

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `triggarr/web/validation.py` (add function) | utility | request-response | Same file — `validate_arr_url()` lines 56-108 | exact (sibling function) |
| `triggarr/models/config.py` (add field_validator) | model | CRUD | Same file — `reject_apikey_in_url` field_validator lines 65-89 | exact (sibling validator) |
| `tests/test_validation.py` (add class) | test | — | Same file — `TestValidateArrUrl` class lines 11-141 | exact (sibling class) |
| `tests/test_config.py` (add tests) | test | — | Same file — `test_instance_url_rejects_apikey` / `test_instance_url_accepts_without_apikey` (parametrize pattern) + `test_toml_*` (TOML load pattern) | exact |
| `CHANGELOG.md` (add v2.9.0 entry) | docs | — | Same file — `## v2.8.1 (2026-05-31)` and `## v2.8.0 (2026-06-01)` entries lines 3-35 | exact (entry format) |
| `README.md` (full rewrite) | docs | — | Current `README.md` (source) + `~/seedsyncarr/README.md` (target structure) | structural reference |
| `SECURITY.md` | docs | — | Current `SECURITY.md` | update in-place |
| `.github/ISSUE_TEMPLATE/bug-report.yml` | config | — | Same file — existing dropdown structure | exact (list update) |
| `CONTRIBUTING.md` | docs | — | Current `CONTRIBUTING.md` | update in-place |

---

## Pattern Assignments

### `triggarr/web/validation.py` — add `validate_arr_url_config()`

**Analog:** `validate_arr_url()` in the same file, lines 56-108

**Full analog to copy and modify** (lines 56-108):
```python
def validate_arr_url(url: str) -> tuple[bool, str]:
    """Validate a user-supplied *arr application URL.

    Empty URLs are allowed (app is disabled). Otherwise the URL must use
    http or https, have a hostname, and not point at cloud metadata or
    link-local addresses. Private-network IPs (10.x, 192.168.x, etc.)
    are intentionally allowed because *arr apps run on local networks.

    Args:
        url: The URL string from the settings form.

    Returns:
        A ``(valid, error_message)`` tuple. ``valid`` is True when the URL
        is acceptable; ``error_message`` is empty on success.
    """
    if not url or not url.strip():
        return (True, "")

    parsed = urlparse(url.strip())

    if parsed.scheme not in {"http", "https"}:
        return (False, "URL scheme must be http or https")

    hostname = parsed.hostname
    if hostname is None:
        return (False, "URL has no hostname")

    if hostname in BLOCKED_HOSTS:
        return (False, "Blocked hostname")

    try:
        addr = ipaddress.ip_address(hostname)
        if addr.is_link_local or addr.is_loopback or addr.is_unspecified or addr.is_multicast:
            return (False, "Blocked address")
        # Check IPv4-mapped IPv6 addresses (e.g., ::ffff:127.0.0.1) per D-10
        if isinstance(addr, ipaddress.IPv6Address) and addr.ipv4_mapped:
            mapped = addr.ipv4_mapped
            if (
                mapped.is_link_local
                or mapped.is_loopback
                or mapped.is_unspecified
                or mapped.is_multicast
                or any(mapped in net for net in _BLOCKED_NETWORKS)
            ):
                return (False, "Blocked address")
    except ValueError:
        # Not an IP literal -- DNS name falls through
        pass

    return (True, "")
```

**The single diff between analog and new function:**
- Remove `addr.is_loopback` from the direct-address check (line 88 in original)
- Remove `mapped.is_loopback` from the IPv4-mapped IPv6 check (line 95 in original)
- Update docstring: "config-load variant", "loopback permitted", reference D-02
- New function name: `validate_arr_url_config`

**Imports:** No new imports needed — `ipaddress`, `urlparse`, `BLOCKED_HOSTS`, `_BLOCKED_NETWORKS` already present at lines 9-24.

**Placement:** Add immediately after `validate_arr_url` closes at line 108, before `safe_int` at line 111.

---

### `triggarr/models/config.py` — add `@field_validator("url")` on `InstanceConfig`

**Analog:** `reject_apikey_in_url` field_validator, lines 65-89

**Full analog to copy and adapt** (lines 65-89):
```python
@field_validator("url")
@classmethod
def reject_apikey_in_url(cls, v: str) -> str:
    """SEC-02 D-06/D-07/D-08: Reject URLs whose query string contains an apikey= parameter
    (any case, including the empty-value variant and URL-encoded forms like apikey%3D...).

    The validator runs at model construction time -- BEFORE the settings POST handler
    acquires search_lock and BEFORE _atomic_toml_write runs -- so a URL carrying an
    embedded API key never reaches the filesystem. Per D-07 the rule is narrow: only
    apikey= keys (any case) are rejected; legitimate non-apikey query parameters
    (?base=/sonarr, ?token=foo) remain valid for reverse-proxy/subpath setups.
    """
    if not v:
        return v
    parsed = urlparse(v)
    if not parsed.query:
        return v
    for key, _value in parse_qsl(parsed.query, keep_blank_values=True):
        if key.lower().startswith("apikey"):
            msg = "URL must not contain an apikey= query parameter. Use the API Key field instead."
            raise ValueError(msg)
    return v
```

**New validator pattern** (define AFTER `reject_apikey_in_url`, before `at_least_one_search_count` at line 91):
```python
@field_validator("url")
@classmethod
def validate_url_ssrf(cls, v: str) -> str:
    """D-01/D-02: Apply relaxed SSRF validation at config-load time.

    Permits loopback/localhost (legitimate same-host *arr installs) but still blocks
    cloud-metadata (169.254.169.254, metadata.google.internal, etc.) and link-local
    addresses. Raises ValueError on violation so pydantic surfaces a ValidationError.
    """
    from triggarr.web.validation import validate_arr_url_config
    ok, err = validate_arr_url_config(v)
    if not ok:
        raise ValueError(err)
    return v
```

**Key constraints:**
- Decorator + `@classmethod` pattern is identical to `reject_apikey_in_url` — copy exactly
- Return type is `str` (field value pass-through on success, `ValueError` on failure)
- Must be placed AFTER `reject_apikey_in_url` — Pydantic v2 runs field validators for the same field in definition order
- The local import `from triggarr.web.validation import validate_arr_url_config` avoids a circular import at module level (models.config is imported early; web.validation imports nothing from models)

---

### `tests/test_validation.py` — add `TestValidateArrUrlConfig` class

**Analog:** `TestValidateArrUrl` class, lines 11-141

**Class structure to mirror** (lines 11-14, method signature pattern):
```python
class TestValidateArrUrl:
    """URL validation: scheme enforcement, SSRF blocking, private-IP allow."""

    def test_valid_http_url(self) -> None:
        ok, err = validate_arr_url("http://radarr:7878")
        assert ok is True
        assert err == ""
```

**Method naming convention from analog** (lines 14-141):
- `test_valid_http_url` / `test_valid_https_url` / `test_empty_string_allowed` — positive cases
- `test_ftp_scheme_rejected` / `test_cloud_metadata_ip_blocked` / `test_link_local_ip_blocked` — negative cases with `assert ok is False`
- Error string assertions use `assert "blocked" in err.lower()` or `assert "scheme" in err.lower()` — substring not exact match

**Import line to add** (line 5 in test file, update the existing import):
```python
from triggarr.web.validation import (
    safe_int,
    safe_log_level,
    validate_arr_url,
    validate_arr_url_config,  # new
    validate_instance_name,
)
```

**New class skeleton** (place after `TestValidateArrUrl` closes at line 141, before `TestSafeInt` at line 147):
```python
class TestValidateArrUrlConfig:
    """Config-load URL validation: loopback allowed, metadata/link-local still blocked."""

    def test_empty_string_allowed(self) -> None:
        ok, err = validate_arr_url_config("")
        assert ok is True
        assert err == ""

    def test_loopback_ipv4_allowed(self) -> None:
        ok, err = validate_arr_url_config("http://127.0.0.1:7878")
        assert ok is True
        assert err == ""

    def test_localhost_hostname_allowed(self) -> None:
        ok, err = validate_arr_url_config("http://localhost:7878")
        assert ok is True
        assert err == ""

    def test_private_192_168_allowed(self) -> None:
        ok, err = validate_arr_url_config("http://192.168.1.100:7878")
        assert ok is True
        assert err == ""

    def test_cloud_metadata_ip_blocked(self) -> None:
        ok, err = validate_arr_url_config("http://169.254.169.254/latest/meta-data")
        assert ok is False

    def test_link_local_ip_blocked(self) -> None:
        ok, err = validate_arr_url_config("http://169.254.42.42")
        assert ok is False
        assert "blocked" in err.lower()

    def test_gcp_metadata_hostname_blocked(self) -> None:
        ok, err = validate_arr_url_config("http://metadata.google.internal")
        assert ok is False
```

**No `@pytest.mark.parametrize` used** in `TestValidateArrUrl` — mirror the one-method-per-case style.

---

### `tests/test_config.py` — add SSRF integration tests

**Analog 1 — ValidationError pattern** (lines 250-268, parametrize variant):
```python
@pytest.mark.parametrize(
    "url",
    [
        "http://radarr:7878?apikey=secret",
        ...
    ],
)
def test_instance_url_rejects_apikey(url: str) -> None:
    """..."""
    with pytest.raises(ValidationError, match="apikey="):
        InstanceConfig(url=url, api_key=SecretStr("k"), enabled=True)
```

**Analog 2 — success path pattern** (lines 271-286):
```python
@pytest.mark.parametrize(
    "url",
    [
        "",
        "http://radarr:7878",
        ...
    ],
)
def test_instance_url_accepts_without_apikey(url: str) -> None:
    """..."""
    cfg = InstanceConfig(url=url, api_key=SecretStr("k"), enabled=True)
    assert cfg.url == url
```

**Analog 3 — TOML load integration pattern** (lines 57-72):
```python
def test_settings_loads_from_toml(tmp_path: Path) -> None:
    """Valid TOML config loads all sections correctly."""
    config_file = tmp_path / "triggarr.toml"
    config_file.write_text(VALID_TOML)
    settings = load_settings(config_file)
    assert settings.radarr["Default"].url == "http://radarr:7878"
```

**New tests to add** (place in a new section after the SEC-02 block ending at line 286, before `test_multi_instance_radarr` at line 289):

```python
# ---------------------------------------------------------------------------
# D-01/D-02/D-03: InstanceConfig config-load SSRF validation (relaxed variant)
# ---------------------------------------------------------------------------

def test_instance_config_loopback_url_valid() -> None:
    """D-02: InstanceConfig accepts loopback URL (same-host *arr is a legitimate homelab pattern)."""
    cfg = InstanceConfig(url="http://127.0.0.1:7878", api_key=SecretStr("k"), enabled=True)
    assert cfg.url == "http://127.0.0.1:7878"


def test_instance_config_localhost_url_valid() -> None:
    """D-02: InstanceConfig accepts localhost hostname (falls through DNS branch)."""
    cfg = InstanceConfig(url="http://localhost:7878", api_key=SecretStr("k"), enabled=True)
    assert cfg.url == "http://localhost:7878"


def test_instance_config_metadata_url_raises() -> None:
    """D-01: InstanceConfig rejects cloud-metadata URL at config-load time."""
    with pytest.raises(ValidationError):
        InstanceConfig(url="http://169.254.169.254/latest/meta-data", api_key=SecretStr("k"), enabled=True)


def test_instance_config_link_local_url_raises() -> None:
    """D-01: InstanceConfig rejects link-local IP at config-load time."""
    with pytest.raises(ValidationError):
        InstanceConfig(url="http://169.254.42.42", api_key=SecretStr("k"), enabled=True)
```

**Import to verify already present** (line 13 in test file): `from pydantic import SecretStr, ValidationError` — already imported.

---

### `CHANGELOG.md` — add `## v2.9.0` entry

**Analog:** `## v2.8.1 (2026-05-31)` entry (lines 3-9) as the canonical one-category template; `## v2.8.0 (2026-06-01)` (lines 11-35) as the multi-category template.

**Format rules** (confirmed from `changelog.py` parser):
- Version header: `## vX.Y.Z (YYYY-MM-DD)` — nothing else on the line
- Optional one-paragraph summary after the header (blank line before first `*`)
- Category line: `* CategoryName:` — colon at end, NOTHING after the colon, no trailing text
- Bullet line: `  * Bullet text` — exactly two spaces before `*`
- Blank line between version header and summary, blank line between summary and first category, blank line between category header and its bullets

**Canonical two-category template to copy structure from** (lines 3-9):
```markdown
## v2.8.1 (2026-05-31)

Security patch release: password changes now invalidate other sessions.

* Security:

  * Changing your password now logs out all other active sessions. ...
```

**v2.9.0 entry must be inserted at line 1** (before the current `## v2.8.1` entry), following this structure:
```markdown
## v2.9.0 (<date-at-execution-time>)

<one-sentence summary — user-facing scope of changes>

* Security:

  * URL validation for *arr instances now applies at config-load time, not only via the web UI. Cloud-metadata and link-local addresses are blocked on startup; loopback addresses are permitted for same-host deployments.

* Fixes:

  * Fixed the manual-search failure counter not resetting after a successful cycle, which could prematurely pause searches on instances that recovered.

* Documentation:

  * Full README rewrite: benefit-led introduction, accurate Quick Start, corrected pip install and systemd unit instructions, tag-filtering fail-open behavior documented.
  * SECURITY.md updated to reflect v2.8/v2.8.1 hardening and clarify at-rest-plaintext caveat.
```

---

### `.github/ISSUE_TEMPLATE/bug-report.yml` — version + App Type dropdown update

**Analog:** Current file lines 6-14 (version dropdown) and lines 29-34 (App Type dropdown).

**Current version options** (lines 9-14) to be replaced:
```yaml
      options:
        - v2.3
        - v2.2
        - v2.1
        - Older
```

**Replacement version options** (D-10):
```yaml
      options:
        - v2.8.1
        - v2.8
        - v2.7
        - v2.6
        - v2.5
        - v2.4
        - Older
```

**Current App Type options** (lines 31-34) to be replaced:
```yaml
      options:
        - Radarr
        - Sonarr
        - Both
```

**Replacement App Type options** (D-10):
```yaml
      options:
        - Radarr
        - Sonarr
        - Lidarr
        - All
```

**CRITICAL — `test_github_templates.py` has snapshot assertions that will break:**
- `test_version_dropdown_options` (line 31-33) asserts `v2.3`, `v2.2`, `v2.1`, `Older` are present — MUST update to assert new versions
- `test_app_type_dropdown_options` (line 39-41) asserts `Radarr`, `Sonarr`, `Both` are present — MUST update to assert `Lidarr`, `All` (and drop `Both`)

**Update `tests/test_github_templates.py` in the same task:**
```python
# Line 31-33 — replace version assertions:
def test_version_dropdown_options(self):
    content = self.path.read_text()
    for version in ("v2.8.1", "v2.8", "v2.7", "v2.6", "v2.5", "v2.4", "Older"):
        assert version in content, f"Version dropdown must include '{version}'"

# Line 39-41 — replace app type assertions:
def test_app_type_dropdown_options(self):
    content = self.path.read_text()
    for app in ("Radarr", "Sonarr", "Lidarr", "All"):
        assert app in content, f"App type dropdown must include '{app}'"
```

---

### `README.md` — full rewrite

**Analog structure (current file):** 277 lines; current order: `# Triggarr` → badges → one-liner → Table of Contents → Features → Screenshots → Install → Configuration Reference → Security Model → Development.

**Target structure (D-04):** Drop ToC. Section order:
1. `<div align="center">` centered header (H1 + 4 badges + benefit tagline)
2. Above-the-fold screenshot `<img>` or `![alt](path)` 
3. `## Quick Start`
4. `## Features`
5. `## How It Works`
6. `## Install`
7. `## Configuration Reference`
8. `## Screenshots`
9. `## Security Model`
10. `## Related Projects`
11. `## Contributing / Development`

**Header pattern (D-05)** — centered HTML block, no wordmark image:
```html
<div align="center">

# Triggarr

[![CI](https://github.com/thejuran/triggarr/actions/workflows/ci.yml/badge.svg)](https://github.com/thejuran/triggarr/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/thejuran/triggarr)](https://github.com/thejuran/triggarr/releases)
[![Docker](https://img.shields.io/badge/docker-ghcr.io-blue)](https://ghcr.io/thejuran/triggarr)
[![License](https://img.shields.io/github/license/thejuran/triggarr)](LICENSE)

**[benefit-led one-liner]**

</div>
```

**Screenshot refs** — drop the `?v=2` cache-buster from current lines 36-40; update alt text to be descriptive. Files stay at `docs/screenshots/dashboard.png`, `history.png`, `settings.png`.

**TOML block constraint (Pitfall 1):** The Configuration Reference section contains TOML code blocks. They must remain valid Pydantic-parseable TOML. `tests/test_docs_accuracy.py:85-100` parses every ` ```toml ``` ` block — preserve or replace with equally valid TOML.

**Tailwind version fix (D-07):** Current watch command at README:275:
```bash
uv run tailwindcss -i triggarr/static/css/input.css -o triggarr/static/css/output.css --watch
```
Replace with (prepend version export):
```bash
TAILWINDCSS_VERSION=v4.2.2 uv run tailwindcss -i triggarr/static/css/input.css -o triggarr/static/css/output.css --watch
```

---

### `SECURITY.md` — reconcile with v2.8/v2.8.1 hardening (D-08/D-09)

**Analog:** Current `SECURITY.md` (edit in-place).

**Line 39 claim to update** (current):
```
URL inputs are validated against an allow-list of schemes (http, https) and a block-list of cloud metadata and link-local hostnames to prevent server-side request forgery.
```
**Post-D-01/D-02 accurate replacement:**
```
URL inputs are validated against an allow-list of schemes (http and https) and a block-list of cloud-metadata and link-local hostnames. This validation applies both to URLs submitted via the web settings form (which additionally rejects loopback addresses) and to URLs loaded from triggarr.toml at startup.
```

**At-rest-plaintext caveat to add** (D-09): "`SecretStr` protects repr/log/HTML exposure — API keys, auth credentials, and the session secret are plaintext in `triggarr.toml`. Protect them with file permissions (`0600`, set by Triggarr on write) and volume security."

**v2.8/v2.8.1 hardening list to enumerate** (D-08 — confirmed from code):
- CSP `script-src` nonce per request (no `unsafe-inline`) — `web/middleware.py:43-57`
- Session-secret rotation on password change — `web/routes.py:1449-1481`
- `apikey=` URL rejection at model construction — `models/config.py:65-89`
- Basic-auth control-character validation — `web/middleware.py:177-186`
- Session-secret startup length check — `startup.py:49-69`

---

### `CONTRIBUTING.md` — Tailwind version alignment (D-07)

**Analog:** Current `CONTRIBUTING.md` (edit in-place, line 20).

**Current watch command at line 20:**
```bash
uv run tailwindcss -i triggarr/static/css/input.css -o triggarr/static/css/output.css --watch
```
**Replacement** (same as README fix — prepend version):
```bash
TAILWINDCSS_VERSION=v4.2.2 uv run tailwindcss -i triggarr/static/css/input.css -o triggarr/static/css/output.css --watch
```

---

## Shared Patterns

### `tuple[bool, str]` Return Convention
**Source:** `triggarr/web/validation.py` — all validation helpers  
**Apply to:** `validate_arr_url_config()`  
Return `(True, "")` on success; `(False, "error message")` on failure. Never raise — the field_validator wrapper raises `ValueError`.

### `@field_validator` + `@classmethod` Declaration Order
**Source:** `triggarr/models/config.py` lines 65-66  
**Apply to:** new `validate_url_ssrf` validator  
```python
@field_validator("url")
@classmethod
def validate_url_ssrf(cls, v: str) -> str:
```
The `@field_validator` decorator must come before `@classmethod`. This is the only order the project uses.

### `pytest.raises(ValidationError)` for model-level rejection
**Source:** `tests/test_config.py` lines 125-133, 250-268  
**Apply to:** new SSRF config tests  
```python
with pytest.raises(ValidationError, match="..."):
    InstanceConfig(url=url, api_key=SecretStr("k"), enabled=True)
```
Use `match=` only when the error message substring is meaningful to document. For SSRF tests the error text comes from `validate_arr_url_config` which returns generic `"Blocked address"` / `"Blocked hostname"` — omit `match=` or use `match="Blocked"`.

### No `asyncio_mode` Required
None of the new tests involve async — all `InstanceConfig` and `validate_arr_url_config` calls are synchronous. Do not add `@pytest.mark.asyncio`. The existing test files have no `async def` in the classes being extended.

---

## No Analog Found

None. All files have exact or role-match analogs in the codebase.

---

## Metadata

**Analog search scope:** `triggarr/web/`, `triggarr/models/`, `tests/`, `.github/ISSUE_TEMPLATE/`, project root docs
**Files read:** `validation.py`, `models/config.py`, `tests/test_validation.py`, `tests/test_config.py`, `tests/test_github_templates.py`, `CHANGELOG.md` (first 60 lines), `.github/ISSUE_TEMPLATE/bug-report.yml`, `README.md` (first 50 lines)
**Pattern extraction date:** 2026-06-02

---

## PATTERN MAPPING COMPLETE
