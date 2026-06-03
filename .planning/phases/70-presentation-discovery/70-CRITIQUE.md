# 70-CRITIQUE.md — Cynical-Reader Teardown (PDISC-01)

**Provenance:** 2026-06-02 · branch: launch-hardening · commit: fc5553d
**Persona:** r/selfhosted commenter arriving cold at github.com/thejuran/triggarr
**Structure:** Three D-08 first-impression lenses
**Status:** Input artifact for Phase 71 PREW-01/03/04/05/07

---

## Lens (a): Is this trustworthy / a serious project?

### Gripe 1 — Plain H1 + two badges: minimum viable header

**Evidence:** `README.md:1-4` — the header is literally `# Triggarr` on line 1 followed by a CI badge and a Docker badge. That is the entire first impression above the fold.

**Why it matters:** Two badges reads as "I got the GitHub Actions boilerplate working." The sibling author's other repo (SeedSyncarr) leads with a centered `<picture>` wordmark block (dark/light variants), a centered screenshot, a benefit-led blockquote, and *four* badges including a live release version badge and a license badge. A viewer hopping from SeedSyncarr to Triggarr will notice the drop in visual seriousness immediately.

**Fix direction:** Add a Release badge (shields.io `github/v/release/thejuran/triggarr`) and a License badge. Consider adding a wordmark or at minimum an above-the-fold screenshot. Phase 71 PREW-01.

---

### Gripe 2 — No release badge: how mature is this thing?

**Evidence:** `README.md:3-4` — only CI and Docker badges. No release badge. The current version is v2.8.1 and was shipped 2026-06-01, but a first visitor has no quick signal of that.

**Why it matters:** A release badge with a live version number is the fastest possible credibility signal — it tells a skeptic "this is actively maintained and tagged." Without it, a visitor must scroll into the README body, find the install section, and notice the pip install URL references `2.7.2` (which then makes them suspicious, not reassured — see Gripe 6).

**Fix direction:** Add `[![Release](https://img.shields.io/github/v/release/thejuran/triggarr)](https://github.com/thejuran/triggarr/releases)`. Phase 71 PREW-01.

---

### Gripe 3 — Screenshots are below the fold and visually stale

**Evidence:** `README.md:35-40` (Screenshots section, below Table of Contents and Features). Screenshot files: `docs/screenshots/dashboard.png`, `history.png`, `settings.png` — all have modification date 2026-04-14.

**Why it matters:** Current version is v2.8.1 (2026-06-01). The screenshots predate the v2.7 dashboard redesign (Phosphor icons, new stat cards, colored app-card borders, three-zone header), the v2.6 auth UI, and all v2.8 observability additions. A r/selfhosted reader who does scroll to Screenshots sees an outdated UI and may conclude the project is abandoned or the README is not maintained. The `?v=2` cache-busting parameter on the image URLs (`dashboard.png?v=2`) paradoxically signals "these images get versioned" — raising the question of whether `?v=2` is the latest. The screenshots being below ToC + Features means a significant fraction of visitors never see the UI at all.

**Fix direction:** Move screenshots above the fold (at minimum after the badges/tagline). Recapture via Playwright at the Phase 71 NAS walkthrough (PREW-02). Do NOT recapture in this phase.

---

### Gripe 4 — Bug report template version dropdown tops at v2.3

**Evidence:** `.github/ISSUE_TEMPLATE/bug-report.yml:10-14` — the version dropdown options are: `v2.3`, `v2.2`, `v2.1`, `Older`. Current version is v2.8.1. A user on any version from v2.4 through v2.8.1 must select "Older" — which is both inaccurate and signals the project hasn't kept up with its own housekeeping.

**Why it matters:** Issue templates are community-health signals that GitHub itself surfaces. An "Older" selection for v2.8.1 makes the bug template feel abandoned and may discourage issue filing. It also means the maintainer gets no accurate version signal in bug reports.

**Fix direction:** Update the version dropdown to include v2.8.1, v2.8, v2.7, v2.6, v2.5, v2.4, and "Older". Phase 71 PREW-04.

---

### Gripe 5 — Bug report "App Type" dropdown omits Lidarr

**Evidence:** `.github/ISSUE_TEMPLATE/bug-report.yml:29-34` — App Type options are `Radarr`, `Sonarr`, `Both`. No `Lidarr`.

**Why it matters:** Lidarr is a documented first-class supported app — it appears in the Features list (`README.md:22`), in the Configuration Reference TOML example (`README.md:178-184`), and in the one-liner (`README.md:6`). A Lidarr user filing a bug must pick `Radarr`, `Sonarr`, or `Both` — none of which is accurate. This is a consistency failure that tells Lidarr users they are second-class.

**Fix direction:** Add `Lidarr` and `All` options to the App Type dropdown. Phase 71 PREW-04.

---

### Gripe 6 (cross-reference) — The pip install line cites v2.7.2

*(Full coverage under Lens (b), Gripe 7. Noted here because it also affects trustworthiness — a visitor who spots the version mismatch in the install section wonders what else is stale.)*

---

## Lens (b): Can I get it running in ~5 minutes?

### Gripe 7 — Standalone pip install hardcodes v2.7.2, not the current version

**Evidence:** `README.md:85` — `pip install https://github.com/thejuran/triggarr/releases/latest/download/triggarr-2.7.2-py3-none-any.whl`

The actual `__version__` in `triggarr/__init__.py` is `2.8.1`. The URL even says `releases/latest/download/` but the filename hardcodes `2.7.2`. This is a factual accuracy failure: a user copy-pasting this line installs v2.7.2, not v2.8.1.

**Why it matters:** This is the #1 PDISC-02 correctness anchor — it is not ambiguous, not stale documentation, not a matter of framing. It is simply wrong. A user following the standalone instructions ends up two minor releases behind without any indication. The Docker path correctly references `:latest`, making the contrast between the two install paths more jarring.

**Fix direction:** The pip URL should either (a) not hardcode a filename and instead link to `releases/latest` with a `curl`-then-pip pattern, or (b) update the whl filename to match the release being documented. The former is more resilient to future releases. Phase 71 PREW-01.

---

### Gripe 8 — Docker first-run exit behavior: described but not explained

**Evidence:** `README.md:78` — "On an empty volume, Triggarr writes `/config/triggarr.toml` first; with the `restart: unless-stopped` example above, the container then starts normally on the next restart."

What actually happens (confirmed: `config.py:353-359`): the container runs `sys.exit(1)` after writing the default config. Docker sees a non-zero exit, applies `restart: unless-stopped`, and brings the container back up. A first-time user watching `docker compose logs -f` sees the container exit and will likely think something is broken.

**Why it matters:** The README documents the outcome ("starts normally on the next restart") but omits the mechanism (`sys.exit(1)` + container restart). A user who doesn't already know Docker's restart semantics cannot distinguish this from a crash loop. The wording "starts normally on the next restart" is accurate but buries the important caveat.

**Fix direction:** Add a single sentence: "The first run exits with code 1 after writing the config — this is expected. Docker's `restart: unless-stopped` brings the container back up automatically; edit the config, then visit `http://localhost:8484`." Phase 71 PREW-01.

---

### Gripe 9 — No "Quick Start" section: installation friction

**Evidence:** `README.md:10-19` (Table of Contents) — first actionable content is the `## Install` section, which is the fourth ToC entry. Readers must scroll past ToC, Features, and Screenshots before finding a compose block to copy.

**Why it matters:** SeedSyncarr leads with a `## Quick Start` section immediately after the badges — three lines of compose YAML, done. Triggarr buries the compose block under three prior sections. For a homelab tool that sells itself on quick setup ("set a schedule, walk away"), the friction before first action is noticeable.

**Fix direction:** Add a `## Quick Start` section at or near the top (after badges/tagline) with the minimal compose block and the "visit `http://localhost:8484`" next step. The current Install section can remain for the full reference. Phase 71 PREW-01.

---

## Lens (c): Why this over the *arr apps' native search or cron + curl?

### Gripe 10 — The one-liner is accurate but dry and feature-focused, not benefit-led

**Evidence:** `README.md:6` — "Python automation daemon that triggers searches in Radarr, Sonarr, and Lidarr on a schedule."

**Why it matters:** This answers "what is it" but not "why do I need this." The follow-up sentence at `README.md:8` is better — "Radarr, Sonarr, and Lidarr don't auto-search for missing and upgrade-eligible media on a timer. Triggarr does -- set a schedule, walk away." — but it is buried after the one-liner. A skeptic skimming the top of the page may not reach it.

SeedSyncarr's equivalent: "Sync files from your seedbox to your local media server — fast, automated, and integrated with Sonarr and Radarr." That leads with the user benefit, not the implementation language.

**Fix direction:** Rewrite the one-liner to lead with the benefit: something like "Missing media sits unwatched because Radarr and Sonarr never re-search. Triggarr fixes that — scheduled searches, closed-loop grab tracking, runs in Docker." Phase 71 PREW-01.

---

### Gripe 11 — No "Related Projects" section: the cross-link gap

**Evidence:** Triggarr README has no "Related Projects" section. SeedSyncarr's `README.md:104-106` has: "Related Projects: **Triggarr** — lightweight search automation daemon for Radarr, Sonarr, and Lidarr. SeedSyncarr handles the download-to-sync side; Triggarr handles the search-to-trigger side."

**Why it matters:** A viewer who arrives at Triggarr via SeedSyncarr's cross-link is told "you're in the right place"; a viewer who arrives at Triggarr cold never gets a pointer to SeedSyncarr (the complementary tool they likely also want). Both tools are by the same author — the asymmetry means Triggarr misses a positioning and discovery opportunity. This is also the highest-signal trivially-fixable item in the entire teardown.

**Fix direction:** Add a `## Related Projects` section linking to SeedSyncarr with the same one-line complement description (mirroring SeedSyncarr's approach). Phase 71 PREW-07.

---

### Gripe 12 — The SECURITY.md is solid but omits v2.8/v2.8.1 hardening specifics

**Evidence:** `SECURITY.md:38` — "a restrictive Content Security Policy" is the only reference to CSP. The following hardening measures implemented in v2.8/v2.8.1 are absent from SECURITY.md:
- CSP `script-src` nonce (no `unsafe-inline`) — implemented, not named
- Session-secret rotation on password change (CWE-613, v2.8.1) — in README Security Model (`README.md:197`) but not in SECURITY.md
- `apikey=` URL rejection (auth middleware) — not mentioned
- Basic-auth control-character validation — not mentioned
- Session-secret startup length check — not mentioned

**Why it matters:** A security-conscious viewer reading SECURITY.md gets a solid overview but misses the most recent hardening layer. For a project calling out "Zero credential exposure by design" (PROJECT.md), the gap between what the code does and what the SECURITY.md claims is a credibility gap at the exact point where skeptics are paying closest attention.

**Fix direction:** Update SECURITY.md to enumerate the v2.8/v2.8.1 hardening specifics. Phase 71 PREW-03.

---

## Summary Hitlist for Phase 71

| # | Gripe | Evidence | Fix Direction | PREW Item |
|---|-------|----------|---------------|-----------|
| 1 | Plain H1 + 2 badges | README:1-4 | Add wordmark or stronger header | PREW-01 |
| 2 | No release badge | README:3-4 | Add shields.io release badge | PREW-01 |
| 3 | Screenshots below fold + stale (2026-04-14) | README:35-40, `docs/screenshots/*.png` timestamps | Move above fold; recapture at walkthrough | PREW-01, PREW-02 |
| 4 | Bug template version tops at v2.3 | `.github/ISSUE_TEMPLATE/bug-report.yml:10-14` | Update to include v2.8.1 through v2.4 | PREW-04 |
| 5 | Bug template omits Lidarr from App Type | `.github/ISSUE_TEMPLATE/bug-report.yml:29-34` | Add Lidarr option | PREW-04 |
| 6 | pip install cites v2.7.2 (actual: v2.8.1) | README:85 | Fix whl URL to not hardcode version | PREW-01 |
| 7 | Docker first-run exit not explained | README:78 | Add one sentence on sys.exit(1) + restart | PREW-01 |
| 8 | No Quick Start section | README ToC (README:10-19) | Add Quick Start with compose block at top | PREW-01 |
| 9 | One-liner is feature-not-benefit-led | README:6 | Rewrite to lead with benefit | PREW-01 |
| 10 | No Related Projects cross-link | README (absent) | Add Related Projects → SeedSyncarr | PREW-07 |
| 11 | SECURITY.md omits v2.8/v2.8.1 specifics | SECURITY.md:38 | Enumerate CSP nonce, session rotation, etc. | PREW-03 |
