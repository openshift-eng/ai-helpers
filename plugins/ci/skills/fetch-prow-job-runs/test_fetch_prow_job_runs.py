import datetime

from fetch_prow_job_runs import build_filter, extract_ids, since_cutoff


def test_build_filter_empty():
    f = build_filter([], [], None, None, [])
    assert f == {"items": [], "linkOperator": "and"}


def test_build_filter_job_contains():
    f = build_filter(["e2e-metal", "ipi"], [], None, None, [])
    assert f["items"] == [
        {"columnField": "name", "operatorValue": "contains", "value": "e2e-metal"},
        {"columnField": "name", "operatorValue": "contains", "value": "ipi"},
    ]
    assert f["linkOperator"] == "and"


def test_build_filter_variants():
    f = build_filter([], ["Platform:metal", "Network:ovn"], None, None, [])
    assert f["items"] == [
        {"columnField": "variants", "operatorValue": "has entry", "value": "Platform:metal"},
        {"columnField": "variants", "operatorValue": "has entry", "value": "Network:ovn"},
    ]


def test_build_filter_result():
    f = build_filter([], [], "F", None, [])
    assert f["items"] == [
        {"columnField": "overall_result", "operatorValue": "equals", "value": "F"},
    ]


def test_build_filter_timestamp_is_rfc3339():
    # build_filter formats the datetime to an RFC 3339 string for the query.
    since = datetime.datetime(2026, 8, 14, 0, 1, 5, tzinfo=datetime.timezone.utc)
    f = build_filter([], [], None, since, [])
    assert f["items"] == [
        {"columnField": "timestamp", "operatorValue": ">", "value": "2026-08-14T00:01:05Z"},
    ]


def test_build_filter_extra_items_merged_last():
    extra = [{"columnField": "cluster", "operatorValue": "equals", "value": "build09"}]
    f = build_filter(["e2e"], [], None, None, extra)
    assert f["items"][-1] == extra[0]
    assert len(f["items"]) == 2


def test_build_filter_all_combined():
    since = datetime.datetime(2026, 8, 14, 0, 1, 5, tzinfo=datetime.timezone.utc)
    f = build_filter(["e2e"], ["Platform:metal"], "n", since, [])
    fields = [i["columnField"] for i in f["items"]]
    assert fields == ["name", "variants", "overall_result", "timestamp"]
    assert f["linkOperator"] == "and"


def test_since_cutoff():
    # 25h after the epoch, minus 24h -> 1h after the epoch.
    now = datetime.datetime(1970, 1, 2, 1, 0, 0, tzinfo=datetime.timezone.utc)
    assert since_cutoff(24, now) == datetime.datetime(
        1970, 1, 1, 1, 0, 0, tzinfo=datetime.timezone.utc
    )


def test_since_cutoff_fractional_hours():
    # 2h after the epoch, minus 0.5h -> 1.5h after the epoch.
    now = datetime.datetime(1970, 1, 1, 2, 0, 0, tzinfo=datetime.timezone.utc)
    assert since_cutoff(0.5, now) == datetime.datetime(
        1970, 1, 1, 1, 30, 0, tzinfo=datetime.timezone.utc
    )


def test_since_cutoff_defaults_to_now_utc():
    # Without an explicit `now`, the cutoff is timezone-aware UTC and offset by `hours`.
    before = datetime.datetime.now(datetime.timezone.utc)
    cutoff = since_cutoff(24)
    after = datetime.datetime.now(datetime.timezone.utc)
    assert cutoff.tzinfo is not None
    assert before - datetime.timedelta(hours=24) <= cutoff <= after - datetime.timedelta(hours=24)


def test_build_filter_since_produces_rfc3339_value():
    # End-to-end: a since_cutoff datetime flows into the timestamp filter as RFC 3339.
    now = datetime.datetime(1970, 1, 1, 2, 0, 0, tzinfo=datetime.timezone.utc)
    since = since_cutoff(1, now)  # 1h after the epoch
    f = build_filter([], [], None, since, [])
    item = f["items"][0]
    assert item["columnField"] == "timestamp"
    assert item["value"] == "1970-01-01T01:00:00Z"


def test_extract_ids():
    rows = [{"prow_id": "111", "job": "a"}, {"prow_id": "222"}]
    assert extract_ids(rows) == ["111", "222"]


def test_extract_ids_empty():
    assert extract_ids([]) == []
