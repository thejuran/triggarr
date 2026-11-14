# Phase 86: Pilot & Reference Record - Pattern Map

**Mapped:** 2026-10-30
**Files analyzed:** 9 (2 source modules, 1 template, 4 test files, 2 new docs)
**Analogs found:** 9 / 9

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `triggarr/search/engine.py` (`refresh_radarr_counts`, `refresh_sonarr_counts`, `refresh_lidarr_counts`) | service (engine/state-mutation) | batch (per-item screen over a fetched record list) | `triggarr/search/engine.py` `run_sonarr_cycle`'s missing-queue chain (same file, same module — the scheduled-cycle screening pattern) | exact (same codebase mechanism, `_screen_queue`, reused verbatim) |
| `triggarr/search/outcome.py` (`cycle_view`, 5 reason-dict construction sites) | model/transform (pure render-ready-dict builder) | transform | same function, same file — adding a sibling key to an existing dict-construction pattern already used 5x in the function | exact |
| `triggarr/templates/partials/cycle_grade.html` | component (Jinja2 SSR partial) | transform (classify-then-render) | same file — replacing its own text-matching `{% if %}` chain (lines 20-27) with a field-matching chain of identical shape | exact |
| `tests/test_refresh_counts.py` (rewrite 3 existing malformed tests + add Lidarr/Radarr-equivalent regression tests) | test | unit | same file's existing `test_refresh_sonarr_counts_malformed_*_data_returns_none` / `test_refresh_radarr_counts_malformed_tag_data_returns_none` (to be rewritten in place, not replaced) | exact |
| `tests/test_malformed_records_client_path.py` (rewrite `test_refresh_counts_unchanged_for_non_object_record`) | test | unit/integration (real client over `httpx.MockTransport`) | same file, same test — docstring literally names this as the follow-up being resolved | exact |
| `tests/test_outcome.py` (~20 dict-equality assertions gain a `"kind"` key) | test | unit | same file's existing `test_cycle_view_*` assertions (e.g. `test_cycle_view_malformed_by_queue_missing_singular`, line 459) | exact |
| `tests/test_app_cards.py` (verify-only — expect zero changes) | test | integration (full-route HTML rendering) | same file's `test_card_malformed_by_queue_row_renders` (line 531) and the `test_card_skip_only_*` family | exact (regression oracle, not itself edited) |
| `.planning/phases/86-pilot-reference-record/86-PILOT-RECORD.md` (new) | docs (process/evidence record) | batch (static write-up of already-collected evidence) | `.planning/phases/85.1-isolated-codex-review-for-untrusted-prs/85.1-REVIEW-EVIDENCE.md` (per-head checkpoint template) + `docs/review-checkpoint-record.md` (the template itself) | exact |
| `docs/review-workflow-adoption.md` (new) | docs (reusable process guidance) | transform (distill existing process into GitHub-enforced vs. instruction-enforced buckets) | `docs/bm-greptile-codex-blueprint.md` (process narrative + target-sequence structure) and `docs/buildomator-greptile-pilot.md` (activation checklist + "what GitHub enforces vs. what Claude enforces" framing) | exact (two-source blend) |

## Pattern Assignments

### `triggarr/search/engine.py` — `refresh_sonarr_counts` / `refresh_lidarr_counts` / `refresh_radarr_counts` (service, batch)

**Analog:** `run_sonarr_cycle`'s missing-queue chain, same file, `triggarr/search/engine.py:1365-1399` — the scheduled-cycle pattern that already does what D-02/D-02a asks for.

**Imports pattern** (file header, `engine.py:9-29` — already present, no new imports needed for this fix):
```python
from __future__ import annotations

import contextlib
import functools
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime

import aiosqlite
import httpx
import pydantic
from loguru import logger

from triggarr.clients.base import _sanitize_exc
from triggarr.clients.lidarr import LidarrClient
from triggarr.clients.radarr import RadarrClient
from triggarr.clients.sonarr import SonarrClient
from triggarr.db import PendingCapExceeded, insert_search_entry
from triggarr.models.arr import Tag
from triggarr.models.config import InstanceConfig, Settings
from triggarr.search.outcome import CycleTally, active_queues
from triggarr.state import AppState, TriggarrState
```
`CycleTally` is already imported at module scope (line 27) — the fix needs no new import, just a local instantiation inside each `refresh_*_counts` function.

**Core pattern to copy — per-item screening before each filter step** (`engine.py:1365-1399`, `run_sonarr_cycle`):
```python
missing_seasons: list[dict] = []
if missing_episodes is not None:
    try:
        missing_episodes = _screen_queue(missing_episodes, app_label="Sonarr", queue="missing", tally=tally)
        missing_episodes = filter_monitored(missing_episodes)
        missing_episodes = _screen_queue(
            missing_episodes, app_label="Sonarr", queue="missing", tally=tally, date_fields=("airDateUtc",)
        )
        missing_episodes = filter_sonarr_episodes(missing_episodes)
        if scope.missing_tag_id is not None:
            missing_episodes = _screen_queue(
                missing_episodes, app_label="Sonarr", queue="missing", tally=tally,
                nested_key="series", tags_at=("series", "tags"),
            )
            missing_episodes = filter_by_tag(missing_episodes, scope.missing_tag_id, _sonarr_tags)
        missing_episodes = _screen_queue(
            missing_episodes, app_label="Sonarr", queue="missing", tally=tally,
            key_fields=("seriesId", "seasonNumber"), nested_key="series",
        )
        missing_seasons = deduplicate_to_seasons(missing_episodes)
        ...
    except (AttributeError, KeyError, TypeError) as exc:
        # backstop for any OTHER unexpected fault -- not the malformed-record case,
        # which _screen_queue already intercepted above
        ...
```
`_screen_queue`'s exact signature (`engine.py:156-166`) — the helper being reused, unchanged:
```python
def _screen_queue(
    items: list,
    *,
    app_label: str,
    queue: str,
    tally: CycleTally,          # required, not Optional
    key_fields: tuple[str, ...] = (),
    nested_key: str | None = None,
    tags_at: tuple[str, ...] | None = None,
    date_fields: tuple[str, ...] = (),
) -> list[dict]:
```

**The code to replace in each `refresh_*_counts`** — the current coarse guard (e.g. `engine.py:1924-1976` for Radarr; sibling blocks at `2047-2103` for Sonarr, `2173-2221` for Lidarr):
```python
scope: _TagScope | None = None
try:
    scope = await _resolve_tag_scope(..., tally=None)
    filtered_missing = filter_monitored(missing)          # <- no _screen_queue call today
    ...
except (AttributeError, KeyError, TypeError) as exc:
    logger.warning("Radarr: Count refresh data fault ({etype}) -- treating as disconnected", ...)
    _mark_unreachable(ist)                                  # <- whole instance marked disconnected
    _clear_faulted_scoped_counts(ist, scope, instance_config, ...)
    return None
```

**Recommended minimal-diff shape (RESEARCH Pattern 1, Assumption A2):** instantiate a throwaway, never-persisted `CycleTally()` local to each `refresh_*_counts` function, pass it to new `_screen_queue(...)` calls inserted immediately before each filter/tag/dedup step (mirroring the `run_*_cycle` call sites above), and never call `.to_record()` on it or write it into `ist`/`state` — this satisfies D-02/D-02a's "no new dashboard warning" exactly, because nothing from the local tally is ever surfaced. The existing `try/except (AttributeError, KeyError, TypeError)` stays in place as the backstop for any *other* unexpected fault (matching the cycle functions' own comment: "the except below is the backstop for any other unexpected fault") — it no longer fires for a single malformed record, because `_screen_queue` now intercepts that case first.

**`_resolve_tag_scope`'s existing `tally: CycleTally | None` parameter** (`engine.py:798`) is the direct precedent for passing a `CycleTally` through a `refresh_*_counts` call without it ever reaching persisted state — the fix's new tally only needs to flow into the new `_screen_queue` calls, not into `_resolve_tag_scope`.

**Error handling / logging pattern** (unchanged, reused as-is): `logger.warning(...)` with structured kwargs (never raw exception text, never an f-string with unsanitized content) — see `_log_malformed_skip` (`engine.py:196-213`), which `_screen_queue` already calls internally; no new logging call needs to be written by this fix.

---

### `triggarr/search/outcome.py` — `cycle_view` (model/transform, 5 construction sites)

**Analog:** the function's own existing dict-construction sites (`outcome.py:260`, `275`, `291`, `306`/`314`, `335`) — the fix adds one sibling key to a pattern already repeated 5 times in this function.

**Core pattern today** (`outcome.py:255-335`, abbreviated — each `reasons.append({...})` site needs a `"kind"` key added):
```python
reasons: list[dict[str, object]] = []

fetch_error = record.get("fetch_error")
fetch_failed = isinstance(fetch_error, str) and bool(fetch_error)
if fetch_failed:
    reasons.append({"text": _truncate(f"Couldn't reach {app_label} ({fetch_error})"), "count": 1})
    # kind="fetch_failed"

...
            reasons.append({"text": _truncate(text), "count": count})
            # kind="failure"  (failure_reasons loop, line 275)

...
            reasons.append({"text": _truncate(f"{label} queue not evaluated: {reason}"), "count": 1})
            # kind="unevaluated"  (unevaluated loop, line 291)

...
            reasons.append({"text": _truncate(text), "count": 1})
            # kind="malformed"  (malformed_by_queue loop, line 306)

if malformed_rows_appended == 0 and malformed_skipped > 0:
    ...
    reasons.append({"text": _truncate(text), "count": 1})
    # kind="malformed"  (legacy aggregate fallback, line 314)

...
        reasons.append({"text": _truncate(text), "count": 1})
        # kind="eligible_not_searched"  (eligible backstop, line 335)
```

**Validation / boundary pattern** (`outcome.py:219-245`, reused unchanged — this is the module's existing "never trust a persisted record" discipline that any new field must also respect): `cycle_view` validates `record` is a dict with a recognized `grade` before building anything, and every sub-field (`_as_count`, `isinstance(..., str)`, `isinstance(..., dict)`/`isinstance(..., list)` checks) treats tampered/garbage `state.json` content as absent rather than raising. A new `"kind"` literal is always a Claude-authored constant at the construction site (never read from `record`), so it needs no additional validation — it cannot be tampered, unlike `text`/`count`.

**Docstring convention to extend** (`outcome.py:1-11`, `219-239`): this module's functions carry long prose docstrings naming the spec section and phase that introduced each behavior (e.g. "Phase 80 reports malformed *arr records..."). The new `"kind"` field's docstring addition should follow the same voice — name D-03/Phase 86 the way the existing docstring names D-07/D-09/D-10.

---

### `triggarr/templates/partials/cycle_grade.html` (component, transform)

**Analog:** the template's own existing branch, same file, lines 18-28.

**Current pattern to replace** (`cycle_grade.html:18-28`):
```jinja2
{% set ns = namespace(malformed=0, malformed_total=0, unevaluated=0, other=0) %}
{% for r in app.last_cycle.reasons %}
  {% if r.text.startswith('Missing queue not evaluated: ') or r.text.startswith('Cutoff unmet queue not evaluated: ') %}
    {% set ns.unevaluated = ns.unevaluated + 1 %}
  {% elif r.text.endswith('— malformed data') or r.text.endswith('skipped') %}
    {% set ns.malformed = ns.malformed + 1 %}
    {% set ns.malformed_total = ns.malformed_total + (r.text.split(' ')[0] | int(0)) %}
  {% else %}
    {% set ns.other = ns.other + 1 %}
  {% endif %}
{% endfor %}
```

**Target shape** (RESEARCH Pattern 2 — same `namespace`/`for`/`if-elif-else` structure, only the condition changes from `r.text.*` to `r.kind`):
```jinja2
{% set ns = namespace(malformed=0, malformed_total=0, unevaluated=0, other=0) %}
{% for r in app.last_cycle.reasons %}
  {% if r.kind == 'unevaluated' %}
    {% set ns.unevaluated = ns.unevaluated + 1 %}
  {% elif r.kind == 'malformed' %}
    {% set ns.malformed = ns.malformed + 1 %}
    {% set ns.malformed_total = ns.malformed_total + r.skip_count %}
  {% else %}
    {% set ns.other = ns.other + 1 %}
  {% endif %}
{% endfor %}
```
Note `r.skip_count` above assumes the optional bonus fix (RESEARCH Pattern 2's "Bonus fix available") is taken; if not taken, keep `(r.text.split(' ')[0] | int(0))` unchanged — D-03 only requires the classification mechanism to stop reading display text, not the count extraction.

**Everything else in the file is unchanged**, including the rendering loop that must still emit identical visible text (`cycle_grade.html:38-42`):
```jinja2
<ul class="mt-1 ml-4 list-disc">
  {% for r in app.last_cycle.reasons %}
  <li>{{ r.text }}{% if r.count > 1 %} &times;{{ r.count }}{% endif %}</li>
  {% endfor %}
</ul>
```
This loop reads only `r.text`/`r.count`, never `r.kind` — the new field is invisible to the actually-rendered HTML, which is why D-03's "no visible difference" is achievable: `tests/test_app_cards.py`'s ~90 rendering assertions check exactly this loop's output and must show zero diff.

---

### `tests/test_refresh_counts.py` (test, unit)

**Analog:** the file's own existing malformed-fault tests, to be rewritten in place — `test_refresh_sonarr_counts_malformed_cutoff_data_returns_none` (line 352), `test_refresh_sonarr_counts_malformed_missing_data_returns_none` (line 394), `test_refresh_radarr_counts_malformed_tag_data_returns_none` (line 431).

**Imports pattern** (`test_refresh_counts.py:15-42`):
```python
from __future__ import annotations

import asyncio
import time
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import aiosqlite
import httpx
import pytest
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.testclient import TestClient

from tests.conftest import make_settings
from triggarr.db import init_db
from triggarr.models.arr import Tag
from triggarr.models.config import InstanceConfig
from triggarr.search.engine import (
    refresh_lidarr_counts,
    refresh_radarr_counts,
    refresh_sonarr_counts,
    run_lidarr_cycle,
    run_radarr_cycle,
    run_sonarr_cycle,
)
from triggarr.state import _default_instance_state, _default_state
from triggarr.web.routes import STATIC_DIR, router
```

**Existing test to rewrite, old assertion (must flip to new behavior)** (`test_refresh_counts.py:352-391`):
```python
async def test_refresh_sonarr_counts_malformed_cutoff_data_returns_none():
    """Rewrite-3: malformed cutoff episode (series=non-dict) -> deduplicate_to_seasons raises
    AttributeError -> helper returns None (does NOT propagate exception), sets disconnected."""
    good_ep = _make_sonarr_episode(series_id=10, season_number=1, episode_id=100)
    malformed_cutoff_ep = {
        "id": 999, "seriesId": 1, "seasonNumber": 2, "monitored": True,
        "airDateUtc": (datetime.now(UTC) - timedelta(days=1)).isoformat().replace("+00:00", "Z"),
        "series": "not-a-dict",  # triggers AttributeError in deduplicate_to_seasons
    }
    client = AsyncMock()
    client.get_wanted_missing = AsyncMock(return_value=[good_ep])
    client.get_wanted_cutoff = AsyncMock(return_value=[malformed_cutoff_ep])
    client.get_library_count = AsyncMock(return_value=10)
    state = _make_test_state()
    result = await refresh_sonarr_counts(client, state, "Default", _instance_config(), make_settings())
    assert result is None
    ist = state["sonarr"]["Default"]
    assert ist["connected"] is False          # <-- D-02: must become True; result is no longer None
    assert ist["unreachable_since"] is not None
```
**New shape (what the rewrite asserts instead, per D-02):** the malformed cutoff episode is skipped, `good_ep` still produces correct counts, `ist["connected"] is True`, and (mirroring `run_sonarr_cycle`'s logging contract) a single `logger.warning` fires once per reason via `_log_malformed_skip` — assert on the surviving eligible/searchable counts the way `tests/test_outcome.py::test_cycle_tally_record_malformed_per_queue` (outcome-side) and the existing non-malformed `refresh_sonarr_counts` success tests already assert `ist["missing_eligible"]`/`ist["cutoff_searchable"]`.

**Radarr test requiring the same rewrite (D-02a, owner-added 2026-10-30)** (`test_refresh_counts.py:431-457`):
```python
async def test_refresh_radarr_counts_malformed_tag_data_returns_none():
    """Rewrite-3: tag configured + item with non-iterable tags -> filter_by_tag raises TypeError
    -> helper returns None (does NOT propagate), sets disconnected."""
    malformed_item = {"id": 1, "title": "Movie A", "monitored": True, "tags": 5}
    instance_config = _instance_config(missing_tag="mytag")
    client = AsyncMock()
    client.get_wanted_missing = AsyncMock(return_value=[malformed_item])
    client.get_tags = AsyncMock(return_value=[Tag(id=42, label="mytag")])
    result = await refresh_radarr_counts(client, state, "Default", instance_config, settings)
    assert result is None
    assert ist["connected"] is False           # <-- must become True under D-02a
```
Rename each test away from `_returns_none` once its own assertion changes (the name documents D-02/D-02a's new contract, e.g. `test_refresh_sonarr_counts_malformed_cutoff_data_skips_record_stays_connected`), matching this repo's convention of the test name stating the exact behavior it locks (seen throughout this file and `test_outcome.py`).

---

### `tests/test_malformed_records_client_path.py` (test, unit/integration — real client over `httpx.MockTransport`)

**Analog:** the file's own `test_refresh_counts_unchanged_for_non_object_record` (lines 273-286) — the literal follow-up test D-02 resolves.

**Imports / fixtures pattern** (`test_malformed_records_client_path.py:1-42`):
```python
from __future__ import annotations

import json

import aiosqlite
import httpx
import pydantic
import pytest
from pydantic import SecretStr

from tests.conftest import make_settings
from triggarr.clients.lidarr import LidarrClient
from triggarr.clients.radarr import RadarrClient
from triggarr.clients.sonarr import SonarrClient
from triggarr.db import init_db
from triggarr.models.config import InstanceConfig
from triggarr.search.engine import (
    refresh_lidarr_counts,
    run_lidarr_cycle,
    run_radarr_cycle,
    run_sonarr_cycle,
)
from triggarr.state import _default_instance_state, _default_state
```
Fake-transport fixture helpers already in the file (`_page`, `_FakeArr`, `_GOOD`, `_CLIENTS`, `_CYCLES`) are reused as-is — no new fixture infrastructure needed.

**Existing test, exact old assertion to rewrite** (`test_malformed_records_client_path.py:273-286`):
```python
async def test_refresh_counts_unchanged_for_non_object_record(tmp_path):
    """Out of scope for PR #28 and recorded as a follow-up: Refresh counts keeps
    its strict fetch, so a null record still marks the instance unreachable
    there, and it does so without raising."""
    fake = _FakeArr({"missing": [_GOOD["lidarr"], None]})
    client = _client("lidarr", fake)
    state = _state("lidarr")
    try:
        config = InstanceConfig(url="http://arr.test", api_key="test-key", enabled=True)
        await refresh_lidarr_counts(client, state, "Default", config, make_settings())
    finally:
        await client.close()
    assert state["lidarr"]["Default"]["connected"] is False   # <-- must become True under D-02
```
Rewrite to assert the `None` record is skipped (via `_screen_queue`'s non-object-record screening — `_malformed_reason`'s first check, `engine.py:137-140`, already handles a bare `None`/non-dict item), the `_GOOD["lidarr"]` record is still counted, and `connected is True`. Update the docstring to say the follow-up is now resolved (D-02), not still out of scope. The sibling `run_radarr_cycle`/`run_sonarr_cycle` test immediately above this one (line ~255-270) already asserts the *cycle*-side (not refresh-side) of this exact non-object-record case and is the template for the new assertion shape: `ist["last_cycle"]["unevaluated"]`/`ist["missing_eligible"]`-style assertions on surviving counts, not a blanket `connected is False`.

---

### `tests/test_outcome.py` (test, unit — ~20 dict-equality assertions)

**Analog:** the file's own `test_cycle_view_malformed_by_queue_missing_singular` (line 459) and its ~20 siblings — every assertion of the shape `assert {"text": ..., "count": N} in view["reasons"]` needs a `"kind"` key added to the expected literal.

**Imports pattern** (`test_outcome.py:1-17`):
```python
"""Unit tests for the honest-outcome grading model (triggarr.search.outcome)."""

from __future__ import annotations

import json

from triggarr.search.outcome import (
    GRADE_FAILED,
    GRADE_LABELS,
    GRADE_NOTHING_NEEDED,
    GRADE_PARTIAL,
    GRADE_SUCCESS,
    CycleTally,
    active_queues,
    cycle_view,
    grade_cycle,
)
```

**Existing assertion shape to edit (add `"kind"` to every expected literal)** (`test_outcome.py:459-471`):
```python
def test_cycle_view_malformed_by_queue_missing_singular() -> None:
    """D-07: a per-queue malformed row replaces the generic row when malformed_by_queue is present."""
    record = {
        "grade": "partial", "accepted": 1, "failed": 0,
        "malformed_skipped": 1, "malformed_by_queue": {"missing": 1},
    }
    view = cycle_view(record, "Radarr")
    assert view is not None
    assert {"text": "1 missing-queue record skipped — malformed data", "count": 1} in view["reasons"]
    # ^ after D-03: {"text": "...", "count": 1, "kind": "malformed"}
    assert not any(r["text"] == "1 malformed record skipped" for r in view["reasons"])
```
Every other `test_cycle_view_*` assertion in this file (plural/singular malformed rows, unevaluated rows, fetch-error row, eligible backstop row, the `malformed_by_queue_both_queues_ordered` list-equality check at line 488-503, the tampered-fallback loop at line 506-529) follows this identical shape — each needs its matching `"kind"` literal added per the table in RESEARCH Pattern 2. `grade_cycle`/`CycleTally` tests (lines 22-375) are untouched; they never construct reason dicts.

---

### `tests/test_app_cards.py` (test, integration — verify-only, zero changes expected)

**Analog:** `test_card_malformed_by_queue_row_renders` (line 531) — the regression oracle proving D-03's "visible output identical" claim.

**Imports / fixture pattern** (`test_app_cards.py:1-33`):
```python
"""Phase 61 App Cards tests. ..."""

from __future__ import annotations

import asyncio
import html
from unittest.mock import AsyncMock, MagicMock

import aiosqlite
import pytest
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.testclient import TestClient

from tests.conftest import make_settings
from triggarr.db import init_db, insert_search_entry
from triggarr.log_buffer import log_buffer
from triggarr.models.config import GeneralConfig
from triggarr.web.routes import STATIC_DIR, _scoped_count_unknown, router
```

**The exact rendering assertion that must still pass unchanged after the template refactor** (`test_app_cards.py:531-543`):
```python
def test_card_malformed_by_queue_row_renders(client, test_app):
    """D-07/D-08: the card shows the per-queue malformed row with no title or item-ID text."""
    test_app.state.triggarr_state["radarr"]["Default"]["connected"] = True
    test_app.state.triggarr_state["radarr"]["Default"]["last_cycle"] = _last_cycle_record(
        grade="partial", accepted=1, malformed_skipped=1, malformed_by_queue={"missing": 1},
    )
    response = client.get("/partials/app-card/radarr/Default")
    assert response.status_code == 200
    assert "1 missing-queue record skipped — malformed data" in response.text
    assert "1 malformed record skipped" not in response.text
```
This test (and its 20+ siblings: `test_card_skip_only_*`, `test_card_details_label_*`, `test_grade_line_*`) drives `_last_cycle_record` → `cycle_view` → the real template through a live FastAPI `TestClient`, asserting on `response.text`. Run this file last in the refactor (after `test_outcome.py` is green) as the final proof D-03's "no visible difference" holds — any diff here is the real signal, not the expected `test_outcome.py` red step (RESEARCH Pitfall 3).

---

### `.planning/phases/86-pilot-reference-record/86-PILOT-RECORD.md` (docs, new)

**Analog:** `.planning/phases/85.1-isolated-codex-review-for-untrusted-prs/85.1-REVIEW-EVIDENCE.md` (per-head checkpoint structure) + the template it implements, `docs/review-checkpoint-record.md`.

**Structure to copy** (`85.1-REVIEW-EVIDENCE.md:1-26`, abbreviated) — one heading per head SHA, each containing a `review-checkpoint` block with the exact field order the template defines:

> `# Phase 85.1 — Review Evidence`
>
> Local checkpoint records (no PR yet), one heading per head SHA, using the
> template in `docs/review-checkpoint-record.md`. Durable copies of the PR
> comments are added here once the phase PR exists.
>
> `## Head cc33f15789952be15f5aa71023fe609929f76891`
>
> Fenced block starting `<!-- review-checkpoint head=cc33f15789952be15f5aa71023fe609929f76891 -->`, containing in order:
> - `### Commit identities` — a `| Field | Value |` table (PR head SHA, PR base SHA, tested SHA, Codex inspected head/base)
> - `### Classification` — the per-head JSON record, e.g. `{"schema":1,"head":"...","classification":"code",...}`
> - `### Risk note (RISK-01)` — `**Scope:**`, `**Risk:** low | moderate | high — ...`, `**Recommended review:**`, `**Required evidence:**`, `**What this recommendation cannot establish:**`
> - followed by `### Vibe-check (RISK-02)`, `### BM review`, `### Codex`, `### Greptile`, `### CI`, `### Dispositions`, `### Incomplete items`, each exactly as `docs/review-checkpoint-record.md`'s template defines them.

For Phase 86, the pilot record additionally needs (per CONTEXT D-15/D-16/D-10..14, Claude's Discretion on layout):
1. The D-15 retirement bar **quoted verbatim**, written before any comparison result exists (per the phase's own locked sequencing requirement).
2. A per-PR scorecard row (PILOT-01/D-10) for each of the 5 pilot PRs, condensing #48's and #36's multi-round records per D-11 ("not recorded" for missing fields, never estimated) — use `gh pr view 44 --comments`'s already-extracted shape (RESEARCH "Code Examples", reproduced below) as the row template:
```
BM review:    standard depth, complete — 0 critical, 0 warning, 1 new info (IN-05)
Codex:        complete, attempt 1, 0 findings, verdict "no-findings"
Greptile:     not run on this head (optional)
CI:           all required jobs success (run 40761276419); Review acceptance passed (attempt 2)
Review time / usage / owner effort: not recorded anywhere in the committed evidence
```
3. The PILOT-02 same-head comparison table (vibe-check vs. BM+Codex on the Refresh-counts PR's first head), judged by D-09's proof-based rule.
4. The two PILOT-03 decisions, recorded as the owner's own words (not Claude's summary), per this repository's standing "never infer approval" rule (`docs/owner-cli-acceptance.md`).

---

### `docs/review-workflow-adoption.md` (docs, new)

**Analog (primary):** `docs/bm-greptile-codex-blueprint.md` — process-narrative structure (`Decision` → `What is native and what remains manual` → `Target sequence` → diagram).
**Analog (secondary):** `docs/buildomator-greptile-pilot.md` — the GitHub-enforced-vs-instruction-enforced split this new doc must make explicit (D-18).

**Structure to copy from the blueprint** (`bm-greptile-codex-blueprint.md:1-23`, abbreviated):
```markdown
# Buildomator + Greptile + Codex review blueprint

Date: ...
Status: ...
Applies to: Triggarr first, then other repositories.

## Decision
<one or two paragraphs, imperative mood, naming the two or three tools kept>

## What is native and what remains manual
<bulleted list, each bullet naming one capability and whether it is
a GitHub-enforced check, an agent-run review, or a manual owner step>
```

**The GitHub-enforced-vs-instruction-enforced split to copy** (`buildomator-greptile-pilot.md:25-36`, the Activation checklist's framing — this is the exact distinction D-18 asks the new doc to make explicit for other repositories):
```markdown
- [x] Default-branch ruleset ... requires PRs, strict/current `CI ready`, `CodeQL`,
      and `Review acceptance` from their expected apps. ...
...
GitHub enforces approval and evidence presence; it cannot establish technical
correctness or user acceptance on its own.
```
For the new `docs/review-workflow-adoption.md`, split every requirement from this repository's review stack into exactly two buckets using this same declarative checklist voice:
- **GitHub-enforced** (ruleset required checks, the protected `review-acceptance` environment, branch protection, SHA-pinned actions) — true regardless of what any agent does.
- **Instruction-enforced** (BM code review depth, the paired Codex pass, the checkpoint-record template, vibe-check recommendations, triage discipline) — true only because `CLAUDE.md`/`docs/*.md` say so, and an agent not reading those files would skip them.

**What not to copy blindly (D-18):** explicitly list repository-specific pieces another repo should NOT copy verbatim — e.g. this repo's exact ruleset ID (`14805779`), the `greptile.json` free-tier posture, the solo-maintainer self-approval exception in the protected environment, and anything naming private infrastructure (NAS/Tailscale paths, per the 2026-10-21 published-history rule already in force for this public repository).

## Shared Patterns

### Per-item malformed-record screening (`_screen_queue`)
**Source:** `triggarr/search/engine.py:156-193`
**Apply to:** `refresh_radarr_counts`, `refresh_sonarr_counts`, `refresh_lidarr_counts` (all three, per D-02/D-02a)
```python
def _screen_queue(
    items: list, *, app_label: str, queue: str, tally: CycleTally,
    key_fields: tuple[str, ...] = (), nested_key: str | None = None,
    tags_at: tuple[str, ...] | None = None, date_fields: tuple[str, ...] = (),
) -> list[dict]:
    """Skip and count malformed records in one wanted queue, per item (ROBUST-01/04)."""
    valid: list[dict] = []
    skipped_by_reason: dict[str, list] = {}
    for item in items:
        reason = _malformed_reason(item, key_fields=key_fields, nested_key=nested_key,
                                     tags_at=tags_at, date_fields=date_fields)
        if reason is None:
            valid.append(item)
        else:
            skipped_by_reason.setdefault(reason, []).append(item)
    for reason, skipped in skipped_by_reason.items():
        _log_malformed_skip(app_label, queue, reason, skipped)
        tally.record_malformed(queue, len(skipped))
    return valid
```
Do not loosen its `tally: CycleTally` parameter to `Optional` (RESEARCH Pattern 1, option 2 — flagged less-preferred) — instantiate a throwaway local `CycleTally()` per `refresh_*_counts` call instead, matching Assumption A2.

### Boundary validation for persisted/untrusted data
**Source:** `triggarr/search/outcome.py:219-245` (`cycle_view`'s entry checks) and `triggarr/search/engine.py:109-153` (`_malformed_reason`)
**Apply to:** any new code reading `state.json` content or *arr API records — never trust shape, always `isinstance`-check before reading a field, return/skip rather than raise on a bad shape.

### Logging discipline (sanitized, structured, never raw exception text)
**Source:** `triggarr/search/engine.py:196-213` (`_log_malformed_skip`) and the existing `logger.warning(..., etype=type(exc).__name__)` calls throughout `refresh_*_counts`
**Apply to:** no new logging call is needed for the Refresh-counts fix (the reused `_screen_queue` already logs); if any new code path needs a log line, use `logger.warning("...", kwarg=value, ...)` with structured kwargs, never an f-string embedding exception text directly (CLAUDE.md's absolute "never log sensitive data" / "never expose stack traces" rules, already honored throughout this module).

### Test-name-as-contract convention
**Source:** every file in `tests/` sampled above — test function names state the exact behavior being locked (e.g. `test_cycle_view_malformed_by_queue_missing_singular`, `test_card_skip_only_partial_label_says_skipped_record`)
**Apply to:** the rewritten `test_refresh_*_malformed_*` tests — their names currently say `_returns_none`, which becomes false under D-02/D-02a; rename to state the new behavior (e.g. `..._skips_record_stays_connected`) rather than leaving a name that contradicts its own assertion.

### Review/checkpoint evidence template
**Source:** `docs/review-checkpoint-record.md` (full template) and `docs/review-classification-policy.md` (the per-head JSON classification record)
**Apply to:** every head of every one of the 5 new pilot-PR branches (Refresh-counts, card-template), and the Phase 86 PR itself — reuse the exact fenced-block template and field order; do not invent a new schema (RESEARCH "Don't Hand-Roll").

## No Analog Found

None. Every file in scope has an exact same-codebase or same-doc-family analog; RESEARCH.md's own "Don't Hand-Roll" table independently confirms this (every mechanism this phase needs already exists in this repository from Phases 79/80/82/83/85).

## Conventions

Derived via the shared deterministic module (`node bin/gsd-tools.cjs verify conventions --derive --scope triggarr`), repo-wide (Triggarr is a pure-Python codebase; the JS/TS-oriented axes below are reported as-is, with a Python-specific caveat noted).

| Axis | Dominant | Share | Entropy | Status |
|---|---|---|---|---|
| File-name casing | `camel`¹ | 77.4% | 0.609 | named contract |
| Identifier casing | — (mixed) | 43.2% | 0.784 | contested hotspot |
| Export style | — | — (0 samples) | — | insufficient data |
| Import style | — | — (0 samples) | — | insufficient data |

¹ The tool's generic "camel" bucket on a Python file set is measuring something coarser than true camelCase — Triggarr's actual, unambiguous file-naming convention (directly observable in every file read above: `engine.py`, `outcome.py`, `cycle_grade.html`, `test_refresh_counts.py`) is **snake_case**, the Python/PEP 8 norm. Follow snake_case for any new `.py`/test file in this phase; do not read "camel" as license to deviate.

Identifier casing is reported "contested" because the generic axis conflates three Python identifier *kinds* that each have their own named, non-contested convention observed in every file read above: classes are PascalCase (`CycleTally`, `_TagScope`), functions/variables/module-level names are snake_case (`cycle_view`, `refresh_sonarr_counts`, `malformed_by_queue`), and true module constants are CONSTANT_CASE (`GRADE_SUCCESS`, `QUEUES`, `_MAX_REASON_LENGTH`). This is PEP 8, applied consistently — not an unresolved repo-level disagreement. Follow the convention for the identifier's own kind (class vs. function/variable vs. constant), not the aggregate "contested" figure.

The two genuinely insufficient-data axes (export-style, import-style) are JS/TS/Go-oriented axes with zero applicable samples in this Python repository; Python's own import conventions were checked separately and are fully resolved repo-wide: `py-wildcard-import` is 100% `explicit` (no `from x import *` anywhere) and `py-import-relativity` is 100% `absolute` (`from triggarr.search.outcome import ...`, never a relative `from .outcome import ...`) — both already modeled in every import block excerpted above.

**Contested hotspots (author's choice):** this repository has no equivalent to the GSD tool's own prototype intentional-contested split — the CJS↔SDK dual resolver (`bin/lib/**` as CJS `module.exports`/`require`, `sdk/src/**` as ESM `export`/`import`) that the convention-derivation tooling itself uses as its reference example of a deliberately-split, locally-consistent, globally-contested convention. Triggarr has no such split: it is one Python package with one resolved import style throughout. No file in this phase's scope needs a "match the local directory's style" judgment call the way a contributor to the GSD tool's own `bin/` vs. `sdk/` trees would.

## Metadata

**Analog search scope:** `triggarr/search/engine.py`, `triggarr/search/outcome.py`, `triggarr/templates/partials/cycle_grade.html`, `tests/test_refresh_counts.py`, `tests/test_malformed_records_client_path.py`, `tests/test_outcome.py`, `tests/test_app_cards.py`, `docs/*.md`, `.planning/phases/85*/`.
**Files scanned:** 9 target files read in full or targeted-range; 6 additional docs/evidence files read for the two new-doc analogs; 1 convention-derivation tool run (repo-wide Python scope).
**Pattern extraction date:** 2026-10-30
