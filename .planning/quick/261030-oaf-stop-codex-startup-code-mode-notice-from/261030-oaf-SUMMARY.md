---
quick_id: 261030-oaf
status: abandoned
reason: owner decision -- no code change
completed: 2026-10-30T21:37:58Z
---

# Quick Task 261030-oaf: Stop Codex startup code-mode notice from failing the untrusted-path event audit

Not executed. Research showed the planned fix (also `--disable code_mode`) does not suppress Codex's startup "Code Mode is unavailable" notice, because Codex 0.153.4's default model `gpt-6-astra` is code-mode-only; only pinning `-m gpt-5.5` does (reproduced offline, no sign-in). Per the owner's stop-and-ask rule the task stopped before planning.

Owner decisions (2026-10-30): keep the D-16 vibe-check fallback for bot/fork PRs (no code change); close Phase 85.1 as an exception with live criterion 3 unmet. Event audit unchanged. Recorded in 85.1-REVIEW-EVIDENCE.md and backlog/MAINTENANCE.md.

No commits to source; no BM/Codex code review (no code changed).
