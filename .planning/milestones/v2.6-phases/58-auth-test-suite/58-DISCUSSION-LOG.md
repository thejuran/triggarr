# Phase 58: Auth Test Suite - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md -- this log preserves the alternatives considered.

**Date:** 2026-04-15
**Phase:** 58-auth-test-suite
**Areas discussed:** Test organization, Coverage gap strategy, Edge case depth, Auth mode switching

---

## Test Organization

| Option | Description | Selected |
|--------|-------------|----------|
| Gap-fill existing files (Recommended) | Add missing tests into 4 existing files + one new integration file | :heavy_check_mark: |
| Single new file | Create one test_auth_suite.py covering all 5 success criteria | |
| One file per success criterion | Create 5 new files mapping 1:1 to success criteria | |

**User's choice:** Gap-fill existing files
**Notes:** Keeps tests co-located with verified code. New test_auth_integration.py for cross-cutting flows only.

---

## Coverage Gap Strategy

| Option | Description | Selected |
|--------|-------------|----------|
| Audit-then-fill (Recommended) | Map existing tests to success criteria, write only for gaps | :heavy_check_mark: |
| Clean-slate per criterion | Write all tests fresh, ignoring existing coverage | |
| You decide | Claude picks based on existing test analysis | |

**User's choice:** Audit-then-fill
**Notes:** None

### Follow-up: Traceability

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, comment block per file | Add docstring mapping tests to SC-1 through SC-5 | :heavy_check_mark: |
| No, tests are self-documenting | Test names and docstrings are enough | |

**User's choice:** Yes, comment block per file
**Notes:** None

---

## Edge Case Depth

| Option | Description | Selected |
|--------|-------------|----------|
| Security-focused edges (Recommended) | Expired/tampered cookies, malformed headers, invalid API keys, open redirects, setup-after-config | :heavy_check_mark: |
| Exhaustive edge cases | Everything including concurrent races, partial corruption, every malformed variant | |
| Minimal -- happy + unhappy only | Valid pass, invalid fail, missing redirect | |

**User's choice:** Security-focused edges
**Notes:** None

### Follow-up: Session Secret Mismatch

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, test secret mismatch | Verify cookie signed with different secret is rejected | :heavy_check_mark: |
| You decide | Claude judges based on existing itsdangerous tests | |

**User's choice:** Yes, test secret mismatch
**Notes:** Simulates secret rotation or config tampering scenario.

---

## Auth Mode Switching

| Option | Description | Selected |
|--------|-------------|----------|
| Isolated + key transitions (Recommended) | Each mode in isolation + 2-3 key transitions (Forms->Basic, any->Disabled, Disabled->Forms) | :heavy_check_mark: |
| Isolated only | Each mode tested alone, no transitions | |
| Full permutation matrix | All 4x4 mode transitions | |

**User's choice:** Isolated + key transitions
**Notes:** None

### Follow-up: Disabled Mode Warning

| Option | Description | Selected |
|--------|-------------|----------|
| Passthrough + warning exists | Verify passthrough AND startup warning log fires (not 60s timing) | :heavy_check_mark: |
| Passthrough only | Only verify requests pass through | |
| You decide | Claude checks existing coverage | |

**User's choice:** Passthrough + warning exists
**Notes:** None

---

## Claude's Discretion

- Test helper/fixture structure
- Exact test names and grouping
- Whether to use parametrize for mode-specific tests
- Integration test flow structure

## Deferred Ideas

None -- discussion stayed within phase scope.
