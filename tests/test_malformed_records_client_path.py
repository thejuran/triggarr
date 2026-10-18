"""Non-object wanted records through the real client-to-engine path (ROBUST-01).

These tests drive the real Radarr/Sonarr/Lidarr clients over an httpx
MockTransport instead of mocking the client methods, so the page validation in
BaseClient.get_paginated is part of what is tested (PR #28 review: a guard
behind that validation never runs on real data).
"""

from __future__ import annotations

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
    """The default stays strict, so every other caller (count refresh included)
    behaves exactly as before."""
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


async def test_radarr_cycle_survives_malformed_tags_on_tag_scoped_missing_queue(tmp_path):
    """A Radarr movie whose `tags` is null on a tag-scoped missing queue must not
    raise out of the cycle (it used to: TypeError in the tag filter, the only
    Radarr chain without the malformed-data backstop). The missing queue is
    skipped and marked unevaluated, like every sibling chain, and the cutoff
    queue still searches its movie."""

    class _TaggedRadarr(_FakeArr):
        def handler(self, request: httpx.Request) -> httpx.Response:
            if request.method == "GET" and request.url.path == "/api/v3/tag":
                return httpx.Response(200, json=[{"id": 5, "label": "movies"}])
            return super().handler(request)

    fake = _TaggedRadarr({
        "missing": [
            {"id": 1, "title": "Good", "monitored": True, "tags": [5]},
            {"id": 2, "title": "Bad Tags", "monitored": True, "tags": None},
        ],
        "cutoff": [{"id": 3, "title": "Upgrade Me", "monitored": True, "tags": [5]}],
    })
    client = _client("radarr", fake)
    db = await aiosqlite.connect(tmp_path / "t.db")
    await init_db(db, tmp_path / "t.db")
    try:
        config = InstanceConfig(
            url="http://arr.test", api_key="test-key", enabled=True,
            search_missing_count=5, search_cutoff_count=5, missing_tag="movies",
        )
        result = await run_radarr_cycle(client, _state("radarr"), "Default", config, make_settings(), db)
    finally:
        await db.close()
        await client.close()

    rec = result["radarr"]["Default"]["last_cycle"]
    assert rec["unevaluated"] == [{"queue": "missing", "reason": "malformed data (TypeError)"}]
    assert rec["accepted"] == 1
    assert rec["grade"] == "partial"
    assert len(fake.posts) == 1


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
    assert state["lidarr"]["Default"]["connected"] is False
