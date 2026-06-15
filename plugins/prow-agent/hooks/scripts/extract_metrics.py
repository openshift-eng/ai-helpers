#!/usr/bin/env python3
"""Extract Claude session metrics from claude-output.log and produce an autodl JSON file.

Parses the streaming JSONL output from one or more `claude -p` invocations
(including --continue runs that share a session) and emits a single autodl
JSON row aggregating cost, tokens, duration, tool usage, and other metrics.

Usage:
    python3 extract_metrics.py <claude-output.log> [output-autodl.json]

If the output path is omitted, writes to claude-session-metrics-autodl.json
in the current directory.
"""

import json
import sys
from collections import Counter
from datetime import datetime, timezone


def parse_log(path):
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
    result = results[-1]

    # --- Identity ---
    session_id = init.get("session_id", result.get("session_id", ""))
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
    # The prompt comes from queue-operation/enqueue in the output log,
    # or from the first assistant text if running via claude -p
    for l in lines:
        if l.get("type") == "queue-operation" and l.get("operation") == "enqueue":
            prompt = l.get("content", "")
            break
    # If no queue-operation, infer from the first skill invocation or assistant text
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

    # --- Duration ---
    duration_ms = result.get("duration_ms", 0)
    duration_api_ms = result.get("duration_api_ms", 0)
    ttft_ms = result.get("ttft_ms", 0)
    num_turns = result.get("num_turns", 0)

    # --- Cost & tokens (modelUsage includes subagents) ---
    model_usage = result.get("modelUsage", {})
    total_cost_usd = result.get("total_cost_usd", 0.0)
    input_tokens = 0
    output_tokens = 0
    cache_read_tokens = 0
    cache_creation_tokens = 0
    for mu in model_usage.values():
        input_tokens += mu.get("inputTokens", 0)
        output_tokens += mu.get("outputTokens", 0)
        cache_read_tokens += mu.get("cacheReadInputTokens", 0)
        cache_creation_tokens += mu.get("cacheCreationInputTokens", 0)

    total_input = input_tokens + cache_read_tokens + cache_creation_tokens
    cache_hit_rate = (cache_read_tokens / total_input * 100) if total_input > 0 else 0

    # --- Tool usage (from assistant messages) ---
    # Deduplicate by tool_use id — each content block gets its own JSONL line,
    # but the same tool_use block (same id) should only be counted once.
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

    # --- Subagents ---
    task_starts = [l for l in lines if l.get("subtype") == "task_started"]
    task_notifications = [l for l in lines if l.get("subtype") == "task_notification"]
    num_subagents = len(task_starts)
    subagent_total_tool_uses = sum(t.get("usage", {}).get("tool_uses", 0) for t in task_notifications)
    subagent_total_duration_ms = sum(t.get("usage", {}).get("duration_ms", 0) for t in task_notifications)

    # --- Outcome ---
    is_error = 1 if result.get("is_error", False) else 0
    terminal_reason = result.get("terminal_reason", "")
    stop_reason = result.get("stop_reason", "")

    # --- Timestamps ---
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
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <claude-output.log> [output-autodl.json]", file=sys.stderr)
        sys.exit(2)

    log_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else "claude-session-metrics-autodl.json"

    row = parse_log(log_path)
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
