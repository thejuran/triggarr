# Phase 63: Header Favicon Icon - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-17
**Phase:** 63-header-favicon-icon
**Areas discussed:** Source asset availability, Asset strategy, Asset cleanup scope, Header visual spec

---

## Area Selection

User selected all four areas for discussion.

| Option | Description | Selected |
|--------|-------------|----------|
| Asset strategy | SVG source, fixed PNG, or Phosphor icon | ✓ |
| Asset cleanup scope | Header-only vs full favicon bundle regen | ✓ |
| Header visual spec | Size, color, gap, alignment | ✓ |
| Source asset availability | User-supplied vs generated | ✓ |

---

## Source Asset Availability

### Q1: Do you have a cleaned-up source file ready (SVG/PNG) for the Triggarr icon?

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, SVG ready | Clean SVG source, cross-size export | |
| Yes, PNG ready | Hi-res PNG, downsample from it | |
| No — use Phosphor icon | Skip asset pipeline, use vendored font icon | |
| No — generate one | Produce SVG from scratch | |
| **Other (free text)** | **"Can you tell from the metadata where the one I have now is from so I can get a new one ready?"** | **✓** |

**User's choice:** Free-text — wanted origin identification before deciding.
**Notes:** Claude inspected existing PNG text chunks (stripped), file naming pattern, site.webmanifest shape. Conclusion: canonical realfavicongenerator.net / favicon.io output signature, no embedded tool tag.

### Q2: If you have a file, where is it (or where will it go)?

| Option | Description | Selected |
|--------|-------------|----------|
| triggarr/static/ root | Alongside existing favicons | |
| triggarr/static/img/ | New img/ subdir | |
| Not yet — decide later | Decide after file exists | ✓ |

**User's choice:** Not yet — decide later (resolved in next batch after SVG confirmed).

### Follow-up: Source size needed for the plan

Claude recommended: SVG ideal (zero aliasing). If PNG, 512×512 master minimum (1024 better). For header-only fix, 48×48 PNG enough — half-fix since tab icon stays broken.

**User's response:** "it's sitting on my desktop as favicon.svg" — SVG source confirmed ready.

---

## Drop Location

### Q: Where should the SVG land in the repo?

| Option | Description | Selected |
|--------|-------------|----------|
| triggarr/static/favicon.svg (Recommended) | Alongside existing favicon.* files | ✓ |
| triggarr/static/img/logo.svg | New img/ subdir | |

**User's choice:** `triggarr/static/favicon.svg`
**Notes:** Matches favicon.* naming convention; simplest drop-in path.

---

## Asset Cleanup Scope

### Q: How much of the favicon bundle should we regenerate from the SVG?

| Option | Description | Selected |
|--------|-------------|----------|
| Full bundle: SVG + all PNGs + .ico (Recommended) | Regenerate 16/32/180/192/512 + .ico; add SVG primary link | ✓ |
| SVG-only, deprecate PNGs | Only favicon.svg + link updates | |
| Header icon only | Use SVG only for header; leave favicons as-is | |

**User's choice:** Full bundle regeneration.
**Notes:** Closes HDR-06 and repairs tab/PWA icon artifacts in a single pass.

---

## Header Markup

### Q: How should the header icon be rendered in base.html?

| Option | Description | Selected |
|--------|-------------|----------|
| `<img src=favicon.svg>` (Recommended) | Simple img tag, browser-cacheable | ✓ |
| Inline `<svg>` | Paste SVG markup directly into base.html | |

**User's choice:** `<img>` tag referencing favicon.svg.
**Notes:** Browser caching + simpler diff review; colors baked into SVG file.

---

## Header Visual Spec

### Q: What visual spec for the header icon?

| Option | Description | Selected |
|--------|-------------|----------|
| 24×24px, gap-2 from text (Recommended) | Slightly larger than logo text for brand weight | ✓ |
| 20×20px, gap-2 from text | Exact logo-text height match | |
| 28×28px, gap-3 from text | Icon-forward, SeedSyncarr-style | |

**User's choice:** 24×24px with `gap-2` (8px) from text.
**Notes:** Balances brand-anchor weight without overwhelming the 20px wordmark.

---

## Regeneration Workflow

### Q: How will the PNGs + favicon.ico be generated from the SVG?

| Option | Description | Selected |
|--------|-------------|----------|
| User runs realfavicongenerator.net (Recommended) | Matches existing bundle origin; drop-in clean | ✓ |
| Automated via sips + ImageMagick | scripts/regen-favicons.sh | |
| Claude generates via Python (cairosvg/Pillow) | Dev-tool one-shot, commits binaries | |

**User's choice:** User runs realfavicongenerator.net.
**Notes:** Filenames + bundle shape match current output byte-for-byte — drops in without markup churn.

---

## SVG Background Handling

### Q: Does your favicon.svg have the dark rounded-square background baked in, or is it transparent?

| Option | Description | Selected |
|--------|-------------|----------|
| Baked-in dark background | Matches current PNG look | |
| Transparent, icon only | Cleaner for header overlay | |
| Not sure — check it | Inspect after drop-in | ✓ |

**User's choice:** Not sure — Claude inspects once SVG lands in repo.
**Notes:** Planning will include a one-step inspection task before finalizing header CSS.

---

## Closing

### Q: Anything else to discuss or ready for CONTEXT.md?

| Option | Description | Selected |
|--------|-------------|----------|
| Ready for context (Recommended) | Write CONTEXT.md | ✓ |
| Explore more gray areas | More ambiguities to surface | |
| Revisit an area | Change a prior decision | |

**User's choice:** Ready for context.

---

## Claude's Discretion

- Nested flex structure to achieve icon↔text `gap-2` while preserving text↔version-badge `gap-3`
- Alt text choice (`alt=""` decorative vs `alt="Triggarr"`)
- Whether to update `site.webmanifest` theme_color
- Test strategy for favicon assets (asset-existence + size assertions favored over byte-exact)

## Deferred Ideas

None — discussion stayed within HDR-06 scope.
