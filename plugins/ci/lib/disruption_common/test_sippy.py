"""Tests for disruption_common.sippy — windowed paging and disruption lookups."""
import datetime
import json
import urllib.error
from io import BytesIO
from unittest.mock import patch

import pytest

from disruption_common import sippy
from disruption_common.sippy import (
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


def test_parse_timestamp_variants():
    utc = datetime.timezone.utc
    assert parse_timestamp("2026-08-14T00:01:05Z") == datetime.datetime(2026, 8, 14, 0, 1, 5, tzinfo=utc)
    assert parse_timestamp("2026-08-14T02:00:00+02:00") == datetime.datetime(2026, 8, 14, tzinfo=utc)
    assert parse_timestamp(0) == datetime.datetime(1970, 1, 1, tzinfo=utc)
    assert parse_timestamp(True) == datetime.datetime(1970, 1, 1, tzinfo=utc)
    assert parse_timestamp("garbage") == datetime.datetime(1970, 1, 1, tzinfo=utc)


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
def test_fetch_runs_in_window_pages_and_dedups(mock_fetch_runs):
    def fake_fetch(_release, filter_dict, _limit):
        bounds = _timestamp_filters(filter_dict)
        if ("<", "2026-09-29T12:00:00Z") in bounds:
            return [{"prow_id": "EDGE", "timestamp": "2026-09-28T03:00:00Z"}]
        if ("<", "2026-10-01T00:00:00Z") in bounds:
            return [{"prow_id": "MID", "timestamp": "2026-10-01T00:00:00Z"},
                    {"prow_id": "OLDER", "timestamp": "2026-09-29T12:00:00Z"}]
        if ("<", "2026-10-05T00:00:00Z") in bounds:
            return [{"prow_id": "MID", "timestamp": "2026-10-01T00:00:00Z"}]
        return [{"prow_id": "NEW", "timestamp": "2026-10-05T00:00:00Z"},
                {"prow_id": "MID", "timestamp": "2026-10-01T00:00:00Z"}]

    mock_fetch_runs.side_effect = fake_fetch
    progress = []
    rows, truncated = fetch_runs_in_window(
        "5.0", {"Platform": "aws"}, SINCE, page_size=2, progress=lambda n, _ts: progress.append(n))
    assert truncated is False
    assert [row["prow_id"] for row in rows] == ["NEW", "MID", "OLDER", "EDGE"]
    assert progress and progress[-1] == 4


@patch("disruption_common.sippy.fetch_runs")
def test_fetch_runs_in_window_keeps_ties_across_page_boundary(mock_fetch_runs):
    def fake_fetch(_release, filter_dict, _limit):
        bounds = _timestamp_filters(filter_dict)
        if any(op == "<" and value == "2026-10-02T00:00:00Z" for op, value in bounds):
            return [{"prow_id": "TIE-HIGH", "timestamp": "2026-10-01T00:00:00Z"},
                    {"prow_id": "TIE-LOW", "timestamp": "2026-10-01T00:00:00Z"}]
        if any(op == "<" and value == "2026-10-01T00:00:00Z" for op, value in bounds):
            return [{"prow_id": "OLDER", "timestamp": "2026-09-30T00:00:00Z"}]
        return [{"prow_id": "NEW", "timestamp": "2026-10-02T00:00:00Z"},
                {"prow_id": "TIE-HIGH", "timestamp": "2026-10-01T00:00:00Z"}]

    mock_fetch_runs.side_effect = fake_fetch
    rows, _truncated = fetch_runs_in_window("5.0", {"Platform": "aws"}, SINCE, page_size=2)
    assert [row["prow_id"] for row in rows] == ["NEW", "TIE-HIGH", "TIE-LOW", "OLDER"]


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


def test_fetch_disruption_data_failure_is_a_warning():
    with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("refused")):
        assert fetch_disruption_data(["1"]) == {}
    assert fetch_disruption_data([]) == {}


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
