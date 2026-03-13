# Phase 43: Update Notification & Cleanup - Context

**Gathered:** 2026-03-13
**Status:** Ready for planning

<domain>
## Phase Boundary

Dashboard indicates when a newer Triggarr release is available by checking GitHub releases. Dashboard shows a migration banner when `.migrated` marker exists from v2.2→v2.3 upgrade. Dead code (ArrConfig alias + any other dead imports from multi-instance migration) removed. Covers requirement VER-02.

</domain>

<decisions>
## Implementation Decisions

### Update notification display
- Nav bar badge next to existing version text — e.g., "v0.1.0 • v0.2.0 available"
- Check GitHub releases API every 24 hours (on startup + periodic background check)
- Badge links to GitHub releases page (opens in new tab)
- Silent fail on GitHub API errors — no indicator shown, debug-level log, retry next cycle
- Green/accent color for the "available" text to match the triggarr-green theme

### Migration banner
- Full-width info banner at top of dashboard, above health summary card
- Blue/info color scheme (bg-blue-500/20 text-blue-400) to distinguish from warnings
- Dismissible — clicking X deletes the `.migrated` marker file via API endpoint
- One-time notice: once dismissed, stays gone across restarts
- Message: "Config migrated to v2.3 format. Your settings were updated."

### Dead code removal
- Remove ArrConfig backward-compat alias from `models/config.py` (lines 64-65)
- Remove ArrConfig import from `tests/test_config.py` (line 18)
- Also scan for and remove any other unused imports or dead references introduced during the v2.3 multi-instance migration

### Claude's Discretion
- GitHub API endpoint choice (releases/latest vs releases list)
- Version comparison logic (semver parsing vs string comparison)
- How to cache the latest version check result in memory
- Background task scheduling approach for the 24h check interval
- Migration banner dismiss endpoint path

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `__version__` in `triggarr/__init__.py` — current version string
- `templates.env.globals["triggarr_version"]` in `routes.py:41` — already passed to all templates
- `base.html:19` — version display in nav bar, insertion point for update badge
- httpx async client pattern in `clients/base.py` — reusable for GitHub API calls
- `.migrated` marker creation in `config.py:158-160` — already writes the file

### Established Patterns
- htmx partials with `hx-swap` for dynamic updates
- Card/banner wrapper: `bg-triggarr-card rounded-lg border border-triggarr-border`
- Color schemes: green (success), red (error), amber (warning), blue (info)
- Startup banner logging in `startup.py`

### Integration Points
- Nav bar version text in `base.html` — extend with update badge
- Dashboard template top — insert migration banner before health summary
- `routes.py` — add dismiss endpoint for migration banner
- App startup — schedule periodic GitHub release check

</code_context>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches within the decisions above.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 43-update-notification-cleanup*
*Context gathered: 2026-03-13*
