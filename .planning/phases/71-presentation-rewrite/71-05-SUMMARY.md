---
phase: 71-presentation-rewrite
plan: "05"
subsystem: documentation / presentation
tags: [readme, documentation, tailwind, repo-metadata, ssrf, prew-01, prew-02, prew-05, prew-07]
dependency_graph:
  requires: ["71-02"]
  provides: ["README-rewrite", "Dockerfile-tailwind-alignment", "repo-metadata-copy-paste"]
  affects:
    - README.md
    - Dockerfile
    - CONTRIBUTING.md
    - docs/repo-metadata.md
tech_stack:
  added: []
  patterns:
    - "D-04 section order: centered header → above-fold screenshot → Quick Start → Features → How It Works → Install → Config Reference → Screenshots → Security Model → Related Projects → Contributing"
    - "version-agnostic pip install via GitHub releases/latest API curl pattern"
    - "SSRF claim quoted verbatim from 71-02-SUMMARY.md precise net-behavior statement"
key_files:
  created:
    - docs/repo-metadata.md
  modified:
    - README.md
    - Dockerfile
    - CONTRIBUTING.md
decisions:
  - "pip install uses curl-to-releases/latest API pattern (Option A from research) — never goes stale, no hardcoded wheel filename"
  - "SSRF claim in Security Model quotes the exact 71-02-SUMMARY.md net-behavior statement verbatim (not broadened)"
  - "Dockerfile TAILWINDCSS_VERSION updated to v4.2.2 (matches committed output.css header)"
  - "docs/repo-metadata.md 181-char About — well within 350-char limit"
  - "PREW-02 screenshot CAPTURE deferred to NAS walkthrough; refs/alt text updated, ?v= dropped"
metrics:
  duration: "~25 minutes"
  completed: "2026-06-02"
  tasks: 2
  files: 4
---

# Phase 71 Plan 05: README Rewrite + Tailwind Alignment + Repo Metadata Summary

Full rewrite of README.md in D-04 section order with all D-05/D-06/D-07 correctness fixes; Tailwind version aligned between Dockerfile and committed output.css; GitHub repo-metadata copy-paste text drafted in docs/repo-metadata.md.

## Tasks Completed

| Task | Description | Commit |
|------|-------------|--------|
| 1 | Full README.md rewrite in D-04 order with all fixes | `19ed397` |
| 2 | Dockerfile Tailwind alignment + CONTRIBUTING.md + docs/repo-metadata.md | `1de0f5e` |

## Implementation Details

### Task 1 — README.md Full Rewrite

Section order per D-04: centered `<div align="center">` header (H1 + 4 badges + benefit-led tagline), above-fold screenshot, Quick Start, Features, How It Works, Install, Configuration Reference, Screenshots, Security Model, Related Projects, Contributing / Development. Table of Contents dropped.

**Correctness fixes applied:**

- **pip install (D-07 / codex HIGH):** Replaced the hardcoded `triggarr-2.7.2-py3-none-any.whl` URL with two options — a reference to the [latest release page](https://github.com/thejuran/triggarr/releases/latest) for manual download, and a curl-to-GitHub-releases-API pattern that derives the `.whl` `browser_download_url` at runtime. No wheel filename is hardcoded. `grep -E 'triggarr-[0-9]+\.[0-9]+\.[0-9]+-py3-none-any\.whl' README.md` returns exit 1 (no match).

- **systemd StateDirectory (codex HIGH):** `StateDirectory=triggarr` added after the `Environment=TRIGGARR_CONFIG_DIR=/var/lib/triggarr` line. Explanation added: instructs systemd to create and own `/var/lib/triggarr` before the service starts.

- **Docker first-run sys.exit(1) (D-07 / Gripe 8):** One clear sentence added to the Docker first-run paragraph: "On an empty volume, the first run exits with code 1 after writing a default `triggarr.toml` — this is expected, not a crash. Docker's `restart: unless-stopped` brings the container back up automatically."

- **Tag-filter fail-open (codex MEDIUM):** Features section documents fail-open: "if a configured tag cannot be resolved or tag fetch fails, Triggarr logs a warning and searches all items for that queue (fail-open)."

- **SSRF claim (codex HIGH):** Security Model updated with a "URL validation and SSRF protection" subsection. The precise net-behavior statement is quoted verbatim from 71-02-SUMMARY.md without broadening: loopback IP literals permitted at config load, blocked only by the web form; `localhost` hostname not resolved and permitted in both paths; arbitrary DNS not resolved = accepted residual risk; link-local/unspecified/multicast IP literals + known metadata hosts blocked both paths. The old broad "loopback, unspecified, or multicast targets" bullet is replaced.

- **External-auth wording (test invariant):** The External mode description explicitly states upstream authentication AND authorization required, and direct access to port 8484 must be blocked. Preserved through reorder.

- **X-Forwarded-Proto / Uvicorn / ASGI scheme / trusted_proxy_ips wording (test invariant):** The Reverse Proxy section preserved verbatim: "accepted `X-Forwarded-Proto` values become the ASGI request scheme used by scheme-aware behavior such as Secure cookie emission." No forbidden direct-trust phrasing introduced.

- **TAILWINDCSS_VERSION=v4.2.2 on dev watch command:** Contributing / Development section includes `TAILWINDCSS_VERSION=v4.2.2 uv run tailwindcss ... --watch`.

- **Related Projects (PREW-07):** `## Related Projects` section added: cross-link to SeedSyncarr mirroring SeedSyncarr's complement description ("SeedSyncarr handles the download-to-sync side; Triggarr handles the search-to-trigger side.").

- **Screenshot refs (PREW-02 refs-only):** `?v=2` cache-buster dropped from all three screenshot refs; alt text updated to descriptive form. PNG files unchanged (capture deferred to NAS walkthrough).

- **No stale claims:** No retired claims (no built-in authentication, config-dir-not-configurable) introduced.

- **TOML blocks valid:** The Configuration Reference TOML block is preserved unchanged from the original and validates against `Settings.model_validate()`.

### Task 2 — Tailwind Alignment + CONTRIBUTING.md + repo-metadata.md

- **Dockerfile:** `ENV TAILWINDCSS_VERSION=v4.2.1` → `v4.2.2` (matches committed `triggarr/static/css/output.css` header `tailwindcss v4.2.2`).
- **CONTRIBUTING.md:** Dev CSS command updated to `TAILWINDCSS_VERSION=v4.2.2 uv run tailwindcss ... --watch` with inline comment `# (must match Dockerfile TAILWINDCSS_VERSION)`.
- **docs/repo-metadata.md:** New file with copy-paste text for GitHub Settings > About. About description: 181 chars (limit 350). Topics list: radarr, sonarr, lidarr, arr, self-hosted, docker, automation, homelab, media-automation, python, fastapi, htmx, scheduler. Homepage: `https://github.com/thejuran/triggarr`. Manual-apply note at top of file.

## Verification Results

- `uv run pytest tests/test_docs_accuracy.py tests/test_community_health.py -x -q`: **25 passed**
  - `test_readme_toml_examples_parse_and_validate_as_settings` — PASSED (TOML block valid Settings)
  - `test_external_auth_docs_require_upstream_authz_and_blocked_direct_access` — PASSED
  - `test_secure_cookie_docs_use_asgi_scheme_not_direct_forwarded_proto_trust` — PASSED
  - `test_tracked_docs_do_not_reintroduce_stale_auth_or_config_dir_claims` — PASSED
- `grep -E 'triggarr-[0-9]+\.[0-9]+\.[0-9]+-py3-none-any\.whl' README.md` → exit 1 (no match) — PASSED
- `grep -q 'releases/latest' README.md` → exit 0 — PASSED
- `grep -q 'StateDirectory=triggarr' README.md` → exit 0 — PASSED
- `grep -qi 'seedsyncarr' README.md` → exit 0 — PASSED
- All four badge URLs present — PASSED
- `TAILWINDCSS_VERSION=v4.2.2` in README.md, Dockerfile, CONTRIBUTING.md — PASSED
- No `?v=` in screenshot refs — PASSED
- `fail-open` in Features section — PASSED
- About text: 181 chars (≤350) — PASSED

## Deviations from Plan

None — plan executed exactly as written.

PREW-02 screenshot CAPTURE is deferred to the milestone-end NAS walkthrough (only refs/alt text updated here), as specified in the plan.

PREW-05 repo-metadata requires manual application by the maintainer in the GitHub web UI — docs/repo-metadata.md delivers the copy-paste text.

The pip-install line hardcodes no wheel filename: the `releases/latest` API curl pattern (Option A from research) was chosen over Option B (update filename) — Option A never goes stale and avoids recreating the Phase 70 HIGH finding at the next release.

## Known Stubs

None. The README, Dockerfile, CONTRIBUTING.md, and docs/repo-metadata.md contain no placeholder data that prevents the plan's goals from being achieved. Screenshot files are real (existing PNGs), only fresh captures are deferred.

## Threat Flags

None. No new security-relevant surface introduced. All edited files are Markdown, a Dockerfile build-arg pin, and a docs copy-paste file. The SSRF claim in the README Security Model section now accurately reflects the post-plan-02 code behavior without overstating coverage.

## Self-Check: PASSED

- README.md: `## Quick Start` present — FOUND
- README.md: `## Related Projects` present — FOUND
- README.md: `## Security Model` present — FOUND
- README.md: No `## Table of Contents` — CONFIRMED
- README.md: No `triggarr-X.Y.Z-py3-none-any.whl` — CONFIRMED (grep exit 1)
- README.md: `releases/latest` present — FOUND
- README.md: `StateDirectory=triggarr` present — FOUND
- README.md: `seedsyncarr` cross-link present — FOUND
- README.md: All 4 badge URLs present — FOUND
- README.md: `TAILWINDCSS_VERSION=v4.2.2` present — FOUND
- README.md: No `png?v=` — CONFIRMED
- README.md: `fail-open` present — FOUND
- Dockerfile: `TAILWINDCSS_VERSION=v4.2.2` present, no `v4.2.1` — FOUND
- CONTRIBUTING.md: `TAILWINDCSS_VERSION=v4.2.2` present — FOUND
- docs/repo-metadata.md: exists — FOUND
- Commit `19ed397` exists — FOUND
- Commit `1de0f5e` exists — FOUND
- 25 tests pass — VERIFIED
