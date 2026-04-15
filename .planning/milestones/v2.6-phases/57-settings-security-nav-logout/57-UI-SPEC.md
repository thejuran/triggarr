# Phase 57: Settings Security — UI Design Contract

**Generated:** 2026-04-14
**Source:** AIDesigner artifact (run `8622a904-ad9a-4932-b2f6-3e66c47056cf`, refined from `4260669d-8a9c-4bb8-a01a-a39f5439aebc`)
**Status:** Locked — pixel-exact implementation required

## Design Artifact

The AIDesigner HTML artifact is the **single source of truth** for this phase's UI. Implementation must match it pixel-exact. The artifact covers all states.

### AIDesigner Run ID

- Initial: `4260669d-8a9c-4bb8-a01a-a39f5439aebc`
- Refined: `8622a904-ad9a-4932-b2f6-3e66c47056cf` (final)

## Component Inventory

### 1. Disabled Auth Warning Banner (conditional)

- **Placement:** Above all settings sections, full-width, outside any card
- **Visibility:** Only when `auth.method == "Disabled"` (config-file-only mode)
- **Structure:** `bg-red-900/30 border border-red-900/80 rounded p-4` with warning icon + bold title + description
- **Icon:** Phosphor `ph-fill ph-warning-circle` in `text-red-500`
- **Title:** "Authentication Override" — `text-sm font-semibold`
- **Body:** "Authentication is disabled. Auth mode can only be changed back from the config file." — `text-sm text-red-200/90`

### 2. Security Card

- **Pattern:** `bg-[#1e293b] rounded-lg border border-[#334155] p-5` (matches General section exactly)
- **Heading:** `<h2 class="text-lg font-semibold mb-4">Security</h2>`
- **Placement:** After General section, before per-app sections
- **Sub-section dividers:** `border-t border-[#334155]` with `my-6` spacing

### 3. Authentication Method (inside Security card)

- **Label:** "Authentication Method" — standard `text-sm text-[#94a3b8] mb-1`
- **Input:** `<select>` with options: Forms, Basic, External (NO Disabled option)
- **Select styling:** `w-full bg-[#0f172a] border border-[#334155] rounded px-3 py-2 text-sm` within `max-w-md`
- **Contextual warnings (below select, conditional):**
  - External selected: "Login page will be bypassed. Ensure your reverse proxy handles auth." — `text-sm text-amber-500 mt-2`
  - Basic selected: "Browser will show a native popup instead of the login page." — `text-sm text-amber-500 mt-2`
  - Forms selected: no warning shown

### 4. Change Password (inside Security card)

- **Sub-heading:** `<h3 class="text-base font-semibold mb-4">Change Password</h3>`
- **Fields:** Current Password, New Password, Confirm New Password — stacked vertically with `gap-4`
- **Input styling:** `w-full bg-[#0f172a] border border-[#334155] rounded px-3 py-2 text-sm` (all `type="password"`)
- **Validation error state:** Input border changes to `border-red-500/80`, error text `text-sm text-red-500 mt-1` below the field
- **Error messages:** "Passwords do not match" (confirm field), "Current password is incorrect" (current field)
- **Success state:** Green text "Password updated" replaces form temporarily, all fields clear
- **Submit button:** "Change Password" — `bg-[#22c55e] hover:bg-[#16a34a] text-white font-medium px-6 py-2 rounded text-sm`
- **Submit method:** htmx `hx-post` to dedicated endpoint (separate from Security save)

### 5. API Key Management (inside Security card)

- **Label:** "API Key" — standard label pattern
- **Key display:** Read-only input, `type="password"` (masked by default), `tracking-widest`
- **Eye toggle:** Button inside input (absolute positioned right), Phosphor `ph-eye` / `ph-eye-slash`, toggles input type between password/text
- **Copy button:** Standalone button next to input, Phosphor `ph-copy`, `bg-[#0f172a] border border-[#334155] rounded px-3 py-2`
- **Regenerate button:** `bg-red-900/10 border border-red-900/40 text-red-500 hover:bg-red-900/30 rounded px-3 py-2 text-sm`
- **Regeneration confirmation (inline expand):**
  - Container: `bg-[#0f172a] border border-red-900/40 rounded p-4` with left red accent bar (`w-1 bg-red-600`)
  - Warning text: "This will invalidate the current API key. Any integrations using it will stop working immediately." — `text-sm text-red-400`
  - Confirm button: `bg-red-600 hover:bg-red-700 text-white font-medium px-4 py-1.5 rounded text-sm`
  - Cancel button: `text-[#94a3b8] hover:text-[#e2e8f0] font-medium px-3 py-1.5 text-sm`
- **After regeneration:** Key field shows new key fully visible (auto-revealed), green "Key regenerated" message

### 6. Save Security Settings Button

- **Placement:** Bottom of Security card, after final divider
- **Styling:** `bg-[#22c55e] hover:bg-[#16a34a] text-white font-medium px-6 py-2 rounded text-sm`
- **Scope:** Saves auth mode selection only (password change has its own submit)

## Layout Rules

- All form content within `max-w-md` (matching General section)
- Sub-sections separated by `border-t border-[#334155]` with `my-6` margin
- Security card is a **separate form** from the existing settings form
- Password change uses htmx partial submit (own endpoint, own response)
- API key regenerate uses htmx (own endpoint)

## Icon Library

Phosphor Icons (already used in the artifact):
- `ph-fill ph-warning-circle` — disabled auth banner
- `ph ph-eye` / `ph ph-eye-slash` — API key visibility toggle
- `ph ph-copy` — clipboard copy

**Note:** If Phosphor is not already in the project, use inline SVG equivalents matching the same visual weight.

## States Shown in Artifact

1. Disabled auth warning banner (visible)
2. Auth mode dropdown with External selected + amber warning
3. Password form with validation error on confirm field
4. API key masked with regeneration confirmation expanded

---

*Phase: 57-settings-security-nav-logout*
*UI-SPEC generated: 2026-04-14 via AIDesigner MCP*
