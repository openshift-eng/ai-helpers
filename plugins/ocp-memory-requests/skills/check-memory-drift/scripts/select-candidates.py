#!/usr/bin/env python3
"""Select memory-drift candidates from singleton-usage query output.

Reads the JSON rows produced by:

    bq query --use_legacy_sql=false --format=json \
      --parameter=release:STRING:<R> --parameter=window_days:INT64:<W> \
      < queries/singleton-usage.sql

on stdin, applies the policy math, and prints the candidate list as JSON on
stdout. Deterministic and unit-tested: the single source of truth for the +10%
recommendation, the drift calculation, the threshold / min-runs filters, the
raise/lower/set direction, and the MB->Mi conversion.

Usage:
    ... | python3 select-candidates.py [--threshold-pct 30] [--min-runs 100]
"""
from __future__ import annotations

import argparse
import json
import sys
from decimal import Decimal, ROUND_HALF_UP, ROUND_CEILING

HEADROOM = Decimal("1.10")      # request = observed p90 + 10% (CONVENTIONS.md)
MB_PER_MI = Decimal("0.9537")   # 1 MB = 10^6 bytes; 1 Mi = 2^20 bytes
MI_INCREMENT = 16               # round recommended Mi up to a clean increment

DEFAULT_THRESHOLD_PCT = 30
DEFAULT_MIN_RUNS = 100


def _dec(value) -> Decimal:
    if value is None or value == "":
        return Decimal(0)
    return Decimal(str(value))


def round1(value) -> Decimal:
    """Round to 1 decimal, half away from zero (matches BigQuery ROUND)."""
    return _dec(value).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)


def mb_to_mi_roundup(mb, increment: int = MI_INCREMENT) -> int:
    """Convert MB to Mi and round UP to the next multiple of `increment`."""
    mi = _dec(mb) * MB_PER_MI
    steps = (mi / Decimal(increment)).to_integral_value(rounding=ROUND_CEILING)
    return int(steps * Decimal(increment))


def select_candidates(rows, threshold_pct=DEFAULT_THRESHOLD_PCT, min_runs=DEFAULT_MIN_RUNS):
    threshold = Decimal(str(threshold_pct))
    out = []
    for r in rows:
        job_runs = int(_dec(r.get("job_runs")))
        if job_runs < min_runs:
            continue
        p90 = round1(r.get("p90_start_mb"))
        p50 = round1(r.get("p50_start_mb"))
        req = round1(r.get("request_mb"))
        req_min = round1(r.get("request_mb_min"))
        req_max = round1(r.get("request_mb_max"))
        recommended = round1(p90 * HEADROOM)

        if req > 0:
            drift = round1((recommended - req) / req * 100)
            if abs(drift) <= threshold:          # strictly greater to qualify
                continue
            direction = "raise" if drift > 0 else "lower"
            drift_val = float(drift)
        elif p90 > 0:
            direction = "set"                    # no request configured at all
            drift_val = None
        else:
            continue

        out.append({
            "deployment": r.get("Deployment") or r.get("deployment"),
            "namespace": r.get("Namespace") or r.get("namespace"),
            "direction": direction,
            "job_runs": job_runs,
            "p50_start_mb": float(p50),
            "p90_start_mb": float(p90),
            "current_mb": float(req),
            "request_mb_min": float(req_min),
            "request_mb_max": float(req_max),
            "recommended_mb": float(recommended),
            "recommended_mi": mb_to_mi_roundup(recommended),
            "drift_pct": drift_val,
            "var": req_min != req_max,
        })

    # Most urgent first: zero-request "set" cases, then largest |drift|.
    out.sort(key=lambda c: (c["drift_pct"] is not None, -abs(c["drift_pct"] or 0)))
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="Select memory-drift candidates from usage JSON on stdin.")
    ap.add_argument("--threshold-pct", type=int, default=DEFAULT_THRESHOLD_PCT)
    ap.add_argument("--min-runs", type=int, default=DEFAULT_MIN_RUNS)
    args = ap.parse_args(argv)

    raw = sys.stdin.read()
    rows = json.loads(raw) if raw.strip() else []
    if isinstance(rows, dict):
        rows = rows.get("rows") or []
    candidates = select_candidates(rows, args.threshold_pct, args.min_runs)
    json.dump(candidates, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
