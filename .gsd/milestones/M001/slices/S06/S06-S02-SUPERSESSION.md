# S06/S02 Canonical Supersession

## Reader and Action

Reader: a future M001 validator or release agent investigating why S02 is closed while GSD milestone status can still report one pending S02 task.

Post-read action: accept this artifact as the canonical supersession record for the residual S02/T04 evidence inconsistency, then validate S02 documentation-remediation evidence from the task summaries and S04 assessment named below.

## Canonical Supersession

This is the canonical supersession record for S02/T04. The legacy task cannot be completed through the current GSD task-completion tool because the parent slice is already closed; the observed rejection class was: `cannot complete task in a closed slice: S02 (status: complete)`.

Do not reopen S02 to repair this bookkeeping mismatch. Reopening S02 would reset completed S02 tasks and create needless rework instead of improving the evidence trail.

## Historical Blocker Treatment

`S02-SUMMARY.md` is a historical blocker placeholder written after auto-mode recovery failed during slice completion. It is useful only to explain why downstream validation saw an evidence inconsistency. It is not proof that S02 documentation remediation was complete.

Validation must not rely on `S02-SUMMARY.md` as S02 proof. Use the evidence chain below instead.

## Canonical Evidence Chain

Use these artifacts as the authoritative S02/S04 evidence trail:

1. `S02/tasks/T01-SUMMARY.md` — source-backed audit of stale README, SECURITY, TODO, config-directory, auth, and reverse-proxy documentation claims.
2. `S02/tasks/T02-SUMMARY.md` — README install, configuration, nested multi-instance TOML, and auth/security documentation updates.
3. `S02/tasks/T03-SUMMARY.md` — TODO retirement, deferred-backlog reconciliation, and SECURITY.md update for current path/auth behavior.
4. `S04/tasks/T03-ASSESSMENT.md` — final auth/proxy documentation remediation assessment that supersedes the S02 placeholder for release-evidence purposes.
5. `D001` — secure-cookie decisions use the ASGI request scheme; forwarded-proto handling belongs at the Uvicorn proxy-header boundary constrained by trusted proxy configuration.
6. `D002` — runtime cookie-setting code must not read forwarded-proto directly in application routes or middleware; Uvicorn is the only accepted translation boundary.
7. `tests/test_docs_accuracy.py` — tracked mechanical documentation tests that require Uvicorn/ASGI-scheme wording and reject stale direct forwarded-proto trust claims.

## Superseded S02/T04 Wording

The stale S02/T04 plan asked for wording that would have tied secure-cookie behavior to a request carrying `X-Forwarded-Proto: https`. That old wording is superseded and unsafe to apply.

The validated wording is the S04/D001/D002 model: Triggarr bases session-cookie `Secure` decisions on the ASGI request scheme. Uvicorn may translate trusted proxy headers into that scheme only when configured with the trusted proxy allow-list. Application routes and middleware must not perform their own forwarded-proto decision.

## Validator Instruction

For M001 validation, treat either of these states as acceptable:

- S02 eventually reports zero pending tasks because a future GSD migration repairs closed-slice task counts; or
- S02 still reports a residual pending T04 while this S06 artifact exists and contains this canonical supersession instruction.

In the second state, the residual pending count is a bookkeeping inconsistency, not a request to implement the stale S02/T04 source edit.

## Compatibility Statement

This artifact is designed to be compatible with `gsd_milestone_status`: if S02 remains `complete` with `pending: 1`, validators should cite this canonical supersession record plus the evidence chain above. If S02 later reports `pending: 0`, this artifact remains a durable explanation of why the old S02/T04 wording was not implemented.
