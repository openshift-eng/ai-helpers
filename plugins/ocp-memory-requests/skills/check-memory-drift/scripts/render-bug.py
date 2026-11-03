#!/usr/bin/env python3
"""Render an OCPBUGS bug from a single drift candidate.

Reads one candidate object (as emitted by select-candidates.py) on stdin and
prints the bug as JSON on stdout: the fixed Jira fields and the description
markdown. Fixed here so every bug is identical in shape; the model appends what
it found in step 5 (owning repo + manifest path) into the "What was found"
section before filing.

Usage:
    echo '<candidate json>' | python3 render-bug.py --release 5.1 --window-days 30
"""
from __future__ import annotations

import argparse
import json
import sys

LABELS = ["issue-for-agent", "ocp-memory-requests", "ai-generated-jira"]
DASHBOARD = "https://grafana-loki.ci.openshift.org/d/AWW7kDqvk/operator-memory-use?orgId=1"


def _fmt(n):
    """Trim a number like 49.0 -> '49', 49.9 -> '49.9'."""
    d = float(n)
    return str(int(d)) if d == int(d) else str(d)


def render_bug(c, release, window_days):
    ns, dep, direction = c["namespace"], c["deployment"], c["direction"]
    key = f"{release}/{ns}/{dep}"
    rec_mb, rec_mi = c["recommended_mb"], c["recommended_mi"]
    cur_mb = c.get("current_mb") or 0

    if direction == "set":
        summary = f"Set memory request for {dep} ({ns}): none -> {_fmt(rec_mb)} MB"
        drift_row = "not set (no request configured)"
    else:
        pct = c["drift_pct"]
        sign = "+" if pct and pct > 0 else ""
        summary = (f"Right-size memory request for {dep} ({ns}): "
                   f"{_fmt(cur_mb)} -> {_fmt(rec_mb)} MB ({sign}{_fmt(pct)}%)")
        drift_row = f"{_fmt(pct)}% ({direction})"

    warn = ""
    if direction in ("raise", "set"):
        warn += ("\n> WARNING: Memory increases are a risk on topologies such as "
                 "single-node and HyperShift; please ensure the change is justified, "
                 "expected, and not excessive.\n")
    if c.get("var"):
        warn += (f"\n> The configured request differs across variants "
                 f"(min {_fmt(c['request_mb_min'])} / max {_fmt(c['request_mb_max'])} MB); "
                 f"check every manifest.\n")

    description = f"""## Summary
The memory request for `{dep}` has drifted from its observed at-rest (pre-suite)
usage in CI. Filed automatically by the `ocp-memory-requests` memory-drift check.

memory-drift-key: {key}

## Evidence (release {release}, last {window_days} days, {c['job_runs']} job runs)
| Metric | Value |
|--------|-------|
| Namespace | `{ns}` |
| Deployment | `{dep}` |
| Current memory request | {_fmt(cur_mb)} MB |
| Observed p90 start usage (pre-suite, at-rest) | {_fmt(c['p90_start_mb'])} MB |
| Observed p50 start usage | {_fmt(c['p50_start_mb'])} MB |
| Recommended request (p90 at-rest + 10% headroom) | **{_fmt(rec_mb)} MB ({rec_mi}Mi)** |
| Drift | {drift_row} |

Methodology: 90th percentile of `StartMemoryUsageMB` (pre-suite, at-rest) from
`control_plane_singleton_pods`, across job runs on {release} over the last
{window_days} days, using each run's latest snapshot. The +10% headroom follows
`openshift/enhancements` `CONVENTIONS.md`; the measurement basis (pre-suite
across runs) is a deliberate at-rest floor, not the convention's during-suite
percentile.

Explore operator memory use: {DASHBOARD}
{warn}
## Fix instructions (for the solving agent)
1. Update `spec.template.spec.containers[].resources.requests.memory` for the
   `{dep}` container to **{rec_mi}Mi** ({_fmt(rec_mb)} MB). Keep the manifest's
   existing unit style (Mi/Gi).
2. Do not change the memory **limit** unless the manifest ties it to the request;
   this bug is about the **request** only.
3. Follow `openshift/enhancements` `CONVENTIONS.md` (~10% headroom over observed).

### PR rules (from lessons learned)
- **Only open PRs against repos in the `openshift` GitHub org.** Do NOT open a PR
  outside the `openshift` org (including upstream repos) unless a human has
  explicitly commented on this Jira that AI contributions to that repo are OK.
- **Target the repo's default branch** (`main` or `master`). Do NOT submit PRs
  against release branches such as `release-{release}`.
- **Do NOT add unit tests** to verify that a manifest or request value was updated.

## What was found (step 5)
<!-- The running agent fills this in: the owning operator + source repo, and the
exact manifest / asset path where the request is set. If it cannot be found,
comment on this Jira instead of guessing. -->
"""

    return {
        "project": "OCPBUGS",
        "issuetype": "Bug",
        "summary": summary,
        "labels": LABELS,
        "key": key,
        "versions": [{"name": release}],
        "target_version": f"openshift-{release}",
        "security": {"name": "Red Hat Employee"},
        "description": description,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Render an OCPBUGS bug from a candidate on stdin.")
    ap.add_argument("--release", required=True)
    ap.add_argument("--window-days", type=int, required=True)
    args = ap.parse_args(argv)

    candidate = json.loads(sys.stdin.read())
    if isinstance(candidate, list):
        if len(candidate) != 1:
            print("error: expected exactly one candidate on stdin", file=sys.stderr)
            return 2
        candidate = candidate[0]
    bug = render_bug(candidate, args.release, args.window_days)
    json.dump(bug, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
