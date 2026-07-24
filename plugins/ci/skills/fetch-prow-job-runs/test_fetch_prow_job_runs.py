from fetch_prow_job_runs import build_filter, since_millis, extract_ids


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


def test_build_filter_since_ms_is_string():
    f = build_filter([], [], None, 1750000000000, [])
    assert f["items"] == [
        {"columnField": "timestamp", "operatorValue": ">", "value": "1750000000000"},
    ]


def test_build_filter_extra_items_merged_last():
    extra = [{"columnField": "cluster", "operatorValue": "equals", "value": "build09"}]
    f = build_filter(["e2e"], [], None, None, extra)
    assert f["items"][-1] == extra[0]
    assert len(f["items"]) == 2


def test_build_filter_all_combined():
    f = build_filter(["e2e"], ["Platform:metal"], "n", 123, [])
    fields = [i["columnField"] for i in f["items"]]
    assert fields == ["name", "variants", "overall_result", "timestamp"]
    assert f["linkOperator"] == "and"


def test_since_millis():
    now_ms = 1_750_000_000_000
    assert since_millis(24, now_ms) == now_ms - 24 * 3600 * 1000


def test_since_millis_fractional_hours():
    assert since_millis(0.5, 7_200_000) == 7_200_000 - 1_800_000


def test_extract_ids():
    rows = [{"prow_id": "111", "job": "a"}, {"prow_id": "222"}]
    assert extract_ids(rows) == ["111", "222"]


def test_extract_ids_empty():
    assert extract_ids([]) == []
