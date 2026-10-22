# Phase 83 — Negative demonstrations

All recipes are local; nothing is pushed (D-17). Constructed inputs live in the session scratchpad and are never presented as real reviews.

These recipes demonstrate REVIEW-03's negative case: a missing, failed, stale, wrong-commit, or unparseable Codex report is reported as **incomplete** with a specific, plain-language reason, never as clean (D-09, D-17). `tests/codex_report_status.py`'s `assess_report`/CLI are the only code under test; none of it was modified to produce these results.

Current head at Task 2 time (per the orchestrator's instruction to use the current HEAD at Task 2 time): `5d9a96fd623d28f1af1585685010fd162ea00e14` (Task 1's own checkpoint-record commit, one commit ahead of the explicit-review head `d501a68316b2c3a032634741f8c73d373870e9f2` reviewed in that record). Base (`git merge-base origin/main HEAD`, unchanged from Task 1): `6f3841aaae4f2511efe6796f7f5c7ad50b423f90`.

### Recipe 1: missing report

- **Input:** a path that was never created — no file was written at it. For the current head `5d9a96fd623d28f1af1585685010fd162ea00e14`.
- **Command run:**
  ```
  uv run python tests/codex_report_status.py --report <scratch>/does-not-exist.last.json \
    --exit-code 0 --expected-head 5d9a96fd623d28f1af1585685010fd162ea00e14 \
    --expected-base 6f3841aaae4f2511efe6796f7f5c7ad50b423f90 \
    --current-head 5d9a96fd623d28f1af1585685010fd162ea00e14 --attempt 1
  ```
- **Expected:** `status: incomplete`, reason `"missing report"`.
- **Observed checker JSON (verbatim):**
  ```json
  {"status": "incomplete", "reasons": ["missing report"], "qualified_ids": [], "finding_count": 0, "inspected_head": null, "inspected_base": null}
  ```
- **Exit code:** `1`
- **Evidence-record line:** `Codex: INCOMPLETE — missing report`

### Recipe 2: failed after one retry (D-09)

- **Input:** the real contract invocation (`docs/codex-adversarial-review-contract.md`, Invocation steps 1-6), run against a genuine detached worktree of the current head, with the contract's `timeout 1800` deliberately replaced by `timeout 5` so `codex exec` is killed well before it can write a report — this is the constructed part of the demonstration, everything else (worktree, prompt template, output-schema flag, checker) is the real, unmodified mechanism. Run twice on the same head, attempt 1 and attempt 2, each with its own fresh detached worktree and its own scratch output path (`<scratch>/recipe2-a1.*`, `<scratch>/recipe2-a2.*`).
- **Command run (attempt 1, same shape for attempt 2 with a fresh `$WT`/`$OUT` and `--attempt 2`):**
  ```
  git worktree add --detach "$WT" 5d9a96fd623d28f1af1585685010fd162ea00e14
  timeout 5 codex exec --sandbox read-only --ephemeral -C "$WT" \
    --output-schema <repo>/.claude/schemas/codex-review-findings.schema.json \
    --json -o "$OUT.last.json" - < prompt.txt > "$OUT.jsonl"
  git worktree remove --force "$WT"
  uv run python tests/codex_report_status.py --report "$OUT.last.json" --exit-code 124 \
    --expected-head 5d9a96fd623d28f1af1585685010fd162ea00e14 \
    --expected-base 6f3841aaae4f2511efe6796f7f5c7ad50b423f90 \
    --current-head 5d9a96fd623d28f1af1585685010fd162ea00e14 --attempt 1
  ```
- **Expected:** both attempts are killed by `timeout` before Codex can write a complete `.last.json`; the review stays incomplete on both; per the failure rule, after attempt 2 is also incomplete, Codex is recorded as INCOMPLETE/PENDING and the owner chooses: wait, retry later, or approve a fallback such as vibe-check.
- **Observed, attempt 1:** `codex exec` ran for 5.034s wall-clock and exited `124` (the `timeout` command's standard "killed by timeout" code). No `.last.json` was written. The `.jsonl` event stream captured 923 bytes: a `thread.started` event, two configuration-warning `item.completed` events (`[features].codex_hooks` deprecated; a `hooks.json` parse error), a `turn.started` event, and one in-progress `agent_message` ("I'll verify the checkout and base commit first, then review the full diff...") before the process was killed.
  Checker JSON (verbatim):
  ```json
  {"status": "incomplete", "reasons": ["codex exited 124", "missing report"], "qualified_ids": [], "finding_count": 0, "inspected_head": null, "inspected_base": null}
  ```
  Exit code: `1`.
- **Observed, attempt 2 (fresh worktree, same timeout):** `codex exec` ran for 5.028s and again exited `124`. No `.last.json` was written. The `.jsonl` stream captured 631 bytes of the same early startup events, killed before any substantive review content.
  Checker JSON (verbatim):
  ```json
  {"status": "incomplete", "reasons": ["codex exited 124", "missing report"], "qualified_ids": [], "finding_count": 0, "inspected_head": null, "inspected_base": null}
  ```
  Exit code: `1`.
- **Evidence-record line:** `Codex: INCOMPLETE/PENDING — codex exited 124; missing report (attempt 1); codex exited 124; missing report (attempt 2). Owner choice required: wait, retry later, or approve a fallback such as vibe-check (D-09).`
- Both worktrees (`recipe2-wt-a1`, `recipe2-wt-a2`) were removed with `git worktree remove --force` immediately after their attempt, before the next one started; `git worktree list` after both attempts shows neither — confirmed below under "Restored state."

### Recipe 3: stale report

- **Input:** Plan 07's real quick-task report, used byte-for-byte unmodified: `.planning/phases/83-paired-bm-codex-review-risk-based-depth/codex/a7995baf187e-quick-a1.last.json` (`inspected_head_sha: a7995baf187e0e96c3f8152212060cedfc7fd921`).
- **Command run:**
  ```
  uv run python tests/codex_report_status.py \
    --report .planning/phases/83-paired-bm-codex-review-risk-based-depth/codex/a7995baf187e-quick-a1.last.json \
    --exit-code 0 --expected-head a7995baf187e0e96c3f8152212060cedfc7fd921 \
    --expected-base 98c2dc68ff3bf6520bb7c3986140749d288d299f \
    --current-head 5d9a96fd623d28f1af1585685010fd162ea00e14 --attempt 1
  ```
- **Expected:** the report's inspected head matches `--expected-head` (both `a7995baf187e...`, so it is not flagged as the "wrong commit" it was requested for) but no longer matches `--current-head` (the real current repository head has since moved to `5d9a96fd623d...`), so it is reported `stale`.
- **Observed checker JSON (verbatim):**
  ```json
  {"status": "incomplete", "reasons": ["stale: report is for a7995baf187e, current head is 5d9a96fd623d"], "qualified_ids": [], "finding_count": 0, "inspected_head": "a7995baf187e0e96c3f8152212060cedfc7fd921", "inspected_base": "98c2dc68ff3bf6520bb7c3986140749d288d299f"}
  ```
- **Exit code:** `1`
- **Evidence-record line:** `Codex: INCOMPLETE — stale: report is for a7995baf187e, current head is 5d9a96fd623d`

### Recipe 4: wrong commit

- **Input:** a constructed copy of Task 1's real `d501a68316b2-explicit-a1.last.json`, with only `inspected_head_sha` replaced by `git rev-parse HEAD~1` (evaluated at Task 2 time, relative to the current head `5d9a96fd623d...`): that resolves to `d501a68316b2c3a032634741f8c73d373870e9f2` — the explicit-review head Task 1 actually reviewed, which is a different, genuinely real commit than the current head this recipe asks the checker to verify against. Every other field (including `inspected_base_sha` and the two real findings) was left untouched.
- **Command run:**
  ```
  uv run python tests/codex_report_status.py --report <scratch>/recipe4-wrong-commit.last.json \
    --exit-code 0 --expected-head 5d9a96fd623d28f1af1585685010fd162ea00e14 \
    --expected-base 6f3841aaae4f2511efe6796f7f5c7ad50b423f90 \
    --current-head 5d9a96fd623d28f1af1585685010fd162ea00e14 --attempt 1
  ```
- **Expected:** the mutated `inspected_head_sha` (`d501a68316b2...`) does not match `--expected-head` (`5d9a96fd623d...`, the head this recipe's review is actually requested for), so the checker reports `"wrong commit"` rather than `"stale"` (the checker's own branch order checks `inspected_head != expected_head` before `inspected_head != current_head`).
- **Observed checker JSON (verbatim):**
  ```json
  {"status": "incomplete", "reasons": ["wrong commit: report inspected d501a68316b2 but review was requested for 5d9a96fd623d"], "qualified_ids": ["codex:d501a68316b2:a1:F001", "codex:d501a68316b2:a1:F002"], "finding_count": 2, "inspected_head": "d501a68316b2c3a032634741f8c73d373870e9f2", "inspected_base": "6f3841aaae4f2511efe6796f7f5c7ad50b423f90"}
  ```
- **Exit code:** `1`
- **Evidence-record line:** `Codex: INCOMPLETE — wrong commit: report inspected d501a68316b2 but review was requested for 5d9a96fd623d`
- Even though the mutated report is otherwise well-formed and still carries its two real, reproduced findings (`finding_count: 2`, both qualified IDs listed), the overall `status` stays `incomplete` — a report with real findings does not buy its way past a commit-binding failure.

### Recipe 5: unparseable

- **Input:** a constructed copy of Task 1's real `d501a68316b2-explicit-a1.last.json` (16017 bytes), truncated with `head -c` to exactly half its byte length (8008 bytes), cutting the JSON document off mid-structure.
- **Command run:**
  ```
  uv run python tests/codex_report_status.py --report <scratch>/recipe5-truncated.last.json \
    --exit-code 0 --expected-head d501a68316b2c3a032634741f8c73d373870e9f2 \
    --expected-base 6f3841aaae4f2511efe6796f7f5c7ad50b423f90 \
    --current-head d501a68316b2c3a032634741f8c73d373870e9f2 --attempt 1
  ```
- **Expected:** `json.loads` raises `JSONDecodeError` on the truncated text, caught and reported as `"unparseable: report is not valid JSON"`.
- **Observed checker JSON (verbatim):**
  ```json
  {"status": "incomplete", "reasons": ["unparseable: report is not valid JSON"], "qualified_ids": [], "finding_count": 0, "inspected_head": null, "inspected_base": null}
  ```
- **Exit code:** `1`
- **Evidence-record line:** `Codex: INCOMPLETE — unparseable: report is not valid JSON`

### Recipe 6: pending request

- **Input:** none — this recipe has no report and runs no checker invocation. It demonstrates the evidence-record line itself for the case where BM cannot invoke Codex at all, or Codex has not yet returned anything, per `docs/review-checkpoint-record.md`'s Rules: "When BM cannot invoke Codex, or Codex has not yet returned a report, the record shows `Codex: PENDING, requested for FULL_SHA` until a report arrives (REVIEW-03)."
- **Command run:** none (not applicable).
- **Expected / observed record line:** `Codex: PENDING, requested for 5d9a96fd623d28f1af1585685010fd162ea00e14`
- A `PENDING` Codex line is one of the statuses the Rules section says is "never written as 'clean,' 'skipped and fine,' or any other status that could be read as complete." The "Owner acceptance checklist" template requires a `Codex: <status...>` line before that checklist is shown to the owner (D-12's manual BM/Codex completion check); a line reading `Codex: PENDING, requested for 5d9a96fd623d28f1af1585685010fd162ea00e14` cannot be read as reviewed or complete, so it blocks presenting the checkpoint as review-complete in that checklist until a real report (complete or INCOMPLETE-with-reasons) replaces it.

## Restored state

- **Scratch files deleted:** the session scratchpad directory holding every recipe's constructed input (the missing-report path that was never created for Recipe 1; both worktrees, prompt file, and `.jsonl` outputs for Recipe 2; the quick-task report was read in place, not copied, for Recipe 3; the mutated-head copy for Recipe 4; the truncated copy for Recipe 5) was removed in full (`rm -rf`) after every recipe's output above was captured verbatim. A subsequent `ls` on that path reports "No such file or directory."
- **`git status --short` shows no stray files:** empty output, immediately before this file's own commit.
- **No push performed:** `git ls-remote --heads origin paired-review` printed empty output both before Task 2 began and again after all six recipes — unchanged, still no remote branch for this phase's work.
- **Worktrees:** the two `recipe2-wt-a1`/`recipe2-wt-a2` detached worktrees created for Recipe 2 were each removed with `git worktree remove --force` immediately after their `codex exec` attempt; `git worktree list` afterward shows neither. The repository's pre-existing `.claude/worktrees/review-*` entries are unrelated to this plan (not created by it, present before Task 2 started) and were left untouched.
