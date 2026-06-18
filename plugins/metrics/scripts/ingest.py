#!/usr/bin/env python3
"""Ingest OTEL JSONL from collector.py into a structured metrics JSON file.

Reads the three OTEL metric types emitted by Claude Code and produces a
single clean JSON file. No session JSONL parsing; OTEL is the sole source.

Metrics extracted:
  /v1/metrics  claude_code.token.usage    → tokens (input/output/cache)
  /v1/metrics  claude_code.cost.usage     → cost_usd
  /v1/metrics  claude_code.active_time.total → timing (api_s, tool_execution_s)
  /v1/logs     tool_decision events       → tools breakdown

Usage:
    python3 ingest.py --otel-log otel-current.jsonl [--out metrics.json]

    # SessionEnd hook (reads session_id from stdin JSON):
    python3 ingest.py --otel-log otel-current.jsonl --from-hook
"""

import argparse
import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone


def load_records(log_file):
    records = []
    try:
        with open(log_file) as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        records.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
    except FileNotFoundError:
        print(f"Error: OTEL log not found: {log_file}", file=sys.stderr)
        sys.exit(1)
    return records


def get_attr(attributes, key):
    for a in attributes:
        if a.get("key") == key:
            v = a.get("value", {})
            return v.get("stringValue", v.get("intValue", v.get("doubleValue")))
    return None


def parse_otel(records):
    tokens = defaultdict(float)     # (model, type) -> count
    costs = defaultdict(float)      # model -> usd
    active_time = defaultdict(float)  # type -> seconds
    tools = defaultdict(int)        # tool_name -> count

    for rec in records:
        path = rec.get("path", "")
        payload = rec.get("payload", {})

        if "/v1/metrics" in path:
            for rm in payload.get("resourceMetrics", []):
                for sm in rm.get("scopeMetrics", []):
                    for metric in sm.get("metrics", []):
                        name = metric.get("name", "")
                        data = metric.get("sum", metric.get("gauge", metric.get("histogram", {})))
                        for dp in data.get("dataPoints", []):
                            attrs = dp.get("attributes", [])
                            value = dp.get("asDouble", dp.get("asInt", 0))

                            if name == "claude_code.token.usage":
                                model = get_attr(attrs, "model") or "unknown"
                                token_type = get_attr(attrs, "type") or "unknown"
                                tokens[(model, token_type)] += value
                            elif name == "claude_code.cost.usage":
                                model = get_attr(attrs, "model") or "unknown"
                                costs[model] += value
                            elif name == "claude_code.active_time.total":
                                time_type = get_attr(attrs, "type") or "unknown"
                                active_time[time_type] += value

        elif "/v1/logs" in path:
            for rl in payload.get("resourceLogs", []):
                for sl in rl.get("scopeLogs", []):
                    for lr in sl.get("logRecords", []):
                        attrs = lr.get("attributes", [])
                        event_name = get_attr(attrs, "event.name") or ""
                        if event_name == "tool_decision":
                            tool_name = get_attr(attrs, "tool_name") or "unknown"
                            decision = get_attr(attrs, "decision") or ""
                            if decision == "accept":
                                tools[tool_name] += 1

    return dict(tokens), dict(costs), dict(active_time), dict(tools)


def build_output(tokens, costs, active_time, tools, records, session_id=None):
    type_map = {
        "input": "input",
        "output": "output",
        "cacheRead": "cache_read",
        "cacheCreation": "cache_creation",
    }
    token_totals = {"input": 0, "output": 0, "cache_read": 0, "cache_creation": 0}
    models = set()
    for (model, token_type), count in tokens.items():
        models.add(model)
        mapped = type_map.get(token_type)
        if mapped:
            token_totals[mapped] += int(count)

    primary_model = max(costs, key=costs.get) if costs else (next(iter(models), "unknown"))
    cost_usd = sum(costs.values())

    total_input = token_totals["input"] + token_totals["cache_read"] + token_totals["cache_creation"]
    cache_hit_rate = round(token_totals["cache_read"] / total_input, 4) if total_input > 0 else 0.0

    timestamps = sorted(r.get("ts") for r in records if r.get("ts"))

    result = {
        "ingested_at": datetime.now(timezone.utc).isoformat(),
        "session_start": timestamps[0] if timestamps else None,
        "session_end": timestamps[-1] if timestamps else None,
        "model": primary_model,
        "cost_usd": round(cost_usd, 6),
        "tokens": {**token_totals, "cache_hit_rate": cache_hit_rate},
        "timing": {
            "api_s": round(active_time.get("api", 0), 2),
            "tool_execution_s": round(active_time.get("tool_execution", 0), 2),
        },
        "tools": {
            "total": sum(tools.values()),
            "breakdown": dict(sorted(tools.items(), key=lambda x: x[1], reverse=True)),
        },
    }
    if session_id:
        result["session_id"] = session_id
    return result


def main():
    parser = argparse.ArgumentParser(description="Ingest OTEL JSONL into session metrics JSON")
    parser.add_argument("--otel-log", required=True, help="OTEL JSONL file from collector.py")
    parser.add_argument("--out", help="Output JSON path (default: same as otel-log with .json extension)")
    parser.add_argument(
        "--from-hook",
        action="store_true",
        help="Read session_id from Claude Code hook stdin (JSON)",
    )
    args = parser.parse_args()

    session_id = None
    if args.from_hook:
        try:
            hook_data = json.load(sys.stdin)
            session_id = hook_data.get("session_id")
        except (json.JSONDecodeError, EOFError):
            pass

    records = load_records(args.otel_log)
    if not records:
        print("Warning: no OTEL records found in log file", file=sys.stderr)

    tokens, costs, active_time, tools = parse_otel(records)
    output = build_output(tokens, costs, active_time, tools, records, session_id)

    out_path = args.out
    if not out_path:
        base = os.path.splitext(args.otel_log)[0]
        out_path = base + ".json"

    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)

    print(f"Metrics written to {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
