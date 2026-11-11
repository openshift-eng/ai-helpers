"""Tests for find_disruption_runs.py — run selection, disruption extraction, output, and the CLI.

URL, alert, and Sippy parsing are tested with the shared library in plugins/ci/lib/disruption_common.
"""
import datetime
import io
import json
import sys
from unittest.mock import patch

import pytest

from find_disruption_runs import (
    backend_summary,
    correlated_runs,
    default_full_table_path,
    dominant_probe_family,
    extract_disruption_failures,
    format_timestamp,
    is_upgrade_series,
    job_summary,
    main,
    max_disruption_for_backend,
    print_json,
    print_table,
    probe_family,
    select_representative_runs,
)


def _flat_disruption(prow_ids, **_kwargs):
    """Equal exact-backend seconds so display order follows timestamp."""
    return {
        str(pid): [{"backend_name": "kube-api-new-connections", "disruption_seconds": 10}]
        for pid in prow_ids
    }


@patch("disruption_common.sippy.fetch_disruption_data", side_effect=_flat_disruption)
@patch("disruption_common.sippy.fetch_runs")
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


@patch("disruption_common.sippy.fetch_runs")
@patch("disruption_common.sippy.fetch_disruption_data")
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


@patch("disruption_common.sippy.fetch_disruption_data", return_value={})
@patch("disruption_common.sippy.fetch_runs", return_value=[])
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


def test_select_follows_where_the_seconds_come_from():
    # One run per job: picks go down by each job's contribution, not across severity tiers.
    rows = [
        {"prow_id": str(i+1), "job": "job-%s" % chr(97+i), "timestamp": "1970-01-01T%02d:00:00Z" % i}
        for i in range(9)
    ]
    dd = _make_disruption_data({
        "1": 100, "2": 90, "3": 80, "4": 50, "5": 40,
        "6": 30, "7": 10, "8": 5, "9": 0,
    })
    assert select_representative_runs(rows, dd, "kube-api", n=5) == [0, 1, 2, 3, 4]


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


def test_select_clean_comparison_keeps_only_same_job_disrupted_run():
    # The only job-a disrupted run is last. Replace another job, not that run.
    rows = [
        {"prow_id": "1", "job": "job-b", "timestamp": "1970-01-01T00:16:40Z"},
        {"prow_id": "2", "job": "job-c", "timestamp": "1970-01-01T00:33:20Z"},
        {"prow_id": "3", "job": "job-a", "timestamp": "1970-01-01T00:50:00Z"},
        {"prow_id": "4", "job": "job-a", "timestamp": "1970-01-01T01:06:40Z"},
    ]
    dd = _make_disruption_data({"1": 40, "2": 20, "3": 10, "4": 0})
    assert select_representative_runs(rows, dd, "kube-api", n=3) == [0, 2, 3]


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


def test_format_timestamp_accepts_rfc3339_string():
    assert format_timestamp("2026-08-14T00:01:05Z") == "2026-08-14 00:01"


def test_format_timestamp_empty_returns_empty():
    # A missing timestamp (None or "") yields an empty string, not a 1970 epoch date.
    assert format_timestamp("") == ""
    assert format_timestamp(None) == ""


def test_format_timestamp_zero_is_epoch():
    # 0 is a valid epoch-ms timestamp, not an absent value, so it formats normally.
    assert format_timestamp(0) == "1970-01-01 00:00"


@patch("disruption_common.sippy.fetch_disruption_data", side_effect=_flat_disruption)
@patch("disruption_common.sippy.fetch_runs")
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


@patch("disruption_common.sippy.fetch_disruption_data", side_effect=_flat_disruption)
@patch("disruption_common.sippy.fetch_runs")
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


def _freeze_now():
    real = datetime.datetime

    class Frozen(real):
        @classmethod
        def now(cls, tz=None):
            return real(2026, 10, 5, 15, 0, tzinfo=datetime.timezone.utc)

    return Frozen


@patch("disruption_common.sippy.fetch_disruption_data", return_value={})
@patch("disruption_common.sippy.fetch_runs", return_value=[])
def test_lookback_sets_filter_and_since_hours_overrides(mock_fetch_runs, _mock_disruption):
    url = (
        "https://grafana-loki.ci.openshift.org/d/abc/dash"
        "?var-backend=kube-api-new-connections&var-releases=5.0&var-lookback=7"
    )
    with patch("disruption_common.series.datetime", _freeze_now()):
        try:
            main(["--grafana-url", url])
        except SystemExit as e:
            assert e.code == 0
    since = _timestamp_lower_bound(mock_fetch_runs.call_args_list[0][0][1])
    assert since == "2026-09-28T00:00:00Z"

    mock_fetch_runs.reset_mock()
    with patch("disruption_common.series.datetime", _freeze_now()):
        try:
            main(["--grafana-url", url, "--since-hours", "48"])
        except SystemExit as e:
            assert e.code == 0
    since = _timestamp_lower_bound(mock_fetch_runs.call_args_list[0][0][1])
    assert since == "2026-10-03T15:00:00Z"


@patch("disruption_common.sippy.fetch_disruption_data", return_value={})
@patch("disruption_common.sippy.fetch_runs", return_value=[])
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


def _variant_values(filter_dict):
    return [item["value"] for item in filter_dict["items"] if item["columnField"] == "variants"]


@patch("disruption_common.sippy.fetch_disruption_data", return_value={})
@patch("disruption_common.sippy.fetch_runs", return_value=[])
def test_alert_text_filters_sippy_and_lookback(mock_fetch_runs, _mock_disruption):
    with patch("disruption_common.series.datetime", _freeze_now()):
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


@patch("disruption_common.sippy.fetch_disruption_data", return_value={})
@patch("disruption_common.sippy.fetch_runs", return_value=[])
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


@patch("disruption_common.sippy.fetch_runs")
@patch("disruption_common.sippy.fetch_disruption_data")
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


@patch("disruption_common.sippy.fetch_runs")
@patch("disruption_common.sippy.fetch_disruption_data")
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


def test_scripts_explain_a_missing_lib(tmp_path):
    import os
    import shutil
    import subprocess

    here = os.path.dirname(os.path.abspath(__file__))
    lonely = tmp_path / "skills" / "analyze-disruption"
    lonely.mkdir(parents=True)
    for script in ("find_disruption_runs.py", "parse_disruption.py"):
        shutil.copy(os.path.join(here, script), lonely)
        result = subprocess.run([sys.executable, str(lonely / script), "--help"], capture_output=True, text=True)
        assert result.returncode != 0
        assert "supporting_dirs: [lib/disruption_common]" in result.stderr

    shutil.copytree(os.path.join(here, "..", "..", "lib", "disruption_common"), tmp_path / "skills" / "disruption_common")
    for script in ("find_disruption_runs.py", "parse_disruption.py"):
        result = subprocess.run([sys.executable, str(lonely / script), "--help"], capture_output=True, text=True)
        assert result.returncode == 0, result.stderr


def test_print_json_matches_target_failures_by_backend_base(capsys):
    rows = [
        {"prow_id": "1", "job": "job-a", "timestamp": "2026-11-01T00:00:00Z",
         "failed_test_names": ["[Monitor:x] disruption/kube-api connection/new should be available"]},
        {"prow_id": "2", "job": "job-a", "timestamp": "2026-11-01T01:00:00Z",
         "failed_test_names": ["[Monitor:x] disruption/kube-api-http2-localhost connection/new should be available"]},
        {"prow_id": "3", "job": "job-b", "timestamp": "2026-11-01T02:00:00Z", "failed_test_names": None},
    ]
    data = {"1": [{"backend_name": "kube-api-new-connections", "disruption_seconds": 6,
                   "release_tag": "tag-1", "job_name": "job-a"}]}
    print_json(rows, ["kube-api-new-connections"], data, selected_indices=[0])
    output = json.loads(capsys.readouterr().out)
    assert [entry["has_target_disruption"] for entry in output] == [True, False, False]
    assert output[0]["disruption_failures"] == ["kube-api"]
    assert output[1]["disruption_failures"] == ["kube-api-http2-localhost"]
    assert (output[0]["disruption_seconds"], output[0]["disruption_backend"]) == (6, "kube-api-new-connections")
    assert output[0]["disruption_backends"] == data["1"]
    assert output[2]["disruption_seconds"] is None
    assert [entry["recommended"] for entry in output] == [True, False, False]



def _run(pid, job, ts, **extra):
    row = {"prow_id": pid, "job": job, "timestamp": ts, "overall_result": "S",
           "url": "https://prow.example/%s" % pid, "failed_test_names": []}
    row.update(extra)
    return row


def test_select_never_drops_the_top_row():
    # One fips run outweighs nothing else in its job, but it is the worst run, so it is kept.
    rows = [_run("fips", "e2e-fips", "2026-11-03T17:10:00Z")]
    secs = {"fips": 226}
    for i in range(12):
        job = "e2e-upgrade" if i % 2 else "e2e-rt-upgrade"
        pid = "u%d" % i
        rows.append(_run(pid, job, "2026-11-%02dT08:00:00Z" % (4 + i)))
        secs[pid] = 60 + i
    result = select_representative_runs(rows, _make_disruption_data(secs), "kube-api", n=3)
    assert 0 in result


def test_select_gives_the_job_with_most_seconds_more_picks():
    rows, secs = [], {}
    for i in range(6):
        rows.append(_run("big%d" % i, "big-job", "2026-11-%02dT00:00:00Z" % (1 + i)))
        secs["big%d" % i] = 90 - i
    rows.append(_run("small", "small-job", "2026-11-09T00:00:00Z"))
    secs["small"] = 95
    rows.append(_run("tiny", "tiny-job", "2026-11-10T00:00:00Z"))
    secs["tiny"] = 2
    result = select_representative_runs(rows, _make_disruption_data(secs), "kube-api", n=4)
    jobs = [rows[i]["job"] for i in result]
    # small-job is the top run; big-job (535s) takes the rest; tiny-job (2s) gets nothing.
    assert jobs.count("big-job") == 3
    assert "small-job" in jobs and "tiny-job" not in jobs


def test_select_second_pick_of_a_job_is_its_most_typical_run():
    rows = [_run(str(i), "job-a", "2026-11-%02dT00:00:00Z" % (1 + i)) for i in range(5)]
    secs = {"0": 100, "1": 52, "2": 50, "3": 48, "4": 10}
    result = select_representative_runs(rows, _make_disruption_data(secs), "kube-api", n=2)
    assert result == [0, 2]


def test_select_counts_a_launch_batch_once():
    # Three job-a runs start within 3 minutes: one batch. The fourth is a new batch.
    rows = [
        _run("a1", "job-a", "2026-11-09T23:36:00Z"),
        _run("a2", "job-a", "2026-11-09T23:37:30Z"),
        _run("a3", "job-a", "2026-11-09T23:39:00Z"),
        _run("a4", "job-a", "2026-11-10T05:36:00Z"),
        _run("b1", "job-b", "2026-11-08T00:00:00Z"),
    ]
    secs = {"a1": 115, "a2": 103, "a3": 99, "a4": 76, "b1": 20}
    result = select_representative_runs(rows, _make_disruption_data(secs), "kube-api", n=5)
    assert result == [0, 3, 4]


def test_select_same_instant_rival_does_not_hide_a_jobs_batch():
    # rt-upgrade's worst batch starts in the same second as a minor job's run. The minor
    # run is not picked, so it must not knock out the rt-upgrade batch.
    rows = [
        _run("top", "ovn-upgrade", "2026-11-09T23:36:00Z"),
        _run("ovn2", "ovn-upgrade", "2026-11-07T17:38:00Z"),
        _run("rt1", "rt-upgrade", "2026-11-10T08:05:00Z"),
        _run("minor", "minor-upgrade", "2026-11-10T08:05:02Z"),
        _run("rt2", "rt-upgrade", "2026-11-06T04:48:00Z"),
    ]
    secs = {"top": 115, "ovn2": 45, "rt1": 99, "minor": 101, "rt2": 62}
    result = select_representative_runs(rows, _make_disruption_data(secs), "kube-api", n=3)
    # rt-upgrade adds the most seconds (161s) after the top run's job, so it takes both slots.
    assert [rows[i]["prow_id"] for i in result] == ["top", "rt1", "rt2"]


def test_select_prefers_upgrade_jobs_in_an_upgrade_series():
    rows = [
        _run("top", "e2e-gcp-ovn-upgrade", "2026-11-01T00:00:00Z"),
        _run("plain", "e2e-gcp-ovn", "2026-11-02T00:00:00Z"),
        _run("rt", "e2e-gcp-ovn-rt-upgrade", "2026-11-03T00:00:00Z"),
    ]
    dd = _make_disruption_data({"top": 100, "plain": 60, "rt": 40})
    assert select_representative_runs(rows, dd, "kube-api", n=2, upgrade_series=True) == [0, 2]
    assert select_representative_runs(rows, dd, "kube-api", n=2, upgrade_series=False) == [0, 1]


# Metal ingress-to-oauth-server series from 2026-11-10 (find-runs-230927.md): 212 runs, P95.
_METAL_PREFIX = "periodic-ci-openshift-release-main-nightly-5.1-e2e-metal-ipi-"
_METAL_DISRUPTED = [
    ("ovn-serial-virtualmedia-2of2", "2118177396950568960", 182, "2026-11-05T03:03:20Z"),
    ("ovn-serial-virtualmedia-1of2", "2118177271108866048", 181, "2026-11-05T03:03:05Z"),
    ("bgp-vip-ovn-bgp-metallb", "2119611341911101440", 31, "2026-11-09T02:00:00Z"),
    ("bgp-vip-ovn-bgp-metallb", "2117799474456694784", 14, "2026-11-04T02:01:00Z"),
    ("bgp-vip-ovn-bgp-metallb", "2118524082776444928", 8, "2026-11-06T02:00:00Z"),
    ("serial-ovn-ipv6", "2120065387394502656", 1, "2026-11-10T08:05:00Z"),
    ("ovn-serial-virtualmedia-2of2", "2119690799170981888", 1, "2026-11-09T07:16:30Z"),
    ("serial-ovn-ipv6", "2119690540793466880", 1, "2026-11-09T07:16:00Z"),
    ("ovn-serial-virtualmedia-2of2", "2119584640590155776", 1, "2026-11-09T00:15:00Z"),
    ("serial-ovn-dualstack", "2119486942994239488", 1, "2026-11-08T17:46:00Z"),
    ("serial-ovn-ipv6", "2119486839810166784", 1, "2026-11-08T17:46:30Z"),
    ("ovn-serial-virtualmedia-2of2", "2119399417168531456", 1, "2026-11-08T11:59:00Z"),
    ("ovn-serial-virtualmedia-2of2", "2119303540282232832", 1, "2026-11-08T05:38:00Z"),
    ("serial-ovn-ipv6", "2119069708463378432", 1, "2026-11-07T14:09:00Z"),
    ("ovn-serial-ipv4", "2118966641550168064", 1, "2026-11-07T07:19:00Z"),
    ("serial-ovn-ipv6-runc", "2118876475875659776", 1, "2026-11-07T01:21:00Z"),
    ("serial-ovn-ipv6", "2118672025131159552", 1, "2026-11-06T11:48:00Z"),
    ("serial-ovn-ipv6", "2118566177235013632", 1, "2026-11-06T04:48:00Z"),
    ("serial-ovn-dualstack", "2118480766777167872", 1, "2026-11-05T23:08:00Z"),
    ("ovn-serial-virtualmedia-2of2", "2118480640109187072", 1, "2026-11-05T23:08:30Z"),
    ("ovn-serial-virtualmedia-2of2", "2118350113309986816", 1, "2026-11-05T14:29:00Z"),
    ("ovn-serial-virtualmedia-2of2", "2118069348168896512", 1, "2026-11-04T19:53:00Z"),
    ("serial-ovn-ipv6", "2118068974909394944", 1, "2026-11-04T19:52:00Z"),
    ("ovn-serial-ipv4", "2117964165975904256", 1, "2026-11-04T12:56:00Z"),
    ("serial-ovn-ipv6", "2117862498282508288", 1, "2026-11-04T06:12:00Z"),
    ("serial-ovn-ipv6-runc", "2117789367614312449", 1, "2026-11-04T01:21:00Z"),
    ("ovn-serial-ipv4", "2117652197033381888", 1, "2026-11-03T16:16:00Z"),
    ("ovn-serial-virtualmedia-2of2", "2117532180757352448", 1, "2026-11-03T08:19:00Z"),
]
_METAL_CLEAN = ("ovn-serial-virtualmedia-2of2", "2120065473658753024", 0, "2026-11-10T08:05:30Z")


def _metal_series():
    runs = _METAL_DISRUPTED + [_METAL_CLEAN]
    # 0s runs fill the series to 212, so P95 lands on the 1s tail as it did on the dashboard.
    for i in range(212 - len(runs)):
        runs.append(("serial-ovn-ipv4" if i % 2 else "ovn-serial-virtualmedia-1of2", "z%d" % i, 0,
                     "2026-11-%02dT%02d:30:00Z" % (3 + i % 7, i % 24)))
    rows = [_run(pid, _METAL_PREFIX + job, ts) for job, pid, _secs, ts in runs]
    return rows, _make_disruption_data({pid: secs for _job, pid, secs, _ts in runs})


def test_select_covers_outliers_and_the_p95_tail_from_the_metal_session():
    rows, dd = _metal_series()
    explain = {}
    result = select_representative_runs(rows, dd, "kube-api", n=5, percentile="P95", explain=explain)
    picked = {rows[i]["prow_id"]: rows[i]["job"][len(_METAL_PREFIX):] for i in result}
    secs = {pid: s for _job, pid, s, _ts in _METAL_DISRUPTED + [_METAL_CLEAN]}

    # The top run, and the 1of2 shard that launched with it counts as the same event.
    assert "2118177396950568960" in picked
    assert "2118177271108866048" not in picked
    assert explain["shared"] == [{"prow_id": "2118177396950568960", "with": ["2118177271108866048"]}]
    # bgp-metallb was disrupted in 3 of 3 runs at 8-31s.
    assert "bgp-vip-ovn-bgp-metallb" in picked.values()
    # At most one extra 2of2 1s blip; the tail picks come from more than one job.
    blips = [job for pid, job in picked.items() if secs[pid] == 1]
    assert blips.count("ovn-serial-virtualmedia-2of2") <= 1
    assert len(set(blips)) == 2
    assert "2120065473658753024" in picked  # clean comparison
    assert (explain["cutoff"], explain["outliers"], explain["tail"]) == (1, 5, 23)


def test_select_reads_the_percentile_for_the_tiers():
    rows, dd = _metal_series()
    explain = {}
    select_representative_runs(rows, dd, "kube-api", n=5, percentile="P50", explain=explain)
    # Most runs are 0s, so P50 is 0 and every disrupted run is an outlier.
    assert (explain["percentile"], explain["cutoff"], explain["outliers"]) == (50, 0, 28)


def test_select_merges_sister_shards_only_within_the_batch_window():
    rows = [
        _run("a", "e2e-serial-1of2", "2026-11-05T03:00:00Z"),
        _run("b", "e2e-serial-2of2", "2026-11-05T03:04:00Z"),
        _run("c", "e2e-serial-2of2", "2026-11-06T03:00:00Z"),
        _run("d", "e2e-other", "2026-11-05T03:01:00Z"),
    ]
    dd = _make_disruption_data({"a": 100, "b": 90, "c": 80, "d": 70})
    result = select_representative_runs(rows, dd, "kube-api", n=3)
    assert [rows[i]["prow_id"] for i in result] == ["a", "c", "d"]


def test_table_explains_tiers_and_shared_events():
    rows, dd = _metal_series()
    explain = {}
    selected = select_representative_runs(rows, dd, "kube-api", n=5, percentile="P95", explain=explain)
    display = [rows[i] for i in range(len(_METAL_DISRUPTED) + 1)]
    out = io.StringIO()
    print_table(display, {"percentile": "P95"}, "kube-api", dd, selected_indices=selected,
                selection=explain, out=out)
    text = out.getvalue()
    assert ("Tiers: P95 of 212 runs is 1s, so outliers are > 2s (5 runs) and the tail is the rest (23 runs)."
            in text)
    assert "Same event, not picked separately: #2 with #1." in text


def test_is_upgrade_series():
    assert is_upgrade_series({"Upgrade": "micro"})
    assert is_upgrade_series({"Upgrade": "micro,minor,none"})
    assert not is_upgrade_series({"Upgrade": "none"})
    assert not is_upgrade_series({})


_LOCALHOST = ["kube-api-http1-localhost-new-connections", "openshift-api-http2-localhost-new-connections",
              "kube-api-new-connections"]


def _entries(**secs):
    return [{"backend_name": name.replace("_", "-"), "disruption_seconds": value} for name, value in secs.items()]


def _localhost_data():
    return {
        "1": _entries(kube_api_http1_localhost_new_connections=50,
                      openshift_api_http2_localhost_new_connections=54, kube_api_new_connections=0),
        "2": _entries(kube_api_http1_localhost_new_connections=90,
                      openshift_api_http2_localhost_new_connections=95, kube_api_new_connections=94),
        "3": _entries(kube_api_http1_localhost_new_connections=1,
                      openshift_api_http2_localhost_new_connections=1, kube_api_new_connections=30),
        "4": _entries(kube_api_new_connections=0),
    }


def _localhost_rows():
    return [_run(str(i), "job-%s" % ("a" if i < 3 else "b"), "2026-11-0%dT00:00:00Z" % i) for i in range(1, 5)]


def test_backend_summary_counts_nonzero_max_and_median():
    summary = {s["name"]: s for s in backend_summary(_localhost_rows(), _localhost_data(), _LOCALHOST)}
    assert summary["openshift-api-http2-localhost-new-connections"] == {
        "name": "openshift-api-http2-localhost-new-connections", "nonzero": 3, "max_in": 2, "median": 54}
    assert summary["kube-api-new-connections"]["max_in"] == 1
    assert summary["kube-api-new-connections"]["median"] == 62
    assert summary["kube-api-http1-localhost-new-connections"]["max_in"] == 0


def test_dominant_probe_family_needs_a_mixed_selection_and_a_majority():
    summary = backend_summary(_localhost_rows(), _localhost_data(), _LOCALHOST)
    assert dominant_probe_family(summary) == ("*-localhost-*", 2, 3)
    only_localhost = [s for s in summary if probe_family(s["name"])]
    assert dominant_probe_family(only_localhost) is None
    assert probe_family("cache-kube-api-new-connections") == "cache-*"
    assert probe_family("kube-api-new-connections") is None


def test_correlated_runs_requires_every_backend_within_tolerance():
    # Run 2 is the only one where all three are within 15% of its max; run 4 is not disrupted.
    assert correlated_runs(_localhost_rows(), _localhost_data(), _LOCALHOST) == (1, 3)
    # Without kube-api-new-connections, run 1 (50 vs 54) and run 3 (1 and 1) also count.
    assert correlated_runs(_localhost_rows(), _localhost_data(), _LOCALHOST[:2]) == (3, 3)


def test_job_summary_sorts_by_total_seconds():
    summary = job_summary(_localhost_rows(), _localhost_data(), _LOCALHOST)
    assert summary == [{"job": "job-a", "runs": 2, "disrupted": 2, "total": 149, "median": 74.5},
                       {"job": "job-b", "runs": 2, "disrupted": 1, "total": 30, "median": 30}]


def _many_rows(count):
    rows = [_run(str(i), "job-%d" % (i % 3), "2026-11-01T%02d:%02d:00Z" % (i // 60, i % 60))
            for i in range(count)]
    data = {str(i): [{"backend_name": "kube-api-new-connections", "disruption_seconds": count - i}]
            for i in range(count)}
    return rows, data


def test_print_table_top_keeps_numbering_and_recommended_rows(capsys):
    rows, data = _many_rows(30)
    print_table(rows, {"_dashboard_name": "dash", "releases": "5.1"}, ["kube-api-new-connections"], data,
                selected_indices=[0, 27], top=5, full_table_path="/tmp/full.md")
    text = capsys.readouterr().out
    assert "| 5 |   | job-1 | 4 |" in text
    assert "\n| 6 |" not in text
    assert "| 28 | * | job-0 | 27 |" in text
    assert "Showing rows 1-5 plus 1 recommended row(s) below them of 30." in text
    assert "Full table (30 rows, all backends and jobs): /tmp/full.md" in text
    assert "Per-job disruption" in text and "| job-0 | 10 | 10 |" in text
    assert "| kube-api-new-connections | 30 | 30 | 15.5 |" in text
    # One selected backend: no correlation line.
    assert "correlated" not in text


def test_print_table_omits_master_nodes_when_y_and_n(capsys):
    rows, data = _many_rows(1)
    print_table(rows, {"_dashboard_name": "dash", "master_nodes_updated": "Y,N"},
                ["kube-api-new-connections"], data)
    assert "MasterNodesUpdated" not in capsys.readouterr().out


_URL = ("https://grafana-loki.ci.openshift.org/d/abc/dash"
        "?var-backend=kube-api-new-connections&var-releases=5.1")


def test_main_table_writes_full_table_and_prints_compact(tmp_path, capsys):
    rows, data = _many_rows(30)
    out_path = str(tmp_path / "sub" / "full.md")
    with patch("disruption_common.sippy.collect_runs", return_value=(rows, False)), \
            patch("disruption_common.sippy.fetch_disruption_data", return_value=data):
        main(["--grafana-url", _URL, "--top", "10", "--full-table-out", out_path])
    text = capsys.readouterr().out
    assert "\n| 10 |" in text and "\n| 11 |" not in text
    assert "Full table (30 rows, all backends and jobs): %s" % out_path in text
    full = open(out_path).read()
    assert "\n| 30 |" in full and "Showing rows" not in full and "Full table" not in full


def test_main_table_default_full_table_path_and_top_zero(tmp_path, capsys, monkeypatch):
    monkeypatch.chdir(tmp_path)
    rows, data = _many_rows(25)
    with patch("disruption_common.sippy.collect_runs", return_value=(rows, False)), \
            patch("disruption_common.sippy.fetch_disruption_data", return_value=data):
        main(["--grafana-url", _URL])
        text = capsys.readouterr().out
        written = list((tmp_path / ".work" / "disruption-analysis").glob("*/find-runs-*.md"))
        assert len(written) == 1
        assert "\n| 20 |" in text and "\n| 21 |" not in text

        main(["--grafana-url", _URL, "--top", "0"])
        text = capsys.readouterr().out
        assert "\n| 25 |" in text and "Full table" not in text
        # Fewer rows than --top: nothing is cut, so no file either.
        main(["--grafana-url", _URL, "--top", "50"])
        assert "Full table" not in capsys.readouterr().out
    assert len(list((tmp_path / ".work").rglob("*.md"))) == 1


def test_main_json_stays_complete(capsys):
    rows, data = _many_rows(30)
    with patch("disruption_common.sippy.collect_runs", return_value=(rows, False)), \
            patch("disruption_common.sippy.fetch_disruption_data", return_value=data):
        main(["--grafana-url", _URL, "--format", "json", "--top", "5"])
    assert len(json.loads(capsys.readouterr().out)) == 30


def test_default_full_table_path():
    now = datetime.datetime(2026, 11, 10, 8, 5, 3, tzinfo=datetime.timezone.utc)
    assert default_full_table_path(now) == ".work/disruption-analysis/2026-11-10/find-runs-080503.md"


@patch("disruption_common.sippy.fetch_runs")
@patch("disruption_common.sippy.fetch_disruption_data")
def test_master_nodes_y_and_n_keeps_every_run_without_warning(mock_disruption, mock_fetch_runs, capsys):
    mock_fetch_runs.return_value = [_run("Yrun", "job", "2026-11-04T00:00:00Z"),
                                    _run("Nrun", "job", "2026-11-04T01:00:00Z")]
    mock_disruption.return_value = {
        "Yrun": [{"backend_name": "kube-api-new-connections", "disruption_seconds": 5, "master_nodes_updated": "Y"}],
        "Nrun": [{"backend_name": "kube-api-new-connections", "disruption_seconds": 7, "master_nodes_updated": "N"}],
    }
    main(["--grafana-url", _URL + "&var-master_nodes_updated=Y&var-master_nodes_updated=N", "--format", "json"])
    captured = capsys.readouterr()
    assert sorted(row["build_id"] for row in json.loads(captured.out)) == ["Nrun", "Yrun"]
    assert "master_nodes_updated" not in captured.err


@patch("disruption_common.sippy.fetch_runs")
@patch("disruption_common.sippy.fetch_disruption_data")
def test_main_warns_about_a_malformed_backend(mock_disruption, mock_fetch_runs, capsys):
    mock_fetch_runs.return_value = [_run("1", "job", "2026-11-04T00:00:00Z")]
    mock_disruption.return_value = {"1": [
        {"backend_name": "kube-api-new-connections", "disruption_seconds": 5},
        {"backend_name": "host-to-host-new-connections", "disruption_seconds": 0},
    ]}
    main(["--grafana-url", _URL + "&var-backend=host-to-host-new-connec%20%20tions", "--format", "json"])
    err = capsys.readouterr().err
    assert "Warning: backend 'host-to-host-new-connec  tions' contains whitespace" in err
    assert "did you mean 'host-to-host-new-connections'?" in err



@patch("disruption_common.sippy.fetch_runs")
@patch("disruption_common.sippy.fetch_disruption_data")
def test_main_warns_when_the_disruption_api_loses_runs(mock_disruption, mock_fetch_runs, capsys):
    mock_fetch_runs.return_value = [
        {"prow_id": pid, "job": "periodic-e2e-upgrade", "timestamp": "2026-11-0%dT10:00:00Z" % pid,
         "overall_result": "F", "url": "https://prow/%d" % pid}
        for pid in (1, 2)]

    def lose_one(prow_ids, failed=None, **_kwargs):
        failed.append("2")
        return {"1": [{"backend_name": "kube-api-new-connections", "disruption_seconds": 9}]}

    mock_disruption.side_effect = lose_one

    main(["--release", "5.1", "--backend", "kube-api-new-connections", "--format", "json",
          "--since-hours", "48"])

    err = capsys.readouterr().err
    assert "failed for 1 of 2 runs" in err
    assert "unknown, not zero" in err



def test_scripts_find_the_lib_through_a_symlinked_skill_directory(tmp_path):
    import os
    import subprocess

    here = os.path.dirname(os.path.abspath(__file__))
    trend = os.path.join(here, "..", "disruption-trend")
    (tmp_path / "skills").mkdir()
    os.symlink(here, tmp_path / "skills" / "analyze-disruption")
    os.symlink(trend, tmp_path / "skills" / "disruption-trend")
    for script in ("analyze-disruption/find_disruption_runs.py", "analyze-disruption/parse_disruption.py",
                   "analyze-disruption/known_issue_queries.py", "disruption-trend/disruption_series.py"):
        result = subprocess.run([sys.executable, str(tmp_path / "skills" / script), "--help"],
                                capture_output=True, text=True)
        assert result.returncode == 0, result.stderr


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
