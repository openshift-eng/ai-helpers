#!/usr/bin/env python3
"""Parse disruption events from OpenShift CI interval/timeline JSON files.

Extracts disruption events, classifies backends, finds concurrent cluster
activity, detects source-node patterns, and summarizes OVS/CPU/disk/etcd
signals.

Usage:
    python3 parse_disruption.py <timeline.json> [timeline2.json ...] \
        [--backends backend1,backend2] [--window 60] [--format json|text]

Output (JSON mode):
    {
        "disruptions": [...],
        "concurrent_events": {...},
        "source_node_analysis": {...},
        "network_liveness": {...},
        "summary": {...}
    }
"""

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime, timedelta


# ---------------------------------------------------------------------------
# Backend classification
# ---------------------------------------------------------------------------

def classify_backend(name):
    """Classify a backend-disruption-name into a category."""
    if "ci-cluster-network-liveness" in name:
        return "canary"
    if "network-liveness" in name:
        return "cloud"
    if "cache-" in name or "-cache-" in name:
        return "cache"
    return "non-cache"


# ---------------------------------------------------------------------------
# Timestamp helpers
# ---------------------------------------------------------------------------

def parse_ts(ts_str):
    """Parse an ISO timestamp string to datetime."""
    return datetime.fromisoformat(ts_str.replace("Z", "+00:00"))


def fmt_ts(dt):
    """Format datetime back to a short timestamp."""
    return dt.strftime("%H:%M:%SZ")


# ---------------------------------------------------------------------------
# Core extraction
# ---------------------------------------------------------------------------

def load_items(paths):
    """Load and merge items from one or more timeline JSON files.

    Items are tagged with a _phase ("upgrade" or "conformance") based on file
    ordering.  Timeline files are sorted by filename timestamp — the first is
    the upgrade phase, the second is the conformance/e2e-test phase.
    """
    sorted_paths = sorted(paths)
    all_items = []
    for idx, path in enumerate(sorted_paths):
        # First file = upgrade, second = conformance
        phase = "upgrade" if idx == 0 and len(sorted_paths) > 1 else "conformance"
        with open(path) as fh:
            data = json.load(fh)
        items = data if isinstance(data, list) else data.get("items", [])
        for item in items:
            item["_phase"] = phase
            item["_source_file"] = path
        all_items.extend(items)
    return all_items


def extract_disruptions(items, backend_filter=None):
    """Extract disruption Error/Warning events, optionally filtered by backend names."""
    results = []
    for item in items:
        if item.get("source") != "Disruption":
            continue
        if item.get("level") not in ("Error", "Warning"):
            continue

        keys = item.get("locator", {}).get("keys", {})
        backend = keys.get("backend-disruption-name", "")
        if not backend:
            continue

        if backend_filter:
            if not any(bf in backend for bf in backend_filter):
                continue

        disruption_path = keys.get("disruption", "")
        src_node, dst_node, dst_endpoint = parse_disruption_path(disruption_path)

        msg = item.get("message", {})
        human = msg.get("humanMessage", "")
        reason = msg.get("reason", "")

        # Extract error type from the message
        error_type = "unknown"
        lower_msg = human.lower()
        if "eof" in lower_msg:
            error_type = "EOF"
        elif "timeout" in lower_msg or "timed out" in lower_msg:
            error_type = "timeout"
        elif "connection refused" in lower_msg:
            error_type = "connection-refused"
        elif "stopped responding" in lower_msg:
            error_type = "stopped-responding"
        elif "no such host" in lower_msg:
            error_type = "dns-failure"
        elif reason == "DisruptionBegan":
            error_type = "stopped-responding"

        results.append({
            "backend": backend,
            "backend_type": classify_backend(backend),
            "from": item["from"],
            "to": item["to"],
            "level": item["level"],
            "error_type": error_type,
            "message": human[:300],
            "source_node": src_node,
            "target_node": dst_node,
            "target_endpoint": dst_endpoint,
            "connection_type": keys.get("connection", ""),
            "phase": item.get("_phase", "unknown"),
        })

    results.sort(key=lambda d: d["from"])
    return results


def parse_disruption_path(path):
    """Parse a disruption locator path to extract source node, target node, endpoint.

    Example path:
      host-to-host-from-node-ci-op-xxx-worker-westus-db64f-to-node-ci-op-xxx-master-0-endpoint-10.0.0.5
    """
    src_node = ""
    dst_node = ""
    endpoint = ""

    if "-from-node-" in path and "-to-node-" in path:
        after_from = path.split("-from-node-", 1)[1]
        parts = after_from.split("-to-node-", 1)
        src_node = parts[0]
        if len(parts) > 1:
            rest = parts[1]
            if "-endpoint-" in rest:
                ep_parts = rest.split("-endpoint-", 1)
                dst_node = ep_parts[0]
                endpoint = ep_parts[1]
            else:
                dst_node = rest

    return src_node, dst_node, endpoint


def extract_network_liveness(items):
    """Extract network-liveness disruption summary."""
    results = defaultdict(list)
    for item in items:
        if item.get("source") != "Disruption":
            continue
        if item.get("level") not in ("Error", "Warning"):
            continue
        keys = item.get("locator", {}).get("keys", {})
        backend = keys.get("backend-disruption-name", "")
        if "network-liveness" not in backend and "ci-cluster-network-liveness" not in backend:
            continue
        results[backend].append({"from": item["from"], "to": item["to"]})

    summary = {}
    for backend, events in results.items():
        events.sort(key=lambda e: e["from"])
        summary[backend] = {
            "count": len(events),
            "first": events[0]["from"],
            "last": events[-1]["to"],
            "type": classify_backend(backend),
        }
    return summary


# ---------------------------------------------------------------------------
# Concurrent event analysis
# ---------------------------------------------------------------------------

CONTEXT_SOURCES = {
    "OVSVswitchdLog", "CPUMonitor", "CloudMetrics", "EtcdLog",
    "EtcdDiskCommitDuration", "EtcdDiskWalFsyncDuration", "AuditLog",
    "Alert", "NodeMonitor", "MachineMonitor", "KubeletLog",
    "ClusterVersion", "ClusterOperator", "E2ETest", "PodLog",
}


def extract_concurrent_events(items, disruptions, window_seconds=60):
    """Extract non-disruption events within a time window of disruption events."""
    if not disruptions:
        return {}

    # Compute the overall disruption window
    all_from = [parse_ts(d["from"]) for d in disruptions]
    all_to = [parse_ts(d["to"]) for d in disruptions]
    window_start = min(all_from) - timedelta(seconds=window_seconds)
    window_end = max(all_to) + timedelta(seconds=window_seconds)

    ws_str = window_start.isoformat().replace("+00:00", "Z")
    we_str = window_end.isoformat().replace("+00:00", "Z")

    by_source = defaultdict(list)
    for item in items:
        if item.get("source") == "Disruption":
            continue
        if item.get("source") not in CONTEXT_SOURCES:
            continue
        if item["from"] < ws_str or item["from"] > we_str:
            continue

        keys = item.get("locator", {}).get("keys", {})
        node = keys.get("node", "")
        msg = item.get("message", {})
        human = msg.get("humanMessage", "")

        entry = {
            "from": item["from"],
            "level": item.get("level", ""),
            "message": human[:200],
        }
        if node:
            entry["node"] = node

        by_source[item["source"]].append(entry)

    # Post-process specific sources into summaries
    result = {}
    for source, events in by_source.items():
        if source == "OVSVswitchdLog":
            result[source] = summarize_ovs(events)
        elif source == "CloudMetrics":
            result[source] = summarize_cloud_metrics(events)
        elif source == "CPUMonitor":
            result[source] = summarize_cpu(events)
        else:
            # Keep raw events but cap at 20
            result[source] = {
                "count": len(events),
                "events": events[:20],
            }

    return result


def summarize_ovs(events):
    """Summarize OVS vswitchd long poll interval warnings."""
    max_poll_ms = 0
    nodes = defaultdict(lambda: {"count": 0, "max_ms": 0})

    for e in events:
        msg = e["message"]
        node = e.get("node", "unknown")
        nodes[node]["count"] += 1

        if "poll interval" in msg:
            try:
                ms = int(msg.split("long ")[1].split("ms")[0])
                if ms > max_poll_ms:
                    max_poll_ms = ms
                if ms > nodes[node]["max_ms"]:
                    nodes[node]["max_ms"] = ms
            except (IndexError, ValueError):
                pass

    return {
        "count": len(events),
        "max_poll_interval_ms": max_poll_ms,
        "nodes_affected": len(nodes),
        "per_node": {
            node_name(n): v for n, v in sorted(
                nodes.items(), key=lambda x: -x[1]["max_ms"]
            )
        },
    }


def summarize_cloud_metrics(events):
    """Summarize Azure/cloud disk metrics warnings."""
    metrics = defaultdict(lambda: {"count": 0, "max_value": 0.0})

    for e in events:
        msg = e["message"]
        # "Average value of 100.00 for metric OS Disk IOPS Consumed Percentage is over the threshold of 50.00"
        try:
            value = float(msg.split("value of ")[1].split(" for")[0])
            metric_name = msg.split("for metric ")[1].split(" is over")[0]
            metrics[metric_name]["count"] += 1
            if value > metrics[metric_name]["max_value"]:
                metrics[metric_name]["max_value"] = value
        except (IndexError, ValueError):
            pass

    return {
        "count": len(events),
        "metrics": dict(metrics),
    }


def summarize_cpu(events):
    """Summarize CPU monitor warnings."""
    nodes = []
    for e in events:
        msg = e["message"]
        node = ""
        if "on node " in msg:
            node = msg.split("on node ")[1].strip()
        nodes.append({
            "from": e["from"],
            "node": node,
            "node_short": node_name(node),
        })
    return {
        "count": len(events),
        "nodes": nodes,
    }


# ---------------------------------------------------------------------------
# Source-node analysis
# ---------------------------------------------------------------------------

def analyze_source_nodes(disruptions):
    """Detect single-source-node fan-out patterns."""
    if not disruptions:
        return {"pattern": "none", "detail": "No disruptions"}

    # Group by source node
    by_source = defaultdict(list)
    for d in disruptions:
        src = d["source_node"] or "unknown"
        by_source[src].append(d)

    if len(by_source) == 1 and "unknown" not in by_source:
        src = list(by_source.keys())[0]
        targets = set()
        for d in by_source[src]:
            if d["target_node"]:
                targets.add(node_name(d["target_node"]))

        return {
            "pattern": "single-source-fan-out",
            "source_node": node_name(src),
            "source_node_full": src,
            "target_nodes": sorted(targets),
            "target_count": len(targets),
            "disruption_count": len(disruptions),
            "detail": (
                f"All {len(disruptions)} disruptions originate from "
                f"{node_name(src)} hitting {len(targets)} target nodes. "
                f"This indicates a source-side networking issue (OVS/CPU/disk "
                f"pressure on the source node), not a destination or network-wide problem."
            ),
        }

    if "unknown" in by_source and len(by_source) == 1:
        return {
            "pattern": "unknown",
            "detail": "Disruption path does not contain source/target node info",
        }

    return {
        "pattern": "multi-source",
        "source_nodes": {
            node_name(src): len(events)
            for src, events in sorted(by_source.items(), key=lambda x: -len(x[1]))
        },
        "detail": (
            f"Disruptions originate from {len(by_source)} different source nodes. "
            f"This suggests a network-wide or destination-side issue rather than "
            f"a single-node problem."
        ),
    }


# ---------------------------------------------------------------------------
# Summary generation
# ---------------------------------------------------------------------------

def generate_summary(disruptions, network_liveness, concurrent, source_analysis):
    """Generate a high-level summary dict."""
    backends = defaultdict(int)
    for d in disruptions:
        backends[d["backend"]] += 1

    # Determine time range
    time_range = None
    if disruptions:
        first = disruptions[0]["from"]
        last = max(d["to"] for d in disruptions)
        time_range = {"from": first, "to": last}

    # Network liveness assessment
    liveness_status = "clean"
    liveness_detail = "No test infra or cloud network issues"
    total_liveness = sum(v["count"] for v in network_liveness.values())
    if total_liveness > 50:
        liveness_status = "unreliable"
        liveness_detail = (
            f"Massive network-liveness disruption ({total_liveness} events) — "
            f"run's disruption data is unreliable"
        )
    elif total_liveness > 5:
        liveness_status = "degraded"
        liveness_detail = (
            f"Moderate network-liveness disruption ({total_liveness} events) — "
            f"some disruption may be attributable to infra/cloud issues"
        )
    elif total_liveness > 0:
        liveness_status = "minor"
        liveness_detail = f"{total_liveness} minor network-liveness blips — negligible"

    # Key signals from concurrent events
    signals = []
    ovs = concurrent.get("OVSVswitchdLog")
    if ovs and ovs.get("max_poll_interval_ms", 0) > 500:
        signals.append(
            f"OVS vswitchd stalls: {ovs['count']} events, "
            f"max poll interval {ovs['max_poll_interval_ms']}ms on "
            f"{ovs['nodes_affected']} nodes"
        )

    cpu = concurrent.get("CPUMonitor")
    if cpu and cpu.get("count", 0) > 0:
        cpu_nodes = [n["node_short"] for n in cpu.get("nodes", [])]
        signals.append(f"CPU >95%: {', '.join(cpu_nodes)}")

    cloud = concurrent.get("CloudMetrics")
    if cloud:
        iops = cloud.get("metrics", {}).get("OS Disk IOPS Consumed Percentage", {})
        if iops.get("max_value", 0) >= 90:
            signals.append(f"Azure disk IOPS saturated ({iops['max_value']:.0f}%)")
        qdepth = cloud.get("metrics", {}).get("OS Disk Queue Depth", {})
        if qdepth.get("max_value", 0) > 10:
            signals.append(f"Azure disk queue depth {qdepth['max_value']:.1f} (threshold 3.0)")

    etcd = concurrent.get("EtcdLog")
    if etcd and etcd.get("count", 0) > 0:
        signals.append(f"etcd pressure: {etcd['count']} events")

    # Phase breakdown
    phase_counts = defaultdict(int)
    for d in disruptions:
        phase_counts[d.get("phase", "unknown")] += 1

    return {
        "disruption_count": len(disruptions),
        "backends": dict(backends),
        "time_range": time_range,
        "phase_breakdown": dict(phase_counts),
        "network_liveness_status": liveness_status,
        "network_liveness_detail": liveness_detail,
        "source_node_pattern": source_analysis.get("pattern", "unknown"),
        "key_signals": signals,
    }


# ---------------------------------------------------------------------------
# Link generation
# ---------------------------------------------------------------------------

GCSWEB_BASE = "https://gcsweb-ci.apps.ci.l2s4.p1.openshiftapps.com/gcs/test-platform-results/logs"


def generate_links(job_name, build_id, target=None, timeline_files=None):
    """Generate deep links for a job run.

    Returns run-level links (prow, sippy_intervals) and artifact-level links
    (gcsweb deep links to specific files used as evidence).
    """
    if not job_name or not build_id:
        return {}

    gcs_base = f"{GCSWEB_BASE}/{job_name}/{build_id}"
    links = {
        "prow": f"https://prow.ci.openshift.org/view/gs/test-platform-results/logs/{job_name}/{build_id}",
        "sippy_intervals": f"https://sippy.dptools.openshift.org/sippy-ng/job_runs/{build_id}/{job_name}/intervals",
        "gcsweb_artifacts": f"{gcs_base}/artifacts/",
    }

    if target:
        artifact_base = f"{gcs_base}/artifacts/{target}"
        links["gcsweb_timeline_dir"] = f"{artifact_base}/openshift-e2e-test/artifacts/junit/"
        links["gcsweb_audit_logs"] = f"{artifact_base}/gather-extra/artifacts/audit_logs/"
        links["gcsweb_etcd_pods"] = f"{artifact_base}/gather-extra/artifacts/pods/openshift-etcd/"
        links["gcsweb_journal_logs"] = f"{artifact_base}/gather-extra/artifacts/journal_logs/"
        links["gcsweb_must_gather"] = f"{artifact_base}/gather-extra/artifacts/must-gather/"

    # Deep links to the specific timeline files that were parsed
    if timeline_files and target:
        artifact_base = f"{gcs_base}/artifacts/{target}"
        timeline_urls = []
        for tf in timeline_files:
            basename = tf.rsplit("/", 1)[-1] if "/" in tf else tf
            timeline_urls.append(
                f"{artifact_base}/openshift-e2e-test/artifacts/junit/{basename}"
            )
        links["gcsweb_timelines"] = timeline_urls

    return links


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def node_name(full_name):
    """Extract a short but meaningful node suffix.

    For workers: last segment (e.g., 'db64f' from '...-worker-westus-db64f')
    For masters: 'master-N' (e.g., 'master-0' from '...-master-0')
    """
    if not full_name:
        return ""
    if "-master-" in full_name:
        idx = full_name.index("-master-")
        return full_name[idx + 1:]  # 'master-0'
    parts = full_name.rsplit("-", 1)
    return parts[-1] if len(parts) > 1 else full_name


# ---------------------------------------------------------------------------
# Text output
# ---------------------------------------------------------------------------

def format_text(data):
    """Format analysis data as human-readable text."""
    lines = []
    summary = data["summary"]

    # Links
    links = data.get("links", {})
    if links:
        lines.append("Links:")
        if links.get("prow"):
            lines.append(f"  Prow Job:        {links['prow']}")
        if links.get("sippy_intervals"):
            lines.append(f"  Sippy Intervals: {links['sippy_intervals']}")
        if links.get("gcsweb_timelines"):
            for url in links["gcsweb_timelines"]:
                lines.append(f"  Timeline:        {url}")
        if links.get("gcsweb_audit_logs"):
            lines.append(f"  Audit Logs:      {links['gcsweb_audit_logs']}")
        if links.get("gcsweb_etcd_pods"):
            lines.append(f"  etcd Pods:       {links['gcsweb_etcd_pods']}")
        if links.get("gcsweb_artifacts"):
            lines.append(f"  All Artifacts:   {links['gcsweb_artifacts']}")
        lines.append("")

    lines.append(f"Disruptions: {summary['disruption_count']}")
    if summary["time_range"]:
        lines.append(f"Time range: {summary['time_range']['from']} to {summary['time_range']['to']}")
    lines.append(f"Network liveness: {summary['network_liveness_status']} -- {summary['network_liveness_detail']}")
    lines.append(f"Source pattern: {summary['source_node_pattern']}")
    phase = summary.get("phase_breakdown", {})
    if phase:
        parts = [f"{p}: {c}" for p, c in sorted(phase.items())]
        lines.append(f"Phase breakdown: {', '.join(parts)}")
    lines.append("")

    # Backends
    lines.append("Disrupted backends:")
    for backend, count in sorted(summary["backends"].items(), key=lambda x: -x[1]):
        btype = classify_backend(backend)
        lines.append(f"  {backend} ({btype}): {count} disruptions")
    lines.append("")

    # Source node analysis
    sa = data["source_node_analysis"]
    lines.append(f"Source node analysis: {sa['detail']}")
    if sa["pattern"] == "single-source-fan-out":
        lines.append(f"  Source: {sa['source_node_full']}")
        lines.append(f"  Targets: {', '.join(sa['target_nodes'])}")
    lines.append("")

    # Key signals
    if summary["key_signals"]:
        lines.append("Key signals:")
        for sig in summary["key_signals"]:
            lines.append(f"  - {sig}")
        lines.append("")

    # Concurrent events detail
    concurrent = data["concurrent_events"]
    if concurrent:
        lines.append("Concurrent events:")
        for source, detail in sorted(concurrent.items()):
            count = detail.get("count", 0)
            lines.append(f"  {source}: {count} events")

            if source == "OVSVswitchdLog":
                lines.append(f"    Max poll interval: {detail.get('max_poll_interval_ms', 0)}ms")
                lines.append(f"    Nodes affected: {detail.get('nodes_affected', 0)}")
            elif source == "CPUMonitor":
                for n in detail.get("nodes", []):
                    lines.append(f"    {n['from']} | {n['node_short']} (>95%)")
            elif source == "CloudMetrics":
                for metric, info in detail.get("metrics", {}).items():
                    lines.append(f"    {metric}: max {info['max_value']:.1f} ({info['count']} events)")
            else:
                for evt in detail.get("events", [])[:5]:
                    lines.append(f"    {evt['from']} | {evt['level']} | {evt['message'][:120]}")
                remaining = count - min(count, 5)
                if remaining > 0:
                    lines.append(f"    ... and {remaining} more")

    # Network liveness detail
    nl = data["network_liveness"]
    if nl:
        lines.append("")
        lines.append("Network liveness backends:")
        for backend, info in sorted(nl.items()):
            lines.append(
                f"  {backend}: {info['count']} disruptions "
                f"({info['first']} to {info['last']})"
            )

    # Individual disruptions
    disruptions = data["disruptions"]
    if disruptions:
        lines.append("")
        lines.append("Disruption events:")
        for d in disruptions[:50]:
            src = node_name(d["source_node"]) or "?"
            dst = node_name(d["target_node"]) or "?"
            lines.append(
                f"  {d['from']}-{d['to']} | {d['backend']} | "
                f"{d['error_type']} | src={src} dst={dst} ep={d['target_endpoint']} | "
                f"phase={d.get('phase', '?')}"
            )
        if len(disruptions) > 50:
            lines.append(f"  ... and {len(disruptions) - 50} more")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Parse disruption from OpenShift CI interval/timeline JSON files"
    )
    parser.add_argument("files", nargs="+", help="Timeline JSON file paths")
    parser.add_argument(
        "--backends", default=None,
        help="Comma-separated backend name filters (substring match)"
    )
    parser.add_argument(
        "--window", type=int, default=60,
        help="Seconds to expand around disruption window for concurrent events (default: 60)"
    )
    parser.add_argument(
        "--format", choices=["json", "text"], default="text",
        help="Output format (default: text)"
    )
    parser.add_argument(
        "--job-name", default=None,
        help="Prow job name (for generating deep links)"
    )
    parser.add_argument(
        "--build-id", default=None,
        help="Prow build ID (for generating deep links)"
    )
    parser.add_argument(
        "--target", default=None,
        help="CI operator target name, e.g. e2e-azure-ovn-upgrade (for GCS artifact deep links)"
    )

    args = parser.parse_args()
    backend_filter = args.backends.split(",") if args.backends else None

    items = load_items(args.files)
    disruptions = extract_disruptions(items, backend_filter)
    network_liveness = extract_network_liveness(items)
    concurrent = extract_concurrent_events(items, disruptions, args.window)
    source_analysis = analyze_source_nodes(disruptions)
    summary = generate_summary(disruptions, network_liveness, concurrent, source_analysis)
    links = generate_links(args.job_name, args.build_id, args.target, args.files)

    data = {
        "disruptions": disruptions,
        "concurrent_events": concurrent,
        "source_node_analysis": source_analysis,
        "network_liveness": network_liveness,
        "summary": summary,
        "links": links,
    }

    if args.format == "json":
        json.dump(data, sys.stdout, indent=2)
        print()
    else:
        print(format_text(data))


if __name__ == "__main__":
    main()
