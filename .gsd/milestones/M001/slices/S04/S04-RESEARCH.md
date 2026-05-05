# S04 — Research

**Date:** 2026-05-05

## Summary

S04 is a remediation slice for two separate but related problems surfaced during S03 closure: (1) user-facing auth/proxy documentation is still not strict enough about the `External` auth trust boundary and overstates how secure-cookie `X-Forwarded-Proto` handling is gated; and (2) the S02 delivery trail is internally inconsistent because `S02-SUMMARY.md` is a placeholder failure artifact while `S02/tasks/T01-T03-SUMMARY.md` and verify JSON files contain the real documentation-update evidence. The formal `.gsd/REQUIREMENTS.md` has no Active requirements, so this slice should not invent requirement IDs; it supports milestone-level acceptance for documentation parity, backlog hygiene, and portable config-dir verification.

The highest-risk implementation issue is the secure-cookie trust boundary. `triggarr.__main__` correctly configures Uvicorn with `proxy_headers=True` and `forwarded_allow_ips=get_trusted_proxy_ips()`, and Uvicorn documentation confirms forwarded headers should only affect client/protocol when the connecting proxy is trusted. However, Triggarr route code and Basic-auth middleware also inspect `x-forwarded-proto` directly when deciding whether to set the `Secure` cookie flag. That direct header check means docs that say cookies rely on `TRUSTED_PROXY_IPS` are not currently true at the application layer. The cleanest remediation is to make code rely on `request.url.scheme == "https"` only, letting Uvicorn be the single trust boundary for forwarded proto, then update README/SECURITY wording to match.

Documentation should be written for a fresh operator, per the `write-docs` skill: name the concrete action the reader must take and avoid prose that assumes implementation history. For `External` auth, the reader action is: enable `auth.method = "External"` only after an upstream layer both authenticates/authorizes users and blocks direct access to Triggarr. A generic “trusted proxy” is not enough, because `External` is a pass-through in `AuthMiddleware` and does no Triggarr-side auth checks.

## Recommendation

Take a code-plus-doc remediation approach rather than papering over the mismatch in docs alone.

1. Centralize secure-cookie context and remove direct `X-Forwarded-Proto` checks from route and middleware cookie-setting paths. With Uvicorn configured for proxy headers and `forwarded_allow_ips`, trusted proxies will still produce `request.url.scheme == "https"`; untrusted direct headers will no longer influence cookie security decisions.
2. Rewrite README.md and SECURITY.md external-auth guidance so `External` clearly means “Triggarr trusts the upstream identity layer and bypasses local auth,” and require upstream authentication/authorization plus blocked direct port access.
3. Repair or supersede S02 evidence using GSD artifacts rather than editing source history by hand. Preferred repair path: after applying the S04 fixes, complete S02/T04 with the GSD task completion tool if accepted, then regenerate/rewrite a real S02 summary through GSD tooling. Fallback supersede path: leave the placeholder `S02-SUMMARY.md` as historical failure evidence but make S04 task/slice summaries explicitly cite the real S02 task summaries and state that S04 supersedes the failed S02 closure artifact.
4. Rerun focused auth/proxy tests, config-dir/state/startup tests, README/TOML docs checks, full tests, and ruff before slice completion. Human documentation UAT remains S05, not S04.

## Implementation Landscape

### Key Files

- `triggarr/__main__.py` — source of the intended proxy trust boundary. `_run()` passes `proxy_headers=True` and `forwarded_allow_ips=get_trusted_proxy_ips()` to Uvicorn; `get_trusted_proxy_ips()` defaults to `127.0.0.1` and reads `TRUSTED_PROXY_IPS`.
- `triggarr/web/routes.py` — contains `_is_secure_context(request)` and cookie-setting calls for setup, login, and logout. Current helper returns true for any `X-Forwarded-Proto: https` header, independent of proxy trust. Natural seam: change helper to `return request.url.scheme == "https"` and update its docstring.
- `triggarr/web/middleware.py` — `AuthMiddleware._handle_basic_auth()` duplicates secure-cookie logic with a direct `x-forwarded-proto` header check. Natural seam: import/reuse a shared helper or add a small local helper that relies only on `request.url.scheme`.
- `tests/test_root_path.py` — already verifies Uvicorn proxy header configuration and `TRUSTED_PROXY_IPS` defaults/customization. Keep these tests; they prove the proxy trust boundary belongs in Uvicorn config.
- `tests/test_auth_routes.py` — best place for setup/login/logout secure-cookie behavior tests. Existing tests assert the cookie is set and max-age exists; add focused cases for HTTPS base URL and spoofed `X-Forwarded-Proto` on HTTP.
- `tests/test_auth_middleware.py` — best place for Basic-auth secure-cookie tests because Basic auth sets the same session cookie from middleware.
- `README.md` — current auth mode text says `External` trusts a proxy/SSO layer and warns about direct port access, but it should explicitly require upstream authentication/authorization. Reverse-proxy text already documents `TRUSTED_PROXY_IPS`, `ROOT_PATH`, and no wildcard; preserve those details while tightening the External mode wording.
- `SECURITY.md` — current Session Cookies bullet says cookies are marked secure when the request is HTTPS or carries `X-Forwarded-Proto: https` from an IP in `TRUSTED_PROXY_IPS`; that is aspirational unless code changes. After code remediation, update wording to say cookies are marked secure when the ASGI request scheme is HTTPS, including when Uvicorn has accepted forwarded proto from a trusted proxy.
- `TODO.md` — currently accurate as an empty backlog marker and should usually remain unchanged. Include it in stale-marker scans to prove configurable config-dir TODO text has not regressed.
- `.gsd/milestones/M001/slices/S02/S02-SUMMARY.md` — placeholder failure artifact: “Unit complete-slice for M001/S02 failed to produce this artifact…”. This is the evidence gap S04 must repair or supersede.
- `.gsd/milestones/M001/slices/S02/tasks/T01-SUMMARY.md`, `T02-SUMMARY.md`, `T03-SUMMARY.md`, and `T*-VERIFY.json` — real S02 evidence trail. T01 audited stale docs, T02 updated README and parsed README TOML through `Settings`, T03 retired TODO and updated SECURITY. Use these as authoritative S02 evidence if S02 summary cannot be regenerated.
- `.gsd/milestones/M001/slices/S02/tasks/T04-PLAN.md` — pending historical remediation plan that overlaps S04. It proposed doc-only corrections; S04 should supersede it with the stronger code-plus-doc secure-cookie remediation and external-auth wording.

### Build Order

1. **Secure-cookie trust boundary first.** This removes the docs/code contradiction and decides whether SECURITY.md can make the stronger trusted-proxy claim. Implement the smallest shared helper change and add focused tests before editing docs.
2. **External-auth docs second.** Once cookie behavior is settled, update README.md and SECURITY.md auth/proxy wording as trunk docs for operators, not as implementation notes. Per `write-docs`, avoid file paths/line numbers in the trunk prose.
3. **Evidence artifact repair/supersession third.** After source/docs are correct and tested, complete any relevant GSD task artifacts with explicit evidence. Try to repair S02/T04/S02 summary through GSD tools if allowed; otherwise make S04 summaries state exactly why S02 is superseded and point to the real S02 task evidence.
4. **Final verification last.** Run focused tests and scans, then full suite and lint. Do not claim human UAT; S05 owns the human documentation review/release gate.

### Verification Approach

Recommended fresh commands/checks for S04 execution:

- Focused auth/proxy tests after code changes:
  - `uv run pytest tests/test_auth_routes.py tests/test_auth_middleware.py tests/test_root_path.py -q`
  - Add/expect tests showing `Secure` is present for HTTPS requests and absent for plain HTTP with spoofed `X-Forwarded-Proto: https` when the app is exercised directly.
- Existing config-dir regression coverage:
  - `uv run pytest tests/test_config_dir.py tests/test_state.py tests/test_startup.py -q`
- Documentation stale/mismatch scans:
  - no legacy configurable-config TODO text in `README.md SECURITY.md TODO.md .gsd/DEFERRED-BACKLOG.md`
  - no SECURITY claim that direct `X-Forwarded-Proto` alone controls secure cookies after code remediation
  - README/SECURITY mention that `External` requires upstream authentication/authorization and blocked direct access
- README executable example check:
  - extract TOML blocks from README and validate the nested multi-instance example with `tomllib.loads(...)` and `Settings.model_validate(...)`, as S02/S03 established.
- Full confidence:
  - `uv run pytest tests/ -x -q`
  - `uv run ruff check triggarr/ tests/`
- Evidence check:
  - verify either a regenerated real `S02-SUMMARY.md` exists or S04 task/slice summaries explicitly supersede the placeholder and cite S02 task evidence.

## Constraints

- Preserve Docker `/config` as the default when `TRIGGARR_CONFIG_DIR` is unset; S04 should not change config-dir behavior.
- Preserve `SecretStr` discipline and do not expose real API keys, password hashes, session secrets, or generated API keys in docs or logs.
- Preserve auth mode semantics unless deliberately changed: `External` currently passes all non-exempt routes through in `AuthMiddleware`; `Disabled` is allowed by config model but rejected by the security settings UI.
- `TRUSTED_PROXY_IPS` is a startup-level environment variable, not a TOML setting and not a `TRIGGARR_...` Pydantic env override.
- Human documentation UAT and `/deep-review` cannot be collected in auto-mode. S04 may prepare docs/evidence, but S05 must own human approval.
- Existing root `.gsd` v1 artifacts are historical; do not migrate or rewrite them unless explicitly requested.

## Common Pitfalls

- **Only changing docs for secure cookies** — If code still reads `x-forwarded-proto` directly, docs cannot honestly claim `TRUSTED_PROXY_IPS` gates secure-cookie behavior. Either change code or weaken the docs; changing code is preferable.
- **Treating `External` as generic reverse-proxy mode** — `External` bypasses Triggarr auth. Docs must require an upstream identity/authz layer, not merely TLS termination or a trusted network proxy.
- **Pretending S02 evidence is clean** — `S02-SUMMARY.md` is a placeholder failure artifact and GSD status shows S02 complete while T04 is pending. S04 must explicitly repair or supersede this inconsistency instead of relying on S02-SUMMARY as authoritative.
- **Over-verifying only docs scans** — This slice touches an auth/security boundary; focused auth/proxy tests need to accompany markdown scans.
- **Claiming human UAT** — S04 can produce agent-side evidence; S05 owns the human docs-review/release gate.

## Open Risks

- Repairing S02 directly via GSD tools may be rejected because S02 is already marked complete despite T04 being pending. Plan a fallback where S04 supersedes S02 closure evidence with a clear S04 artifact trail.
- Tests using `TestClient` do not run through Uvicorn’s proxy header middleware. That is useful for proving spoofed direct headers no longer affect app-level cookie flags, but it does not by itself prove a real trusted proxy marks `request.url.scheme` as HTTPS; `tests/test_root_path.py` and Uvicorn documentation cover that integration seam.
- If the team decides not to change runtime secure-cookie logic, SECURITY.md must be weakened to say Triggarr currently honors `X-Forwarded-Proto` directly in cookie paths. That resolves documentation accuracy but leaves the trust-boundary concern as a release blocker.

## Skills Discovered

| Technology | Skill | Status |
|------------|-------|--------|
| Documentation/README writing | `write-docs` | Installed and used for fresh-reader/documentation structure guidance |
| Security/API hardening | `security-review`, `api-design` | Installed; consider for final review if S04 changes auth/proxy behavior |
| FastAPI/Uvicorn proxy/security | `secondsky/claude-skills@api-security-hardening` | Available via `npx skills add`; 182 installs |
| FastAPI | `itechmeat/llm-code@fastapi` | Available via `npx skills add`; 65 installs |
| Uvicorn | `slanycukr/riot-api-project@uvicorn` | Available via `npx skills add`; 41 installs |

## Sources

- Uvicorn proxy header behavior: `proxy_headers=True` enables proxy header processing; `forwarded_allow_ips` configures trusted IPs/networks; forwarded headers can be set by anyone, so trusting clients incorrectly can create security vulnerabilities (source: Context7 `/kludex/uvicorn`, topic “proxy_headers forwarded_allow_ips X-Forwarded-Proto scheme trusted proxy”).
- Project memory: README/SECURITY may lag auth behavior; S02-SUMMARY may be a placeholder; human docs review cannot be collected in auto-mode; settings env overrides do not include arbitrary TOML env vars; secure-cookie code directly checks `X-Forwarded-Proto` today.
- Local research artifacts: `.gsd/exec/20d49dde-7685-4c16-9eb1-600f9d62aef2.stdout`, `.gsd/exec/1d9394b1-9b93-4c46-8f0d-8aff663587be.stdout`, `.gsd/exec/488d41f9-4d6f-4517-a06b-bccae934e961.stdout`, `.gsd/exec/f9421a26-0f01-47b7-95cc-ce07b8e42b37.stdout`, `.gsd/exec/2ad00428-af52-42ff-8811-8f72eee0a4ae.stdout`.
