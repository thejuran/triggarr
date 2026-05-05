# BLOCKER — auto-mode recovery failed

Unit `complete-slice` for `M001/S02` failed to produce this artifact after idle recovery exhausted all retries.

**Reason**: Deterministic policy rejection for complete-slice "M001/S02": edit: HARD BLOCK: unit "complete-slice" runs under tools-policy "planning-dispatch" — cannot edit "README.md" — writes are restricted to .gsd/. This is a mechanical gate enforced by manifest.tools (#4934). You MUST NOT proceed, retry the same call, or rationalize past this block. If you need to write user source, the work belongs in execute-task, not in a planning unit.. Retrying cannot resolve this gate — writing blocker placeholder to advance pipeline.

This placeholder was written by auto-mode so the pipeline can advance.
Review and replace this file before relying on downstream artifacts.