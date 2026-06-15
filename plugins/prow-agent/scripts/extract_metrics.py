#!/usr/bin/env python3
"""Extract Claude session metrics and produce an autodl JSON file for BigQuery.

Supports two input formats (auto-detected):
  1. OTEL JSONL — from the OTLP collector (preferred)
  2. Stream-JSON — from claude --output-format stream-json (legacy)

For OTEL input, identity fields (session_id, model, etc.) can be
supplemented from a stream-json log via --stream-log.

Usage:
    # OTEL mode (preferred)
    python3 extract_metrics.py claude-otel.jsonl [output-autodl.json]

    # OTEL + stream-json for identity fields
    python3 extract_metrics.py claude-otel.jsonl [output-autodl.json] --stream-log claude-output.log

    # Legacy stream-json mode (auto-detected)
    python3 extract_metrics.py claude-output.log [output-autodl.json]
"""

import json
import sys
from collections import Counter
from datetime import datetime, timezone


# ---------------------------------------------------------------------------
# Format detection
# ---------------------------------------------------------------------------

def detect_format(path):
    """Return 'otel' or 'stream' based on the first parseable line."""
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if "path" in obj and "payload" in obj:
                return "otel"
            if obj.get("type") in ("system", "assistant", "user", "result"):
                return "stream"
    return "stream"


# ---------------------------------------------------------------------------
# OTEL JSONL parsing
# ---------------------------------------------------------------------------

def parse_otel(path):
    """Parse an OTEL JSONL log and return a metrics row dict."""
    from collections import defaultdict

    records = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))

    if not records:
        print("ERROR: empty OTEL log file", file=sys.stderr)
        sys.exit(1)

    token_totals = defaultdict(float)
    cost_totals = defaultdict(float)
    active_time = defaultdict(float)
    api_requests = []

    for rec in records:
        rpath = rec.get("path", "")
        payload = rec.get("payload", {})

        if "/v1/metrics" in rpath:
            for rm in payload.get("resourceMetrics", []):
                for sm in rm.get("scopeMetrics", []):
                    for metric in sm.get("metrics", []):
                        name = metric.get("name", "")
                        data = metric.get("sum", metric.get("gauge", metric.get("histogram", {})))
                        for dp in data.get("dataPoints", []):
                            attrs = {
                                a["key"]: a["value"].get(
                                    "stringValue",
                                    a["value"].get("intValue", a["value"].get("doubleValue")),
                                )
                                for a in dp.get("attributes", [])
                            }
                            value = dp.get("asDouble", dp.get("asInt", 0))

                            if name == "claude_code.token.usage":
                                model = attrs.get("model", "unknown")
                                token_type = attrs.get("type", "unknown")
                                token_totals[(model, token_type)] += value
                            elif name == "claude_code.cost.usage":
                                model = attrs.get("model", "unknown")
                                cost_totals[model] += value
                            elif name == "claude_code.active_time.total":
                                time_type = attrs.get("type", "unknown")
                                active_time[time_type] += value

        elif "/v1/logs" in rpath:
            for rl in payload.get("resourceLogs", []):
                for sl in rl.get("scopeLogs", []):
                    for lr in sl.get("logRecords", []):
                        event_attrs = {}
                        event_name = ""
                        for a in lr.get("attributes", []):
                            key = a["key"]
                            val = a["value"]
                            v = val.get("stringValue", val.get("intValue", val.get("doubleValue")))
                            event_attrs[key] = v
                            if key == "event.name":
                                event_name = v
                        if event_name == "claude_code.api_request":
                            api_requests.append(event_attrs)

    total_cost_usd = sum(cost_totals.values())
    input_tokens = int(sum(v for (m, t), v in token_totals.items() if t == "input"))
    output_tokens = int(sum(v for (m, t), v in token_totals.items() if t == "output"))
    cache_read_tokens = int(sum(v for (m, t), v in token_totals.items() if t == "cacheRead"))
    cache_creation_tokens = int(sum(v for (m, t), v in token_totals.items() if t == "cacheCreation"))

    total_input = input_tokens + cache_read_tokens + cache_creation_tokens
    cache_hit_rate = (cache_read_tokens / total_input * 100) if total_input > 0 else 0

    # Tool usage from api_request log events
    tool_counts = Counter()
    for req in api_requests:
        tool = req.get("tool_name", "")
        if tool:
            tool_counts[tool] += 1
    total_tool_calls = sum(tool_counts.values())

    # Duration from active_time
    duration_api_s = active_time.get("api", 0)

    # Primary model is the one with the highest cost
    model = max(cost_totals, key=cost_totals.get) if cost_totals else ""

    analyzed_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    return {
        "session_id": "",
        "model": model,
        "claude_code_version": "",
        "permission_mode": "",
        "entrypoint": "",
        "prompt": "",
        "plugins_loaded": "",
        "analyzed_at": analyzed_at,
        "duration_ms": "0",
        "duration_api_ms": str(int(duration_api_s * 1000)),
        "ttft_ms": "0",
        "num_turns": "0",
        "total_cost_usd": f"{total_cost_usd:.6f}",
        "input_tokens": str(input_tokens),
        "output_tokens": str(output_tokens),
        "cache_read_input_tokens": str(cache_read_tokens),
        "cache_creation_input_tokens": str(cache_creation_tokens),
        "cache_hit_rate_pct": f"{cache_hit_rate:.1f}",
        "total_tool_calls": str(total_tool_calls),
        "tool_call_breakdown": json.dumps(dict(tool_counts.most_common())),
        "skills_invoked": "",
        "files_written": "0",
        "num_thinking_blocks": "0",
        "num_subagents": "0",
        "subagent_total_tool_uses": "0",
        "subagent_total_duration_ms": "0",
        "is_error": "0",
        "terminal_reason": "",
        "stop_reason": "",
    }


def enrich_from_stream_log(row, stream_log_path):
    """Fill in identity/outcome fields from a stream-json log."""
    try:
        with open(stream_log_path) as f:
            lines = [json.loads(line) for line in f if line.strip()]
    except (FileNotFoundError, json.JSONDecodeError):
        return row

    inits = [l for l in lines if l.get("type") == "system" and l.get("subtype") == "init"]
    results = [l for l in lines if l.get("type") == "result"]

    if inits:
        init = inits[0]
        row["session_id"] = row["session_id"] or init.get("session_id", "")
        row["model"] = row["model"] or init.get("model", "")
        row["claude_code_version"] = row["claude_code_version"] or init.get("claude_code_version", "")
        row["permission_mode"] = row["permission_mode"] or init.get("permissionMode", "")
        plugins = [p.get("name", "") for p in init.get("plugins", [])]
        row["plugins_loaded"] = row["plugins_loaded"] or ",".join(plugins)

    # Entrypoint
    if not row["entrypoint"]:
        for l in lines:
            if l.get("type") == "user" and l.get("entrypoint"):
                row["entrypoint"] = l["entrypoint"]
                break

    # Prompt
    if not row["prompt"]:
        for l in lines:
            if l.get("type") == "queue-operation" and l.get("operation") == "enqueue":
                row["prompt"] = l.get("content", "")[:500]
                break
    if not row["prompt"]:
        for l in lines:
            if l.get("type") != "assistant":
                continue
            msg = l.get("message", l)
            content = msg.get("content", [])
            if not isinstance(content, list):
                continue
            for block in content:
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    if block.get("name") == "Skill":
                        skill = block.get("input", {}).get("skill", "")
                        args = block.get("input", {}).get("args", "")
                        row["prompt"] = f"/{skill} {args}".strip()[:500]
                        break
            if row["prompt"]:
                break

    # Duration and turns from results
    if results:
        last_result = results[-1]
        row["duration_ms"] = str(sum(r.get("duration_ms", 0) for r in results))
        row["ttft_ms"] = str(results[0].get("ttft_ms", 0))
        row["num_turns"] = str(sum(r.get("num_turns", 0) for r in results))
        row["is_error"] = str(1 if last_result.get("is_error", False) else 0)
        row["terminal_reason"] = last_result.get("terminal_reason", "")
        row["stop_reason"] = last_result.get("stop_reason", "")

    # Skills and subagents from assistant messages
    seen_tool_ids = set()
    skills = []
    files_written_count = 0
    num_thinking = 0
    for l in lines:
        if l.get("type") != "assistant":
            continue
        msg = l.get("message", l)
        content = msg.get("content", [])
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "tool_use":
                tool_id = block.get("id", "")
                if tool_id and tool_id in seen_tool_ids:
                    continue
                seen_tool_ids.add(tool_id)
                inp = block.get("input", {})
                if block.get("name") == "Skill":
                    skills.append(inp.get("skill", ""))
                elif block.get("name") == "Write":
                    files_written_count += 1
            elif block.get("type") == "thinking":
                num_thinking += 1

    if skills:
        row["skills_invoked"] = ",".join(dict.fromkeys(skills))
    row["files_written"] = str(files_written_count)
    row["num_thinking_blocks"] = str(num_thinking)

    task_starts = [l for l in lines if l.get("subtype") == "task_started"]
    task_notifications = [l for l in lines if l.get("subtype") == "task_notification"]
    row["num_subagents"] = str(len(task_starts))
    row["subagent_total_tool_uses"] = str(sum(t.get("usage", {}).get("tool_uses", 0) for t in task_notifications))
    row["subagent_total_duration_ms"] = str(sum(t.get("usage", {}).get("duration_ms", 0) for t in task_notifications))

    return row


# ---------------------------------------------------------------------------
# Legacy stream-JSON parsing
# ---------------------------------------------------------------------------

def parse_stream_log(path):
    """Parse a claude-output.log file and return structured metrics."""
    with open(path) as f:
        lines = [json.loads(line) for line in f if line.strip()]

    if not lines:
        print("ERROR: empty log file", file=sys.stderr)
        sys.exit(1)

    inits = [l for l in lines if l.get("type") == "system" and l.get("subtype") == "init"]
    results = [l for l in lines if l.get("type") == "result"]

    if not results:
        print("ERROR: no result message found — session may not have completed", file=sys.stderr)
        sys.exit(1)

    init = inits[0] if inits else {}
    last_result = results[-1]

    session_id = init.get("session_id", last_result.get("session_id", ""))
    model = init.get("model", "")
    claude_code_version = init.get("claude_code_version", "")
    permission_mode = init.get("permissionMode", "")
    plugins = [p.get("name", "") for p in init.get("plugins", [])]
    entrypoint = ""
    prompt = ""
    for l in lines:
        if l.get("type") == "user" and l.get("entrypoint"):
            entrypoint = l["entrypoint"]
            break
    for l in lines:
        if l.get("type") == "queue-operation" and l.get("operation") == "enqueue":
            prompt = l.get("content", "")
            break
    if not prompt:
        for l in lines:
            if l.get("type") != "assistant":
                continue
            msg = l.get("message", l)
            content = msg.get("content", [])
            if not isinstance(content, list):
                continue
            for block in content:
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    if block.get("name") == "Skill":
                        skill = block.get("input", {}).get("skill", "")
                        args = block.get("input", {}).get("args", "")
                        prompt = f"/{skill} {args}".strip()
                        break
            if prompt:
                break

    duration_ms = sum(r.get("duration_ms", 0) for r in results)
    duration_api_ms = sum(r.get("duration_api_ms", 0) for r in results)
    ttft_ms = results[0].get("ttft_ms", 0)
    num_turns = sum(r.get("num_turns", 0) for r in results)

    total_cost_usd = sum(r.get("total_cost_usd", 0.0) for r in results)
    input_tokens = 0
    output_tokens = 0
    cache_read_tokens = 0
    cache_creation_tokens = 0
    for r in results:
        for mu in r.get("modelUsage", {}).values():
            input_tokens += mu.get("inputTokens", 0)
            output_tokens += mu.get("outputTokens", 0)
            cache_read_tokens += mu.get("cacheReadInputTokens", 0)
            cache_creation_tokens += mu.get("cacheCreationInputTokens", 0)

    total_input = input_tokens + cache_read_tokens + cache_creation_tokens
    cache_hit_rate = (cache_read_tokens / total_input * 100) if total_input > 0 else 0

    seen_tool_ids = set()
    tool_counts = Counter()
    skills_invoked = []
    files_written = []
    num_thinking_blocks = 0

    for l in lines:
        if l.get("type") != "assistant":
            continue
        msg = l.get("message", l)
        content = msg.get("content", [])
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "tool_use":
                tool_id = block.get("id", "")
                if tool_id and tool_id in seen_tool_ids:
                    continue
                seen_tool_ids.add(tool_id)
                tool_counts[block.get("name", "unknown")] += 1
                inp = block.get("input", {})
                if block.get("name") == "Skill":
                    skills_invoked.append(inp.get("skill", ""))
                elif block.get("name") == "Write":
                    files_written.append(inp.get("file_path", ""))
            elif block.get("type") == "thinking":
                num_thinking_blocks += 1

    total_tool_calls = sum(tool_counts.values())

    task_starts = [l for l in lines if l.get("subtype") == "task_started"]
    task_notifications = [l for l in lines if l.get("subtype") == "task_notification"]
    num_subagents = len(task_starts)
    subagent_total_tool_uses = sum(t.get("usage", {}).get("tool_uses", 0) for t in task_notifications)
    subagent_total_duration_ms = sum(t.get("usage", {}).get("duration_ms", 0) for t in task_notifications)

    is_error = 1 if last_result.get("is_error", False) else 0
    terminal_reason = last_result.get("terminal_reason", "")
    stop_reason = last_result.get("stop_reason", "")

    analyzed_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    return {
        "session_id": session_id,
        "model": model,
        "claude_code_version": claude_code_version,
        "permission_mode": permission_mode,
        "entrypoint": entrypoint,
        "prompt": prompt[:500],
        "plugins_loaded": ",".join(plugins),
        "analyzed_at": analyzed_at,
        "duration_ms": str(duration_ms),
        "duration_api_ms": str(duration_api_ms),
        "ttft_ms": str(ttft_ms),
        "num_turns": str(num_turns),
        "total_cost_usd": f"{total_cost_usd:.6f}",
        "input_tokens": str(input_tokens),
        "output_tokens": str(output_tokens),
        "cache_read_input_tokens": str(cache_read_tokens),
        "cache_creation_input_tokens": str(cache_creation_tokens),
        "cache_hit_rate_pct": f"{cache_hit_rate:.1f}",
        "total_tool_calls": str(total_tool_calls),
        "tool_call_breakdown": json.dumps(dict(tool_counts.most_common())),
        "skills_invoked": ",".join(dict.fromkeys(skills_invoked)),
        "files_written": str(len(files_written)),
        "num_thinking_blocks": str(num_thinking_blocks),
        "num_subagents": str(num_subagents),
        "subagent_total_tool_uses": str(subagent_total_tool_uses),
        "subagent_total_duration_ms": str(subagent_total_duration_ms),
        "is_error": str(is_error),
        "terminal_reason": terminal_reason,
        "stop_reason": stop_reason,
    }


# ---------------------------------------------------------------------------
# Autodl output
# ---------------------------------------------------------------------------

SCHEMA = {
    "session_id": "string",
    "model": "string",
    "claude_code_version": "string",
    "permission_mode": "string",
    "entrypoint": "string",
    "prompt": "string",
    "plugins_loaded": "string",
    "analyzed_at": "string",
    "duration_ms": "int64",
    "duration_api_ms": "int64",
    "ttft_ms": "int64",
    "num_turns": "int64",
    "total_cost_usd": "float64",
    "input_tokens": "int64",
    "output_tokens": "int64",
    "cache_read_input_tokens": "int64",
    "cache_creation_input_tokens": "int64",
    "cache_hit_rate_pct": "float64",
    "total_tool_calls": "int64",
    "tool_call_breakdown": "string",
    "skills_invoked": "string",
    "files_written": "int64",
    "num_thinking_blocks": "int64",
    "num_subagents": "int64",
    "subagent_total_tool_uses": "int64",
    "subagent_total_duration_ms": "int64",
    "is_error": "int64",
    "terminal_reason": "string",
    "stop_reason": "string",
}


def build_autodl(row):
    return {
        "table_name": "claude_session_metrics",
        "schema": SCHEMA,
        "schema_mapping": None,
        "rows": [row],
        "chunk_size": 0,
        "expiration_days": 0,
        "partition_column": "",
    }


def main():
    stream_log = None
    args = list(sys.argv[1:])

    # Parse --stream-log flag
    if "--stream-log" in args:
        idx = args.index("--stream-log")
        if idx + 1 < len(args):
            stream_log = args[idx + 1]
            args = args[:idx] + args[idx + 2:]
        else:
            print("ERROR: --stream-log requires a path argument", file=sys.stderr)
            sys.exit(2)

    if not args:
        print(f"Usage: {sys.argv[0]} <input.jsonl> [output-autodl.json] [--stream-log <claude-output.log>]",
              file=sys.stderr)
        sys.exit(2)

    log_path = args[0]
    output_path = args[1] if len(args) > 1 else "claude-session-metrics-autodl.json"

    fmt = detect_format(log_path)

    if fmt == "otel":
        row = parse_otel(log_path)
        if stream_log:
            row = enrich_from_stream_log(row, stream_log)
    else:
        row = parse_stream_log(log_path)

    autodl = build_autodl(row)

    with open(output_path, "w") as f:
        json.dump(autodl, f, indent=4)

    print(f"OK: wrote {output_path} (format={fmt})")
    print(f"  model={row['model']} cost=${row['total_cost_usd']} "
          f"duration={int(row['duration_ms'])//1000}s "
          f"turns={row['num_turns']} tools={row['total_tool_calls']} "
          f"subagents={row['num_subagents']}")
    print(f"  tokens: in={row['input_tokens']} out={row['output_tokens']} "
          f"cache_read={row['cache_read_input_tokens']} "
          f"cache_create={row['cache_creation_input_tokens']} "
          f"hit_rate={row['cache_hit_rate_pct']}%")


if __name__ == "__main__":
    main()
