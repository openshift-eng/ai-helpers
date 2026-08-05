"""Tests for find_disruption_runs.py — URL parsing, backend parsing, disruption extraction."""
import json
from io import BytesIO
from unittest.mock import patch

from find_disruption_runs import (
    extract_disruption_failures,
    fetch_disruption_data,
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
        {"backend_name": "cache-kube-api-new-connections", "disruption_seconds": 75},
        {"backend_name": "oauth-api-new-connections", "disruption_seconds": 5},
    ]
    assert max_disruption_for_backend(entries, "kube-api") == 75


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
        {"prow_id": "1", "job": "job-a", "timestamp": 1000000},
        {"prow_id": "2", "job": "job-b", "timestamp": 2000000},
    ]
    dd = _make_disruption_data({"1": 10, "2": 20})
    result = select_representative_runs(rows, dd, "kube-api", n=5)
    assert sorted(result) == [0, 1]


def test_select_n1_picks_highest():
    rows = [
        {"prow_id": "1", "job": "job-a", "timestamp": 1000000},
        {"prow_id": "2", "job": "job-b", "timestamp": 2000000},
        {"prow_id": "3", "job": "job-c", "timestamp": 3000000},
    ]
    dd = _make_disruption_data({"1": 10, "2": 50, "3": 30})
    result = select_representative_runs(rows, dd, "kube-api", n=1)
    assert result == [1]


def test_select_deduplicates_same_job_within_60s():
    rows = [
        {"prow_id": "1", "job": "job-a", "timestamp": 1000000},
        {"prow_id": "2", "job": "job-a", "timestamp": 1050000},
        {"prow_id": "3", "job": "job-b", "timestamp": 2000000},
    ]
    dd = _make_disruption_data({"1": 10, "2": 30, "3": 20})
    result = select_representative_runs(rows, dd, "kube-api", n=5)
    assert 0 not in result
    assert 1 in result
    assert 2 in result


def test_select_deduplicates_cross_job_within_5s():
    rows = [
        {"prow_id": "1", "job": "job-a", "timestamp": 1000000},
        {"prow_id": "2", "job": "job-b", "timestamp": 1003000},
        {"prow_id": "3", "job": "job-c", "timestamp": 2000000},
    ]
    dd = _make_disruption_data({"1": 10, "2": 50, "3": 20})
    result = select_representative_runs(rows, dd, "kube-api", n=5)
    assert 0 not in result
    assert 1 in result
    assert 2 in result


def test_select_cross_job_dedup_anchor_based():
    rows = [
        {"prow_id": "1", "job": "job-a", "timestamp": 1000000},
        {"prow_id": "2", "job": "job-b", "timestamp": 1004000},
        {"prow_id": "3", "job": "job-c", "timestamp": 1009000},
    ]
    dd = _make_disruption_data({"1": 10, "2": 50, "3": 30})
    result = select_representative_runs(rows, dd, "kube-api", n=5)
    # Anchor=row0. Row1 is 4s from anchor -> merge. Row2 is 9s from anchor -> new cluster.
    assert 0 not in result
    assert 1 in result
    assert 2 in result


def test_select_prefers_job_diversity():
    rows = [
        {"prow_id": "1", "job": "job-a", "timestamp": 1000000},
        {"prow_id": "2", "job": "job-a", "timestamp": 2000000},
        {"prow_id": "3", "job": "job-a", "timestamp": 3000000},
        {"prow_id": "4", "job": "job-a", "timestamp": 4000000},
        {"prow_id": "5", "job": "job-b", "timestamp": 5000000},
        {"prow_id": "6", "job": "job-c", "timestamp": 6000000},
    ]
    dd = _make_disruption_data({str(i+1): (i+1)*10 for i in range(6)})
    result = select_representative_runs(rows, dd, "kube-api", n=3)
    jobs_selected = [rows[i]["job"] for i in result]
    assert "job-b" in jobs_selected
    assert "job-c" in jobs_selected


def test_select_includes_disruption_diversity():
    rows = [
        {"prow_id": str(i+1), "job": "job-%s" % chr(97+i), "timestamp": (i+1)*1000000}
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
        {"prow_id": "1", "job": "job-a", "timestamp": 1000000},
        {"prow_id": "2", "job": "job-b", "timestamp": 2000000},
        {"prow_id": "3", "job": "job-c", "timestamp": 3000000},
    ]
    dd = _make_disruption_data({"1": 50})
    # prow_id 2 and 3 have no BQ data (None disruption) — should not be selected
    result = select_representative_runs(rows, dd, "kube-api", n=5)
    assert result == [0]
    assert 1 not in result
    assert 2 not in result


def test_select_returns_empty_when_all_none():
    rows = [
        {"prow_id": str(i+1), "job": "job-%s" % chr(97 + i % 3), "timestamp": (i+1)*1000000}
        for i in range(6)
    ]
    result = select_representative_runs(rows, {}, "kube-api", n=3)
    assert result == []


def test_select_is_deterministic():
    rows = [
        {"prow_id": str(i+1), "job": "job-%s" % chr(97 + i % 4), "timestamp": (i+1)*1000000}
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
        {"prow_id": "1", "job": "job-a", "timestamp": 1000000},
        {"prow_id": "2", "job": "job-b", "timestamp": 2000000},
        {"prow_id": "3", "job": "job-c", "timestamp": 3000000},
        {"prow_id": "4", "job": "job-a", "timestamp": 4000000},
        {"prow_id": "5", "job": "job-b", "timestamp": 5000000},
        {"prow_id": "6", "job": "job-c", "timestamp": 6000000},
        {"prow_id": "7", "job": "job-d", "timestamp": 7000000},
        {"prow_id": "8", "job": "job-a", "timestamp": 8000000},  # same job as disrupted row 1
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
    # A 0s run shares a job with disrupted candidates, but that job wasn't selected.
    # The clean-comparison slot should not pick it — only jobs in the selected set matter.
    rows = [
        {"prow_id": "1", "job": "job-a", "timestamp": 1000000},
        {"prow_id": "2", "job": "job-b", "timestamp": 2000000},
        {"prow_id": "3", "job": "job-c", "timestamp": 3000000},
        {"prow_id": "4", "job": "job-d", "timestamp": 4000000},
        {"prow_id": "5", "job": "job-a", "timestamp": 5000000},
        {"prow_id": "6", "job": "job-b", "timestamp": 6000000},
        {"prow_id": "7", "job": "job-c", "timestamp": 7000000},
        {"prow_id": "8", "job": "job-d", "timestamp": 8000000},
        {"prow_id": "9", "job": "job-e", "timestamp": 9000000},   # disrupted, unique job
        {"prow_id": "10", "job": "job-e", "timestamp": 10000000}, # 0s, same job as row 9
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
    # If job-e wasn't selected, its 0s run should not be the clean comparison
    if "job-e" not in selected_jobs:
        assert 0 not in selected_secs


def test_select_no_clean_from_unrelated_job():
    # If 0s runs are all from jobs with no disrupted runs, the clean-comparison slot
    # is skipped, freeing that slot for another disrupted run.
    # 8 disrupted runs across 4 jobs, 2 clean runs from unique unrelated jobs.
    rows = [
        {"prow_id": "1", "job": "job-a", "timestamp": 1000000},
        {"prow_id": "2", "job": "job-a", "timestamp": 2000000},
        {"prow_id": "3", "job": "job-b", "timestamp": 3000000},
        {"prow_id": "4", "job": "job-b", "timestamp": 4000000},
        {"prow_id": "5", "job": "job-c", "timestamp": 5000000},
        {"prow_id": "6", "job": "job-c", "timestamp": 6000000},
        {"prow_id": "7", "job": "job-d", "timestamp": 7000000},
        {"prow_id": "8", "job": "job-d", "timestamp": 8000000},
        {"prow_id": "9", "job": "job-e", "timestamp": 9000000},   # unrelated job, 0s
        {"prow_id": "10", "job": "job-f", "timestamp": 10000000}, # unrelated job, 0s
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
