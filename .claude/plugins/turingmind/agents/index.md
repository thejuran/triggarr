---
name: Agent Router
description: Routes to appropriate agents based on detected context
---

# Agent Router

This file helps select the right agents based on the code being reviewed.
Only load agents that are relevant to reduce context and improve accuracy.

## Agent Selection Matrix

| Detected | Load Agents |
|----------|-------------|
| Any code | `@agents/bugs.md`, `@agents/security.md` |
| Has CLAUDE.md | `@agents/compliance.md` |
| TypeScript/JavaScript | `@agents/language-typescript.md` |
| Python | `@agents/language-python.md` |
| Deep review mode | `@agents/architecture.md` |

## Core Agents (Always Load)

These agents apply to all code reviews:

1. **`bugs.md`** - Logic errors, null access, race conditions
2. **`security.md`** - OWASP Top 10, injection, XSS, secrets

## Conditional Agents (Load When Relevant)

### Compliance Agent
Load when: `CLAUDE.md` exists in project root or modified directories

```
@agents/compliance.md
```

### Language Agents
Load based on file extensions detected in diff:

| Extensions | Agent |
|------------|-------|
| `.ts`, `.tsx`, `.js`, `.jsx`, `.mjs` | `@agents/language-typescript.md` |
| `.py` | `@agents/language-python.md` |

### Architecture Agent
Load when: Deep review mode (`/turingmind-code-review:deep-review`)

```
@agents/architecture.md
```

## Progressive Loading Pattern

```
Step 1: Detect languages from git diff
        └─ Extract file extensions from changed files

Step 2: Check for CLAUDE.md
        └─ Look in root and directories with changes

Step 3: Load minimum required agents
        └─ Core: bugs + security (always)
        └─ Language: based on Step 1
        └─ Compliance: if Step 2 found CLAUDE.md
        └─ Architecture: only for deep review

Step 4: Run agents in parallel
        └─ Each agent returns structured issues

Step 5: Score and filter
        └─ Apply confidence scoring
        └─ Filter based on threshold
```

## Why Progressive Loading?

| Approach | Context Size | Accuracy |
|----------|--------------|----------|
| Load all agents | Large | Lower (noise) |
| Progressive load | Minimal | Higher (focused) |

By only loading relevant agents:
- Faster reviews (less to process)
- Fewer false positives (no irrelevant checks)
- Better fixes (language-specific suggestions)

## Adding New Agents

To add support for a new language or framework:

1. Create `agents/language-{name}.md` or `agents/framework-{name}.md`
2. Add entry to the selection matrix above
3. Update `commands/review.md` Step 3 with detection logic

Template for new language agent:
```markdown
---
name: {Language} Issues
model: sonnet
applies_to: ["*.ext"]
---

Language-specific checks for {Language}.

## Checks
- [Check 1]
- [Check 2]

## Output Format
(Use same format as bugs.md with diff-style fixes)
```

