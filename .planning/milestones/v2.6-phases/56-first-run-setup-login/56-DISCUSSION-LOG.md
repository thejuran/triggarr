# Phase 56: First-Run Setup & Login - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md -- this log preserves the alternatives considered.

**Date:** 2026-04-14
**Phase:** 56-first-run-setup-login
**Areas discussed:** Setup completion flow, Login page behavior, Template structure, Logout & nav integration

---

## Setup Completion Flow

| Option | Description | Selected |
|--------|-------------|----------|
| API key reveal step | Show success screen with API key, copy button, and "Continue to Dashboard" button. Auto-logged in but stays on setup. | :heavy_check_mark: |
| Inline flash + redirect | Auto-login, redirect to dashboard with dismissible banner showing API key. | |
| Modal overlay on dashboard | Auto-login, redirect to dashboard, show modal with API key. | |

**User's choice:** API key reveal step
**Notes:** Matches *arr pattern

| Option | Description | Selected |
|--------|-------------|----------|
| Clipboard API + feedback | navigator.clipboard.writeText() with "Copied" feedback. Vanilla JS. | :heavy_check_mark: |
| Select-all on click | Click selects all text, user Ctrl+C. | |
| You decide | Claude picks. | |

**User's choice:** Clipboard API + feedback

| Option | Description | Selected |
|--------|-------------|----------|
| Minimum length only | Require at least 1 character. No complexity rules. | :heavy_check_mark: |
| Minimum 8 characters | Basic floor for password length. | |
| You decide | Claude picks. | |

**User's choice:** Minimum length only
**Notes:** Matches Out of Scope decision on password complexity

---

## Login Page Behavior

| Option | Description | Selected |
|--------|-------------|----------|
| Inline error message | Red text below form: "Invalid username or password". Username pre-filled. | :heavy_check_mark: |
| Toast notification | Dismissible toast/banner at top. Form clears. | |
| You decide | Claude picks. | |

**User's choice:** Inline error message

| Option | Description | Selected |
|--------|-------------|----------|
| Original page via ?next= | Middleware stores original URL in ?next= param. Redirect back after login. | :heavy_check_mark: |
| Always dashboard | Always redirect to /. | |
| You decide | Claude picks. | |

**User's choice:** Original page via ?next=

| Option | Description | Selected |
|--------|-------------|----------|
| Redirect to dashboard | If session valid, /login redirects to /. | :heavy_check_mark: |
| Show login page anyway | Display form even if logged in. | |
| You decide | Claude picks. | |

**User's choice:** Redirect to dashboard

---

## Template Structure

| Option | Description | Selected |
|--------|-------------|----------|
| Standalone minimal | Centered card on dark bg. No nav. New base-auth.html. | :heavy_check_mark: |
| Extend base.html | Reuse existing base.html with nav bar. | |
| You decide | Claude picks. | |

**User's choice:** Standalone minimal
**Notes:** "This still needs to come from AIDesigner MCP and copied exactly"

| Option | Description | Selected |
|--------|-------------|----------|
| Thin auth base + AIDesigner body | base-auth.html with <head> and {% block content %}. AIDesigner HTML goes into extending templates. | :heavy_check_mark: |
| Fully standalone per page | Each page is complete HTML, no shared base. | |
| You decide | Claude picks. | |

**User's choice:** Thin auth base + AIDesigner body

---

## Logout & Nav Integration

| Option | Description | Selected |
|--------|-------------|----------|
| Right side, after Settings | Text link after Settings in nav. | |
| Icon-only button | Small logout icon in far right. | |
| You decide | Claude picks. | |

**User's choice:** "Ask AIDesigner MCP" -- placement determined by AIDesigner

| Option | Description | Selected |
|--------|-------------|----------|
| Instant logout | Click = clear cookie, redirect to /login. No confirmation. | :heavy_check_mark: |
| Confirmation prompt | "Are you sure?" dialog before clearing session. | |
| You decide | Claude picks. | |

**User's choice:** Instant logout

| Option | Description | Selected |
|--------|-------------|----------|
| POST form | POST to /logout via form or htmx hx-post. CSRF-safe. | :heavy_check_mark: |
| GET link | Simple <a href="/logout">. | |
| You decide | Claude picks. | |

**User's choice:** POST form

| Option | Description | Selected |
|--------|-------------|----------|
| Only when auth active | Show logout only for Forms/Basic modes. | :heavy_check_mark: |
| Always visible | Show regardless of auth mode. | |
| You decide | Claude picks. | |

**User's choice:** Only when auth active

---

## Claude's Discretion

- Route handler structure (single file vs separate auth routes)
- Cookie attributes (httpOnly, secure, SameSite, path)
- Setup form field ordering
- ?next= param validation (open redirect prevention)
- Whether setup success is separate route or same route with state

## Deferred Ideas

None -- discussion stayed within phase scope
