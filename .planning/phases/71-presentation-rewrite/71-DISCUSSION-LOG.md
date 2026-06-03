# Phase 71: Presentation rewrite - Discussion Log

> **Audit trail only.** Not consumed by downstream agents (researcher, planner, executor).
> Decisions are captured in `71-CONTEXT.md`; this log preserves how they were reached.

**Date:** 2026-06-02
**Phase:** 71-presentation-rewrite
**Mode:** discuss (default)
**Areas presented:** README restructure depth, Header/wordmark treatment, SSRF claim fix (docs vs code), Release-notes & security tone
**Areas selected by user:** all four

---

## Area 1 — SSRF claim fix: docs vs code

**Context presented:** Codex HIGH — `validate_arr_url()` runs only in the web settings POST
(`web/routes.py:561`); URLs set directly in `triggarr.toml` bypass SSRF/scheme validation, so the
blanket README:215 / SECURITY.md:39 claim is overstated. Verified in code before asking.

**Q1 — How to resolve?**
- Options: Scope the doc claim (docs-only, recommended) / Widen validation into config load (code) /
  Defer code fix to backlog.
- **User chose:** Widen validation into config load (code) — make the claim true rather than scope it.

**Q2 — Loopback + fail mode (follow-up, since widening touches startup behavior):**
- Confirmed first: `validate_arr_url` intentionally allows private LAN IPs (10.x/192.168.x); only
  loopback/link-local/unspecified/multicast/metadata are blocked. Edge case: same-host *arr via
  `127.0.0.1`/`localhost` would be rejected on TOML load.
- Options: Allow loopback on load, block only metadata/link-local (recommended) / strict + fail-fast /
  strict + log-and-skip.
- **User chose:** Allow loopback on TOML load; reject only metadata/link-local. Web-form stays strict.
- **Result:** No existing config breaks on upgrade; doc claim becomes accurate; covering test required.

---

## Area 2 — README restructure depth

**Context presented:** Consistency-audit signal 5 + teardown want Quick Start first, Related Projects,
screenshots above the fold. SeedSyncarr's full section order shown vs Triggarr's current order.

**Q1 — How deep should the restructure go?**
- Options: Full reorder to mirror SeedSyncarr (recommended, with proposed 11-section order, ToC dropped) /
  Targeted insertions keep current order / Let planner decide per-section.
- **User chose:** Full reorder to mirror SeedSyncarr — accepted the proposed order and dropping the ToC.

---

## Area 3 — Header / wordmark treatment

**Context presented:** SeedSyncarr leads with a centered `<picture>` wordmark (dark/light). Triggarr
has a plain H1. Triggarr has a v2.7 favicon asset but no README wordmark image.

**Q1 — Header look?**
- Options: Centered H1 + 4 badges + tagline, no image wordmark (recommended) / Create a wordmark image
  to match SeedSyncarr / Reuse the v2.7 favicon as a small logo mark.
- **User chose:** Centered H1 + badges + benefit-led tagline + above-fold screenshot, no new image asset.
- **Result:** Mirrors SeedSyncarr's centered/badge-rich feel with zero new-asset dependency.

---

## Area 4 — Release-notes & security tone

**Context presented:** (A) SECURITY.md needs the at-rest-plaintext caveat (codex MEDIUM) AND the
v2.8/v2.8.1 hardening enumerated (PREW-03). (B) CHANGELOG.md IS the in-app changelog source — what
should the v2.9.0 entry list?

**Q1 — Framing?**
- Options: Honest selling-point security + user-facing v2.9.0 notes (recommended) / Minimal factual /
  Comprehensive (include internal work).
- **User chose:** Honest selling-point security + user-facing v2.9.0 notes.
- **Result:** SECURITY.md enumerates hardening confidently + states plaintext caveat plainly; CHANGELOG
  v2.9.0 lists user-facing changes (config-load URL validation, manual-search failure-counter fix,
  docs overhaul as Documentation bullets); internal mechanics under Fixes only where user-relevant.

---

## Decisions left to Claude's discretion (recorded in CONTEXT.md)

- Exact final README copy within the locked structure; exact one-liner wording.
- Quick Start compose block contents (minimized from current Install block).
- Whether above-fold + Screenshots-section images are the same or different (both refreshed at walkthrough).
- Exact resilient pip-install pattern (curl+pip vs version-agnostic URL).
- Topics/tags list for PREW-05; optional `~/seedsync` cross-link note.

## Locked to critique-recommended defaults (no gray area — not separately discussed)

All cited `file:line` correctness fixes from the three Phase 70 artifacts: pip wheel version,
systemd `StateDirectory`, Docker first-run-exit explanation, tag-filter fail-open documentation,
Tailwind version pinning, bug-report.yml version + App-Type dropdowns, Related Projects cross-link.

## Deferred ideas raised

None beyond the pre-known milestone deferrals (screenshots → walkthrough, repo-metadata application
→ maintainer in GitHub UI, SeedSyncarr-side reconciliation → its own milestone).
