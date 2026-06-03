# Phase 70: Presentation Discovery - Research

**Researched:** 2026-06-02
**Domain:** Documentation critique / adversarial review / cross-repo consistency audit
**Confidence:** HIGH — all findings are from direct file inspection; codex CLI flags verified live

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Three focused critique artifacts, one per PDISC requirement, all in `.planning/phases/70-presentation-discovery/`:
  - `70-CRITIQUE.md` — cynical-reader teardown (PDISC-01)
  - `70-CODEX-REVIEW.md` — codex adversarial-pass findings against docs (PDISC-02)
  - `70-CONSISTENCY-AUDIT.md` — SeedSyncarr cross-repo divergence list (PDISC-03)
- **D-02:** Three separate files (not one combined artifact) because each has a different natural shape — persona prose, a findings table, a divergence-reconciliation list — with 1:1 requirement traceability.
- **D-03:** Every actionable item must be specific enough for Phase 71 to rewrite against without re-investigation — each gripe and each divergence cites the specific README/doc section (or `file:line`) and states the recommended direction of the fix.
- **D-04:** PDISC-02 is run via the direct `codex` CLI (confirmed installed: `/opt/homebrew/bin/codex`, codex-cli 0.133.0), pointed at the drafted docs, framed for technical-claims accuracy, broken/incomplete install/quickstart, and unsupported assertions. This is the SEPARATE codex pass against docs (not the orchestrator's per-phase codex plan review — those are two distinct invocations; one does NOT substitute for the other).
- **D-05:** In-scope docs for the codex pass: `README.md`, `SECURITY.md`, `CONTRIBUTING.md`, plus the install/quickstart path they describe. Findings captured in `70-CODEX-REVIEW.md` as a table: severity, doc/`file:line`, the claim or instruction at issue, and a recommended correction.
- **D-06:** PDISC-03 reads SeedSyncarr's `README.md`, `SECURITY.md`, `CONTRIBUTING.md`, and its launch-hardening design spec (`~/seedsyncarr/docs/superpowers/specs/2026-06-02-launch-hardening-design.md`) for the target framing. Records divergences in `70-CONSISTENCY-AUDIT.md` as a table: signal · Triggarr's current state · SeedSyncarr's state · recommended reconciliation.
- **D-07:** Reconciliation of quality signals, NOT forced homogenization. Each project keeps its accurate identity; only the signals of seriousness align.
- **D-08:** PDISC-01 is written as a single cynical "r/selfhosted commenter" persona, structured across three first-impression questions: (a) is this trustworthy/a serious project?, (b) can I get it running in ~5 minutes?, (c) why this over native *arr search or a cron + curl?

### Claude's Discretion

- Exact table column layout within each artifact (as long as D-03's "specific + cited" bar is met).
- Order in which the three activities run (independent; no blocking dependencies between them).
- Exact codex CLI flags/prompt wording for PDISC-02 (as long as scope = D-05 docs, framing = technical-claims/broken-instructions/unsupported-assertions).
- Whether to capture a short provenance header (codex version, date, commit) per artifact — encouraged for reproducibility, not mandated.
- Whether `~/seedsync` (the separate smaller repo, github.com/thejuran/seedsync) is worth a one-line cross-link note; the canonical sibling for PDISC-03 is `~/seedsyncarr`.

### Deferred Ideas (OUT OF SCOPE)

- All actual rewriting — README rewrite (PREW-01), SECURITY.md reconciliation (PREW-03), community-health fixes (PREW-04), repo-metadata copy (PREW-05), release notes + in-app changelog (PREW-06), cross-repo signal reconciliation edits (PREW-07) — is Phase 71.
- Fresh screenshots (PREW-02) — captured via Playwright at the milestone-end NAS walkthrough.
- GitHub repo-metadata application — Phase 71 drafts copy-paste text; maintainer applies it in the GitHub web UI.
- Config-knob UI debt (DEBT-03/06/07/08), UI-01/02/03 pixel verification — parked to v2.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| PDISC-01 | A framed cynical-reader ("r/selfhosted commenter") teardown of Triggarr's positioning, credibility, and first impression, captured as written artifact `70-CRITIQUE.md`. | Pre-seeded with concrete gripes: stale version in pip install line, missing release badge, no wordmark/screenshot above the fold, bug template missing Lidarr, screenshot staleness. Three question structure locked via D-08. |
| PDISC-02 | A codex adversarial pass against the existing README + docs (technical-claims accuracy, broken/incomplete install/quickstart, unsupported assertions), findings in `70-CODEX-REVIEW.md`. | Concrete invocation established: `codex exec --sandbox read-only -o <output-file> "<framing-prompt>"` from the repo root. One pre-confirmed claim issue: standalone pip install line cites `triggarr-2.7.2-py3-none-any.whl` while `__version__ = "2.8.1"`. |
| PDISC-03 | A same-author cross-repo consistency audit comparing Triggarr vs SeedSyncarr (README structure, security-posture framing, badge style, "what this is" one-liner), recording divergences to reconcile in `70-CONSISTENCY-AUDIT.md`. | 8 concrete divergences pre-enumerated and ready to seed the audit table. |
</phase_requirements>

---

## Summary

Phase 70 is a pure discovery/critique phase that writes exactly three Markdown artifacts — `70-CRITIQUE.md`, `70-CODEX-REVIEW.md`, `70-CONSISTENCY-AUDIT.md` — and nothing else. All file editing is deferred to Phase 71. The phase mirrors the Phase 68 discover-don't-fix contract on the presentation track.

Research confirms all three inputs are directly readable with no tool gaps. The codex CLI (`/opt/homebrew/bin/codex`, codex-cli 0.133.0) supports a fully non-interactive mode via `codex exec` with `--sandbox read-only` and `-o <file>` flags, making the PDISC-02 pass reproducible without a TUI session. The SeedSyncarr checkout at `/Users/julianamacbook/seedsyncarr` is current and complete. The Triggarr presentation surface has been read in full and eight concrete divergences and pre-confirmed issues have been enumerated below.

**Primary recommendation:** Write tasks that (1) produce persona prose for PDISC-01 by reading the live README and SECURITY.md, (2) invoke `codex exec` non-interactively for PDISC-02 and post-process its output into a findings table, and (3) do a structured diff of paired sections between the two repos for PDISC-03. Every task output is a Markdown file in the phase directory — no source files are touched.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Cynical-reader teardown (PDISC-01) | Claude agent (text generation) | — | Pure prose critique of existing Markdown files; no external service needed |
| Codex adversarial docs pass (PDISC-02) | codex CLI (`/opt/homebrew/bin/codex exec`) | Claude agent (post-process into table) | codex performs the adversarial read; executor formats findings into the required table |
| Cross-repo consistency audit (PDISC-03) | Claude agent (file diffing) | — | Direct read of two local checkouts; no service dependency |
| Artifact storage | Phase directory (`.planning/phases/70-presentation-discovery/`) | git (commit_docs=true) | All three artifacts live here; committed with the phase per D-01 |

---

## Standard Stack

This phase installs no packages. The only external tool is the codex CLI, already present.

### Core

| Tool | Version | Purpose | Status |
|------|---------|---------|--------|
| codex CLI | 0.133.0 | PDISC-02 adversarial docs pass | Confirmed installed at `/opt/homebrew/bin/codex` [VERIFIED: live invocation] |
| bash / file reads | — | PDISC-01 and PDISC-03 (direct Markdown reads) | Native; no install [VERIFIED: live invocation] |

### No packages to install

This phase produces Markdown critique artifacts only. No `pip install`, `npm install`, or any other package manager invocation is needed.

---

## Package Legitimacy Audit

**Not applicable.** This phase installs no external packages.

---

## Architecture Patterns

### System Architecture Diagram

```
Triggarr repo (README.md, SECURITY.md, CONTRIBUTING.md, docs/screenshots/, .github/)
        |
        +---> [PDISC-01: persona read] -----> 70-CRITIQUE.md
        |
        +---> [PDISC-02: codex exec]   -----> raw codex output
        |         |                           |
        |      (codex CLI)          [executor formats into table]
        |                                     |
        |                          70-CODEX-REVIEW.md
        |
SeedSyncarr repo (README.md, SECURITY.md, CONTRIBUTING.md, launch-hardening spec)
        |
        +---> [PDISC-03: paired diff] -----> 70-CONSISTENCY-AUDIT.md
```

Data flow: all three paths are READ-ONLY against existing files. The only writes are the three output `.md` files in the phase directory.

### Recommended Phase Directory Contents After Execution

```
.planning/phases/70-presentation-discovery/
├── 70-CONTEXT.md         (already exists — input)
├── 70-DISCUSSION-LOG.md  (already exists — input)
├── 70-RESEARCH.md        (this file)
├── 70-CRITIQUE.md        (PDISC-01 output)
├── 70-CODEX-REVIEW.md    (PDISC-02 output)
└── 70-CONSISTENCY-AUDIT.md (PDISC-03 output)
```

---

## PDISC-02: Codex CLI Invocation (Concrete and Reproducible)

### Confirmed flags

From `codex exec --help` verified live:

- `codex exec` — non-interactive agent execution (alias: `codex e`)
- `--sandbox read-only` — sandboxes the agent to read-only filesystem access; appropriate for a docs review that must not modify files
- `-o <FILE>` / `--output-last-message <FILE>` — writes the agent's last message to a file; use to capture findings without piping TUI output
- `--ephemeral` — runs without persisting session files; clean for scripted use
- The prompt may be passed as a positional argument or via stdin (piped with `-`)

### Recommended invocation

```bash
cd /Users/julianamacbook/triggarr

/opt/homebrew/bin/codex exec \
  --sandbox read-only \
  --ephemeral \
  -o .planning/phases/70-presentation-discovery/70-CODEX-REVIEW-raw.md \
  "You are performing an adversarial review of this project's documentation for launch readiness. \
Read README.md, SECURITY.md, and CONTRIBUTING.md. Your job is to find: \
(1) technical claims that are inaccurate or not supported by the code, \
(2) install or quickstart instructions that are broken, incomplete, or would mislead a first-time user, \
(3) assertions about security behavior that are absent, outdated, or misleading. \
For each finding, state: the file and approximate line, the exact claim or instruction at issue, \
whether it is factually wrong / incomplete / misleading, and a recommended correction. \
Format your findings as a Markdown table with columns: Severity | File:Line | Claim/Instruction | Issue Type | Recommended Correction. \
Severity: HIGH (factually wrong or would cause setup failure), MEDIUM (misleading or outdated), LOW (minor gap). \
Do not report style issues. Only report substantive claims and instructions."
```

After the raw output lands in `70-CODEX-REVIEW-raw.md`, the executor adds a provenance header (codex version, date, branch, commit) and any additional context, then renames/finalizes as `70-CODEX-REVIEW.md`.

### Important distinction (spec D-9 / CONTEXT.md D-04)

The orchestrator's automatic per-phase codex PLAN review checks the engineering plan artifacts. This PDISC-02 invocation checks the DOCS content. They are different commands, different targets, different framing. One does not substitute for the other. The plan task must explicitly invoke the above command — it is not covered by the orchestrator's automatic review.

### Credential-scrubbing reminder

If the codex output quotes README snippets containing placeholder API key patterns (e.g., `<radarr-api-key>` from the TOML example), these are safe — they are already placeholder strings. Do NOT include any real key values in the artifact. The executor should verify the raw output before finalizing.

---

## PDISC-01: Cynical-Reader Teardown — Pre-Seeded Inputs

The executor writes a persona-voice critique structured around D-08's three questions. Research has pre-confirmed the following concrete gripes that the artifact MUST address (executor may add others found during the read):

### Pre-confirmed issues for the teardown

**Question (a) — Is this trustworthy / a serious project?**

1. **Missing release/version badge.** Triggarr has two badges: CI and Docker. SeedSyncarr has four: CI, Release (live version from GitHub), Docker, License. Triggarr has no release badge showing the current version number. A first visitor has no quick signal of how mature or current the project is. [VERIFIED: direct read of both READMEs]

2. **No wordmark or screenshot above the fold.** Triggarr opens with `# Triggarr` (plain H1) + two badges + a one-liner. SeedSyncarr opens with a centered `<picture>` wordmark block + a centered screenshot before any text. Triggarr's screenshots are below a Table of Contents, below a Features list — a viewer who doesn't scroll far never sees the UI. [VERIFIED: direct read]

3. **Screenshot staleness.** All three screenshots (`docs/screenshots/dashboard.png`, `history.png`, `settings.png`) have modification date 2026-04-14. Current version is v2.8.1 (2026-06-01). Screenshots predate the v2.6 auth UI, v2.7 dashboard redesign completion, and v2.8.1 security hardening. A skeptical reviewer notices `?v=2` cache-busting in the image URLs — which paradoxically draws attention to the fact that these are versioned, raising the question of when they were last updated. [VERIFIED: `stat` on files]

4. **Bug report template version dropdown tops out at v2.3.** Current version is v2.8.1. The version dropdown in `bug-report.yml` lists: `v2.3`, `v2.2`, `v2.1`, `Older`. A user on v2.8.1 who files a bug has to select "Older" — signals the project hasn't kept up with its own templates. [VERIFIED: direct read of `bug-report.yml`]

5. **Bug report template "App Type" missing Lidarr.** Options are `Radarr`, `Sonarr`, `Both`. Lidarr is a documented first-class supported app (Feature list line 22, README TOML example). A Lidarr user filing a bug hits a gap. [VERIFIED: direct read of bug-report.yml vs README feature list]

**Question (b) — Can I get it running in ~5 minutes?**

6. **Standalone pip install line cites v2.7.2, not current version.** README line 85 hardcodes `triggarr-2.7.2-py3-none-any.whl`. Actual `__version__` = `2.8.1`. A user copy-pasting this installs a version that is two minor releases behind without knowing it. This is a factual accuracy failure, not just staleness. [VERIFIED: README read + `grep __version__ triggarr/__init__.py`]

7. **Docker first-run behavior unexplained for newcomers.** README line 78 says "On an empty volume, Triggarr writes `/config/triggarr.toml` first; with the `restart: unless-stopped` example above, the container then starts normally on the next restart." What actually happens: `sys.exit(1)` fires, Docker restarts the container, it finds the config and runs. A first-time user who watches `docker compose logs -f` may see the exit and think something is broken. The behavior is accurate but the explanation relies on the reader inferring the restart mechanism — this is a UX friction point. [VERIFIED: `config.py:353-359` reads `sys.exit(1)` after writing default]

**Question (c) — Why this over native *arr search or cron + curl?**

8. **No "Related Projects" cross-link to SeedSyncarr.** SeedSyncarr's README has a "Related Projects" section linking to Triggarr with a one-line description of how they complement each other. Triggarr has no such section. A viewer who arrives at Triggarr from SeedSyncarr is told "you're in the right place"; a viewer who arrives at Triggarr cold has no pointer to the sibling tool they might also want. [VERIFIED: direct read of both READMEs]

---

## PDISC-03: SeedSyncarr Consistency Audit — Pre-Enumerated Divergences

The executor reads both repos and fills the `70-CONSISTENCY-AUDIT.md` divergence table. Research has pre-enumerated the following concrete divergences: [VERIFIED: direct read of both repos]

| # | Signal | Triggarr current | SeedSyncarr current | Reconciliation direction |
|---|--------|-----------------|---------------------|--------------------------|
| 1 | **Header / wordmark** | Plain `# Triggarr` H1 | Centered `<picture>` wordmark block (dark/light variants) | Phase 71 to decide: add a wordmark (PREW-01); for now, note the gap |
| 2 | **Screenshot position** | Below Table of Contents + Features list | Above the fold, immediately after wordmark | Phase 71 PREW-01: move screenshots above the fold |
| 3 | **Badge set** | 2 badges: CI + Docker | 4 badges: CI + Release (live version) + Docker + License | Phase 71: add Release badge + License badge |
| 4 | **Badge style — Docker** | `img.shields.io/badge/ghcr.io-thejuran%2Ftriggarr-blue?logo=docker` (custom static) | `img.shields.io/badge/docker-ghcr.io-blue` (simpler, no encoded slashes or logo param) | Minor; align style in PREW-01 |
| 5 | **Section ordering** | ToC → Features → Screenshots → Install → Config Ref → Security Model → Development | Quick Start → Features → How It Works → Installation → Config → Screenshots → Related Projects → Contributing → Security → License → Usage Examples | Phase 71 PREW-01: restructure; at minimum move Screenshots up and add Related Projects |
| 6 | **Quick Start / one-step compose** | No dedicated "Quick Start" section; install section is the first actionable content | Dedicated `## Quick Start` with a minimal compose block at top of README | Phase 71 PREW-01: add a Quick Start section |
| 7 | **"Related Projects" section** | ABSENT — no cross-link to SeedSyncarr | Present: links Triggarr with a one-line complement description | Phase 71 PREW-07: add Related Projects section linking SeedSyncarr |
| 8 | **Security reporting path** | GitHub private vulnerability reporting URL (the standard GitHub GSVR flow) | Email to maintainer (`thejuran@users.noreply.github.com`) + detailed steps | Triggarr's approach (GSVR) is more mature; this is a case where SeedSyncarr should align TO Triggarr, not vice versa — note in audit |
| 9 | **Security section depth** | `SECURITY.md`: detailed threat model (5+ subsections), `## Deployment Recommendations`; links back to vulnerability reporting | `SECURITY.md`: reporting policy + "Security Best Practices for Users" (5 bullet points); NO threat model | Triggarr's SECURITY.md is materially stronger; reconcile by updating SeedSyncarr's in its own milestone (out of scope here) and in the audit note |
| 10 | **CONTRIBUTING.md structure** | Prerequisites + Getting Started + Dev Commands + Before Opening a PR + Commit Conventions + Pull Requests + Reporting Issues | Reporting Bugs + Requesting Features + Development Setup + Code Style + Pull Requests + Security | Triggarr has explicit Commit Conventions (conventional commits); SeedSyncarr does not. Both functional; note the gap. |
| 11 | **"What this is" one-liner** | `Python automation daemon that triggers searches in Radarr, Sonarr, and Lidarr on a schedule.` (README line 6) | `Sync files from your seedbox to your local media server — fast, automated, and integrated with Sonarr and Radarr.` (blockquote after wordmark) | Triggarr's one-liner is accurate but dry; SeedSyncarr's leads with the user benefit. Phase 71 PREW-01 to sharpen Triggarr's. |

**Notes on items 8-9:** These show Triggarr is actually AHEAD of SeedSyncarr in security presentation maturity. The audit must note this directionally — the reconciliation goal is raising both, and for these signals SeedSyncarr is the project that has a gap.

---

## SECURITY.md Divergence from v2.8/v2.8.1 Hardening (PDISC-02 Input)

The current `SECURITY.md` (5.4 KB) does NOT mention the following v2.8/v2.8.1 hardening measures that the code track confirmed are implemented:

| v2.8/v2.8.1 Feature | Code-track status | SECURITY.md current state |
|--------------------|-------------------|---------------------------|
| CSP nonces on inline `<script>` elements | Confirmed implemented (68-FINDINGS.md public-surface inventory) | Not mentioned by name; "restrictive Content Security Policy" is the only reference (line 38) |
| Session-secret rotation on password change (CWE-613 mitigation, v2.8.1) | Confirmed implemented; v2.8.1 patch notes | Mentioned in README Security Model (line 197) but NOT in SECURITY.md |
| `apikey=` query-parameter rejection | Confirmed implemented (auth middleware) | Not mentioned anywhere in SECURITY.md |
| Basic-auth control-character validation | Confirmed implemented (middleware) | Not mentioned anywhere in SECURITY.md |
| Session-secret startup length check (SEC-04) | Confirmed implemented (`startup.py:204`) | Not mentioned anywhere in SECURITY.md |

These are Phase 71 PREW-03 reconciliation targets. Phase 70's job is to NOTE the divergences; the codex pass (PDISC-02) will likely flag them independently.

---

## Common Pitfalls

### Pitfall 1: Writing fixes instead of critique

**What goes wrong:** The executor instinctively rewrites the README sentence it's critiquing instead of noting the issue and its fix direction.
**Why it happens:** The natural assistant reflex is to correct rather than document.
**How to avoid:** Every output file is a CRITIQUE artifact. No `README.md`, `SECURITY.md`, `CONTRIBUTING.md`, or any file outside `.planning/phases/70-presentation-discovery/` is written in this phase. If a task description says "update README", it is out of scope.
**Warning signs:** Any tool call to `Write` or `Edit` targeting a file outside the phase directory.

### Pitfall 2: Assuming codex exec terminates quickly

**What goes wrong:** The `codex exec` invocation for PDISC-02 can take several minutes to complete depending on model latency.
**Why it happens:** The agent reads and processes three files, runs reasoning, generates a structured table.
**How to avoid:** The planner should set a generous timeout on the codex task (e.g., 10 minutes). Do NOT retry if the terminal shows no output for 60 seconds — codex may be processing.
**Warning signs:** Killing and re-running codex exec before it completes.

### Pitfall 3: Confusing the two codex invocations

**What goes wrong:** The executor runs `codex exec review` (the code-review subcommand) thinking that is the PDISC-02 docs pass.
**Why it happens:** `codex exec review` is for reviewing code diffs against a branch. The docs pass is `codex exec "<prompt>"` (the general-purpose exec with a docs-framing prompt).
**How to avoid:** The planner must specify the exact command form from the PDISC-02 section above. `codex exec review` is NOT the right subcommand for this use case.

### Pitfall 4: Embedding real credentials in the codex output artifact

**What goes wrong:** Codex quotes a TOML configuration block that includes placeholder `<api-key>` strings; the executor is confused about whether these are real.
**Why it happens:** The README TOML example has `api_key = "<radarr-api-key>"` — these ARE placeholder strings, not real values.
**How to avoid:** Verify before finalizing `70-CODEX-REVIEW.md` that no real API key, hostname, or credential appears in the artifact. Placeholders (`<radarr-api-key>` etc.) are safe to include.

### Pitfall 5: Treating Phase 70 as having testable outputs

**What goes wrong:** The planner applies `type: tdd` to tasks, requiring test coverage for the critique artifacts.
**Why it happens:** The global `tdd_mode: true` config is on.
**How to avoid:** All three tasks in this phase produce Markdown critique artifacts, not executable code or I/O contracts. There is nothing to test. No `type: tdd` applies. Acceptance criteria for each task are instead: "artifact exists, is non-empty, contains a table/section per D-03's cited-and-specific bar, and no source files outside the phase directory were modified."

### Pitfall 6: Treating "UI hint: yes" in the ROADMAP as requiring UI design work

**What goes wrong:** The planner looks for a UI design contract or AIDesigner artifact.
**Why it happens:** The ROADMAP's literal "UI hint: yes" line triggered the keyword gate.
**How to avoid:** There is NO frontend work in Phase 70. The output is three `.md` files. No UI design contract is needed. The "UI hint" in the ROADMAP is a carry-forward keyword and does not apply to this phase.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Non-interactive codex invocation | A shell script that sends keystrokes to the TUI | `codex exec --sandbox read-only -o <file> "<prompt>"` | codex already has a proper non-interactive `exec` subcommand with output capture |
| Cross-repo diff | A custom git diff or script | Direct file reads of both local checkouts | Both repos are on-disk; direct read is simpler and produces a better structured comparison |

---

## Validation Architecture

> `nyquist_validation` key is absent from `.planning/config.json` → treated as enabled.

However, this phase produces Markdown critique artifacts with no testable I/O contracts. There are no unit tests, no integration tests, no automated commands. Acceptance gates are structural, not executable:

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| PDISC-01 | `70-CRITIQUE.md` exists, non-empty, references specific README sections/lines, covers all three D-08 questions | manual inspection | `test -s .planning/phases/70-presentation-discovery/70-CRITIQUE.md` | ❌ Wave 0 (created by executor) |
| PDISC-02 | `70-CODEX-REVIEW.md` exists, non-empty, contains a severity/file:line/claim/issue/correction table | manual inspection | `test -s .planning/phases/70-presentation-discovery/70-CODEX-REVIEW.md` | ❌ Wave 0 (created by executor) |
| PDISC-03 | `70-CONSISTENCY-AUDIT.md` exists, non-empty, contains a signal/Triggarr/SeedSyncarr/reconciliation table | manual inspection | `test -s .planning/phases/70-presentation-discovery/70-CONSISTENCY-AUDIT.md` | ❌ Wave 0 (created by executor) |

### Sampling Rate

- **Per task:** `test -s <artifact-path>` (artifact is non-empty)
- **Phase gate:** All three artifacts exist and are non-empty; no source file outside the phase directory was modified; `uv run ruff check triggarr/ tests/` still clean (sanity check — this phase touches no Python); `uv run pytest tests/ -x -q` still green (sanity check).

### Wave 0 Gaps

None — no test infrastructure is needed. The three artifact files are created by task execution itself.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| codex CLI | PDISC-02 adversarial docs pass | ✓ | codex-cli 0.133.0 at `/opt/homebrew/bin/codex` | — (no fallback needed; confirmed present) |
| SeedSyncarr checkout | PDISC-03 consistency audit | ✓ | Present at `/Users/julianamacbook/seedsyncarr` (git remote: github.com/thejuran/seedsyncarr) | — (no fallback needed; confirmed present) |
| Triggarr README, SECURITY.md, CONTRIBUTING.md | All three activities | ✓ | In repo root, fully readable | — |
| `.github/` issue templates | PDISC-01/02 community health signals | ✓ | `bug-report.yml`, `feature-request.yml`, `config.yml`, `pull_request_template.md` all present | — |

**Missing dependencies with no fallback:** None.
**Missing dependencies with fallback:** None.

---

## Security Domain

This phase does not modify any code, write any configuration, or introduce any executable logic. The only security-relevant concern is:

- **Credential-scrubbing in codex output:** The codex pass reads files containing placeholder API keys (`<radarr-api-key>`, `<sonarr-api-key>`, etc.). These are placeholder strings (not real credentials) and are safe to include in the critique artifact. The executor must verify no real key appears in `70-CODEX-REVIEW.md` before commit.

No ASVS categories apply to Markdown critique artifact production.

---

## Open Questions (RESOLVED)

1. **Codex model selection for PDISC-02**
   - What we know: `codex exec` defaults to the model configured in `~/.codex/config.toml`; can be overridden with `-m <model>`.
   - What's unclear: Whether a specific model override is warranted for a docs review task.
   - Recommendation: Use the default configured model (no `-m` override); if the output is thin, retry with `-m o3` as the follow-up.
   - RESOLVED: Plan 70-01 Task 2 adopts the default-model-then-retry-with-`-m o3` recommendation verbatim.

2. **Whether to run PDISC-01, PDISC-02, PDISC-03 as three separate tasks or combine some**
   - What we know: The three artifacts are independent; the only ordering constraint is that codex exec (PDISC-02) should complete before the planner merges its findings — but it doesn't block PDISC-01 or PDISC-03.
   - Recommendation: Three separate tasks, each producing one artifact. Parallelization is possible (all three activities are read-only and independent) but the planner may sequence them for simplicity.
   - RESOLVED: Plan 70-01 implements three separate tasks (70-01-01/02/03), one per artifact, in a single autonomous Wave 1.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `codex exec --sandbox read-only -o <file> "<prompt>"` will run to completion without requiring a TTY or interactive approval in `yolo` mode | PDISC-02 invocation | Task hangs; executor would need to add `--dangerously-bypass-approvals-and-sandbox` flag or check codex config for auto-approval setting |
| A2 | The `codex exec` `-o` flag captures the agent's final message in a machine-readable way without requiring further parsing | PDISC-02 invocation | Output may require stripping ANSI codes; executor should verify the raw file before committing |

---

## Sources

### Primary (HIGH confidence — direct file inspection)

- `README.md` (277 lines) — Triggarr; read in full; version, badge, section structure, pip install line, first-run claim, screenshot refs all verified directly
- `SECURITY.md` — Triggarr; read in full; hardening gaps enumerated against 68-FINDINGS public-surface inventory
- `CONTRIBUTING.md` — Triggarr; read in full
- `.github/ISSUE_TEMPLATE/bug-report.yml` — version dropdown gap and Lidarr omission confirmed
- `.github/ISSUE_TEMPLATE/feature-request.yml` — read
- `.github/pull_request_template.md` — read
- `docs/screenshots/` — `stat` timestamps confirmed 2026-04-14 for all three images
- `triggarr/__init__.py` — `__version__ = "2.8.1"` confirmed
- `pyproject.toml` — `version = "2.8.1"` confirmed
- `triggarr/config.py:353-359` — `sys.exit(1)` after writing default config confirmed
- `seedsyncarr/README.md` — read in full; section structure, wordmark block, badge set, Related Projects all confirmed
- `seedsyncarr/SECURITY.md` — read; reporting-via-email vs Triggarr's GSVR gap confirmed
- `seedsyncarr/CONTRIBUTING.md` — read; structure differences noted
- `seedsyncarr/docs/superpowers/specs/2026-06-02-launch-hardening-design.md` — read; confirmed SeedSyncarr's presentation track scope and hostile-take framing is the target state both repos are converging toward
- `docs/superpowers/specs/2026-06-02-launch-hardening-design.md` — Triggarr's design spec; §3.2, D-6, D-7, D-9 verified
- `.planning/phases/68-code-track-hostile-reader-discovery/68-FINDINGS.md` — precedent artifact read; confirms public-surface inventory (clean), hardening measures intact
- `.planning/phases/68-code-track-hostile-reader-discovery/68-CONTEXT.md` — D-02 schema and D-03 actionability bar are the precedent for artifact structure
- `.planning/config.json` — `nyquist_validation` absent (treated as enabled); `commit_docs: true`; `tdd_mode: true`
- `/opt/homebrew/bin/codex --help` and `codex exec --help` — flags verified live; `--sandbox read-only`, `-o <file>`, `--ephemeral` confirmed available

### Secondary (MEDIUM confidence)

None needed — all findings are from direct file reads.

---

## Metadata

**Confidence breakdown:**
- Triggarr presentation surface: HIGH — read in full, specific claims verified
- Codex CLI invocation: HIGH — flags verified by running `--help` live against installed binary
- SeedSyncarr divergences: HIGH — both repos read in full, divergences enumerated from direct comparison
- Pre-confirmed PDISC-01 gripes: HIGH — each gripe cites a specific file:line verified during research

**Research date:** 2026-06-02
**Valid until:** Until any of the following change: README.md, SECURITY.md, codex-cli version, or SeedSyncarr README — all stable for the duration of the v2.9 milestone.
