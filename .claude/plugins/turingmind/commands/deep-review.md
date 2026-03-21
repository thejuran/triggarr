---
allowed-tools: Bash(git diff:*), Bash(git status:*), Bash(git log:*), Bash(git blame:*), Bash(git show:*), Read, Grep, Glob, LS
description: Deep comprehensive code review with full context analysis
---

Comprehensive code review with full context analysis. Includes architecture review, test coverage, and impact analysis.

## Phase 1: Gather Context (3 Parallel Haiku Agents)

**Agent 1A - Change Summary:**
```
1. Run `git status`, `git diff`, `git diff --staged`
2. If no changes → inform user and stop
3. Extract:
   - Files changed (list)
   - Languages detected (from extensions)
   - Line counts (additions/deletions)
```

**Agent 1B - Project Context:**
```
1. Find CLAUDE.md (root + directories with changes)
2. Read dependency files:
   - package.json / requirements.txt / go.mod / Cargo.toml
3. Identify project type and framework
```

**Agent 1C - Related Files:**
```
For each modified file, find:
- Files that import the modified file
- Files that the modified file imports
- Test files (foo.ts → foo.test.ts)
```

## Phase 2: Load Agents (Progressive)

Only load agents relevant to detected context:

| Condition | Load Agent |
|-----------|------------|
| Always | `@agents/bugs.md` |
| Always | `@agents/security.md` |
| Always (deep) | `@agents/architecture.md` |
| CLAUDE.md exists | `@agents/compliance.md` |
| `.ts/.tsx/.js/.jsx` files | `@agents/language-typescript.md` |
| `.py` files | `@agents/language-python.md` |

See `@agents/index.md` for full routing logic.

## Phase 3: Deep Analysis (Parallel Sonnet Agents)

Launch loaded agents in parallel. Each agent:
1. Reads full file context + related files from Phase 1C
2. Analyzes only the diff (not pre-existing code)
3. Returns structured issues with **diff-style fixes**

**Core Agents (always):**
- `@agents/bugs.md` - Logic errors, null access, race conditions
- `@agents/security.md` - OWASP Top 10, injection, XSS, secrets
- `@agents/architecture.md` - Patterns, coupling, dependencies

**Conditional Agents:**
- `@agents/compliance.md` - If CLAUDE.md exists
- `@agents/language-typescript.md` - If TS/JS files
- `@agents/language-python.md` - If Python files

**Additional Deep Analysis:**
- **Tests & Documentation Agent:**
  - Do test files exist for modified code?
  - Do tests need updating for this change?
  - Are new public APIs missing tests?
  - Do README/docs need updates?

## Phase 4: Impact Analysis (Sonnet Agent)

Using Phase 1C results, analyze:
- What other parts of codebase could be affected?
- Are there breaking changes to public APIs?
- Could this affect performance at scale?
- Are there database/schema implications?
- What's the blast radius if this has a bug?

## Phase 5: Score & Filter (Haiku Agents)

For each issue, score confidence 0-100:

| Factor | Points |
|--------|--------|
| In the diff (new code) | +20 |
| Would cause failure | +30 |
| In CLAUDE.md rules | +20 |
| Senior engineer would flag | +20 |
| Has ignore comment | -50 |

Apply filters from `@templates/false-positive-rules.md`:
- Filter issues with score < 70 (lower threshold for deep review)
- Track filtered count by reason

## Phase 6: Present Results

Format output using `@templates/output-format.md`:

```
## Deep Code Review

**Summary:** Reviewed X files, Y lines changed

| Found | Reported | Filtered |
|-------|----------|----------|
| total | ≥70 score | <70 score |

### Critical (95-100) 🔴
[Issues with diff-style fixes]

### Warning (80-94) 🟠  
[Issues with diff-style fixes]

### Medium (70-79) 🟡
[Issues with diff-style fixes]

### Filtered Issues 🔇
[Count by reason, expandable details]

### Architectural Notes 📐
- Pattern consistency: ✅/⚠️/❌
- Test coverage: ✅/⚠️/❌
- Documentation: ✅/⚠️/❌
- Dependencies: ✅/⚠️/❌

### Impact Analysis 💥
- Affected files: [list]
- Blast radius: [scope]
- Breaking changes: [yes/no]
```

## Differences from Quick Review

| Aspect | Quick Review | Deep Review |
|--------|--------------|-------------|
| Threshold | ≥80 | ≥70 |
| Architecture | ❌ | ✅ |
| Impact Analysis | ❌ | ✅ |
| Test Coverage | ❌ | ✅ |
| Related Files | ❌ | ✅ |
| Medium Priority | ❌ | ✅ |
