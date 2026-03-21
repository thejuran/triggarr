---
allowed-tools: Bash(git diff:*), Bash(git status:*), Bash(git log:*), Bash(git blame:*), Bash(git show:*)
description: Quick code review for uncommitted local changes
---

Quick code review for uncommitted changes. Fast, focused on critical issues.

## Step 1: Gather Context (Haiku Agent)

Detect what needs to be reviewed:

```
1. Run `git status` and `git diff` / `git diff --staged`
2. If no changes → inform user and stop
3. Extract:
   - Files changed (list)
   - Languages detected (from extensions)
   - Line counts (additions/deletions)
   - Has CLAUDE.md? (root or in changed directories)
```

## Step 2: Load Agents (Progressive)

Only load agents relevant to detected context:

| Condition | Load Agent |
|-----------|------------|
| Always | `@agents/bugs.md` |
| Always | `@agents/security.md` |
| CLAUDE.md exists | `@agents/compliance.md` |
| `.ts/.tsx/.js/.jsx` files | `@agents/language-typescript.md` |
| `.py` files | `@agents/language-python.md` |

See `@agents/index.md` for full routing logic.

## Step 3: Run Review (Parallel Sonnet Agents)

Launch loaded agents in parallel. Each agent:
1. Reads full file context for changed files
2. Analyzes only the diff (not pre-existing code)
3. Returns structured issues with **diff-style fixes**

Output format per agent (see `@agents/bugs.md` for example):
```markdown
### 🐛 {{issue_title}}
**Location:** `{{file}}:{{line}}`
**Confidence:** {{score}}/100

**Problem:** {{reason}}

**Suggested Fix:**
```diff
- {{old_code}}
+ {{new_code}}
```
```

## Step 4: Score & Filter (Haiku Agents)

For each issue, score confidence 0-100:

| Factor | Points |
|--------|--------|
| In the diff (new code) | +20 |
| Would cause failure | +30 |
| In CLAUDE.md rules | +20 |
| Senior engineer would flag | +20 |
| Has ignore comment | -50 |

Apply filters from `@templates/false-positive-rules.md`:
- Filter issues with score < 80
- Track filtered count by reason

## Step 5: Present Results

Format output using `@templates/output-format.md`:

```
## Code Review

**Summary:** Reviewed X files, Y lines changed

| Found | Reported | Filtered |
|-------|----------|----------|
| total | ≥80 score | <80 score |

### Critical (95-100) 🔴
[Issues with diff-style fixes]

### Warning (80-94) 🟠  
[Issues with diff-style fixes]

### Filtered Issues 🔇
[Count by reason, expandable details]
```

## Output Rules

- **Always** include filtered issues summary (builds trust)
- **Always** use diff-style fixes (actionable)
- **Never** report pre-existing issues (not in diff)
- **Never** report linter territory (ESLint will catch)
- If no issues found, confirm code looks good for commit
