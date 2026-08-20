"""Tests for find_disruption_runs.py — URL parsing, backend parsing, disruption extraction."""
import datetime
import json
from io import BytesIO
from unittest.mock import patch

from find_disruption_runs import (
    _parse_timestamp,
    build_sippy_filter,
    extract_disruption_failures,
    fetch_disruption_data,
    format_timestamp,
    main,
    max_disruption_for_backend,
    parse_backend,
    parse_grafana_url,
    select_representative_runs,
)


def test_parse_grafana_url_extracts_vars():
    url = (
        "https://grafana-loki.ci.openshift.org/d/gEdw_aLvk/"
        "disruption-for-5-0-os-agnostic"
        "?orgId=1&var-percentile=P50&var-platform=gcp"
        "&var-backend=host-to-host-new-connections"
        "&var-upgrade_type=micro&var-releases=5.0"
    )
    result = parse_grafana_url(url)
    assert result["platform"] == "gcp"
    assert result["backend"] == "host-to-host-new-connections"
    assert result["upgrade_type"] == "micro"
    assert result["releases"] == "5.0"
    assert result["percentile"] == "P50"
    assert result["_dashboard_name"] == "disruption-for-5-0-os-agnostic"
    assert "orgId" not in result


def test_parse_grafana_url_multi_value():
    url = (
        "https://grafana-loki.ci.openshift.org/d/abc/dash"
        "?var-platform=azure&var-platform=gcp"
        "&var-backend=host-to-host-new-connections"
        "&var-releases=5.0&var-ipmode=ipv6&var-ipmode=ipv4"
        "&var-os=rhcos10&var-os=rhcos9"
    )
    result = parse_grafana_url(url)
    assert result["platform"] == "azure,gcp"
    assert result["backend"] == "host-to-host-new-connections"
    assert result["ipmode"] == "ipv6,ipv4"
    assert result["os"] == "rhcos10,rhcos9"
    assert result["releases"] == "5.0"


@patch("find_disruption_runs.fetch_disruption_data", return_value={})
@patch("find_disruption_runs.fetch_runs")
def test_multi_value_queries_and_dedup(mock_fetch_runs, _mock_disruption):
    """Multi-value params expand into separate queries, dedup by prow_id, sort by timestamp, and cap at --limit."""
    import io
    from contextlib import redirect_stdout

    # Base 2024-08-07T00:00:00Z; suffixes below give each row a distinct offset
    # (+50s/+30s/+10s azure, +40s/+10s/+5s gcp) as RFC 3339 strings.
    azure_rows = [
        {"prow_id": "A1", "timestamp": "2024-08-07T00:00:50Z", "job": "azure-job"},
        {"prow_id": "A2", "timestamp": "2024-08-07T00:00:30Z", "job": "azure-job"},
        {"prow_id": "SHARED", "timestamp": "2024-08-07T00:00:10Z", "job": "shared-job"},
    ]
    gcp_rows = [
        {"prow_id": "G1", "timestamp": "2024-08-07T00:00:40Z", "job": "gcp-job"},
        {"prow_id": "SHARED", "timestamp": "2024-08-07T00:00:10Z", "job": "shared-job"},
        {"prow_id": "G2", "timestamp": "2024-08-07T00:00:05Z", "job": "gcp-job"},
    ]
    mock_fetch_runs.side_effect = [azure_rows, gcp_rows]

    buf = io.StringIO()
    with redirect_stdout(buf):
        main([
            "--grafana-url",
            "https://grafana-loki.ci.openshift.org/d/abc/dash"
            "?var-platform=azure&var-platform=gcp"
            "&var-backend=kube-api-new-connections&var-releases=5.0",
            "--format", "json", "--limit", "4",
        ])
    output = json.loads(buf.getvalue())

    # Both platform values were queried
    assert mock_fetch_runs.call_count == 2
    platforms_queried = set()
    for call in mock_fetch_runs.call_args_list:
        filter_dict = call[0][1]  # positional: (release, filter_dict, limit)
        for item in filter_dict["items"]:
            if "Platform:" in item["value"]:
                platforms_queried.add(item["value"])
    assert platforms_queried == {"Platform:azure", "Platform:gcp"}

    # Dedup: SHARED appears once; limit enforced (5 unique -> capped to 4)
    prow_ids = [r["build_id"] for r in output]
    assert len(prow_ids) == 4
    assert len(set(prow_ids)) == 4
    assert "SHARED" in prow_ids

    # Output rows are sorted newest-first; the preserved RFC 3339 values
    # therefore appear in descending order.
    timestamps = [r["timestamp"] for r in output]
    assert timestamps == sorted(timestamps, reverse=True)
    assert timestamps[0] > timestamps[-1]


@patch("find_disruption_runs.fetch_disruption_data", return_value={})
@patch("find_disruption_runs.fetch_runs", return_value=[])
def test_multi_value_backend_rejected(_mock_fetch, _mock_disruption):
    """Multi-value var-backend should error, not silently produce garbage."""
    import io
    from contextlib import redirect_stderr

    buf = io.StringIO()
    try:
        with redirect_stderr(buf):
            main([
                "--grafana-url",
                "https://grafana-loki.ci.openshift.org/d/abc/dash"
                "?var-backend=host-to-host-new-connections&var-backend=kube-api-new-connections"
                "&var-releases=5.0",
            ])
        assert False, "should have exited"
    except SystemExit as e:
        assert e.code == 1
    assert "multiple backends not supported" in buf.getvalue()


@patch("find_disruption_runs.fetch_disruption_data", return_value={})
@patch("find_disruption_runs.fetch_runs", return_value=[])
def test_multi_value_release_rejected(_mock_fetch, _mock_disruption):
    """Multi-value var-releases should error, not silently query nonsense."""
    import io
    from contextlib import redirect_stderr

    buf = io.StringIO()
    try:
        with redirect_stderr(buf):
            main([
                "--grafana-url",
                "https://grafana-loki.ci.openshift.org/d/abc/dash"
                "?var-releases=5.0&var-releases=5.1"
                "&var-backend=kube-api-new-connections",
            ])
        assert False, "should have exited"
    except SystemExit as e:
        assert e.code == 1
    assert "multiple releases not supported" in buf.getvalue()


def test_parse_grafana_url_all_variants():
    url = (
        "https://grafana-loki.ci.openshift.org/d/abc/dash"
        "?var-platform=aws&var-architectures=arm64"
        "&var-topologies=single&var-networks=sdn"
        "&var-upgrade_type=minor&var-releases=4.18"
        "&var-backend=kube-api-reused-connections"
    )
    result = parse_grafana_url(url)
    assert result["platform"] == "aws"
    assert result["architectures"] == "arm64"
    assert result["topologies"] == "single"
    assert result["networks"] == "sdn"
    assert result["upgrade_type"] == "minor"
    assert result["releases"] == "4.18"
    assert result["backend"] == "kube-api-reused-connections"


def test_parse_grafana_url_featureset_ipmode_os():
    url = (
        "https://grafana-loki.ci.openshift.org/d/abc/dash"
        "?var-platform=aws&var-backend=kube-api-new-connections"
        "&var-releases=5.0&var-featureset=techpreview"
        "&var-ipmode=ipv6&var-os=rhcos10"
    )
    result = parse_grafana_url(url)
    assert result["featureset"] == "techpreview"
    assert result["ipmode"] == "ipv6"
    assert result["os"] == "rhcos10"


def test_parse_backend_new_connections():
    base, conn = parse_backend("host-to-host-new-connections")
    assert base == "host-to-host"
    assert conn == "new"


def test_parse_backend_reused_connections():
    base, conn = parse_backend("kube-api-reused-connections")
    assert base == "kube-api"
    assert conn == "reused"


def test_parse_backend_no_suffix():
    base, conn = parse_backend("oauth-api")
    assert base == "oauth-api"
    assert conn is None


def test_parse_backend_cache_prefix():
    base, conn = parse_backend("cache-kube-api-new-connections")
    assert base == "cache-kube-api"
    assert conn == "new"


def test_extract_disruption_failures_typical():
    names = [
        "[Monitor:apiserver-external-availability][sig-api-machinery] disruption/cache-kube-api apiserver/kube-apiserver connection/new should be available throughout the test",
        "[Monitor:apiserver-external-availability][sig-api-machinery] disruption/kube-api apiserver/kube-apiserver connection/new should be available throughout the test",
        "[sig-sippy] openshift-tests should work",
    ]
    result = extract_disruption_failures(names)
    assert result == ["cache-kube-api", "kube-api"]


def test_extract_disruption_failures_empty():
    assert extract_disruption_failures(None) == []
    assert extract_disruption_failures([]) == []


def test_extract_disruption_failures_no_disruption():
    names = ["[sig-sippy] openshift-tests should work"]
    assert extract_disruption_failures(names) == []


def test_extract_disruption_failures_dedup():
    names = [
        "disruption/metrics-api connection/new should be available throughout the test",
        "disruption/metrics-api connection/new should be available throughout the test",
    ]
    result = extract_disruption_failures(names)
    assert result == ["metrics-api"]


def test_max_disruption_for_backend_matching():
    entries = [
        {"backend_name": "kube-api-new-connections", "disruption_seconds": 73},
        {"backend_name": "kube-api-reused-connections", "disruption_seconds": 40},
        {"backend_name": "cache-kube-api-new-connections", "disruption_seconds": 75},
        {"backend_name": "oauth-api-new-connections", "disruption_seconds": 5},
    ]
    # Should match both connection types but exclude cache variant
    assert max_disruption_for_backend(entries, "kube-api") == 73


def test_max_disruption_for_backend_cache_target():
    entries = [
        {"backend_name": "cache-kube-api-new-connections", "disruption_seconds": 300},
        {"backend_name": "cache-kube-api-reused-connections", "disruption_seconds": 50},
        {"backend_name": "kube-api-new-connections", "disruption_seconds": 73},
    ]
    # When the target is a cache backend, only cache variants should match
    assert max_disruption_for_backend(entries, "cache-kube-api") == 300


def test_max_disruption_for_backend_no_match():
    entries = [
        {"backend_name": "oauth-api-new-connections", "disruption_seconds": 5},
    ]
    assert max_disruption_for_backend(entries, "kube-api") == 0


def test_max_disruption_for_backend_empty():
    assert max_disruption_for_backend([], "kube-api") is None
    assert max_disruption_for_backend(None, "kube-api") is None


def _mock_urlopen(response_data):
    """Create a mock context manager for urllib.request.urlopen."""
    body = json.dumps(response_data).encode("utf-8")
    mock_resp = BytesIO(body)
    mock_resp.status = 200

    class ContextManager:
        def __enter__(self):
            return mock_resp
        def __exit__(self, *args):
            pass

    return ContextManager()


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
    with patch("find_disruption_runs.urllib.request.urlopen",
               return_value=_mock_urlopen(api_response)):
        result = fetch_disruption_data(["123", "456"], "kube-api")

    assert "123" in result
    assert len(result["123"]) == 2
    assert result["123"][0]["disruption_seconds"] == 73
    assert "456" in result
    assert len(result["456"]) == 1


def test_fetch_disruption_data_empty_ids():
    assert fetch_disruption_data([]) == {}


def test_fetch_disruption_data_handles_error():
    import urllib.error
    with patch("find_disruption_runs.urllib.request.urlopen",
               side_effect=urllib.error.URLError("connection refused")):
        result = fetch_disruption_data(["123"])
    assert result == {}


def _make_disruption_data(mapping):
    """Helper: {prow_id: seconds} -> disruption_data dict."""
    data = {}
    for pid, secs in mapping.items():
        data[str(pid)] = [{"backend_name": "kube-api-new-connections", "disruption_seconds": secs}]
    return data


def test_select_empty_input():
    assert select_representative_runs([], {}, "kube-api", n=5) == []


def test_select_returns_all_when_fewer_than_n():
    rows = [
        {"prow_id": "1", "job": "job-a", "timestamp": "1970-01-01T00:16:40Z"},
        {"prow_id": "2", "job": "job-b", "timestamp": "1970-01-01T00:33:20Z"},
    ]
    dd = _make_disruption_data({"1": 10, "2": 20})
    result = select_representative_runs(rows, dd, "kube-api", n=5)
    assert sorted(result) == [0, 1]


def test_select_n1_picks_highest():
    rows = [
        {"prow_id": "1", "job": "job-a", "timestamp": "1970-01-01T00:16:40Z"},
        {"prow_id": "2", "job": "job-b", "timestamp": "1970-01-01T00:33:20Z"},
        {"prow_id": "3", "job": "job-c", "timestamp": "1970-01-01T00:50:00Z"},
    ]
    dd = _make_disruption_data({"1": 10, "2": 50, "3": 30})
    result = select_representative_runs(rows, dd, "kube-api", n=1)
    assert result == [1]


def test_select_deduplicates_same_job_within_60s():
    # job-a runs are 50s apart (00:16:40 -> 00:17:30), inside the 60s window.
    rows = [
        {"prow_id": "1", "job": "job-a", "timestamp": "1970-01-01T00:16:40Z"},
        {"prow_id": "2", "job": "job-a", "timestamp": "1970-01-01T00:17:30Z"},
        {"prow_id": "3", "job": "job-b", "timestamp": "1970-01-01T00:33:20Z"},
    ]
    dd = _make_disruption_data({"1": 10, "2": 30, "3": 20})
    result = select_representative_runs(rows, dd, "kube-api", n=5)
    assert 0 not in result
    assert 1 in result
    assert 2 in result


def test_select_deduplicates_cross_job_within_5s():
    # Rows 0 and 1 are different jobs 3s apart (00:16:40 -> 00:16:43), inside 5s.
    rows = [
        {"prow_id": "1", "job": "job-a", "timestamp": "1970-01-01T00:16:40Z"},
        {"prow_id": "2", "job": "job-b", "timestamp": "1970-01-01T00:16:43Z"},
        {"prow_id": "3", "job": "job-c", "timestamp": "1970-01-01T00:33:20Z"},
    ]
    dd = _make_disruption_data({"1": 10, "2": 50, "3": 20})
    result = select_representative_runs(rows, dd, "kube-api", n=5)
    assert 0 not in result
    assert 1 in result
    assert 2 in result


def test_select_cross_job_dedup_anchor_based():
    # Anchor=row0 (00:16:40). Row1 +4s (00:16:44) merges; row2 +9s (00:16:49)
    # is >5s from the anchor and starts a new cluster.
    rows = [
        {"prow_id": "1", "job": "job-a", "timestamp": "1970-01-01T00:16:40Z"},
        {"prow_id": "2", "job": "job-b", "timestamp": "1970-01-01T00:16:44Z"},
        {"prow_id": "3", "job": "job-c", "timestamp": "1970-01-01T00:16:49Z"},
    ]
    dd = _make_disruption_data({"1": 10, "2": 50, "3": 30})
    result = select_representative_runs(rows, dd, "kube-api", n=5)
    # Anchor=row0. Row1 is 4s from anchor -> merge. Row2 is 9s from anchor -> new cluster.
    assert 0 not in result
    assert 1 in result
    assert 2 in result


def test_select_prefers_job_diversity():
    rows = [
        {"prow_id": "1", "job": "job-a", "timestamp": "1970-01-01T00:16:40Z"},
        {"prow_id": "2", "job": "job-a", "timestamp": "1970-01-01T00:33:20Z"},
        {"prow_id": "3", "job": "job-a", "timestamp": "1970-01-01T00:50:00Z"},
        {"prow_id": "4", "job": "job-a", "timestamp": "1970-01-01T01:06:40Z"},
        {"prow_id": "5", "job": "job-b", "timestamp": "1970-01-01T01:23:20Z"},
        {"prow_id": "6", "job": "job-c", "timestamp": "1970-01-01T01:40:00Z"},
    ]
    dd = _make_disruption_data({str(i+1): (i+1)*10 for i in range(6)})
    result = select_representative_runs(rows, dd, "kube-api", n=3)
    jobs_selected = [rows[i]["job"] for i in result]
    assert "job-b" in jobs_selected
    assert "job-c" in jobs_selected


def test_select_includes_disruption_diversity():
    rows = [
        {"prow_id": str(i+1), "job": "job-%s" % chr(97+i), "timestamp": "1970-01-01T%02d:00:00Z" % i}
        for i in range(9)
    ]
    dd = _make_disruption_data({
        "1": 100, "2": 90, "3": 80, "4": 50, "5": 40,
        "6": 30, "7": 10, "8": 5, "9": 0,
    })
    result = select_representative_runs(rows, dd, "kube-api", n=5)
    secs = []
    for i in result:
        pid = str(rows[i]["prow_id"])
        s = max_disruption_for_backend(dd.get(pid, []), "kube-api")
        secs.append(s)
    assert any(s >= 80 for s in secs)
    assert any(s <= 10 for s in secs)


def test_select_excludes_none_disruption():
    rows = [
        {"prow_id": "1", "job": "job-a", "timestamp": "1970-01-01T00:16:40Z"},
        {"prow_id": "2", "job": "job-b", "timestamp": "1970-01-01T00:33:20Z"},
        {"prow_id": "3", "job": "job-c", "timestamp": "1970-01-01T00:50:00Z"},
    ]
    dd = _make_disruption_data({"1": 50})
    # prow_id 2 and 3 have no BQ data (None disruption) — should not be selected
    result = select_representative_runs(rows, dd, "kube-api", n=5)
    assert result == [0]
    assert 1 not in result
    assert 2 not in result


def test_select_returns_empty_when_all_none():
    rows = [
        {"prow_id": str(i+1), "job": "job-%s" % chr(97 + i % 3), "timestamp": "1970-01-01T%02d:00:00Z" % i}
        for i in range(6)
    ]
    result = select_representative_runs(rows, {}, "kube-api", n=3)
    assert result == []


def test_select_is_deterministic():
    rows = [
        {"prow_id": str(i+1), "job": "job-%s" % chr(97 + i % 4), "timestamp": "1970-01-01T%02d:00:00Z" % i}
        for i in range(20)
    ]
    dd = _make_disruption_data({str(i+1): (i * 7) % 100 for i in range(20)})
    r1 = select_representative_runs(rows, dd, "kube-api", n=5)
    r2 = select_representative_runs(rows, dd, "kube-api", n=5)
    assert r1 == r2


def test_select_zero_disruption_as_clean_comparison():
    # Clean run from same job as a disrupted run gets the clean-comparison slot.
    # Need >n disrupted candidates so the algorithm reaches Phase 5.5.
    rows = [
        {"prow_id": "1", "job": "job-a", "timestamp": "1970-01-01T00:16:40Z"},
        {"prow_id": "2", "job": "job-b", "timestamp": "1970-01-01T00:33:20Z"},
        {"prow_id": "3", "job": "job-c", "timestamp": "1970-01-01T00:50:00Z"},
        {"prow_id": "4", "job": "job-a", "timestamp": "1970-01-01T01:06:40Z"},
        {"prow_id": "5", "job": "job-b", "timestamp": "1970-01-01T01:23:20Z"},
        {"prow_id": "6", "job": "job-c", "timestamp": "1970-01-01T01:40:00Z"},
        {"prow_id": "7", "job": "job-d", "timestamp": "1970-01-01T01:56:40Z"},
        {"prow_id": "8", "job": "job-a", "timestamp": "1970-01-01T02:13:20Z"},  # same job as disrupted row 1
    ]
    dd = _make_disruption_data({
        "1": 100, "2": 80, "3": 60, "4": 40, "5": 30, "6": 20, "7": 10, "8": 0,
    })
    result = select_representative_runs(rows, dd, "kube-api", n=5)
    selected_secs = []
    for i in result:
        pid = str(rows[i]["prow_id"])
        selected_secs.append(max_disruption_for_backend(dd.get(pid, []), "kube-api"))
    assert 0 in selected_secs


def test_select_no_clean_from_unselected_job():
    # A 0s run shares a job with disrupted candidates, but that job is not in the selected set.
    # The clean-comparison slot should not pick it — only jobs in the selected set matter.
    rows = [
        {"prow_id": "1", "job": "job-a", "timestamp": "1970-01-01T00:16:40Z"},
        {"prow_id": "2", "job": "job-b", "timestamp": "1970-01-01T00:33:20Z"},
        {"prow_id": "3", "job": "job-c", "timestamp": "1970-01-01T00:50:00Z"},
        {"prow_id": "4", "job": "job-d", "timestamp": "1970-01-01T01:06:40Z"},
        {"prow_id": "5", "job": "job-a", "timestamp": "1970-01-01T01:23:20Z"},
        {"prow_id": "6", "job": "job-b", "timestamp": "1970-01-01T01:40:00Z"},
        {"prow_id": "7", "job": "job-c", "timestamp": "1970-01-01T01:56:40Z"},
        {"prow_id": "8", "job": "job-d", "timestamp": "1970-01-01T02:13:20Z"},
        {"prow_id": "9", "job": "job-e", "timestamp": "1970-01-01T02:30:00Z"},   # disrupted, unique job
        {"prow_id": "10", "job": "job-e", "timestamp": "1970-01-01T02:46:40Z"}, # 0s, same job as row 9
    ]
    dd = _make_disruption_data({
        "1": 100, "2": 80, "3": 60, "4": 50, "5": 40, "6": 30, "7": 20, "8": 10,
        "9": 5,   # job-e has disruption but low — may not be selected
        "10": 0,  # 0s run from job-e
    })
    result = select_representative_runs(rows, dd, "kube-api", n=5)
    selected_jobs = set(rows[i]["job"] for i in result)
    selected_secs = []
    for i in result:
        pid = str(rows[i]["prow_id"])
        selected_secs.append(max_disruption_for_backend(dd.get(pid, []), "kube-api"))
    # job-e has the lowest disruption (5s) and should not be selected with n=5 and
    # 8 higher-disruption candidates across 4 other jobs — so its 0s run must not
    # appear as a clean comparison.
    assert "job-e" not in selected_jobs
    assert 0 not in selected_secs


def test_select_no_clean_from_unrelated_job():
    # If 0s runs are all from jobs with no disrupted runs, the clean-comparison slot
    # is skipped, freeing that slot for another disrupted run.
    # 8 disrupted runs across 4 jobs, 2 clean runs from unique unrelated jobs.
    rows = [
        {"prow_id": "1", "job": "job-a", "timestamp": "1970-01-01T00:16:40Z"},
        {"prow_id": "2", "job": "job-a", "timestamp": "1970-01-01T00:33:20Z"},
        {"prow_id": "3", "job": "job-b", "timestamp": "1970-01-01T00:50:00Z"},
        {"prow_id": "4", "job": "job-b", "timestamp": "1970-01-01T01:06:40Z"},
        {"prow_id": "5", "job": "job-c", "timestamp": "1970-01-01T01:23:20Z"},
        {"prow_id": "6", "job": "job-c", "timestamp": "1970-01-01T01:40:00Z"},
        {"prow_id": "7", "job": "job-d", "timestamp": "1970-01-01T01:56:40Z"},
        {"prow_id": "8", "job": "job-d", "timestamp": "1970-01-01T02:13:20Z"},
        {"prow_id": "9", "job": "job-e", "timestamp": "1970-01-01T02:30:00Z"},   # unrelated job, 0s
        {"prow_id": "10", "job": "job-f", "timestamp": "1970-01-01T02:46:40Z"}, # unrelated job, 0s
    ]
    dd = _make_disruption_data({
        "1": 100, "2": 90, "3": 70, "4": 60, "5": 40, "6": 30, "7": 20, "8": 10,
        "9": 0, "10": 0,
    })
    result = select_representative_runs(rows, dd, "kube-api", n=5)
    selected_jobs = [rows[i]["job"] for i in result]
    # Clean runs from job-e/job-f should not get the reserved clean-comparison slot
    # since they don't share a job with any disrupted run. All 5 slots go to disrupted runs.
    selected_secs = []
    for i in result:
        pid = str(rows[i]["prow_id"])
        selected_secs.append(max_disruption_for_backend(dd.get(pid, []), "kube-api"))
    assert all(s > 0 for s in selected_secs)


def test_parse_timestamp_parses_z():
    assert _parse_timestamp("2026-08-14T00:01:05Z") == datetime.datetime(
        2026, 8, 14, 0, 1, 5, tzinfo=datetime.timezone.utc
    )


def test_parse_timestamp_handles_missing_and_bad():
    # None, empty string, and unparseable strings all fall back to the epoch sentinel (no raise).
    epoch = datetime.datetime(1970, 1, 1, tzinfo=datetime.timezone.utc)
    assert _parse_timestamp(None) == epoch
    assert _parse_timestamp("") == epoch
    assert _parse_timestamp("not-a-timestamp") == epoch


def test_parse_timestamp_normalizes_offset_to_utc():
    # A non-UTC offset is converted to the equivalent UTC time.
    utc = datetime.datetime(2026, 8, 14, 0, 1, 5, tzinfo=datetime.timezone.utc)
    assert _parse_timestamp("2026-08-14T02:01:05+02:00") == _parse_timestamp("2026-08-14T00:01:05Z")
    assert _parse_timestamp("2026-08-14T02:01:05+02:00") == utc


def test_parse_timestamp_accepts_int_epoch_ms():
    # Integer epoch-milliseconds convert to the matching UTC datetime.
    assert _parse_timestamp(1704067200000) == datetime.datetime(
        2024, 1, 1, 0, 0, 0, tzinfo=datetime.timezone.utc
    )
    # Epoch-ms 0 maps to the 1970 epoch.
    assert _parse_timestamp(0) == datetime.datetime(1970, 1, 1, tzinfo=datetime.timezone.utc)


def test_parse_timestamp_accepts_float_epoch_ms():
    # Float epoch-milliseconds keep sub-second precision (500 ms -> 500000 us).
    assert _parse_timestamp(1704067200500.0) == datetime.datetime(
        2024, 1, 1, 0, 0, 0, 500000, tzinfo=datetime.timezone.utc
    )


def test_parse_timestamp_rejects_bool():
    # bool is a subclass of int, but True/False are not epoch-ms values, so they
    # fall through to the epoch sentinel instead of converting as 1/0.
    epoch = datetime.datetime(1970, 1, 1, tzinfo=datetime.timezone.utc)
    assert _parse_timestamp(True) == epoch
    assert _parse_timestamp(False) == epoch


def test_parse_timestamp_non_finite_or_overflow_returns_epoch():
    # Infinity, NaN, and out-of-range magnitudes fall back to the epoch sentinel
    # rather than raising out of datetime.fromtimestamp.
    epoch = datetime.datetime(1970, 1, 1, tzinfo=datetime.timezone.utc)
    assert _parse_timestamp(float("inf")) == epoch
    assert _parse_timestamp(float("-inf")) == epoch
    assert _parse_timestamp(float("nan")) == epoch
    assert _parse_timestamp(10**1000) == epoch


def test_parse_timestamp_naive_string_is_utc():
    # A string with no Z suffix or offset is interpreted as UTC.
    utc = datetime.datetime(2026, 8, 14, 0, 1, 5, tzinfo=datetime.timezone.utc)
    assert _parse_timestamp("2026-08-14T00:01:05") == utc
    assert _parse_timestamp("2026-08-14T00:01:05") == _parse_timestamp("2026-08-14T00:01:05Z")


def test_format_timestamp_accepts_rfc3339_string():
    assert format_timestamp("2026-08-14T00:01:05Z") == "2026-08-14 00:01"


def test_format_timestamp_empty_returns_empty():
    # A missing timestamp (None or "") yields an empty string, not a 1970 epoch date.
    assert format_timestamp("") == ""
    assert format_timestamp(None) == ""


def test_format_timestamp_zero_is_epoch():
    # 0 is a valid epoch-ms timestamp, not an absent value, so it formats normally.
    assert format_timestamp(0) == "1970-01-01 00:00"


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


@patch("find_disruption_runs.fetch_disruption_data", return_value={})
@patch("find_disruption_runs.fetch_runs")
def test_multi_value_sort_with_rfc3339_timestamps(mock_fetch_runs, _mock_disruption):
    """Multi-value queries dedup and sort merged rows by RFC 3339 timestamp
    descending, then format timestamps without crashing (real API-shaped data)."""
    import io
    from contextlib import redirect_stdout

    azure_rows = [
        {"prow_id": "A_NEW", "timestamp": "2026-08-15T10:00:00Z", "job": "azure-job"},
        {"prow_id": "SHARED", "timestamp": "2026-08-14T00:00:00Z", "job": "shared-job"},
    ]
    gcp_rows = [
        {"prow_id": "G_MID", "timestamp": "2026-08-15T00:00:00Z", "job": "gcp-job"},
        {"prow_id": "SHARED", "timestamp": "2026-08-14T00:00:00Z", "job": "shared-job"},
        {"prow_id": "G_OLD", "timestamp": "2026-08-13T00:00:00Z", "job": "gcp-job"},
    ]
    mock_fetch_runs.side_effect = [azure_rows, gcp_rows]

    buf = io.StringIO()
    with redirect_stdout(buf):
        main([
            "--grafana-url",
            (
                "https://grafana-loki.ci.openshift.org/d/abc/dash"
                "?var-platform=azure&var-platform=gcp"
                "&var-backend=kube-api-new-connections&var-releases=5.0"
            ),
            "--format", "json", "--limit", "10",
        ])
    output = json.loads(buf.getvalue())

    ids = [r["build_id"] for r in output]
    # Dedup SHARED, then sort newest-first by RFC 3339 timestamp.
    assert ids == ["A_NEW", "G_MID", "SHARED", "G_OLD"]
    assert len(ids) == len(set(ids))
    # The raw RFC 3339 value is preserved and timestamp_human is derived from it.
    assert output[0]["timestamp"] == "2026-08-15T10:00:00Z"
    assert output[0]["timestamp_human"] == "2026-08-15 10:00"


@patch("find_disruption_runs.fetch_disruption_data", return_value={})
@patch("find_disruption_runs.fetch_runs")
def test_sort_key_orders_mixed_timestamp_types_by_time(mock_fetch_runs, _mock_disruption):
    """The merged-row sort key parses each timestamp to a datetime, so rows with
    mixed representations (RFC 3339 strings and numeric epoch-ms) order by actual
    time — a raw-string key could not even compare a str against an int."""
    import io
    from contextlib import redirect_stdout

    mid_epoch_ms = int(
        datetime.datetime(2026, 8, 14, 12, 0, 0, tzinfo=datetime.timezone.utc).timestamp() * 1000
    )
    azure_rows = [
        {"prow_id": "NEW", "timestamp": "2026-08-15T10:00:00Z", "job": "azure-job"},
    ]
    gcp_rows = [
        {"prow_id": "MID_EPOCH", "timestamp": mid_epoch_ms, "job": "gcp-job"},
        {"prow_id": "OLD", "timestamp": "2026-08-13T00:00:00Z", "job": "gcp-job"},
    ]
    mock_fetch_runs.side_effect = [azure_rows, gcp_rows]

    buf = io.StringIO()
    with redirect_stdout(buf):
        main([
            "--grafana-url",
            (
                "https://grafana-loki.ci.openshift.org/d/abc/dash"
                "?var-platform=azure&var-platform=gcp"
                "&var-backend=kube-api-new-connections&var-releases=5.0"
            ),
            "--format", "json", "--limit", "10",
        ])
    output = json.loads(buf.getvalue())

    # Newest-first by actual time: RFC 3339 string, then epoch-ms, then older string.
    ids = [r["build_id"] for r in output]
    assert ids == ["NEW", "MID_EPOCH", "OLD"]
