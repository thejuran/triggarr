# Launch-Hardening (Sibling Consistency) — Design Spec

**Date:** 2026-06-02
**Status:** Approved (brainstorming) — pending user review before handoff to `/gsd:new-milestone`
**Proposed version:** v2.9.0
**Working branch:** `launch-hardening` (all work isolated; nothing touches `main` until merge)

---

## 1. Goal

Make Triggarr's public-facing surface — both the code a skeptical engineer reads and the
presentation a visitor sees — hold up to the same scrutiny as its sibling project SeedSyncarr,
so a technical viewer who arrives via cross-reference (same owner, sibling repos) sees one
coherent, serious author across both. Close the launch-visible holes, run a fresh
hostile-reader pass to catch what is not yet on any list, and rebuild the presentation so the
project's genuine quality is evident within 30 seconds and is consistent with the sibling repo.

**Context driving this milestone:** Triggarr is *already* public and launched on Reddit.
SeedSyncarr is undergoing its own launch-hardening pass (`v1.4.0`, spec dated 2026-06-02).
Because both repos show from the same owner, technical viewers will cross-reference between
them. Triggarr is mature — 13 shipped milestones, currently v2.8.1, 965 tests passing, ruff
clean, and v2.8 just completed a security/safety hardening milestone (CSP nonces, session
rotation on password change, `apikey=` query rejection, scheduler resilience, graceful-shutdown
drain). But maturity is not the same as *coherent presentation*, and the "already public with a
long commit history" condition introduces one risk SeedSyncarr does not have at pre-launch: any
secret leaked in an old commit is *already* exposed and findable with `git log -p`. This
milestone therefore (a) runs a deliberate "this is on Reddit" hostile-reader pass over both code
and presentation, (b) fixes the launch-visible holes it finds plus a tightly curated known
subset, and (c) rebuilds presentation so genuine quality is evident fast and is consistent with
SeedSyncarr.

## 2. Decisions Locked During Brainstorming

| # | Decision | Rationale |
|---|----------|-----------|
| D-1 | **Both code-substance and presentation in scope, weighted equally** | A polished README over sloppy code gets torn apart; bulletproof code behind an amateur README never gets clicked. Mirrors SeedSyncarr D-1. |
| D-2 | **Fix the launch-visible holes, don't merely document them** | Strongest "nothing to attack" posture for the already-public repo. |
| D-3 | **Curated known subset + fresh hostile-reader pass** (not known-only, not a full external-tooling gate) | Pre-commit only to launch-*visible* known items; park invisible config-knob UI debt; let a deliberate "going on Reddit" adversarial sweep catch blind spots. Bounded: only genuinely high-visibility findings fold in. |
| D-4 | **Curated known subset = `.gitignore`/repo-hygiene audit + SAFETY-03 failure-counter unification** | A skeptical repo browser scans for sloppy-tooling tells (untracked transients, committed editor cruft); SAFETY-03 is the one known *correctness* asymmetry (not UI-config debt) a careful reader could spot in `scheduler.py`/`routes.py`. NB: as of 2026-06-02, `.DS_Store` and `.playwright-mcp/` are *already* git-ignored and no `.DS_Store` is tracked — the only confirmed gap is `.orchestrator.json` (untracked, not ignored). The phase audits the full picture and closes whatever is actually open rather than assuming a list. |
| D-5 | **Park the config-knob UI debt** (DEBT-07 request timeout, DEBT-08 page-size, DEBT-03 history cap, DEBT-06 shutdown-drain) | Real debt, but invisible to a launch reader — no r/selfhosted commenter sees "timeout isn't tunable in the UI." Explicitly parked with written rationale. |
| D-6 | **Presentation: hostile take first, then rewrite driven by the critique** | A framed cynical-reader teardown AND an explicit codex adversarial pass against the existing README/docs run *before* rewriting. Treat existing presentation as a draft to tear apart, not assumed-good. Mirrors SeedSyncarr D-5. |
| D-7 | **Same-author cross-repo consistency is an explicit presentation target** | The actual driver: viewers hopping between Triggarr and SeedSyncarr should see consistent README structure, security-posture framing, and honest positioning — one coherent serious author. |
| D-8 | **Hostile-reader code pass = `ruff` whole-tree + Shield (Semgrep SAST + gitleaks secrets + dependency audit) + git-*history* secrets scan + skim highest-traffic entry points** | Full SeedSyncarr toolchain, adapted to Triggarr's stack. The git-history scan is the launch-visible-risk addition unique to an already-public repo with 13 milestones of commits. |
| D-9 | **Code track relies on the orchestrator's existing per-phase codex *plan* review** — no extra codex invocation for code | That review already challenges the engineering artifacts; no double-paying. A separate, explicit codex pass targets the drafted *docs* (D-6). |
| D-10 | **Screenshots captured via Playwright during the walkthrough** against the NAS-deployed branch build with real/representative data | Cleaner, consistent framing than manual capture; captures the *real* product, not dev fixtures. Directly closes the stale-screenshot TODO. Mirrors SeedSyncarr D-8. |
| D-11 | **Branch-based workflow**: all phases + NAS walkthrough on `launch-hardening`; merge to `main` and tag only after CI is green and the maintainer confirms | Full isolation; `main` stays releasable throughout. Mirrors SeedSyncarr D-9. |
| D-12 | **Version = v2.9.0 (minor)**, `release_intent=true` | No breaking changes, but a deliberate multi-phase hardening pass is more than a patch; a minor bump honestly says "meaningful polish, safe to upgrade" and keeps release-process parity with the sibling project. |

## 3. Scope

### 3.1 In scope — Code track

**Discovery (gates fix scope, per D-3 / D-8):**

1. **Hostile-reader code pass.** Before fix-scoping is finalized, a focused "what would a
   skeptical engineer on Reddit find" sweep:
   - `ruff check triggarr/ tests/` whole-tree with launch framing.
   - **Shield** (Semgrep SAST + gitleaks secrets scan + dependency audit) against the working tree.
   - **git-*history* secrets scan** — gitleaks over full commit history (not just the working
     tree), since the repo is already public with 13 milestones of commits. A leaked key in an
     old commit is already exposed; a skeptical reader can `git log -p` and grep. `.gitleaksignore`
     is already present, so this is partly wired.
   - Skim the highest-traffic entry-point files: `triggarr/web/routes.py`,
     `triggarr/search/scheduler.py`, `triggarr/config.py`, `triggarr/db.py`, `triggarr/auth.py`,
     `triggarr/startup.py`.
   - Produce a **triaged findings artifact**. **Only genuinely high-visibility findings fold into
     the fix phases** — not every nitpick. Anything not folded in is explicitly parked with rationale.

**Curated known items (fix regardless, per D-4):**

2. **Repo hygiene / `.gitignore` audit.** Audit the repo for sloppy-tooling tells a skeptical
   browser would catch, and close whatever is actually open. **Confirmed state as of 2026-06-02:**
   `.DS_Store`, `triggarr/.DS_Store`, and `.playwright-mcp/` are *already* git-ignored, and no
   `.DS_Store` is tracked in the index — so those need no change. The one confirmed gap is
   `.orchestrator.json` (untracked and *not* ignored → risk of accidental commit). Add it to
   `.gitignore`. While here, re-scan `git status --ignored` and `git ls-files` for any other
   untracked transient or accidentally-tracked editor/tooling artifact and resolve it. This is an
   audit-and-close, not a fixed checklist — do not re-add already-ignored entries.

3. **SAFETY-03 — failure-counter unification.** Manual searches via
   `/search-now/{app}/{instance}` bypass the per-job consecutive-failure counter
   (`app.state.search_failures`): the route calls `cycle_fn(...)` directly instead of routing
   through `make_search_job`, so manual-search failures neither increment nor reset the threshold
   counter. Extract a shared `_run_one_cycle(app, app_name, instance_name)` helper (or route the
   manual-search path through `make_search_job`) so both scheduled cycles and manual searches
   unify failure counting and reset semantics.
   - Files: `triggarr/web/routes.py` (`search_now` handler, ~`:876`),
     `triggarr/search/scheduler.py` (the `# TODO` at ~`:325`).
   - **Bar:** the `# TODO` is resolved and a test covers manual-search failure increment/reset.

**Parked — explicitly out of scope (per D-5):**

- **DEBT-07** — HTTP request timeout (30s) not exposed in settings UI.
- **DEBT-08** — *arr API page size (50) not exposed in settings UI.
- **DEBT-03** — search history cap (1000) not exposed in settings UI.
- **DEBT-06** — graceful-shutdown drain timeout not surfaced in settings UI.

All four are "field exists in the config model, not exposed in the UI" debt — real, but invisible
to a launch reader. Parked with rationale; candidates for a later quality-of-life milestone.

### 3.2 In scope — Presentation track

**Hostile take first (D-6), then rewrite driven by the critique:**

- **Cynical-reader teardown** — a framed "r/selfhosted commenter" critique of Triggarr's
  positioning, credibility, and first impression, captured as a written artifact.
- **Codex adversarial pass** against the existing README + docs — technical-claims accuracy,
  broken or incomplete install/quickstart instructions, unsupported assertions. Codex has
  historically caught real README issues for this maintainer.

**Content surface to harden:**

- **README** (highest stakes): instantly-clear one-line "what this is"; current screenshots above
  the fold; honest feature list; *accurate* install/quickstart verified against current behavior
  (Docker compose, `TRIGGARR_CONFIG_DIR`, first-run setup); security posture stated plainly as a
  selling point.
- **Screenshots** — current, real screenshots of the dashboard, search history, and settings
  views, **captured via Playwright during the walkthrough** (D-10) against the NAS deploy with
  representative end-user data. Must not expose real API keys, hostnames, or credentials. README
  image references and alt text updated to match. Closes the stale-screenshot TODO
  (`docs/screenshots/dashboard.png`, `history.png`, `settings.png`).
- **SECURITY.md** — confirm the vulnerability-reporting policy and a short, honest threat-model
  note read as maturity; reconcile with the v2.8 / v2.8.1 hardening (CSP nonces, session-secret
  rotation on password change, `apikey=` query rejection, Basic-auth control-char validation,
  session-secret startup checks).
- **Community-health files** — `CONTRIBUTING.md`, issue templates, PR template, accurate
  `LICENSE`. Confirm present and accurate (their absence/staleness is a common "not a serious
  project" tell).
- **Repo metadata** — GitHub "About" description, topics/tags, homepage link. **Drafted by Claude
  as copy-paste text; applied manually by the maintainer** (GitHub web-UI settings cannot be
  edited from the session).
- **Release notes** — a clean v2.9.0 release entry so the releases page stays sharp; in-app
  changelog (`triggarr/changelog.py` / changelog source) updated to match.

**Same-author cross-repo consistency (D-7):**

- Audit Triggarr's README structure, security-posture framing, badge style, and "what this is"
  positioning *against SeedSyncarr's* (read its README and `2026-06-02-launch-hardening-design.md`
  for the target framing). Note and reconcile divergences so a viewer hopping between the two
  repos sees one coherent, serious author. This is a reconciliation pass, not a forced
  homogenization — keep each project's accurate identity, align the *quality signals* (section
  ordering, honest security framing, clear one-liner).

### 3.3 Out of scope (parked explicitly to prevent drift)

- No new user-facing features.
- No broad refactoring beyond what a specific finding justifies.
- The config-knob UI debt — DEBT-07 / DEBT-08 / DEBT-03 / DEBT-06 (D-5).
- **UI-01 / UI-02 / UI-03** — pixel-exact auth-page visual verification (v2.6 deferred,
  `human_needed`). Not launch-visible; auth pages are behind first-run setup.
- **`--color-triggarr-primaryDark`** duplicate-token cleanup (cosmetic, invisible to a launch reader).
- Other CONCERNS.md residual tech debt not surfaced as high-visibility by the discovery pass.

## 4. Approach & Structure

**Two largely-disjoint tracks** (Python code vs. Markdown/docs/repo-metadata), each opening with
its own hostile take. The roadmapper (`/gsd:new-milestone`) sets the exact phase count; the
natural decomposition is:

- **Code-track discovery phase** — hostile-reader pass (ruff whole-tree + Shield + git-history
  secrets scan + entry-point skim) → triaged findings artifact that gates fix scope.
- **Code-track hardening phase(s)** — `.gitignore`/repo hygiene + SAFETY-03 failure-counter
  unification + any high-visibility findings folded in from discovery.
- **Presentation discovery phase** — cynical-reader teardown + codex adversarial pass against
  existing README/docs → critique artifact + the cross-repo consistency audit against SeedSyncarr.
- **Presentation rewrite phase(s)** — README / SECURITY.md / community-health files / repo-metadata
  text / release notes + in-app changelog, driven by the critique; Playwright screenshots captured
  at the walkthrough.

The two tracks touch disjoint files (Python source vs. Markdown/docs) and can be sequenced with
minimal coupling. The only cross-cutting thread is the security framing: the v2.8/v2.8.1 hardening
that the code track confirms is intact is the same posture the presentation track states plainly
as a selling point in README/SECURITY.md.

## 5. Verification & Definition of Done

**Per-phase verification** (existing CI gates + orchestrator gates):

- `uv run pytest tests/ -x` green (currently 965 tests); `uv run ruff check triggarr/ tests/` clean.
- Build-verify typecheck gate green per phase (orchestrator Sub-step 4.5).
- Every phase receives the orchestrator's automatic per-phase codex *plan* review (D-9).
- Every phase receives the orchestrator's turingmind deep review; no unfixed critical/warning findings.
- **SAFETY-03 phase bar:** the `# TODO` at `scheduler.py:~325` is resolved; a test covers
  manual-search failure increment/reset; no test deleted or skipped.

**Milestone-end:**

- **Walkthrough** — deploy the `launch-hardening` branch build to NAS; drive the golden paths
  (first-run setup, dashboard, settings save, search history, manual search-now); capture
  Playwright screenshots against the real deploy with representative data; catch any regression
  from the SAFETY-03 refactor live.
- **Codex presentation pass** — explicitly run codex against the drafted README/docs (D-6),
  separate from the per-phase code plan reviews.
- **Branch → merge → tag (D-11, D-12):** only after CI is green and the maintainer confirms, merge
  `launch-hardening` → `main` and cut the **v2.9.0** tag. `release_intent=true` is set, so the
  orchestrator's milestone-end surfaces the tag discussion.

**Definition of done — the milestone succeeds when:**

1. The curated known items are *closed*: repo-hygiene audit done (`.orchestrator.json` ignored, no
   untracked transients or accidentally-tracked editor cruft remain); SAFETY-03 unifies manual +
   scheduled failure counting with test coverage.
2. The hostile-reader code pass ran (ruff whole-tree + Shield + git-history secrets scan +
   entry-point skim); its high-visibility findings are either fixed or explicitly parked with
   rationale; no secret is exposed in working tree *or* commit history.
3. The presentation hostile take ran (cynical-reader teardown + codex pass); README / SECURITY.md /
   community-health files / release notes survived it; screenshots are real, current, and free of
   exposed credentials.
4. The cross-repo consistency audit ran against SeedSyncarr; Triggarr's quality signals (one-liner,
   section ordering, security framing) are reconciled so the two repos read as one coherent author.
5. Repo-metadata text is drafted for the maintainer to apply; CI green throughout; a clean v2.9.0
   release is ready to tag after merge to `main`.

## 6. Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| SAFETY-03 refactor regresses scheduled-search failure counting | Extract a shared helper used by both paths; existing scheduler failure-counter tests stay green (no deletion/skip); walkthrough exercises both manual and scheduled search live on the branch build before merge. |
| Hostile-reader pass balloons scope | D-3 bound: only *genuinely high-visibility* findings fold in; everything else parked with written rationale. |
| git-history secrets scan surfaces a real leaked key in old commits | If found, this is the highest-priority finding: rotate the exposed credential, add to `.gitleaksignore` only after rotation, and decide on history rewrite vs. accept-and-rotate based on severity. (Public repo — assume already exposed.) |
| Screenshots misrepresent real behavior or leak credentials | D-10: capture against the real NAS deploy with representative data; scrub/verify no API keys, hostnames, or credentials are visible; flag any staged state explicitly. |
| Cross-repo consistency forces inappropriate homogenization | D-7 is a reconciliation of *quality signals*, not identity; each project keeps its accurate "what this is" — only the signals of seriousness align. |
| Repo-metadata changes can't be applied from the session | Drafted as copy-paste text + handoff note; maintainer applies in the GitHub web UI. |
