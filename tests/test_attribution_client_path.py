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
from datetime import UTC, datetime

import aiosqlite
import httpx
from loguru import logger
from pydantic import SecretStr

from tests.sonarr_fixtures import load_sonarr_fixture
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
    """Serves fixture grab-history records for one or more series IDs."""

    def __init__(self, records_by_series: dict[int, list[dict]]) -> None:
        self.records_by_series = records_by_series
        self.requests: list[httpx.Request] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if request.url.path == "/api/v3/history/series":
            series_id = int(request.url.params["seriesId"])
            records = self.records_by_series.get(series_id, [])
            return httpx.Response(200, json=records)
        return httpx.Response(404, json={"error": "not found"})


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
