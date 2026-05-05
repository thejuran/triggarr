---
estimated_steps: 4
estimated_files: 5
skills_used:
  - security-review
  - tdd
  - verify-before-complete
---

# T01: Align secure-cookie trust boundary with ASGI scheme

Expected task-plan frontmatter skills_used: `security-review`, `tdd`, `verify-before-complete`.

Implement the runtime security fix that makes cookie `Secure` decisions depend on the ASGI request scheme rather than direct `X-Forwarded-Proto` header reads. This closes the highest-risk docs/code mismatch before documentation is rewritten.

## Failure Modes

| Dependency | On error | On timeout | On malformed response |
|------------|----------|------------|------------------------|
| Browser request headers | Treat as untrusted at app layer; never directly trust spoofed `X-Forwarded-Proto` for cookie security | N/A | Ignore malformed forwarded-proto values because the app should only inspect `request.url.scheme` |
| Uvicorn proxy-header processing | Keep existing `proxy_headers=True` and `forwarded_allow_ips=get_trusted_proxy_ips()` contract in `triggarr/__main__.py` | N/A | Covered by startup config tests rather than app route code |

## Load Profile

- **Shared resources**: none beyond request objects and cookie headers.
- **Per-operation cost**: trivial string comparison of `request.url.scheme` per cookie-setting path.
- **10x breakpoint**: none expected; this must not add I/O, DB access, or network calls.

## Negative Tests

- **Malformed inputs**: direct HTTP request with `X-Forwarded-Proto: https` must not mark cookies Secure.
- **Error paths**: absent/irrelevant forwarded headers must behave like plain HTTP unless `request.url.scheme` is HTTPS.
- **Boundary conditions**: HTTPS `base_url` in TestClient must set Secure; HTTP `base_url` with spoofed forwarded proto must not.

## Steps

1. Add a small shared helper, preferably `is_secure_request(request: Request) -> bool` in `triggarr/web/security.py`, whose docstring states that Uvicorn/trusted proxy processing is responsible for translating accepted forwarded proto into `request.url.scheme`.
2. Replace `_is_secure_context()` in `triggarr/web/routes.py` and the duplicated Basic-auth middleware expression in `triggarr/web/middleware.py` so all session-cookie `secure=` arguments use the shared helper and no runtime cookie path reads `x-forwarded-proto` directly.
3. Add/extend focused tests in `tests/test_auth_routes.py` for setup/login/logout cookie paths and in `tests/test_auth_middleware.py` for Basic auth: HTTPS requests set `Secure`; HTTP requests with spoofed `X-Forwarded-Proto: https` do not.
4. Preserve `tests/test_root_path.py` coverage proving `proxy_headers=True`, `forwarded_allow_ips`, and `TRUSTED_PROXY_IPS` remain configured at startup.

## Must-Haves

- [ ] No direct `request.headers.get("x-forwarded-proto")` or equivalent direct header trust remains in `triggarr/web/routes.py` or `triggarr/web/middleware.py` runtime cookie logic.
- [ ] The shared helper avoids circular imports and is reusable by both route and middleware code.
- [ ] Tests prove both positive HTTPS and negative spoofed-header cases for Forms route cookies and Basic-auth middleware cookies.
- [ ] Existing auth setup/login/logout behavior and root-path/proxy configuration tests continue to pass.

## Inputs

- `triggarr/web/routes.py`
- `triggarr/web/middleware.py`
- `triggarr/__main__.py`
- `tests/test_auth_routes.py`
- `tests/test_auth_middleware.py`
- `tests/test_root_path.py`

## Expected Output

- `triggarr/web/security.py`
- `triggarr/web/routes.py`
- `triggarr/web/middleware.py`
- `tests/test_auth_routes.py`
- `tests/test_auth_middleware.py`

## Verification

uv run pytest tests/test_auth_routes.py tests/test_auth_middleware.py tests/test_root_path.py -q

## Observability Impact

- Signals added/changed: no new production signals; tests become the diagnostic surface for the auth/proxy trust boundary.
- How a future agent inspects this: run `uv run pytest tests/test_auth_routes.py tests/test_auth_middleware.py tests/test_root_path.py -q` and inspect cookie assertions.
- Failure state exposed: a failing test identifies whether HTTPS scheme handling, spoofed forwarded-proto handling, or Uvicorn proxy config regressed.
