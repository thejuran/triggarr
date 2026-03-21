---
name: Python Issues
model: sonnet
applies_to: ["*.py"]
---

Language-specific checks for Python.

## Checks

### Type Safety
- Missing type hints on public function signatures
- `Any` type where specific type is known
- Incorrect Optional handling

### Common Pitfalls
- Mutable default arguments (`def foo(x=[])`)
- Bare `except:` clauses
- Using `is` for value comparison
- Missing `if __name__ == "__main__"`

### Resource Management
- Missing context managers for files
- Unclosed connections/cursors
- Missing finally blocks

### Performance
- String concatenation in loops (use join)
- Repeated dictionary lookups
- Loading large files into memory

## Output

For each issue, return:
- `file`: File path
- `line`: Line number
- `issue`: Brief description
- `fix`: Suggested fix with code

