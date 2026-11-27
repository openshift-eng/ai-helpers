#!/usr/bin/env python3
"""Mock bq CLI for the check-memory-drift eval.

Stands in for "the environment's bq CLI" wherever the skill runs bq. The SQL on
stdin identifies which of the skill's two queries is being run; the mock serves
the matching per-case fixture from the working directory, so the skill's real
pipeline step — run the query, with named parameters, dry-run first — is
exercised end to end. No live BigQuery.

Every call appends one JSON line to ``bq-calls.jsonl`` in the current working
directory, so the eval judges score the parameters the skill actually passed
(release, window_days) and that a dry-run preceded each query — not a
self-report.

Usage (mirrors ``bq query``):
  python3 bq-mock.py query --use_legacy_sql=false --format=json \
      --parameter=release:STRING:5.1 --parameter=window_days:INT64:30 \
      [--dry_run] < queries/singleton-usage.sql

Fixtures served from the working directory:
  usage.json                  — result rows of singleton-usage.sql
  defective-upgrade-runs.json — result rows of defective-upgrade-runs.sql

Each logged line: {"action": "dry_run"|"query", "query":
"singleton-usage"|"defective-upgrade-runs", "parameters": {…}} (dry_run adds
"bytes", query adds "rows").
"""
import argparse
import json
import sys
from pathlib import Path

LOG = Path("bq-calls.jsonl")

# The two queries are told apart by a token unique to each one's SQL: the usage
# query is the only one selecting p90_start_mb; the defective-run count is the
# only one selecting defective_upgrade_runs. (Both read the same table, so the
# table name cannot distinguish them.)
QUERIES = {
    "singleton-usage": {
        "marker": "p90_start_mb",
        "fixture": "usage.json",
        "bytes": 214748364,  # ~204 MB, the observed scan size
    },
    "defective-upgrade-runs": {
        "marker": "defective_upgrade_runs",
        "fixture": "defective-upgrade-runs.json",
        "bytes": 52428800,  # ~50 MB
    },
}


def _append(record):
    with LOG.open("a") as f:
        f.write(json.dumps(record, sort_keys=True) + "\n")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="bq-mock.py")
    sub = ap.add_subparsers(dest="command", required=True)
    q = sub.add_parser("query", help="run a query (SQL on stdin)")
    q.add_argument("--parameter", action="append", default=[],
                   help="named parameter as name:TYPE:value")
    q.add_argument("--dry_run", action="store_true",
                   help="validate the query and estimate bytes without billing")
    q.add_argument("--format", default="json")
    q.add_argument("--use_legacy_sql", help="ignored (mock)")
    q.add_argument("--project_id", help="ignored (mock)")
    q.add_argument("--max_rows", type=int, help="ignored (mock)")
    args = ap.parse_args(argv)

    sql = sys.stdin.read()
    name = next((n for n, c in QUERIES.items() if c["marker"] in sql), None)
    if name is None:
        print("bq-mock: unrecognized query — no known marker in the SQL on stdin",
              file=sys.stderr)
        return 2

    params = {}
    for raw in args.parameter:
        bits = raw.split(":", 2)
        if len(bits) != 3:
            print(f"bq-mock: bad --parameter {raw!r} (want name:TYPE:value)",
                  file=sys.stderr)
            return 2
        params[bits[0]] = bits[2]

    if args.dry_run:
        _append({"action": "dry_run", "query": name, "parameters": params,
                 "bytes": QUERIES[name]["bytes"]})
        print(json.dumps({"status": "valid",
                          "totalBytesProcessed": QUERIES[name]["bytes"]}))
        return 0

    fixture = Path(QUERIES[name]["fixture"])
    if not fixture.is_file():
        print(f"bq-mock: fixture {fixture} not found in the working directory",
              file=sys.stderr)
        return 2
    rows = fixture.read_text()
    try:
        count = len(json.loads(rows))
    except json.JSONDecodeError as exc:
        print(f"bq-mock: fixture {fixture} is not valid JSON: {exc}",
              file=sys.stderr)
        return 2
    _append({"action": "query", "query": name, "parameters": params,
             "rows": count})
    sys.stdout.write(rows if rows.endswith("\n") else rows + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
