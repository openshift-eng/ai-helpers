#!/usr/bin/env python3
"""Extract Claude session metrics from OTEL JSONL and produce an autodl JSON file for BigQuery.

Parses the OTEL JSONL output produced by agentic-ci's OTLP collector.
Identity fields (session_id, model, etc.) can be supplemented from a
stream-json log via --stream-log.

Usage:
    python3 extract_metrics.py claude-otel.jsonl [output-autodl.json]
    python3 extract_metrics.py claude-otel.jsonl [output-autodl.json] --stream-log claude-output.log
"""

import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone


def _parse_span_attrs(span):
    """Extract span attributes as a flat dict."""
    attrs = {}
    for a in span.get("attributes", []):
        key = a["key"]
        val = a.get("value", {})
        v = val.get("stringValue", val.get("intValue", val.get("doubleValue")))
        if v is not None:
            attrs[key] = v
    return attrs


class TraceAccumulator:
    """Accumulates session metadata across batched /v1/traces payloads."""

    def __init__(self):
        self.session_id = ""
        self.claude_code_version = ""
        self.permission_mode = ""
        self.min_start_ns = None
        self.max_end_ns = None
        self.first_interaction_start_ns = None
        self.first_ttft_ms = 0
        self.num_turns = 0
        self.last_stop_reason = ""
        self.skills = []
        self.files_written = 0
        self.num_subagents = 0

    def add(self, payload):
        """Process one /v1/traces payload."""
        for rs in payload.get("resourceSpans", []):
            for ra in rs.get("resource", {}).get("attributes", []):
                if ra["key"] == "service.version" and not self.claude_code_version:
                    val = ra.get("value", {})
                    self.claude_code_version = val.get("stringValue", "")

            for ss in rs.get("scopeSpans", []):
                for span in ss.get("spans", []):
                    attrs = _parse_span_attrs(span)
                    name = span.get("name", "")
                    start_ns = span.get("startTimeUnixNano")
                    end_ns = span.get("endTimeUnixNano")

                    if start_ns is not None:
                        start_ns = int(start_ns)
                        if self.min_start_ns is None or start_ns < self.min_start_ns:
                            self.min_start_ns = start_ns
                    if end_ns is not None:
                        end_ns = int(end_ns)
                        if self.max_end_ns is None or end_ns > self.max_end_ns:
                            self.max_end_ns = end_ns

                    if not self.session_id:
                        self.session_id = str(attrs.get("session.id", ""))
                    if not self.permission_mode:
                        self.permission_mode = str(attrs.get("permission_mode", ""))

                    if name == "claude_code.llm_request":
                        context = attrs.get("llm_request.context", "")
                        if context == "interaction":
                            self.num_turns += 1
                            if start_ns is not None:
                                if (self.first_interaction_start_ns is None
                                        or start_ns < self.first_interaction_start_ns):
                                    self.first_interaction_start_ns = start_ns
                                    ttft = attrs.get("ttft_ms")
                                    if ttft is not None:
                                        self.first_ttft_ms = int(float(str(ttft)))
                        self.last_stop_reason = str(attrs.get("stop_reason", ""))

                    elif name == "claude_code.tool":
                        tool_name = attrs.get("tool_name", "")
                        if tool_name == "Skill":
                            skill = attrs.get("skill_name", "")
                            if skill:
                                self.skills.append(skill)
                        elif tool_name == "Write":
                            self.files_written += 1
                        elif tool_name == "Agent":
                            self.num_subagents += 1

    def result(self):
        duration_ms = 0
        if self.min_start_ns is not None and self.max_end_ns is not None:
            duration_ms = (self.max_end_ns - self.min_start_ns) // 1_000_000

        return {
            "session_id": self.session_id,
            "claude_code_version": self.claude_code_version,
            "permission_mode": self.permission_mode,
            "duration_ms": duration_ms,
            "ttft_ms": self.first_ttft_ms,
            "num_turns": self.num_turns,
            "stop_reason": self.last_stop_reason,
            "skills": self.skills,
            "files_written": self.files_written,
            "num_subagents": self.num_subagents,
        }


def parse_otel(path):
    """Parse an OTEL JSONL log and return a metrics row dict."""
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
    tool_uses = []
    traces = TraceAccumulator()

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
                        if event_name in ("api_request", "claude_code.api_request"):
                            api_requests.append(event_attrs)
                        elif event_name == "tool_decision":
                            tool = event_attrs.get("tool_name", "")
                            if tool:
                                tool_uses.append(tool)

        elif "/v1/traces" in rpath:
            traces.add(payload)

    total_cost_usd = sum(cost_totals.values())
    input_tokens = int(sum(v for (m, t), v in token_totals.items() if t == "input"))
    output_tokens = int(sum(v for (m, t), v in token_totals.items() if t == "output"))
    cache_read_tokens = int(sum(v for (m, t), v in token_totals.items() if t == "cacheRead"))
    cache_creation_tokens = int(sum(v for (m, t), v in token_totals.items() if t == "cacheCreation"))

    total_input = input_tokens + cache_read_tokens + cache_creation_tokens
    cache_hit_rate = (cache_read_tokens / total_input * 100) if total_input > 0 else 0

    tool_counts = Counter()
    if tool_uses:
        tool_counts.update(tool_uses)
    else:
        for req in api_requests:
            tool = req.get("tool_name", "")
            if tool:
                tool_counts[tool] += 1
    total_tool_calls = sum(tool_counts.values())

    duration_api_s = active_time.get("api", 0)
    model = max(cost_totals, key=cost_totals.get) if cost_totals else ""
    analyzed_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    trace_data = traces.result()
    skills = trace_data.get("skills", [])
    skills_str = ",".join(dict.fromkeys(skills)) if skills else ""

    return {
        "session_id": trace_data.get("session_id", ""),
        "model": model,
        "claude_code_version": trace_data.get("claude_code_version", ""),
        "permission_mode": trace_data.get("permission_mode", ""),
        "entrypoint": "",
        "prompt": "",
        "plugins_loaded": "",
        "analyzed_at": analyzed_at,
        "duration_ms": str(trace_data.get("duration_ms", 0)),
        "duration_api_ms": str(int(duration_api_s * 1000)),
        "ttft_ms": str(trace_data.get("ttft_ms", 0)),
        "num_turns": str(trace_data.get("num_turns", 0)),
        "total_cost_usd": f"{total_cost_usd:.6f}",
        "input_tokens": str(input_tokens),
        "output_tokens": str(output_tokens),
        "cache_read_input_tokens": str(cache_read_tokens),
        "cache_creation_input_tokens": str(cache_creation_tokens),
        "cache_hit_rate_pct": f"{cache_hit_rate:.1f}",
        "total_tool_calls": str(total_tool_calls),
        "tool_call_breakdown": json.dumps(dict(tool_counts.most_common())),
        "skills_invoked": skills_str,
        "files_written": str(trace_data.get("files_written", 0)),
        "num_thinking_blocks": "0",
        "num_subagents": str(trace_data.get("num_subagents", 0)),
        "subagent_total_tool_uses": "0",
        "subagent_total_duration_ms": "0",
        "is_error": "0",
        "terminal_reason": "",
        "stop_reason": trace_data.get("stop_reason", ""),
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

    if not row["entrypoint"]:
        for l in lines:
            if l.get("type") == "user" and l.get("entrypoint"):
                row["entrypoint"] = l["entrypoint"]
                break

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

    if results:
        last_result = results[-1]
        row["duration_ms"] = str(sum(r.get("duration_ms", 0) for r in results))
        row["ttft_ms"] = str(results[0].get("ttft_ms", 0))
        row["num_turns"] = str(sum(r.get("num_turns", 0) for r in results))
        row["is_error"] = str(1 if last_result.get("is_error", False) else 0)
        row["terminal_reason"] = last_result.get("terminal_reason", "")
        row["stop_reason"] = last_result.get("stop_reason", "")

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

    if "--stream-log" in args:
        idx = args.index("--stream-log")
        if idx + 1 < len(args):
            stream_log = args[idx + 1]
            args = args[:idx] + args[idx + 2:]
        else:
            print("ERROR: --stream-log requires a path argument", file=sys.stderr)
            sys.exit(2)

    if not args:
        print(f"Usage: {sys.argv[0]} <otel.jsonl> [output-autodl.json] [--stream-log <claude-output.log>]",
              file=sys.stderr)
        sys.exit(2)

    log_path = args[0]
    output_path = args[1] if len(args) > 1 else "claude-session-metrics-autodl.json"

    row = parse_otel(log_path)
    if stream_log:
        row = enrich_from_stream_log(row, stream_log)

    autodl = build_autodl(row)

    with open(output_path, "w") as f:
        json.dump(autodl, f, indent=4)

    print(f"OK: wrote {output_path}")
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
