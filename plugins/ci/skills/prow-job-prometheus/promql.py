#!/usr/bin/env python3
"""Run a PromQL query against a local Prometheus and print a time-by-series table.

Usage:
    python3 promql.py 'sum by (instance) (apiserver_current_inflight_requests)' \
        --start 2026-10-13T14:30:00Z --end 2026-10-13T14:56:00Z --step 60 --label instance
    python3 promql.py 'up{job="etcd"}' --time 2026-10-13T14:40:00Z

Without --start/--end a range query covers the whole snapshot. --time runs an
instant query and prints one line per series.
"""
import argparse
import json
import sys
import time
import urllib.parse
import urllib.request


def api(base, path, params):
    u = base.rstrip("/") + path + "?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(u, timeout=300) as resp:
        d = json.load(resp)
    if d.get("status") != "success":
        raise RuntimeError(d.get("error", d))
    return d["data"]


def series_name(metric, label):
    if label:
        return metric.get(label, "") or "-"
    parts = [f"{k}={v}" for k, v in sorted(metric.items()) if k != "__name__"]
    return ",".join(parts) or "value"


def format_range(result, label, width=14, max_series=12):
    """Render a matrix result as a table: one row per timestamp, one column per series."""
    if not result:
        return "(no data)"
    # Keep the series with the largest peak when there are too many columns.
    result = sorted(result, key=lambda r: -max((float(v) for _, v in r["values"]), default=0))[:max_series]
    names = [series_name(r["metric"], label) for r in result]
    vals = [{int(float(t)): float(v) for t, v in r["values"]} for r in result]
    ts = sorted({t for v in vals for t in v})
    lines = ["time   " + " ".join(f"{n[-width:]:>{width}}" for n in names)]
    for t in ts:
        cells = " ".join(f"{v[t]:>{width}.4g}" if t in v else f"{'-':>{width}}" for v in vals)
        lines.append(time.strftime("%H:%M:%S", time.gmtime(t)) + " " + cells)
    return "\n".join(lines)


def format_instant(result, label):
    if not result:
        return "(no data)"
    rows = sorted(result, key=lambda r: -float(r["value"][1]))
    return "\n".join(f"{float(r['value'][1]):>14.4g}  {series_name(r['metric'], label)}" for r in rows)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("query")
    ap.add_argument("--url", default="http://localhost:9090", help="Prometheus base URL")
    ap.add_argument("--start", help="RFC3339 start (default: snapshot start)")
    ap.add_argument("--end", help="RFC3339 end (default: snapshot end)")
    ap.add_argument("--step", type=int, default=60, help="step in seconds (default 60)")
    ap.add_argument("--time", help="run an instant query at this RFC3339 time")
    ap.add_argument("--label", help="label to name each series column by")
    ap.add_argument("--max-series", type=int, default=12, help="columns to show, by peak value (default 12)")
    args = ap.parse_args()
    try:
        if args.time:
            print(format_instant(api(args.url, "/api/v1/query", {"query": args.query, "time": args.time})["result"], args.label))
            return 0
        start, end = args.start, args.end
        if not (start and end):
            hs = api(args.url, "/api/v1/status/tsdb", {})["headStats"]
            start = start or hs["minTime"] / 1000
            end = end or hs["maxTime"] / 1000
        data = api(args.url, "/api/v1/query_range", {"query": args.query, "start": start, "end": end, "step": args.step})
        print(format_range(data["result"], args.label, max_series=args.max_series))
        return 0
    except (OSError, RuntimeError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
