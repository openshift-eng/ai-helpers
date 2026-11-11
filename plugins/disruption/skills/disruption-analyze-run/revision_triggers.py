#!/usr/bin/env python3
"""List what triggered each static-pod revision in one or more job runs.

Reads gather-extra events.json and configmaps.json (download them with
`download_timelines.py --gather`). For each run it prints:

- every {namespace}/revision-status-N configmap with its creation time and
  reason (the revision controller records why revision N was created)
- every StartingNewRevision / RevisionTriggered event from the operator, with
  the SecretUpdated / ConfigMapUpdated / *Created events from any namespace
  within --tolerance seconds of it (revision controllers' own copies such as
  config-N are left out). Those writes are the trigger chain: for
  example the authentication operator updating
  openshift-config/webhook-authentication-integrated-oauth, then the
  kube-apiserver operator copying it to openshift-kube-apiserver/webhook-authenticator
  in the same second.
- the operator's own OperatorVersionChanged events. The first change from a
  non-empty version marks the start of the upgrade: revisions before it are
  install-time and hidden unless --all is given. A revision that starts after
  the operator reports its new "operator" version, and is not the upgrade's
  first revision, is tagged [after operator upgrade]: an extra rollout beyond
  the upgrade's own. (Some operators report the new version before their own
  rollout starts, so the first upgrade revision is never tagged.)

With two or more runs it also prints the trigger reasons found in only some
of them (the before/after comparison), using upgrade-time revisions when every
run has an upgrade marker.

Usage:
    python3 revision_triggers.py <build_dir> [<build_dir> ...] \
        [--operator kube-apiserver] [--tolerance 1] [--all] [--format text|json]
    python3 revision_triggers.py --events events.json --configmaps configmaps.json

A build dir is the per-run directory download_timelines.py writes
({output-dir}/{build_id}); the files are read from its gather/ subdirectory,
or from the directory itself.

Caveats: the cluster keeps events for about 3 hours and aggregates repeats
(count > 1 keeps only the first and last time), so early upgrade events can be
missing. The revision controller prunes old revision-status configmaps. Report
what is absent instead of assuming it did not happen.
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime

# operator name -> (operand namespace, operator namespace)
OPERATOR_NAMESPACES = {
    "kube-apiserver": ("openshift-kube-apiserver", "openshift-kube-apiserver-operator"),
    "etcd": ("openshift-etcd", "openshift-etcd-operator"),
    "kube-controller-manager": ("openshift-kube-controller-manager",
                                "openshift-kube-controller-manager-operator"),
    "kube-scheduler": ("openshift-kube-scheduler", "openshift-kube-scheduler-operator"),
}

REVISION_REASONS = ("StartingNewRevision", "RevisionTriggered")
WRITE_REASONS = ("SecretUpdated", "ConfigMapUpdated", "SecretCreated", "ConfigMapCreated")

_REVISION_MSG_RE = re.compile(r'new revision (\d+) triggered by "(.*)"', re.DOTALL)
_VERSION_MSG_RE = re.compile(
    r'clusteroperator/(\S+) version "([^"]*)" changed from "([^"]*)" to "([^"]*)"')


def parse_ts(value):
    if not value:
        return None
    try:
        return datetime.strptime(value[:19], "%Y-%m-%dT%H:%M:%S")
    except ValueError:
        return None


def load_items(path):
    """Items of a Kubernetes List JSON file, or [] with a warning on stderr."""
    try:
        with open(path) as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        print("Warning: cannot read %s: %s" % (path, exc), file=sys.stderr)
        return []
    if isinstance(data, list):
        return data
    return data.get("items", []) or []


def clean_reason(reason):
    """Revision reasons are Go %q strings inside quotes; drop the escaping."""
    return (reason or "").replace('\\"', '"').strip()


def find_gather_file(build_dir, name):
    """Path to {build_dir}/gather/{name} or {build_dir}/{name}, or None."""
    for candidate in (os.path.join(build_dir, "gather", name), os.path.join(build_dir, name)):
        if os.path.isfile(candidate):
            return candidate
    return None


def event_time(event):
    """Last time the event happened (lastTimestamp, else eventTime, else firstTimestamp)."""
    return (event.get("lastTimestamp") or event.get("eventTime")
            or event.get("firstTimestamp") or "")


def event_namespace(event):
    return (event.get("metadata", {}).get("namespace")
            or event.get("involvedObject", {}).get("namespace") or "")


def event_component(event):
    return event.get("source", {}).get("component") or event.get("reportingComponent") or ""


def revision_statuses(configmaps, namespace):
    """revision-status-N configmaps in namespace, sorted by revision."""
    result = []
    for cm in configmaps:
        meta = cm.get("metadata", {})
        name = meta.get("name", "")
        if meta.get("namespace") != namespace or not name.startswith("revision-status-"):
            continue
        suffix = name[len("revision-status-"):]
        if not suffix.isdigit():
            continue
        data = cm.get("data") or {}
        result.append({
            "revision": int(suffix),
            "created": meta.get("creationTimestamp"),
            "reason": clean_reason(data.get("reason", "")),
        })
    result.sort(key=lambda r: r["revision"])
    return result


def _within(event, when, tolerance):
    """True when the event's first or last time is within tolerance seconds of when."""
    for stamp in (event.get("firstTimestamp"), event.get("lastTimestamp"), event.get("eventTime")):
        t = parse_ts(stamp)
        if t is not None and abs((t - when).total_seconds()) <= tolerance:
            return True
    return False


def revision_triggers(events, operator_namespace, tolerance=1):
    """Revision events grouped by revision, each with the writes in the same second.

    Returns a list sorted by revision of {revision, reason, started, triggered,
    writes}. started is the StartingNewRevision time, triggered the
    RevisionTriggered time; writes are WRITE_REASONS events from any namespace
    within tolerance seconds of started (or triggered when started is absent).
    """
    by_revision = {}
    for event in events:
        if event.get("reason") not in REVISION_REASONS:
            continue
        if event_namespace(event) != operator_namespace:
            continue
        match = _REVISION_MSG_RE.search(event.get("message", ""))
        if not match:
            continue
        revision = int(match.group(1))
        entry = by_revision.setdefault(revision, {
            "revision": revision, "reason": clean_reason(match.group(2)),
            "started": None, "triggered": None, "writes": [],
        })
        key = "started" if event["reason"] == "StartingNewRevision" else "triggered"
        entry[key] = event_time(event)

    # Revision controllers copy every input to a numbered name (config-11,
    # webhook-authenticator-10) when a revision starts. Those are effects.
    writes = [e for e in events if e.get("reason") in WRITE_REASONS
              and "revisioncontroller" not in event_component(e)]
    for entry in by_revision.values():
        when = parse_ts(entry["started"] or entry["triggered"])
        if when is None:
            continue
        matched = [e for e in writes if _within(e, when, tolerance)]
        matched.sort(key=event_time)
        entry["writes"] = [{
            "time": event_time(e),
            "namespace": event_namespace(e),
            "reason": e.get("reason"),
            "component": event_component(e),
            "count": e.get("count"),
            "message": (e.get("message") or "").replace("\n", " ")[:300],
        } for e in matched]
    return [by_revision[k] for k in sorted(by_revision)]


def operator_version_changes(events, operator, operator_namespace):
    """OperatorVersionChanged events for clusteroperator/{operator}, sorted by time.

    Each entry has time, name (the version name: operator, raw-internal, ...),
    from, to and message.
    """
    result = []
    for event in events:
        if event.get("reason") != "OperatorVersionChanged":
            continue
        if event_namespace(event) != operator_namespace:
            continue
        message = event.get("message", "")
        match = _VERSION_MSG_RE.search(message)
        if not match or match.group(1) != operator:
            continue
        result.append({"time": event_time(event), "name": match.group(2),
                       "from": match.group(3), "to": match.group(4), "message": message[:300]})
    result.sort(key=lambda e: e["time"])
    return result


def upgrade_markers(versions):
    """(upgrade_started, operator_upgraded) times, or None when not seen.

    upgrade_started is the first version change from a non-empty value (any
    version name; raw-internal changes first). operator_upgraded is the last
    change of the "operator" version from a non-empty value.
    """
    upgrades = [v for v in versions if v["from"]]
    started = upgrades[0]["time"] if upgrades else None
    operator_done = [v["time"] for v in upgrades if v["name"] == "operator"]
    return started, (operator_done[-1] if operator_done else None)


def _phase(when, upgrade_started):
    if not upgrade_started or not when:
        return "unknown"
    return "upgrade" if when >= upgrade_started else "install"


def analyze_run(label, events, configmaps, operator, tolerance):
    namespace, operator_namespace = OPERATOR_NAMESPACES[operator]
    triggers = revision_triggers(events, operator_namespace, tolerance)
    versions = operator_version_changes(events, operator, operator_namespace)
    upgrade_started, operator_upgraded = upgrade_markers(versions)
    first_upgrade_revision = None
    for t in triggers:
        when = t["started"] or t["triggered"]
        t["phase"] = _phase(when, upgrade_started)
        if t["phase"] == "upgrade" and first_upgrade_revision is None:
            first_upgrade_revision = t["revision"]
        t["after_operator_upgrade"] = bool(
            operator_upgraded and when and when >= operator_upgraded
            and t["phase"] == "upgrade" and t["revision"] != first_upgrade_revision)
    statuses = revision_statuses(configmaps, namespace)
    for r in statuses:
        r["phase"] = _phase(r["created"], upgrade_started)
    return {
        "run": label,
        "operator": operator,
        "upgrade_started": upgrade_started,
        "operator_upgraded": operator_upgraded,
        "revision_statuses": statuses,
        "triggers": triggers,
        "operator_version_changes": versions,
        "have_events": bool(events),
        "have_configmaps": bool(configmaps),
    }


def _reasons(run, upgrade_only):
    entries = list(run["triggers"]) + list(run["revision_statuses"])
    return {e["reason"] for e in entries
            if e["reason"] and (not upgrade_only or e["phase"] == "upgrade")}


def compare_runs(runs):
    """Trigger reasons that appear in only some of the runs.

    Uses upgrade-time revisions only when every run has an upgrade marker.
    """
    if len(runs) < 2:
        return []
    upgrade_only = all(r["upgrade_started"] for r in runs)
    all_reasons = set()
    per_run = {}
    for run in runs:
        per_run[run["run"]] = _reasons(run, upgrade_only)
        all_reasons |= per_run[run["run"]]
    result = []
    for reason in sorted(all_reasons):
        present = [r["run"] for r in runs if reason in per_run[r["run"]]]
        if len(present) != len(runs):
            result.append({"reason": reason, "present_in": present,
                           "absent_in": [r["run"] for r in runs if r["run"] not in present]})
    return result


def format_text(runs, differences, show_all=False):
    lines = []
    for run in runs:
        lines.append("== %s (%s)" % (run["run"], run["operator"]))
        if not run["have_configmaps"]:
            lines.append("  configmaps.json missing or empty")
        if not run["have_events"]:
            lines.append("  events.json missing or empty")
        for v in run["operator_version_changes"]:
            if v["name"] in ("operator", "raw-internal") and (show_all or v["from"]):
                lines.append("  %s version %s: %s -> %s" % (
                    v["time"], v["name"], v["from"] or '""', v["to"]))
        if run["have_events"] and not run["upgrade_started"]:
            lines.append("  no upgrade OperatorVersionChanged event (events expire after ~3h); "
                         "showing every revision")
        statuses = [r for r in run["revision_statuses"] if show_all or r["phase"] != "install"]
        hidden = len(run["revision_statuses"]) - len(statuses)
        if statuses or hidden:
            lines.append("  revision-status configmaps:")
            for r in statuses:
                lines.append("    %-4d %s  %s" % (r["revision"], r["created"], r["reason"]))
            if hidden:
                lines.append("    (%d install-time revision%s hidden; --all shows them)"
                             % (hidden, "" if hidden == 1 else "s"))
        triggers = [t for t in run["triggers"] if show_all or t["phase"] != "install"]
        hidden = len(run["triggers"]) - len(triggers)
        if triggers or hidden:
            lines.append("  revision events (writes within the tolerance of StartingNewRevision):")
            if hidden:
                lines.append("    (%d install-time revision%s hidden; --all shows them)"
                             % (hidden, "" if hidden == 1 else "s"))
            for t in triggers:
                tag = " [after operator upgrade]" if t["after_operator_upgrade"] else ""
                lines.append("    revision %d  started %s  triggered %s  %s%s" % (
                    t["revision"], t["started"] or "-", t["triggered"] or "-", t["reason"], tag))
                for w in t["writes"]:
                    lines.append("      %s %s %s (%s): %s" % (
                        w["time"], w["reason"], w["namespace"], w["component"], w["message"]))
        lines.append("")
    if differences:
        lines.append("Trigger reasons not present in every run:")
        for d in differences:
            lines.append("  %s" % d["reason"])
            lines.append("    present in: %s; absent in: %s" % (
                ", ".join(d["present_in"]), ", ".join(d["absent_in"])))
    return "\n".join(lines).rstrip()


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="List static-pod revision triggers from gather-extra events and configmaps")
    parser.add_argument("build_dirs", nargs="*",
                        help="Per-run directories holding gather/events.json and gather/configmaps.json")
    parser.add_argument("--events", help="events.json for a single run (instead of a build dir)")
    parser.add_argument("--configmaps", help="configmaps.json for a single run (instead of a build dir)")
    parser.add_argument("--operator", choices=sorted(OPERATOR_NAMESPACES), default="kube-apiserver",
                        help="Static-pod operator (default: kube-apiserver)")
    parser.add_argument("--tolerance", type=int, default=1,
                        help="Seconds between StartingNewRevision and a matching write (default: 1)")
    parser.add_argument("--all", action="store_true",
                        help="Also show install-time revisions in text output (JSON always has them)")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    args = parser.parse_args(argv)

    inputs = []
    if args.events or args.configmaps:
        inputs.append(("input", args.events, args.configmaps))
    for build_dir in args.build_dirs:
        label = os.path.basename(os.path.normpath(build_dir))
        inputs.append((label, find_gather_file(build_dir, "events.json"),
                       find_gather_file(build_dir, "configmaps.json")))
    if not inputs:
        parser.error("give at least one build dir, or --events/--configmaps")

    runs = []
    for label, events_path, configmaps_path in inputs:
        if not events_path and not configmaps_path:
            print("Warning: %s has neither events.json nor configmaps.json; "
                  "run download_timelines.py --gather first" % label, file=sys.stderr)
        events = load_items(events_path) if events_path else []
        configmaps = load_items(configmaps_path) if configmaps_path else []
        runs.append(analyze_run(label, events, configmaps, args.operator, args.tolerance))

    differences = compare_runs(runs)
    if args.format == "json":
        json.dump({"runs": runs, "differences": differences}, sys.stdout, indent=2)
        print()
    else:
        print(format_text(runs, differences, args.all))
    if not any(r["have_events"] or r["have_configmaps"] for r in runs):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
