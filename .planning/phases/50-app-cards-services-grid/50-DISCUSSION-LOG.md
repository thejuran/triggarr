# Phase 50: App Cards & Services Grid - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-13
**Phase:** 50-app-cards-services-grid
**Areas discussed:** Connection pill states, Unreachable card treatment, Schedule row & pass pills, Grid layout breakpoints

---

## Gray Area Selection

| Option | Description | Selected |
|--------|-------------|----------|
| Connection pill states | How to render Connected / Unreachable / Waiting in one unified pill shape | (deferred to mockup) |
| Unreachable card treatment | Danger stripes, Retry button, dimmed stats | (deferred to mockup) |
| Schedule row & pass pills | Where timestamps go, pass count format | (deferred to mockup) |
| Grid layout breakpoints | 3-column at xl breakpoint behavior | (deferred to mockup) |

**User's choice:** "Ask the AIDesigner MCP/skill" — user directed to use the existing mockup as the definitive design contract rather than interactive discussion.

**Notes:** The existing mockup at `.aidesigner/enhanced-mockup-v3.html` L264-417 already defines every visual detail for all 4 gray areas. All decisions were extracted directly from the mockup markup and locked as implementation decisions in CONTEXT.md.

---

## Claude's Discretion

- Time formatting for schedule row (HH:MM:SS vs relative time)
- Tag warning SVG icon choice
- Whether `.card-hover` includes transform property
- Test file organization
- Retry button endpoint (reuse vs separate)

## Deferred Ideas

- Sparkline trend in app cards (FUT-01)
- Keyboard shortcut overlay (FUT-02)
- Card collapse/expand (not in requirements)
