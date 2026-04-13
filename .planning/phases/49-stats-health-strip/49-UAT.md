---
status: complete
phase: 49-stats-health-strip
source: 49-CONTEXT.md, 49-01-PLAN.md, 49-02-PLAN.md, 49-03-PLAN.md
started: 2026-04-13T00:00:00Z
updated: 2026-04-13T19:15:00Z
---

## Current Test

[testing complete]

## Tests

### 1. Health strip replaces health card
expected: Single-line strip above stats grid. No card background. Colored dots (green=connected, red=disconnected, gray=pending) with bold counts. Right-aligned "Last sync" timestamp. No border, no shadow — just text with dots.
result: pass

### 2. Last sync timestamp updates
expected: On first dashboard load, "Last sync never" appears. After ~30 seconds (one htmx poll cycle), it updates to "Last sync Xs ago" relative time. Continues updating every 30s.
result: pass

### 3. Hero Grab Rate card layout
expected: First card in the stats grid spans 2 columns (wider than other cards). Shows "Grab Rate" label top-left, large percentage number (text-4xl size), and a subtle green gradient overlay on the card background. Card has shadow-sm elevation.
result: pass

### 4. Health badge on Grab Rate card
expected: Top-right of the Grab Rate card shows a small pill badge. If grab rate >=70%: green "Healthy" badge. If >=40%: amber "Warn" badge. If <40%: red "Critical" badge. If no data: no badge shown.
result: pass

### 5. Per-app colored bar chart
expected: Below the grab rate number, each configured app type shows a labeled row with mini-bar CSS (6px height, 3px border-radius, slate background). Only apps with data appear. No bars when no search data exists.
result: pass

### 6. Shadow-sm on all stat cards
expected: All stat cards (Grab Rate, Movies, Episodes, Albums, Time to Grab) have shadow-sm class and computed box-shadow.
result: pass

### 7. Instance filter still works
expected: When filtered to a specific app, irrelevant stat cards hide. Grid adjusts to 3 columns. Hero Grab Rate card adjusts to col-span-1 for even layout. Cards fill the row cleanly.
result: pass

## Summary

total: 7
passed: 7
issues: 0
pending: 0
skipped: 0
blocked: 0

## Gaps

[none]
