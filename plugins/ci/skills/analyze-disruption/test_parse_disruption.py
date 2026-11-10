"""Tests for parse_disruption.py — format_summary, blast_radius, classify_backend, node_name, e2e filtering,
episodes and waves, static-pod revision rollouts, and payloads."""
import json
import os
import sys
import tempfile

import pytest

from parse_disruption import (
    analyze_episodes,
    backend_matches_filter,
    classify_backend,
    describe_episodes,
    describe_rollouts,
    extract_concurrent_events,
    extract_disruptions,
    extract_revision_rollouts,
    extract_timeline_target_version,
    find_episodes,
    find_payloads,
    find_waves,
    format_blast_radius,
    format_summary,
    format_text,
    generate_summary,
    link_rollouts_to_episodes,
    node_name,
    parse_revision_message,
    summarize_e2e_tests,
)


def _make_data(
    disruptions=None,
    backends=None,
    ovs=None,
    etcd=None,
    cpu=None,
    cloud=None,
    liveness="clean",
    phase=None,
    source_pattern="unknown",
    source_node=None,
):
    """Build a minimal analysis data dict for format_summary tests."""
    summary = {
        "disruption_count": len(disruptions or []),
        "backends": backends or {},
        "time_range": None,
        "phase_breakdown": phase or {},
        "network_liveness_status": liveness,
        "network_liveness_detail": "",
        "source_node_pattern": source_pattern,
        "key_signals": [],
    }
    concurrent = {}
    if ovs:
        concurrent["OVSVswitchdLog"] = ovs
    if etcd:
        concurrent["EtcdLog"] = etcd
    if cpu:
        concurrent["CPUMonitor"] = cpu
    if cloud:
        concurrent["CloudMetrics"] = cloud

    sa = {"pattern": source_pattern}
    if source_pattern == "single-source-fan-out" and source_node:
        sa["source_node"] = source_node

    return {
        "disruptions": disruptions or [],
        "concurrent_events": concurrent,
        "source_node_analysis": sa,
        "network_liveness": {},
        "summary": summary,
        "links": {},
    }


def test_format_summary_no_disruptions():
    data = _make_data()
    result = format_summary(data)
    assert result.startswith("0 disruptions")


def test_format_summary_single_disruption():
    data = _make_data(
        disruptions=[{"backend": "host-to-host-new-connections"}],
        backends={"host-to-host-new-connections": 1},
    )
    result = format_summary(data)
    assert "1 disruption" in result
    assert "1 disruptions" not in result
    assert "host-to-host:1" in result


def test_format_summary_with_ovs():
    data = _make_data(
        disruptions=[{}] * 3,
        backends={"kube-api-new-connections": 3},
        ovs={"count": 5, "max_poll_interval_ms": 1200, "nodes_affected": 2},
    )
    result = format_summary(data)
    assert "OVS:5 (max 1200ms)" in result


def test_format_summary_with_etcd():
    data = _make_data(
        disruptions=[{}] * 2,
        backends={"kube-api-new-connections": 2},
        etcd={"count": 8, "events": []},
    )
    result = format_summary(data)
    assert "etcd:8" in result


def test_format_summary_with_cpu():
    data = _make_data(
        disruptions=[{}] * 1,
        backends={"host-to-host-new-connections": 1},
        cpu={"count": 2, "nodes": [
            {"node_short": "master-0", "from": "t0", "node": "x"},
            {"node_short": "master-1", "from": "t1", "node": "y"},
        ]},
    )
    result = format_summary(data)
    assert "CPU: master-0,master-1" in result


def test_format_summary_with_cloud_metrics():
    data = _make_data(
        disruptions=[{}] * 1,
        backends={"kube-api-new-connections": 1},
        cloud={"count": 3, "metrics": {
            "OS Disk IOPS Consumed Percentage": {"count": 3, "max_value": 98.5},
        }},
    )
    result = format_summary(data)
    assert "cloud:" in result
    assert "IOPS%:99" in result or "IOPS%:98" in result


def test_format_summary_degraded_liveness():
    data = _make_data(
        disruptions=[{}] * 2,
        backends={"kube-api-new-connections": 2},
        liveness="degraded",
    )
    result = format_summary(data)
    assert "net-liveness: degraded" in result


def test_format_summary_clean_liveness_omitted():
    data = _make_data(
        disruptions=[{}] * 2,
        backends={"kube-api-new-connections": 2},
        liveness="clean",
    )
    result = format_summary(data)
    assert "net-liveness" not in result


def test_format_summary_phase_breakdown():
    data = _make_data(
        disruptions=[{}] * 3,
        backends={"kube-api-new-connections": 3},
        phase={"upgrade": 2, "conformance": 1},
    )
    result = format_summary(data)
    assert "phase:" in result
    assert "upgrade:2" in result
    assert "conformance:1" in result


def test_format_summary_single_source_fanout():
    data = _make_data(
        disruptions=[{}] * 4,
        backends={"host-to-host-new-connections": 4},
        source_pattern="single-source-fan-out",
        source_node="db64f",
    )
    result = format_summary(data)
    assert "src-node: db64f" in result


def test_format_summary_strips_connection_suffix():
    data = _make_data(
        disruptions=[{}] * 5,
        backends={
            "kube-api-new-connections": 3,
            "kube-api-reused-connections": 2,
        },
    )
    result = format_summary(data)
    assert "kube-api:5" in result
    assert "new-connections" not in result
    assert "reused-connections" not in result


def test_format_summary_full_example():
    data = _make_data(
        disruptions=[{}] * 11,
        backends={"host-to-host-new-connections": 8, "cache-host-to-host-new-connections": 3},
        ovs={"count": 12, "max_poll_interval_ms": 9000, "nodes_affected": 1},
        etcd={"count": 5, "events": []},
        cpu={"count": 1, "nodes": [{"node_short": "master-0", "from": "t0", "node": "x"}]},
        phase={"upgrade": 11},
        source_pattern="single-source-fan-out",
        source_node="abc12",
    )
    result = format_summary(data)
    assert "11 disruptions" in result
    assert "host-to-host:" in result
    assert "OVS:12 (max 9000ms)" in result
    assert "etcd:5" in result
    assert "CPU: master-0" in result
    assert "src-node: abc12" in result
    assert "phase: upgrade:11" in result


def test_classify_backend_cache():
    assert classify_backend("cache-kube-api-new-connections") == "cache"


def test_classify_backend_non_cache():
    assert classify_backend("kube-api-new-connections") == "non-cache"


def test_classify_backend_canary():
    assert classify_backend("ci-cluster-network-liveness") == "canary"


def test_classify_backend_cloud():
    assert classify_backend("aws-network-liveness-static") == "cloud"


def test_node_name_master():
    assert node_name("ci-op-xxx-master-0") == "master-0"


def test_node_name_worker():
    assert node_name("ci-op-xxx-worker-westus-db64f") == "db64f"


def test_node_name_empty():
    assert node_name("") == ""


def test_e2e_passed_and_failed_in_concurrent():
    """Both passed and failed E2ETest events are captured with test names."""
    disruptions = [{"from": "2026-01-01T12:00:00Z", "to": "2026-01-01T12:00:05Z"}]
    items = [
        {
            "source": "E2ETest", "level": "Info",
            "from": "2026-01-01T12:00:00Z", "to": "2026-01-01T12:00:02Z",
            "locator": {"keys": {"e2e-test": "passing-test"}},
            "message": {"humanMessage": "e2e test finished As Passed"},
        },
        {
            "source": "E2ETest", "level": "Error",
            "from": "2026-01-01T12:00:01Z", "to": "2026-01-01T12:00:03Z",
            "locator": {"keys": {"e2e-test": "failing-test"}},
            "message": {"humanMessage": "e2e test finished As Failed"},
        },
    ]
    result = extract_concurrent_events(items, disruptions, window_seconds=60)
    e2e = result.get("E2ETest", {})
    assert e2e["count"] == 2
    assert "failing-test" in e2e["failed_tests"]
    assert "passing-test" in e2e["passed_tests"]


def test_e2e_test_name_extracted():
    """E2ETest events include the test name from locator.keys."""
    events = [
        {"from": "t0", "level": "Error", "message": "failed",
         "test_name": "my-important-test"},
    ]
    result = summarize_e2e_tests(events)
    assert "my-important-test" in result["tests"]
    assert "my-important-test" in result["failed_tests"]


def test_e2e_summarize_dedup():
    """Multiple events for same test keep worst level."""
    events = [
        {"from": "t0", "level": "Warning", "message": "x", "test_name": "test-a"},
        {"from": "t1", "level": "Error", "message": "y", "test_name": "test-a"},
    ]
    result = summarize_e2e_tests(events)
    assert result["tests"]["test-a"]["level"] == "Error"


def test_blast_radius_excludes_filtered():
    disruptions = [
        {"backend": "host-to-host-new-connections", "backend_type": "non-cache"},
        {"backend": "host-to-host-new-connections", "backend_type": "non-cache"},
        {"backend": "kube-api-new-connections", "backend_type": "non-cache"},
        {"backend": "oauth-api-new-connections", "backend_type": "non-cache"},
        {"backend": "cache-kube-api-new-connections", "backend_type": "cache"},
    ]
    result = format_blast_radius(disruptions, ["host-to-host"])
    assert result is not None
    names = [e["backend"] for e in result["backends"]]
    assert "host-to-host-new-connections" not in names
    assert "kube-api-new-connections" in names
    assert "oauth-api-new-connections" in names
    assert result["total_count"] == 3
    assert result["backend_count"] == 3


def test_blast_radius_none_when_no_others():
    disruptions = [
        {"backend": "host-to-host-new-connections", "backend_type": "non-cache"},
    ]
    result = format_blast_radius(disruptions, ["host-to-host"])
    assert result is None


def test_blast_radius_keeps_derived_backends():
    disruptions = [
        {"backend": "kube-api-new-connections", "backend_type": "non-cache"},
        {"backend": "kube-api-http2-localhost-new-connections", "backend_type": "non-cache"},
        {"backend": "cache-kube-api-new-connections", "backend_type": "cache"},
    ]
    result = format_blast_radius(disruptions, ["kube-api-new-connections"])
    names = [entry["backend"] for entry in result["backends"]]
    assert "kube-api-new-connections" not in names
    assert "kube-api-http2-localhost-new-connections" in names
    assert "cache-kube-api-new-connections" in names


def test_backend_filter_does_not_match_derived_names():
    assert backend_matches_filter("kube-api-new-connections", ["kube-api-new-connections"])
    assert not backend_matches_filter(
        "kube-api-http2-localhost-new-connections", ["kube-api-new-connections"])
    assert not backend_matches_filter(
        "cache-kube-api-new-connections", ["kube-api-new-connections"])
    # A bare base still matches only the two connection variants.
    assert backend_matches_filter("kube-api-reused-connections", ["kube-api"])
    assert not backend_matches_filter("kube-api-http2-localhost-new-connections", ["kube-api"])


def _disruption_item(backend):
    return {
        "source": "Disruption",
        "level": "Error",
        "from": "2026-10-01T00:00:00Z",
        "to": "2026-10-01T00:00:10Z",
        "locator": {"keys": {"backend-disruption-name": backend}},
        "message": {"humanMessage": "%s stopped responding" % backend, "reason": "DisruptionBegan"},
    }


def test_extract_disruptions_exact_backend_names():
    items = [
        _disruption_item("kube-api-new-connections"),
        _disruption_item("kube-api-http2-localhost-new-connections"),
        _disruption_item("cache-kube-api-new-connections"),
    ]
    result = extract_disruptions(items, ["kube-api-new-connections"])
    assert [event["backend"] for event in result] == ["kube-api-new-connections"]


def test_blast_radius_compact_format():
    disruptions = [
        {"backend": "kube-api-new-connections", "backend_type": "non-cache"},
        {"backend": "kube-api-new-connections", "backend_type": "non-cache"},
        {"backend": "oauth-api-new-connections", "backend_type": "non-cache"},
    ]
    result = format_blast_radius(disruptions, ["host-to-host"])
    assert "kube-api-new-connections:2" in result["compact"]
    assert "oauth-api-new-connections:1" in result["compact"]


# ---------------------------------------------------------------------------
# Episodes and waves
# ---------------------------------------------------------------------------

LOCALHOST = (
    "kube-api-http1-localhost-new-connections",
    "kube-api-http2-localhost-new-connections",
    "openshift-api-http2-localhost-new-connections",
)


def _outage(start, end, tail_end=None):
    """One outage as the probes record it: every backend from start to end, and the
    openshift-api probe continuing in a back-to-back interval until tail_end."""
    def interval(backend, begin, finish):
        return {"backend": backend, "from": begin, "to": finish, "phase": "upgrade",
                "error_type": "connection-refused", "source_node": "", "target_node": "",
                "target_endpoint": ""}
    out = [interval(b, start, end) for b in LOCALHOST]
    if tail_end:
        out.append(interval(LOCALHOST[2], end, tail_end))
    return out


# Shape of run 2120065590293958656: two kube-apiserver rollouts, one master at a time.
TWO_ROLLOUTS = (
    _outage("2026-11-10T09:41:18Z", "2026-11-10T09:41:36Z", "2026-11-10T09:41:38Z")
    + _outage("2026-11-10T09:44:48Z", "2026-11-10T09:45:01Z", "2026-11-10T09:45:03Z")
    + _outage("2026-11-10T09:48:14Z", "2026-11-10T09:48:35Z", "2026-11-10T09:48:38Z")
    + _outage("2026-11-10T10:00:59Z", "2026-11-10T10:01:07Z", "2026-11-10T10:01:09Z")
    + _outage("2026-11-10T10:04:19Z", "2026-11-10T10:04:28Z", "2026-11-10T10:04:30Z")
    + _outage("2026-11-10T10:07:40Z", "2026-11-10T10:07:52Z", "2026-11-10T10:07:59Z")
)


def test_find_episodes_merges_backends_and_back_to_back_intervals():
    episodes = find_episodes(_outage("2026-11-10T09:41:18Z", "2026-11-10T09:41:36Z", "2026-11-10T09:41:38Z"))
    assert len(episodes) == 1
    ep = episodes[0]
    assert ep["index"] == 1
    assert (ep["from"], ep["to"]) == ("2026-11-10T09:41:18Z", "2026-11-10T09:41:38Z")
    assert ep["duration_seconds"] == 20
    assert ep["backends"] == sorted(LOCALHOST)
    assert ep["interval_count"] == 4
    assert ep["phases"] == ["upgrade"]


def test_find_episodes_gap_tolerance():
    near = [
        {"backend": "a", "from": "2026-11-10T09:00:00Z", "to": "2026-11-10T09:00:05Z"},
        {"backend": "b", "from": "2026-11-10T09:00:30Z", "to": "2026-11-10T09:00:31Z"},
    ]
    assert len(find_episodes(near)) == 1
    far = [
        {"backend": "a", "from": "2026-11-10T09:00:00Z", "to": "2026-11-10T09:00:05Z"},
        {"backend": "b", "from": "2026-11-10T09:00:36Z", "to": "2026-11-10T09:00:37Z"},
    ]
    episodes = find_episodes(far)
    assert len(episodes) == 2
    assert episodes[1]["phases"] == ["unknown"]


def test_find_episodes_unsorted_input():
    episodes = find_episodes(list(reversed(TWO_ROLLOUTS)))
    assert [ep["from"][11:] for ep in episodes] == [
        "09:41:18Z", "09:44:48Z", "09:48:14Z", "10:00:59Z", "10:04:19Z", "10:07:40Z"]


def test_two_waves_from_two_rollouts():
    data = analyze_episodes(TWO_ROLLOUTS)
    waves = data["waves"]
    assert [w["episode_indices"] for w in waves] == [[1, 2, 3], [4, 5, 6]]
    assert waves[0]["gap_before_seconds"] is None
    assert waves[1]["gap_before_seconds"] == 741  # 09:48:38 -> 10:00:59
    assert waves[1]["start_spacing_before_seconds"] == 1181  # 09:41:18 -> 10:00:59
    assert waves[0]["median_spacing_seconds"] == 206
    assert data["wave_split_threshold_seconds"] == 380
    assert describe_episodes(data) == "6 episodes in 2 waves (3+3), wave gap 12m (starts 20m apart)"


def test_one_wave_for_one_rollout():
    data = analyze_episodes(TWO_ROLLOUTS[:12])
    assert len(data["waves"]) == 1
    assert describe_episodes(data) == "3 episodes in 1 wave, ~3.4m apart"


def test_wave_split_clamps():
    def ep(idx, start, end):
        return {"index": idx, "from": start, "to": end}
    # Small gaps never split, even when one is much larger than the others.
    waves, threshold = find_waves([
        ep(1, "2026-11-10T09:00:00Z", "2026-11-10T09:00:10Z"),
        ep(2, "2026-11-10T09:00:40Z", "2026-11-10T09:00:50Z"),
        ep(3, "2026-11-10T09:04:00Z", "2026-11-10T09:04:10Z"),
    ])
    assert threshold == 300
    assert len(waves) == 1
    # A single gap over the maximum always splits.
    waves, threshold = find_waves([
        ep(1, "2026-11-10T09:00:00Z", "2026-11-10T09:00:10Z"),
        ep(2, "2026-11-10T09:40:00Z", "2026-11-10T09:40:10Z"),
    ])
    assert threshold == 600
    assert [w["episode_indices"] for w in waves] == [[1], [2]]


def test_episodes_empty_and_single():
    assert analyze_episodes([]) == {"episodes": [], "waves": [], "episode_gap_seconds": 30,
                                    "wave_split_threshold_seconds": None}
    assert describe_episodes(analyze_episodes([])) == ""
    single = analyze_episodes(_outage("2026-11-10T09:41:18Z", "2026-11-10T09:41:36Z"))
    assert describe_episodes(single) == "1 episode"
    assert single["waves"][0]["episode_indices"] == [1]


# ---------------------------------------------------------------------------
# Static-pod revision rollouts
# ---------------------------------------------------------------------------

def _operator_state(operator, start, end, message, reason="NodeInstaller"):
    return {
        "level": "Warning", "source": "OperatorState", "display": True,
        "locator": {"type": "ClusterOperator", "keys": {"clusteroperator": operator}},
        "message": {"reason": reason, "cause": "", "humanMessage": message,
                    "annotations": {"condition": "Progressing", "reason": reason, "status": "True"}},
        "from": start, "to": end,
    }


ROLLOUT_ITEMS = [
    _operator_state("etcd", "2026-11-10T09:37:42Z", "2026-11-10T09:44:15Z",
                    "NodeInstallerProgressing: 3 nodes are at revision 8; 0 nodes have achieved new revision 9"),
    _operator_state("kube-apiserver", "2026-11-10T09:38:22Z", "2026-11-10T09:49:21Z",
                    "NodeInstallerProgressing: 3 nodes are at revision 6; 0 nodes have achieved new revision 7"),
    _operator_state("kube-scheduler", "2026-11-10T09:49:03Z", "2026-11-10T09:54:40Z",
                    "NodeInstallerProgressing: 3 nodes are at revision 5; 0 nodes have achieved new revision 6"),
    _operator_state("kube-apiserver", "2026-11-10T09:58:38Z", "2026-11-10T10:08:34Z",
                    "NodeInstallerProgressing: 3 nodes are at revision 8; 0 nodes have achieved new revision 9"),
    # Not static-pod operators, or not a revision message.
    _operator_state("openshift-apiserver", "2026-11-10T09:58:00Z", "2026-11-10T10:02:00Z",
                    "APIServerDeploymentProgressing: observed generation is 8, desired generation is 9.",
                    reason="APIServerDeployment_NewGeneration"),
    _operator_state("kube-apiserver", "2026-11-10T09:30:00Z", "2026-11-10T09:30:05Z",
                    "Progressing: 3 nodes are at revision 6", reason="AsExpected"),
    {"source": "Disruption", "level": "Error", "from": "2026-11-10T09:41:18Z", "to": "2026-11-10T09:41:36Z",
     "locator": {"keys": {"backend-disruption-name": LOCALHOST[0]}},
     "message": {"humanMessage": "3 nodes are at revision 6; 0 nodes have achieved new revision 7"}},
]


@pytest.mark.parametrize("message,expected", [
    ("NodeInstallerProgressing: 3 nodes are at revision 6; 0 nodes have achieved new revision 7", (6, 7)),
    ("NodeInstallerProgressing: 2 nodes are at revision 6; 1 node is at revision 7; "
     "0 nodes have achieved new revision 8", (6, 8)),
    ("NodeInstallerProgressing: 2 nodes are at revision 6; 1 node has achieved new revision 7", (6, 7)),
    ("NodeInstallerProgressing: 1 node is at revision 7; 2 nodes are at revision 8", (7, 8)),
    ("NodeInstallerProgressing: 3 nodes are at revision 0; 0 nodes have achieved new revision 1", (0, 1)),
    ("NodeInstallerProgressing: 3 nodes are at revision 8", None),
    ("", None),
])
def test_parse_revision_message(message, expected):
    assert parse_revision_message(message) == expected


def test_extract_revision_rollouts():
    rollouts = extract_revision_rollouts(ROLLOUT_ITEMS)
    assert [(r["operator"], r["from_revision"], r["to_revision"]) for r in rollouts] == [
        ("etcd", 8, 9), ("kube-apiserver", 6, 7), ("kube-scheduler", 5, 6), ("kube-apiserver", 8, 9)]
    kas = rollouts[1]
    assert (kas["from"], kas["to"]) == ("2026-11-10T09:38:22Z", "2026-11-10T09:49:21Z")
    assert kas["duration_seconds"] == 659
    assert kas["message"].startswith("NodeInstallerProgressing: 3 nodes are at revision 6")


def test_extract_revision_rollouts_merges_progress_updates_and_duplicates():
    items = [
        _operator_state("kube-apiserver", "2026-11-10T09:38:22Z", "2026-11-10T09:42:00Z",
                        "NodeInstallerProgressing: 3 nodes are at revision 6; 0 nodes have achieved new revision 7"),
        _operator_state("kube-apiserver", "2026-11-10T09:42:00Z", "2026-11-10T09:49:21Z",
                        "NodeInstallerProgressing: 2 nodes are at revision 6; 1 node has achieved new revision 7"),
        # The same interval again, as when it appears in both timeline files.
        _operator_state("kube-apiserver", "2026-11-10T09:42:00Z", "2026-11-10T09:49:21Z",
                        "NodeInstallerProgressing: 2 nodes are at revision 6; 1 node has achieved new revision 7"),
    ]
    rollouts = extract_revision_rollouts(items)
    assert len(rollouts) == 1
    assert (rollouts[0]["from"], rollouts[0]["to"]) == ("2026-11-10T09:38:22Z", "2026-11-10T09:49:21Z")
    assert (rollouts[0]["from_revision"], rollouts[0]["to_revision"]) == (6, 7)


def test_link_rollouts_to_episodes_and_waves():
    episode_data = analyze_episodes(TWO_ROLLOUTS)
    rollouts = link_rollouts_to_episodes(extract_revision_rollouts(ROLLOUT_ITEMS), episode_data)
    by_key = {(r["operator"], r["to_revision"]): r for r in rollouts}
    assert by_key[("kube-apiserver", 7)]["episode_indices"] == [1, 2, 3]
    assert by_key[("kube-apiserver", 7)]["waves"] == [
        {"wave": 1, "episodes_inside": 3, "episodes_in_wave": 3}]
    assert by_key[("kube-apiserver", 9)]["episode_indices"] == [4, 5, 6]
    # Ends 33s before episode 2 starts.
    assert by_key[("etcd", 9)]["episode_indices"] == [1]
    # Starts 25s after episode 3 ends, outside the 15s slack.
    assert by_key[("kube-scheduler", 6)]["episode_indices"] == []
    waves = episode_data["waves"]
    assert waves[0]["rollouts"] == ["etcd 8->9 (1/3)", "kube-apiserver 6->7 (3/3)"]
    assert waves[1]["rollouts"] == ["kube-apiserver 8->9 (3/3)"]
    assert describe_rollouts(rollouts) == (
        "etcd 8->9 (w1 1/3), KAS 6->7 (w1 3/3), KAS 8->9 (w2 3/3), +1 without disruption")


def test_generate_summary_flags_multiple_kas_rollouts():
    episode_data = analyze_episodes(TWO_ROLLOUTS)
    rollouts = link_rollouts_to_episodes(extract_revision_rollouts(ROLLOUT_ITEMS), episode_data)
    summary = generate_summary(TWO_ROLLOUTS, {}, {}, {"pattern": "unknown"}, episode_data, rollouts)
    assert summary["episode_count"] == 6
    assert summary["wave_count"] == 2
    assert summary["episode_summary"].startswith("6 episodes in 2 waves (3+3)")
    assert "2 kube-apiserver revision rollouts (6->7, 8->9)" in summary["key_signals"]
    # Old callers still work and get empty episode fields.
    legacy = generate_summary([], {}, {}, {"pattern": "none"})
    assert legacy["episode_count"] == 0
    assert legacy["episode_summary"] == ""


def test_format_summary_and_text_include_episodes_rollouts_payloads():
    episode_data = analyze_episodes(TWO_ROLLOUTS)
    rollouts = link_rollouts_to_episodes(extract_revision_rollouts(ROLLOUT_ITEMS), episode_data)
    summary = generate_summary(TWO_ROLLOUTS, {}, {}, {"pattern": "unknown", "detail": ""},
                               episode_data, rollouts)
    data = {
        "disruptions": TWO_ROLLOUTS, "concurrent_events": {},
        "source_node_analysis": {"pattern": "unknown", "detail": ""}, "network_liveness": {},
        "episodes": episode_data, "revision_rollouts": rollouts,
        "payloads": {"initial": "registry.ci.openshift.org/ocp/release-5:5.0.0-0.nightly-2026-11-09-184859",
                     "target": "registry.ci.openshift.org/ocp/release-5:5.1.0-0.nightly-2026-11-10-075706",
                     "source": "prowjob-env"},
        "summary": summary, "links": {},
    }
    line = format_summary(data)
    assert "| 6 episodes in 2 waves (3+3), wave gap 12m (starts 20m apart) |" in line
    assert "rollouts: etcd 8->9 (w1 1/3), KAS 6->7 (w1 3/3), KAS 8->9 (w2 3/3)" in line
    assert line.endswith(
        "payload: 5.0.0-0.nightly-2026-11-09-184859 -> 5.1.0-0.nightly-2026-11-10-075706")
    text = format_text(data)
    assert "Episodes: 6 episodes in 2 waves" in text
    assert ("Payloads: 5.0.0-0.nightly-2026-11-09-184859 -> 5.1.0-0.nightly-2026-11-10-075706 "
            "(from prowjob-env)") in text
    assert "Wave 2: episodes 4,5,6" in text
    assert "inside kube-apiserver 8->9 (3/3)" in text
    assert "kube-scheduler 5->6 | 2026-11-10T09:49:03Z-2026-11-10T09:54:40Z" in text
    assert "no disruption episodes" in text


def test_format_summary_without_new_keys_is_unchanged():
    data = _make_data(disruptions=[{}] * 2, backends={"kube-api-new-connections": 2})
    assert format_summary(data) == "2 disruptions | kube-api:2"


# ---------------------------------------------------------------------------
# Payloads
# ---------------------------------------------------------------------------

CLUSTERVERSION_ITEM = {
    "source": "OperatorState", "level": "Warning",
    "locator": {"type": "ClusterVersion", "keys": {"clusterversion": "version"}},
    "message": {"humanMessage": "changed to Progressing=True: Working towards 5.1.0-0.ci-2026-11-09-112923: "
                                "2 of 1072 done (0% complete)"},
    "from": "2026-11-09T23:44:41Z", "to": "2026-11-10T00:23:14Z",
}


def test_extract_timeline_target_version():
    assert extract_timeline_target_version([CLUSTERVERSION_ITEM]) == "5.1.0-0.ci-2026-11-09-112923"
    no_counts = dict(CLUSTERVERSION_ITEM, message={
        "humanMessage": "changed to Progressing=True: Working towards 5.1.0-0.nightly-2026-11-10-075706"})
    assert extract_timeline_target_version([no_counts]) == "5.1.0-0.nightly-2026-11-10-075706"
    assert extract_timeline_target_version(ROLLOUT_ITEMS) is None


def test_find_payloads_reads_prowjob_beside_timelines():
    with tempfile.TemporaryDirectory() as tmp:
        logs = os.path.join(tmp, "123", "logs")
        os.makedirs(logs)
        with open(os.path.join(logs, "prowjob.json"), "w") as f:
            json.dump({"spec": {"pod_spec": {"containers": [{"env": [
                {"name": "RELEASE_IMAGE_LATEST", "value": "registry.ci.openshift.org/ocp/release-5:5.1.0-b"},
                {"name": "RELEASE_IMAGE_INITIAL", "value": "registry.ci.openshift.org/ocp/release-5:5.0.0-a"},
            ]}]}}}, f)
        payloads = find_payloads([os.path.join(logs, "e2e-timelines_spyglass_1.json")], [CLUSTERVERSION_ITEM])
    assert payloads["initial"].endswith(":5.0.0-a")
    assert payloads["target"].endswith(":5.1.0-b")
    assert payloads["source"] == "prowjob-env"
    assert payloads["timeline_target_version"] == "5.1.0-0.ci-2026-11-09-112923"


def test_find_payloads_falls_back_to_clusterversion_then_timeline():
    with tempfile.TemporaryDirectory() as tmp:
        logs = os.path.join(tmp, "123", "logs")
        gather = os.path.join(tmp, "123", "gather")
        os.makedirs(logs)
        os.makedirs(gather)
        timeline = os.path.join(logs, "e2e-timelines_spyglass_1.json")
        with open(os.path.join(logs, "prowjob.json"), "w") as f:
            json.dump({"spec": {"pod_spec": {"containers": [{"args": ["--target=e2e-gcp-runc-upgrade"]}]}}}, f)

        payloads = find_payloads([timeline], [CLUSTERVERSION_ITEM])
        assert payloads["initial"] is None and payloads["target"] is None
        assert payloads["timeline_target_version"] == "5.1.0-0.ci-2026-11-09-112923"

        with open(os.path.join(gather, "clusterversion.json"), "w") as f:
            json.dump({"kind": "List", "items": [{"status": {"history": [
                {"state": "Completed", "version": "5.1.0-0.ci-2026-11-09-112923", "image": "reg/release@sha256:b"},
                {"state": "Completed", "version": "5.1.0-0.ci-2026-11-08-232923", "image": "reg/release@sha256:a"},
            ]}}]}, f)
        payloads = find_payloads([timeline], [CLUSTERVERSION_ITEM])
    assert payloads["initial"] == "5.1.0-0.ci-2026-11-08-232923"
    assert payloads["target"] == "5.1.0-0.ci-2026-11-09-112923"
    assert payloads["source"] == "clusterversion-history"


def test_parser_without_download_timelines_reports_unknown_payloads(tmp_path):
    import shutil
    import subprocess

    here = os.path.dirname(os.path.abspath(__file__))
    skill = tmp_path / "skills" / "analyze-disruption"
    skill.mkdir(parents=True)
    shutil.copy(os.path.join(here, "parse_disruption.py"), skill)
    shutil.copytree(os.path.join(here, "..", "..", "lib", "disruption_common"),
                    tmp_path / "skills" / "disruption_common")
    timeline = tmp_path / "e2e-timelines_spyglass_1.json"
    timeline.write_text(json.dumps({"items": ROLLOUT_ITEMS + [CLUSTERVERSION_ITEM]}))
    result = subprocess.run([sys.executable, str(skill / "parse_disruption.py"), str(timeline),
                             "--format", "json"], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert data["payloads"]["target"] is None
    assert "download_timelines.py not found" in data["payloads"]["warning"]
    assert data["payloads"]["timeline_target_version"] == "5.1.0-0.ci-2026-11-09-112923"
    assert data["summary"]["episode_count"] == 1
    assert [r["operator"] for r in data["revision_rollouts"]][:2] == ["etcd", "kube-apiserver"]


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
