# Phase 71: Presentation rewrite - Context

**Gathered:** 2026-06-02
**Status:** Ready for planning

<domain>
## Phase Boundary

Rewrite Triggarr's public presentation to survive the Phase 70 teardown and reconcile with
the sibling repo **SeedSyncarr**, so genuine quality is evident within 30 seconds and the two
repos read as one coherent author. Surfaces in scope:

- **README.md** (PREW-01) — full rewrite: benefit-led one-liner, centered badge-rich header,
  above-the-fold screenshot, Quick Start, honest feature list, install/quickstart verified
  accurate, security posture as a selling point.
- **SECURITY.md** (PREW-03) — reconcile with v2.8/v2.8.1 hardening + add at-rest-plaintext caveat.
- **Community-health files** (PREW-04) — CONTRIBUTING.md, issue/PR templates, LICENSE confirmed
  present + accurate; the bug-template version/app-type gaps fixed.
- **Repo-metadata text** (PREW-05) — GitHub About / topics / homepage drafted as copy-paste text
  for the maintainer to apply manually (cannot be applied from the session).
- **Release notes + in-app changelog** (PREW-06) — a clean v2.9.0 entry in `CHANGELOG.md` (which
  IS the in-app changelog source; see code_context).
- **Cross-repo signal reconciliation** (PREW-07) — Related Projects cross-link to SeedSyncarr;
  one-liner / section-ordering / security-framing alignment.

**One genuine code change is in scope this phase** (see D-01): widening `validate_arr_url` SSRF
validation into config-load so the README/SECURITY URL-validation claim becomes accurate rather
than scoped-down. Everything else is docs/Markdown/text.

**Out of this phase's body:** fresh screenshots (PREW-02) are captured via Playwright at the
milestone-end NAS walkthrough against the deployed branch build — Phase 71 only updates the
image refs/alt text and leaves placeholders/old images until the walkthrough replaces them.

Covers PREW-01, PREW-02 (refs only; capture at walkthrough), PREW-03, PREW-04, PREW-05, PREW-06,
PREW-07.
</domain>

<decisions>
## Implementation Decisions

### SSRF / URL-validation claim — widen the code, don't scope the doc (D-01..D-03)
- **D-01:** Resolve the codex HIGH finding (README:215 / SECURITY.md:39 overstate SSRF scope —
  `validate_arr_url` runs only in the web settings POST at `web/routes.py:561`, so TOML-set URLs
  bypass validation) by **widening validation into config load** (a real code change), NOT by
  scoping the doc claim down. After this, the URL-validation claim is accurate as written.
- **D-02:** Config-load validation uses a **relaxed variant**, not the strict web-form one:
  on TOML load, **permit loopback/localhost** (running an *arr app on the same host via
  `http://127.0.0.1:7878` / `http://localhost` is a legitimate homelab pattern and must not break
  on upgrade) but **still block cloud-metadata + link-local** (the genuine SSRF targets). The
  web-settings-form path stays strict (unchanged). Private LAN IPs (10.x/192.168.x) are already
  allowed by `validate_arr_url` (intentional — `validation.py:61-62`), so no LAN config breaks.
  Net: "cloud-metadata + link-local blocked everywhere; full scheme + SSRF allow-list enforced on
  web-UI input."
- **D-03:** A covering test is REQUIRED for the new config-load validation path (metadata/link-local
  rejected on load; loopback + private LAN allowed on load). Do not delete or skip any existing
  `validate_arr_url` / web-form validation test. The README:215 and SECURITY.md:39 wording is
  updated to match the now-true behavior (per D-02 net statement).

### README rewrite — full reorder to mirror SeedSyncarr (D-04..D-06)
- **D-04:** **Full section reorder** to mirror SeedSyncarr (not targeted insertions). Target order:
  1. Centered header (badges + tagline) → 2. Above-the-fold representative screenshot →
  3. Quick Start (minimal compose block + "visit http://localhost:8484") → 4. Features →
  5. How It Works → 6. Install (full reference, Docker + standalone) → 7. Configuration Reference →
  8. Screenshots (fuller set) → 9. Security Model → 10. Related Projects → 11. Contributing/Development.
  **Drop the Table of Contents** — a short README reads better without it and SeedSyncarr has none.
- **D-05:** **Header treatment:** centered HTML block (`<div align="center">`) with the existing
  `# Triggarr` H1, **four badges** (CI, Release `shields.io/github/v/release/thejuran/triggarr`,
  Docker, License `shields.io/github/license/thejuran/triggarr`), and the benefit-led tagline
  directly under it. **No new wordmark image asset** — mirror SeedSyncarr's centered/badge-rich
  feel without introducing a design-asset dependency. Align the Docker badge style with
  SeedSyncarr's simpler form (consistency signal 4).
- **D-06:** **Benefit-led one-liner** replaces the dry feature-led one (README:6). Direction (final
  copy is execution-time): lead with the user benefit, e.g. *"Radarr, Sonarr, and Lidarr never
  auto-search for missing or upgrade-eligible media — Triggarr does. Scheduled searches,
  closed-loop grab tracking, runs in Docker."*

### README correctness fixes — locked to the critique hit-list (D-07)
- **D-07:** Every cited correctness/accuracy fix from the three Phase 70 artifacts is in scope and
  locked (no re-litigation): pip-install line must **not hardcode the wheel filename** (currently
  cites `2.7.2`; use a `releases/latest` curl+pip pattern or otherwise version-agnostic) (critique
  Gripe 7 / codex HIGH README:85); **systemd unit** gets `StateDirectory=triggarr` (or a documented
  pre-create step) so first start doesn't fail (codex HIGH README:98-109); **Docker first-run** gets
  one sentence explaining the `sys.exit(1)` + `restart: unless-stopped` behavior so it doesn't read
  as a crash loop (critique Gripe 8 / `config.py:353-359`); **tag-filtering fail-open** behavior is
  documented (codex MEDIUM README:25); **Tailwind version** pinned/aligned in dev docs to match the
  Dockerfile (`TAILWINDCSS_VERSION=v4.2.1` vs committed output.css v4.2.2) (codex MEDIUM
  README:275 / CONTRIBUTING.md:20).

### SECURITY.md — honest selling-point framing (D-08..D-09)
- **D-08:** Enumerate the **v2.8/v2.8.1 hardening** as a confident "what we do" list: CSP `script-src`
  nonce (no `unsafe-inline`), session-secret rotation on password change (CWE-613), `apikey=` URL
  rejection, Basic-auth control-char validation, session-secret startup length check. Framed as a
  maturity signal, not a wall of jargon.
- **D-09:** State the **at-rest-plaintext caveat plainly** (codex MEDIUM SECURITY.md:18,28): API keys,
  auth credentials, and the session secret are plaintext in `triggarr.toml`; `SecretStr` protects
  repr/log/HTML exposure, NOT at-rest secrecy — protect with file permissions + volume security.
  Mirror the caveat the README Security Model already states (README:212). Honesty here is a
  credibility win, not a weakness to hide.

### Community-health fixes — locked (D-10)
- **D-10:** All four community-health files are confirmed present. Fix the cited gaps:
  bug-report.yml version dropdown (tops at v2.3 → add v2.8.1, v2.8, v2.7, v2.6, v2.5, v2.4, "Older")
  (critique Gripe 4); bug-report.yml App Type dropdown (omits Lidarr → add `Lidarr` and `All`)
  (critique Gripe 5). Otherwise confirm CONTRIBUTING.md / PR template / LICENSE accuracy and fix any
  drift found.

### Release notes + in-app changelog — user-facing v2.9.0 entry (D-11..D-12)
- **D-11:** `CHANGELOG.md` **is** the in-app changelog source (`triggarr/changelog.py` reads it from
  disk, Tautulli model). So PREW-06's "release notes" and "in-app changelog" are the **same edit**:
  one `## v2.9.0 (<date>)` entry in `CHANGELOG.md` in the expected Features/Fixes format.
- **D-12:** The v2.9.0 entry lists **user-facing changes**: the SSRF/config-load URL-validation
  hardening (D-01), the manual-search failure-counter fix (Phase 69 SAFETY-03), and the
  docs/presentation overhaul as "Documentation" bullets. Internal-only milestone mechanics
  (gitleaks `.gitleaksignore` fingerprint repair, fastapi/starlette dependency bump,
  `.orchestrator.json` gitignore) go under **Fixes/Security only where user-relevant** — not as a
  comprehensive internal log. Date stamped at execution time (do not invent a date now).

### Repo-metadata text (D-13)
- **D-13:** PREW-05 produces **copy-paste text only** (GitHub About description ≤350 chars, topics/tags
  list, homepage link) for the maintainer to apply in the GitHub web UI — it cannot be applied from
  the session. Reconcile the About one-liner with the new benefit-led README one-liner (D-06) and
  with SeedSyncarr's About framing.

### Claude's Discretion
- Exact final README copy/wording within the locked structure (D-04) and one-liner direction (D-06).
- Exact Quick Start compose block contents (derive from the current Install Docker block, minimized).
- Whether the above-the-fold screenshot (README item 2) and the fuller Screenshots section (item 8)
  use the same image or different ones — both get fresh captures at the walkthrough (PREW-02).
- Exact pip-install resilient pattern (curl+pip vs version-agnostic URL), as long as it stops
  hardcoding the wheel version (D-07).
- Topics/tags list contents for PREW-05.
- Whether to add a one-line `~/seedsync` cross-link note (the separate smaller repo) — optional per
  consistency audit; the canonical sibling is SeedSyncarr.
</decisions>

<specifics>
## Specific Ideas

- The driving goal (spec D-7 / D-07) is **same-author coherence**: a viewer hopping between
  Triggarr and SeedSyncarr (both `thejuran`) should see consistent README structure, security-posture
  framing, and honest positioning — **reconciliation of quality signals, NOT forced homogenization**.
  Each repo keeps its accurate identity; "what this is" stays true to each tool.
- Triggarr **leads** SeedSyncarr on security signals (GSVR reporting vs email; full threat-model
  SECURITY.md vs 5 bullets; documented commit conventions) — do NOT downgrade those to match; they
  are the bar SeedSyncarr will rise to in its own milestone (consistency audit signals 8, 9, 10).
- The **Related Projects cross-link** is the highest-signal trivially-fixable gap (critique Gripe 11
  / audit signal 7): mirror SeedSyncarr's one-line complement — "SeedSyncarr handles the
  download-to-sync side; Triggarr handles the search-to-trigger side."
- Honesty is a feature: the at-rest-plaintext caveat (D-09) and the Docker first-run-exit explanation
  (D-07) both *increase* credibility with the skeptical r/selfhosted reader rather than hiding rough
  edges.
</specifics>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 70 critique artifacts (the gate — these define the rewrite scope)
- `.planning/phases/70-presentation-discovery/70-CRITIQUE.md` — cynical-reader teardown (PDISC-01):
  12 gripes, each with `file:line` evidence + fix direction + PREW mapping. The README/community-health
  hit-list.
- `.planning/phases/70-presentation-discovery/70-CODEX-REVIEW.md` — codex adversarial docs pass
  (PDISC-02): 3 HIGH (pip version, systemd StateDirectory, SSRF claim scope) + 3 MEDIUM (at-rest
  plaintext caveat, tag-filter fail-open, Tailwind version) findings with recommended corrections.
- `.planning/phases/70-presentation-discovery/70-CONSISTENCY-AUDIT.md` — SeedSyncarr cross-repo
  divergence table (PDISC-03): 11 signals, the Phase 71 Action Map, and where Triggarr already leads.

### Milestone design (authoritative scope)
- `docs/superpowers/specs/2026-06-02-launch-hardening-design.md` — §3.2 (presentation track),
  D-6 (hostile take before rewrite), D-7 (cross-repo consistency = reconcile signals not homogenize),
  §5 (definition of done items 3 & 4).
- `.planning/REQUIREMENTS.md` — PREW-01..07 requirement text + success criteria (lines 46-52).

### Triggarr presentation surface being rewritten
- `README.md` — 277 lines; current order ToC → Features → Screenshots → Install → Configuration
  Reference → Security Model → Development. Full rewrite target (D-04).
- `SECURITY.md` — reconcile per D-08/D-09 (PREW-03).
- `CONTRIBUTING.md`, `LICENSE`, `.github/ISSUE_TEMPLATE/bug-report.yml`, `feature-request.yml`,
  `config.yml`, `.github/pull_request_template.md` — community-health (PREW-04); bug-report.yml is
  the one with the version + App-Type gaps (D-10).
- `CHANGELOG.md` — the v2.9.0 release-notes + in-app-changelog target (D-11/D-12).
- `docs/screenshots/dashboard.png`, `history.png`, `settings.png` — current images dated 2026-04-14
  (stale); replaced via Playwright at the walkthrough (PREW-02). Update refs/alt text in this phase;
  recapture at walkthrough.

### Code touched this phase (D-01..D-03)
- `triggarr/web/validation.py` — `validate_arr_url()` (line 56); BLOCKED_HOSTS / `_BLOCKED_NETWORKS`.
  The relaxed config-load variant (D-02) lives here or in config.py.
- `triggarr/config.py` — `InstanceConfig` / TOML load path; `sys.exit(1)` first-run at lines 353-359
  (referenced by the README Docker first-run explanation, D-07).
- `triggarr/web/routes.py:561` — the existing strict web-form validation call site (stays unchanged).
- `triggarr/changelog.py` — reads `CHANGELOG.md` at runtime (Tautulli model); informs D-11. Not
  edited; the edit is to `CHANGELOG.md`.

### Sibling repo (target framing for PREW-07)
- `~/seedsyncarr/README.md` — section order + centered header + Related Projects + benefit-led
  one-liner to align toward.
- `~/seedsyncarr/SECURITY.md`, `~/seedsyncarr/CONTRIBUTING.md` — framing reference.

### Standing codebase context
- `.planning/codebase/CONVENTIONS.md`, `.planning/codebase/STRUCTURE.md`,
  `.planning/codebase/TESTING.md` — for the config-load validation code change + its test.
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`validate_arr_url()`** (`triggarr/web/validation.py:56`) — existing SSRF/scheme validator,
  already allows private LAN IPs (lines 61-62), blocks loopback/link-local/unspecified/multicast +
  metadata hosts + IPv4-mapped IPv6. The config-load path reuses this logic with the loopback
  relaxation (D-02), not a parallel reimplementation.
- **`CHANGELOG.md` + `triggarr/changelog.py`** — the in-app changelog renders `CHANGELOG.md` from
  disk (Tautulli model). One file edit satisfies both "release notes" and "in-app changelog" (D-11).
- **v2.7 favicon/icon asset** (Phase 63) — exists but NOT used for the README header (D-05 chose a
  no-image centered header). Available if a future phase wants a logo mark.
- **Phase 70 three-artifact pattern** — the critique/codex/consistency artifacts are the sole input
  interface; every fix traces back to a cited finding.

### Established Patterns
- Atomic file writes (write-then-rename) for config/state; pydantic validation before any config
  write — the config-load validator (D-01) must fit this existing validation discipline.
- SecretStr for all API keys; `.get_secret_value()` only at HTTP client init — relevant to the
  at-rest-plaintext caveat framing (D-09), do not contradict it.
- pytest-asyncio, `asyncio_mode=auto` — the new config-load validation test follows existing
  config/validation test conventions.

### Integration Points
- The config-load validation (D-01/D-02) hooks the `InstanceConfig` / TOML-load path in
  `triggarr/config.py`; must not regress the existing web-form call site (`routes.py:561`) or any
  existing validation test.
- README/SECURITY URL-validation wording (D-03) must match the post-change behavior exactly.
- README image refs (PREW-02) point at `docs/screenshots/*.png`; the walkthrough replaces the files,
  so refs/alt text are updated in-phase but image freshness is verified at walkthrough.
</code_context>

<deferred>
## Deferred Ideas

- **Fresh screenshots (PREW-02)** — captured via Playwright at the milestone-end NAS walkthrough,
  not in the Phase 71 body. This phase updates refs/alt text only.
- **GitHub repo-metadata application (PREW-05)** — Phase 71 drafts copy-paste text; the maintainer
  applies About/topics/homepage in the GitHub web UI (cannot be done from the session).
- **SeedSyncarr-side reconciliation** — SeedSyncarr rising to Triggarr's security-signal bar (GSVR,
  full threat model, commit conventions) is SeedSyncarr's own milestone, out of scope here
  (consistency audit signals 8, 9, 10).
- **`~/seedsync` (separate smaller repo) cross-link** — optional one-line note; not required.
- Config-knob UI debt (DEBT-03/06/07/08), UI-01/02/03 pixel verification — parked to v2 (spec D-5),
  invisible to a launch reader.

### Reviewed Todos (not folded)
None — `todo.match-phase 71` returned zero matches.
</deferred>

---

*Phase: 71-presentation-rewrite*
*Context gathered: 2026-06-02*
