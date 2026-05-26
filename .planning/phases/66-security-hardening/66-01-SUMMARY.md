# Plan 66-01: SEC-02 URL Validator — SUMMARY

**Date:** 2026-05-26
**Plan:** 66-01-PLAN.md
**Requirement:** SEC-02 (Reject `apikey=` in *arr URLs at config save time)
**Type:** TDD
**Wave:** 1
**Status:** Complete

## What Shipped

Added a Pydantic v2 `@field_validator("url")` on `InstanceConfig` in `triggarr/models/config.py` that rejects URLs whose query string contains an `apikey=` key (any case, including URL-encoded variants and empty-value form).

## Tasks Completed

| Task | Type | Outcome |
|------|------|---------|
| 1. RED — Add failing parametrized tests | tdd | 14 parametrized cases (8 reject + 6 accept); imports SecretStr added to tests |
| 2. GREEN — Implement validator | tdd | `@field_validator("url")` placed above existing `@model_validator(mode="after")`; uses `parse_qsl(keep_blank_values=True)` per Pitfall 6; `key.lower().startswith("apikey")` per codex M2; raises ValueError with exact D-08 message |
| 3. REFACTOR — Regression sweep | tdd | Verify-only — no source change needed; 76/76 config tests pass; ruff clean |

## Files Changed

| File | +/- |
|------|-----|
| `triggarr/models/config.py` | +28 −1 |
| `tests/test_config.py` | +45 −1 |

## Test Results

- `tests/test_config.py` — 76 passed
- Full suite (`uv run pytest tests/ -x -q`) — 928 passed (up from 857 baseline; +71 new tests across Wave 1)
- `uv run ruff check triggarr/ tests/` — All checks passed

## Key Decisions

1. **Validator placement above `at_least_one_search_count`** — field-level checks must run before the model-level invariant (Pydantic v2 semantics).
2. **`parse_qsl(keep_blank_values=True)`** — `?apikey=` (empty value) parses as `("apikey", "")` and must still be rejected; default `parse_qsl(keep_blank_values=False)` would drop it (Pitfall 6).
3. **`startswith("apikey")` instead of `== "apikey"`** — codex M2 (2026-05-26 adversarial review): the URL-encoded variant `?apikey%3Dsecret` is decoded by parse_qsl to the key `apikey=secret`, which is NOT exactly `apikey` but DOES start with it. Narrow rule still excludes legitimate non-apikey query keys.
4. **No UI surfacing** — the existing handler at `routes.py:565-569` catches `pydantic.ValidationError`, logs WARNING via the redacting loguru sink, and 303-redirects. The user-visible failure mode is "save did not take effect; URL field still shows the rejected value on reload." Documented as acceptable per CONTEXT D-08 deferral; future UX phase can layer field-level error surfacing.

## Codex Adversarial Findings Addressed

- **M2 (URL-encoded apikey variant):** Implementation uses `startswith("apikey")`; tests include `?apikey%3Dsecret` and `?apikey%3D%73ecret` parametrized cases.
- **M1 (silent-redirect UX):** Documented as accepted deferral per D-08; success criteria explicitly note the log-only path.

## Decisions Covered

- D-06 (validator placement on `InstanceConfig`) ✓
- D-07 (narrow rule: only `apikey=`) ✓
- D-08 (exact error message text) ✓
