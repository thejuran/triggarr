# Phase 48 — UI Review

**Audited:** 2026-04-13
**Baseline:** Abstract 6-pillar standards (no UI-SPEC.md)
**Screenshots:** Not captured (no dev server detected on ports 3000, 5173, or 8080)

---

## Pillar Scores

| Pillar | Score | Key Finding |
|--------|-------|-------------|
| 1. Copywriting | 3/4 | Nav and state text is purposeful; changelog close button uses raw &times; with no aria-label |
| 2. Visuals | 3/4 | Sticky nav, active-tab underline, and pulsing dot are correctly implemented; tracking-tight omitted from brand wordmark |
| 3. Color | 4/4 | All color values in templates use design-system tokens; hardcoded hex confined to @theme definitions only |
| 4. Typography | 3/4 | 5 font sizes and 4 weights in use across templates — slightly over the 4-size / 2-weight abstract guideline, but the scale is coherent and intentional |
| 5. Spacing | 3/4 | Scale is consistent; -mb-[7px] arbitrary value is intentional per spec; one legacy min-w-[180px] in history partial is a pre-48 carry-over |
| 6. Experience Design | 3/4 | Accessibility primitives (focus-visible, reduced-motion) shipped; geist-mono token defined but log_viewer uses system font-mono instead |

**Overall: 19/24**

---

## Top 3 Priority Fixes

1. **Changelog close button missing aria-label** — Screen-reader users hear "&times;" read as "multiply sign" or "times" with no context that it dismisses the modal — add `aria-label="Close changelog"` to the `<button onclick="closeChangelog()">` element at `base.html:61`.

2. **log_viewer.html uses `font-mono` instead of `font-geist-mono`** — The Geist Mono token was shipped specifically to give monospace surfaces (the log pane is the primary one) a consistent branded typeface. The existing partial at `triggarr/templates/partials/log_viewer.html:10` uses the system `font-mono` utility. Change `font-mono` to `font-geist-mono` to activate the self-hosted font where it matters most.

3. **Brand wordmark missing `tracking-tight`** — The design mockup (enhanced-mockup-v3.html line 165) and CONTEXT.md both specify `tracking-tight` on the "Triggarr" brand span. The implementation at `base.html:19` has `font-bold text-xl` but omits `tracking-tight`. This is a minor visual regression; add `tracking-tight` to the span class list.

---

## Detailed Findings

### Pillar 1: Copywriting (3/4)

The nav chrome introduced in this phase uses purposeful, specific copy throughout:

- Update chip label "v{{ latest_version }} available" (`base.html:30`) is concrete and action-oriented — no generic "New version" pattern.
- Version button title "View changelog" (`base.html:22`) is accurate and specific.
- Update chip title "Update available — click to view release" (`base.html:28`) provides context without being verbose.
- Nav links ("Dashboard", "History", "Settings") use direct functional names.

One gap: the changelog close button at `base.html:61–62` uses `&times;` as its visible label with no `aria-label` or `title` attribute. An icon-only interactive element without an accessible name fails WCAG 2.1 SC 1.1.1. The `openChangelog` button has `title="View changelog"` — the close button should have equivalent disclosure.

No generic "Submit", "OK", or "Cancel" labels were found anywhere in the templates. Empty-state copy is specific ("No apps configured. Visit Settings to add...") and provides a resolution path.

### Pillar 2: Visuals (3/4)

The phase 48 chrome additions implement the spec correctly:

- `sticky top-0 z-30 backdrop-blur-md bg-triggarr-card/80` on the `<nav>` element (`base.html:16`) — all four classes present.
- Active-tab underline: `text-white border-b-2 border-triggarr-green pb-1 -mb-[7px]` applied conditionally via `request.url.path` comparison (`base.html:40, 44, 48`).
- Pulsing update dot: `w-1.5 h-1.5 rounded-full bg-triggarr-green dot-pulse` inside the update chip anchor, guard-wrapped in `{% if update_info and update_info.update_available %}` (`base.html:29`).
- Changelog modal retains `max-w-2xl` at z-50 — correctly above the sticky nav at z-30.
- Container widened to `max-w-7xl` on both the nav inner div and the `<main>` element (`base.html:17, 86`).

One minor gap: the "Triggarr" brand span at `base.html:19` omits `tracking-tight`, which the mockup specifies (enhanced-mockup-v3.html:165: `tracking-tight`). This is a subtle typographic discrepancy — the wordmark will render with default letter-spacing rather than the slightly condensed treatment the design system intended.

### Pillar 3: Color (4/4)

No hardcoded hex values appear in any template file. All color application goes through the design-system token classes:

- `text-triggarr-green`, `bg-triggarr-green`, `border-triggarr-green` — 18 occurrences across templates, used purposefully for interactive elements, active states, and success indicators.
- `bg-triggarr-green/15`, `bg-triggarr-green/25` — opacity-modified variants used only in the update chip, not scattered across unrelated elements.
- `bg-triggarr-card/80` on the sticky nav — intentional translucency for the backdrop-blur effect.
- `text-triggarr-muted`, `text-triggarr-text`, `bg-triggarr-bg`, `bg-triggarr-card` — all semantic.
- `text-red-400 hover:text-red-300` appears in `settings.html:92` (Remove instance button) — the one deliberate use of an off-palette color for a destructive action. This is appropriate signal differentiation and not an error.

Hardcoded hex values in `input.css` are exclusively within the `@theme` block as token definitions, which is the correct and only acceptable location per Tailwind v4 convention.

The new `--color-triggarr-card-elevated: #233346` token is defined and compiled into `output.css` (1 occurrence confirmed) but not yet applied to any element — this is correct per D-15 (usage deferred to phases 49/50).

### Pillar 4: Typography (3/4)

Font sizes in use across templates:

| Size | Count | Role |
|------|-------|------|
| text-xs | 58 | Helper text, meta labels, chip copy |
| text-sm | 46 | Body, form labels, nav links |
| text-lg | 12 | Section headings |
| text-xl | 3 | Page-level headings, brand name |
| text-2xl | 1 | Settings page title |

5 distinct sizes are in use — one above the 4-size abstract guideline. However, `text-2xl` appears only once (Settings H1 at `settings.html:6`) and the scale reads coherently: xs/sm for dense information, lg/xl for hierarchy, 2xl as a single outlier. This is a minor deviation, not a design breakdown.

Font weights:

| Weight | Count | Role |
|--------|-------|------|
| font-medium | 17 | Form labels, instance names |
| font-bold | 8 | Brand name, structural emphasis |
| font-semibold | 7 | Card headings, modal titles |
| font-normal | 1 | Explicit default reset |

4 weights in use — above the 2-weight guideline. The distinction between semibold and bold is meaningful in this dark UI (modal title vs brand wordmark); medium vs semibold for form vs structural headings is intentional. The scale is consistent enough that the abstract guideline overfits here.

The `--font-geist-mono` token is defined and compiled, but `font-geist-mono` does not appear in any template. The log viewer at `triggarr/templates/partials/log_viewer.html:10` uses `font-mono` (system stack). This gap means the self-hosted font will not activate on the primary monospace surface — a meaningful miss since the font was vendored specifically for this use.

### Pillar 5: Spacing (3/4)

The spacing scale across templates is largely consistent with Tailwind's 4px-step system:

- `px-3`, `py-2`, `p-4`, `p-5`, `px-6`, `py-3` dominate — all standard scale steps.
- `gap-2`, `gap-3`, `gap-4`, `gap-6` — consistent gap progression.
- `mt-1`, `mb-1`, `mb-4`, `mb-6` — standard vertical rhythm.

Arbitrary spacing in the phase 48 files:

- `-mb-[7px]` at `base.html:40, 44, 48` — 3 occurrences, all identical, intentional per spec (D-22). This compensates for the 2px active-tab border to maintain nav baseline alignment. Not a problem.
- `min-w-[180px]` at `triggarr/templates/partials/history_results.html:107` — pre-phase-48 carry-over, not introduced in this phase.

No arbitrary rem or em values appear. The `py-0.5`, `px-2` usage in the update chip matches the mockup spec for the compact chip component. The `gap-1.5` in the update chip (`base.html:27`) is a half-step value that corresponds to Tailwind's defined `gap-1.5` (6px) — not arbitrary.

### Pillar 6: Experience Design (3/4)

Phase 48 delivers meaningful accessibility improvements:

**Implemented correctly:**
- `:focus-visible` global ring using `var(--color-triggarr-green)` with 2px outline + 2px offset — compiled into `output.css` (confirmed).
- `@media (prefers-reduced-motion: reduce)` global flattening — compiled into `output.css` (confirmed), applies to `dot-pulse` animation.
- `font-display: swap` on both Geist Mono `@font-face` declarations — no FOIT blocking.
- Update dot renders only inside the `{% if update_info and update_info.update_available %}` guard — no spurious visual noise.
- Update chip href uses a `.startswith('https://github.com/')` guard before rendering the URL (`base.html:26`) — additional security not required by spec but added during implementation.
- Changelog modal has `Escape` key dismissal via `keydown` listener (`base.html:81–83`).
- `hx-confirm` on destructive "Remove instance" action (`settings.html:89`).

**Gaps:**
- Changelog close button (`base.html:61`) has no `aria-label` or `title` — the `&times;` entity is not machine-readable as "close". Fix: `aria-label="Close changelog"`.
- `font-geist-mono` token is not wired to any template — the self-hosted Geist Mono font faces will not load in practice until a template references the utility class. The log viewer (`log_viewer.html:10`) is the natural first consumer.
- Keyframe name in `input.css` was changed from `pulse` (as specified in the plan) to `dot-ring-pulse` (`input.css:54, 56`) — likely to avoid a collision with any Tailwind built-in `pulse` keyframe. The tests at `test_ui_foundations.py:255` assert on `dot-ring-pulse` confirming the change was intentional and tested. No functional issue, but the plan documentation references `@keyframes pulse` which would mislead future phases.

---

## Files Audited

- `triggarr/static/css/input.css` — full read, 60 lines
- `triggarr/static/css/output.css` — token presence verified (34042 bytes)
- `triggarr/templates/base.html` — full read, 90 lines
- `triggarr/templates/dashboard.html` — full read, 39 lines
- `triggarr/templates/history.html` — full read, 10 lines
- `triggarr/templates/settings.html` — full read, 192 lines
- `triggarr/templates/partials/log_viewer.html` — referenced, font-mono check
- `triggarr/templates/partials/history_results.html` — arbitrary spacing check
- `tests/test_ui_foundations.py` — keyframe name and assertions verified
- `.planning/phases/48-foundations-navigation-chrome/48-01-PLAN.md`
- `.planning/phases/48-foundations-navigation-chrome/48-02-PLAN.md`
- `.planning/phases/48-foundations-navigation-chrome/48-03-PLAN.md`
- `.planning/phases/48-foundations-navigation-chrome/48-CONTEXT.md`

Registry audit: shadcn not initialized — skipped.
