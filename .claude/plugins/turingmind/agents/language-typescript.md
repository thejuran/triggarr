---
name: TypeScript/JavaScript Issues
model: sonnet
applies_to: ["*.ts", "*.tsx", "*.js", "*.jsx", "*.mjs", "*.cjs"]
---

Language-specific checks for TypeScript and JavaScript.

## Checks

### Type Safety
- Implicit `any` types
- Type assertions without validation (`as Type`)
- Missing null checks before property access
- Non-null assertions (`!`) without justification

### Async/Await
- Missing try-catch around await
- Unhandled promise rejections
- Floating promises (missing await)
- async function without await

### Common Pitfalls
- `==` instead of `===` for non-null checks
- Mutable default parameters
- Modifying objects during iteration
- Missing dependency arrays in hooks

### Performance
- Creating functions/objects in render
- Missing memoization for expensive computations
- N+1 queries in loops

## Output

For each issue, return:
- `file`: File path
- `line`: Line number
- `issue`: Brief description
- `fix`: Suggested fix with code

