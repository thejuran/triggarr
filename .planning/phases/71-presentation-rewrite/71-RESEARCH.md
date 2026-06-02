# Phase 71: Presentation Rewrite — Research

**Researched:** 2026-06-02
**Domain:** Documentation rewrite (README, SECURITY.md, community health, CHANGELOG) + one SSRF config-load validation code change
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Widen SSRF validation into config-load (code change), NOT scope the doc claim down.
- **D-02:** Config-load uses a relaxed variant: permit loopback/localhost, still block cloud-metadata + link-local. Web-form path stays strict and unchanged at `routes.py:561`.
- **D-03:** Covering test required for the new config-load validation path. Do not delete or skip existing `validate_arr_url` / web-form tests. README:215 and SECURITY.md:39 wording updated to match post-change behavior.
- **D-04:** Full section reorder to mirror SeedSyncarr. Order: Centered header → Above-the-fold screenshot → Quick Start → Features → How It Works → Install → Configuration Reference → Screenshots → Security Model → Related Projects → Contributing/Development. Drop the Table of Contents.
- **D-05:** Header = centered HTML block with `# Triggarr` H1, four badges (CI, Release shields.io/github/v/release/thejuran/triggarr, Docker simplified, License shields.io/github/license/thejuran/triggarr), benefit-led tagline. No wordmark image asset.
- **D-06:** Benefit-led one-liner replaces README:6. Direction: lead with user benefit (e.g. "Radarr, Sonarr, and Lidarr never auto-search for missing or upgrade-eligible media — Triggarr does. Scheduled searches, closed-loop grab tracking, runs in Docker.").
- **D-07:** All correctness/accuracy fixes locked: pip-install line not hardcoded; systemd unit gets `StateDirectory=triggarr`; Docker first-run gets sys.exit(1) explanation; tag-filtering fail-open documented; Tailwind version pinned/aligned.
- **D-08:** Enumerate v2.8/v2.8.1 hardening in SECURITY.md as confident "what we do" list.
- **D-09:** State at-rest-plaintext caveat plainly in SECURITY.md. SecretStr protects repr/log/HTML, NOT disk. Mirror README:212 caveat.
- **D-10:** Fix bug-report.yml version dropdown (v2.8.1, v2.8, v2.7, v2.6, v2.5, v2.4, "Older") and App Type dropdown (add Lidarr and All).
- **D-11:** CHANGELOG.md is the in-app changelog source (Tautulli model). One edit satisfies both.
- **D-12:** v2.9.0 entry lists user-facing changes: SSRF config-load hardening, manual-search failure-counter fix (CHARD-02), docs/presentation overhaul. Date stamped at execution time.
- **D-13:** PREW-05 produces copy-paste text only (GitHub About ≤350 chars, topics, homepage). Cannot apply from session.

### Claude's Discretion

- Exact final README copy/wording within locked structure and one-liner direction.
- Exact Quick Start compose block contents (minimize from current Install Docker block).
- Whether above-the-fold screenshot and Screenshots section use same or different image.
- Exact pip-install resilient pattern (curl+pip vs version-agnostic URL).
- Topics/tags list contents for PREW-05.
- Whether to add a one-line `~/seedsync` cross-link note (optional).

### Deferred Ideas (OUT OF SCOPE)

- Fresh screenshots (PREW-02) — captured via Playwright at NAS walkthrough, not in this phase body. Phase 71 updates refs/alt text only.
- GitHub repo-metadata application (PREW-05) — Phase 71 drafts copy-paste text; maintainer applies in GitHub web UI.
- SeedSyncarr-side reconciliation — SeedSyncarr rises to Triggarr's security bar in its own milestone.
- `~/seedsync` cross-link — optional, not required.
- Config-knob UI debt (DEBT-03/06/07/08), UI-01/02/03 pixel verification — parked to v2.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| PREW-01 | README rewritten: instant one-liner, current screenshots above fold, honest feature list, install/quickstart verified accurate, security posture as selling point | D-04..D-07 + full accuracy audit below |
| PREW-02 | Screenshot refs/alt text updated; fresh captures deferred to NAS walkthrough | `docs/screenshots/dashboard.png`, `history.png`, `settings.png` confirmed present |
| PREW-03 | SECURITY.md reconciled with v2.8/v2.8.1 hardening + at-rest-plaintext caveat | D-08/D-09 + code confirmation below |
| PREW-04 | Community-health files confirmed present and accurate; bug-template gaps fixed | D-10 + file audit below |
| PREW-05 | GitHub About/topics/homepage copy-paste text drafted | D-13 |
| PREW-06 | v2.9.0 CHANGELOG.md entry written in correct format | D-11/D-12 + format confirmed below |
| PREW-07 | Triggarr quality signals reconciled against SeedSyncarr | D-04..D-06 + SeedSyncarr README confirmed |
</phase_requirements>

---

## Summary

Phase 71 is a documentation rewrite driven entirely by the three Phase 70 critique artifacts. It has exactly one real code change (SSRF validation widened into config-load), and the rest is Markdown/YAML/text editing. The research confirms every specific fix that the planner needs to generate actionable tasks, with file:line precision.

The SSRF code change is lower-complexity than it might appear. `validate_arr_url()` in `triggarr/web/validation.py` already does exactly what D-02 describes as the "strict" mode. A second function `validate_arr_url_config()` (or a parameter `allow_loopback: bool = False`) in the same file, calling the same logic but skipping the `is_loopback` check, is the lowest-duplication approach. The hook point in `triggarr/models/config.py` is `InstanceConfig.url` via a new `field_validator("url")` that runs `validate_arr_url_config()` — the existing `reject_apikey_in_url` validator shows exactly how to add one. The test file to extend is `tests/test_validation.py` (for the new function) and/or `tests/test_config.py` (for the config-load integration path).

The README correctness fixes are unambiguous: the pip line hardcodes `2.7.2` (current version is `2.8.1`); the systemd unit omits `StateDirectory=triggarr`; the Docker first-run explanation omits the `sys.exit(1)` mechanism; the Tailwind version mismatch is Dockerfile pin `v4.2.1` vs committed `output.css` header `v4.2.2`; and the tag-filter fail-open behavior is confirmed in `search/engine.py`.

**Primary recommendation:** Implement the SSRF config-load validator as a sibling function `validate_arr_url_config(url: str) -> tuple[bool, str]` in `validation.py`, add a `field_validator("url")` to `InstanceConfig` that calls it (after the existing `reject_apikey_in_url` validator), and run the full rewrite/fix passes driven by the three Phase 70 artifacts.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| SSRF URL validation (web form) | API/Backend | — | Already lives in `web/validation.py`, called from `web/routes.py:561`. Unchanged. |
| SSRF URL validation (config-load) | API/Backend (model layer) | — | Pydantic `field_validator` on `InstanceConfig.url` in `models/config.py` is the correct hook — runs before any TOML write and at Settings construction time. |
| README / SECURITY.md / CONTRIBUTING.md / CHANGELOG.md | Static files | — | Markdown edits, no runtime component |
| Community-health YAML templates | Static files | — | `.github/ISSUE_TEMPLATE/` YAML edits only |
| In-app changelog | API/Backend (read-only) | — | `changelog.py` reads `CHANGELOG.md` from disk at runtime; the edit target is `CHANGELOG.md` not the parser |

---

## Standard Stack

### Core (no new packages — this phase edits existing code)

The one code change adds no dependencies. The validation extension reuses:

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `pydantic` (existing) | in `pyproject.toml` | `field_validator` on `InstanceConfig` | Already the config model framework |
| `ipaddress` (stdlib) | stdlib | IP address classification in `validate_arr_url_config` | Already used at `validation.py:9` |
| `urllib.parse` (stdlib) | stdlib | URL parsing in `validate_arr_url_config` | Already used at `validation.py:12` |

[VERIFIED: codebase grep — these imports are present in `validation.py:9-12` and `models/config.py:10`]

### Package Legitimacy Audit

No new external packages are introduced in this phase. This section is not applicable.

---

## Architecture Patterns

### System Architecture Diagram

```
TOML file on disk
      │
      ▼
ensure_config() [config.py:333]
      │
      ▼
load_settings() → Settings(**data) → InstanceConfig.url field_validators
      │                                   │
      │                           [existing] reject_apikey_in_url (blocks ?apikey=)
      │                           [NEW]     validate_arr_url_config (blocks metadata+link-local, allows loopback)
      │
      ▼
Settings object in memory (validated, safe to use)

Web settings POST [routes.py:561]
      │
      ▼
validate_arr_url(url) ← STRICT (blocks loopback too) — UNCHANGED
      │
      ▼
InstanceConfig construction → reject_apikey_in_url + validate_arr_url_config
      │
      ▼
_atomic_toml_write → disk
```

### Recommended Project Structure (no changes this phase)

The code change adds one function to `triggarr/web/validation.py` and one `field_validator` to `triggarr/models/config.py`. No new files.

### Pattern 1: Adding a Field Validator to InstanceConfig (D-01/D-02)

**What:** A second `@field_validator("url")` on `InstanceConfig` that calls the new relaxed validator.
**When to use:** Config-load path — TOML-set URLs must pass relaxed SSRF check.

The existing `reject_apikey_in_url` validator is the exact template to follow:

```python
# Source: triggarr/models/config.py:65-89 (existing pattern)
@field_validator("url")
@classmethod
def reject_apikey_in_url(cls, v: str) -> str:
    if not v:
        return v
    parsed = urlparse(v)
    if not parsed.query:
        return v
    for key, _value in parse_qsl(parsed.query, keep_blank_values=True):
        if key.lower().startswith("apikey"):
            msg = "URL must not contain an apikey= query parameter."
            raise ValueError(msg)
    return v
```

New validator to add after `reject_apikey_in_url`:

```python
@field_validator("url")
@classmethod
def validate_url_ssrf(cls, v: str) -> str:
    """D-01/D-02: Apply relaxed SSRF validation at config-load time.

    Permits loopback/localhost (legitimate same-host *arr installs) but
    still blocks cloud-metadata (169.254.169.254, metadata.google.internal,
    etc.) and link-local addresses. Raises ValueError on violation.
    """
    from triggarr.web.validation import validate_arr_url_config
    ok, err = validate_arr_url_config(v)
    if not ok:
        raise ValueError(err)
    return v
```

**Important note on Pydantic v2 field_validator ordering:** When multiple `@field_validator` decorators target the same field, Pydantic v2 runs them in definition order. The new `validate_url_ssrf` must be defined AFTER `reject_apikey_in_url` so the apikey check runs first. [VERIFIED: pydantic v2 docs — field validators run in order of definition for the same field mode]

### Pattern 2: Sibling Function in validation.py (D-02)

**What:** `validate_arr_url_config(url: str) -> tuple[bool, str]` — same logic as `validate_arr_url` but does NOT check `is_loopback`.

```python
# New function in triggarr/web/validation.py (after validate_arr_url)
def validate_arr_url_config(url: str) -> tuple[bool, str]:
    """Validate a *arr URL loaded from TOML config (relaxed variant).

    Same rules as validate_arr_url EXCEPT loopback addresses (127.x.x.x,
    ::1, localhost) are permitted. Running an *arr app on the same host via
    http://127.0.0.1:7878 is a legitimate homelab pattern.

    Still blocks cloud-metadata hosts and link-local addresses.
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
        # NOTE: loopback is ALLOWED here (unlike validate_arr_url)
        if addr.is_link_local or addr.is_unspecified or addr.is_multicast:
            return (False, "Blocked address")
        if isinstance(addr, ipaddress.IPv6Address) and addr.ipv4_mapped:
            mapped = addr.ipv4_mapped
            if (
                mapped.is_link_local
                or mapped.is_unspecified
                or mapped.is_multicast
                or any(mapped in net for net in _BLOCKED_NETWORKS)
            ):
                return (False, "Blocked address")
    except ValueError:
        pass  # hostname is a DNS name, not an IP literal

    return (True, "")
```

**Why sibling function, not a parameter:** A single `validate_arr_url(url, allow_loopback=False)` parameter would work, but the sibling function keeps call sites maximally explicit — the routes.py call stays `validate_arr_url(url)` with no arguments changed, and the new config-load call is `validate_arr_url_config(url)` with an obviously distinct name. Zero risk of accidentally passing `allow_loopback=True` at the web-form call site. [ASSUMED: this preference for the sibling approach — both approaches are valid]

### Pattern 3: CHANGELOG.md Entry Format

**What:** `changelog.py` parses a strict format. The v2.9.0 entry MUST match it exactly.

```markdown
## v2.9.0 (<date-at-execution-time>)

Brief release summary sentence.

* Features:

  * First feature bullet

* Security:

  * Security bullet

* Documentation:

  * Documentation bullet

* Fixes:

  * Fix bullet
```

**Critical format rules confirmed from `changelog.py:35-37` and `CHANGELOG.md:1-35`:**
- Version header: `## vX.Y.Z (YYYY-MM-DD)` — the regex is `^##\s+(.+)$`
- Category line: `* Category:` — regex is `^\*\s+([^:]+):\s*$` — the category name ends with `:` and nothing after
- Bullet: `  * Item text` — regex is `^\s+\*\s+(.+)$` — TWO spaces indent before `*`
- An optional summary sentence after the version header (before any `*`) is allowed — changelog.py skips lines that don't match any pattern

The most-recent entry (`## v2.8.1 (2026-05-31)`) uses: summary sentence, then `* Security:`, then `  * bullet`. The `## v2.8.0 (2026-06-01)` entry uses: summary sentence, then `* Features:`, `  * bullet`, then `* Improvements:`, etc.

"Documentation" is a valid category name (no constraint on category names in the parser). [VERIFIED: codebase — changelog.py:36-37 `_CATEGORY_ITEM` and `_BULLET_ITEM` patterns]

### Anti-Patterns to Avoid

- **Using `validate_arr_url(url, allow_loopback=True)` at routes.py:561:** The web-form call site must NOT change. Only the new config-load path uses the relaxed logic. Verify the routes.py call is untouched.
- **Adding `StateDirectory=triggarr` without verifying it implies `/var/lib/triggarr`:** `StateDirectory=triggarr` in a systemd `[Service]` section creates `/var/lib/triggarr` owned by the service user automatically (systemd manages it). This is the correct fix for the codex HIGH finding.
- **CHANGELOG heading with text after the colon:** `* Security: some text` would NOT parse — the category regex requires nothing after the colon (`^\*\s+([^:]+):\s*$`). Category line must be `* Security:` alone.
- **Breaking the `test_docs_accuracy.py` TOML block test:** `tests/test_docs_accuracy.py:85-100` parses every ```toml``` block in README.md and validates it against `Settings`. The rewritten README must preserve valid TOML blocks or the test suite breaks.

---

## Research Findings by Target

### 1. SSRF Config-Load Validation (D-01/D-02/D-03)

**Current state of `validation.py`:** [VERIFIED: direct read]
- `validate_arr_url()` lives at line 56.
- Blocks: `is_link_local`, `is_loopback`, `is_unspecified`, `is_multicast` (line 88); BLOCKED_HOSTS set (line 83); IPv4-mapped IPv6 bypass (lines 91-100); `_BLOCKED_NETWORKS` including `100.64.0.0/10` for Alibaba cloud metadata.
- Allows: private LAN (`10.x`, `192.168.x`) — intentionally, per comment at lines 61-62 and test at lines 52-55 of `test_validation.py`.
- Empty URL returns `(True, "")` — disabled instances are valid.

**Current state of `models/config.py`:** [VERIFIED: direct read]
- `InstanceConfig` at line 45 has two validators: `reject_apikey_in_url` (field_validator, lines 65-89) and `at_least_one_search_count` (model_validator, lines 91-97).
- `load_settings()` at `config.py:213-227` calls `Settings(**data)`, which constructs `InstanceConfig` objects. Pydantic validators run during construction — this is the config-load hook point.
- No SSRF validation currently runs at config-load. D-01's premise is confirmed. [VERIFIED: codebase grep — no call to `validate_arr_url` outside `routes.py:561`]

**Routes.py call site:** [VERIFIED: direct read at lines 560-564]
```python
url = fields.get("url", "").strip()
valid, err = validate_arr_url(url)
if not valid:
    ...return RedirectResponse(...)
```
This call is strict (blocks loopback). It must stay unchanged.

**Recommended implementation (D-02):**
1. Add `validate_arr_url_config(url: str) -> tuple[bool, str]` to `triggarr/web/validation.py` after `validate_arr_url` (line ~109). Same logic, but skip the `is_loopback` check.
2. Add `validate_url_ssrf` `@field_validator("url")` to `InstanceConfig` in `triggarr/models/config.py` after `reject_apikey_in_url` (after line 89). It calls `validate_arr_url_config(v)`.
3. The validator raises `ValueError` on failure — consistent with `reject_apikey_in_url` pattern.

**What the net behavior claim becomes (for README:215 and SECURITY.md:39):**
> "Cloud-metadata endpoints and link-local addresses are blocked at all entry points (web UI and config file). Loopback addresses (`127.x.x.x`, `localhost`) are permitted in the config file for same-host *arr deployments but rejected via the web settings form."

**Existing test file:** `tests/test_validation.py` — `TestValidateArrUrl` class (line 11) covers `validate_arr_url`. New tests for `validate_arr_url_config` go in the same file as a new class `TestValidateArrUrlConfig`. Additionally, `tests/test_config.py` should get integration tests confirming that TOML with a loopback URL loads successfully and that TOML with a cloud-metadata URL raises `ValidationError`.

**D-03 minimum test coverage (must be implemented):**

| Test | Type | Target |
|------|------|--------|
| `test_config_load_loopback_allowed` | unit | `validate_arr_url_config("http://127.0.0.1:7878")` → `(True, "")` |
| `test_config_load_localhost_allowed` | unit | `validate_arr_url_config("http://localhost:7878")` → `(True, "")` |
| `test_config_load_private_lan_allowed` | unit | `validate_arr_url_config("http://192.168.1.100:7878")` → `(True, "")` |
| `test_config_load_metadata_blocked` | unit | `validate_arr_url_config("http://169.254.169.254/...")` → `(False, ...)` |
| `test_config_load_link_local_blocked` | unit | `validate_arr_url_config("http://169.254.42.42")` → `(False, ...)` |
| `test_config_load_gcp_metadata_blocked` | unit | `validate_arr_url_config("http://metadata.google.internal")` → `(False, ...)` |
| `test_instance_config_loopback_url_valid` | integration | `InstanceConfig(url="http://127.0.0.1:7878", ...)` succeeds |
| `test_instance_config_metadata_url_raises` | integration | `InstanceConfig(url="http://169.254.169.254/...", ...)` raises `ValidationError` |

---

### 2. Install/Quickstart Accuracy (D-07)

**a. Pip install line (README:85)** [VERIFIED: direct read]

Current line:
```bash
pip install https://github.com/thejuran/triggarr/releases/latest/download/triggarr-2.7.2-py3-none-any.whl
```
`__version__` in `triggarr/__init__.py:1` = `"2.8.1"`. The filename is stale by two minor versions.

**Resilient fix pattern options (Claude's discretion):**

Option A — `curl` + `pip` (most resilient):
```bash
pip install "$(curl -s https://api.github.com/repos/thejuran/triggarr/releases/latest | python3 -c 'import sys,json; print(next(a["browser_download_url"] for a in json.load(sys.stdin)["assets"] if a["name"].endswith(".whl")))')"
```
This never goes stale but is complex and requires network access at copy-paste time.

Option B — update filename to current version:
```bash
pip install https://github.com/thejuran/triggarr/releases/latest/download/triggarr-2.8.1-py3-none-any.whl
```
Simple but will go stale again with the next release.

Option C — link to releases page only (no pip-install one-liner):
Point to `https://github.com/thejuran/triggarr/releases/latest` and instruct users to download the `.whl` themselves.

**Recommendation:** Use Option B (update to `2.8.1`) as the immediate fix since v2.9.0 will be tagged after this milestone ships anyway, and note "update this line on each release" in the commit. The critique and codex both flag the version mismatch; the fix just needs to be non-stale at time of release. [ASSUMED — the planner/executor should pick one of Options A/B/C per the Claude's Discretion grant]

**b. Systemd unit (README:98-109)** [VERIFIED: direct read]

Current unit has `Environment=TRIGGARR_CONFIG_DIR=/var/lib/triggarr` but no `StateDirectory=triggarr`. `TRIGGARR_CONFIG_DIR` is checked at `models/config.py:18-29` — it must be an absolute path.

When `User=triggarr` runs systemd without `StateDirectory=triggarr`, `/var/lib/triggarr` may not exist. `StateDirectory=triggarr` (in `[Service]`) makes systemd create and own `/var/lib/triggarr` automatically, owned by the service user. This is the correct one-line fix per the codex HIGH finding.

**Exact line to add** (after `Environment=TRIGGARR_CONFIG_DIR=/var/lib/triggarr`):
```ini
StateDirectory=triggarr
```

**c. Docker first-run exit (README:78)** [VERIFIED: direct read at config.py:353-359]

`ensure_config()` at `config.py:333-373`: when `config_path` does not exist, it calls `generate_default_config()`, logs a warning, then calls `sys.exit(1)` (line 359). Docker sees exit code 1, `restart: unless-stopped` triggers, and the container restarts. On second start, the config file exists, so `ensure_config()` proceeds to `load_settings()`.

**Current README:78 wording:** "On an empty volume, Triggarr writes `/config/triggarr.toml` first; with the `restart: unless-stopped` example above, the container then starts normally on the next restart."

**What to add:** "The first run exits with code 1 after writing the default config — this is expected and not a crash. Docker's `restart: unless-stopped` brings the container back up automatically. Edit the config at `/config/triggarr.toml`, then visit `http://localhost:8484` to complete setup."

**d. Tailwind version (README:275, CONTRIBUTING.md:20)** [VERIFIED: direct read]
- `Dockerfile:9`: `ENV TAILWINDCSS_VERSION=v4.2.1`
- `triggarr/static/css/output.css:1`: `/*! tailwindcss v4.2.2 | MIT License | ...`

There is a one-minor-version mismatch. The committed `output.css` was built with `v4.2.2`, but the Dockerfile pins `v4.2.1`. The `output.css` header is authoritative for what is actually compiled into the image. The correct documentation fix is:

1. Decide which version is authoritative: the `output.css` header says `v4.2.2`. The Dockerfile should be updated to `v4.2.1` → `v4.2.2` (or left as-is and output.css regenerated with `v4.2.1`). [ASSUMED: executor should update Dockerfile `TAILWINDCSS_VERSION=v4.2.2` to match `output.css`, since the committed CSS is the artifact that ships]
2. Add `export TAILWINDCSS_VERSION=v4.2.2` (or whichever is decided) to the dev commands in README and CONTRIBUTING.md, before the `tailwindcss` watch command.

**Current watch command in README:275 and CONTRIBUTING.md:20:**
```bash
uv run tailwindcss -i triggarr/static/css/input.css -o triggarr/static/css/output.css --watch
```

**Corrected form (example with v4.2.2 decision):**
```bash
export TAILWINDCSS_VERSION=v4.2.2   # must match Dockerfile TAILWINDCSS_VERSION
uv run tailwindcss -i triggarr/static/css/input.css -o triggarr/static/css/output.css --watch
```

Or inline: `TAILWINDCSS_VERSION=v4.2.2 uv run tailwindcss ...`

**e. Tag-filtering fail-open (README:25)** [VERIFIED: search/engine.py:355-390]

The actual behavior is confirmed:
1. If tag fetch fails (httpx/pydantic error) → `tag_fetch_ok = False` → `tag_id` stays `None` → `filter_by_tag` is not called → **all items searched**. Log: `"Radarr: Failed to fetch tags -- skipping tag filtering: {exc}"` (engine.py:369).
2. If tag fetch succeeds but the configured tag name is not found → `resolve_tag_id()` returns `None` → `tag_id` stays `None` → **all items searched**. Log: `"Radarr: Tag '{tag}' not found -- searching all missing items"` (engine.py:378). A `tag_warnings` entry is appended (dashboard signal).

**Precise wording to add to README (for "Tag-based filtering" feature bullet):**
> "Tag-based filtering — scope searches to specific tags per instance. If a configured tag can't be resolved or tag fetch fails, Triggarr logs a warning and searches all items for that queue (fail-open). The dashboard surfaces a tag-warning indicator."

---

### 3. SECURITY.md Reconciliation (D-08/D-09)

**Confirmed hardening items in code** [VERIFIED: direct read]:

| Item | Location | What it does |
|------|----------|--------------|
| CSP `script-src` nonce (no `unsafe-inline`) | `web/middleware.py:43-57` | `SecurityHeadersMiddleware` generates `secrets.token_urlsafe(16)` per request, stores in `request.state.csp_nonce`, emits `Content-Security-Policy: script-src 'self' 'nonce-{nonce}'` — no `unsafe-inline` |
| Session-secret rotation on password change (CWE-613) | `web/routes.py:1449-1481` | `new_session_secret = generate_session_secret()` during `change_password` handler; re-issued to current session; v2.8.1 patch |
| `apikey=` URL rejection | `models/config.py:65-89` `reject_apikey_in_url` field_validator | Raises `ValueError` at model construction, blocking `?apikey=` in any case/encoding |
| Basic-auth control-char validation | `web/middleware.py:25-26, 177-186` | `_has_control_chars()` checks C0 control chars (0x00..0x1F) + DEL (0x7F) in username/password; returns 401 on match |
| Session-secret startup length check | `startup.py:49-69` | `_warn_if_session_secret_short()` warns at startup if `len(session_secret) < 32` |

**At-rest-plaintext reality (D-09):** [VERIFIED: direct read, `models/config.py:53`, `SECURITY.md:28-30`]
- `api_key: SecretStr` and `session_secret: SecretStr` are stored as pydantic `SecretStr`, which masks them in `repr()`/`str()`/`model_dump_json()` and the Loguru redacting sink.
- The TOML config file is written by `_atomic_toml_write` using `tomli_w.dump` — API keys and session secret are stored as plaintext strings in `triggarr.toml`.
- `README:212` already states: "Config secrets in triggarr.toml are plaintext on disk; protect them with file permissions and volume security."
- SECURITY.md needs this caveat added. Exact framing: "`SecretStr` protects repr/log/HTML exposure — API keys, auth credentials, and the session secret are plaintext in `triggarr.toml`. Protect them with file permissions (`0600`, set by Triggarr on write) and volume security."

**Current SECURITY.md:39 claim to update:**
```
URL inputs are validated against an allow-list of schemes (http, https) and a block-list of cloud metadata and link-local hostnames to prevent server-side request forgery.
```

**Post-D-01/D-02 accurate claim:**
```
URL inputs are validated against an allow-list of schemes (http and https) and a block-list of cloud-metadata and link-local hostnames. This validation applies both to URLs submitted via the web settings form (which additionally rejects loopback addresses) and to URLs loaded from triggarr.toml at startup.
```

---

### 4. Community-Health Files (D-10)

**Confirmed file inventory** [VERIFIED: direct filesystem read]:

| File | Present | Status |
|------|---------|--------|
| `CONTRIBUTING.md` | Yes | Current, functional, no drift |
| `LICENSE` | Yes | MIT, year 2026 — correct |
| `.github/ISSUE_TEMPLATE/bug-report.yml` | Yes | Version dropdown tops at v2.3; App Type omits Lidarr — NEEDS FIX |
| `.github/ISSUE_TEMPLATE/feature-request.yml` | Yes | No version/app-type issues, looks current |
| `.github/ISSUE_TEMPLATE/config.yml` | Yes | `blank_issues_enabled: false` + Discussions link — current |
| `.github/pull_request_template.md` | Yes | Tests/lint/Docker checklist — current, no drift |

**Exact current bug-report.yml state** [VERIFIED: direct read at lines 10-14 and 29-34]:

Version dropdown options (lines 10-14):
```yaml
options:
  - v2.3
  - v2.2
  - v2.1
  - Older
```

App Type options (lines 29-34):
```yaml
options:
  - Radarr
  - Sonarr
  - Both
```

**Exact replacement version dropdown** (D-10):
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

**Exact replacement App Type dropdown** (D-10):
```yaml
options:
  - Radarr
  - Sonarr
  - Lidarr
  - All
```

**Note on existing test:** `tests/test_community_health.py` tests CONTRIBUTING.md, SECURITY.md, and LICENSE but does NOT test bug-report.yml or feature-request.yml. No test regression from these YAML edits. No new test required (the fix is a list update, not logic).

**Note on `tests/test_github_templates.py`:** This file exists. The executor must verify its contents don't check the exact option lists before editing bug-report.yml.

---

### 5. CHANGELOG.md Format and v2.9.0 Entry (D-11/D-12)

**Parser behavior confirmed** [VERIFIED: `changelog.py:35-37, 83-141`]:
- Version header regex: `^##\s+(.+)$` — matches `## v2.9.0 (2026-06-02)` exactly
- Category regex: `^\*\s+([^:]+):\s*$` — category name is everything before `:`, nothing after
- Bullet regex: `^\s+\*\s+(.+)$` — any leading whitespace before `*`, two spaces is conventional
- Optional summary line after version header is fine (changelog.py skips non-matching lines gracefully)
- `latest_only=True` returns the first version block only — used by dashboard

**Most-recent entry format (v2.8.1)** — confirmed canonical template:
```
## v2.8.1 (2026-05-31)

<one-sentence summary paragraph>

* Security:

  * <bullet>
```

**Changelog.md also has the "Documentation" category** — confirmed ABSENT in current CHANGELOG.md, but the parser accepts any category name. The executor can introduce `* Documentation:` for the presentation work.

**v2.9.0 user-facing content per D-12:**
- SSRF/config-load URL-validation hardening (D-01) → `* Security:` bullet
- Manual-search failure-counter fix (Phase 69 CHARD-02/SAFETY-03) → `* Fixes:` bullet
- Docs/presentation overhaul → `* Documentation:` bullet (or `* Improvements:`)
- Internal-only (gitleaks `.gitleaksignore`, fastapi/starlette dep bump, `.orchestrator.json` gitignore) → include under `* Fixes:` or `* Security:` ONLY if user-relevant (e.g. the dep bump is security-relevant; the gitignore is not)

---

### 6. README Structure Mirror / SeedSyncarr Alignment (D-04/D-05/D-06)

**SeedSyncarr README section order** [VERIFIED: direct read]:
1. `<div align="center">` + wordmark picture block
2. Screenshot `<img>`
3. Blockquote tagline
4. Four badges (CI, Release, Docker, License) inline
5. `## Quick Start` (compose YAML only — 5 lines)
6. `## Features`
7. `## How It Works`
8. `## Installation`
9. `## Configuration`
10. `## Screenshots`
11. `## Related Projects`
12. `## Contributing`
13. `## Security`
14. `## License`
15. `## Usage Examples`

**D-04 target order for Triggarr:**
1. Centered header (HTML div) → H1 + badges + tagline
2. Above-the-fold screenshot
3. `## Quick Start` (minimal compose)
4. `## Features`
5. `## How It Works`
6. `## Install` (full reference — Docker + standalone)
7. `## Configuration Reference`
8. `## Screenshots`
9. `## Security Model`
10. `## Related Projects`
11. `## Contributing / Development`

**SeedSyncarr badge URL patterns** [VERIFIED: direct read at README.md:15-18]:
```
[![CI](https://github.com/thejuran/seedsyncarr/actions/workflows/ci.yml/badge.svg)]
[![Release](https://img.shields.io/github/v/release/thejuran/seedsyncarr)]
[![Docker](https://img.shields.io/badge/docker-ghcr.io-blue)]
[![License](https://img.shields.io/github/license/thejuran/seedsyncarr)]
```

**Triggarr equivalents (D-05):**
```markdown
[![CI](https://github.com/thejuran/triggarr/actions/workflows/ci.yml/badge.svg)](https://github.com/thejuran/triggarr/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/thejuran/triggarr)](https://github.com/thejuran/triggarr/releases)
[![Docker](https://img.shields.io/badge/docker-ghcr.io-blue)](https://ghcr.io/thejuran/triggarr)
[![License](https://img.shields.io/github/license/thejuran/triggarr)](LICENSE)
```

**SeedSyncarr's Related Projects block** [VERIFIED: direct read at lines 104-106]:
```markdown
## Related Projects

- [**Triggarr**](https://github.com/thejuran/triggarr) — lightweight search automation daemon for Radarr, Sonarr, and Lidarr. SeedSyncarr handles the download-to-sync side; Triggarr handles the search-to-trigger side.
```

**Triggarr's mirror (D-04, item 10):**
```markdown
## Related Projects

- [**SeedSyncarr**](https://github.com/thejuran/seedsyncarr) — sync files from your seedbox to your local media server, integrated with Sonarr and Radarr. SeedSyncarr handles the download-to-sync side; Triggarr handles the search-to-trigger side.
```

**D-05 header treatment — no wordmark image:**
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

---

### 7. Screenshots (PREW-02 — refs only this phase)

**Current screenshot files** [VERIFIED: filesystem]:
- `docs/screenshots/dashboard.png` (present)
- `docs/screenshots/history.png` (present)
- `docs/screenshots/settings.png` (present)

**Current README references** [VERIFIED: README.md:36-40]:
```markdown
![Dashboard with app cards, grab rate stats, and live recent activity rail](docs/screenshots/dashboard.png?v=2)
![Search history with filter chips for app, queue type, outcome, and title search](docs/screenshots/history.png?v=2)
![Settings page with general options and per-instance configuration for Radarr, Sonarr, and Lidarr](docs/screenshots/settings.png?v=2)
```

The `?v=2` cache-buster is embedded. For the rewritten README the executor should drop the `?v=` parameter (it is a GitHub-viewer artifact, not a web server cache control) and write clean alt text. The actual PNG files stay untouched until the NAS walkthrough.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| SSRF IP classification | Custom IP range comparison | `ipaddress.ip_address(hostname).is_link_local` etc. | Already used in `validate_arr_url`; stdlib handles all edge cases including IPv6 |
| Pydantic field validation | Manual field check outside model | `@field_validator("url")` on `InstanceConfig` | Runs at every construction site (TOML load, Settings(**data), direct instantiation) |
| CHANGELOG HTML rendering | Custom markdown parser | `changelog.py:70-143` already handles it | Reuse existing `parse_changelog()` — only `CHANGELOG.md` content changes |

---

## Common Pitfalls

### Pitfall 1: Breaking the TOML Accuracy Test
**What goes wrong:** `tests/test_docs_accuracy.py:85-100` parses every ```toml``` code block in README.md and validates it against `Settings.model_validate(data)`. If the rewritten README introduces a TOML block that is not valid Triggarr config shape, this test fails.
**Why it happens:** The README config reference contains a multi-section TOML example (lines 127-185). The rewrite must preserve or replace it with equally valid TOML.
**How to avoid:** Keep all ```toml``` blocks in the README valid Pydantic-parseable TOML. Run `uv run pytest tests/test_docs_accuracy.py -x -q` after the README edit.
**Warning signs:** `ValueError`/`ValidationError` from `test_readme_toml_examples_parse_and_validate_as_settings`.

### Pitfall 2: InstanceConfig Field Validator Order (Pydantic v2)
**What goes wrong:** Two `@field_validator("url")` decorators on `InstanceConfig` run in definition order. If `validate_url_ssrf` is defined BEFORE `reject_apikey_in_url`, the `?apikey=` check may run after SSRF check — creating a subtle ordering dependency.
**Why it happens:** Pydantic v2 runs multiple validators for the same field in definition order.
**How to avoid:** Define `validate_url_ssrf` AFTER `reject_apikey_in_url` in `InstanceConfig` (after line 89 of `models/config.py`).
**Warning signs:** Test that passes `?apikey=` URL to `InstanceConfig` may hit the SSRF error message instead of the apikey error message.

### Pitfall 3: CHANGELOG Category Line Format
**What goes wrong:** A category line with trailing text (e.g., `* Security: patch release`) does NOT match `_CATEGORY_ITEM = re.compile(r"^\*\s+([^:]+):\s*$")` — the `\s*$` requires end-of-line after the colon.
**Why it happens:** The regex is strict about the category line format.
**How to avoid:** Category line must be exactly `* Security:` with no trailing text. The summary goes in a separate paragraph before the first category.
**Warning signs:** In-app changelog renders the line as a stray bullet rather than a category heading.

### Pitfall 4: `validate_arr_url_config` Must Not Accidentally Block `localhost` Hostname
**What goes wrong:** `ipaddress.ip_address("localhost")` raises `ValueError` because `localhost` is a DNS name, not an IP literal. The `except ValueError: pass` branch in `validate_arr_url` (and the new `validate_arr_url_config`) handles this correctly — hostname-as-string falls through to `(True, "")`.
**Why it happens:** `localhost` is only loopback by convention; it resolves via DNS/hosts. The current strict validator accidentally allows `http://localhost` through because it hits the `except ValueError` branch (not the `is_loopback` check).
**How to avoid:** The new `validate_arr_url_config` should NOT need to special-case `localhost` — it already falls through the `except ValueError` branch to `(True, "")`. Confirm the test `test_config_load_localhost_allowed` passes.

### Pitfall 5: `test_github_templates.py` may assert on bug-report.yml content
**What goes wrong:** `tests/test_github_templates.py` exists. If it currently asserts the exact option list in `bug-report.yml`, the D-10 fix will fail tests unless the test is updated.
**Why it happens:** Community-health tests sometimes snapshot template content.
**How to avoid:** Read `tests/test_github_templates.py` before editing `bug-report.yml`; update any snapshot assertions to match the new option lists.

---

## Runtime State Inventory

Not applicable. This phase is a documentation rewrite + one config-model field validator addition. No rename/refactor affecting stored data, live service config, OS-registered state, secrets/env vars, or build artifacts.

---

## Environment Availability

This phase has no external tool dependencies beyond the existing project stack. The code change uses stdlib (`ipaddress`, `urllib.parse`) and existing Pydantic — both already present.

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.11+ | SSRF validator code | ✓ | (project requirement) | — |
| pydantic | `InstanceConfig` field_validator | ✓ | in pyproject.toml | — |
| pytest | test_validation.py, test_config.py | ✓ | in pyproject.toml dev extras | — |

---

## Validation Architecture

`nyquist_validation` not explicitly set in `.planning/config.json` → treated as **enabled**.

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest with pytest-asyncio, asyncio_mode=auto |
| Config file | `pyproject.toml` (pytest section) |
| Quick run command | `uv run pytest tests/test_validation.py tests/test_config.py tests/test_community_health.py tests/test_docs_accuracy.py -x -q` |
| Full suite command | `uv run pytest tests/ -x -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| PREW-01 (SSRF docs claim accuracy) | README:215 and SECURITY.md:39 wording matches post-D-01 behavior | source assertion | Manual review against code | — |
| PREW-01 (TOML examples valid) | All README ```toml``` blocks parse as valid Settings | unit | `uv run pytest tests/test_docs_accuracy.py::test_readme_toml_examples_parse_and_validate_as_settings -x -q` | ✅ exists |
| D-01/D-02/D-03 (config-load rejects metadata) | `InstanceConfig(url="http://169.254.169.254/...")` raises ValidationError | unit | `uv run pytest tests/test_config.py::test_instance_config_metadata_url_raises -x -q` | ❌ Wave 0 |
| D-01/D-02/D-03 (config-load allows loopback) | `InstanceConfig(url="http://127.0.0.1:7878", ...)` succeeds | unit | `uv run pytest tests/test_config.py::test_instance_config_loopback_url_valid -x -q` | ❌ Wave 0 |
| D-01/D-02/D-03 (validate_arr_url_config) | New function blocks metadata/link-local, allows loopback + private LAN | unit | `uv run pytest tests/test_validation.py::TestValidateArrUrlConfig -x -q` | ❌ Wave 0 |
| D-01/D-02 (web-form path unchanged) | Existing `TestValidateArrUrl.test_ipv4_loopback_blocked` still passes | unit | `uv run pytest tests/test_validation.py::TestValidateArrUrl -x -q` | ✅ exists |
| PREW-04 (community health) | CONTRIBUTING.md, SECURITY.md, LICENSE pass all checks | unit | `uv run pytest tests/test_community_health.py -x -q` | ✅ exists |
| PREW-03 (SECURITY.md content checks) | SECURITY.md `test_ssrf_documented`, `test_secretstr_documented` pass | unit | `uv run pytest tests/test_community_health.py::TestSecurity -x -q` | ✅ exists |
| D-10 (bug-report.yml App Type includes Lidarr) | Template has Lidarr option | unit | `uv run pytest tests/test_github_templates.py -x -q` | ✅ (contents TBD — see Pitfall 5) |
| PREW-06 (CHANGELOG format) | `read_changelog()` renders v2.9.0 entry without errors | unit | `uv run pytest tests/test_changelog.py -x -q` | ✅ exists |

### Sampling Rate

- **Per task commit:** `uv run pytest tests/test_validation.py tests/test_config.py -x -q`
- **Per wave merge:** `uv run pytest tests/ -x -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/test_validation.py` — add `TestValidateArrUrlConfig` class (covers PREW-01 D-03)
- [ ] `tests/test_config.py` — add `test_instance_config_loopback_url_valid` and `test_instance_config_metadata_url_raises` (covers D-03 integration)
- [ ] Read `tests/test_github_templates.py` before editing bug-report.yml — update any version/app-type assertions that would break

---

## Security Domain

`security_enforcement` not explicitly set → treated as **enabled**.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | — (not modified this phase) |
| V3 Session Management | no | — (not modified this phase) |
| V4 Access Control | no | — (not modified this phase) |
| V5 Input Validation | yes | New `validate_arr_url_config` + pydantic field_validator on InstanceConfig.url |
| V6 Cryptography | no | — (not modified this phase) |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation | Phase Status |
|---------|--------|---------------------|-------------|
| SSRF via TOML-configured URL | Spoofing / Information Disclosure | `validate_arr_url_config` field_validator on InstanceConfig | Fixed by D-01/D-02 |
| Stale doc claiming SSRF validation applies broadly when it doesn't | Information Disclosure (false security claim) | Accurate documentation matching code behavior | Fixed by D-03 + doc updates |

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Pydantic v2 field validators on the same field run in definition order | Code Examples — Pattern 1 | If wrong, apikey and SSRF validators could interleave unexpectedly; executor must verify by running the test suite |
| A2 | `localhost` hostname resolves to loopback via `/etc/hosts` convention and is already permitted by the existing `except ValueError: pass` branch | Research Finding 1 / Pitfall 4 | If wrong (e.g., someone adds explicit `localhost` to BLOCKED_HOSTS), the relaxed config validator might allow `http://localhost` inconsistently vs `http://127.0.0.1` |
| A3 | Updating Dockerfile `TAILWINDCSS_VERSION` to `v4.2.2` to match `output.css` header is the right resolution for the version mismatch | Install/Quickstart section | If `v4.2.1` was intentional (e.g., `v4.2.2` introduced a breaking change for this project), regenerating `output.css` with `v4.2.1` and updating only the docs would be the right direction; executor should decide |
| A4 | Pip wheel fix uses Option B (update filename to current version) | Install/Quickstart section | If the maintainer prefers the curl+pip pattern (Option A), the wording will differ; executor should pick per Claude's Discretion |

---

## Open Questions

1. **Tailwind version resolution direction**
   - What we know: Dockerfile pins `v4.2.1`; committed `output.css` was built with `v4.2.2`
   - What's unclear: Was `v4.2.1` pinned before the CSS was regenerated, or was `output.css` accidentally regenerated with a local `v4.2.2` install?
   - Recommendation: Update Dockerfile to `v4.2.2` (match the committed artifact) and document `v4.2.2` in dev instructions. Regenerating CSS is not needed since output.css is already correct.

2. **`test_github_templates.py` content**
   - What we know: The file exists at `tests/test_github_templates.py`
   - What's unclear: Whether it snapshots the exact option lists in `bug-report.yml`
   - Recommendation: Read this file in Wave 0 before editing `bug-report.yml`. Update any assertions for the new version/app-type options as part of the same task.

---

## Sources

### Primary (HIGH confidence)

- `triggarr/web/validation.py` — direct read, confirmed `validate_arr_url()` signature and blocked addresses
- `triggarr/models/config.py` — direct read, confirmed `InstanceConfig` field validators and `load_settings()` hook
- `triggarr/web/routes.py:560-564` — direct read, confirmed strict web-form call site
- `triggarr/web/middleware.py:43-57, 177-186` — direct read, confirmed CSP nonce and Basic-auth control-char validation
- `triggarr/startup.py:49-69` — direct read, confirmed session-secret startup length check
- `triggarr/changelog.py` — direct read, confirmed Tautulli model and exact regex patterns
- `CHANGELOG.md` — direct read, confirmed format and most-recent entry template
- `README.md` — direct read (277 lines), confirmed all gripe evidence points
- `SECURITY.md` — direct read, confirmed all hardening gaps
- `CONTRIBUTING.md`, `.github/ISSUE_TEMPLATE/bug-report.yml`, `feature-request.yml`, `config.yml`, `.github/pull_request_template.md`, `LICENSE` — direct read, confirmed presence and content
- `Dockerfile:9` — direct read, confirmed `TAILWINDCSS_VERSION=v4.2.1`
- `triggarr/static/css/output.css:1` — direct read, confirmed `tailwindcss v4.2.2`
- `triggarr/__init__.py:1` — direct read, confirmed `__version__ = "2.8.1"`
- `triggarr/search/engine.py:355-390` — direct read, confirmed tag-filter fail-open behavior
- `~/seedsyncarr/README.md` — direct read, confirmed section order and badge URLs
- `tests/test_validation.py` — direct read, confirmed existing test class names and coverage
- `tests/test_config.py` — direct read, confirmed existing test names and Wave 0 gaps
- `tests/test_community_health.py` — direct read, confirmed coverage
- `tests/test_docs_accuracy.py` — direct read, confirmed TOML block accuracy test (Pitfall 1)
- `.planning/phases/71-presentation-rewrite/71-CONTEXT.md` — direct read, all 13 locked decisions
- `.planning/phases/70-presentation-discovery/70-CRITIQUE.md` — direct read, all 12 gripes
- `.planning/phases/70-presentation-discovery/70-CODEX-REVIEW.md` — direct read, 6 findings
- `.planning/phases/70-presentation-discovery/70-CONSISTENCY-AUDIT.md` — direct read, 11 signals

### Secondary (MEDIUM confidence)

- Pydantic v2 field validator ordering: confirmed by project convention (existing validators in `InstanceConfig` run in definition order) [ASSUMED pending executor verification]

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all code confirmed by direct read
- Architecture: HIGH — hook points identified with file:line
- Pitfalls: HIGH — most confirmed by test file reads and code trace
- CHANGELOG format: HIGH — confirmed by reading `changelog.py` regex patterns against live `CHANGELOG.md`
- Community health: HIGH — all files read directly
- SeedSyncarr alignment: HIGH — `~/seedsyncarr/README.md` read directly

**Research date:** 2026-06-02
**Valid until:** 2026-07-02 (stable codebase; only risk is a code change between now and execution that moves the validated line numbers)
