"""Non-object wanted records through the real client-to-engine path (ROBUST-01).

These tests drive the real Radarr/Sonarr/Lidarr clients over an httpx
MockTransport instead of mocking the client methods, so the page validation in
BaseClient.get_paginated is part of what is tested (PR #28 review: a guard
behind that validation never runs on real data).
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

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
    refresh_radarr_counts,
    refresh_sonarr_counts,
    run_lidarr_cycle,
    run_radarr_cycle,
    run_sonarr_cycle,
)
from triggarr.state import _default_instance_state, _default_state

_GOOD = {
    "radarr": {"id": 1, "title": "Good Movie", "monitored": True},
    "sonarr": {
        "id": 100, "seriesId": 10, "seasonNumber": 1, "monitored": True,
        "airDateUtc": "2020-01-01T00:00:00Z", "series": {"title": "Good Show"},
    },
    "lidarr": {"id": 1, "title": "Good Album", "monitored": True},
}
_CLIENTS = {"radarr": RadarrClient, "sonarr": SonarrClient, "lidarr": LidarrClient}
_CYCLES = {"radarr": run_radarr_cycle, "sonarr": run_sonarr_cycle, "lidarr": run_lidarr_cycle}
_REFRESH = {"radarr": refresh_radarr_counts, "sonarr": refresh_sonarr_counts, "lidarr": refresh_lidarr_counts}


def _page(records: list, *, page: int = 1, page_size: int = 50, total: int | None = None) -> dict:
    return {
        "page": page, "pageSize": page_size, "sortKey": "id",
        "totalRecords": len(records) if total is None else total, "records": records,
    }


class _FakeArr:
    """Minimal *arr HTTP stand-in: wanted pages from `wanted`, records every POST."""

    def __init__(self, wanted: dict[str, list]):
        self.wanted = wanted
        self.posts: list[dict] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if request.method == "POST":
            self.posts.append({"path": path, "body": request.read().decode()})
            return httpx.Response(201, json={"id": 1, "status": "queued"})
        for queue in ("missing", "cutoff"):
            if path.endswith(f"/wanted/{queue}"):
                return httpx.Response(200, json=_page(self.wanted.get(queue, [])))
        if path == "/api/v3/movie":
            return httpx.Response(200, json=_page([], total=0))
        return httpx.Response(200, json=[])


def _client(app: str, fake: _FakeArr):
    client = _CLIENTS[app]("http://arr.test", SecretStr("test-key"))
    client._client = httpx.AsyncClient(
        base_url="http://arr.test", transport=httpx.MockTransport(fake.handler)
    )
    return client


def _state(app: str) -> dict:
    state = _default_state()
    state[app] = {"Default": _default_instance_state()}
    return state


# ---------------------------------------------------------------------------
# Client layer
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("app", ["radarr", "sonarr", "lidarr"])
async def test_wanted_fetch_keeps_non_object_records_when_allowed(app):
    """With allow_non_object_records=True the wanted fetch returns the page's
    records as-is (null and string included) instead of rejecting the page."""
    fake = _FakeArr({"missing": [_GOOD[app], None, "junk"], "cutoff": [None, _GOOD[app]]})
    client = _client(app, fake)
    try:
        missing = await client.get_wanted_missing(allow_non_object_records=True)
        cutoff = await client.get_wanted_cutoff(allow_non_object_records=True)
    finally:
        await client.close()
    assert missing == [_GOOD[app], None, "junk"]
    assert cutoff == [None, _GOOD[app]]


@pytest.mark.parametrize("app", ["radarr", "sonarr", "lidarr"])
async def test_wanted_fetch_default_still_rejects_non_object_records(app):
    """The default stays strict, so a caller that never opts in to
    ``allow_non_object_records`` behaves exactly as before (D-02/D-02a: count
    refresh now opts in, same as the scheduled cycles)."""
    fake = _FakeArr({"missing": [_GOOD[app], None]})
    client = _client(app, fake)
    try:
        with pytest.raises(pydantic.ValidationError):
            await client.get_wanted_missing()
    finally:
        await client.close()


async def test_get_paginated_non_object_records_paginate_by_raw_count():
    """Non-object records still count toward page length, so pagination stops
    after exactly the pages the server reports."""
    calls: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        page = int(request.url.params["page"])
        calls.append(page)
        records = [{"id": 1}, None] if page == 1 else [{"id": 2}]
        return httpx.Response(200, json=_page(records, page=page, page_size=2, total=3))

    client = RadarrClient("http://arr.test", SecretStr("test-key"), page_size=2)
    client._client = httpx.AsyncClient(base_url="http://arr.test", transport=httpx.MockTransport(handler))
    try:
        records = await client.get_paginated("/api/v3/wanted/missing", allow_non_object_records=True)
    finally:
        await client.close()
    assert records == [{"id": 1}, None, {"id": 2}]
    assert calls == [1, 2]


# ---------------------------------------------------------------------------
# Client to engine: one bad record is skipped and counted, the rest is searched
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("queue", ["missing", "cutoff"])
@pytest.mark.parametrize("app", ["radarr", "sonarr", "lidarr"])
async def test_cycle_skips_non_object_record_from_real_client(tmp_path, app, queue):
    """A null record in a real wanted response is skipped and counted against
    its queue; the good record in the same page is still searched and the
    instance stays connected (it is not marked unreachable)."""
    fake = _FakeArr({queue: [_GOOD[app], None]})
    client = _client(app, fake)
    db = await aiosqlite.connect(tmp_path / "t.db")
    await init_db(db, tmp_path / "t.db")
    try:
        config = InstanceConfig(
            url="http://arr.test", api_key="test-key", enabled=True,
            search_missing_count=5, search_cutoff_count=5,
        )
        result = await _CYCLES[app](client, _state(app), "Default", config, make_settings(), db)
    finally:
        await db.close()
        await client.close()

    ist = result[app]["Default"]
    rec = ist["last_cycle"]
    assert ist["connected"] is True
    assert rec["fetch_error"] is None
    assert rec["malformed_by_queue"] == {queue: 1}
    assert rec["accepted"] == 1
    assert rec["unevaluated"] == []
    assert rec["grade"] == "partial"
    assert len(fake.posts) == 1


class _TaggedRadarr(_FakeArr):
    """Fake Radarr that also serves one tag, so a queue can be tag-scoped."""

    def handler(self, request: httpx.Request) -> httpx.Response:
        if request.method == "GET" and request.url.path == "/api/v3/tag":
            return httpx.Response(200, json=[{"id": 5, "label": "movies"}])
        return super().handler(request)


def _searched_movie_ids(fake: _FakeArr) -> list[int]:
    return sorted(i for post in fake.posts for i in json.loads(post["body"]).get("movieIds", []))


def _seeded_radarr_state(monitored: int, eligible: int) -> dict:
    state = _state("radarr")
    state["radarr"]["Default"]["missing_monitored"] = monitored
    state["radarr"]["Default"]["missing_eligible"] = eligible
    return state


_TAG_SCOPED_RADARR = InstanceConfig(
    url="http://arr.test", api_key="test-key", enabled=True,
    search_missing_count=5, search_cutoff_count=5, missing_tag="movies",
)


async def test_radarr_cycle_skips_malformed_tags_per_item_on_tag_scoped_missing_queue(tmp_path):
    """On a tag-scoped Radarr missing queue, a movie whose `tags` is not a list
    (null here) is skipped and counted on its own: the valid tagged movies in the
    same page are still searched, the queue is not marked unevaluated, and the
    malformed movie is counted in malformed_by_queue rather than as monitored."""
    fake = _TaggedRadarr({
        "missing": [
            {"id": 1, "title": "Good", "monitored": True, "tags": [5]},
            {"id": 2, "title": "Bad Tags", "monitored": True, "tags": None},
            {"id": 3, "title": "Good Too", "monitored": True, "tags": [5]},
            {"id": 4, "title": "Untagged", "monitored": True, "tags": []},
        ],
        "cutoff": [{"id": 30, "title": "Upgrade Me", "monitored": True, "tags": [5]}],
    })
    client = _client("radarr", fake)
    db = await aiosqlite.connect(tmp_path / "t.db")
    await init_db(db, tmp_path / "t.db")
    try:
        result = await run_radarr_cycle(
            client, _seeded_radarr_state(1, 1), "Default", _TAG_SCOPED_RADARR, make_settings(), db
        )
    finally:
        await db.close()
        await client.close()

    ist = result["radarr"]["Default"]
    rec = ist["last_cycle"]
    assert _searched_movie_ids(fake) == [1, 3, 30]
    assert rec["unevaluated"] == []
    assert rec["malformed_by_queue"] == {"missing": 1}
    assert rec["grade"] == "partial"
    assert ist["missing_monitored"] == 3  # Good, Good Too, Untagged -- not the malformed movie
    assert ist["missing_eligible"] == 2


async def test_radarr_missing_chain_fault_keeps_previous_counts(tmp_path, monkeypatch):
    """If the Radarr missing chain still faults part-way (an unexpected shape),
    the backstop must leave the previous monitored/eligible counts untouched, not
    a fresh monitored count next to a stale eligible count (which the card would
    show as a false 'N skipped')."""
    import triggarr.search.engine as engine

    def _boom(*_args, **_kwargs):
        raise TypeError("unexpected shape")

    monkeypatch.setattr(engine, "filter_by_tag", _boom)
    fake = _TaggedRadarr({
        "missing": [
            {"id": 1, "title": "Good", "monitored": True, "tags": [5]},
            {"id": 3, "title": "Good Too", "monitored": True, "tags": [5]},
            {"id": 4, "title": "Untagged", "monitored": True, "tags": []},
        ],
    })
    client = _client("radarr", fake)
    db = await aiosqlite.connect(tmp_path / "t.db")
    await init_db(db, tmp_path / "t.db")
    try:
        result = await run_radarr_cycle(
            client, _seeded_radarr_state(1, 1), "Default", _TAG_SCOPED_RADARR, make_settings(), db
        )
    finally:
        await db.close()
        await client.close()

    ist = result["radarr"]["Default"]
    assert ist["last_cycle"]["unevaluated"] == [{"queue": "missing", "reason": "malformed data (TypeError)"}]
    assert ist["missing_monitored"] == 1
    assert ist["missing_eligible"] == 1
    assert fake.posts == []


@pytest.mark.parametrize("app", ["radarr", "sonarr", "lidarr"])
async def test_refresh_counts_skips_non_object_record(app):
    """Resolves the PR #28 follow-up (D-02/D-02a): Refresh counts now fetches
    with ``allow_non_object_records=True``, the same as the scheduled cycles,
    so a null wanted record reaches per-item screening (_screen_queue) instead
    of rejecting the whole page -- the instance stays connected and the good
    record in the same page is still counted. This test drives the real
    Radarr/Sonarr/Lidarr client over httpx.MockTransport, so the fetch flag is
    part of what's tested here, not just the screening."""
    fake = _FakeArr({"missing": [_GOOD[app], None], "cutoff": [None, _GOOD[app]]})
    client = _client(app, fake)
    state = _state(app)
    try:
        config = InstanceConfig(url="http://arr.test", api_key="test-key", enabled=True)
        result = await _REFRESH[app](client, state, "Default", config, make_settings())
    finally:
        await client.close()
    assert result is not None
    ist = state[app]["Default"]
    assert ist["connected"] is True
    assert ist["unreachable_since"] is None
    assert ist["missing_eligible"] == 1


class _BadEnvelopeArr(_FakeArr):
    """Fake *arr that serves an invalid wanted-list envelope (missing totalRecords)."""

    def handler(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if request.method == "GET" and ("/wanted/missing" in path or "/wanted/cutoff" in path):
            return httpx.Response(200, json={"page": 1, "pageSize": 50, "sortKey": "id", "records": []})
        return super().handler(request)


class _ServerErrorArr(_FakeArr):
    """Fake *arr that returns HTTP 500 for every wanted-list request."""

    def handler(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if request.method == "GET" and ("/wanted/missing" in path or "/wanted/cutoff" in path):
            return httpx.Response(500)
        return super().handler(request)


@pytest.mark.parametrize("app", ["radarr", "sonarr", "lidarr"])
async def test_refresh_counts_invalid_envelope_still_disconnects(app):
    """Guard (pins the fetch-failure contract, D-02/D-02a): enabling
    allow_non_object_records does not widen it -- an invalid wanted-list
    envelope (the ``RawPaginatedResponse`` fields themselves, not a record)
    still disconnects the instance and returns None."""
    fake = _BadEnvelopeArr({})
    client = _client(app, fake)
    state = _state(app)
    try:
        config = InstanceConfig(url="http://arr.test", api_key="test-key", enabled=True)
        result = await _REFRESH[app](client, state, "Default", config, make_settings())
    finally:
        await client.close()
    assert result is None
    assert state[app]["Default"]["connected"] is False


@pytest.mark.parametrize("app", ["radarr", "sonarr", "lidarr"])
async def test_refresh_counts_http_error_still_disconnects(app):
    """Guard (pins the fetch-failure contract, D-02/D-02a): an HTTP error from
    the wanted endpoint still disconnects the instance and returns None."""
    fake = _ServerErrorArr({})
    client = _client(app, fake)
    state = _state(app)
    try:
        config = InstanceConfig(url="http://arr.test", api_key="test-key", enabled=True)
        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await _REFRESH[app](client, state, "Default", config, make_settings())
    finally:
        await client.close()
    assert result is None
    assert state[app]["Default"]["connected"] is False
