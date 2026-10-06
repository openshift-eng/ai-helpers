"""Tests for find_disruption_runs.py — URL parsing, backend parsing, disruption extraction."""
import datetime
import json
from io import BytesIO
from unittest.mock import patch

from find_disruption_runs import (
    _parse_timestamp,
    apply_master_nodes_filter,
    build_sippy_filter,
    extract_disruption_failures,
    fetch_disruption_data,
    fetch_runs_in_window,
    format_timestamp,
    grafana_params_from_inputs,
    main,
    max_disruption_for_backend,
    parse_backend,
    parse_grafana_url,
    print_table,
    resolve_window_start,
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


def _flat_disruption(prow_ids):
    """Equal exact-backend seconds so display order follows timestamp."""
    return {
        str(pid): [{"backend_name": "kube-api-new-connections", "disruption_seconds": 10}]
        for pid in prow_ids
    }


@patch("find_disruption_runs.fetch_disruption_data", side_effect=_flat_disruption)
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


@patch("find_disruption_runs.fetch_runs")
@patch("find_disruption_runs.fetch_disruption_data")
def test_multi_value_backends_score_exact_names(mock_disruption, mock_fetch_runs):
    """Every var-backend is scored. Derived and cache names do not win the max."""
    import io
    from contextlib import redirect_stdout

    mock_fetch_runs.return_value = [{
        "prow_id": "1",
        "job": "periodic-ci-openshift-release-main-nightly-5.0-e2e-aws-ovn-serial-ipsec",
        "timestamp": "2026-10-01T23:49:29Z",
        "overall_result": "S",
        "url": "https://prow.example/1",
    }]
    mock_disruption.return_value = {
        "1": [
            {"backend_name": "pod-to-host-new-connections", "disruption_seconds": 476},
            {"backend_name": "kube-api-new-connections", "disruption_seconds": 1},
            {"backend_name": "kube-api-http2-localhost-new-connections", "disruption_seconds": 88},
            {"backend_name": "cache-kube-api-new-connections", "disruption_seconds": 90},
        ],
    }

    buf = io.StringIO()
    with redirect_stdout(buf):
        main([
            "--grafana-url",
            "https://grafana-loki.ci.openshift.org/d/abc/dash"
            "?var-backend=pod-to-host-new-connections&var-backend=kube-api-new-connections"
            "&var-releases=5.0",
            "--format", "json",
        ])
    output = json.loads(buf.getvalue())
    assert len(output) == 1
    assert output[0]["disruption_seconds"] == 476
    assert output[0]["disruption_backend"] == "pod-to-host-new-connections"
    names = [entry["backend_name"] for entry in output[0]["disruption_backends"]]
    assert names == ["pod-to-host-new-connections", "kube-api-new-connections"]
    assert "kube-api-http2-localhost-new-connections" not in names
    assert "cache-kube-api-new-connections" not in names


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


def test_max_disruption_ignores_derived_and_cache_backends():
    entries = [
        {"backend_name": "kube-api-new-connections", "disruption_seconds": 17},
        {"backend_name": "kube-api-reused-connections", "disruption_seconds": 13},
        {"backend_name": "kube-api-http2-localhost-new-connections", "disruption_seconds": 56},
        {"backend_name": "kube-api-http1-service-network-new-connections", "disruption_seconds": 39},
        {"backend_name": "kube-api-http2-internal-lb-new-connections", "disruption_seconds": 20},
        {"backend_name": "cache-kube-api-new-connections", "disruption_seconds": 75},
    ]
    # Exact dashboard name: not reused, not localhost/http/lb, not cache.
    assert max_disruption_for_backend(entries, "kube-api-new-connections") == 17
    # Bare base: only the two connection variants.
    assert max_disruption_for_backend(entries, "kube-api") == 17
    assert max_disruption_for_backend(entries, ["pod-to-host-new-connections", "kube-api-new-connections"]) == 17


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
        result = fetch_disruption_data(["123", "456"])

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


def test_select_clean_comparison_when_disrupted_set_fits():
    # Fewer disrupted runs than n leaves a free slot for a same-job 0s run.
    rows = [
        {"prow_id": "1", "job": "job-a", "timestamp": "1970-01-01T00:16:40Z"},
        {"prow_id": "2", "job": "job-b", "timestamp": "1970-01-01T00:33:20Z"},
        {"prow_id": "3", "job": "job-a", "timestamp": "1970-01-01T00:50:00Z"},
    ]
    dd = _make_disruption_data({"1": 40, "2": 20, "3": 0})
    assert select_representative_runs(rows, dd, "kube-api", n=5) == [0, 1, 2]


def test_select_clean_comparison_replaces_when_early_selection_is_full():
    # Exactly n disrupted runs: keep the limit by replacing one with the clean run.
    rows = [
        {"prow_id": "1", "job": "job-a", "timestamp": "1970-01-01T00:16:40Z"},
        {"prow_id": "2", "job": "job-b", "timestamp": "1970-01-01T00:33:20Z"},
        {"prow_id": "3", "job": "job-c", "timestamp": "1970-01-01T00:50:00Z"},
        {"prow_id": "4", "job": "job-a", "timestamp": "1970-01-01T01:06:40Z"},
    ]
    dd = _make_disruption_data({"1": 40, "2": 20, "3": 10, "4": 0})
    assert select_representative_runs(rows, dd, "kube-api", n=3) == [0, 1, 3]


def test_select_skips_clean_comparison_below_three_slots():
    rows = [
        {"prow_id": "1", "job": "job-a", "timestamp": "1970-01-01T00:16:40Z"},
        {"prow_id": "2", "job": "job-a", "timestamp": "1970-01-01T00:33:20Z"},
    ]
    dd = _make_disruption_data({"1": 40, "2": 0})
    assert select_representative_runs(rows, dd, "kube-api", n=2) == [0]


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


@patch("find_disruption_runs.fetch_disruption_data", side_effect=_flat_disruption)
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


@patch("find_disruption_runs.fetch_disruption_data", side_effect=_flat_disruption)
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


def test_table_names_the_dashboard_percentile():
    """The summary must follow var-percentile, not a hardcoded P95."""
    import io
    from contextlib import redirect_stdout

    rows = [{
        "prow_id": "1",
        "job": "job-a",
        "timestamp": "2026-10-01T00:00:00Z",
        "overall_result": "S",
        "failed_test_names": [],
    }]
    disruption = {"1": [{"backend_name": "pod-to-host-reused-connections", "disruption_seconds": 12}]}
    buf = io.StringIO()
    with redirect_stdout(buf):
        print_table(
            rows,
            {"_dashboard_name": "dash", "releases": "5.0", "percentile": "P75",
             "backend": "pod-to-host-reused-connections"},
            ["pod-to-host-reused-connections"],
            disruption,
            selected_indices=[0],
            scanned_count=164,
        )
    text = buf.getvalue()
    assert "per-run seconds, not P75" in text
    assert "not P95" not in text
    assert "| 1 | * | job-a | 1 | S | 12 | pod-to-host-reused-connections |" in text
    assert "Scanned 164 runs." in text


def test_resolve_window_start_lookback_is_calendar_days():
    now = datetime.datetime(2026, 10, 5, 15, 0, tzinfo=datetime.timezone.utc)
    assert resolve_window_start(None, 7, now=now) == datetime.datetime(
        2026, 9, 28, tzinfo=datetime.timezone.utc)
    # Explicit --since-hours wins over var-lookback.
    assert resolve_window_start(48, 7, now=now) == datetime.datetime(
        2026, 10, 3, 15, 0, tzinfo=datetime.timezone.utc)
    # No lookback and no --since-hours: 30 days rolling.
    assert resolve_window_start(None, None, now=now) == now - datetime.timedelta(hours=720)


def _freeze_now():
    real = datetime.datetime

    class Frozen(real):
        @classmethod
        def now(cls, tz=None):
            return real(2026, 10, 5, 15, 0, tzinfo=datetime.timezone.utc)

    return Frozen


@patch("find_disruption_runs.fetch_disruption_data", return_value={})
@patch("find_disruption_runs.fetch_runs", return_value=[])
def test_lookback_sets_filter_and_since_hours_overrides(mock_fetch_runs, _mock_disruption):
    url = (
        "https://grafana-loki.ci.openshift.org/d/abc/dash"
        "?var-backend=kube-api-new-connections&var-releases=5.0&var-lookback=7"
    )
    with patch("find_disruption_runs.datetime", _freeze_now()):
        try:
            main(["--grafana-url", url])
        except SystemExit as e:
            assert e.code == 0
    since = _timestamp_lower_bound(mock_fetch_runs.call_args_list[0][0][1])
    assert since == "2026-09-28T00:00:00Z"

    mock_fetch_runs.reset_mock()
    with patch("find_disruption_runs.datetime", _freeze_now()):
        try:
            main(["--grafana-url", url, "--since-hours", "48"])
        except SystemExit as e:
            assert e.code == 0
    since = _timestamp_lower_bound(mock_fetch_runs.call_args_list[0][0][1])
    assert since == "2026-10-03T15:00:00Z"


@patch("find_disruption_runs.fetch_disruption_data", return_value={})
@patch("find_disruption_runs.fetch_runs", return_value=[])
def test_featureset_all_is_not_a_sippy_filter(mock_fetch_runs, _mock_disruption):
    try:
        main([
            "--grafana-url",
            "https://grafana-loki.ci.openshift.org/d/abc/dash"
            "?var-platform=aws&var-featureset=All&var-backend=kube-api-new-connections"
            "&var-releases=5.0",
        ])
    except SystemExit as e:
        assert e.code == 0
    values = [item["value"] for item in mock_fetch_runs.call_args_list[0][0][1]["items"]]
    assert "Platform:aws" in values
    assert "FeatureSet:All" not in values
    assert not any(value.startswith("FeatureSet:") for value in values)


def _timestamp_lower_bound(filter_dict):
    for item in filter_dict["items"]:
        if item["columnField"] == "timestamp" and item["operatorValue"] == ">":
            return item["value"]
    raise AssertionError("no timestamp lower bound in %s" % filter_dict)


@patch("find_disruption_runs.fetch_runs")
def test_fetch_runs_in_window_pages_until_short_page_and_dedups(mock_fetch_runs):
    since = datetime.datetime(2026, 9, 28, tzinfo=datetime.timezone.utc)
    mock_fetch_runs.side_effect = [
        [
            {"prow_id": "NEW", "timestamp": "2026-10-05T00:00:00Z"},
            {"prow_id": "MID", "timestamp": "2026-10-01T00:00:00Z"},
        ],
        [
            {"prow_id": "MID", "timestamp": "2026-10-01T00:00:00Z"},
            {"prow_id": "OLDER", "timestamp": "2026-09-29T12:00:00Z"},
        ],
        [
            {"prow_id": "EDGE", "timestamp": "2026-09-28T03:00:00Z"},
        ],
    ]
    rows, truncated = fetch_runs_in_window(
        "5.0", {"Platform": "aws"}, since, page_size=2, max_runs=5000)
    assert truncated is False
    assert [row["prow_id"] for row in rows] == ["NEW", "MID", "OLDER", "EDGE"]
    assert mock_fetch_runs.call_count == 3
    second = mock_fetch_runs.call_args_list[1][0][1]
    third = mock_fetch_runs.call_args_list[2][0][1]
    assert {
        "columnField": "timestamp", "operatorValue": "<", "value": "2026-10-01T00:00:00Z",
    } in second["items"]
    assert {
        "columnField": "timestamp", "operatorValue": "<", "value": "2026-09-29T12:00:00Z",
    } in third["items"]


@patch("find_disruption_runs.fetch_runs")
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


SAMPLE_ALERT = """\
Alert:  - warning
Description: P95 disruption has regressed over the past several days when compared to the 30 days prior to previous GA release for: openshift-api-http2-service-network-reused-connections azure micro ovn
Details:
   • alertname: DisruptionRegressionP95
   • architecture: amd64
   • backend: openshift-api-http2-service-network-reused-connections
   • category: disruption
   • compare_release: 4.22
   • delta: P95
   • feature_set: default
   • master_nodes_updated: Y
   • namespace: trt-monitoring
   • network: ovn
   • platform: azure
   • prometheus: trt-monitoring/trt
   • release: 5.0
   • releaseStatus: Development
   • severity: warning
   • topology: ha
   • upgrade_type: micro
"""

ALERT_LINK = (
    "https://grafana-loki.ci.openshift.org/d/gEdw_aLvk/disruption-for-5-0-os-agnostic"
    "?orgId=1&var-percentile=P95&var-platform=azure"
    "&var-backend=openshift-api-http2-service-network-reused-connections"
    "&var-upgrade_type=micro&var-master_nodes_updated=Y"
    "&var-architectures=amd64&var-topologies=ha&var-networks=ovn"
    "&var-releases=5.0&var-lookback=7"
)


def test_parse_grafana_url_feature_set_alias():
    url = (
        "https://grafana-loki.ci.openshift.org/d/abc/dash"
        "?var-feature_set=default&var-backend=kube-api-new-connections&var-releases=5.0"
    )
    result = parse_grafana_url(url)
    assert result["featureset"] == "default"
    assert "feature_set" not in result


def test_alert_without_link_uses_series_labels_and_three_day_lookback():
    params = grafana_params_from_inputs(alert_text=SAMPLE_ALERT + "   • os: rhcos10\n")
    assert params["_dashboard_name"] == "(alert)"
    assert params["lookback"] == "3"
    assert params["releases"] == "5.0"
    assert params["backend"] == "openshift-api-http2-service-network-reused-connections"
    assert params["platform"] == "azure"
    assert params["architectures"] == "amd64"
    assert params["topologies"] == "ha"
    assert params["networks"] == "ovn"
    assert params["upgrade_type"] == "micro"
    assert params["featureset"] == "default"
    assert params["os"] == "rhcos10"
    assert params["master_nodes_updated"] == "Y"
    assert params["percentile"] == "P95"
    assert params["compare_release"] == "4.22"
    assert "releaseStatus" not in params


def test_alert_link_wins_and_omitted_labels_are_overlaid():
    text = SAMPLE_ALERT + "link: " + ALERT_LINK + "\n   • os: rhcos10\n"
    params = grafana_params_from_inputs(alert_text=text)
    assert params["_dashboard_name"] == "disruption-for-5-0-os-agnostic"
    assert params["lookback"] == "7"
    assert params["percentile"] == "P95"
    assert params["featureset"] == "default"
    assert params["os"] == "rhcos10"
    assert params["compare_release"] == "4.22"
    assert params["master_nodes_updated"] == "Y"


def test_explicit_url_is_not_replaced_by_alert_link():
    params = grafana_params_from_inputs(
        grafana_url="https://grafana-loki.ci.openshift.org/d/abc/other?var-releases=5.0&var-backend=kube-api-new-connections&var-lookback=1",
        alert_text=SAMPLE_ALERT + "link: " + ALERT_LINK + "\n",
    )
    assert params["_dashboard_name"] == "other"
    assert params["lookback"] == "1"
    assert params["backend"] == "kube-api-new-connections"
    assert params["featureset"] == "default"
    assert params["platform"] == "azure"


def _variant_values(filter_dict):
    return [item["value"] for item in filter_dict["items"] if item["columnField"] == "variants"]


@patch("find_disruption_runs.fetch_disruption_data", return_value={})
@patch("find_disruption_runs.fetch_runs", return_value=[])
def test_alert_text_filters_sippy_and_lookback(mock_fetch_runs, _mock_disruption):
    with patch("find_disruption_runs.datetime", _freeze_now()):
        try:
            main(["--alert-text", SAMPLE_ALERT + "   • os: rhcos10\n"])
        except SystemExit as e:
            assert e.code == 0
    values = _variant_values(mock_fetch_runs.call_args_list[0][0][1])
    assert "Platform:azure" in values
    assert "Architecture:amd64" in values
    assert "Topology:ha" in values
    assert "Network:ovn" in values
    assert "Upgrade:micro" in values
    assert "FeatureSet:default" in values
    assert "OS:rhcos10" in values
    assert not any(value.startswith("CompareRelease:") for value in values)
    assert _timestamp_lower_bound(mock_fetch_runs.call_args_list[0][0][1]) == "2026-10-02T00:00:00Z"


@patch("find_disruption_runs.fetch_disruption_data", return_value={})
@patch("find_disruption_runs.fetch_runs", return_value=[])
def test_feature_set_alias_is_a_sippy_filter(mock_fetch_runs, _mock_disruption):
    try:
        main([
            "--grafana-url",
            "https://grafana-loki.ci.openshift.org/d/abc/dash"
            "?var-feature_set=techpreview&var-backend=kube-api-new-connections&var-releases=5.0",
        ])
    except SystemExit as e:
        assert e.code == 0
    values = _variant_values(mock_fetch_runs.call_args_list[0][0][1])
    assert "FeatureSet:techpreview" in values


def test_fetch_disruption_data_keeps_master_nodes_updated():
    api_response = {
        "rows": [
            {"backend_name": "kube-api-new-connections", "disruption_seconds": 12,
             "job_run_name": "123", "master_nodes_updated": "Y"},
            {"backend_name": "kube-api-new-connections", "disruption_seconds": 4,
             "job_run_name": "456", "master_nodes_updated": None},
        ],
    }
    with patch("find_disruption_runs.urllib.request.urlopen",
               return_value=_mock_urlopen(api_response)):
        result = fetch_disruption_data(["123", "456"])
    assert result["123"][0]["master_nodes_updated"] == "Y"
    assert result["456"][0]["master_nodes_updated"] == ""


def test_apply_master_nodes_filter_drops_other_runs_including_clean():
    rows = [
        {"prow_id": "Y1"},
        {"prow_id": "N1"},
        {"prow_id": "Y0"},
    ]
    data = {
        "Y1": [{"backend_name": "b", "disruption_seconds": 20, "master_nodes_updated": "Y"}],
        "N1": [{"backend_name": "b", "disruption_seconds": 90, "master_nodes_updated": "N"}],
        "Y0": [{"backend_name": "b", "disruption_seconds": 0, "master_nodes_updated": "Y"}],
    }
    kept = apply_master_nodes_filter(rows, data, "Y", True)
    assert [row["prow_id"] for row in kept] == ["Y1", "Y0"]
    assert apply_master_nodes_filter(rows, data, "Y", False) == []


@patch("find_disruption_runs.fetch_runs")
@patch("find_disruption_runs.fetch_disruption_data")
def test_master_nodes_updated_drops_nonmatching_runs(mock_disruption, mock_fetch_runs):
    import io
    from contextlib import redirect_stderr, redirect_stdout

    mock_fetch_runs.return_value = [
        {"prow_id": "Yrun", "job": "azure-upgrade", "timestamp": "2026-10-04T00:00:00Z",
         "overall_result": "S", "url": "https://prow.example/Y"},
        {"prow_id": "Nrun", "job": "azure-upgrade", "timestamp": "2026-10-04T01:00:00Z",
         "overall_result": "S", "url": "https://prow.example/N"},
    ]
    mock_disruption.return_value = {
        "Yrun": [{
            "backend_name": "openshift-api-http2-service-network-reused-connections",
            "disruption_seconds": 11,
            "master_nodes_updated": "Y",
        }],
        "Nrun": [{
            "backend_name": "openshift-api-http2-service-network-reused-connections",
            "disruption_seconds": 80,
            "master_nodes_updated": "N",
        }],
    }
    buf = io.StringIO()
    err = io.StringIO()
    with redirect_stdout(buf), redirect_stderr(err):
        main([
            "--grafana-url",
            "https://grafana-loki.ci.openshift.org/d/abc/dash"
            "?var-backend=openshift-api-http2-service-network-reused-connections"
            "&var-releases=5.0&var-master_nodes_updated=Y&var-featureset=default",
            "--format", "json",
        ])
    output = json.loads(buf.getvalue())
    assert [row["build_id"] for row in output] == ["Yrun"]
    assert "Kept 1 of 2 runs with master_nodes_updated=Y." in err.getvalue()


@patch("find_disruption_runs.fetch_runs")
@patch("find_disruption_runs.fetch_disruption_data")
def test_missing_master_nodes_field_does_not_return_unfiltered(mock_disruption, mock_fetch_runs):
    import io
    from contextlib import redirect_stderr, redirect_stdout

    mock_fetch_runs.return_value = [
        {"prow_id": "1", "job": "job", "timestamp": "2026-10-04T00:00:00Z"},
    ]
    mock_disruption.return_value = {
        "1": [{"backend_name": "kube-api-new-connections", "disruption_seconds": 9}],
    }
    out = io.StringIO()
    err = io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        try:
            main([
                "--grafana-url",
                "https://grafana-loki.ci.openshift.org/d/abc/dash"
                "?var-backend=kube-api-new-connections&var-releases=5.0"
                "&var-master_nodes_updated=Y",
                "--format", "json",
            ])
        except SystemExit as e:
            assert e.code == 0
    assert out.getvalue().strip() == ""
    assert "did not include that field" in err.getvalue()
    assert "No runs matched master_nodes_updated=Y" in err.getvalue()


def test_table_prints_series_context():
    import io
    from contextlib import redirect_stdout

    rows = [{
        "prow_id": "1",
        "job": "job-a",
        "timestamp": "2026-10-01T00:00:00Z",
        "overall_result": "S",
        "failed_test_names": [],
    }]
    disruption = {"1": [{
        "backend_name": "kube-api-new-connections",
        "disruption_seconds": 12,
        "master_nodes_updated": "Y",
    }]}
    buf = io.StringIO()
    with redirect_stdout(buf):
        print_table(
            rows,
            {
                "_dashboard_name": "(alert)",
                "releases": "5.0",
                "percentile": "P95",
                "backend": "kube-api-new-connections",
                "platform": "azure",
                "featureset": "default",
                "os": "rhcos10",
                "master_nodes_updated": "Y",
                "lookback": "3",
                "compare_release": "4.22",
            },
            ["kube-api-new-connections"],
            disruption,
        )
    text = buf.getvalue()
    assert "Platform=azure" in text
    assert "FeatureSet=default" in text
    assert "OS=rhcos10" in text
    assert "MasterNodesUpdated=Y" in text
    assert "Lookback=3d" in text
    assert "CompareRelease=4.22" in text
    assert "Percentile: P95" in text
