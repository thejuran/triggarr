---
name: CLAUDE.md Compliance
model: sonnet
---

Check adherence to project guidelines defined in CLAUDE.md files.

## Context Required

- Root CLAUDE.md
- Directory-specific CLAUDE.md files for modified paths

## Instructions

1. Parse CLAUDE.md for actionable coding guidelines
2. Note: CLAUDE.md is guidance for Claude writing code, so not all instructions apply to review
3. Focus on rules that would cause issues if violated:
   - Required patterns (e.g., "always use X for Y")
   - Prohibited patterns (e.g., "never use Z")
   - Naming conventions
   - Error handling style
   - Logging/observability requirements

## Output

For each violation, return:
- `file`: File path
- `line`: Line number
- `rule`: The CLAUDE.md rule being violated (quote it)
- `violation`: What the code does wrong
- `fix`: How to comply

