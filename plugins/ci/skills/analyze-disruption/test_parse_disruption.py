"""Tests for parse_disruption.py — format_summary, blast_radius, classify_backend, node_name, e2e filtering."""
from parse_disruption import (
    classify_backend,
    extract_concurrent_events,
    format_blast_radius,
    format_summary,
    node_name,
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


def test_blast_radius_compact_format():
    disruptions = [
        {"backend": "kube-api-new-connections", "backend_type": "non-cache"},
        {"backend": "kube-api-new-connections", "backend_type": "non-cache"},
        {"backend": "oauth-api-new-connections", "backend_type": "non-cache"},
    ]
    result = format_blast_radius(disruptions, ["host-to-host"])
    assert "kube-api-new-connections:2" in result["compact"]
    assert "oauth-api-new-connections:1" in result["compact"]
