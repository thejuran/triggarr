# Quick Task 261030-oaf: Stop Codex startup code-mode notice from failing the untrusted-path event audit - Context

**Gathered:** 2026-10-30
**Status:** Ready for planning

<domain>
## Task Boundary

The Phase 85.1 post-merge live inspection-only review (PR #52, head `16a719d`) was INCOMPLETE because Codex emitted a startup item
`{"type": "error", "message": "Code Mode is unavailable because code-mode host is disabled. Code mode will fail closed; enable features.code_mode_host and install codex-code-mode-host."}`
and `audit_event_types` (`tests/codex_review_run.py`) correctly failed closed on it ("inspection-only review used a tool: error").
`code_mode` is `under development`/off by default in the review image (Codex 0.153.4), so it is being enabled for the account from outside the image; the runner already passes `--disable code_mode_host` (DISABLED_FEATURES), which is what produces the notice.

Fix: make the inspection-only Codex invocation also disable `code_mode` (and related `code_mode_*` flags that can surface the notice), so the notice is never emitted, with the audit allowlist unchanged.

</domain>

<decisions>
## Implementation Decisions

### Audit strictness (owner decision, 2026-10-30)
- The event audit (`audit_event_types` / `_new_disallowed_item`, ALLOWED_ITEM_TYPES / ALLOWED_EVENT_TYPES) MUST stay unchanged and fail-closed. No allowlisting of `error` items, and no exception for this notice text.
- Owner chose "Stop and ask": ship only the feature switch-off. If a local check shows the notice is still emitted with `code_mode` disabled, STOP and report to the owner — do not loosen the audit.

### Claude's Discretion
- Which exact `code_mode_*` flags to add (verify each name exists in the image's `codex features list`; `--strict-config` must still accept the argv).
- Whether the trusted-path argv gets the same flags (only if it shares DISABLED_FEATURES or it is free and consistent).
- Test shape, following the existing tests for DISABLED_FEATURES / audit_event_types.

</decisions>

<specifics>
## Specific Ideas

- Tests: argv includes `--disable code_mode`; an event stream containing the recorded `error` item still yields "inspection-only review used a tool: error" (regression pin that the audit was not loosened).
- Pre-merge local proof (runner refuses non-main HEAD for live `--untrusted` runs, D-02): run the pinned review image's Codex directly with the new disable set on a trivial, non-PR prompt and confirm the JSON event stream contains no `error` item. Record the result.
- The real live rerun on a qualifying Dependabot PR happens after this PR merges (D-03), per 85.1-UNTRUSTED-BOUNDARY.md.

</specifics>

<canonical_refs>
## Canonical References

- `.planning/phases/85.1-isolated-codex-review-for-untrusted-prs/85.1-REVIEW-EVIDENCE.md` — "Post-merge live run (D-02, D-03): INCOMPLETE"
- `.planning/phases/85.1-isolated-codex-review-for-untrusted-prs/85.1-UNTRUSTED-BOUNDARY.md` — post-merge procedure and escalation rules
- `.planning/phases/85.1-isolated-codex-review-for-untrusted-prs/codex/16a719d720b3-untrusted-e2e-a1.jsonl` — the recorded event stream
- `docs/codex-adversarial-review-contract.md`

</canonical_refs>

## Outcome (2026-10-30)

Research (261030-oaf-RESEARCH.md) met the owner's stop condition: disabling `code_mode` does not suppress the notice (the default model is code-mode-only); only `-m gpt-5.5` does. Reproduced by the orchestrator offline. Owner decisions: "Keep vibe-check fallback" (no code change) and "Close as an exception" for Phase 85.1. No plan, execution, review or verification ran; nothing was changed in code.
