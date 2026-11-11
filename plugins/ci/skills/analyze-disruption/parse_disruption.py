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
        "episodes": {"episodes": [...], "waves": [...], ...},
        "revision_rollouts": [...],
        "payloads": {"initial": ..., "target": ..., "source": ..., ...},
        "summary": {...}
    }

Episodes group intervals across the selected backends that overlap or start
within EPISODE_GAP_SECONDS of each other; waves group episodes separated by a
large idle gap (see find_waves). Revision rollouts are the static-pod
NodeInstaller rollouts of kube-apiserver, etcd, kube-controller-manager and
kube-scheduler, with the episodes and waves that fall inside each one.
Payloads come from the prowjob.json beside the timeline files (or --prowjob),
falling back to ../gather/clusterversion.json when the prowjob has no
RELEASE_IMAGE_* env.
"""

import argparse
import json
import os
import re
import sys
from collections import defaultdict
from datetime import datetime, timedelta

# disruption_common is in plugins/ci/lib when the whole plugin is installed, or
# beside the skill directories when a Chai persona lists it in supporting_dirs.
_HERE = os.path.dirname(os.path.abspath(__file__))
# Search beside the skill directory as reached, then beside its resolved target,
# since a symlinked skill directory can sit outside the plugin checkout. abspath
# keeps ".." textual, the way sys.path entries resolve it.
_LIB_PARENTS = list(dict.fromkeys(
    os.path.abspath(os.path.join(base, *rel))
    for base in (_HERE, os.path.realpath(_HERE))
    for rel in (("..", "..", "lib"), ("..",))))
for _parent in _LIB_PARENTS:
    if os.path.isfile(os.path.join(_parent, "disruption_common", "__init__.py")):
        sys.path.insert(0, _parent)
        break
else:
    sys.exit("Error: disruption_common library not found. Install the whole ci plugin, or add "
             "`supporting_dirs: [lib/disruption_common]` to the persona's ci plugin entry. Looked in: %s"
             % ", ".join(_LIB_PARENTS))

from disruption_common.series import expand_backend_selectors  # noqa: E402

# download_timelines.py sits beside this script and reads payloads from
# prowjob.json and clusterversion.json. Add the directory explicitly so the
# import also works under `python3 -I`, which leaves it off sys.path. Without
# it (the parser copied on its own) payloads are reported as unknown.
if _HERE not in sys.path:
    sys.path.append(_HERE)
try:
    from download_timelines import extract_payloads, payload_tag, payloads_from_clusterversion  # noqa: E402
except ImportError:
    extract_payloads = payloads_from_clusterversion = None

    def payload_tag(pullspec):
        return pullspec


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


def backend_matches_filter(backend_name, backend_filter):
    """True when backend_name is one of the exact names backend_filter selects.

    A full connection name matches only itself. A bare base matches only
    `{base}-new-connections` and `{base}-reused-connections`, not localhost,
    http1/http2, service-network, internal-lb, or cache derivatives.
    """
    if not backend_filter:
        return True
    return backend_name in expand_backend_selectors(backend_filter)


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
    sorted_paths = sorted(paths, key=lambda p: os.path.basename(p))
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

        if backend_filter and not backend_matches_filter(backend, backend_filter):
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
# Episodes and waves
# ---------------------------------------------------------------------------

# Intervals on the selected backends that overlap, or start within this many
# seconds of the current episode's end, belong to one episode. The probes of
# one outage start within a second of each other and often continue as
# back-to-back intervals, while separate outages (one master after another in
# a static-pod rollout) are minutes apart.
EPISODE_GAP_SECONDS = 30

# A new wave starts where the idle time between two episodes exceeds twice the
# typical (lower median) idle time, clamped to this range. Gaps under the
# minimum never split; gaps over the maximum always do. One kube-apiserver
# rollout gives ~3 minutes between masters; two rollouts are 10+ minutes apart.
WAVE_GAP_MIN_SECONDS = 300
WAVE_GAP_MAX_SECONDS = 600
WAVE_GAP_FACTOR = 2


def _seconds(start, end):
    return int((parse_ts(end) - parse_ts(start)).total_seconds())


def _lower_median(values):
    ordered = sorted(values)
    return ordered[(len(ordered) - 1) // 2]


def find_episodes(disruptions, gap_seconds=EPISODE_GAP_SECONDS):
    """Group disruption intervals across backends into episodes.

    Returns a list of dicts with 1-based index, from, to, duration_seconds,
    backends (sorted), interval_count, and phases.
    """
    episodes = []
    for d in sorted(disruptions, key=lambda x: (x["from"], x["to"])):
        d_from, d_to = parse_ts(d["from"]), parse_ts(d["to"])
        if episodes and d_from <= episodes[-1]["_to"] + timedelta(seconds=gap_seconds):
            ep = episodes[-1]
            if d_to > ep["_to"]:
                ep["_to"] = d_to
                ep["to"] = d["to"]
        else:
            ep = {"from": d["from"], "to": d["to"], "_to": d_to,
                  "_backends": set(), "_phases": set(), "interval_count": 0}
            episodes.append(ep)
        ep["_backends"].add(d["backend"])
        ep["_phases"].add(d.get("phase", "unknown"))
        ep["interval_count"] += 1

    result = []
    for idx, ep in enumerate(episodes, 1):
        result.append({
            "index": idx,
            "from": ep["from"],
            "to": ep["to"],
            "duration_seconds": _seconds(ep["from"], ep["to"]),
            "backends": sorted(ep["_backends"]),
            "interval_count": ep["interval_count"],
            "phases": sorted(ep["_phases"]),
        })
    return result


def find_waves(episodes):
    """Group consecutive episodes into waves separated by a large idle gap.

    Returns (waves, split_threshold_seconds). Each wave has a 1-based index,
    episode_indices, from, to, median_spacing_seconds (start to start inside
    the wave, None for one episode), gap_before_seconds (idle time since the
    previous wave ended) and start_spacing_before_seconds (previous wave start
    to this wave start).
    """
    if not episodes:
        return [], None
    idle = [_seconds(a["to"], b["from"]) for a, b in zip(episodes, episodes[1:])]
    threshold = None
    if idle:
        threshold = WAVE_GAP_FACTOR * _lower_median(idle)
        threshold = max(WAVE_GAP_MIN_SECONDS, min(WAVE_GAP_MAX_SECONDS, threshold))

    groups = [[episodes[0]]]
    for gap, ep in zip(idle, episodes[1:]):
        if gap > threshold:
            groups.append([ep])
        else:
            groups[-1].append(ep)

    waves = []
    for idx, group in enumerate(groups, 1):
        spacings = [_seconds(a["from"], b["from"]) for a, b in zip(group, group[1:])]
        wave = {
            "index": idx,
            "episode_indices": [ep["index"] for ep in group],
            "from": group[0]["from"],
            "to": group[-1]["to"],
            "median_spacing_seconds": _lower_median(spacings) if spacings else None,
            "gap_before_seconds": None,
            "start_spacing_before_seconds": None,
        }
        if waves:
            wave["gap_before_seconds"] = _seconds(waves[-1]["to"], wave["from"])
            wave["start_spacing_before_seconds"] = _seconds(waves[-1]["from"], wave["from"])
        waves.append(wave)
    return waves, threshold


def analyze_episodes(disruptions):
    """Episodes and waves for the selected disruptions, as one JSON-ready dict."""
    episodes = find_episodes(disruptions)
    waves, threshold = find_waves(episodes)
    return {
        "episodes": episodes,
        "waves": waves,
        "episode_gap_seconds": EPISODE_GAP_SECONDS,
        "wave_split_threshold_seconds": threshold,
    }


def _fmt_minutes(seconds):
    """Compact duration: 45s, 3.4m, 19m."""
    if seconds is None:
        return "?"
    if seconds < 60:
        return "%ds" % seconds
    minutes = seconds / 60.0
    if minutes < 10:
        return "%.1fm" % minutes
    return "%dm" % round(minutes)


def describe_episodes(episode_data):
    """One-line episode/wave description, e.g. '6 episodes in 2 waves (3+3), wave gap 12m (starts 20m apart)'."""
    episodes = episode_data.get("episodes") or []
    waves = episode_data.get("waves") or []
    if not episodes:
        return ""
    n = len(episodes)
    text = "%d episode%s" % (n, "" if n == 1 else "s")
    if n == 1:
        return text
    if len(waves) == 1:
        spacing = waves[0].get("median_spacing_seconds")
        return "%s in 1 wave, ~%s apart" % (text, _fmt_minutes(spacing))
    sizes = "+".join(str(len(w["episode_indices"])) for w in waves)
    gaps = [w["gap_before_seconds"] for w in waves[1:]]
    starts = [w["start_spacing_before_seconds"] for w in waves[1:]]
    text += " in %d waves (%s), wave gap %s (starts %s apart)" % (
        len(waves), sizes,
        "/".join(_fmt_minutes(g) for g in gaps),
        "/".join(_fmt_minutes(s) for s in starts))
    return text


# ---------------------------------------------------------------------------
# Static-pod revision rollouts
# ---------------------------------------------------------------------------

# Operators that roll out static pods one master at a time through node
# installers. Their OperatorState Progressing intervals carry messages like
# "NodeInstallerProgressing: 3 nodes are at revision 6; 0 nodes have achieved
# new revision 7".
STATIC_POD_OPERATORS = ("kube-apiserver", "etcd", "kube-controller-manager", "kube-scheduler")
STATIC_POD_SHORT = {
    "kube-apiserver": "KAS",
    "etcd": "etcd",
    "kube-controller-manager": "KCM",
    "kube-scheduler": "sched",
}

_AT_REVISION_RE = re.compile(r"(\d+) nodes? (?:is|are) at revision (\d+)")
_NEW_REVISION_RE = re.compile(r"(\d+) nodes? ha(?:s|ve) achieved new revision (\d+)")

# An episode counts as inside a rollout when it overlaps the rollout's
# Progressing interval widened by this much on each side. The interval ends
# when Progressing goes False, which can lag the last master by a few seconds,
# or lead a disruption that the probe records late.
ROLLOUT_SLACK_SECONDS = 15


def parse_revision_message(message):
    """Return (from_revision, to_revision) from a NodeInstaller message, or None."""
    at = [int(rev) for _count, rev in _AT_REVISION_RE.findall(message or "")]
    new = [int(rev) for _count, rev in _NEW_REVISION_RE.findall(message or "")]
    if new:
        revisions = at or new
        return min(revisions), max(new)
    if len(set(at)) > 1:
        return min(at), max(at)
    return None


def extract_revision_rollouts(items):
    """Extract static-pod revision rollouts from OperatorState intervals.

    Consecutive intervals for the same operator and target revision that
    touch or overlap are merged into one rollout. Returns rollouts sorted by
    start, each with operator, from_revision, to_revision, from, to,
    duration_seconds and message.
    """
    raw = []
    seen = set()
    for item in items:
        if item.get("source") == "Disruption":
            continue
        keys = item.get("locator", {}).get("keys", {})
        operator = keys.get("clusteroperator", "")
        if operator not in STATIC_POD_OPERATORS:
            continue
        human = item.get("message", {}).get("humanMessage", "")
        if "revision" not in human:
            continue
        revisions = parse_revision_message(human)
        if not revisions:
            continue
        key = (operator, item["from"], item.get("to", item["from"]), revisions)
        if key in seen:
            continue
        seen.add(key)
        raw.append({
            "operator": operator,
            "from_revision": revisions[0],
            "to_revision": revisions[1],
            "from": item["from"],
            "to": item.get("to", item["from"]),
            "message": human.split("\n", 1)[0][:200],
        })

    raw.sort(key=lambda r: (r["operator"], r["from"]))
    merged = []
    for r in raw:
        prev = merged[-1] if merged else None
        if (prev and prev["operator"] == r["operator"]
                and prev["to_revision"] == r["to_revision"]
                and parse_ts(r["from"]) <= parse_ts(prev["to"])):
            if parse_ts(r["to"]) > parse_ts(prev["to"]):
                prev["to"] = r["to"]
            prev["from_revision"] = min(prev["from_revision"], r["from_revision"])
            continue
        merged.append(dict(r))

    for r in merged:
        r["duration_seconds"] = _seconds(r["from"], r["to"])
    merged.sort(key=lambda r: (r["from"], r["operator"]))
    return merged


def link_rollouts_to_episodes(rollouts, episode_data, slack_seconds=ROLLOUT_SLACK_SECONDS):
    """Record which episodes and waves fall inside each rollout.

    Adds episode_indices and waves (list of {wave, episodes_inside,
    episodes_in_wave}) to each rollout, and rollouts (list of short labels)
    to each wave. Mutates and returns the rollouts list.
    """
    episodes = episode_data.get("episodes") or []
    waves = episode_data.get("waves") or []
    wave_of = {}
    for w in waves:
        w.setdefault("rollouts", [])
        for idx in w["episode_indices"]:
            wave_of[idx] = w

    slack = timedelta(seconds=slack_seconds)
    for r in rollouts:
        r_from = parse_ts(r["from"]) - slack
        r_to = parse_ts(r["to"]) + slack
        inside = [ep["index"] for ep in episodes
                  if parse_ts(ep["from"]) <= r_to and parse_ts(ep["to"]) >= r_from]
        r["episode_indices"] = inside
        r["waves"] = []
        for w in waves:
            count = sum(1 for idx in inside if wave_of.get(idx) is w)
            if not count:
                continue
            r["waves"].append({
                "wave": w["index"],
                "episodes_inside": count,
                "episodes_in_wave": len(w["episode_indices"]),
            })
            w["rollouts"].append("%s %d->%d (%d/%d)" % (
                r["operator"], r["from_revision"], r["to_revision"],
                count, len(w["episode_indices"])))
    return rollouts


def describe_rollouts(rollouts, short=True):
    """Compact rollout list for the summary line.

    Rollouts that contain disruption episodes are listed with their wave
    coverage; the rest are counted.
    """
    if not rollouts:
        return ""
    parts = []
    quiet = 0
    for r in rollouts:
        if not r.get("episode_indices"):
            quiet += 1
            continue
        name = STATIC_POD_SHORT.get(r["operator"], r["operator"]) if short else r["operator"]
        coverage = ",".join("w%d %d/%d" % (w["wave"], w["episodes_inside"], w["episodes_in_wave"])
                            for w in r.get("waves", []))
        parts.append("%s %d->%d (%s)" % (name, r["from_revision"], r["to_revision"], coverage))
    if quiet:
        parts.append("+%d without disruption" % quiet)
    return ", ".join(parts)


# ---------------------------------------------------------------------------
# Payloads
# ---------------------------------------------------------------------------

_WORKING_TOWARDS_RE = re.compile(r"Working towards (\S+?):?(?:\s|$)")


def extract_timeline_target_version(items):
    """Version the cluster upgraded to, from ClusterVersion 'Working towards X' intervals."""
    for item in sorted(items, key=lambda i: i.get("from", "")):
        keys = item.get("locator", {}).get("keys", {})
        if "clusterversion" not in keys:
            continue
        match = _WORKING_TOWARDS_RE.search(item.get("message", {}).get("humanMessage", ""))
        if match:
            return match.group(1)
    return None


def find_payloads(timeline_files, items, prowjob_path=None):
    """Initial and target payload for the run.

    Reads prowjob.json (explicit path, or the one download_timelines.py saved
    beside the timelines) and falls back to gather/clusterversion.json history.
    Always adds timeline_target_version from the timeline itself.
    """
    payloads = {"initial": None, "target": None, "source": None}
    if extract_payloads is None:
        payloads["warning"] = "download_timelines.py not found beside parse_disruption.py"
        payloads["timeline_target_version"] = extract_timeline_target_version(items)
        return payloads
    logs_dir = os.path.dirname(os.path.abspath(timeline_files[0])) if timeline_files else None
    if not prowjob_path and logs_dir:
        candidate = os.path.join(logs_dir, "prowjob.json")
        if os.path.isfile(candidate):
            prowjob_path = candidate
    if prowjob_path:
        payloads.update(extract_payloads(prowjob_path))
    if not payloads.get("target") and logs_dir:
        cv_path = os.path.join(logs_dir, "..", "gather", "clusterversion.json")
        if os.path.isfile(cv_path):
            from_cv = payloads_from_clusterversion(cv_path)
            if from_cv.get("target"):
                payloads.update(from_cv)
    payloads["timeline_target_version"] = extract_timeline_target_version(items)
    return payloads


def describe_payloads(payloads):
    """'initial -> target' using tags, or '' when nothing is known."""
    if not payloads:
        return ""
    initial = payload_tag(payloads.get("initial"))
    target = payload_tag(payloads.get("target")) or payloads.get("timeline_target_version")
    if not initial and not target:
        return ""
    return "%s -> %s" % (initial or "?", target or "?")


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

    # Build per-disruption windows so we catch events that started before
    # a window but still overlapped, and avoid pulling in unrelated events
    # from gaps between non-contiguous disruptions.
    disruption_windows = []
    for d in disruptions:
        d_from = parse_ts(d["from"])
        d_to = parse_ts(d["to"])
        disruption_windows.append((
            d_from - timedelta(seconds=window_seconds),
            d_to + timedelta(seconds=window_seconds),
        ))

    seen = set()
    by_source = defaultdict(list)
    for item in items:
        source = item.get("source")
        if source == "Disruption":
            continue
        if source not in CONTEXT_SOURCES:
            continue

        item_from = parse_ts(item["from"])
        item_to = parse_ts(item.get("to", item["from"]))

        # Check if this item overlaps any per-disruption window
        overlaps = False
        for win_start, win_end in disruption_windows:
            if item_from <= win_end and item_to >= win_start:
                overlaps = True
                break
        if not overlaps:
            continue

        # Deduplicate by (source, from, locator keys, message snippet) so
        # distinct records from different locators at the same second are kept.
        loc_keys = tuple(sorted(item.get("locator", {}).get("keys", {}).items()))
        dedup_key = (item.get("source"), item["from"], loc_keys,
                     item.get("message", {}).get("humanMessage", "")[:80])
        if dedup_key in seen:
            continue
        seen.add(dedup_key)

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
        if source == "E2ETest":
            test_name = keys.get("e2e-test", "")
            if test_name:
                entry["test_name"] = test_name

        by_source[source].append(entry)

    # Post-process specific sources into summaries
    result = {}
    for source, events in by_source.items():
        if source == "OVSVswitchdLog":
            result[source] = summarize_ovs(events)
        elif source == "CloudMetrics":
            result[source] = summarize_cloud_metrics(events)
        elif source == "CPUMonitor":
            result[source] = summarize_cpu(events)
        elif source == "E2ETest":
            result[source] = summarize_e2e_tests(events)
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


def summarize_e2e_tests(events):
    """Summarize E2ETest events active during disruption.

    Tracks both passed and failed tests. "Passed" includes any non-Error level
    (Info and Warning). Passed tests that consistently appear during disruption
    across runs may be causing the resource pressure that triggers disruption.
    Failed tests (Error level) are usually victims.
    """
    tests = {}
    for e in events:
        name = e.get("test_name", "")
        if not name:
            continue
        if name not in tests:
            tests[name] = {"level": e["level"], "from": e["from"]}
        elif e["level"] == "Error":
            tests[name]["level"] = "Error"

    failed = sorted(n for n, t in tests.items() if t["level"] == "Error")
    passed = sorted(n for n, t in tests.items() if t["level"] != "Error")

    return {
        "count": len(events),
        "failed_tests": failed,
        "passed_tests": passed,
        "tests": tests,
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

def generate_summary(disruptions, network_liveness, concurrent, source_analysis,
                     episode_data=None, rollouts=None):
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

    # More than one kube-apiserver rollout doubles the localhost-probe outages.
    kas = [r for r in (rollouts or []) if r["operator"] == "kube-apiserver"]
    if len(kas) > 1:
        signals.append("%d kube-apiserver revision rollouts (%s)" % (
            len(kas), ", ".join("%d->%d" % (r["from_revision"], r["to_revision"]) for r in kas)))

    # Phase breakdown
    phase_counts = defaultdict(int)
    for d in disruptions:
        phase_counts[d.get("phase", "unknown")] += 1

    episode_data = episode_data or {}
    return {
        "disruption_count": len(disruptions),
        "episode_count": len(episode_data.get("episodes") or []),
        "wave_count": len(episode_data.get("waves") or []),
        "episode_summary": describe_episodes(episode_data),
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

GCSWEB_BASE = "https://gcsweb-ci.apps.ci.l2s4.p1.openshiftapps.com/gcs/test-platform-results-public/logs"


def generate_links(job_name, build_id, target=None, timeline_files=None):
    """Generate deep links for a job run.

    Returns run-level links (prow, sippy_intervals) and artifact-level links
    (gcsweb deep links to specific files used as evidence).
    """
    if not job_name or not build_id:
        return {}

    gcs_base = f"{GCSWEB_BASE}/{job_name}/{build_id}"
    links = {
        "prow": f"https://prow.ci.openshift.org/view/gs/test-platform-results-public/logs/{job_name}/{build_id}",
        "sippy_intervals": f"https://sippy.dptools.openshift.org/sippy-ng/job_runs/{build_id}/{job_name}/intervals",
        "gcsweb_artifacts": f"{gcs_base}/artifacts/",
    }

    if target:
        artifact_base = f"{gcs_base}/artifacts/{target}"
        links["gcsweb_timeline_dir"] = f"{artifact_base}/openshift-e2e-test/artifacts/junit/"
        links["gcsweb_audit_logs"] = f"{artifact_base}/gather-extra/artifacts/audit_logs/"
        links["gcsweb_etcd_pods"] = f"{artifact_base}/gather-extra/artifacts/pods/openshift-etcd/"
        links["gcsweb_journal_logs"] = f"{artifact_base}/gather-extra/artifacts/nodes/"
        links["gcsweb_must_gather"] = f"{artifact_base}/gather-must-gather/artifacts/"

    # Deep links to the specific timeline files that were parsed
    if timeline_files and target:
        artifact_base = f"{gcs_base}/artifacts/"
        timeline_urls = []
        for tf in timeline_files:
            # Preserve the original artifact-relative path rather than using
            # just the basename.  The local file path typically contains an
            # "/artifacts/" segment mirroring the GCS layout; extract everything
            # after it.  Fall back to a flat junit/ path if the marker is absent.
            marker = "/artifacts/"
            idx = tf.find(marker)
            if idx >= 0:
                rel_path = tf[idx + len(marker):]
            else:
                basename = tf.rsplit("/", 1)[-1] if "/" in tf else tf
                rel_path = f"{target}/openshift-e2e-test/artifacts/junit/{basename}"
            timeline_urls.append(f"{artifact_base}{rel_path}")
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

def format_blast_radius(all_disruptions, backend_filter):
    """Summarize all disrupted backends NOT covered by the --backends filter."""
    by_backend = defaultdict(int)
    for d in all_disruptions:
        if backend_matches_filter(d["backend"], backend_filter):
            continue
        by_backend[d["backend"]] += 1

    if not by_backend:
        return None

    backends = sorted(
        [{"backend": b, "type": classify_backend(b), "count": c}
         for b, c in by_backend.items()],
        key=lambda x: -x["count"],
    )
    compact_parts = [f"{e['backend']}:{e['count']}" for e in backends[:10]]
    if len(backends) > 10:
        compact_parts.append(f"+{len(backends) - 10} more")

    return {
        "backends": backends,
        "backend_count": len(backends),
        "total_count": sum(by_backend.values()),
        "compact": " ".join(compact_parts),
    }


def format_summary(data):
    """Format analysis data as a concise one-line summary.

    Example output:
      3 disruptions | host-to-host:3 | OVS:2 (max 1200ms) | etcd:5 | CPU: master-0 | net-liveness: clean | phase: upgrade:2,conformance:1
    """
    summary = data["summary"]
    concurrent = data["concurrent_events"]
    parts = []

    count = summary["disruption_count"]
    parts.append(f"{count} disruption{'s' if count != 1 else ''}")

    episodes_text = summary.get("episode_summary")
    if episodes_text:
        parts.append(episodes_text)

    backends = summary.get("backends", {})
    if backends:
        merged = {}
        for name, cnt in backends.items():
            short = name
            for suffix in ("-new-connections", "-reused-connections"):
                if short.endswith(suffix):
                    short = short[: -len(suffix)]
                    break
            merged[short] = merged.get(short, 0) + cnt
        backend_parts = [f"{s}:{c}" for s, c in sorted(merged.items(), key=lambda x: -x[1])]
        parts.append(" ".join(backend_parts))

    ovs = concurrent.get("OVSVswitchdLog")
    if ovs and ovs.get("count", 0) > 0:
        max_ms = ovs.get("max_poll_interval_ms", 0)
        parts.append(f"OVS:{ovs['count']} (max {max_ms}ms)")

    etcd = concurrent.get("EtcdLog")
    if etcd and etcd.get("count", 0) > 0:
        parts.append(f"etcd:{etcd['count']}")

    cpu = concurrent.get("CPUMonitor")
    if cpu and cpu.get("count", 0) > 0:
        nodes = [n["node_short"] for n in cpu.get("nodes", []) if n.get("node_short")]
        unique_nodes = list(dict.fromkeys(nodes))
        if unique_nodes:
            parts.append(f"CPU: {','.join(unique_nodes[:3])}")
        else:
            parts.append(f"CPU:{cpu['count']}")

    cloud = concurrent.get("CloudMetrics")
    if cloud and cloud.get("count", 0) > 0:
        metrics_parts = []
        for metric, info in cloud.get("metrics", {}).items():
            short_metric = metric.replace("OS Disk ", "").replace(" Consumed Percentage", "%")
            metrics_parts.append(f"{short_metric}:{info['max_value']:.0f}")
        if metrics_parts:
            parts.append(f"cloud: {','.join(metrics_parts)}")

    sa = data.get("source_node_analysis", {})
    pattern = sa.get("pattern", "unknown")
    if pattern == "single-source-fan-out":
        src = sa.get("source_node", "?")
        parts.append(f"src-node: {src}")

    liveness = summary.get("network_liveness_status", "clean")
    if liveness != "clean":
        parts.append(f"net-liveness: {liveness}")

    phase = summary.get("phase_breakdown", {})
    if phase:
        phase_parts = [f"{p}:{c}" for p, c in sorted(phase.items())]
        parts.append(f"phase: {','.join(phase_parts)}")

    rollouts_text = describe_rollouts(data.get("revision_rollouts") or [])
    if rollouts_text:
        parts.append(f"rollouts: {rollouts_text}")

    payload_text = describe_payloads(data.get("payloads"))
    if payload_text:
        parts.append(f"payload: {payload_text}")

    return " | ".join(parts)


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
    if summary.get("episode_summary"):
        lines.append(f"Episodes: {summary['episode_summary']}")
    if summary["time_range"]:
        lines.append(f"Time range: {summary['time_range']['from']} to {summary['time_range']['to']}")
    payloads = data.get("payloads") or {}
    payload_text = describe_payloads(payloads)
    if payload_text:
        source = payloads.get("source") or "timeline"
        lines.append(f"Payloads: {payload_text} (from {source})")
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

    # Episodes and waves
    episode_data = data.get("episodes") or {}
    if episode_data.get("episodes"):
        wave_of = {}
        for w in episode_data.get("waves", []):
            for idx in w["episode_indices"]:
                wave_of[idx] = w["index"]
        lines.append("Disruption episodes (intervals within %ss merged across backends):"
                     % episode_data.get("episode_gap_seconds"))
        for ep in episode_data["episodes"]:
            lines.append(
                f"  #{ep['index']} wave {wave_of.get(ep['index'], '?')} | {ep['from']}-{ep['to']} "
                f"({ep['duration_seconds']}s) | {len(ep['backends'])} backends, "
                f"{ep['interval_count']} intervals | phase={','.join(ep['phases'])}"
            )
        for w in episode_data.get("waves", []):
            gap = ""
            if w.get("gap_before_seconds") is not None:
                gap = (f", {_fmt_minutes(w['gap_before_seconds'])} after previous wave "
                       f"(starts {_fmt_minutes(w['start_spacing_before_seconds'])} apart)")
            spacing = ""
            if w.get("median_spacing_seconds") is not None:
                spacing = f", episodes ~{_fmt_minutes(w['median_spacing_seconds'])} apart"
            inside = w.get("rollouts") or []
            lines.append(
                f"  Wave {w['index']}: episodes {','.join(str(i) for i in w['episode_indices'])} "
                f"{w['from']}-{w['to']}{spacing}{gap}"
                + (f" | inside {'; '.join(inside)}" if inside else " | inside no static-pod rollout")
            )
        lines.append("")

    # Static-pod revision rollouts
    rollouts = data.get("revision_rollouts") or []
    if rollouts:
        lines.append("Static-pod revision rollouts (OperatorState NodeInstallerProgressing):")
        for r in rollouts:
            eps = r.get("episode_indices") or []
            where = f"episodes {','.join(str(i) for i in eps)}" if eps else "no disruption episodes"
            lines.append(
                f"  {r['operator']} {r['from_revision']}->{r['to_revision']} | "
                f"{r['from']}-{r['to']} ({_fmt_minutes(r['duration_seconds'])}) | {where}"
            )
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
            elif source == "E2ETest":
                failed = detail.get("failed_tests", [])
                passed = detail.get("passed_tests", [])
                if failed:
                    lines.append(f"    Failed ({len(failed)}):")
                    for t in failed[:10]:
                        lines.append(f"      - {t}")
                    if len(failed) > 10:
                        lines.append(f"      ... and {len(failed) - 10} more")
                if passed:
                    lines.append(f"    Passed ({len(passed)}):")
                    for t in passed[:5]:
                        lines.append(f"      - {t}")
                    if len(passed) > 5:
                        lines.append(f"      ... and {len(passed) - 5} more")
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
        "--format", choices=["json", "text", "summary"], default="text",
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
    parser.add_argument(
        "--blast-radius", action="store_true",
        help="Append a compact list of ALL disrupted backends (ignoring --backends filter)"
    )
    parser.add_argument(
        "--prowjob", default=None,
        help="prowjob.json for the initial/target payloads (default: prowjob.json beside the timelines)"
    )

    args = parser.parse_args()
    backend_filter = args.backends.split(",") if args.backends else None

    items = load_items(args.files)
    disruptions = extract_disruptions(items, backend_filter)
    network_liveness = extract_network_liveness(items)
    concurrent = extract_concurrent_events(items, disruptions, args.window)
    source_analysis = analyze_source_nodes(disruptions)
    episode_data = analyze_episodes(disruptions)
    rollouts = link_rollouts_to_episodes(extract_revision_rollouts(items), episode_data)
    payloads = find_payloads(args.files, items, args.prowjob)
    summary = generate_summary(disruptions, network_liveness, concurrent, source_analysis,
                               episode_data, rollouts)
    links = generate_links(args.job_name, args.build_id, args.target, args.files)

    blast_radius = None
    if args.blast_radius and not backend_filter:
        print("Warning: --blast-radius has no effect without --backends", file=sys.stderr)
    elif args.blast_radius and backend_filter:
        all_disruptions = extract_disruptions(items, backend_filter=None)
        blast_radius = format_blast_radius(all_disruptions, backend_filter)

    data = {
        "disruptions": disruptions,
        "concurrent_events": concurrent,
        "source_node_analysis": source_analysis,
        "network_liveness": network_liveness,
        "episodes": episode_data,
        "revision_rollouts": rollouts,
        "payloads": payloads,
        "summary": summary,
        "links": links,
    }
    if blast_radius is not None:
        data["blast_radius"] = blast_radius

    if args.format == "json":
        json.dump(data, sys.stdout, indent=2)
        print()
    elif args.format == "summary":
        prefix = ""
        if args.build_id:
            prefix = f"{args.build_id}: "
        line = prefix + format_summary(data)
        if blast_radius:
            line += " | other: " + blast_radius["compact"]
        print(line)
    else:
        print(format_text(data))
        if blast_radius:
            print()
            print("Other disrupted backends (blast radius):")
            for entry in blast_radius["backends"]:
                print(f"  {entry['backend']} ({entry['type']}): {entry['count']}")
            print(f"  Total: {blast_radius['total_count']} disruptions across {blast_radius['backend_count']} backends")


if __name__ == "__main__":
    main()
