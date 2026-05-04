# Knowledge Register

Append-only project-specific rules, patterns, and lessons learned that future agents should preserve.

## 2026-05-03 — GSD structure transition

- The existing root-level `.gsd/PROJECT.md`, `.gsd/REQUIREMENTS.md`, `.gsd/DECISIONS.md`, `.gsd/QUEUE.md`, and `.gsd/STATE.md` are historical GSD v1 artifacts and should remain in place for continuity.
- New planning work should use the current GSD structure going forward: `.gsd/milestones/M###/`, slice directories under `slices/S##/`, and task files under `tasks/T##-*`.
- Do not migrate or rewrite historical v1 milestone/requirement/decision content unless the user explicitly requests a migration; reference it as project history and capability context.
