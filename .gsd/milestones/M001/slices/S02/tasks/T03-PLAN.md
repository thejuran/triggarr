---
estimated_steps: 8
estimated_files: 5
skills_used: []
---

# T03: Retire stale TODO and reconcile supporting docs

Why: stale backlog notes caused this milestone; leaving them stale would recreate the problem for the next agent.

Do:
1. Update or remove the obsolete `TODO.md` entry claiming configurable config-dir support is missing.
2. If no pending TODOs remain, make that clear rather than leaving an empty ambiguous file.
3. Update `.gsd/DEFERRED-BACKLOG.md` if execution findings change the transition audit.
4. Check supporting docs for links/paths referenced by README.
5. Do not rewrite legacy `.gsd/PROJECT.md`, `.gsd/REQUIREMENTS.md`, `.gsd/DECISIONS.md`, `.gsd/QUEUE.md`, or `.gsd/STATE.md`.

Done when: project-local backlog docs do not point future agents at missing plans or already-shipped work.

## Inputs

- `T01 docs audit findings`
- `T02 README changes`
- `TODO.md`
- `.gsd/DEFERRED-BACKLOG.md`

## Expected Output

- `TODO.md`
- `.gsd/DEFERRED-BACKLOG.md`

## Verification

`! rg -n "mellow-tinkering-creek|Hardcoded `/config/` paths prevent running outside Docker|Fix: add `TRIGGARR_CONFIG_DIR`" TODO.md .gsd/DEFERRED-BACKLOG.md README.md`

## Observability Impact

Keeps backlog signals clean and prevents recurring false-positive planning work.
