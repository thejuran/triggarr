"""Real Sonarr-client-path fixture regressions for grab attribution (Phase 81, D-12).

These are fixture regressions, not live evidence: a real ``SonarrClient``
talks over ``httpx.MockTransport`` to sanitized fixture records
(``tests/fixtures/sonarr/``, each labelled ``live_evidence: false``). They
prove the production parsing, identity-gate, season-match and
ownership-accumulation code handles these response shapes correctly end to
end (``SonarrClient.get_grab_history`` -> ``GrabEvent`` validation ->
``run_tracking_check``). They do not substitute for the live v4/v5
verification required by SONARRV5-02.

``history_standard_v4`` is synthesized from the Sonarr v3 OpenAPI schema.
``history_season_pack_nested_synth``, ``history_multi_season_pack_nested_synth``
and ``history_alternate_order_nested_synth`` are also synthesized -- they
model the pre-v5 nested ``episode`` shape, and cover the multi-season-pack
and alternate-order scenarios that the v5 sandbox cannot produce.
``history_season_pack_v5`` and ``episodes_v5`` are a sanitized, live-captured
real Sonarr v5 response confirming v5 omits that nested object entirely.
"""

from __future__ import annotations

import copy
from datetime import UTC, datetime, timedelta

import aiosqlite
import httpx
from loguru import logger
from pydantic import SecretStr

from tests.sonarr_fixtures import load_sonarr_fixture, load_sonarr_series_episode_list
from triggarr import tracking as tracking_module
from triggarr.clients.sonarr import SonarrClient
from triggarr.db import get_owned_grabs, init_db, insert_search_entry
from triggarr.tracking import run_tracking_check

# Far larger than any gap between the fixtures' synthesized dates (all
# within a few days of each other) and small enough to stay well inside
# datetime's range -- these tests only need the grab date to fall between
# the search timestamp and the window end; a fully-resolved outcome
# ("grabbed") never consults window_expired at all.
_WIDE_WINDOW = 999_999


class _SonarrHistoryFake:
    """Serves fixture grab-history, series-episode-list and per-episode records.

    ``series_episode_lists``/``episodes`` key the v5 episode-identity
    resolution endpoints (``GET /api/v3/episode?seriesId=X`` and
    ``GET /api/v3/episode/{id}``). An unconfigured series' episode list
    defaults to an empty 200 (Sonarr always returns an array for a real
    series), so resolution falls through to the per-id endpoint, which
    defaults to 404 for an unconfigured id -- a realistic "deleted or
    moved episode" shape, never a fake-harness artifact. Override hooks
    force a status code, raise an exception (e.g. a transport error), or
    replace the response body, keyed by seriesId (list) / episodeId
    (per-id). Every request is recorded for request-volume assertions.
    """

    def __init__(
        self,
        records_by_series: dict[int, list[dict]],
        *,
        series_episode_lists: dict[int, list[dict]] | None = None,
        episodes: dict[int, dict] | None = None,
    ) -> None:
        self.records_by_series = records_by_series
        self.series_episode_lists = series_episode_lists or {}
        self.episodes = episodes or {}
        self.requests: list[httpx.Request] = []
        self.list_status: dict[int, int] = {}
        self.list_exception: dict[int, Exception] = {}
        self.list_body_override: dict[int, object] = {}
        self.episode_status: dict[int, int] = {}
        self.episode_exception: dict[int, Exception] = {}
        self.episode_body_override: dict[int, object] = {}

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        path = request.url.path

        if path == "/api/v3/history/series":
            series_id = int(request.url.params["seriesId"])
            records = self.records_by_series.get(series_id, [])
            return httpx.Response(200, json=records)

        if path == "/api/v3/episode":
            series_id = int(request.url.params["seriesId"])
            if series_id in self.list_exception:
                raise self.list_exception[series_id]
            if series_id in self.list_body_override:
                return httpx.Response(self.list_status.get(series_id, 200), json=self.list_body_override[series_id])
            status = self.list_status.get(series_id, 200)
            if status != 200:
                return httpx.Response(status, json={"error": "error"})
            return httpx.Response(200, json=self.series_episode_lists.get(series_id, []))

        if path.startswith("/api/v3/episode/"):
            episode_id = int(path.rsplit("/", 1)[-1])
            if episode_id in self.episode_exception:
                raise self.episode_exception[episode_id]
            if episode_id in self.episode_body_override:
                return httpx.Response(
                    self.episode_status.get(episode_id, 200), json=self.episode_body_override[episode_id]
                )
            status = self.episode_status.get(episode_id, 200)
            if status != 200:
                return httpx.Response(status, json={"error": "error"})
            if episode_id in self.episodes:
                return httpx.Response(200, json=self.episodes[episode_id])
            return httpx.Response(404, json={"error": "not found"})

        return httpx.Response(404, json={"error": "not found"})


def _list_requests(fake: _SonarrHistoryFake) -> list[httpx.Request]:
    """Requests to the series-episode-list endpoint."""
    return [r for r in fake.requests if r.url.path == "/api/v3/episode"]


def _per_id_requests(fake: _SonarrHistoryFake) -> list[httpx.Request]:
    """Requests to the per-episode-id endpoint."""
    return [r for r in fake.requests if r.url.path.startswith("/api/v3/episode/")]


def _shift_records(records: list[dict], delta: timedelta) -> list[dict]:
    """Deep-copy records with every ``date`` shifted by delta.

    Derived from the live capture, dates shifted -- relative spacing
    between records is preserved so the scenario still looks like one
    real grab event (or batch of events) relative to each other.
    """
    shifted = []
    for r in records:
        r2 = copy.deepcopy(r)
        dt = datetime.fromisoformat(r2["date"].replace("Z", "+00:00")) + delta
        r2["date"] = dt.isoformat().replace("+00:00", "Z")
        shifted.append(r2)
    return shifted


def _assert_grab_in_window(records: list[dict], search_time: datetime, window_minutes: int) -> None:
    """Sanity-check that at least one served grab date lies inside the search's window."""
    window_end = search_time + timedelta(minutes=window_minutes)
    assert any(
        search_time <= datetime.fromisoformat(r["date"].replace("Z", "+00:00")) <= window_end for r in records
    ), "fixture setup error: no served grab date lies inside the seeded search's window"


def _client(fake: _SonarrHistoryFake) -> SonarrClient:
    client = SonarrClient("http://sonarr.test", SecretStr("test-key"))
    client._client = httpx.AsyncClient(
        base_url="http://sonarr.test", transport=httpx.MockTransport(fake.handler)
    )
    return client


async def _init_db(tmp_path):
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)
    return db


async def _seed(
    db, *, item_id: int, season_number: int, missing_count: int, timestamp: datetime,
    instance_stable_id: str = "sid-main",
) -> int:
    """Insert a pending Sonarr search entry with an explicit timestamp, return its id."""
    await insert_search_entry(
        db, "Sonarr", "missing", f"Series {item_id} S{season_number}",
        item_id=item_id, season_number=season_number, missing_count=missing_count,
        instance_id="Main", instance_stable_id=instance_stable_id,
    )
    async with db.execute("SELECT last_insert_rowid()") as cursor:
        row_id = (await cursor.fetchone())[0]
    ts = timestamp.isoformat().replace("+00:00", "Z")
    await db.execute("UPDATE search_history SET timestamp = ? WHERE id = ?", (ts, row_id))
    await db.commit()
    return row_id


async def _outcome(db, row_id: int) -> str:
    async with db.execute("SELECT outcome FROM search_history WHERE id = ?", (row_id,)) as cursor:
        return (await cursor.fetchone())[0]


async def _detail(db, row_id: int) -> str:
    async with db.execute("SELECT detail FROM search_history WHERE id = ?", (row_id,)) as cursor:
        return (await cursor.fetchone())[0]


async def _stat(db, column: str, instance_stable_id: str = "sid-main") -> int:
    async with db.execute(
        f"SELECT {column} FROM lifetime_stats WHERE app = 'Sonarr' AND instance_stable_id = ?",  # noqa: S608
        (instance_stable_id,),
    ) as cursor:
        row = await cursor.fetchone()
    return row[column] if row is not None else 0


async def test_client_path_season_pack_credits_season_once(tmp_path):
    """A season-1 pack (plus a repeat grab of one episode) credits only the S1 search, once."""
    db = await _init_db(tmp_path)
    records = load_sonarr_fixture("history_season_pack_nested_synth")
    fake = _SonarrHistoryFake({202: records})
    client = _client(fake)

    base = datetime(2026, 1, 31, tzinfo=UTC)
    row_s1 = await _seed(db, item_id=202, season_number=1, missing_count=6, timestamp=base)
    row_s2 = await _seed(db, item_id=202, season_number=2, missing_count=1, timestamp=base)

    try:
        await run_tracking_check(
            db, client, "Sonarr", "Main", tracking_window_minutes=_WIDE_WINDOW, instance_stable_id="sid-main",
        )

        assert any(r.url.params.get("includeEpisode") == "true" for r in fake.requests)
        assert await _outcome(db, row_s1) == "grabbed"
        assert "6/6" in await _detail(db, row_s1)
        assert await _stat(db, "episodes_found") == 6
        assert await _outcome(db, row_s2) == "searched"
        owned = await get_owned_grabs(db, app="Sonarr", instance_stable_id="sid-main", series_id=202)
        assert len(owned) == 7  # 6 distinct episodes + the repeat grab of episode 3

        # A second check adds nothing.
        await run_tracking_check(
            db, client, "Sonarr", "Main", tracking_window_minutes=_WIDE_WINDOW, instance_stable_id="sid-main",
        )
        assert await _stat(db, "episodes_found") == 6
        owned_after = await get_owned_grabs(db, app="Sonarr", instance_stable_id="sid-main", series_id=202)
        assert len(owned_after) == 7
    finally:
        await client.close()
        await db.close()


async def test_client_path_multi_season_pack_no_cross_season(tmp_path):
    """A pack spanning two seasons credits each season's search independently, with no shared grab id."""
    db = await _init_db(tmp_path)
    records = load_sonarr_fixture("history_multi_season_pack_nested_synth")
    fake = _SonarrHistoryFake({303: records})
    client = _client(fake)

    base = datetime(2026, 2, 28, tzinfo=UTC)
    row_s1 = await _seed(db, item_id=303, season_number=1, missing_count=3, timestamp=base)
    row_s2 = await _seed(db, item_id=303, season_number=2, missing_count=3, timestamp=base)

    try:
        await run_tracking_check(
            db, client, "Sonarr", "Main", tracking_window_minutes=_WIDE_WINDOW, instance_stable_id="sid-main",
        )

        assert await _outcome(db, row_s1) == "grabbed"
        assert "3/3" in await _detail(db, row_s1)
        assert await _outcome(db, row_s2) == "grabbed"
        assert "3/3" in await _detail(db, row_s2)
        assert await _stat(db, "episodes_found") == 6

        owned = await get_owned_grabs(db, app="Sonarr", instance_stable_id="sid-main", series_id=303)
        assert len(owned) == 6
        assert len({o.grab_id for o in owned}) == 6  # every grab id owned exactly once

        # A second check adds nothing.
        await run_tracking_check(
            db, client, "Sonarr", "Main", tracking_window_minutes=_WIDE_WINDOW, instance_stable_id="sid-main",
        )
        assert await _stat(db, "episodes_found") == 6
        owned_after = await get_owned_grabs(db, app="Sonarr", instance_stable_id="sid-main", series_id=303)
        assert len(owned_after) == 6
    finally:
        await client.close()
        await db.close()


async def test_client_path_alternate_order_uses_canonical_season(tmp_path):
    """Scene numbering reporting the wrong season never overrides Sonarr's canonical season."""
    db = await _init_db(tmp_path)
    records = load_sonarr_fixture("history_alternate_order_nested_synth")
    fake = _SonarrHistoryFake({404: records})
    client = _client(fake)

    base = datetime(2026, 3, 31, tzinfo=UTC)
    row_s1 = await _seed(db, item_id=404, season_number=1, missing_count=3, timestamp=base)
    row_s2 = await _seed(db, item_id=404, season_number=2, missing_count=1, timestamp=base)

    try:
        await run_tracking_check(
            db, client, "Sonarr", "Main", tracking_window_minutes=_WIDE_WINDOW, instance_stable_id="sid-main",
        )
    finally:
        await client.close()

    assert await _outcome(db, row_s1) == "grabbed"
    assert "3/3" in await _detail(db, row_s1)
    assert await _outcome(db, row_s2) == "grabbed"
    assert "1/1" in await _detail(db, row_s2)
    assert await _stat(db, "episodes_found") == 4
    owned = await get_owned_grabs(db, app="Sonarr", instance_stable_id="sid-main", series_id=404)
    assert len(owned) == 4
    await db.close()


async def test_client_path_standard_v4_repeated_checks(tmp_path):
    """Three consecutive checks against a standard v4 response credit exactly once."""
    db = await _init_db(tmp_path)
    records = load_sonarr_fixture("history_standard_v4")
    fake = _SonarrHistoryFake({101: records})
    client = _client(fake)

    base = datetime(2026, 1, 9, tzinfo=UTC)
    row_id = await _seed(db, item_id=101, season_number=1, missing_count=2, timestamp=base)

    try:
        for _ in range(3):
            await run_tracking_check(
                db, client, "Sonarr", "Main", tracking_window_minutes=_WIDE_WINDOW, instance_stable_id="sid-main",
            )
    finally:
        await client.close()

    assert await _outcome(db, row_id) == "grabbed"
    assert "2/2" in await _detail(db, row_id)
    assert await _stat(db, "episodes_found") == 2
    await db.close()


async def test_client_path_missing_episode_id_not_counted(tmp_path):
    """R2: two grabs of the same episode, each missing a top-level episodeId, are never credited."""
    db = await _init_db(tmp_path)
    base_record = load_sonarr_fixture("history_standard_v4")[0]

    bad1 = copy.deepcopy(base_record)
    bad1["id"] = 20001
    del bad1["episodeId"]
    bad2 = copy.deepcopy(base_record)
    bad2["id"] = 20002
    del bad2["episodeId"]

    fake = _SonarrHistoryFake({101: [bad1, bad2]})
    client = _client(fake)

    base = datetime(2026, 1, 9, tzinfo=UTC)
    row_id = await _seed(db, item_id=101, season_number=1, missing_count=2, timestamp=base)

    try:
        counts = await run_tracking_check(
            db, client, "Sonarr", "Main", tracking_window_minutes=_WIDE_WINDOW, instance_stable_id="sid-main",
        )
    finally:
        await client.close()

    assert await _outcome(db, row_id) == "searched"
    assert counts["identity_skipped"] == 2
    owned = await get_owned_grabs(db, app="Sonarr", instance_stable_id="sid-main", series_id=101)
    assert len(owned) == 0
    await db.close()


async def test_client_path_malformed_identity_not_counted(tmp_path):
    """R2: malformed identity values are skipped through the real parse path without raising."""
    db = await _init_db(tmp_path)
    good_records = load_sonarr_fixture("history_standard_v4")  # 2 good records, series 101

    bad_str_episode_id = copy.deepcopy(good_records[0])
    bad_str_episode_id["id"] = 20011
    bad_str_episode_id["episodeId"] = "abc"

    bad_bool_episode_id = copy.deepcopy(good_records[0])
    bad_bool_episode_id["id"] = 20012
    bad_bool_episode_id["episodeId"] = True

    bad_zero_episode_id = copy.deepcopy(good_records[0])
    bad_zero_episode_id["id"] = 20013
    bad_zero_episode_id["episodeId"] = 0

    bad_episode_not_object = copy.deepcopy(good_records[0])
    bad_episode_not_object["id"] = 20014
    bad_episode_not_object["episode"] = "oops"

    bad_season_not_int = copy.deepcopy(good_records[0])
    bad_season_not_int["id"] = 20015
    bad_season_not_int["episode"] = {**bad_season_not_int["episode"], "seasonNumber": "x"}

    malformed = [
        bad_str_episode_id, bad_bool_episode_id, bad_zero_episode_id,
        bad_episode_not_object, bad_season_not_int,
    ]
    records = good_records + malformed

    fake = _SonarrHistoryFake({101: records})
    client = _client(fake)

    base = datetime(2026, 1, 9, tzinfo=UTC)
    row_id = await _seed(db, item_id=101, season_number=1, missing_count=2, timestamp=base)

    try:
        counts = await run_tracking_check(
            db, client, "Sonarr", "Main", tracking_window_minutes=_WIDE_WINDOW, instance_stable_id="sid-main",
        )
    finally:
        await client.close()

    # The 2 good records in the same response still credit the search.
    assert await _outcome(db, row_id) == "grabbed"
    assert "2/2" in await _detail(db, row_id)
    assert counts["identity_skipped"] == 5
    await db.close()


# ---------------------------------------------------------------------------
# v5 episode-identity resolution (Phase 81, gap closure: episode-ID fallback
# via per-check series episode list + per-id fallback, series validation,
# transient deferral with per-row 24h escalation, no credit on missing or
# conflicting identity)
# ---------------------------------------------------------------------------

_S2_CAPTURE_DATE = datetime.fromisoformat("2026-10-19T23:34:51+00:00")


def _v5_s2_records() -> list[dict]:
    """The 8 real S2 grab records (episodeId 11-18) from the live v5 capture."""
    return [r for r in load_sonarr_fixture("history_season_pack_v5") if r["episodeId"] >= 11]


def _shift_to_now(records: list[dict], anchor_date: datetime, offset: timedelta) -> list[dict]:
    """Shift records (sharing ``anchor_date``) so that date lands at ``now + offset``."""
    delta = (datetime.now(UTC) + offset) - anchor_date
    return _shift_records(records, delta)


def _to_v5_shape(records: list[dict]) -> tuple[list[dict], list[dict]]:
    """Strip each record's nested ``episode`` into a parallel series-episode-list entry.

    Synthesized v5-shaped coverage: moves the nested_synth fixtures' episode
    data into the fake's series list (labelled synthesized) so the history
    records themselves carry no nested episode, matching the real v5 shape.
    """
    history: list[dict] = []
    episode_list: list[dict] = []
    for r in records:
        r2 = copy.deepcopy(r)
        episode = r2.pop("episode", None)
        history.append(r2)
        if episode is not None:
            episode_list.append(episode)
    return history, episode_list


async def test_client_path_v5_season_pack_real_dates_credits_once_then_stable(tmp_path):
    """Real v5 capture: an 8-episode S2 pack with no nested episode resolves via one
    series-list call, credits the S2 search once, and repeat checks add nothing."""
    db = await _init_db(tmp_path)
    records = load_sonarr_fixture("history_season_pack_v5")  # 18 real records, series 1
    series_list = load_sonarr_series_episode_list("episodes_v5", 1)
    fake = _SonarrHistoryFake({1: records}, series_episode_lists={1: series_list})
    client = _client(fake)

    search_time = datetime.fromisoformat("2026-10-19T23:34:45.161529+00:00")
    row_s1 = await _seed(db, item_id=1, season_number=1, missing_count=10, timestamp=search_time)
    row_s2 = await _seed(db, item_id=1, season_number=2, missing_count=8, timestamp=search_time)

    try:
        await run_tracking_check(
            db, client, "Sonarr", "Main", tracking_window_minutes=60, instance_stable_id="sid-main",
        )

        assert await _outcome(db, row_s2) == "grabbed"
        assert "8/8" in await _detail(db, row_s2)
        assert await _stat(db, "episodes_found") == 8
        assert await _outcome(db, row_s1) != "grabbed"

        owned = await get_owned_grabs(db, app="Sonarr", instance_stable_id="sid-main", series_id=1)
        assert {o.episode_id for o in owned} == set(range(11, 19))

        assert len(_list_requests(fake)) == 1
        assert len(_per_id_requests(fake)) == 0

        # Two more checks: all S2 grabs are already owned -- zero further requests.
        await run_tracking_check(
            db, client, "Sonarr", "Main", tracking_window_minutes=60, instance_stable_id="sid-main",
        )
        await run_tracking_check(
            db, client, "Sonarr", "Main", tracking_window_minutes=60, instance_stable_id="sid-main",
        )

        assert len(_list_requests(fake)) == 1
        assert len(_per_id_requests(fake)) == 0
        assert await _stat(db, "episodes_found") == 8
        owned_after = await get_owned_grabs(db, app="Sonarr", instance_stable_id="sid-main", series_id=1)
        assert len(owned_after) == 8
    finally:
        await client.close()
        await db.close()


async def test_client_path_v5_distinct_repeat_grab_one_list_request(tmp_path):
    """A repeat grab of an already-seen episode still resolves via the one
    series-list call made for the group, and counts as the same distinct episode."""
    db = await _init_db(tmp_path)
    s2 = _shift_to_now(_v5_s2_records(), _S2_CAPTURE_DATE, -timedelta(minutes=10))
    repeat = copy.deepcopy(s2[-1])  # repeat grab of episodeId 18, new history id
    repeat["id"] = 90001
    records = s2 + [repeat]
    series_list = load_sonarr_series_episode_list("episodes_v5", 1)
    fake = _SonarrHistoryFake({1: records}, series_episode_lists={1: series_list})
    client = _client(fake)

    search_time = datetime.now(UTC) - timedelta(minutes=15)
    _assert_grab_in_window(records, search_time, 60)
    row = await _seed(db, item_id=1, season_number=2, missing_count=8, timestamp=search_time)

    try:
        await run_tracking_check(
            db, client, "Sonarr", "Main", tracking_window_minutes=60, instance_stable_id="sid-main",
        )
    finally:
        await client.close()

    assert await _outcome(db, row) == "grabbed"
    assert "8/8" in await _detail(db, row)
    assert len(_list_requests(fake)) == 1
    assert len(_per_id_requests(fake)) == 0
    owned = await get_owned_grabs(db, app="Sonarr", instance_stable_id="sid-main", series_id=1)
    assert len(owned) == 9  # 8 distinct episodes + the repeat grab row
    assert len({o.episode_id for o in owned}) == 8
    await db.close()


def _synth_large_pack(series_id: int, count: int, when: datetime) -> tuple[list[dict], list[dict]]:
    """Synthesized (labelled) v5-shaped complete-series pack of ``count`` grabs."""
    history = []
    episodes = []
    for i in range(1, count + 1):
        episode_id = 100_000 + i
        history.append({
            "id": 200_000 + i,
            "episodeId": episode_id,
            "seriesId": series_id,
            "sourceTitle": "Synthetic.Complete.Series.1080p-GRP",
            "date": when.isoformat().replace("+00:00", "Z"),
            "eventType": "grabbed",
            "downloadId": "DL-SYNTHLARGE",
            "data": {},
        })
        episodes.append({"id": episode_id, "seriesId": series_id, "seasonNumber": 1, "episodeNumber": i})
    return history, episodes


async def test_client_path_v5_large_pack_one_check_one_list_request(tmp_path):
    """A synthesized complete-series pack of more than 100 in-window grabs is
    credited in a single check with exactly one series-list request."""
    db = await _init_db(tmp_path)
    count = 120
    when = datetime.now(UTC) - timedelta(minutes=5)
    history, episodes = _synth_large_pack(5, count, when)
    fake = _SonarrHistoryFake({5: history}, series_episode_lists={5: episodes})
    client = _client(fake)

    search_time = datetime.now(UTC) - timedelta(minutes=10)
    _assert_grab_in_window(history, search_time, 60)
    row = await _seed(db, item_id=5, season_number=1, missing_count=count, timestamp=search_time)

    try:
        await run_tracking_check(
            db, client, "Sonarr", "Main", tracking_window_minutes=60, instance_stable_id="sid-main",
        )
    finally:
        await client.close()

    assert await _outcome(db, row) == "grabbed"
    assert f"{count}/{count}" in await _detail(db, row)
    assert len(_list_requests(fake)) == 1
    assert len(_per_id_requests(fake)) == 0
    owned = await get_owned_grabs(db, app="Sonarr", instance_stable_id="sid-main", series_id=5)
    assert len(owned) == count
    await db.close()


async def test_client_path_v5_per_id_fallback_credits_when_verified(tmp_path):
    """An episodeId absent from the series list resolves via one per-id request and
    credits when it verifies."""
    db = await _init_db(tmp_path)
    when = datetime.now(UTC) - timedelta(minutes=5)
    record = {
        "id": 70001, "episodeId": 9999, "seriesId": 1,
        "sourceTitle": "Hacks.S02E09.1080p-GRP",
        "date": when.isoformat().replace("+00:00", "Z"),
        "eventType": "grabbed", "downloadId": "DL-FALLBACK", "data": {},
    }
    series_list = load_sonarr_series_episode_list("episodes_v5", 1)  # does not contain id 9999
    fake = _SonarrHistoryFake(
        {1: [record]},
        series_episode_lists={1: series_list},
        episodes={9999: {"id": 9999, "seriesId": 1, "seasonNumber": 2, "episodeNumber": 9}},
    )
    client = _client(fake)

    search_time = datetime.now(UTC) - timedelta(minutes=10)
    _assert_grab_in_window([record], search_time, 60)
    row = await _seed(db, item_id=1, season_number=2, missing_count=1, timestamp=search_time)

    try:
        await run_tracking_check(
            db, client, "Sonarr", "Main", tracking_window_minutes=60, instance_stable_id="sid-main",
        )
    finally:
        await client.close()

    assert await _outcome(db, row) == "grabbed"
    assert len(_list_requests(fake)) == 1
    assert len(_per_id_requests(fake)) == 1
    owned = await get_owned_grabs(db, app="Sonarr", instance_stable_id="sid-main", series_id=1)
    assert {o.episode_id for o in owned} == {9999}
    await db.close()


async def test_client_path_v5_per_id_fallback_404_is_definitive(tmp_path):
    """A per-id 404 is a definitive identity failure: no credit, identity_skipped
    counted, the row resolves through the normal state machine (never stuck)."""
    db = await _init_db(tmp_path)
    when = datetime.now(UTC) - timedelta(minutes=5)
    record = {
        "id": 70002, "episodeId": 8888, "seriesId": 1,
        "sourceTitle": "Hacks.S02E10.1080p-GRP",
        "date": when.isoformat().replace("+00:00", "Z"),
        "eventType": "grabbed", "downloadId": "DL-FALLBACK404", "data": {},
    }
    series_list = load_sonarr_series_episode_list("episodes_v5", 1)  # does not contain id 8888
    fake = _SonarrHistoryFake({1: [record]}, series_episode_lists={1: series_list})
    client = _client(fake)

    search_time = datetime.now(UTC) - timedelta(minutes=10)
    row = await _seed(db, item_id=1, season_number=2, missing_count=1, timestamp=search_time)

    try:
        counts = await run_tracking_check(
            db, client, "Sonarr", "Main", tracking_window_minutes=60, instance_stable_id="sid-main",
        )
    finally:
        await client.close()

    assert counts["identity_skipped"] == 1
    assert await _outcome(db, row) == "searched"
    owned = await get_owned_grabs(db, app="Sonarr", instance_stable_id="sid-main", series_id=1)
    assert len(owned) == 0
    assert len(_per_id_requests(fake)) == 1
    await db.close()


async def test_client_path_v5_list_entry_wrong_series_falls_back_to_per_id(tmp_path):
    """A series-list entry for a different seriesId is ignored; the grab falls back
    to per-id and is credited when that verifies."""
    db = await _init_db(tmp_path)
    when = datetime.now(UTC) - timedelta(minutes=5)
    record = {
        "id": 70003, "episodeId": 55, "seriesId": 1,
        "sourceTitle": "Hacks.S02E11.1080p-GRP",
        "date": when.isoformat().replace("+00:00", "Z"),
        "eventType": "grabbed", "downloadId": "DL-WRONGSERIES", "data": {},
    }
    series_list = [{"id": 55, "seriesId": 999, "seasonNumber": 2, "episodeNumber": 11}]  # wrong series
    fake = _SonarrHistoryFake(
        {1: [record]},
        series_episode_lists={1: series_list},
        episodes={55: {"id": 55, "seriesId": 1, "seasonNumber": 2, "episodeNumber": 11}},
    )
    client = _client(fake)

    search_time = datetime.now(UTC) - timedelta(minutes=10)
    row = await _seed(db, item_id=1, season_number=2, missing_count=1, timestamp=search_time)

    try:
        await run_tracking_check(
            db, client, "Sonarr", "Main", tracking_window_minutes=60, instance_stable_id="sid-main",
        )
    finally:
        await client.close()

    assert await _outcome(db, row) == "grabbed"
    assert len(_per_id_requests(fake)) == 1
    owned = await get_owned_grabs(db, app="Sonarr", instance_stable_id="sid-main", series_id=1)
    assert {o.episode_id for o in owned} == {55}
    await db.close()


async def test_client_path_v5_list_entry_missing_season_falls_back_to_per_id(tmp_path):
    """A series-list entry with a missing seasonNumber is ignored; the grab falls back
    to per-id and is credited when that verifies."""
    db = await _init_db(tmp_path)
    when = datetime.now(UTC) - timedelta(minutes=5)
    record = {
        "id": 70004, "episodeId": 66, "seriesId": 1,
        "sourceTitle": "Hacks.S02E12.1080p-GRP",
        "date": when.isoformat().replace("+00:00", "Z"),
        "eventType": "grabbed", "downloadId": "DL-NOSEASON", "data": {},
    }
    series_list = [{"id": 66, "seriesId": 1, "episodeNumber": 12}]  # no seasonNumber key -> ignored
    fake = _SonarrHistoryFake(
        {1: [record]},
        series_episode_lists={1: series_list},
        episodes={66: {"id": 66, "seriesId": 1, "seasonNumber": 2, "episodeNumber": 12}},
    )
    client = _client(fake)

    search_time = datetime.now(UTC) - timedelta(minutes=10)
    row = await _seed(db, item_id=1, season_number=2, missing_count=1, timestamp=search_time)

    try:
        await run_tracking_check(
            db, client, "Sonarr", "Main", tracking_window_minutes=60, instance_stable_id="sid-main",
        )
    finally:
        await client.close()

    assert await _outcome(db, row) == "grabbed"
    assert len(_per_id_requests(fake)) == 1
    owned = await get_owned_grabs(db, app="Sonarr", instance_stable_id="sid-main", series_id=1)
    assert {o.episode_id for o in owned} == {66}
    await db.close()


async def test_client_path_v5_transient_series_list_error_defers_then_heals(tmp_path):
    """Transient (shifted dates, search 2 hours ago): check 1 with the series list
    returning 503 leaves the row 'searched', no ownership, errors counted,
    identity_skipped unchanged; check 2 healthy credits 'grabbed' n/n; check 3
    changes nothing."""
    db = await _init_db(tmp_path)
    when = datetime.now(UTC) - timedelta(minutes=90)
    record = {
        "id": 70005, "episodeId": 77, "seriesId": 1,
        "sourceTitle": "Hacks.S02E13.1080p-GRP",
        "date": when.isoformat().replace("+00:00", "Z"),
        "eventType": "grabbed", "downloadId": "DL-TRANSIENT", "data": {},
    }
    fake = _SonarrHistoryFake(
        {1: [record]},
        episodes={77: {"id": 77, "seriesId": 1, "seasonNumber": 2, "episodeNumber": 1}},
    )
    fake.list_status[1] = 503
    client = _client(fake)

    search_time = datetime.now(UTC) - timedelta(hours=2)
    _assert_grab_in_window([record], search_time, 60)
    row = await _seed(db, item_id=1, season_number=2, missing_count=1, timestamp=search_time)

    try:
        counts1 = await run_tracking_check(
            db, client, "Sonarr", "Main", tracking_window_minutes=60, instance_stable_id="sid-main",
        )

        assert await _outcome(db, row) == "searched"
        assert counts1["identity_skipped"] == 0
        assert counts1["errors"] == 1
        owned = await get_owned_grabs(db, app="Sonarr", instance_stable_id="sid-main", series_id=1)
        assert len(owned) == 0

        fake.list_status.pop(1)
        await run_tracking_check(
            db, client, "Sonarr", "Main", tracking_window_minutes=60, instance_stable_id="sid-main",
        )
        assert await _outcome(db, row) == "grabbed"
        assert "1/1" in await _detail(db, row)

        await run_tracking_check(
            db, client, "Sonarr", "Main", tracking_window_minutes=60, instance_stable_id="sid-main",
        )
        assert len(_list_requests(fake)) == 2
    finally:
        await client.close()
    await db.close()


async def test_client_path_v5_circuit_breaker_stops_further_requests(tmp_path):
    """A transport error on the first episode request opens the circuit for the rest
    of the check: a second series group needing resolution is deferred too, with
    zero further episode requests; a later healthy check credits both."""
    db = await _init_db(tmp_path)
    when = datetime.now(UTC) - timedelta(minutes=90)
    record_a = {
        "id": 70010, "episodeId": 111, "seriesId": 11,
        "sourceTitle": "SeriesA.1080p-GRP", "date": when.isoformat().replace("+00:00", "Z"),
        "eventType": "grabbed", "downloadId": "DL-CIRCUIT-A", "data": {},
    }
    record_b = {
        "id": 70011, "episodeId": 222, "seriesId": 12,
        "sourceTitle": "SeriesB.1080p-GRP", "date": when.isoformat().replace("+00:00", "Z"),
        "eventType": "grabbed", "downloadId": "DL-CIRCUIT-B", "data": {},
    }
    fake = _SonarrHistoryFake({11: [record_a], 12: [record_b]})
    fake.list_exception[11] = httpx.ReadTimeout("timeout", request=httpx.Request("GET", "http://sonarr.test"))
    client = _client(fake)

    search_time = datetime.now(UTC) - timedelta(hours=2)
    row_a = await _seed(db, item_id=11, season_number=1, missing_count=1, timestamp=search_time)
    row_b = await _seed(
        db, item_id=12, season_number=1, missing_count=1, timestamp=search_time + timedelta(seconds=1),
    )

    try:
        counts = await run_tracking_check(
            db, client, "Sonarr", "Main", tracking_window_minutes=60, instance_stable_id="sid-main",
        )

        assert await _outcome(db, row_a) == "searched"
        assert await _outcome(db, row_b) == "searched"
        assert counts["errors"] == 2
        assert len(_list_requests(fake)) == 1  # circuit opened after series 11; series 12 never attempted
        assert len(_per_id_requests(fake)) == 0

        fake.list_exception.clear()
        fake.series_episode_lists = {
            11: [{"id": 111, "seriesId": 11, "seasonNumber": 1, "episodeNumber": 1}],
            12: [{"id": 222, "seriesId": 12, "seasonNumber": 1, "episodeNumber": 1}],
        }
        await run_tracking_check(
            db, client, "Sonarr", "Main", tracking_window_minutes=60, instance_stable_id="sid-main",
        )
        assert await _outcome(db, row_a) == "grabbed"
        assert await _outcome(db, row_b) == "grabbed"
    finally:
        await client.close()
    await db.close()


async def test_client_path_v5_malformed_list_body_is_transient(tmp_path):
    """A non-list series-list body is a transient failure, not a crash: the row is
    held, not resolved, this check."""
    db = await _init_db(tmp_path)
    when = datetime.now(UTC) - timedelta(minutes=90)
    record = {
        "id": 70020, "episodeId": 333, "seriesId": 1,
        "sourceTitle": "Hacks.S02E14.1080p-GRP", "date": when.isoformat().replace("+00:00", "Z"),
        "eventType": "grabbed", "downloadId": "DL-MALFORMEDLIST", "data": {},
    }
    fake = _SonarrHistoryFake({1: [record]})
    fake.list_body_override[1] = {"not": "a list"}
    client = _client(fake)

    search_time = datetime.now(UTC) - timedelta(hours=2)
    row = await _seed(db, item_id=1, season_number=2, missing_count=1, timestamp=search_time)

    try:
        counts = await run_tracking_check(
            db, client, "Sonarr", "Main", tracking_window_minutes=60, instance_stable_id="sid-main",
        )
    finally:
        await client.close()

    assert await _outcome(db, row) == "searched"
    assert counts["identity_skipped"] == 0
    assert counts["errors"] == 1
    await db.close()


async def test_client_path_v5_list_http_500_is_transient(tmp_path):
    """A 500 from the series-list endpoint is transient, not a definitive failure."""
    db = await _init_db(tmp_path)
    when = datetime.now(UTC) - timedelta(minutes=90)
    record = {
        "id": 70021, "episodeId": 444, "seriesId": 1,
        "sourceTitle": "Hacks.S02E15.1080p-GRP", "date": when.isoformat().replace("+00:00", "Z"),
        "eventType": "grabbed", "downloadId": "DL-500LIST", "data": {},
    }
    fake = _SonarrHistoryFake({1: [record]})
    fake.list_status[1] = 500
    client = _client(fake)

    search_time = datetime.now(UTC) - timedelta(hours=2)
    row = await _seed(db, item_id=1, season_number=2, missing_count=1, timestamp=search_time)

    try:
        counts = await run_tracking_check(
            db, client, "Sonarr", "Main", tracking_window_minutes=60, instance_stable_id="sid-main",
        )
    finally:
        await client.close()

    assert await _outcome(db, row) == "searched"
    assert counts["identity_skipped"] == 0
    assert counts["errors"] == 1
    await db.close()


async def test_client_path_v5_series_list_cap_defers_other_group(tmp_path, monkeypatch):
    """With the series-list budget capped to 1 and two groups needing resolution, the
    expired-window group is served first (even though inserted second) and the other
    is deferred."""
    monkeypatch.setattr(tracking_module, "_MAX_SERIES_EPISODE_LISTS_PER_CHECK", 1)

    db = await _init_db(tmp_path)
    when_fresh = datetime.now(UTC) - timedelta(minutes=10)
    when_expired = datetime.now(UTC) - timedelta(hours=2, minutes=55)
    record_fresh = {
        "id": 70030, "episodeId": 501, "seriesId": 21,
        "sourceTitle": "Fresh.1080p-GRP", "date": when_fresh.isoformat().replace("+00:00", "Z"),
        "eventType": "grabbed", "downloadId": "DL-FRESH", "data": {},
    }
    record_expired = {
        "id": 70031, "episodeId": 502, "seriesId": 22,
        "sourceTitle": "Expired.1080p-GRP", "date": when_expired.isoformat().replace("+00:00", "Z"),
        "eventType": "grabbed", "downloadId": "DL-EXPIRED", "data": {},
    }
    fake = _SonarrHistoryFake(
        {21: [record_fresh], 22: [record_expired]},
        series_episode_lists={
            21: [{"id": 501, "seriesId": 21, "seasonNumber": 1, "episodeNumber": 1}],
            22: [{"id": 502, "seriesId": 22, "seasonNumber": 1, "episodeNumber": 1}],
        },
    )
    client = _client(fake)

    # Inserted first: fresh (window not yet expired).
    row_fresh = await _seed(
        db, item_id=21, season_number=1, missing_count=1, timestamp=datetime.now(UTC) - timedelta(minutes=15),
    )
    # Inserted second: expired (window ended well in the past).
    row_expired = await _seed(
        db, item_id=22, season_number=1, missing_count=1, timestamp=datetime.now(UTC) - timedelta(hours=3),
    )

    try:
        await run_tracking_check(
            db, client, "Sonarr", "Main", tracking_window_minutes=60, instance_stable_id="sid-main",
        )
    finally:
        await client.close()

    assert await _outcome(db, row_expired) == "grabbed"  # served despite being inserted second
    assert await _outcome(db, row_fresh) == "searched"  # deferred -- budget exhausted
    assert len(_list_requests(fake)) == 1
    await db.close()


async def test_client_path_v5_per_id_cap_defers_second_lookup(tmp_path, monkeypatch):
    """With the per-id lookup budget capped to 1 and two ids missing from the list,
    the second is transient and the row is deferred (no partial credit this check)."""
    monkeypatch.setattr(tracking_module, "_MAX_EPISODE_ID_LOOKUPS_PER_CHECK", 1)

    db = await _init_db(tmp_path)
    when = datetime.now(UTC) - timedelta(minutes=10)
    record1 = {
        "id": 70040, "episodeId": 601, "seriesId": 31,
        "sourceTitle": "PerIdCap.1080p-GRP", "date": when.isoformat().replace("+00:00", "Z"),
        "eventType": "grabbed", "downloadId": "DL-PIDCAP1", "data": {},
    }
    record2 = {
        "id": 70041, "episodeId": 602, "seriesId": 31,
        "sourceTitle": "PerIdCap.1080p-GRP", "date": when.isoformat().replace("+00:00", "Z"),
        "eventType": "grabbed", "downloadId": "DL-PIDCAP2", "data": {},
    }
    fake = _SonarrHistoryFake(
        {31: [record1, record2]},
        series_episode_lists={31: []},  # neither id present -- both need per-id fallback
        episodes={
            601: {"id": 601, "seriesId": 31, "seasonNumber": 1, "episodeNumber": 1},
            602: {"id": 602, "seriesId": 31, "seasonNumber": 1, "episodeNumber": 2},
        },
    )
    client = _client(fake)

    search_time = datetime.now(UTC) - timedelta(minutes=15)
    row = await _seed(db, item_id=31, season_number=1, missing_count=2, timestamp=search_time)

    try:
        counts = await run_tracking_check(
            db, client, "Sonarr", "Main", tracking_window_minutes=60, instance_stable_id="sid-main",
        )
    finally:
        await client.close()

    assert await _outcome(db, row) == "searched"  # deferred -- not credited this check
    assert counts["identity_skipped"] == 0
    assert len(_per_id_requests(fake)) == 1
    owned = await get_owned_grabs(db, app="Sonarr", instance_stable_id="sid-main", series_id=31)
    assert len(owned) == 0
    await db.close()


async def test_client_path_v5_per_id_budget_overflow_keeps_progress_across_checks(tmp_path):
    """More ids missing from the series list than one check's per-id budget allows:
    the verified lookups are kept (owned, row partial) so the next check spends its
    budget only on the rest and credits every episode -- never the same lookups
    repeated until 24h escalation undercounts the search."""
    budget = tracking_module._MAX_EPISODE_ID_LOOKUPS_PER_CHECK
    total = budget + 1
    db = await _init_db(tmp_path)
    when = datetime.now(UTC) - timedelta(minutes=10)
    records = [
        {
            "id": 71000 + n, "episodeId": 1000 + n, "seriesId": 61,
            "sourceTitle": "Overflow.S01.1080p-GRP", "date": when.isoformat().replace("+00:00", "Z"),
            "eventType": "grabbed", "downloadId": "DL-OVERFLOW", "data": {},
        }
        for n in range(total)
    ]
    fake = _SonarrHistoryFake(
        {61: records},
        series_episode_lists={61: []},  # no id present -- every grab needs the per-id fallback
        episodes={
            1000 + n: {"id": 1000 + n, "seriesId": 61, "seasonNumber": 1, "episodeNumber": n + 1}
            for n in range(total)
        },
    )

    search_time = datetime.now(UTC) - timedelta(minutes=15)
    row = await _seed(db, item_id=61, season_number=1, missing_count=total, timestamp=search_time)

    client = _client(fake)
    try:
        await run_tracking_check(
            db, client, "Sonarr", "Main", tracking_window_minutes=60, instance_stable_id="sid-main",
        )
    finally:
        await client.close()

    owned = await get_owned_grabs(db, app="Sonarr", instance_stable_id="sid-main", series_id=61)
    assert len(owned) == budget  # verified progress kept, not discarded
    assert await _outcome(db, row) == "partial"  # non-terminal while one identity is unverified
    first_check_lookups = len(_per_id_requests(fake))
    assert first_check_lookups == budget

    client = _client(fake)
    try:
        await run_tracking_check(
            db, client, "Sonarr", "Main", tracking_window_minutes=60, instance_stable_id="sid-main",
        )
    finally:
        await client.close()

    assert len(_per_id_requests(fake)) - first_check_lookups == 1  # only the remaining id
    assert await _outcome(db, row) == "grabbed"
    assert f"{total}/{total}" in await _detail(db, row)
    owned = await get_owned_grabs(db, app="Sonarr", instance_stable_id="sid-main", series_id=61)
    assert {o.episode_id for o in owned} == {1000 + n for n in range(total)}
    await db.close()


async def test_client_path_v5_row_escalation_old_row_resolves_recent_held(tmp_path):
    """One series with an old row (26h past its window end) and a recently-expired
    row (2h past), list returning 503: the old row escalates to 'unresolved' with
    identity_skipped counted; the recent row gets no write and errors += 1."""
    db = await _init_db(tmp_path)
    now_ref = datetime.now(UTC)
    # Inside the recent row's window (3h..2h ago) so the grab genuinely needs
    # resolution; the old row's escalation still applies to the whole check.
    grab_time = now_ref - timedelta(hours=2, minutes=30)
    record = {
        "id": 70050, "episodeId": 701, "seriesId": 41,
        "sourceTitle": "Escalation.1080p-GRP",
        "date": grab_time.isoformat().replace("+00:00", "Z"),
        "eventType": "grabbed", "downloadId": "DL-ESCALATE", "data": {},
    }
    fake = _SonarrHistoryFake({41: [record]})
    fake.list_status[41] = 503
    client = _client(fake)

    old_search_time = now_ref - timedelta(hours=27)
    recent_search_time = now_ref - timedelta(hours=3)
    row_old = await _seed(db, item_id=41, season_number=1, missing_count=1, timestamp=old_search_time)
    row_recent = await _seed(db, item_id=41, season_number=1, missing_count=1, timestamp=recent_search_time)

    try:
        counts = await run_tracking_check(
            db, client, "Sonarr", "Main", tracking_window_minutes=60, instance_stable_id="sid-main",
        )
    finally:
        await client.close()

    assert await _outcome(db, row_old) == "unresolved"
    assert await _outcome(db, row_recent) == "searched"
    assert counts["identity_skipped"] == 1
    assert counts["errors"] == 1
    owned = await get_owned_grabs(db, app="Sonarr", instance_stable_id="sid-main", series_id=41)
    assert len(owned) == 0
    await db.close()


async def test_client_path_v5_row_not_escalated_before_24h_stays_pending(tmp_path):
    """A single row 23h past its window end (not yet 24h) stays pending -- the whole
    group defers, no credit, no identity_skipped."""
    db = await _init_db(tmp_path)
    now_ref = datetime.now(UTC)
    grab_time = now_ref - timedelta(hours=23, minutes=30)
    record = {
        "id": 70051, "episodeId": 801, "seriesId": 42,
        "sourceTitle": "NotEscalated.1080p-GRP",
        "date": grab_time.isoformat().replace("+00:00", "Z"),
        "eventType": "grabbed", "downloadId": "DL-NOTESCALATED", "data": {},
    }
    fake = _SonarrHistoryFake({42: [record]})
    fake.list_status[42] = 503
    client = _client(fake)

    search_time = now_ref - timedelta(hours=24)  # window end 23h ago
    row = await _seed(db, item_id=42, season_number=1, missing_count=1, timestamp=search_time)

    try:
        counts = await run_tracking_check(
            db, client, "Sonarr", "Main", tracking_window_minutes=60, instance_stable_id="sid-main",
        )
    finally:
        await client.close()

    assert await _outcome(db, row) == "searched"
    assert counts["identity_skipped"] == 0
    assert counts["errors"] == 1
    await db.close()


async def test_client_path_v5_definitive_id_mismatch_no_credit(tmp_path):
    """A resolved episode whose id disagrees with the grab's own episodeId is a
    definitive failure: no credit, identity_skipped counted, row resolves normally,
    and the warning never logs the release title."""
    db = await _init_db(tmp_path)
    base = datetime(2026, 1, 9, tzinfo=UTC)  # long expired relative to "now"
    record = {
        "id": 70060, "episodeId": 901, "seriesId": 51,
        "sourceTitle": "IdMismatch.1080p.WEB-DL-GRP",
        "date": base.isoformat().replace("+00:00", "Z"),
        "eventType": "grabbed", "downloadId": "DL-IDMISMATCH", "data": {},
    }
    fake = _SonarrHistoryFake(
        {51: [record]},
        series_episode_lists={51: []},
        episodes={901: {"id": 999, "seriesId": 51, "seasonNumber": 1, "episodeNumber": 1}},
    )
    client = _client(fake)

    captured: list[str] = []
    sink_id = logger.add(lambda m: captured.append(str(m)), level="WARNING")

    row = await _seed(db, item_id=51, season_number=1, missing_count=1, timestamp=base)

    try:
        counts = await run_tracking_check(
            db, client, "Sonarr", "Main", tracking_window_minutes=60, instance_stable_id="sid-main",
        )
    finally:
        await client.close()
        logger.remove(sink_id)

    assert counts["identity_skipped"] == 1
    assert await _outcome(db, row) == "unresolved"
    owned = await get_owned_grabs(db, app="Sonarr", instance_stable_id="sid-main", series_id=51)
    assert len(owned) == 0
    # Pins that resolution was actually attempted (list + per-id fallback), not
    # just the pre-existing generic "missing season" gate (which never requests).
    assert len(_list_requests(fake)) == 1
    assert len(_per_id_requests(fake)) == 1

    warning_lines = [m for m in captured if "skipped grab" in m]
    assert len(warning_lines) == 1
    assert "70060" in warning_lines[0]  # the grab's own history-record id
    assert "WEB-DL" not in warning_lines[0]
    await db.close()


async def test_client_path_v5_definitive_series_mismatch_no_credit(tmp_path):
    """A resolved episode whose seriesId disagrees with the tracked series is a
    definitive failure: no credit, identity_skipped counted, row resolves normally."""
    db = await _init_db(tmp_path)
    base = datetime(2026, 1, 9, tzinfo=UTC)
    record = {
        "id": 70061, "episodeId": 902, "seriesId": 52,
        "sourceTitle": "SeriesMismatch.1080p-GRP",
        "date": base.isoformat().replace("+00:00", "Z"),
        "eventType": "grabbed", "downloadId": "DL-SERIESMISMATCH", "data": {},
    }
    fake = _SonarrHistoryFake(
        {52: [record]},
        series_episode_lists={52: []},
        episodes={902: {"id": 902, "seriesId": 999, "seasonNumber": 1, "episodeNumber": 1}},
    )
    client = _client(fake)

    row = await _seed(db, item_id=52, season_number=1, missing_count=1, timestamp=base)

    try:
        counts = await run_tracking_check(
            db, client, "Sonarr", "Main", tracking_window_minutes=60, instance_stable_id="sid-main",
        )
    finally:
        await client.close()

    assert counts["identity_skipped"] == 1
    assert await _outcome(db, row) == "unresolved"
    owned = await get_owned_grabs(db, app="Sonarr", instance_stable_id="sid-main", series_id=52)
    assert len(owned) == 0
    assert len(_list_requests(fake)) == 1
    assert len(_per_id_requests(fake)) == 1
    await db.close()


async def test_client_path_v5_definitive_series_absent_no_credit(tmp_path):
    """A resolved episode with no seriesId at all is a definitive failure (never
    assumed to agree): no credit, identity_skipped counted, row resolves normally."""
    db = await _init_db(tmp_path)
    base = datetime(2026, 1, 9, tzinfo=UTC)
    record = {
        "id": 70062, "episodeId": 903, "seriesId": 53,
        "sourceTitle": "SeriesAbsent.1080p-GRP",
        "date": base.isoformat().replace("+00:00", "Z"),
        "eventType": "grabbed", "downloadId": "DL-SERIESABSENT", "data": {},
    }
    fake = _SonarrHistoryFake(
        {53: [record]},
        series_episode_lists={53: []},
        episodes={903: {"id": 903, "seasonNumber": 1, "episodeNumber": 1}},  # no seriesId key
    )
    client = _client(fake)

    row = await _seed(db, item_id=53, season_number=1, missing_count=1, timestamp=base)

    try:
        counts = await run_tracking_check(
            db, client, "Sonarr", "Main", tracking_window_minutes=60, instance_stable_id="sid-main",
        )
    finally:
        await client.close()

    assert counts["identity_skipped"] == 1
    assert await _outcome(db, row) == "unresolved"
    owned = await get_owned_grabs(db, app="Sonarr", instance_stable_id="sid-main", series_id=53)
    assert len(owned) == 0
    assert len(_list_requests(fake)) == 1
    assert len(_per_id_requests(fake)) == 1
    await db.close()


async def test_client_path_v5_definitive_no_valid_season_no_credit(tmp_path):
    """A resolved episode with no valid season anywhere is a definitive failure: no
    credit, identity_skipped counted, row resolves normally."""
    db = await _init_db(tmp_path)
    base = datetime(2026, 1, 9, tzinfo=UTC)
    record = {
        "id": 70063, "episodeId": 904, "seriesId": 54,
        "sourceTitle": "NoSeason.1080p-GRP",
        "date": base.isoformat().replace("+00:00", "Z"),
        "eventType": "grabbed", "downloadId": "DL-NOSEASON2", "data": {},
    }
    fake = _SonarrHistoryFake(
        {54: [record]},
        series_episode_lists={54: []},
        episodes={904: {"id": 904, "seriesId": 54, "episodeNumber": 1}},  # no seasonNumber key
    )
    client = _client(fake)

    row = await _seed(db, item_id=54, season_number=1, missing_count=1, timestamp=base)

    try:
        counts = await run_tracking_check(
            db, client, "Sonarr", "Main", tracking_window_minutes=60, instance_stable_id="sid-main",
        )
    finally:
        await client.close()

    assert counts["identity_skipped"] == 1
    assert await _outcome(db, row) == "unresolved"
    owned = await get_owned_grabs(db, app="Sonarr", instance_stable_id="sid-main", series_id=54)
    assert len(owned) == 0
    assert len(_list_requests(fake)) == 1
    assert len(_per_id_requests(fake)) == 1
    await db.close()


async def test_client_path_v5_nested_episode_without_season_credited_when_verified(tmp_path):
    """A grab with a nested episode object lacking a season is resolved via the
    episode endpoints and credited once the resolution verifies."""
    db = await _init_db(tmp_path)
    base = datetime(2026, 1, 9, tzinfo=UTC)
    record = {
        "id": 70070, "episodeId": 905, "seriesId": 55,
        "sourceTitle": "NestedNoSeason.1080p-GRP",
        "date": base.isoformat().replace("+00:00", "Z"),
        "eventType": "grabbed", "downloadId": "DL-NESTEDNOSEASON", "data": {},
        "episode": {"id": 905, "seriesId": 55, "episodeNumber": 1},  # no seasonNumber
    }
    fake = _SonarrHistoryFake(
        {55: [record]},
        series_episode_lists={55: [{"id": 905, "seriesId": 55, "seasonNumber": 1, "episodeNumber": 1}]},
    )
    client = _client(fake)

    row = await _seed(db, item_id=55, season_number=1, missing_count=1, timestamp=base)

    try:
        await run_tracking_check(
            db, client, "Sonarr", "Main", tracking_window_minutes=60, instance_stable_id="sid-main",
        )
    finally:
        await client.close()

    assert await _outcome(db, row) == "grabbed"
    owned = await get_owned_grabs(db, app="Sonarr", instance_stable_id="sid-main", series_id=55)
    assert {o.episode_id for o in owned} == {905}
    await db.close()


async def test_client_path_v5_nested_episode_without_season_conflict_skipped(tmp_path):
    """Same shape, but the resolved seriesId conflicts with the nested episode's own
    seriesId: no credit, identity_skipped counted."""
    db = await _init_db(tmp_path)
    base = datetime(2026, 1, 9, tzinfo=UTC)
    record = {
        "id": 70071, "episodeId": 906, "seriesId": 56,
        "sourceTitle": "NestedConflict.1080p-GRP",
        "date": base.isoformat().replace("+00:00", "Z"),
        "eventType": "grabbed", "downloadId": "DL-NESTEDCONFLICT", "data": {},
        "episode": {"id": 906, "seriesId": 999, "episodeNumber": 1},  # conflicting seriesId, no season
    }
    fake = _SonarrHistoryFake(
        {56: [record]},
        series_episode_lists={56: [{"id": 906, "seriesId": 56, "seasonNumber": 1, "episodeNumber": 1}]},
    )
    client = _client(fake)

    row = await _seed(db, item_id=56, season_number=1, missing_count=1, timestamp=base)

    try:
        counts = await run_tracking_check(
            db, client, "Sonarr", "Main", tracking_window_minutes=60, instance_stable_id="sid-main",
        )
    finally:
        await client.close()

    assert counts["identity_skipped"] == 1
    assert await _outcome(db, row) == "unresolved"
    owned = await get_owned_grabs(db, app="Sonarr", instance_stable_id="sid-main", series_id=56)
    assert len(owned) == 0
    assert len(_list_requests(fake)) == 1
    assert len(_per_id_requests(fake)) == 0  # entry found in the list; no fallback needed
    await db.close()


async def test_client_path_v5_bounded_volume_out_of_window_never_resolved_or_counted(tmp_path):
    """Grabs needing resolution outside every pending search's window are dropped
    silently: never resolved, never counted in identity_skipped, and when a whole
    group has nothing in-window, it makes no episode request at all."""
    db = await _init_db(tmp_path)
    real_records = load_sonarr_fixture("history_season_pack_v5")
    series_list = load_sonarr_series_episode_list("episodes_v5", 1)

    # A second, synthetic series whose only grab (needing resolution, v5-shaped) is
    # dated long before its own pending search -- nothing in-window for this group.
    out_of_window_record = {
        "id": 50001, "episodeId": 9001, "seriesId": 777,
        "sourceTitle": "Synthetic.Show.1080p-GRP",
        "date": "2020-01-01T00:00:00Z",
        "eventType": "grabbed", "downloadId": "DL-OOW", "data": {},
    }
    fake = _SonarrHistoryFake(
        {1: real_records, 777: [out_of_window_record]},
        series_episode_lists={1: series_list},
    )
    client = _client(fake)

    search_time = datetime.fromisoformat("2026-10-19T23:34:45.161529+00:00")
    row_s2 = await _seed(db, item_id=1, season_number=2, missing_count=8, timestamp=search_time)
    row_oow = await _seed(db, item_id=777, season_number=1, missing_count=1, timestamp=datetime.now(UTC))

    try:
        counts = await run_tracking_check(
            db, client, "Sonarr", "Main", tracking_window_minutes=60, instance_stable_id="sid-main",
        )
    finally:
        await client.close()

    assert await _outcome(db, row_s2) == "grabbed"
    assert counts["identity_skipped"] == 0  # 10 S1 records + the out-of-window record, never counted
    assert len(_list_requests(fake)) == 1  # only series 1 (in-window); series 777 never attempted
    assert all(r.url.params.get("seriesId") != "777" for r in _list_requests(fake))
    assert len(_per_id_requests(fake)) == 0
    owned_oow = await get_owned_grabs(db, app="Sonarr", instance_stable_id="sid-main", series_id=777)
    assert len(owned_oow) == 0
    assert await _outcome(db, row_oow) == "searched"
    await db.close()


async def test_client_path_v5_v4_shape_makes_zero_episode_requests(tmp_path):
    """v4-shaped records (valid nested season) never trigger an episode request --
    the v4 attribution path is unchanged."""
    db = await _init_db(tmp_path)
    records = load_sonarr_fixture("history_standard_v4")
    fake = _SonarrHistoryFake({101: records})
    client = _client(fake)

    base = datetime(2026, 1, 9, tzinfo=UTC)
    row = await _seed(db, item_id=101, season_number=1, missing_count=2, timestamp=base)

    try:
        await run_tracking_check(
            db, client, "Sonarr", "Main", tracking_window_minutes=_WIDE_WINDOW, instance_stable_id="sid-main",
        )
    finally:
        await client.close()

    assert await _outcome(db, row) == "grabbed"
    assert len(_list_requests(fake)) == 0
    assert len(_per_id_requests(fake)) == 0
    await db.close()


async def test_client_path_v5_synthesized_multi_season_credits_by_canonical_season(tmp_path):
    """v5-shaped synthesized coverage: a multi-season pack (no nested episode on any
    history record, full identity in the series list) credits each season's search
    independently by Sonarr's canonical season."""
    db = await _init_db(tmp_path)
    nested_records = load_sonarr_fixture("history_multi_season_pack_nested_synth")
    history, episode_list = _to_v5_shape(nested_records)
    fake = _SonarrHistoryFake({303: history}, series_episode_lists={303: episode_list})
    client = _client(fake)

    base = datetime(2026, 2, 28, tzinfo=UTC)
    row_s1 = await _seed(db, item_id=303, season_number=1, missing_count=3, timestamp=base)
    row_s2 = await _seed(db, item_id=303, season_number=2, missing_count=3, timestamp=base)

    try:
        await run_tracking_check(
            db, client, "Sonarr", "Main", tracking_window_minutes=_WIDE_WINDOW, instance_stable_id="sid-main",
        )
    finally:
        await client.close()

    assert await _outcome(db, row_s1) == "grabbed"
    assert "3/3" in await _detail(db, row_s1)
    assert await _outcome(db, row_s2) == "grabbed"
    assert "3/3" in await _detail(db, row_s2)
    assert len(_list_requests(fake)) == 1
    await db.close()


async def test_client_path_v5_synthesized_alternate_order_credits_by_canonical_season(tmp_path):
    """v5-shaped synthesized coverage: scene numbering reporting the wrong season (no
    nested episode on any history record) never overrides Sonarr's canonical season,
    resolved entirely from the series list."""
    db = await _init_db(tmp_path)
    nested_records = load_sonarr_fixture("history_alternate_order_nested_synth")
    history, episode_list = _to_v5_shape(nested_records)
    fake = _SonarrHistoryFake({404: history}, series_episode_lists={404: episode_list})
    client = _client(fake)

    base = datetime(2026, 3, 31, tzinfo=UTC)
    row_s1 = await _seed(db, item_id=404, season_number=1, missing_count=3, timestamp=base)
    row_s2 = await _seed(db, item_id=404, season_number=2, missing_count=1, timestamp=base)

    try:
        await run_tracking_check(
            db, client, "Sonarr", "Main", tracking_window_minutes=_WIDE_WINDOW, instance_stable_id="sid-main",
        )
    finally:
        await client.close()

    assert await _outcome(db, row_s1) == "grabbed"
    assert "3/3" in await _detail(db, row_s1)
    assert await _outcome(db, row_s2) == "grabbed"
    assert "1/1" in await _detail(db, row_s2)
    assert len(_list_requests(fake)) == 1
    await db.close()


async def test_client_path_conflicting_identity_not_counted(tmp_path):
    """R2, R6: conflicting or missing series identity is skipped and counted, never logging the title."""
    db = await _init_db(tmp_path)
    base_record = load_sonarr_fixture("history_standard_v4")[0]

    conflicting_episode_id = copy.deepcopy(base_record)
    conflicting_episode_id["id"] = 30001
    conflicting_episode_id["episode"] = {**conflicting_episode_id["episode"], "id": 999}

    series_mismatch_top = copy.deepcopy(base_record)
    series_mismatch_top["id"] = 30002
    series_mismatch_top["seriesId"] = 999

    series_mismatch_episode = copy.deepcopy(base_record)
    series_mismatch_episode["id"] = 30003
    series_mismatch_episode["episode"] = {**series_mismatch_episode["episode"], "seriesId": 999}

    no_series_id = copy.deepcopy(base_record)
    no_series_id["id"] = 30004
    del no_series_id["seriesId"]
    no_series_id["episode"] = {k: v for k, v in no_series_id["episode"].items() if k != "seriesId"}

    records = [conflicting_episode_id, series_mismatch_top, series_mismatch_episode, no_series_id]

    fake = _SonarrHistoryFake({101: records})
    client = _client(fake)

    captured: list[str] = []
    sink_id = logger.add(lambda m: captured.append(str(m)), level="WARNING")

    base = datetime(2026, 1, 9, tzinfo=UTC)
    row_id = await _seed(db, item_id=101, season_number=1, missing_count=1, timestamp=base)

    try:
        counts = await run_tracking_check(
            db, client, "Sonarr", "Main", tracking_window_minutes=_WIDE_WINDOW, instance_stable_id="sid-main",
        )
    finally:
        await client.close()
        logger.remove(sink_id)

    assert counts["identity_skipped"] == 4
    assert await _outcome(db, row_id) == "searched"
    owned = await get_owned_grabs(db, app="Sonarr", instance_stable_id="sid-main", series_id=101)
    assert len(owned) == 0

    warning_lines = [m for m in captured if "skipped grab" in m]
    assert len(warning_lines) == 4
    for grab_id in (30001, 30002, 30003, 30004):
        assert any(str(grab_id) in line for line in warning_lines)
    # Never log the release title.
    assert not any("WEB-DL" in line for line in warning_lines)
    await db.close()


async def test_client_path_v5_definitive_skip_counted_when_group_deferred(tmp_path):
    """A definitively bad grab (series mismatch) is still logged and counted in
    identity_skipped on a check where another grab in the same series hits a
    transient lookup failure and the row is deferred (not yet escalated)."""
    db = await _init_db(tmp_path)
    when = datetime.now(UTC) - timedelta(minutes=10)
    record_bad = {
        "id": 70090, "episodeId": 951, "seriesId": 61,
        "sourceTitle": "MixedGroup.1080p-GRP", "date": when.isoformat().replace("+00:00", "Z"),
        "eventType": "grabbed", "downloadId": "DL-MIXED1", "data": {},
    }
    record_transient = {
        "id": 70091, "episodeId": 952, "seriesId": 61,
        "sourceTitle": "MixedGroup.1080p-GRP", "date": when.isoformat().replace("+00:00", "Z"),
        "eventType": "grabbed", "downloadId": "DL-MIXED2", "data": {},
    }
    fake = _SonarrHistoryFake(
        {61: [record_bad, record_transient]},
        series_episode_lists={61: []},  # both ids need the per-id fallback
        episodes={951: {"id": 951, "seriesId": 999, "seasonNumber": 1, "episodeNumber": 1}},
    )
    fake.episode_status[952] = 500
    client = _client(fake)

    search_time = datetime.now(UTC) - timedelta(minutes=15)
    row = await _seed(db, item_id=61, season_number=1, missing_count=2, timestamp=search_time)

    try:
        counts = await run_tracking_check(
            db, client, "Sonarr", "Main", tracking_window_minutes=60, instance_stable_id="sid-main",
        )
    finally:
        await client.close()

    assert await _outcome(db, row) == "searched"  # deferred by the transient grab
    assert counts["identity_skipped"] == 1  # the series-mismatch grab is still counted
    assert counts["errors"] == 1
    owned = await get_owned_grabs(db, app="Sonarr", instance_stable_id="sid-main", series_id=61)
    assert len(owned) == 0
    await db.close()


async def test_client_path_v5_grab_between_row_windows_not_resolved(tmp_path):
    """A grab needing resolution that falls between two pending rows' windows (inside
    their combined span but outside each row's own window) can never be credited, so
    it makes no episode request and is not counted."""
    db = await _init_db(tmp_path)
    now_ref = datetime.now(UTC)
    grab_time = now_ref - timedelta(hours=3)
    record = {
        "id": 70095, "episodeId": 961, "seriesId": 62,
        "sourceTitle": "BetweenWindows.1080p-GRP", "date": grab_time.isoformat().replace("+00:00", "Z"),
        "eventType": "grabbed", "downloadId": "DL-BETWEEN", "data": {},
    }
    fake = _SonarrHistoryFake(
        {62: [record]},
        series_episode_lists={62: [{"id": 961, "seriesId": 62, "seasonNumber": 1, "episodeNumber": 1}]},
    )
    client = _client(fake)

    await _seed(db, item_id=62, season_number=1, missing_count=1, timestamp=now_ref - timedelta(hours=5))
    await _seed(db, item_id=62, season_number=1, missing_count=1, timestamp=now_ref - timedelta(minutes=30))

    try:
        counts = await run_tracking_check(
            db, client, "Sonarr", "Main", tracking_window_minutes=60, instance_stable_id="sid-main",
        )
    finally:
        await client.close()

    assert counts["identity_skipped"] == 0
    assert len(_list_requests(fake)) == 0
    assert len(_per_id_requests(fake)) == 0
    owned = await get_owned_grabs(db, app="Sonarr", instance_stable_id="sid-main", series_id=62)
    assert len(owned) == 0
    await db.close()
