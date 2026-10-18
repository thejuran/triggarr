"""Six-path malformed-record matrix through the real clients (ROBUST-01).

Each test drives run_radarr_cycle / run_sonarr_cycle / run_lidarr_cycle with
the real RadarrClient / SonarrClient / LidarrClient over an httpx
MockTransport, so client parsing, page validation, filtering, dispatch and
state updates are all exercised. The queue under test is tag-scoped where the
case needs it; the other queue holds one valid record (id 90) and is untagged,
so it also shows that the unaffected queue keeps working.

Contract (spec 4 Phase 80, ROBUST-01, cycle grading 3.1):
1. one malformed record does not stop valid records in the same queue;
2. malformed records are skipped and counted per queue, grading Partial;
3. a fault never leaves partially updated counts;
4. tag scoping, dedup, searched-log and dispatch semantics are unchanged;
5. a whole-response or transport failure is still a failed fetch, never an
   empty successful queue.
"""

from __future__ import annotations

import json

import aiosqlite
import httpx
import pytest
from pydantic import SecretStr

import triggarr.clients.base as client_base
import triggarr.search.engine as engine
from tests.conftest import make_settings
from triggarr.clients.lidarr import LidarrClient
from triggarr.clients.radarr import RadarrClient
from triggarr.clients.sonarr import SonarrClient
from triggarr.db import init_db
from triggarr.models.config import InstanceConfig
from triggarr.state import _default_instance_state, _default_state

APPS = ["radarr", "sonarr", "lidarr"]
QUEUES = ["missing", "cutoff"]
_CLIENTS = {"radarr": RadarrClient, "sonarr": SonarrClient, "lidarr": LidarrClient}
_CYCLES = {"radarr": engine.run_radarr_cycle, "sonarr": engine.run_sonarr_cycle, "lidarr": engine.run_lidarr_cycle}
_TAG_ID = 5
_OTHER = {"missing": "cutoff", "cutoff": "missing"}
# Counts each app persists for a queue (only these are asserted for "unchanged").
_STORED_COUNTS = {
    ("radarr", "missing"): ("missing_monitored", "missing_eligible"),
    ("radarr", "cutoff"): (),
    ("sonarr", "missing"): ("missing_eligible", "missing_searchable"),
    ("sonarr", "cutoff"): ("cutoff_searchable",),
    ("lidarr", "missing"): ("missing_monitored", "missing_eligible"),
    ("lidarr", "cutoff"): (),
}


def _record(app: str, rid: int, *, tags=(_TAG_ID,)) -> dict:
    """A valid wanted record for `app` with id `rid` carrying `tags`."""
    tag_list = list(tags)
    if app == "radarr":
        return {"id": rid, "title": f"Movie {rid}", "monitored": True, "tags": tag_list}
    if app == "sonarr":
        return {
            "id": rid, "seriesId": rid, "seasonNumber": 1, "monitored": True,
            "airDateUtc": "2020-01-01T00:00:00Z", "series": {"title": f"Show {rid}", "tags": tag_list},
        }
    return {"id": rid, "title": f"Album {rid}", "monitored": True, "artist": {"tags": tag_list}}


def _set_tags(app: str, record: dict, value) -> dict:
    """Put a raw `tags` value where `app` keeps it (top level or nested)."""
    if app == "radarr":
        record["tags"] = value
    else:
        record["series" if app == "sonarr" else "artist"]["tags"] = value
    return record


def _drop_id(app: str, record: dict) -> dict:
    """Remove the key each app's dispatch is keyed on."""
    record.pop("seriesId" if app == "sonarr" else "id")
    return record


def _page(records) -> dict:
    return {"page": 1, "pageSize": 50, "sortKey": "id", "totalRecords": len(records), "records": records}


class _FakeArr:
    """Minimal *arr over MockTransport: per-queue pages, one tag, records POSTs."""

    def __init__(self, pages: dict):
        self.pages = pages
        self.posts: list[dict] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if request.method == "POST":
            self.posts.append(json.loads(request.read() or b"{}"))
            return httpx.Response(201, json={"id": 1, "status": "queued"})
        if path.endswith("/tag"):
            return httpx.Response(200, json=[{"id": _TAG_ID, "label": "scope"}])
        for queue in QUEUES:
            if path.endswith(f"/wanted/{queue}"):
                body = self.pages.get(queue, _page([]))
                if isinstance(body, httpx.Response):
                    return body
                return httpx.Response(200, json=body)
        if path == "/api/v3/movie":
            return httpx.Response(200, json=_page([]))
        return httpx.Response(200, json=[])

    def searched(self) -> list:
        ids: list = []
        for body in self.posts:
            if "movieIds" in body:
                ids += body["movieIds"]
            elif "albumIds" in body:
                ids += body["albumIds"]
            elif "seriesId" in body:
                ids.append(body["seriesId"])
        return sorted(ids)


async def _run(tmp_path, app: str, fake: _FakeArr, *, tagged_queue: str | None, prior: dict | None = None):
    client = _CLIENTS[app]("http://arr.test", SecretStr("test-key"))
    client._client = httpx.AsyncClient(base_url="http://arr.test", transport=httpx.MockTransport(fake.handler))
    state = _default_state()
    ist = _default_instance_state()
    ist.update(prior or {})
    state[app] = {"Default": ist}
    tags = {f"{tagged_queue}_tag": "scope"} if tagged_queue else {}
    config = InstanceConfig(
        url="http://arr.test", api_key="test-key", enabled=True,
        search_missing_count=5, search_cutoff_count=5, **tags,
    )
    db = await aiosqlite.connect(tmp_path / "t.db")
    await init_db(db, tmp_path / "t.db")
    try:
        result = await _CYCLES[app](client, state, "Default", config, make_settings(), db)
    finally:
        await db.close()
        await client.close()
    return result[app]["Default"]


def _other_queue_record(app: str) -> list:
    return [_record(app, 90, tags=())]


# ---------------------------------------------------------------------------
# 1 + 2: one malformed record is skipped and counted; valid records still searched
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("bad_tags", [None, "5"], ids=["null-tags", "string-tags"])
@pytest.mark.parametrize("queue", QUEUES)
@pytest.mark.parametrize("app", APPS)
async def test_non_list_tags_skipped_per_item(tmp_path, app, queue, bad_tags):
    records = [_record(app, 1), _set_tags(app, _record(app, 2), bad_tags), _record(app, 3)]
    fake = _FakeArr({queue: _page(records), _OTHER[queue]: _page(_other_queue_record(app))})

    ist = await _run(tmp_path, app, fake, tagged_queue=queue)
    rec = ist["last_cycle"]

    assert fake.searched() == [1, 3, 90]
    assert rec["malformed_by_queue"] == {queue: 1}
    assert rec["unevaluated"] == []
    assert rec["eligible"][queue] == 2
    assert rec["grade"] == "partial"


@pytest.mark.parametrize("queue", QUEUES)
@pytest.mark.parametrize("app", APPS)
async def test_record_without_dispatch_key_skipped_per_item(tmp_path, app, queue):
    """A record missing the key dispatch is keyed on (Radarr/Lidarr `id`, Sonarr
    `seriesId`) is skipped and counted -- it neither crashes the cycle nor
    disappears silently with a Success grade."""
    records = [_record(app, 1), _drop_id(app, _record(app, 2)), _record(app, 3)]
    fake = _FakeArr({queue: _page(records), _OTHER[queue]: _page(_other_queue_record(app))})

    ist = await _run(tmp_path, app, fake, tagged_queue=None)
    rec = ist["last_cycle"]

    assert fake.searched() == [1, 3, 90]
    assert rec["malformed_by_queue"] == {queue: 1}
    assert rec["unevaluated"] == []
    assert rec["eligible"][queue] == 2
    assert rec["grade"] == "partial"


@pytest.mark.parametrize("queue", QUEUES)
@pytest.mark.parametrize("app", APPS)
async def test_non_object_record_skipped_per_item(tmp_path, app, queue):
    """Guardrail (already handled by c6947fe): a null record in the page."""
    records = [_record(app, 1), None, _record(app, 3)]
    fake = _FakeArr({queue: _page(records), _OTHER[queue]: _page(_other_queue_record(app))})

    ist = await _run(tmp_path, app, fake, tagged_queue=None)
    rec = ist["last_cycle"]

    assert fake.searched() == [1, 3, 90]
    assert rec["malformed_by_queue"] == {queue: 1}
    assert rec["eligible"][queue] == 2
    assert rec["grade"] == "partial"


@pytest.mark.parametrize("queue", QUEUES)
@pytest.mark.parametrize("app", ["sonarr", "lidarr"])
async def test_null_nested_object_skipped_per_item(tmp_path, app, queue):
    """Guardrail: null `series` (Sonarr) / `artist` (Lidarr, tag-scoped) is
    skipped per item."""
    bad = _record(app, 2)
    bad["series" if app == "sonarr" else "artist"] = None
    records = [_record(app, 1), bad, _record(app, 3)]
    fake = _FakeArr({queue: _page(records), _OTHER[queue]: _page(_other_queue_record(app))})

    ist = await _run(tmp_path, app, fake, tagged_queue=queue)
    rec = ist["last_cycle"]

    assert fake.searched() == [1, 3, 90]
    assert rec["malformed_by_queue"] == {queue: 1}
    assert rec["eligible"][queue] == 2


# ---------------------------------------------------------------------------
# Truthful saved counts: a skipped malformed record is not a monitored record
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("app", ["radarr", "lidarr"])
async def test_malformed_record_not_counted_as_monitored(tmp_path, app):
    """missing_monitored counts monitored records that were actually evaluated,
    so it never includes a record skipped as malformed (the card derives its
    'N skipped' label from missing_monitored - missing_eligible)."""
    bad = _record(app, 2)
    if app == "lidarr":
        bad["artist"] = None
    else:
        bad["tags"] = None
    records = [_record(app, 1), bad, _record(app, 3)]
    fake = _FakeArr({"missing": _page(records), "cutoff": _page([])})

    ist = await _run(tmp_path, app, fake, tagged_queue="missing")

    assert ist["missing_monitored"] == 2
    assert ist["missing_eligible"] == 2


# ---------------------------------------------------------------------------
# 3: a fault after partial processing leaves the previous counts untouched
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("queue", QUEUES)
@pytest.mark.parametrize("app", APPS)
async def test_fault_after_partial_processing_keeps_previous_counts(tmp_path, app, queue, monkeypatch):
    def _boom(*_args, **_kwargs):
        raise TypeError("unexpected shape")

    monkeypatch.setattr(engine, "filter_by_tag", _boom)
    prior = {key: 1 for key in _STORED_COUNTS[(app, queue)]}
    fake = _FakeArr({queue: _page([_record(app, 1), _record(app, 3)]), _OTHER[queue]: _page(_other_queue_record(app))})

    ist = await _run(tmp_path, app, fake, tagged_queue=queue, prior=prior)
    rec = ist["last_cycle"]

    assert rec["unevaluated"] == [{"queue": queue, "reason": "malformed data (TypeError)"}]
    assert {key: ist[key] for key in prior} == prior
    assert fake.searched() == [90]
    assert rec["grade"] == "partial"


# ---------------------------------------------------------------------------
# 5: whole-response and transport failures stay failures
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("app", APPS)
async def test_malformed_page_envelope_is_a_failed_fetch(tmp_path, app):
    """Guardrail: a page whose `records` is not a list is a failed fetch
    (instance unreachable, cycle Failed), never an empty successful queue."""
    bad_page = {"page": 1, "pageSize": 50, "sortKey": "id", "totalRecords": 1, "records": None}
    fake = _FakeArr({"missing": bad_page, "cutoff": _page([])})

    ist = await _run(tmp_path, app, fake, tagged_queue=None)
    rec = ist["last_cycle"]

    assert ist["connected"] is False
    assert rec["grade"] == "failed"
    assert rec["fetch_error"]
    assert fake.posts == []


@pytest.mark.parametrize("app", APPS)
async def test_transport_failure_is_a_failed_fetch(tmp_path, app, monkeypatch):
    """Guardrail: an HTTP failure on an active wanted queue is a failed fetch."""

    async def _no_sleep(_seconds):
        return None

    monkeypatch.setattr(client_base.asyncio, "sleep", _no_sleep)
    fake = _FakeArr({"missing": httpx.Response(500), "cutoff": _page([])})

    ist = await _run(tmp_path, app, fake, tagged_queue=None)
    rec = ist["last_cycle"]

    assert ist["connected"] is False
    assert rec["grade"] == "failed"
    assert rec["fetch_error"]
    assert fake.posts == []
