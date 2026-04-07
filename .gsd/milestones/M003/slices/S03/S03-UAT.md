# S03: Web UI & Templates — UAT

**Milestone:** M003
**Written:** 2026-04-06

## UAT Type

- UAT mode: live-runtime
- Why this mode is sufficient: This slice is template/UI changes — visual verification in a running browser is the definitive check that Lidarr appears correctly across all UI surfaces.

## Preconditions

- Triggarr running locally (`uv run python -m triggarr` or Docker)
- At least one Lidarr instance configured in `config.toml` (can be a fake URL if just checking templates render)
- Optionally: a real Lidarr instance for full end-to-end verification

## Smoke Test

Open the dashboard at `http://localhost:8080`. Confirm Lidarr instance cards appear alongside Radarr/Sonarr cards (or empty-state text mentions Lidarr if no instances configured).

## Test Cases

### 1. Dashboard — Lidarr instance cards

1. Configure at least one Lidarr instance in `config.toml`
2. Open `http://localhost:8080`
3. **Expected:** Lidarr instance card(s) appear with connection health indicator, queue size, and position label — visually distinct from Radarr (orange) and Sonarr (blue)

### 2. Dashboard — Empty state mentions Lidarr

1. Remove all instances from config (or use a fresh config)
2. Open dashboard
3. **Expected:** Empty-state text mentions Lidarr alongside Radarr and Sonarr

### 3. Stats row — Albums card and Lidarr grab rate

1. With Lidarr configured and some search history present, open dashboard
2. Look at the stats row below instance cards
3. **Expected:** "Albums" card appears (showing found + upgraded counts). Grab rate row shows `L:` percentage alongside `R:` and `S:`. Grid expands to 5 columns when all app types have data.

### 4. History — Lidarr filter pill

1. Navigate to Search History page
2. Look at the app filter bar
3. **Expected:** "Lidarr" pill appears with green color (`bg-green-500/20 text-green-400`). Clicking it filters to Lidarr-only entries.

### 5. History — Lidarr entry badge color

1. Trigger a Lidarr search (or have existing Lidarr history entries)
2. View Search History
3. **Expected:** Lidarr entries show a green badge (not orange/blue), clearly distinguishing them from Radarr/Sonarr entries

### 6. Settings — Lidarr instance management

1. Navigate to Settings page
2. Click "Add Instance" and select Lidarr
3. **Expected:** URL placeholder shows `http://lidarr:8686` (port 8686, not 7878 or 8989). All fields (name, URL, API key, schedule, batch sizes, tags) are present and functional.

### 7. Settings — Edit existing Lidarr instance

1. With a Lidarr instance configured, open Settings
2. Edit the Lidarr instance
3. **Expected:** Existing values populated correctly, can modify and save

## Edge Cases

### Lidarr-only config (no Radarr/Sonarr)

1. Configure only Lidarr instances, no Radarr or Sonarr
2. Open dashboard, stats, history
3. **Expected:** Dashboard shows only Lidarr cards. Stats row shows only Albums card (no Movies/Episodes). History shows only Lidarr pill active. No errors or broken layout.

### Mixed instances with tag filtering

1. Configure a Lidarr instance with tag filters
2. Verify tags appear in the instance card/settings
3. **Expected:** Tag names display correctly (resolved from Lidarr API tag IDs)

## Failure Signals

- Lidarr cards missing from dashboard when instances are configured
- "Lidarr" pill missing from history filter bar
- Lidarr entries showing wrong badge color (orange or blue instead of green)
- Settings URL placeholder showing wrong port for Lidarr
- Albums card missing from stats row when Lidarr data exists
- Layout breaking when all 3 app types are present (grid overflow)
- JavaScript errors in browser console

## Requirements Proved By This UAT

- none (Lidarr is a new capability without prior requirement IDs)
- Proves: Lidarr is a first-class citizen in all UI surfaces matching Radarr/Sonarr parity

## Not Proven By This UAT

- Lidarr API correctness (covered by S01 unit tests)
- Search cycle logic (covered by S02 unit tests)
- Scheduler job execution (covered by integration tests)
- Docker build (separate CI verification)

## Notes for Tester

- If no real Lidarr instance is available, the connection health will show as unhealthy — that's fine, focus on template rendering and layout.
- Green color for Lidarr was chosen to contrast with Radarr orange and Sonarr blue.
- Stats grid goes from 4 to 5 columns when all app types are present — check it doesn't look cramped on smaller screens.
