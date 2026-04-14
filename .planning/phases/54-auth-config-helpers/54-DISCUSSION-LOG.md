# Phase 54: Auth Config & Helpers - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md -- this log preserves the alternatives considered.

**Date:** 2026-04-14
**Phase:** 54-auth-config-helpers
**Areas discussed:** Config integration, Helper structure, SecretStr discipline

---

## Config Integration

### Default Config Template

| Option | Description | Selected |
|--------|-------------|----------|
| Omit from template | Don't include [auth] in DEFAULT_CONFIG. Pydantic defaults handle it. Setup page writes the section on first-run. | ✓ |
| Include commented-out | Add a commented [auth] section to DEFAULT_CONFIG like other optional fields. | |
| Include with defaults | Add [auth] section with method = "Forms" and empty fields. | |

**User's choice:** Omit from template
**Notes:** Keeps the template clean for new users. Pydantic creates valid AuthConfig() defaults when section is missing.

### ensure_config() Behavior

| Option | Description | Selected |
|--------|-------------|----------|
| Still exit(1) | Keep current behavior -- user must create config with app URLs first. Setup page only handles auth credentials. | ✓ |
| Generate and continue | Write defaults and start the app. Setup page handles both app config and auth. | |

**User's choice:** Still exit(1)
**Notes:** Separation of concerns -- config file setup (app URLs) vs auth credential setup (username/password/API key).

---

## Helper Structure

### Module Organization

| Option | Description | Selected |
|--------|-------------|----------|
| Single file | All helpers in triggarr/auth.py. Matches design spec. ~60-80 lines total. | ✓ |
| Package with modules | triggarr/auth/__init__.py re-exports from auth/password.py, auth/cookies.py, auth/keys.py. | |

**User's choice:** Single file
**Notes:** Small enough that splitting adds indirection without benefit.

---

## SecretStr Discipline

### Field Coverage

| Option | Description | Selected |
|--------|-------------|----------|
| All three | password_hash, api_key, and session_secret all get SecretStr. | ✓ |
| api_key + session_secret only | Skip SecretStr for password_hash since bcrypt hashes are safe to expose. | |
| api_key only | Only the API key needs redaction. | |

**User's choice:** All three
**Notes:** Consistent with project convention. All sensitive fields get SecretStr treatment.

### TOML Serialization Pattern

| Option | Description | Selected |
|--------|-------------|----------|
| Same pattern as instance API keys | Follow existing .get_secret_value() at write time convention. | ✓ |
| Claude decides | Claude picks the implementation approach. | |

**User's choice:** Same pattern as instance API keys
**Notes:** Consistent, already tested in routes.py settings save path.

---

## Claude's Discretion

- Bcrypt work factor, exact function signatures, docstring style, optional @property helpers on AuthConfig

## Deferred Ideas

None -- discussion stayed within phase scope.
