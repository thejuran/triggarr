# Phase 68 — Code-track hostile-reader discovery: FINDINGS

> **This file (`68-FINDINGS.md`) is the AUTHORITATIVE discovery artifact for Phase 68.**
> Its [`## Fold-In Summary`](#fold-in-summary) section is the fix checklist that **Phase 69 (CHARD-04)**
> consumes directly, without re-investigation. The GSD per-plan `68-01-SUMMARY.md` is execution
> bookkeeping, **not** a discovery deliverable — when the two disagree, this file wins.

This artifact is the product of a deliberate *"this is on Reddit and a skeptical r/selfhosted engineer
is reading the repo, the README, and `git log`"* hostile pass over Triggarr's whole code surface, its
launch-visible self-hosting surface (Docker / compose / entrypoint / templates / htmx / middleware / CI),
and its **full git history across all refs**. This phase writes **no source code** — it runs read-only
discovery tools and records + triages their output.

---

## Scan Provenance

| Field | Value |
|-------|-------|
| Run date | 2026-06-02 |
| Branch | `launch-hardening` |
| Repo | Triggarr (`ghcr.io/thejuran/triggarr`) |
| gitleaks version | `8.30.1` |
| semgrep version | `1.136.0` |
| pip-audit version | `pip-audit 2.10.0` |
| uv version | `uv 0.10.2 (a788db7e5 2026-02-10)` |
| **All-refs commit count** (`git rev-list --count --all`) | **1036** |
| HEAD commit count (`git rev-list --count HEAD`) | 1026 |
| ruff ruleset | `E, F, I, UP, B, SIM` (line-length 120, target py311 — from `pyproject.toml`) |

> **The history section cites the ALL-REFS count (1036), not the HEAD count (1026).** On this repo the two
> differ by 10 commits, so an all-refs scan must state the all-refs figure to be honest about coverage.

---

## Schema (read before classifying anything)

### Classification bar (LOCKED — 68-CONTEXT.md D-04)

- **FOLD-IN** if **(a) launch-visible** — something a skeptical r/selfhosted engineer browsing the repo /
  README / `git log` would actually see and ding — **OR (b) any real security or secret exposure**,
  regardless of visibility.
- **PARK** pure-internal nitpicks (style the linter doesn't enforce, invisible debt, cosmetic items) —
  with written rationale.
- **NARROWED HARD RULE (F-5):** the config-knob **UI-exposure** debt — *"the setting EXISTS in the model
  but is NOT exposed in the settings UI"* — (DEBT-03 history cap, DEBT-06 drain timeout, DEBT-07 request
  timeout, DEBT-08 page size; UI-01/02/03 auth-page pixel verification) **MUST NOT** be folded in even if a
  tool surfaces it. Record it PARKED with rationale *"spec D-5: UI-exposure debt, invisible to launch
  reader, parked to v2."*
- **TIEBREAKER (F-5):** an *independent* security / secret / runtime-correctness / launch-visible finding
  that merely happens to touch the same file or setting as a pre-parked knob still applies the D-04 bar
  normally and **CAN** be FOLD-IN. Only the UI-exposure debt *itself* is forced PARKED.

### Source classification matrix (F-8)

- **FOLD-IN sources:** any security finding, any secret exposure, any runtime-correctness defect, any
  user-visible failure (crash, wrong result, broken install/quickstart, leaked internals in a response).
- **PARKED sources** (unless they produce a visible failure): pure style the linter does not enforce,
  import-ordering (ruff `I`), pyupgrade modernization (ruff `UP`) with no behavior change, test-only cleanup.
- **AMBIGUOUS:** if a finding does not cleanly fall into either bucket, it requires a written one-sentence
  *"why a Reddit reviewer would notice"* justification **before** it may be marked FOLD-IN. With no such
  justification it is PARKED.

### FOLD-IN row schema (every FOLD-IN row carries all of these — F-6/F-9)

| Field | Meaning |
|-------|---------|
| **ID** | Stable `P68-FI-NNN` (zero-padded, assigned sequentially across all sources) |
| **Source** | `ruff` / `semgrep` / `gitleaks` / `pip-audit` / `skim` |
| **Locator** | `file:line` OR commit SHA (history hits) |
| **Rule/Advisory** | ruff rule code / semgrep rule ID / CVE-or-advisory ID / gitleaks rule |
| **Severity** | tool severity or assessed severity |
| **Evidence** | sanitized — **never** the raw secret value |
| **Rationale** | applies the D-04 bar + the source matrix |
| **Remediation** | concrete fix Phase 69 applies |
| **Verify cmd** | command Phase 69 runs to confirm the fix |

### PARKED row schema (lighter)

| Field | Meaning |
|-------|---------|
| **Source** | which discovery source surfaced it |
| **Locator** | `file:line` or summary scope |
| **Classification** | `PARKED` |
| **Rationale** | one-line written reason it is parked |

### Tool contract (F-2 + F-3)

Structured JSON output is the contract; capture it, then classify rows from it. **All four tools use a
NON-ZERO exit code to mean "findings exist," NOT "the command failed."** A finding-exit-code is
**SUCCESS-WITH-FINDINGS** (capture + classify). A genuine failure (tool-not-found, flag rejected, parse
error, crash) is a **DISCOVERY FAILURE**, recorded separately in the section's `Discovery status:` line —
a discovery failure on a required source **FAILS** the phase gate.

---

## ruff

*Discovery status:* Command `uv run ruff check triggarr/ tests/ --output-format json` — **exit 0** (clean,
not a finding-exit). JSON output was `[]` (0 violations). This is a genuine clean result, not a discovery
failure. **ruff clean, 0 violations.**

No FOLD-IN or PARKED rows: the whole tree (`triggarr/` + `tests/`) passes the project ruleset
(E/F/I/UP/B/SIM, line-length 120) with zero violations. A skeptical reviewer running `ruff check` sees a
clean tree.

| ID | Source | Locator | Rule | Severity | Evidence | Rationale | Remediation | Verify cmd |
|----|--------|---------|------|----------|----------|-----------|-------------|------------|
| _(none — ruff clean, 0 violations)_ | | | | | | | | |

---

## Shield (Semgrep)

*Discovery status:* Command `semgrep scan --json --config auto triggarr/` — **exit 0**. 11 results + 2
`PartialParsing` *warn*-level errors (semgrep's Jinja parser choked on `{% extends %}` in `dashboard.html`
and `setup.html` — a tool template-coverage limitation, **not** a discovery failure; the SAST scan itself
completed). Direct command is the primary contract; Shield skill not used. Every one of the 11 results was
examined against the source and `.planning/codebase/CONVENTIONS.md` — **all 11 are false positives against
established, verified-safe intentional patterns. Zero FOLD-IN.**

**Why each is PARKED (cross-checked against the actual source):**

| Semgrep rule | Locators | Disposition + rationale |
|--------------|----------|-------------------------|
| `formatted-sql-query` + `sqlalchemy-execute-raw-query` | `db.py:124`, `db.py:132`, `db.py:552`, `db.py:703` | **PARKED — false positive.** All four are f-string SQL where the interpolated tokens are **hardcoded SQL identifiers** (migration column names/types from literal tuples at `db.py:122-133`) or **allowlisted column names** (`stat_increments` keys validated against `_ALLOWED_STAT_COLUMNS` at `db.py:682` before use, with an existing reviewed `# noqa: S608` at `db.py:704`). All user-facing **values** go through `?` placeholders + a separate `params` list (`db.py:519-548`) — never interpolated. No injection path. Semgrep flags any f-string reaching `.execute()` regardless of source-of-data. |
| `flask...direct-use-of-jinja2` | `routes.py:61` | **PARKED — false positive.** The `jinja2.Environment(...)` at `routes.py:61` explicitly sets `autoescape=True` (`routes.py:63`). Output is auto-escaped; the rule fires on any manual `Environment()` construction. |
| `django...raw-html-format` | `routes.py:754` | **PARKED — false positive.** The `<option>` HTML is assembled with `html.escape(tag.label)` on every interpolated value (`routes.py:754`). Output is escaped; no XSS path. |
| `django-no-csrf-token` | `base.html:81`, `settings.html:100`, `settings.html:256` | **PARKED — wrong-stack rule.** This is a **Django** template rule; Triggarr is FastAPI + htmx, not Django, so `{% csrf_token %}` does not apply. CSRF is defended by `samesite="lax"` on all session cookies (`middleware.py:199`, `routes.py:1223/1360/1389/1487`) and an explicit non-htmx-request 403 reject on mutating routes (`routes.py:1102`). Same-origin posture is intact; no Django CSRF token is the correct design here. |

| ID | Source | Locator | Rule | Severity | Evidence | Rationale | Remediation | Verify cmd |
|----|--------|---------|------|----------|----------|-----------|-------------|------------|
| _(none FOLD-IN — all 11 semgrep results are verified false positives, parked per table above)_ | | | | | | | | |

---

## Shield (gitleaks working-tree)

*Discovery status:* Command `gitleaks git . --no-banner --report-format json --report-path <tmp> --redact`
— **exit 1 = leaks-found (success-with-findings, NOT a failure)**; 1007 commits scanned, 23 hits reported.
Cross-checked with a working-tree-only `gitleaks dir . --no-banner --report-format json --redact` run
(exit 1, 163 hits incl. gitignored transients). Direct command is the primary contract; Shield skill not
used. **Every hit is rule `generic-api-key` (gitleaks' highest-false-positive rule); zero real
credentials.** Hits resolve to three buckets: (a) test-fixture dummy keys (`api_key="..."` in `tests/`),
(b) prose/phrase matches in planning-doc Markdown (`.planning/`, `.gsd/`, `reports/` — e.g.
`.planning/codebase/TESTING.md:390`, `S06-HUMAN-UAT-GATE.md:19` matching the word "warnings"), and
(c) gitignored transients (`.gsd/gsd.db-wal` ×134, `__pycache__/*.pyc`) that are **not in a clone** and so
not part of the reviewer's surface.

**The one material finding here is the tooling itself, not a leaked secret:** the existing `.gitleaksignore`
is **non-functional** under gitleaks 8.30.x — all 4 bare-filepath entries are rejected with
`WRN Invalid .gitleaksignore entry` (gitleaks 8.x requires *fingerprints* `commitSHA:filepath:rule:line`,
not bare paths). So the intended 4-file test-fixture allowlist provides **zero** suppression today, and a
skeptical reviewer who runs gitleaks sees 4 "Invalid entry" warnings + "leaks found: 23". That is
launch-visible repo-hygiene (FOLD-IN). The dummy-key and doc-prose hits themselves are PARKED as confirmed
false positives.

| ID | Source | Locator | Rule | Severity | Evidence | Rationale | Remediation | Verify cmd |
|----|--------|---------|------|----------|----------|-----------|-------------|------------|
| **P68-FI-001** | gitleaks (working-tree) | `.gitleaksignore` (whole file); reproduced by `gitleaks git .` / `gitleaks dir .` | gitleaks `Invalid .gitleaksignore entry` + `generic-api-key` noise | Low (hygiene/tooling — launch-visible) | `WRN Invalid .gitleaksignore entry fingerprint=tests/test_auth_*.py` ×4; `WRN leaks found: 23` (all `generic-api-key`, all test-fixture dummy keys or doc-prose false positives — no real secret) | **D-04 (a) launch-visible:** a reviewer running gitleaks sees "Invalid entry" warnings + 23 "leaks", which reads as a broken/ignored secret-scan posture. The allowlist that is *supposed* to suppress the 4 test-fixture files does nothing because 8.30.x rejected the bare-path syntax. Not a real secret exposure, but a visible tooling/hygiene defect. | Convert `.gitleaksignore` to gitleaks-8.x fingerprint entries (or move the test-fixture allowlist into a `[allowlist] paths = [...]` regex block in a `gitleaks.toml` config), so the 4 test-fixture files are suppressed cleanly. Optionally tune `generic-api-key` to stop matching planning-doc prose, or add the doc dirs to an allowlist `paths`. Goal: `gitleaks git .` exits 0 with no "Invalid entry" warnings. | `gitleaks git . --no-banner --redact 2>&1 \| grep -E "Invalid .gitleaksignore entry\|leaks found"` returns no "Invalid entry" lines and `leaks found: 0` (or only intentionally-allowlisted fingerprints) |

**PARKED (false-positive `generic-api-key` hits — not real secrets):**

| Source | Locator (representative) | Classification | Rationale |
|--------|--------------------------|----------------|-----------|
| gitleaks (working-tree) | `tests/test_auth_*.py`, `tests/test_config.py:24/363`, `tests/test_logging.py:14` | PARKED | Test-fixture dummy API keys (`api_key="..."` literals in unit tests) — the very files the `.gitleaksignore` was meant to allowlist; not real credentials. (Suppressing them is the remediation of P68-FI-001.) |
| gitleaks (working-tree) | `.planning/**`, `.gsd/**`, `reports/security-2026-04-15.md` Markdown | PARKED | `generic-api-key` phrase/entropy matches in planning-doc prose (e.g. the word "warnings"); no secret value present (`--redact` shows nothing exploitable). Pure scanner noise. |
| gitleaks (working-tree, `dir` mode) | `.gsd/gsd.db-wal`, `tests/__pycache__/*.pyc` | PARKED | Gitignored runtime transients — confirmed `git check-ignore` matches; absent from any clone, so outside the reviewer's surface entirely. |

---

## Shield (dependency audit)

*Discovery status:* Primary command `uv run pip-audit --format json` — **exit 1 = vulns-found
(success-with-findings)** — but that run emitted `WARNING: pip-audit will run pip against
.../pipx/venvs/pip-audit/bin/python ... your local environment will not be audited`, i.e. it audited the
**pipx tool venv**, not Triggarr. Its 5 "vulns" (`idna@3.13`, `pip@26.0.1` ×2, `urllib3@2.6.3` ×2) are
**pipx-environment noise** — Triggarr's `uv.lock` pins `idna@3.15` (already the CVE-2026-45409 fix; PR #19
bumped it) and ships **no** `urllib3`/`pip`. To audit the *project's* actual locked dependencies I ran the
authoritative command `uv export --no-dev --no-emit-project --format requirements-txt > reqs.txt &&
uv run pip-audit -r reqs.txt --format json` — **exit 1**, 35 project deps audited, **1 real vulnerability
in 1 shipped dependency:** `starlette@0.52.1 → PYSEC-2026-161`. Direct command is the primary contract;
Shield skill not used.

> **Recorded discovery caveat (not a failure):** the bare `pip-audit` invocation silently targets the pipx
> tool venv on this machine, so the project audit MUST go through `uv export ... | pip-audit -r`. The
> verify command below uses that authoritative form.

| ID | Source | Locator (pkg@ver) | Advisory/CVE | Severity | Evidence | Rationale | Remediation | Verify cmd |
|----|--------|-------------------|--------------|----------|----------|-----------|-------------|------------|
| **P68-FI-002** | pip-audit (project lock) | `starlette@0.52.1` (transitive via `fastapi@0.133.0`) | `PYSEC-2026-161` (alias `GHSA-86qp-5c8j-p5mr`) | Medium (security — auth-relevant) | pip-audit on `uv export --no-dev`: `starlette@0.52.1 -> PYSEC-2026-161 fix=['1.0.1']`. Advisory: Starlette reconstructs the request URL from the unvalidated `Host` header, allowing path injection into the host part — *"may lead to authentication bypass when authentication depends on the reconstructed URL's path."* | **D-04 (b) real security exposure** (always FOLD-IN regardless of visibility): a published CVE in a shipped production dependency. Triggarr runs custom auth middleware, so a Host-header/URL-reconstruction auth-bypass class is directly relevant. (Mitigating factor for Phase 69 to confirm: Triggarr's `AuthMiddleware` routes on the actual request path, not a reconstructed URL — practical exposure may be low — but the fix is a clean version bump regardless.) | Bump `starlette` to `>=1.0.1` via the `fastapi` dependency (raise the `fastapi` pin to a release whose resolved `starlette` is ≥1.0.1, or add a direct `starlette>=1.0.1` constraint), then `uv lock` + re-audit. Confirm no API breakage from the starlette 0.x→1.x major. | `uv export --no-dev --no-emit-project --format requirements-txt > /tmp/r.txt && uv run pip-audit -r /tmp/r.txt --format json \| python3 -c "import json,sys; d=json.load(sys.stdin); v=[x for x in d['dependencies'] if x.get('vulns')]; print('CLEAN' if not v else v)"` returns `CLEAN` |

**PARKED (pipx-tool-environment noise — NOT shipped by Triggarr):**

| Source | Locator | Classification | Rationale |
|--------|---------|----------------|-----------|
| pip-audit (default invocation) | `idna@3.13`, `pip@26.0.1`, `urllib3@2.6.3` | PARKED | The bare `pip-audit` run audited the pipx tool venv, not the project. Triggarr's `uv.lock` pins `idna@3.15` (already fixed) and ships no `urllib3`/`pip`. Not part of the deployed image's dependency set; out of scope per the source matrix (no project-visible failure). |

---

## gitleaks (full history)

*Discovery status:* _(pending — populated in Task 3)_

| ID | Source | Locator (commit SHA) | Rule | Severity | Evidence (redacted) | Rationale | Remediation | Verify cmd |
|----|--------|----------------------|------|----------|---------------------|-----------|-------------|------------|
| _(empty — populated in Task 3)_ | | | | | | | | |

---

## public-surface inventory

*Discovery status:* _(pending — populated in Task 4)_

_(empty — populated in Task 4: each launch-visible non-Python surface item either skimmed or carries an
explicit not-present / covered-by / out-of-scope line)_

---

## entry-point skim

*Discovery status:* _(pending — populated in Task 4)_

_(empty — populated in Task 4: hostile ~2-min surface skim of the six entry-point files with the extended
smell list, file:line anchors for anything flagged)_

| ID | Source | Locator | Rule/smell | Severity | Evidence | Rationale | Remediation | Verify cmd |
|----|--------|---------|-----------|----------|----------|-----------|-------------|------------|
| _(empty — populated in Task 4)_ | | | | | | | | |

---

## Fold-In Summary

> **This is Phase 69's CHARD-04 fix checklist.** Every `P68-FI-NNN` that appears as FOLD-IN in a source
> section above appears here exactly once, with the same rich metadata. One-to-one, no gaps, no duplicates.

*Discovery status:* _(pending — consolidated in Task 5)_

| ID | Source | Locator | Rule/Advisory | Severity | Remediation | Verify cmd |
|----|--------|---------|---------------|----------|-------------|------------|
| _(empty — consolidated in Task 5)_ | | | | | | |

---

## Cross-check against CONCERNS.md

*Discovery status:* _(pending — populated in Task 5)_

_(empty — populated in Task 5: reconcile discovery findings against `.planning/codebase/CONCERNS.md`; for
each relevant catalogued item note whether this pass re-confirmed it; confirm the two curated known items —
`.orchestrator.json` gitignore gap and SAFETY-03 — are recorded and in the Fold-In Summary)_
