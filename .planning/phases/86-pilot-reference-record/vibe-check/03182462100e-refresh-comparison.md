# Vibe-check deep review — Refresh-counts pilot, H1

Rendered report as shown in the session (raw agent outputs and the scorer result are in the `.json` file beside this one).

- Tool: vibe-check deep-review 2.12.0, stock invocation, range mode (stateless, no fix loop)
- Range: `d5a4467a4c38f8f675fb057d9a77bcc3030c379d..03182462100e9f71defc9408245410d2b99110a5`
- Coverage evidence: exact-head local coverage (option 2), provenance `check` passed for H1
- Agents: bugs (opus), security, architecture (opus), impact, test-sufficiency, compliance, language-python, framework-fastapi; vibe-check's own Codex pass joined (verdict approve, 0 findings)
- Git-safety gate: rc 0; four agent commands refused by the guard (awk, two `uv run ruff`, one heredoc), repo untouched

| Found | Reported | Filtered |
|-------|----------|----------|
| 7 | 3 | 4 |

## Bottom line

Ship-safe as written. No reviewer found a correctness, security or data-loss problem. Codex approved; security, compliance, Python and FastAPI found nothing. Three items remain, all minor:

1. Three agents flagged it independently: Sonarr's Refresh counts checks air dates before dropping unmonitored episodes, while the scheduled cycle does the reverse. The counts are identical either way; the only effect is extra "skipped malformed record" warnings in System Logs.
2. Test gap: the tag-scoped Sonarr missing-queue skip is untested.
3. Test gap: no test asserts that the returned cutoff list is the screened one.

## Warning

| # | File | Score | Agent | Finding |
|---|------|-------|-------|---------|
| 1 | `triggarr/search/engine.py:2116` | 80 | test-sufficiency | Sonarr count refresh never tests the new tag-screening step for a missing-queue tag (L2117/L2121 0 hits, L2116 50% branch) |

## Medium

| # | File | Score | Agents | Finding |
|---|------|-------|--------|---------|
| 2 | `triggarr/search/engine.py:2112` | 79 | architecture + bugs + impact | Sonarr Refresh counts checks air dates before the monitored filter, unlike the scheduled Sonarr cycle (missing 2111-2115 and cutoff 2137-2141) |
| 3 | `triggarr/search/engine.py:2015` | 77 | test-sufficiency | No test checks that the screened cutoff list (not the raw one) is what Refresh counts returns (also L2181, L2337) |

## Filtered

| Reason | Count |
|---|---|
| Absorbed into row #2 (cross-agent dedup) | 2 (bugs-001, imp-001) |
| Sub-threshold | 2 (cov-003 monitored-count correction never tested with a non-zero drop; cov-004 Radarr/Lidarr cutoff-tag-unresolved path untested) |

## Notes

- Architecture: the cycle and refresh chains exist in two copies per app, and the Sonarr copies have already drifted (row #2). The comments at `routes.py` 1157-1158 and 1177-1179 still refer to the old "rewrite-3 data fault" behavior and are now stale.
- Impact: no signature changes, and the only production caller ignores the returned tuple. Count parity with the cycles was verified line by line; the only difference is the Sonarr ordering, which affects logs only. No breaking changes.
- Test coverage: `engine.py` at H1 has 97.3% line and 94.85% branch coverage, from 3279 passing tests.
