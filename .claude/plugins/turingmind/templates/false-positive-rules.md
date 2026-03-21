---
name: False Positive Filtering Rules
---

## False Positive Filtering

Use these rules to filter out issues that should not be reported.

### Always Filter Out

1. **Pre-existing Issues**
   - Issue exists in lines not modified by this diff
   - Use `git blame` to verify if uncertain

2. **Linter/Compiler Territory**
   - Syntax errors
   - Type mismatches (TypeScript will catch)
   - Unused variables
   - Import ordering

3. **Pedantic Nitpicks**
   - Would a senior engineer call this out in code review?
   - Is this actionable, or just "could be better"?

4. **Silenced Issues**
   - `// eslint-disable-next-line`
   - `# noqa`
   - `// nolint`
   - `#[allow(...)]`
   - `@SuppressWarnings`

5. **Intentional Changes**
   - Functionality changes that appear deliberate
   - Style changes matching existing codebase patterns

6. **Style Not in CLAUDE.md**
   - General style preferences not explicitly required
   - Formatting issues (prettier/black will handle)

### Confidence Scoring Guide

| Score | Meaning | Quick Review | Deep Review |
|-------|---------|--------------|-------------|
| 0-25 | False positive or pre-existing | Filter out | Filter out |
| 26-50 | Nitpick or rare edge case | Filter out | Filter out |
| 51-69 | Real but minor | Filter out | Filter out |
| 70-79 | Real, will likely happen | Filter out | Include as Medium |
| 80-94 | High confidence, impacts users | Include as Warning | Include as High |
| 95-100 | Certain, will cause failures | Include as Critical | Include as Critical |

### Scoring Criteria

When scoring an issue, consider:

1. **Is this new?**
   - In the diff: +20 points
   - Pre-existing: -50 points

2. **Would it cause failures?**
   - Definitely: +30 points
   - Likely: +20 points
   - Possibly: +10 points
   - Unlikely: +0 points

3. **Is it in CLAUDE.md?**
   - Explicitly required: +20 points
   - Not mentioned: +0 points

4. **Would a senior engineer flag it?**
   - Yes, immediately: +20 points
   - Maybe: +10 points
   - No: -20 points

5. **Is it silenced?**
   - Has ignore comment: -50 points

