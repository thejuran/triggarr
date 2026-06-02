# 70-CONSISTENCY-AUDIT.md — SeedSyncarr Cross-Repo Consistency Audit (PDISC-03)

**Provenance:** 2026-06-02 · branch: launch-hardening · commit: 131f73a
**Triggarr source:** `/Users/julianamacbook/triggarr` (README.md, SECURITY.md, CONTRIBUTING.md)
**SeedSyncarr source:** `/Users/julianamacbook/seedsyncarr` (README.md, SECURITY.md, CONTRIBUTING.md, docs/superpowers/specs/2026-06-02-launch-hardening-design.md)
**Approach:** D-07 — reconciliation of quality signals, NOT forced homogenization. Each project keeps its accurate identity. Security-posture signals where Triggarr leads are noted directionally (SeedSyncarr has the gap, not Triggarr).
**Status:** Both repos read-only; neither working tree modified.

---

## Divergence Table

| # | Signal | Triggarr current state | SeedSyncarr current state | Recommended reconciliation direction | Phase 71 item |
|---|--------|------------------------|---------------------------|--------------------------------------|---------------|
| 1 | **Header / wordmark** | Plain `# Triggarr` H1 (README.md:1) | Centered `<picture>` block with dark/light wordmark variants (README.md:1-7) | Phase 71 to decide: add a visual wordmark above the fold OR at minimum elevate the header with a stronger visual treatment. Exact implementation is Phase 71 PREW-01 scope — note gap here. | PREW-01 |
| 2 | **Screenshot position** | Screenshots section is the third ToC entry, below "Features" (README.md:14 ToC, README.md:35-40 Screenshots). Visitor must scroll past ToC + Features to see the UI. | Screenshot displayed immediately after wordmark, above the fold, before any text (README.md:9-11) | Move screenshots above the fold — at minimum, place one representative screenshot before the ToC/Features sections. Phase 71 PREW-01. | PREW-01 |
| 3 | **Badge set** | 2 badges: CI + Docker (README.md:3-4) | 4 badges: CI + Release (live version from GitHub) + Docker + License (README.md:15-18) | Add Release badge (`img.shields.io/github/v/release/thejuran/triggarr`) and License badge (`img.shields.io/github/license/thejuran/triggarr`). Release badge is the highest-value addition: gives a first visitor an immediate version signal. Phase 71 PREW-01. | PREW-01 |
| 4 | **Docker badge style** | Custom static badge with encoded slashes: `img.shields.io/badge/ghcr.io-thejuran%2Ftriggarr-blue?logo=docker` (README.md:4) | Simpler style, no encoded path: `img.shields.io/badge/docker-ghcr.io-blue` (README.md:17) | Minor inconsistency; align badge style in Phase 71 PREW-01 for visual consistency between sibling repos. | PREW-01 |
| 5 | **Section ordering** | ToC → Features → Screenshots → Install → Configuration Reference → Security Model → Development (README.md:10-19) | Quick Start → Features → How It Works → Installation → Configuration → Screenshots → Related Projects → Contributing → Security → License → Usage Examples (README.md:20+) | Restructure in Phase 71 PREW-01: at minimum (a) add a Quick Start section near the top, (b) move Screenshots above the fold, (c) add Related Projects before Contributing. Full section reorder is Phase 71 scope. | PREW-01 |
| 6 | **Quick Start section** | ABSENT — no dedicated Quick Start section; the `## Install` section contains the first compose block (README.md:43-78), reached after ToC, Features, Screenshots | `## Quick Start` is the first section after badges/blockquote/screenshot (README.md:20-33); contains a minimal compose YAML block — five lines, immediately actionable | Add a `## Quick Start` section at or near the top with the minimal compose block and "visit `http://localhost:8484`" next step. The current detailed Install section stays as the full reference. Phase 71 PREW-01. | PREW-01 |
| 7 | **"Related Projects" section** | ABSENT — no cross-link to SeedSyncarr or any sibling project (README.md, all sections) | Present: `## Related Projects` section links Triggarr with a one-line complement description: "SeedSyncarr handles the download-to-sync side; Triggarr handles the search-to-trigger side." (README.md:104-106) | Add `## Related Projects` section in Triggarr README linking to SeedSyncarr. This is the highest-signal trivially-fixable gap: a viewer arriving cold at Triggarr never gets a pointer to the complementary sibling tool. Phase 71 PREW-07. | PREW-07 |
| 8 | **Security reporting path** | GitHub private vulnerability reporting (GitHub Security Advisories / GSVR): `github.com/thejuran/triggarr/security/advisories/new` with 7-day response SLA. Structured and integrated with GitHub's CVE publication pipeline. (SECURITY.md:12-14) | Email to maintainer: `thejuran@users.noreply.github.com` with acknowledgment in 48h, resolution in 2-4 weeks. Manual process. (SECURITY.md:14-32) | **Triggarr is AHEAD.** GitHub GSVR is more mature, structured, and verifiable than an email address. SeedSyncarr should align TO Triggarr on this signal in its own milestone — that is out of scope for Phase 71 here. No action needed on Triggarr's SECURITY.md for this signal. | (SeedSyncarr's gap — out of scope) |
| 9 | **SECURITY.md depth** | Detailed threat model with 4 main subsections (Authentication & Access Control, Credential Protection, Web Security, Data Integrity & Runtime Paths, Container Hardening), plus `## Deployment Recommendations`. Links back from SECURITY.md to vulnerability reporting. (SECURITY.md, all sections) | Reporting policy + 5-bullet "Security Best Practices for Users" section. No threat model, no deployment hardening section. (SECURITY.md, all sections) | **Triggarr is AHEAD.** Triggarr's SECURITY.md is materially stronger and more complete. SeedSyncarr should expand its SECURITY.md in its own milestone. For Phase 71: update Triggarr's SECURITY.md to add the v2.8/v2.8.1 hardening specifics (CSP nonces, session-secret rotation, `apikey=` rejection) — this is PREW-03, independent of the SeedSyncarr comparison. | PREW-03 |
| 10 | **CONTRIBUTING.md structure** | Prerequisites → Getting Started → Development Commands → Before Opening a PR → Commit Conventions (conventional commits: feat/fix/docs/test/refactor) → Pull Requests → Reporting Issues (CONTRIBUTING.md, all sections) | Reporting Bugs → Requesting Features → Development Setup (Prerequisites, Getting Started, Code Style) → Pull Requests → Security (CONTRIBUTING.md, all sections). No explicit commit convention section. | Triggarr's explicit Commit Conventions section is a quality signal. Both are functional. No mandatory change for Phase 71 — note for informational alignment. If SeedSyncarr's maintainer adds commit conventions in its own milestone, they can match Triggarr's. | (informational) |
| 11 | **"What this is" one-liner** | "Python automation daemon that triggers searches in Radarr, Sonarr, and Lidarr on a schedule." (README.md:6) — technically accurate, feature-focused, leads with implementation language | "Sync files from your seedbox to your local media server — fast, automated, and integrated with Sonarr and Radarr." (README.md:13, blockquote) — leads with user benefit; "fast" and "automated" are outcomes not implementation details | Triggarr's one-liner is dry. Phase 71 PREW-01 should rewrite to lead with the user benefit: "Radarr, Sonarr, and Lidarr never auto-search — Triggarr does. Scheduled searches, closed-loop grab tracking, runs in Docker." (Direction only; exact copy is Phase 71 scope.) | PREW-01 |

---

## Additional Signal: `~/seedsync` cross-link

The separate smaller repo `github.com/thejuran/seedsync` (at `/Users/julianamacbook/seedsync` locally) is a distinct project from SeedSyncarr. It is not referenced in either Triggarr or SeedSyncarr's Related Projects sections and appears out of scope for the v2.9 launch-hardening milestone. Not a Phase 71 item unless the maintainer decides to add it to the Related Projects cross-links.

---

## Summary: Where Triggarr Leads vs. Where SeedSyncarr Leads

**Triggarr is AHEAD (signals 8, 9, 10):**
- Security reporting: GSVR vs email
- SECURITY.md depth: full threat model vs 5 bullet points
- Commit conventions: explicitly documented

**SeedSyncarr leads in presentation (signals 1, 2, 3, 5, 6, 7, 11):**
- Visual wordmark above the fold
- Screenshot above the fold
- 4 badges including Release + License
- Section structure: Quick Start first, Related Projects present
- Benefit-led one-liner

**Rough parity (signals 4, 10):**
- Docker badge style (minor)
- CONTRIBUTING structure (both functional)

---

## Phase 71 Action Map

| Phase 71 PREW item | Signals from this audit |
|--------------------|------------------------|
| PREW-01 (README rewrite) | 1, 2, 3, 4, 5, 6, 11 |
| PREW-03 (SECURITY.md reconciliation) | 9 (Triggarr gaps: v2.8/v2.8.1 hardening specifics) |
| PREW-04 (community-health files) | — (not in scope of this audit; see 70-CRITIQUE.md for bug-template gap) |
| PREW-07 (cross-repo signal reconciliation) | 7 (Related Projects), 8 (security reporting — Triggarr already leads) |

---

**Verification:** `git -C /Users/julianamacbook/seedsyncarr status --porcelain` = clean (only pre-existing untracked files; no working-tree modifications). SeedSyncarr working tree was read-only throughout this audit.
