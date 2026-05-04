---
estimated_steps: 8
estimated_files: 3
skills_used: []
---

# T03: Run user docs review gate before UAT

Why: documentation changes need human judgment, and project preference requires prompting the user to run deep review before UAT when completing a slice.

Do:
1. Summarize the doc/runtime diff for the user.
2. Prompt the user to review the documentation changes.
3. Prompt the user to run deep review externally before UAT using the current milestone/slice context, e.g. `/deep-review on branch <current-branch> against main`, and wait for their results.
4. Incorporate any user/deep-review feedback before UAT completion.
5. Record accepted feedback and remaining caveats.

Done when: user documentation review is complete, deep-review results if provided are handled, and there are no unresolved release-blocking docs/runtime issues.

## Inputs

- `S03/T02 verification evidence`
- `README.md`
- `TODO.md`

## Expected Output

- `M001/S03/T03 summary with user review/deep-review outcome`
- `M001/S03 UAT artifact during completion`

## Verification

Manual review gate — user confirms README/docs changes are acceptable and any requested deep-review findings are resolved before slice completion.

## Observability Impact

Preserves human review feedback and release-readiness caveats for future agents.
