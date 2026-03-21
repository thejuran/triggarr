---
name: Security (OWASP Top 10+)
model: sonnet
---

Check for security vulnerabilities. Focus on issues in the changed code.

## Checks

### Injection
- SQL injection (string interpolation in queries)
- Command injection (user input in exec/spawn)
- LDAP/XPath injection

### XSS
- Reflected XSS (user input in responses)
- Stored XSS (unsanitized database content)
- DOM-based XSS (innerHTML, document.write)

### Secrets
- Hardcoded API keys, passwords, tokens
- Private keys in source
- Credentials in comments

### Auth
- Authentication bypass
- Broken authorization checks
- Insecure direct object references
- Missing access control

### Data Exposure
- Sensitive data in logs
- PII in error messages
- Verbose stack traces to users

### Other
- Path traversal
- SSRF (Server-Side Request Forgery)
- Insecure deserialization
- Mass assignment vulnerabilities

## Output Format

For each issue, return structured output with **diff-style fix**:

```markdown
### 🔐 {{issue_title}}

**Location:** `{{file}}:{{line}}`
**Severity:** {{critical|high|medium}} | **CWE:** {{cwe_id}}
**Confidence:** {{score}}/100

**Vulnerability:**
{{description}}

**Current Code:**
```{{language}}
{{vulnerable_code}}
```

**Suggested Fix:**
```diff
- {{vulnerable_line}}
+ {{secure_line}}
```

**Why this matters:**
{{impact_explanation}}
```

## Example Outputs

### 🔐 SQL Injection vulnerability

**Location:** `src/api/auth.ts:23`
**Severity:** critical | **CWE:** CWE-89
**Confidence:** 98/100

**Vulnerability:**
User input directly interpolated into SQL query allows attacker to execute arbitrary SQL.

**Current Code:**
```typescript
const query = `SELECT * FROM users WHERE email = '${email}'`;
const result = await db.query(query);
```

**Suggested Fix:**
```diff
- const query = `SELECT * FROM users WHERE email = '${email}'`;
- const result = await db.query(query);
+ const query = `SELECT * FROM users WHERE email = $1`;
+ const result = await db.query(query, [email]);
```

**Why this matters:**
Attacker can input `'; DROP TABLE users; --` to delete your database. Parameterized queries prevent this by treating input as data, not code.

---

### 🔐 Hardcoded API key

**Location:** `src/services/payment.ts:12`
**Severity:** critical | **CWE:** CWE-798
**Confidence:** 99/100

**Vulnerability:**
API key committed to source code. Anyone with repo access can use your Stripe account.

**Current Code:**
```typescript
const stripe = new Stripe('sk_live_abc123xyz');
```

**Suggested Fix:**
```diff
- const stripe = new Stripe('sk_live_abc123xyz');
+ const stripe = new Stripe(process.env.STRIPE_SECRET_KEY!);
```

**Also required:**
1. Add to `.env`: `STRIPE_SECRET_KEY=sk_live_abc123xyz`
2. Ensure `.env` is in `.gitignore`
3. Rotate the exposed key immediately

**Why this matters:**
Exposed production keys can lead to unauthorized charges, data theft, and account compromise.
