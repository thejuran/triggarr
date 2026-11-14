# Routine vibe-check: main-CI fix, passes 2 and 3 (heads e18d1ed8bbb4 and 8e3d6b49f6b5)

Continues `49403734406a-mainfix-routine.md` (pass 1). Same command (`/vibe-check:deep-review`, stock) and state file; each pass reviews the changes since the previous pass's head. Run 2026-11-13.

## Pass 2: head e18d1ed8bbb492c15b2d1b5a34384e697b7659ff (not pushed)

- Reviewed: `49403734406a..e18d1ed8bbb4`, the Dockerfile step that upgrades `zlib1g` (9 lines).
- Lanes run (5): bugs, security, architecture, impact, compliance. test-sufficiency not run (coverage has no rows for the changed file). Codex lane inside vibe-check skipped (`unauthenticated`).
- Coverage evidence: exact-head local coverage, provenance `check` passed.
- Result: found 3, reported 1, filtered 2 (both absorbed into the reported row, same site).
- **Warning (score 90), `Dockerfile:51`**: "zlib1g security upgrade is unpinned, unlike every other dependency in this image" (compliance; bugs and architecture at the same site). The step took whatever version the mirror served and never checked the result, so a build could keep the vulnerable package while the comment said it was patched.
  - Absorbed: bugs, "upgrade step succeeds silently when the fixed version is not available".
  - Absorbed: architecture, "in-image apt upgrade adds an OS-scan fix route that the documented policy does not list".
- Triage: confirmed defect (BM IN-01 on the same head says the same). Fixed in one batched revision, `8e3d6b4`.

## Pass 3: head 8e3d6b49f6b5a923d7ee7202c3d5e56f7ec233dc

- Reviewed: `e18d1ed8bbb4..8e3d6b49f6b5`, the build-time version check in the Dockerfile and the naive `now()` in the test clock (12 lines, 2 files).
- Lanes run (6): bugs, security, architecture, impact, compliance, language-python. test-sufficiency not run (same reason). Codex lane inside vibe-check skipped (`unauthenticated`).
- Coverage evidence: exact-head local coverage, provenance `check` passed.
- Result: found 1, reported 0, filtered 1; 2 resolved on recheck.
- Resolved on recheck (by the lanes that raised them, against the code at this head):
  - compliance: the unpinned-upgrade warning. The version check now fails the build if the fixed package is not installed.
  - bugs: the silent-success note. Same fix.
- Still applies, below the reporting threshold: architecture's note that `docs/os-scan-policy.md` names two responses to a red scan (base-image rebuild, owner-approved exception) and this change uses a third. The document is unchanged; this is the owner's policy call.
- No new findings from any lane.
- Git-safety comparison: repository unchanged on both passes; a few agent commands were refused by the guard (command substitution, heredocs).

Across the three passes the whole PR diff (`b80c3e26cf94..8e3d6b49f6b5`) was reviewed except `uv.lock`, which pass 1's triage set aside as a lockfile.
