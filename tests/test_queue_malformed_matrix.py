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
from triggarr.models.config import GeneralConfig, InstanceConfig
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


async def _run(
    tmp_path, app: str, fake: _FakeArr, *, tagged_queue: str | None, prior: dict | None = None, settings=None
):
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
        result = await _CYCLES[app](client, state, "Default", config, settings or make_settings(), db)
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
# Dispatch-key type: an ID the client contract cannot take is a malformed record
# ---------------------------------------------------------------------------

# The search commands take JSON integers: RadarrClient.search_movies(list[int]),
# LidarrClient.search_albums(list[int]), SonarrClient.search_season(int, int).
# Booleans, fractional or integral floats, numeric strings, other strings,
# nulls and lists are not integers there, and must not be coerced into one.
_BAD_IDS = {
    "true": True,
    "false": False,
    "fraction": 2.5,
    "integral-float": 2.0,
    "numeric-string": "2",
    "string": "abc",
    "null": None,
    "list": [2],
}
# (app, field) pairs dispatch is keyed on.
_ID_FIELDS = [("radarr", "id"), ("lidarr", "id"), ("sonarr", "seriesId"), ("sonarr", "seasonNumber")]


def _dispatched(fake: _FakeArr) -> list:
    """Every search target POSTed, unsorted and uncoerced (Sonarr as (seriesId, seasonNumber))."""
    out: list = []
    for body in fake.posts:
        if "movieIds" in body:
            out += body["movieIds"]
        elif "albumIds" in body:
            out += body["albumIds"]
        elif "seriesId" in body:
            out.append((body["seriesId"], body["seasonNumber"]))
    return out


def _expected_targets(app: str, ids) -> list:
    return [(i, 1) for i in ids] if app == "sonarr" else list(ids)


@pytest.mark.parametrize("tagged", [False, True], ids=["untagged", "tag-scoped"])
@pytest.mark.parametrize("bad", list(_BAD_IDS))
@pytest.mark.parametrize("queue", QUEUES)
@pytest.mark.parametrize(("app", "field"), _ID_FIELDS, ids=[f"{a}-{f}" for a, f in _ID_FIELDS])
async def test_wrongly_typed_dispatch_id_skipped_per_item(tmp_path, app, field, queue, bad, tagged):
    """A record whose dispatch key is not an integer is skipped and counted once
    on its own queue: it is never sent to the *arr (so it can never become a
    failed command), never faults the rest of its queue, and the valid records
    in both queues are still searched."""
    bad_record = _record(app, 2)
    bad_record[field] = _BAD_IDS[bad]
    records = [_record(app, 1), bad_record, _record(app, 3)]
    fake = _FakeArr({queue: _page(records), _OTHER[queue]: _page(_other_queue_record(app))})

    ist = await _run(tmp_path, app, fake, tagged_queue=queue if tagged else None)
    rec = ist["last_cycle"]

    dispatched = _dispatched(fake)
    expected = _expected_targets(app, [1, 3, 90])
    assert len(dispatched) == len(expected)
    assert all(t in dispatched for t in expected), dispatched
    assert rec["malformed_by_queue"] == {queue: 1}
    assert rec["unevaluated"] == []
    assert rec["eligible"][queue] == 2
    assert rec["failed"] == 0
    assert rec["accepted"] == 3
    assert rec["grade"] == "partial"
    if queue == "missing" and app != "sonarr":
        assert ist["missing_monitored"] == 2
        assert ist["missing_eligible"] == 2


@pytest.mark.parametrize("queue", QUEUES)
@pytest.mark.parametrize("app", APPS)
async def test_supported_integer_ids_still_searched(tmp_path, app, queue):
    """Guardrail: integer IDs the clients accept are never screened out -- large
    IDs on every app, and Sonarr season 0 (specials are an ordinary key, D-09)."""
    big = 2**31 + 7
    if app == "sonarr":
        specials = _record(app, 2)
        specials["seasonNumber"] = 0
        large = _record(app, big)
        records = [_record(app, 1), specials, large]
        expected = [(1, 1), (2, 0), (big, 1), (90, 1)]
    else:
        records = [_record(app, 1), _record(app, big)]
        expected = [1, big, 90]
    fake = _FakeArr({queue: _page(records), _OTHER[queue]: _page(_other_queue_record(app))})

    ist = await _run(tmp_path, app, fake, tagged_queue=None)
    rec = ist["last_cycle"]

    assert sorted(_dispatched(fake)) == sorted(expected)
    assert rec["malformed_by_queue"] == {}
    assert rec["grade"] == "success"


# ---------------------------------------------------------------------------
# Timezone-less dates: malformed only where the queue's filter reads the date
# ---------------------------------------------------------------------------

# The filters that read dates compare them with an aware "now":
# filter_sonarr_episodes reads airDateUtc on both Sonarr queues, and
# filter_unreleased_movies reads digitalRelease and physicalRelease on the
# Radarr missing queue when skip_unreleased is on (the default). A parseable
# date without a UTC offset cannot be compared, and its timezone is not guessed.
_NAIVE = "2020-01-01T00:00:00"
_DATE_PATHS = [
    ("sonarr", "missing", "airDateUtc"),
    ("sonarr", "cutoff", "airDateUtc"),
    ("radarr", "missing", "digitalRelease"),
    ("radarr", "missing", "physicalRelease"),
]
# (records in the queue under test, records in the other queue, expected
# searched, eligible in the queue under test, grade per spec 3.1)
_NAIVE_SCENARIOS = {
    "mixed": ([1, "naive", 3], [90], [1, 3, 90], 2, "partial"),
    "only-malformed-other-queue-searched": (["naive"], [90], [90], 0, "partial"),
    "only-malformed-nothing-searched": (["naive"], [], [], 0, "failed"),
}


def _naive_record(app: str, field: str) -> dict:
    record = _record(app, 2)
    record[field] = _NAIVE
    return record


@pytest.mark.parametrize("scenario", list(_NAIVE_SCENARIOS))
@pytest.mark.parametrize(("app", "queue", "field"), _DATE_PATHS, ids=[f"{a}-{q}-{f}" for a, q, f in _DATE_PATHS])
async def test_naive_date_skipped_per_item(tmp_path, app, queue, field, scenario):
    """A record whose date lacks a UTC offset is skipped and counted once on its
    own queue; it never faults the queue, valid records are still searched, and
    the grade follows spec 3.1 (Partial with any accepted search, else Failed)."""
    queue_ids, other_ids, searched, eligible, grade = _NAIVE_SCENARIOS[scenario]
    records = [_naive_record(app, field) if rid == "naive" else _record(app, rid) for rid in queue_ids]
    other = [_record(app, rid, tags=()) for rid in other_ids]
    fake = _FakeArr({queue: _page(records), _OTHER[queue]: _page(other)})

    ist = await _run(tmp_path, app, fake, tagged_queue=None)
    rec = ist["last_cycle"]

    assert fake.searched() == searched
    assert rec["malformed_by_queue"] == {queue: 1}
    assert rec["unevaluated"] == []
    assert rec["eligible"][queue] == eligible
    assert rec["failed"] == 0
    assert rec["accepted"] == len(searched)
    assert rec["grade"] == grade


@pytest.mark.parametrize(
    ("digital", "physical", "searched", "malformed"),
    [
        ("2020-01-01T00:00:00Z", _NAIVE, [1, 2], {}),
        (_NAIVE, "2020-01-01T00:00:00+02:00", [1, 2], {}),
        (_NAIVE, "2999-01-01T00:00:00Z", [1], {"missing": 1}),
        ("2999-01-01T00:00:00Z", _NAIVE, [1], {"missing": 1}),
        (_NAIVE, None, [1], {"missing": 1}),
    ],
    ids=[
        "past-digital-decides", "past-physical-decides", "future-physical-cannot-decide",
        "future-digital-cannot-decide", "no-other-date",
    ],
)
async def test_radarr_one_valid_past_release_date_decides(tmp_path, digital, physical, searched, malformed):
    """skip_unreleased treats a movie as released when EITHER release date is in
    the past (v2.2, filter_unreleased_movies). A valid past date therefore
    decides eligibility without the other date, whichever field holds it, and a
    timezone-less other date is not read. Only when no valid date shows the
    movie released does the timezone-less date decide -- then it is malformed."""
    movie = _record("radarr", 2)
    movie["digitalRelease"] = digital
    movie["physicalRelease"] = physical
    fake = _FakeArr({"missing": _page([_record("radarr", 1), movie]), "cutoff": _page([])})

    ist = await _run(tmp_path, "radarr", fake, tagged_queue=None)
    rec = ist["last_cycle"]

    assert fake.searched() == searched
    assert rec["malformed_by_queue"] == malformed
    assert rec["unevaluated"] == []
    assert rec["grade"] == ("success" if not malformed else "partial")


@pytest.mark.parametrize("queue", QUEUES)
async def test_sonarr_existing_air_date_handling_unchanged(tmp_path, queue):
    """Guardrail: absent air dates (TBA) and future dates are still skipped
    without counting as malformed, unparseable text keeps its silent skip, and
    aware timestamps (Z or an explicit offset) are still searched."""
    variants = {
        1: "2020-01-01T00:00:00Z",
        2: "2020-01-01T00:00:00+05:00",
        3: None,
        4: "absent",
        5: "2999-01-01T00:00:00Z",
        6: "not a date",
    }
    records = []
    for rid, value in variants.items():
        record = _record("sonarr", rid)
        if value == "absent":
            del record["airDateUtc"]
        else:
            record["airDateUtc"] = value
        records.append(record)
    fake = _FakeArr({queue: _page(records), _OTHER[queue]: _page(_other_queue_record("sonarr"))})

    ist = await _run(tmp_path, "sonarr", fake, tagged_queue=None)
    rec = ist["last_cycle"]

    assert fake.searched() == [1, 2, 90]
    assert rec["malformed_by_queue"] == {}
    assert rec["grade"] == "success"


async def test_radarr_existing_release_date_handling_unchanged(tmp_path):
    """Guardrail: no release dates still passes through, aware past dates are
    released, and aware future dates are still skipped as unreleased, not as
    malformed."""
    both_absent = _record("radarr", 1)
    digital_past = _record("radarr", 2)
    digital_past["digitalRelease"] = "2020-01-01T00:00:00Z"
    physical_past = _record("radarr", 3)
    physical_past["physicalRelease"] = "2020-01-01T00:00:00+02:00"
    both_future = _record("radarr", 4)
    both_future["digitalRelease"] = "2999-01-01T00:00:00Z"
    both_future["physicalRelease"] = "2999-01-01T00:00:00Z"
    fake = _FakeArr({"missing": _page([both_absent, digital_past, physical_past, both_future]), "cutoff": _page([])})

    ist = await _run(tmp_path, "radarr", fake, tagged_queue=None)
    rec = ist["last_cycle"]

    assert fake.searched() == [1, 2, 3]
    assert rec["malformed_by_queue"] == {}
    assert rec["grade"] == "success"


@pytest.mark.parametrize(
    ("app", "queue", "field", "skip_unreleased"),
    [
        ("radarr", "cutoff", "digitalRelease", True),
        ("radarr", "missing", "digitalRelease", False),
        ("lidarr", "missing", "releaseDate", True),
        ("lidarr", "cutoff", "releaseDate", True),
    ],
)
async def test_naive_date_ignored_where_no_filter_reads_it(tmp_path, app, queue, field, skip_unreleased):
    """Guardrail: dates are validated only where a filter reads them -- not on
    Radarr cutoff, not on Radarr missing with skip_unreleased off, and never on
    Lidarr."""
    fake = _FakeArr({queue: _page([_record(app, 1), _naive_record(app, field)]), _OTHER[queue]: _page([])})
    settings = make_settings(general=GeneralConfig(skip_unreleased=skip_unreleased))

    ist = await _run(tmp_path, app, fake, tagged_queue=None, settings=settings)
    rec = ist["last_cycle"]

    assert fake.searched() == [1, 2]
    assert rec["malformed_by_queue"] == {}
    assert rec["grade"] == "success"


# ---------------------------------------------------------------------------
# Eligibility first: a field is validated only where the next step reads it
# ---------------------------------------------------------------------------

# Every queue drops unmonitored records before it reads anything else, and a
# record another safe check already excluded (out of tag scope, not yet aired,
# not yet released) never reaches the steps that read its other fields. Such a
# record must not be counted as malformed for a field nothing reads. A record
# that is not an object is still malformed: its eligibility cannot be read.
# (app, queue, kind, tag-scoped)
_UNREAD_CASES = [
    *[(app, queue, kind, False) for app in APPS for queue in QUEUES for kind in ("id-string", "id-missing")],
    *[(app, queue, "tags-null", True) for app in APPS for queue in QUEUES],
    ("sonarr", "missing", "nested-null", False),
    ("sonarr", "cutoff", "nested-null", False),
    ("lidarr", "missing", "nested-null", True),
    ("lidarr", "cutoff", "nested-null", True),
    ("sonarr", "missing", "naive-date", False),
    ("sonarr", "cutoff", "naive-date", False),
    ("radarr", "missing", "naive-date", False),
]


def _bad_record(app: str, rid: int, kind: str, *, monitored: bool) -> dict:
    record = _record(app, rid)
    record["monitored"] = monitored
    id_field = "seriesId" if app == "sonarr" else "id"
    if kind == "id-string":
        record[id_field] = "abc"
    elif kind == "id-missing":
        del record[id_field]
    elif kind == "tags-null":
        _set_tags(app, record, None)
    elif kind == "nested-null":
        record["series" if app == "sonarr" else "artist"] = None
    elif kind == "naive-date":
        record["airDateUtc" if app == "sonarr" else "digitalRelease"] = "2020-01-01T00:00:00"
    return record


def _ids(cases):
    return [f"{a}-{q}-{k}-{'tagged' if t else 'untagged'}" for a, q, k, t in cases]


@pytest.mark.parametrize(("app", "queue", "kind", "tagged"), _UNREAD_CASES, ids=_ids(_UNREAD_CASES))
async def test_unmonitored_malformed_record_not_counted(tmp_path, app, queue, kind, tagged):
    """An unmonitored record is dropped by the monitored check before any of its
    other fields are read, so it is never counted as malformed: valid records
    are searched, the grade stays Success and the monitored count excludes it."""
    records = [_record(app, 1), _bad_record(app, 2, kind, monitored=False), _record(app, 3)]
    fake = _FakeArr({queue: _page(records), _OTHER[queue]: _page(_other_queue_record(app))})

    ist = await _run(tmp_path, app, fake, tagged_queue=queue if tagged else None)
    rec = ist["last_cycle"]

    assert fake.searched() == [1, 3, 90]
    assert rec["malformed_by_queue"] == {}
    assert rec["unevaluated"] == []
    assert rec["eligible"][queue] == 2
    assert rec["grade"] == "success"
    if queue == "missing" and app != "sonarr":
        assert ist["missing_monitored"] == 2
        assert ist["missing_eligible"] == 2


@pytest.mark.parametrize(("app", "queue", "kind", "tagged"), _UNREAD_CASES, ids=_ids(_UNREAD_CASES))
async def test_monitored_malformed_record_still_counted_beside_unmonitored(tmp_path, app, queue, kind, tagged):
    """The same malformed shape on a MONITORED record is still skipped and
    counted once (the unmonitored copy is not), valid records are still
    searched, the grade is Partial, and the malformed record is not counted as
    monitored."""
    records = [
        _record(app, 1),
        _bad_record(app, 2, kind, monitored=True),
        _bad_record(app, 4, kind, monitored=False),
        _record(app, 3),
    ]
    fake = _FakeArr({queue: _page(records), _OTHER[queue]: _page(_other_queue_record(app))})

    ist = await _run(tmp_path, app, fake, tagged_queue=queue if tagged else None)
    rec = ist["last_cycle"]

    assert fake.searched() == [1, 3, 90]
    assert rec["malformed_by_queue"] == {queue: 1}
    assert rec["unevaluated"] == []
    assert rec["eligible"][queue] == 2
    assert rec["grade"] == "partial"
    if queue == "missing" and app != "sonarr":
        assert ist["missing_monitored"] == 2
        assert ist["missing_eligible"] == 2


@pytest.mark.parametrize("queue", QUEUES)
@pytest.mark.parametrize("app", APPS)
async def test_only_unmonitored_malformed_records_need_nothing(tmp_path, app, queue):
    """A queue holding nothing but unmonitored records with a bad ID has no
    work and nothing malformed to report: the cycle grades Nothing needed."""
    fake = _FakeArr({queue: _page([_bad_record(app, 2, "id-string", monitored=False)]), _OTHER[queue]: _page([])})

    ist = await _run(tmp_path, app, fake, tagged_queue=None)
    rec = ist["last_cycle"]

    assert fake.searched() == []
    assert rec["malformed_by_queue"] == {}
    assert rec["grade"] == "nothing_needed"


def _out_of_scope(app: str, rid: int) -> dict:
    """A monitored record whose tags exclude it from a tag-scoped queue."""
    return _set_tags(app, _record(app, rid), [])


@pytest.mark.parametrize(
    ("app", "queue", "tagged", "excluded", "expected_monitored"),
    [
        # Out of tag scope: tags are read, then nothing else.
        ("radarr", "missing", True, lambda: {**_out_of_scope("radarr", 2), "id": "abc"}, 3),
        ("radarr", "missing", True, lambda: {**_out_of_scope("radarr", 2), "digitalRelease": _NAIVE}, 3),
        ("radarr", "cutoff", True, lambda: {**_out_of_scope("radarr", 2), "id": "abc"}, None),
        ("lidarr", "missing", True, lambda: {**_out_of_scope("lidarr", 2), "id": "abc"}, 3),
        ("lidarr", "cutoff", True, lambda: {**_out_of_scope("lidarr", 2), "id": "abc"}, None),
        ("sonarr", "missing", True, lambda: {**_out_of_scope("sonarr", 2), "seriesId": "abc"}, None),
        ("sonarr", "cutoff", True, lambda: {**_out_of_scope("sonarr", 2), "seasonNumber": 1.5}, None),
        # Not yet released / aired: the date check excludes it before dispatch reads the ID.
        (
            "radarr", "missing", False,
            lambda: {**_record("radarr", 2), "id": "abc",
                     "digitalRelease": "2999-01-01T00:00:00Z", "physicalRelease": "2999-01-01T00:00:00Z"},
            3,
        ),
        ("sonarr", "missing", False, lambda: {**_record("sonarr", 2), "seriesId": "abc",
                                               "airDateUtc": "2999-01-01T00:00:00Z"}, None),
        ("sonarr", "cutoff", False, lambda: {**_record("sonarr", 2), "seriesId": None, "airDateUtc": None}, None),
    ],
    ids=[
        "radarr-missing-out-of-scope-bad-id", "radarr-missing-out-of-scope-naive-date",
        "radarr-cutoff-out-of-scope-bad-id", "lidarr-missing-out-of-scope-bad-id",
        "lidarr-cutoff-out-of-scope-bad-id", "sonarr-missing-out-of-scope-bad-series-id",
        "sonarr-cutoff-out-of-scope-fractional-season", "radarr-missing-unreleased-bad-id",
        "sonarr-missing-unaired-bad-series-id", "sonarr-cutoff-tba-null-series-id",
    ],
)
async def test_record_excluded_by_earlier_check_not_counted(
    tmp_path, app, queue, tagged, excluded, expected_monitored
):
    """A monitored record that an earlier safe check already excludes (tag
    scope, release date, air date) is never read for the fields only later
    steps use, so a bad ID or date on it is not counted as malformed. Saved
    counts keep their meaning: an out-of-scope or unreleased movie is still a
    monitored record, just not an eligible one."""
    records = [_record(app, 1), excluded(), _record(app, 3)]
    fake = _FakeArr({queue: _page(records), _OTHER[queue]: _page(_other_queue_record(app))})

    ist = await _run(tmp_path, app, fake, tagged_queue=queue if tagged else None)
    rec = ist["last_cycle"]

    assert fake.searched() == [1, 3, 90]
    assert rec["malformed_by_queue"] == {}
    assert rec["eligible"][queue] == 2
    assert rec["grade"] == "success"
    if expected_monitored is not None:
        assert ist["missing_monitored"] == expected_monitored
        assert ist["missing_eligible"] == 2


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
