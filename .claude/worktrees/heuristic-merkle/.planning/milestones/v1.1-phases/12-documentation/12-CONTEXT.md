# Phase 12: Documentation - Context

**Gathered:** 2026-02-24
**Status:** Ready for planning

<domain>
## Phase Boundary

Create a README.md that lets a new user install and configure Fetcharr from the README alone. Covers install guide, config reference, security model, and screenshots. No new features or code changes — documentation only.

</domain>

<decisions>
## Implementation Decisions

### README structure
- Hero section first: one-liner description, badge bar (CI, Docker pulls, license), brief motivation paragraph
- Table of contents after hero section with linked section anchors
- Section order: hero → TOC → features list → screenshots → install → config reference → security model → development
- Brief development section at the bottom with uv sync, pytest, ruff commands for contributors

### Install section
- Docker Compose only — no docker run one-liner, no bare-metal instructions
- Single copy-paste docker-compose.yml example with inline comments
- Docker-first project, audience already knows Docker

### Config reference format
- Annotated TOML example showing all fields with their defaults
- Every field documented with inline comments (default value, valid range, description)
- Environment variable overrides shown inline alongside TOML fields
- Mention the web UI config editor as an alternative to editing TOML directly

### Tone & audience
- Primary audience: arr power users already running Radarr/Sonarr in Docker
- Concise & practical tone — short sentences, code-first, minimal prose (like Traefik/Caddy docs)
- Brief motivation paragraph: "Radarr/Sonarr don't auto-search on a schedule. Fetcharr does." Then move on.
- Short feature bullet list (5-6 items): scheduled searches, web dashboard, config editor, search history, hard max limit, Docker-first

### Screenshots
- 2 screenshots: dashboard + config editor (matches success criteria)
- Placed after features list, before install section
- Stored in docs/screenshots/ directory, referenced as relative paths
- Placeholder paths in README (docs/screenshots/dashboard.png, docs/screenshots/config-editor.png) — user adds actual images manually

### Claude's Discretion
- Badge selection and ordering
- Exact section heading wording
- Security model section structure and depth
- Whether to include a "How it works" brief explanation
- LICENSE badge linking

</decisions>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 12-documentation*
*Context gathered: 2026-02-24*
