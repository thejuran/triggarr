# Phase 54: Auth Config & Helpers - Context

**Gathered:** 2026-04-14
**Status:** Ready for planning

<domain>
## Phase Boundary

Auth primitives exist in the codebase -- Pydantic config model, bcrypt password hashing, itsdangerous cookie signing, and API key generation -- ready for the middleware and UI layers to consume. No routes, no middleware, no templates in this phase.

</domain>

<decisions>
## Implementation Decisions

### Config Integration
- **D-01:** Omit `[auth]` section from `DEFAULT_CONFIG` template in `triggarr/config.py`. Pydantic defaults create a valid `AuthConfig()` when the section is missing from TOML. The setup page (Phase 56) writes the `[auth]` section on first-run credential creation.
- **D-02:** `ensure_config()` behavior unchanged -- still exits with code 1 when no config file exists. Auth setup only triggers when config exists but `auth.username` is empty (handled by middleware in Phase 55). Separation of concerns: config file setup vs auth credential setup.
- **D-03:** No config migration needed for v2.5 -> v2.6 upgrade. Existing installs without `[auth]` section get Pydantic defaults (empty username = needs-setup state).

### Helper Module Structure
- **D-04:** All auth helpers in a single flat file `triggarr/auth.py`. Functions: password hashing (bcrypt hash + verify), cookie signing (itsdangerous sign + validate with 30-day expiry), API key generation (`secrets.token_hex(16)`), session secret generation (`secrets.token_hex(32)`). ~60-80 lines total.

### SecretStr Discipline
- **D-05:** All three sensitive `AuthConfig` fields use `SecretStr`: `password_hash`, `api_key`, `session_secret`. Consistent with project convention (instance API keys already use SecretStr).
- **D-06:** TOML serialization follows existing pattern -- call `.get_secret_value()` at write time before `_atomic_toml_write()`, same as instance API key handling in `routes.py` settings save path.
- **D-07:** `collect_secrets()` in `triggarr/startup.py` updated to also gather auth secrets (`api_key`, `session_secret`) for log redaction. `password_hash` included too for completeness.

### Claude's Discretion
- Bcrypt work factor (design spec says 12 rounds default -- follow it)
- Exact function signatures and docstring style (follow existing codebase conventions)
- Whether to add `@property` helpers on `AuthConfig` (e.g., `needs_setup`, `is_disabled`) -- Claude decides based on downstream consumer needs

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Design Specification
- `docs/superpowers/specs/2026-04-14-built-in-auth-design.md` -- Full auth design: config schema, auth flow, session management, all four modes, file manifest

### Existing Code (must understand before modifying)
- `triggarr/models/config.py` -- `Settings` model where `AuthConfig` is added; `SecretStr` usage pattern; `InstanceConfig` as reference for nested model
- `triggarr/config.py` -- `DEFAULT_CONFIG` template (D-01: do NOT add [auth]), `_atomic_toml_write()`, `load_settings()`, `ensure_config()` (D-02: keep exit(1))
- `triggarr/startup.py` -- `collect_secrets()` function (D-07: extend for auth secrets)
- `triggarr/web/routes.py` -- Settings save path with `.get_secret_value()` pattern (D-06: follow this for auth TOML writes)

### Requirements
- `.planning/REQUIREMENTS.md` -- SETUP-03, LOGIN-02, LOGIN-05 mapped to this phase

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `SecretStr` from pydantic -- already used for instance API keys, same pattern for auth fields
- `_atomic_toml_write()` in `triggarr/config.py` -- reuse for writing auth config to TOML
- `collect_secrets()` in `triggarr/startup.py` -- extend to include auth secrets

### Established Patterns
- Pydantic `BaseModel` for config sub-sections (`GeneralConfig`, `InstanceConfig` -> `AuthConfig`)
- `model_validator(mode="after")` for cross-field validation
- `SecretStr` + `.get_secret_value()` only at HTTP client init or TOML serialization
- Loguru logging with redacting sink

### Integration Points
- `Settings` class in `triggarr/models/config.py` -- add `auth: AuthConfig = AuthConfig()` field
- `collect_secrets()` in `triggarr/startup.py` -- add auth secret gathering
- `pyproject.toml` -- add `bcrypt` dependency
- `itsdangerous` available as Starlette transitive dependency (no explicit dep needed)

</code_context>

<specifics>
## Specific Ideas

- API key format: 32-character hex token via `secrets.token_hex(16)` (per design spec)
- Session secret: 64-character hex via `secrets.token_hex(32)` (per design spec)
- Cookie signing: `itsdangerous.TimestampSigner` with configurable max_age (30 days = 2592000 seconds)
- Auth method enum: `Literal["Forms", "Basic", "External", "Disabled"]` with "Forms" as default

</specifics>

<deferred>
## Deferred Ideas

None -- discussion stayed within phase scope

</deferred>

---

*Phase: 54-auth-config-helpers*
*Context gathered: 2026-04-14*
