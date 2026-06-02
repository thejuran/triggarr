# Requirements: Triggarr — v2.9 Launch-Hardening / Sibling Consistency

**Defined:** 2026-06-02
**Core Value:** Reliably trigger searches in Radarr, Sonarr, and Lidarr for missing and upgrade-eligible media on a schedule, with closed-loop feedback — without exposing credentials or expanding attack surface.

> Source spec: `docs/superpowers/specs/2026-06-02-launch-hardening-design.md`. Two equal tracks
> (code substance + presentation) framed around same-author cross-referencing with the sibling
> SeedSyncarr project. Work isolated on a `launch-hardening` branch; `release_intent=true`
> (tag v2.9.0 after merge to `main`).

## v1 Requirements

Requirements for this milestone. Each maps to exactly one roadmap phase.

### Code Discovery

<!-- Hostile-reader pass that gates the fix scope (spec §3.1.1, D-3/D-8). -->

- [x] **CDISC-01**: A hostile-reader code pass runs `ruff check triggarr/ tests/` whole-tree with launch framing and records the result in a triaged findings artifact.
- [x] **CDISC-02**: A hostile-reader code pass runs Shield (Semgrep SAST + gitleaks working-tree secrets + dependency audit) and records findings in the triaged artifact.
- [x] **CDISC-03**: A gitleaks scan runs over the full git **history** (not just working tree); any secret exposed in past commits is identified and recorded as highest-priority.
- [x] **CDISC-04**: The highest-traffic entry-point files (`web/routes.py`, `search/scheduler.py`, `config.py`, `db.py`, `auth.py`, `startup.py`) are skimmed with "what would a skeptical r/selfhosted engineer find" framing, with notes captured in the artifact.
- [x] **CDISC-05**: The discovery produces a single triaged findings artifact where each finding is classified fold-in (launch-visible, fix this milestone) or parked (with written rationale).

### Code Hardening

<!-- Curated known items + folded-in discovery findings (spec §3.1.2, D-4). -->

- [x] **CHARD-01**: The repo-hygiene gap is closed — `.orchestrator.json` is git-ignored, and no untracked transient or accidentally-tracked editor/tooling artifact remains (audit-and-close, not a fixed checklist).
- [x] **CHARD-02**: SAFETY-03 is resolved — manual searches via `/search-now/{app}/{instance}` and scheduled cycles share one failure-counting path, so manual-search failures increment and reset the consecutive-failure counter identically to scheduled cycles; the `# TODO` at `scheduler.py:~325` is removed.
- [x] **CHARD-03**: A test covers manual-search failure increment/reset (proving CHARD-02), with no existing scheduler failure-counter test deleted or skipped.
- [x] **CHARD-04**: Every discovery finding classified fold-in (CDISC-05) is fixed; every parked finding is recorded with rationale in the findings artifact.

### Presentation Discovery

<!-- Hostile take + cross-repo consistency, before any rewrite (spec §3.2, D-6/D-7). -->

- [ ] **PDISC-01**: A framed cynical-reader ("r/selfhosted commenter") teardown of Triggarr's positioning, credibility, and first impression is captured as a written artifact.
- [ ] **PDISC-02**: A codex adversarial pass runs against the existing README + docs (technical-claims accuracy, broken/incomplete install/quickstart, unsupported assertions), with findings captured.
- [ ] **PDISC-03**: A same-author cross-repo consistency audit compares Triggarr's README structure, security-posture framing, badge style, and "what this is" one-liner against SeedSyncarr's, recording divergences to reconcile.

### Presentation Rewrite

<!-- Driven by PDISC findings (spec §3.2). -->

- [ ] **PREW-01**: The README is rewritten to survive the teardown — instantly-clear one-liner, current screenshots above the fold, honest feature list, install/quickstart verified accurate against current behavior, security posture stated as a selling point.
- [ ] **PREW-02**: Fresh, real screenshots (dashboard, search history, settings) are captured via Playwright during the NAS walkthrough against the deployed branch build with representative data and no exposed API keys/hostnames/credentials; README image refs and alt text updated to match.
- [ ] **PREW-03**: SECURITY.md is reconciled with the v2.8/v2.8.1 hardening (CSP nonces, session-secret rotation on password change, `apikey=` rejection, Basic-auth control-char validation) and reads as an honest, mature threat-model + reporting policy.
- [ ] **PREW-04**: Community-health files (CONTRIBUTING.md, issue/PR templates, LICENSE) are confirmed present and accurate; gaps fixed.
- [ ] **PREW-05**: GitHub repo-metadata text (About description, topics/tags, homepage link) is drafted as copy-paste text for the maintainer to apply manually.
- [ ] **PREW-06**: A clean v2.9.0 release-notes entry is written and the in-app changelog is updated to match.
- [ ] **PREW-07**: Triggarr's quality signals (one-liner, section ordering, security framing) are reconciled against SeedSyncarr per the PDISC-03 audit so the two repos read as one coherent author (reconciliation of signals, not forced homogenization).

## v2 Requirements

Deferred — tracked but not in this milestone's roadmap.

### Config Knobs (parked — invisible to a launch reader, spec D-5)

- **DEBT-07**: Expose HTTP request timeout in the settings UI.
- **DEBT-08**: Expose *arr API page size in the settings UI.
- **DEBT-03**: Expose search-history cap in the settings UI.
- **DEBT-06**: Surface graceful-shutdown drain timeout in the settings UI.

### Carried-forward UI verification (v2.6)

- **UI-01/02/03**: Pixel-exact auth-page (login/setup/settings-security) visual verification — `human_needed`, behind first-run setup, not launch-visible.

## Out of Scope

Explicitly excluded this milestone. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| New user-facing features | Launch-hardening milestone — close holes + rebuild presentation, don't add surface |
| Config-knob UI debt (DEBT-03/06/07/08) | Real debt but invisible to a launch reader; parked to v2 (spec D-5) |
| UI-01/02/03 pixel-exact auth verification | Behind first-run setup; not launch-visible; `human_needed` |
| `--color-triggarr-primaryDark` duplicate-token cleanup | Cosmetic, invisible to a launch reader |
| Broad refactoring beyond a specific finding | Only fix what a discovery finding justifies; avoid scope drift |

## Traceability

Which phases cover which requirements. Populated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| CDISC-01 | Phase 68 | Complete |
| CDISC-02 | Phase 68 | Complete |
| CDISC-03 | Phase 68 | Complete |
| CDISC-04 | Phase 68 | Complete |
| CDISC-05 | Phase 68 | Complete |
| CHARD-01 | Phase 69 | Complete |
| CHARD-02 | Phase 69 | Complete |
| CHARD-03 | Phase 69 | Complete |
| CHARD-04 | Phase 69 | Complete |
| PDISC-01 | Phase 70 | Pending |
| PDISC-02 | Phase 70 | Pending |
| PDISC-03 | Phase 70 | Pending |
| PREW-01 | Phase 71 | Pending |
| PREW-02 | Phase 71 | Pending |
| PREW-03 | Phase 71 | Pending |
| PREW-04 | Phase 71 | Pending |
| PREW-05 | Phase 71 | Pending |
| PREW-06 | Phase 71 | Pending |
| PREW-07 | Phase 71 | Pending |

**Coverage:**
- v1 requirements: 19 total
- Mapped to phases: 19 ✓ (Phase 68 ×5, Phase 69 ×4, Phase 70 ×3, Phase 71 ×7)
- Unmapped: 0 ✓

---
*Requirements defined: 2026-06-02*
*Last updated: 2026-06-02 after roadmap creation (phases 68-71 mapped)*
