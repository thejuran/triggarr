# M001/S05 — Research

**Date:** 2026-05-05

## Summary

S05 is a release-gate/documentation-UAT slice, not a new implementation slice. All code/docs remediation work from S04 is already in place: `README.md`, `SECURITY.md`, and `TODO.md` now describe the portable config directory, nested multi-instance TOML, current authentication modes, External-auth trust boundary, ASGI/Uvicorn secure-cookie behavior, and retired configurable-config TODO. A quick research verification of `uv run pytest tests/test_docs_accuracy.py -q` passed with `4 passed in 0.01s` (`.gsd/exec/a113302a-d2b6-48bd-b0c8-63f177d0da2f.stdout`).

There are no Active requirements for S05 to transition. S05 supports milestone-level acceptance: a real human documentation review, an explicit release/deep-review decision, and final validation evidence before milestone completion. Prior artifacts already warn that S03/S04 used agent-side review surrogates only; S05 must not repeat that as if it were human UAT.

The main planner concern is gate honesty. If the executor can reach the user, it should present a concise review packet and collect approval/change/defer decisions with `ask_user_questions`. If it cannot get a human response, it should record the release gate as unresolved or explicitly deferred by the user; it must not mark “human reviewed” based only on agent-side scans.

## Recommendation

Plan S05 as three thin tasks:

1. **Prepare a review packet** for README/SECURITY/TODO, using a stable committed diff range and a cold-reader checklist. This should be a durable artifact under the S05 slice, not a huge chat dump.
2. **Collect the human/release-gate decision**: docs approved vs changes requested vs deferred, plus `/deep-review` run-now vs defer. If the user asks for changes, replan/patch docs and rerun docs guardrails before proceeding.
3. **Run final mechanical verification and close the slice** only after the gate outcome is recorded. Fresh verification should include docs accuracy, config-dir/startup/state regressions, full pytest, and ruff.

Use the installed `write-docs` skill’s reader-test principle: name the reader and post-read action, cold-read the docs against that action, and do not ship docs that have not passed a reader-test. For this slice, the reader is an operator installing/upgrading Triggarr; the post-read action is: configure Docker or standalone runtime paths and choose a safe auth/proxy mode without being misled by stale claims.

## Implementation Landscape

### Key Files

- `README.md` — Primary user-facing documentation. Relevant current sections: Docker install and `/config` default (around lines 44–75), standalone `TRIGGARR_CONFIG_DIR` flow (around lines 77–113), nested multi-instance TOML example (around lines 115–181), Security Model/auth modes (around lines 183–216), reverse-proxy `TRUSTED_PROXY_IPS`/`ROOT_PATH` guidance (around lines 216–257), Synology note (around lines 259–263).
- `SECURITY.md` — Security-policy version of the operator contract. Relevant current sections: auth/access control, session-cookie ASGI scheme behavior, API-key handling, SecretStr/log redaction, runtime paths, container hardening, deployment recommendations.
- `TODO.md` — Now a short “no pending TODOs” note with the old configurable config-directory item retired. Human review should confirm this is acceptable instead of maintaining a backlog file.
- `tests/test_docs_accuracy.py` — Guardrail tests for External-auth upstream-auth/authz wording, secure-cookie ASGI/Uvicorn/proxy wording, stale auth/config-dir claims, and README TOML examples validated through `Settings.model_validate(...)`.
- `.gsd/milestones/M001/slices/S03/S03-UAT.md` — Important caveat source: explicitly says S03 did not perform human docs review or `/deep-review`.
- `.gsd/milestones/M001/slices/S04/S04-UAT.md` — Important caveat source: explicitly assigns human readability/release deep-review acceptance to S05.
- `.gsd/milestones/M001/slices/S04/tasks/T03-ASSESSMENT.md` — Evidence repair/supersession artifact for the stale S02 placeholder summary; downstream validation should cite it if evidence provenance comes up.
- `.gsd/exec/22f64ec5-b4cc-4d9f-8385-8c18c3208b80.stdout` — Research output comparing candidate documentation diff ranges for human review.
- `.gsd/exec/141814d6-7346-41fd-a482-75ff24bcdfc4.stdout` — Research output summarizing current high-risk README/SECURITY/TODO/doc-test lines.

### Review Diff Base

Use `a3f09ad^..HEAD` for the full milestone documentation review packet:

```bash
git diff --stat a3f09ad^..HEAD -- README.md SECURITY.md TODO.md
git diff a3f09ad^..HEAD -- README.md SECURITY.md TODO.md
```

Research found that range covers the docs milestone changes across README/SECURITY/TODO: `115 insertions(+), 68 deletions(-)` over 3 files. It includes the portable config-dir docs, nested TOML replacement for flat examples, auth/security rewrite, TODO retirement, and S04 trust-boundary tightening.

If the user wants only the remediation delta after earlier docs work, `40d7baa^..HEAD` is the narrower range (`39 insertions(+), 18 deletions(-)`), and `ea9826a^..HEAD` is only the final External-auth/secure-cookie wording polish (`6 insertions(+), 6 deletions(-)`). For S05 acceptance, prefer the broader `a3f09ad^..HEAD` range.

### Build Order

1. **Review packet first** — Create a concise artifact/checklist that points the human to the exact diff range, summarizes changed claims, and lists approval criteria. Do not rerun full tests before the user has had a chance to request wording changes.
2. **Human gate second** — Ask one or two concrete questions via `ask_user_questions` if interactive prompting is available:
   - Documentation decision: approve, request changes, or defer/no approval.
   - Release/deep-review decision: run `/deep-review` now, defer because no push/tag is happening, or stop.
3. **Corrections or final verification third** — If changes are requested, edit docs and rerun `tests/test_docs_accuracy.py`. If approved/deferred, run the final mechanical suite and record exactly what was and was not proven.

### Verification Approach

Minimum fresh commands for S05 closure:

```bash
uv run pytest tests/test_docs_accuracy.py -q
uv run pytest tests/test_config_dir.py tests/test_state.py tests/test_startup.py tests/test_docs_accuracy.py -q
uv run pytest tests/ -x -q
uv run ruff check triggarr/ tests/
```

Optional mechanical stale-claim scan used during research and suitable for the review packet:

```bash
git grep -n -i -E 'no authentication|authentication is not implemented|config directory is not configurable|make config directory configurable|flat \[radarr\]|\[radarr\][[:space:]]*$|TRIGGARR_GENERAL__|directly trusts.*x-forwarded-proto|routes trust.*x-forwarded-proto' -- README.md SECURITY.md TODO.md CONTRIBUTING.md docs 2>/dev/null || true
```

Research run result: no matches in the tracked stale-claim scan (`.gsd/exec/b0670ec1-49e9-420d-ae22-51c3c85db840.stdout`). Treat this as scout evidence only; closure still needs fresh output.

## Constraints

- Project convention says: before pushing to main or creating a release tag, offer `/deep-review` to the user. S05 should resolve this explicitly. Since the milestone scope excludes publishing/tagging/pushing, a user-approved deferral is acceptable only if recorded as such; do not silently skip it.
- Do not ask the user to edit files manually. If docs changes are requested, the executor should make them and rerun guardrails.
- Do not expose real API keys or generated auth secrets in review artifacts. Current docs use placeholders such as `<radarr-api-key>` and state that setup creates secrets.
- `S02-SUMMARY.md` is known unreliable/placeholder. Use S02 task summaries plus S04 `T03-ASSESSMENT.md` for evidence provenance if needed.
- If no human response is available in auto-mode, the honest outcome is “human review unresolved/deferred,” not “passed.”

## Common Pitfalls

- **Claiming human UAT from agent scans** — S03 and S04 already did agent-side surrogates and left human review to S05. S05 must collect human input or clearly record deferral.
- **Using an empty `git diff`** — README/SECURITY/TODO changes are already committed on `main`, so plain `git diff -- README.md SECURITY.md TODO.md` is empty. Use a committed range such as `a3f09ad^..HEAD`.
- **Over-broad deep-review scope** — `/deep-review` is a release/push gate, not necessarily required to finish a no-push docs-UAT slice. Ask the user whether to run or defer, and document the answer.
- **Mutating docs after approval without rerunning the gate** — If any README/SECURITY/TODO edits happen after the human approves, rerun `tests/test_docs_accuracy.py` and recollect/refresh the approval note.

## Open Risks

- Human review may request wording changes, especially around `External` auth, `TRUSTED_PROXY_IPS`, TODO file strategy, or whether docs should mention no live reverse-proxy proof. Plan for a rework path instead of assuming approval.
- The available skills list does not include a literal `deep-review` skill. If the user asks to run `/deep-review`, use the project’s actual slash command if available in the harness; otherwise fall back to the installed code-review/security/test skills only after telling the user the exact `/deep-review` skill is unavailable.

## Skills Discovered

| Technology / Work Type | Skill | Status |
|---|---|---|
| Documentation / reader-test workflow | `write-docs` | Installed and used for S05 research guidance |
| Code review / deep review surrogate | `turingmind-code-review`, `review`, `security-review`, `test` | Installed; useful only if `/deep-review` is requested/unavailable |

No external technology-specific skill search was needed: this slice is repository documentation/UAT gating, not work against a third-party API or unfamiliar framework.
