# M005: In-App Changelog

**Vision:** Users can view a formatted changelog directly in the Triggarr web UI, following the Tautulli model: a CHANGELOG.md shipped in the repo, read from disk at runtime, rendered as HTML. No external API calls, works offline.

## Success Criteria

- CHANGELOG.md in repo root with entries for all releases from v2.6.0+
- Changelog link visible in the nav bar
- Clicking it shows a formatted changelog with version headers and categorized bullet lists
- Changelog renders correctly in the app's dark theme
- Existing functionality unchanged (no regressions)

## Key Risks / Unknowns

- Markdown-to-HTML approach: use a library (mistune/markdown) or custom regex like Tautulli — need to decide
- How to present: modal (Tautulli style) vs dedicated page — modal keeps nav clean, page allows linking

## Proof Strategy

- Rendering approach → retire in S01 by building parser and testing with real changelog content

## Verification Classes

- Contract verification: pytest tests for changelog parser with fixture content
- Integration verification: route serves rendered HTML from real CHANGELOG.md
- Operational verification: Docker build includes CHANGELOG.md
- UAT / human verification: changelog displays correctly in browser

## Milestone Definition of Done

This milestone is complete only when all are true:

- CHANGELOG.md exists with release history
- Changelog renders in web UI via nav bar link
- Parser handles version headers, categorized lists, and edge cases
- All existing tests still pass
- Docker builds successfully

## Requirement Coverage

- Covers: in-app changelog (new capability)
- Partially covers: none
- Leaves for later: cross-instance dedup (someday/maybe)
- Orphan risks: none

## Slices

- [x] **S01: Changelog Parser, Route & UI** `risk:medium` `depends:[]`
  > After this: CHANGELOG.md exists in repo, a parser reads and converts it to HTML, a nav bar link opens the changelog as a modal or page in the web UI with dark-theme styling. Proven by parser unit tests, route tests, and browser verification.
