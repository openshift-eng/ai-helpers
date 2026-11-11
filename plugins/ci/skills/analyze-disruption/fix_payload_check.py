"""Check whether disruption stopped after a fix payload.

Groups runs by the payload they tested (release_tag) and compares the runs
before and after the first payload with the fix. Payloads are ordered by the
timestamp in the tag, so 5.1.0-0.nightly-2026-11-06-043907 sorts by
2026-11-06 04:39:07.

Input is either file:
- disruption-trend's runs file (--runs-out). It has every run, including runs
  with 0s, so the disrupted share per payload day is meaningful. Prefer it.
- find_disruption_runs.py --format json. It lists only runs with disruption,
  so only the signature counts are meaningful.

Usage:
    python3 ../disruption-trend/disruption_series.py --alert-text "<alert>" --days 30 \
        --runs-out runs.json --format json > /dev/null
    python3 fix_payload_check.py --runs runs.json --fix-payload 5.1.0-0.nightly-2026-11-06-043907
    python3 fix_payload_check.py --runs runs.json --fix-payload <tag> \
        --timelines-dir .work/disruption-analysis/<date> --backends <names> --signature 'roundtrip=15'
"""
import argparse
import datetime
import glob
import json
import math
import os
import re
import sys

from parse_disruption import backend_matches_filter, load_items

_TAG_TIME = re.compile(r"(\d{4}-\d{2}-\d{2}-\d{6})$")


def payload_time(tag):
    """Build time encoded at the end of a payload tag, or None."""
    match = _TAG_TIME.search(tag or "")
    if not match:
        return None
    return datetime.datetime.strptime(match.group(1), "%Y-%m-%d-%H%M%S")


def normalize_run(run):
    """(prow_id, seconds, release_tag, liveness_unreliable) from either input format.

    seconds is None when the run has no disruption data.
    """
    if "disruption_backends" in run:
        entries = run.get("disruption_backends") or []
        tag = next((e.get("release_tag") for e in entries if e.get("release_tag")), "")
        return str(run.get("prow_id", "")), run.get("disruption_seconds"), tag, False
    return (str(run.get("prow_id", "")), run.get("seconds"), run.get("release_tag") or "",
            bool(run.get("liveness_unreliable")))


def percentile(values, pct):
    """Nearest-rank percentile; 0 for no values."""
    if not values:
        return 0
    ordered = sorted(values)
    return ordered[max(0, math.ceil(pct / 100.0 * len(ordered)) - 1)]


def scan_signature(timelines_dir, pattern, backends):
    """Build IDs under timelines_dir whose disruption messages on backends match pattern.

    Returns (matched, scanned). The layout is download_timelines.py's:
    <timelines_dir>/<build_id>/logs/e2e-timelines_spyglass_*.json.
    """
    regex = re.compile(pattern)
    matched, scanned = set(), set()
    for logs in sorted(glob.glob(os.path.join(timelines_dir, "*", "logs"))):
        files = glob.glob(os.path.join(logs, "e2e-timelines_spyglass_*.json"))
        if not files:
            continue
        build_id = os.path.basename(os.path.dirname(logs))
        scanned.add(build_id)
        try:
            items = load_items(files)
        except (OSError, ValueError) as err:
            print("Warning: skipping %s: %s" % (build_id, err), file=sys.stderr)
            scanned.discard(build_id)
            continue
        if any(_matches(item, regex, backends) for item in items):
            matched.add(build_id)
    return matched, scanned


def _matches(item, regex, backends):
    """A disruption Error/Warning interval on backends whose full message matches."""
    if item.get("source") != "Disruption" or item.get("level") not in ("Error", "Warning"):
        return False
    backend = item.get("locator", {}).get("keys", {}).get("backend-disruption-name", "")
    if not backend or not backend_matches_filter(backend, backends):
        return False
    return bool(regex.search(item.get("message", {}).get("humanMessage", "")))


def _summary(runs, signature_ids, scanned_ids=None):
    seconds = [r["seconds"] for r in runs]
    summary = {
        "runs": len(runs),
        "disrupted": sum(1 for s in seconds if s > 0),
        "p95_seconds": percentile(seconds, 95),
        "max_seconds": max(seconds) if seconds else 0,
    }
    if signature_ids is not None:
        summary["signature"] = sum(1 for r in runs if r["prow_id"] in signature_ids)
    if scanned_ids is not None:
        summary["timelines"] = sum(1 for r in runs if r["prow_id"] in scanned_ids)
    return summary


def check_fix(runs, fix_payload, signature_ids=None, scanned_ids=None):
    """Split runs at the fix payload. scanned_ids, when given, are the runs whose
    timelines were searched for the signature; the others count as unknown."""
    fix_time = payload_time(fix_payload)
    if fix_time is None:
        raise ValueError("cannot read a timestamp from payload %r" % fix_payload)
    finder_input = any("disruption_backends" in run for run in runs)
    by_day, before, after = {}, [], []
    no_data = untagged = liveness = 0
    for raw in runs:
        prow_id, seconds, tag, unreliable = normalize_run(raw)
        if seconds is None:
            no_data += 1
            continue
        if unreliable:
            liveness += 1
            continue
        built = payload_time(tag)
        if built is None:
            untagged += 1
            continue
        run = {"prow_id": prow_id, "seconds": seconds}
        by_day.setdefault(built.date().isoformat(), []).append(run)
        (after if built >= fix_time else before).append(run)
    fix_day = fix_time.date().isoformat()
    days = [dict(day=day, fixed="split" if day == fix_day else ("yes" if day > fix_day else "no"),
                 **_summary(by_day[day], signature_ids, scanned_ids))
            for day in sorted(by_day)]
    result = {
        "fix_payload": fix_payload,
        "before_fix": _summary(before, signature_ids, scanned_ids),
        "after_fix": _summary(after, signature_ids, scanned_ids),
        "by_payload_day": days,
        "excluded": {"no_disruption_data": no_data, "no_payload_tag": untagged,
                     "liveness_unreliable": liveness},
        "caveats": [
            "release_tag is the payload the job tested. An upgrade job runs the old payload until "
            "its upgrade finishes, so upgrades to a fixed payload can still show the bug for a day "
            "or two after the fix lands.",
        ],
    }
    if fix_day in by_day:
        result["caveats"].append("Fixed=split: payloads built on %s before the fix payload count as "
                                 "before_fix, the rest as after_fix." % fix_day)
    if not before:
        result["caveats"].append("No runs tested a payload older than the fix. Start the window before "
                                 "the fix (--days on disruption-trend, --since-hours on the finder).")
    if not after:
        result["caveats"].append("No runs tested the fix payload or a newer one yet.")
    if finder_input:
        result["caveats"].append("The finder's JSON lists only runs with disruption, so runs and disrupted "
                                 "are the same. Use disruption-trend's runs file for the disrupted share.")
    if untagged:
        result["caveats"].append("%d runs had no payload tag and are not counted." % untagged)
    if scanned_ids is not None:
        # Only disrupted runs count: a leftover clean-run timeline must not hide a missing one.
        disrupted_ids = [r["prow_id"] for r in before + after if r["seconds"] > 0]
        disrupted = len(disrupted_ids)
        searched = sum(1 for prow_id in disrupted_ids if prow_id in scanned_ids)
        if searched < disrupted:
            result["caveats"].append("Only %d of %d disrupted runs had timelines to search, so signature "
                                     "counts are a lower bound. Download timelines for every disrupted run "
                                     "in the window." % (searched, disrupted))
    return result


def _share(summary):
    if not summary["runs"]:
        return "0"
    return "%d (%d%%)" % (summary["disrupted"], round(100.0 * summary["disrupted"] / summary["runs"]))


def print_table(result):
    has_signature = "signature" in result["before_fix"]
    has_timelines = "timelines" in result["before_fix"]
    header = "%-12s %-6s %5s %10s %5s %5s" % ("Payload day", "Fixed", "Runs", "Disrupted", "P95", "Max")
    if has_timelines:
        header += " %9s" % "Timelines"
    if has_signature:
        header += " %9s" % "Signature"
    print("Fix payload: %s" % result["fix_payload"])
    print(header)
    for day in result["by_payload_day"]:
        line = "%-12s %-6s %5d %10s %5s %5s" % (
            day["day"], day["fixed"], day["runs"], _share(day),
            day["p95_seconds"], day["max_seconds"])
        if has_timelines:
            line += " %9d" % day["timelines"]
        if has_signature:
            line += " %9d" % day["signature"]
        print(line)
    for label, key in (("Before fix", "before_fix"), ("After fix", "after_fix")):
        part = result[key]
        line = "%s: %d runs, %s disrupted, P95 %ss" % (label, part["runs"], _share(part), part["p95_seconds"])
        if has_signature:
            line += ", %d with the signature" % part["signature"]
        print(line)
    for caveat in result["caveats"]:
        print("Caveat: %s" % caveat)


def read_signature_ids(value):
    """Comma-separated build IDs, or @path to a file with one per line."""
    if value.startswith("@"):
        with open(value[1:]) as handle:
            text = handle.read()
    else:
        text = value
    return {part.strip() for part in re.split(r"[,\s]+", text) if part.strip()}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Compare disruption before and after a fix payload")
    parser.add_argument("--runs", required=True,
                        help="disruption-trend runs file (preferred) or find_disruption_runs.py JSON")
    parser.add_argument("--fix-payload", required=True,
                        help="First payload with the fix, e.g. 5.1.0-0.nightly-2026-11-06-043907")
    parser.add_argument("--signature-runs",
                        help="Build IDs that show the bug's signature: comma-separated, or @file "
                             "with one per line")
    parser.add_argument("--signature",
                        help="Regex for the bug's error text, searched in disruption messages on "
                             "--backends in the timelines under --timelines-dir")
    parser.add_argument("--timelines-dir", help="download_timelines.py --output-dir")
    parser.add_argument("--backends", help="Comma-separated exact backend names to search")
    parser.add_argument("--format", choices=["table", "json"], default="table")
    args = parser.parse_args(argv)
    if args.signature and args.signature_runs:
        parser.error("use --signature or --signature-runs, not both")
    if args.signature and not (args.timelines_dir and args.backends):
        parser.error("--signature needs --timelines-dir and --backends")

    try:
        with open(args.runs) as handle:
            runs = json.load(handle)
    except (OSError, ValueError) as err:
        print("Error: cannot read %s: %s" % (args.runs, err), file=sys.stderr)
        return 1
    if not isinstance(runs, list):
        print("Error: %s is not the finder's JSON array" % args.runs, file=sys.stderr)
        return 1
    try:
        signature_ids = scanned_ids = None
        if args.signature_runs:
            signature_ids = read_signature_ids(args.signature_runs)
        elif args.signature:
            backends = [b.strip() for b in args.backends.split(",") if b.strip()]
            signature_ids, scanned_ids = scan_signature(args.timelines_dir, args.signature, backends)
        result = check_fix(runs, args.fix_payload, signature_ids, scanned_ids)
    except re.error as err:
        print("Error: bad --signature regex: %s" % err, file=sys.stderr)
        return 1
    except (OSError, ValueError) as err:
        print("Error: %s" % err, file=sys.stderr)
        return 1
    if args.format == "json":
        print(json.dumps(result, indent=2))
    else:
        print_table(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
