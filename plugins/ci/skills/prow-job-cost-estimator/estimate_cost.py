#!/usr/bin/env python3
"""Estimate cloud cost for OpenShift CI prow jobs based on duration and platform.

Accepts a JSON array of jobs on stdin or via --input file. Each job object must have:
  - name (string): job name, used to infer platform
  - duration_minutes (number): average runtime in minutes
  - decision (string): "run" or "skip"
  - ci_status (string): "required" or "optional"

Outputs per-job cost breakdown and totals.
"""

import argparse
import json
import sys

RATES = [
    ("microshift", 0.15),
    ("aws", 1),
    ("gcp", 2),
    ("azure", 2),
    ("metal", 3),
    ("vsphere", 4),
]


def get_rate(name):
    lower = name.lower()
    for platform, rate in RATES:
        if platform in lower:
            return platform, rate
    return "aws", 1


def estimate(jobs):
    for j in jobs:
        platform, rate = get_rate(j["name"])
        j["platform"] = platform
        j["rate_per_hr"] = rate
        j["cost_usd"] = round((j["duration_minutes"] / 60) * rate, 2)

    run_jobs = [j for j in jobs if j["decision"] == "run"]
    skip_jobs = [j for j in jobs if j["decision"] == "skip"]

    recommended_cost = round(sum(j["cost_usd"] for j in run_jobs), 2)
    savings = round(sum(j["cost_usd"] for j in skip_jobs if j["ci_status"] == "required"), 2)
    added = round(sum(j["cost_usd"] for j in run_jobs if j["ci_status"] == "optional"), 2)
    net_savings = round(savings - added, 2)

    return {
        "recommended_cost_usd": recommended_cost,
        "savings_from_skipped_required_usd": savings,
        "added_cost_from_optional_usd": added,
        "net_savings_usd": net_savings,
        "jobs": jobs,
    }


def main():
    parser = argparse.ArgumentParser(description="Estimate prow job cloud costs.")
    parser.add_argument("--input", default=None, help="Path to JSON file with jobs array (default: stdin)")
    parser.add_argument("--format", choices=["json", "summary"], default="summary", help="Output format")
    args = parser.parse_args()

    if args.input:
        with open(args.input) as f:
            jobs = json.load(f)
    else:
        jobs = json.load(sys.stdin)

    result = estimate(jobs)

    if args.format == "json":
        print(json.dumps(result, indent=2))
    else:
        print("Per-job breakdown:")
        for j in result["jobs"]:
            print(f"  {j['name']}: {j['duration_minutes']} min x ${j['rate_per_hr']}/hr ({j['platform']}) = ${j['cost_usd']:.2f} [{j['decision']}]")
        print()
        print(f"Recommended cost: ${result['recommended_cost_usd']:.2f}")
        print(f"Savings (skipped required): ${result['savings_from_skipped_required_usd']:.2f}")
        print(f"Added (optional triggered): ${result['added_cost_from_optional_usd']:.2f}")
        print(f"Net savings: ${result['net_savings_usd']:.2f}")


if __name__ == "__main__":
    main()
