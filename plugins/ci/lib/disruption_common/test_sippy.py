"""Tests for disruption_common.sippy — windowed paging and disruption lookups."""
import datetime
import http.client
import json
import os
import sys
import urllib.error
from io import BytesIO
from unittest.mock import patch

import pytest

# Run as a script (make test), the package parent is not on sys.path yet.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from disruption_common import sippy  # noqa: E402
from disruption_common.sippy import (  # noqa: E402
    SippyError,
    build_sippy_filter,
    collect_runs,
    fetch_disruption_data,
    fetch_runs,
    fetch_runs_in_window,
    parse_timestamp,
)

SINCE = datetime.datetime(2026, 9, 28, tzinfo=datetime.timezone.utc)


def _urlopen_returning(data):
    class Response:
        def __enter__(self):
            return BytesIO(json.dumps(data).encode("utf-8"))

        def __exit__(self, *args):
            return False

    return Response()


def _timestamp_filters(filter_dict):
    return [(item["operatorValue"], item["value"])
            for item in filter_dict["items"] if item["columnField"] == "timestamp"]


def test_build_sippy_filter_rfc3339_bounds():
    until = SINCE + datetime.timedelta(days=1)
    f = build_sippy_filter({"Platform": "aws"}, SINCE, until)
    assert f["items"][0]["value"] == "Platform:aws"
    assert _timestamp_filters(f) == [(">", "2026-09-28T00:00:00Z"), ("<", "2026-09-29T00:00:00Z")]


def test_fetch_runs_raises_on_connection_error():
    with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("refused")):
        with pytest.raises(SippyError, match="failed to connect"):
            fetch_runs("5.0", build_sippy_filter({}, SINCE), 10)


@patch("disruption_common.sippy.fetch_runs")
def test_fetch_runs_in_window_respects_max_runs(mock_fetch_runs):
    mock_fetch_runs.return_value = [
        {"prow_id": str(i), "timestamp": "2026-10-0%dT00:00:00Z" % (9 - i)} for i in range(3)]
    rows, truncated = fetch_runs_in_window("5.0", {}, SINCE, page_size=3, max_runs=2)
    assert truncated is True
    assert len(rows) == 2


@patch("disruption_common.sippy.fetch_runs")
def test_collect_runs_queries_each_multi_value_combo(mock_fetch_runs):
    def fake_fetch(_release, filter_dict, _limit):
        platform = [i["value"] for i in filter_dict["items"] if i["columnField"] == "variants"][0]
        if platform == "Platform:aws":
            return [{"prow_id": "A", "timestamp": "2026-10-02T00:00:00Z"}]
        return [{"prow_id": "G", "timestamp": "2026-10-03T00:00:00Z"},
                {"prow_id": "A", "timestamp": "2026-10-02T00:00:00Z"}]

    mock_fetch_runs.side_effect = fake_fetch
    rows, _truncated = collect_runs("5.0", {"Platform": "aws,gcp"}, SINCE)
    assert [row["prow_id"] for row in rows] == ["G", "A"]


def test_collect_runs_rejects_too_many_combos():
    variants = {"A": "1,2,3", "B": "1,2,3", "C": "1,2,3"}
    with pytest.raises(SippyError, match="variant combinations"):
        collect_runs("5.0", variants, SINCE)


def test_fetch_disruption_data_keeps_tag_job_and_master_field():
    api = {"rows": [
        {"backend_name": "kube-api-new-connections", "disruption_seconds": 7, "job_run_name": "1",
         "release_tag": "5.0.0-0.nightly-2026-11-03-192557", "job_name": "job-a",
         "master_nodes_updated": "Y"},
        {"backend_name": "kube-api-new-connections", "disruption_seconds": 0, "job_run_name": "2",
         "release_tag": "", "job_name": "job-b"},
    ]}
    with patch("urllib.request.urlopen", return_value=_urlopen_returning(api)):
        result = fetch_disruption_data(["1", "2"])
    assert result["1"] == [{"backend_name": "kube-api-new-connections", "disruption_seconds": 7,
                            "release_tag": "5.0.0-0.nightly-2026-11-03-192557", "job_name": "job-a",
                            "master_nodes_updated": "Y"}]
    assert "master_nodes_updated" not in result["2"][0]


def test_fetch_disruption_data_cache_skips_known_runs_and_empty_results(tmp_path):
    cache = tmp_path / "cache" / "disruption.json"
    cache.parent.mkdir()
    cache.write_text(json.dumps({"1": [{"backend_name": "x", "disruption_seconds": 3}]}))
    api = {"rows": [{"backend_name": "x", "disruption_seconds": 5, "job_run_name": "2"}]}
    with patch.object(sippy, "_fetch_disruption_batch", return_value=api["rows"]) as batch:
        result = fetch_disruption_data(["1", "2", "3"], cache_path=str(cache))
    batch.assert_called_once_with(["2", "3"])
    assert result["1"][0]["disruption_seconds"] == 3
    assert result["2"][0]["disruption_seconds"] == 5
    saved = json.loads(cache.read_text())
    assert set(saved) == {"1", "2"}


def test_fetch_disruption_data_builds_lookup():
    api_response = {
        "rows": [
            {"backend_name": "kube-api-new-connections", "disruption_seconds": 73,
             "job_run_name": "123"},
            {"backend_name": "cache-kube-api-new-connections", "disruption_seconds": 75,
             "job_run_name": "123"},
            {"backend_name": "kube-api-new-connections", "disruption_seconds": 10,
             "job_run_name": "456"},
        ],
    }
    with patch("urllib.request.urlopen",
               return_value=_urlopen_returning(api_response)):
        result = fetch_disruption_data(["123", "456"])

    assert "123" in result
    assert len(result["123"]) == 2
    assert result["123"][0]["disruption_seconds"] == 73
    assert "456" in result
    assert len(result["456"]) == 1


def test_fetch_disruption_data_empty_ids():
    assert fetch_disruption_data([]) == {}


def test_fetch_disruption_data_handles_error():
    with patch("urllib.request.urlopen",
               side_effect=urllib.error.URLError("connection refused")):
        result = fetch_disruption_data(["123"])
    assert result == {}


def test_fetch_disruption_data_keeps_master_nodes_updated():
    api_response = {
        "rows": [
            {"backend_name": "kube-api-new-connections", "disruption_seconds": 12,
             "job_run_name": "123", "master_nodes_updated": "Y"},
            {"backend_name": "kube-api-new-connections", "disruption_seconds": 4,
             "job_run_name": "456", "master_nodes_updated": None},
        ],
    }
    with patch("urllib.request.urlopen",
               return_value=_urlopen_returning(api_response)):
        result = fetch_disruption_data(["123", "456"])
    assert result["123"][0]["master_nodes_updated"] == "Y"
    assert result["456"][0]["master_nodes_updated"] == ""


def test_parse_timestamp_parses_z():
    assert parse_timestamp("2026-08-14T00:01:05Z") == datetime.datetime(
        2026, 8, 14, 0, 1, 5, tzinfo=datetime.timezone.utc
    )


def test_parse_timestamp_handles_missing_and_bad():
    # None, empty string, and unparseable strings all fall back to the epoch sentinel (no raise).
    epoch = datetime.datetime(1970, 1, 1, tzinfo=datetime.timezone.utc)
    assert parse_timestamp(None) == epoch
    assert parse_timestamp("") == epoch
    assert parse_timestamp("not-a-timestamp") == epoch


def test_parse_timestamp_normalizes_offset_to_utc():
    # A non-UTC offset is converted to the equivalent UTC time.
    utc = datetime.datetime(2026, 8, 14, 0, 1, 5, tzinfo=datetime.timezone.utc)
    assert parse_timestamp("2026-08-14T02:01:05+02:00") == parse_timestamp("2026-08-14T00:01:05Z")
    assert parse_timestamp("2026-08-14T02:01:05+02:00") == utc


def test_parse_timestamp_accepts_int_epoch_ms():
    # Integer epoch-milliseconds convert to the matching UTC datetime.
    assert parse_timestamp(1704067200000) == datetime.datetime(
        2024, 1, 1, 0, 0, 0, tzinfo=datetime.timezone.utc
    )
    # Epoch-ms 0 maps to the 1970 epoch.
    assert parse_timestamp(0) == datetime.datetime(1970, 1, 1, tzinfo=datetime.timezone.utc)


def test_parse_timestamp_accepts_float_epoch_ms():
    # Float epoch-milliseconds keep sub-second precision (500 ms -> 500000 us).
    assert parse_timestamp(1704067200500.0) == datetime.datetime(
        2024, 1, 1, 0, 0, 0, 500000, tzinfo=datetime.timezone.utc
    )


def test_parse_timestamp_rejects_bool():
    # bool is a subclass of int, but True/False are not epoch-ms values, so they
    # fall through to the epoch sentinel instead of converting as 1/0.
    epoch = datetime.datetime(1970, 1, 1, tzinfo=datetime.timezone.utc)
    assert parse_timestamp(True) == epoch
    assert parse_timestamp(False) == epoch


def test_parse_timestamp_non_finite_or_overflow_returns_epoch():
    # Infinity, NaN, and out-of-range magnitudes fall back to the epoch sentinel
    # rather than raising out of datetime.fromtimestamp.
    epoch = datetime.datetime(1970, 1, 1, tzinfo=datetime.timezone.utc)
    assert parse_timestamp(float("inf")) == epoch
    assert parse_timestamp(float("-inf")) == epoch
    assert parse_timestamp(float("nan")) == epoch
    assert parse_timestamp(10**1000) == epoch


def test_parse_timestamp_naive_string_is_utc():
    # A string with no Z suffix or offset is interpreted as UTC.
    utc = datetime.datetime(2026, 8, 14, 0, 1, 5, tzinfo=datetime.timezone.utc)
    assert parse_timestamp("2026-08-14T00:01:05") == utc
    assert parse_timestamp("2026-08-14T00:01:05") == parse_timestamp("2026-08-14T00:01:05Z")


def test_build_sippy_filter_timestamp_is_rfc3339():
    since = datetime.datetime(2026, 8, 14, 0, 1, 5, tzinfo=datetime.timezone.utc)
    f = build_sippy_filter({"Platform": "gcp"}, since)
    assert f["items"][0] == {
        "columnField": "variants", "operatorValue": "has entry", "value": "Platform:gcp",
    }
    assert {
        "columnField": "timestamp", "operatorValue": ">", "value": "2026-08-14T00:01:05Z",
    } in f["items"]
    assert f["linkOperator"] == "and"


def test_build_sippy_filter_no_since():
    f = build_sippy_filter({"Platform": "gcp"}, None)
    assert all(item["columnField"] != "timestamp" for item in f["items"])


@patch("disruption_common.sippy.fetch_runs")
def test_fetch_runs_in_window_pages_until_short_page_and_dedups(mock_fetch_runs):
    since = datetime.datetime(2026, 9, 28, tzinfo=datetime.timezone.utc)

    def fake_fetch(_release, filter_dict, _limit):
        bounds = _timestamp_filters(filter_dict)
        if ("<", "2026-09-29T12:00:00Z") in bounds:
            return [{"prow_id": "EDGE", "timestamp": "2026-09-28T03:00:00Z"}]
        if ("<", "2026-10-01T00:00:00Z") in bounds:
            return [
                {"prow_id": "MID", "timestamp": "2026-10-01T00:00:00Z"},
                {"prow_id": "OLDER", "timestamp": "2026-09-29T12:00:00Z"},
            ]
        if ("<", "2026-10-05T00:00:00Z") in bounds:
            return [{"prow_id": "MID", "timestamp": "2026-10-01T00:00:00Z"}]
        return [
            {"prow_id": "NEW", "timestamp": "2026-10-05T00:00:00Z"},
            {"prow_id": "MID", "timestamp": "2026-10-01T00:00:00Z"},
        ]

    mock_fetch_runs.side_effect = fake_fetch
    rows, truncated = fetch_runs_in_window(
        "5.0", {"Platform": "aws"}, since, page_size=2, max_runs=5000)
    assert truncated is False
    assert [row["prow_id"] for row in rows] == ["NEW", "MID", "OLDER", "EDGE"]
    filters = [_timestamp_filters(call[0][1]) for call in mock_fetch_runs.call_args_list]
    assert any(("<", "2026-10-01T00:00:00Z") in bounds for bounds in filters)
    assert any(("<", "2026-09-29T12:00:00Z") in bounds for bounds in filters)


@patch("disruption_common.sippy.fetch_runs")
def test_fetch_runs_in_window_keeps_equal_timestamps_across_page_boundary(mock_fetch_runs):
    since = datetime.datetime(2026, 9, 28, tzinfo=datetime.timezone.utc)

    def fake_fetch(_release, filter_dict, limit):
        bounds = _timestamp_filters(filter_dict)
        if any(op == "<" and value == "2026-10-02T00:00:00Z" for op, value in bounds):
            return [
                {"prow_id": "TIE-HIGH", "timestamp": "2026-10-01T00:00:00Z"},
                {"prow_id": "TIE-LOW", "timestamp": "2026-10-01T00:00:00Z"},
            ]
        if any(op == "<" and value == "2026-10-01T00:00:00Z" for op, value in bounds):
            return [{"prow_id": "OLDER", "timestamp": "2026-09-30T00:00:00Z"}]
        return [
            {"prow_id": "NEW", "timestamp": "2026-10-02T00:00:00Z"},
            {"prow_id": "TIE-HIGH", "timestamp": "2026-10-01T00:00:00Z"},
        ]

    mock_fetch_runs.side_effect = fake_fetch
    rows, truncated = fetch_runs_in_window(
        "5.0", {"Platform": "aws"}, since, page_size=2, max_runs=5000)
    assert truncated is False
    assert [row["prow_id"] for row in rows] == ["NEW", "TIE-HIGH", "TIE-LOW", "OLDER"]
    tie_calls = [
        call for call in mock_fetch_runs.call_args_list
        if ("<", "2026-10-02T00:00:00Z") in _timestamp_filters(call[0][1])
    ]
    assert tie_calls
    assert tie_calls[0][0][2] > 2


@patch("disruption_common.sippy.fetch_runs")
def test_fetch_runs_in_window_stops_at_window_start(mock_fetch_runs):
    since = datetime.datetime(2026, 9, 28, tzinfo=datetime.timezone.utc)
    mock_fetch_runs.return_value = [
        {"prow_id": "NEW", "timestamp": "2026-10-05T00:00:00Z"},
        {"prow_id": "AT_START", "timestamp": "2026-09-28T00:00:00Z"},
    ]
    rows, truncated = fetch_runs_in_window(
        "5.0", {"Platform": "aws"}, since, page_size=2, max_runs=5000)
    assert truncated is False
    assert mock_fetch_runs.call_count == 1
    assert [row["prow_id"] for row in rows] == ["NEW", "AT_START"]


def test_parse_timestamp_z_suffix_does_not_need_python_311():
    utc = datetime.timezone.utc
    assert parse_timestamp("2026-08-14T00:01:05.123456Z") == datetime.datetime(2026, 8, 14, 0, 1, 5, 123456, tzinfo=utc)
    assert parse_timestamp("2026-08-14T00:01:05z") == datetime.datetime(2026, 8, 14, 0, 1, 5, tzinfo=utc)


def test_malformed_rows_reach_the_sippy_error_path():
    with patch("urllib.request.urlopen", return_value=_urlopen_returning({"rows": "oops"})):
        with pytest.raises(SippyError, match="unexpected rows type"):
            fetch_runs("5.0", build_sippy_filter({}, SINCE), 10)
    with patch("urllib.request.urlopen", return_value=_urlopen_returning({"rows": ["junk", {"prow_id": "1"}]})):
        assert fetch_runs("5.0", build_sippy_filter({}, SINCE), 10) == [{"prow_id": "1"}]
    with patch("urllib.request.urlopen", return_value=_urlopen_returning({"rows": {"a": 1}})):
        assert fetch_disruption_data(["1"]) == {}


def test_seconds_rejects_booleans_and_non_numeric_values():
    assert sippy._seconds(True) is None
    assert sippy._seconds(False) is None
    assert sippy._seconds(None) is None
    assert sippy._seconds("n/a") is None
    assert sippy._seconds("4") == 4.0
    assert sippy._seconds(3) == 3


def test_fetch_disruption_data_drops_non_numeric_seconds():
    api = {"rows": [
        {"backend_name": "a", "disruption_seconds": None, "job_run_name": "1"},
        {"backend_name": "b", "disruption_seconds": "4", "job_run_name": "1"},
        {"backend_name": "c", "disruption_seconds": "n/a", "job_run_name": "1"},
        {"backend_name": "d", "disruption_seconds": True, "job_run_name": "1"},
        {"backend_name": "e", "disruption_seconds": 3, "job_run_name": "1"},
    ]}
    with patch("urllib.request.urlopen", return_value=_urlopen_returning(api)):
        result = fetch_disruption_data(["1"])
    assert [(e["backend_name"], e["disruption_seconds"]) for e in result["1"]] == [("b", 4.0), ("e", 3)]


@pytest.mark.parametrize("error", [TimeoutError("timed out"), http.client.IncompleteRead(b"par")])
def test_read_failures_reach_the_sippy_error_path(error):
    with patch("urllib.request.urlopen", side_effect=error):
        with pytest.raises(SippyError, match="failed to read"):
            fetch_runs("5.0", build_sippy_filter({}, SINCE), 10)
        assert fetch_disruption_data(["1"]) == {}


def test_non_utf8_body_reaches_the_sippy_error_path():
    class Response:
        def __enter__(self):
            return BytesIO(b"\xff\xfe")

        def __exit__(self, *args):
            return False

    with patch("urllib.request.urlopen", return_value=Response()):
        with pytest.raises(SippyError, match="not UTF-8"):
            fetch_runs("5.0", build_sippy_filter({}, SINCE), 10)


def test_cache_write_failure_is_a_warning(tmp_path, capsys):
    cache = tmp_path / "cache" / "disruption.json"
    api = [{"backend_name": "x", "disruption_seconds": 5, "job_run_name": "2"}]
    with patch.object(sippy, "_fetch_disruption_batch", return_value=api), \
            patch.object(sippy, "write_json_atomic", side_effect=PermissionError("read-only")):
        result = fetch_disruption_data(["2"], cache_path=str(cache))
    assert result["2"][0]["disruption_seconds"] == 5
    assert "could not write disruption cache" in capsys.readouterr().err


def _tie_rows(count):
    return [{"prow_id": "TIE-%02d" % i, "timestamp": "2026-10-01T00:00:00Z"} for i in range(count)]


@patch("disruption_common.sippy.fetch_runs")
def test_fetch_runs_in_window_keeps_a_tie_larger_than_the_page(mock_fetch_runs):
    ties = _tie_rows(7)

    def fake_fetch(_release, filter_dict, limit):
        bounds = _timestamp_filters(filter_dict)
        if ("<", "2026-10-02T00:00:00Z") in bounds:
            return ties[:limit]
        if ("<", "2026-10-01T00:00:00Z") in bounds:
            return [{"prow_id": "OLDER", "timestamp": "2026-09-30T00:00:00Z"}]
        return [{"prow_id": "NEW", "timestamp": "2026-10-02T00:00:00Z"}, ties[0]]

    mock_fetch_runs.side_effect = fake_fetch
    rows, truncated = fetch_runs_in_window("5.0", {}, SINCE, page_size=2)
    assert truncated is False
    assert [row["prow_id"] for row in rows] == ["NEW"] + [row["prow_id"] for row in ties] + ["OLDER"]
    tie_limits = [call[0][2] for call in mock_fetch_runs.call_args_list
                  if ("<", "2026-10-02T00:00:00Z") in _timestamp_filters(call[0][1])]
    assert tie_limits == [2, 4, 8]


@patch("disruption_common.sippy.fetch_runs")
def test_fetch_runs_in_window_marks_truncated_when_a_full_tie_page_has_nothing_new(mock_fetch_runs):
    seen_tie_row = _tie_rows(1)[0]

    def fake_fetch(_release, filter_dict, limit):
        if ("<", "2026-10-02T00:00:00Z") in _timestamp_filters(filter_dict):
            return [seen_tie_row] * limit
        return [{"prow_id": "NEW", "timestamp": "2026-10-02T00:00:00Z"}, seen_tie_row]

    mock_fetch_runs.side_effect = fake_fetch
    rows, truncated = fetch_runs_in_window("5.0", {}, SINCE, page_size=2)
    assert truncated is True
    assert [row["prow_id"] for row in rows] == ["NEW", "TIE-00"]


@patch("disruption_common.sippy.fetch_runs_in_window")
def test_collect_runs_reports_every_failed_combo(mock_window):
    def fake_window(_release, variants, _since, max_runs=None, progress=None):
        if variants["Platform"] == "aws":
            return [{"prow_id": "A", "timestamp": "2026-10-02T00:00:00Z"}], False
        raise SippyError("HTTP 500 from Sippy runs API: %s down" % variants["Platform"])

    mock_window.side_effect = fake_window
    with pytest.raises(SippyError) as excinfo:
        collect_runs("5.0", {"Platform": "aws,gcp,azure"}, SINCE)
    message = str(excinfo.value)
    assert message.startswith("2 of 3 variant combinations failed")
    assert "Platform=gcp: HTTP 500 from Sippy runs API: gcp down" in message
    assert "Platform=azure: HTTP 500 from Sippy runs API: azure down" in message


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
