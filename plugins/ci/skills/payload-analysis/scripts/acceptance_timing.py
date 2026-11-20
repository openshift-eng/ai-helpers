#!/usr/bin/env python3
"""Assess the force-accept timing criterion from recorded payload history."""

import argparse
from datetime import datetime, timedelta
import json
from pathlib import Path

MINIMUM_HOURS = 18


def _cut_time(tag):
    try:
        return datetime.strptime(tag[-17:], "%Y-%m-%d-%H%M%S")
    except (TypeError, ValueError):
        return None


def assess_acceptance_timing(summary):
    """Assess timing from a payload-snapshot summary.json dict.

    Input contract (see payload-snapshot/SKILL.md, summary.json):
      payload_tag: full target tag with a UTC YYYY-MM-DD-HHMMSS suffix.
      payloads: newest-first list starting at the target, with entries:
        tag: full payload tag with the same timestamp suffix format.
        phase: recorded Accepted, Rejected, or Ready phase.

    Other fields, including chain-baseline metrics, are ignored. Missing
    phases/cut times or no observed Accepted payload yield unknown timing.
    """
    result = {
        "status": "unknown",
        "minimum_hours": MINIMUM_HOURS,
        "accepted_payload_tag": None,
        "hours_before_target": None,
        "reason": None,
    }
    target_time = _cut_time(summary.get("payload_tag"))
    if target_time is None:
        return {**result, "reason": "Target payload cut time is unavailable"}

    for payload in summary.get("payloads", []):
        phase = payload.get("phase")
        if phase not in ("Accepted", "Rejected", "Ready"):
            return {**result, "reason": "Unreadable payload phase prevents identifying the newest Accepted payload"}
        if phase != "Accepted":
            continue

        result["accepted_payload_tag"] = payload.get("tag")
        accepted_time = _cut_time(result["accepted_payload_tag"])
        if accepted_time is None or accepted_time > target_time:
            return {**result, "reason": "Accepted payload cut time is unavailable or after the target"}
        interval = target_time - accepted_time
        result["hours_before_target"] = interval.total_seconds() / 3600
        result["status"] = "met" if interval >= timedelta(hours=MINIMUM_HOURS) else "not_met"
        return result

    return {**result, "reason": "No Accepted payload found in collected history"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("summary", type=Path, help="Snapshot summary.json")
    args = parser.parse_args()
    try:
        summary = json.loads(args.summary.read_text())
    except (OSError, ValueError) as error:
        parser.error(str(error))
    print(json.dumps(assess_acceptance_timing(summary), indent=2))


if __name__ == "__main__":
    main()
