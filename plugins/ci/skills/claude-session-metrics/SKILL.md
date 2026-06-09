---
name: claude-session-metrics
description: Extract cost, token, duration, and tool-usage metrics from a claude-output.log and produce an autodl JSON file for BigQuery ingestion
---

# Claude Session Metrics

Extract metrics from a `claude-output.log` file and produce an autodl JSON file suitable for BigQuery ingestion. The script does all the work — just run it on the log file.

## When to Use This Skill

Use this skill after a CI job that runs Claude Code completes, to produce a metrics autodl file from the `claude-output.log` artifact. The autodl file feeds a Grafana dashboard that tracks agent cost, token usage, and performance over time.

## Implementation Steps

### Step 1: Locate the claude-output.log

The log file is the JSONL streaming output produced by `claude -p`. In CI, it is typically at:

```
artifacts/claude-output.log
```

### Step 2: Run the extraction script

```bash
EXTRACT_METRICS="${CLAUDE_PLUGIN_ROOT}/skills/claude-session-metrics/scripts/extract_metrics.py"
if [ ! -f "$EXTRACT_METRICS" ]; then
  EXTRACT_METRICS=$(find ~/.claude/plugins -type f -path "*/ci/skills/claude-session-metrics/scripts/extract_metrics.py" 2>/dev/null | sort | head -1)
fi
if [ -z "$EXTRACT_METRICS" ] || [ ! -f "$EXTRACT_METRICS" ]; then echo "ERROR: extract_metrics.py not found" >&2; exit 2; fi
python3 "$EXTRACT_METRICS" <claude-output.log> [output-autodl.json]
```

If the output path is omitted, writes to `claude-session-metrics-autodl.json` in the current directory.

The script reads the `result` message from the log, which contains aggregate cost and token data including all subagents. It also parses individual assistant messages to count tool calls, skills invoked, and thinking blocks.

### Step 3: Report the results

Print a summary of the key metrics to the user:

- Total cost (USD)
- Duration (seconds)
- Model used
- Token breakdown (input, output, cache read, cache creation)
- Cache hit rate
- Number of tool calls and subagents

## Output Schema

The autodl JSON uses table name `claude_session_metrics`. One row per prow job run.

| Field | Type | Description |
|-------|------|-------------|
| `session_id` | string | Claude session UUID |
| `model` | string | Model used (e.g. `claude-opus-4-6`) |
| `claude_code_version` | string | CLI version |
| `permission_mode` | string | Permission mode (`default`, `plan`, etc.) |
| `entrypoint` | string | How the session was started (`sdk-cli`, etc.) |
| `prompt` | string | The initial prompt or skill invocation (truncated to 500 chars) |
| `plugins_loaded` | string | Comma-separated list of loaded plugins |
| `analyzed_at` | string | ISO 8601 timestamp of when metrics were extracted |
| `duration_ms` | int64 | Wall-clock duration in milliseconds |
| `duration_api_ms` | int64 | Time spent in API calls |
| `ttft_ms` | int64 | Time to first token |
| `num_turns` | int64 | Number of conversation turns |
| `total_cost_usd` | float64 | Total cost including subagents |
| `input_tokens` | int64 | Input tokens (uncached) |
| `output_tokens` | int64 | Output tokens |
| `cache_read_input_tokens` | int64 | Tokens served from cache |
| `cache_creation_input_tokens` | int64 | Tokens written to cache |
| `cache_hit_rate_pct` | float64 | `cache_read / (cache_read + cache_create + input) * 100` |
| `total_tool_calls` | int64 | Total tool invocations (main session only) |
| `tool_call_breakdown` | string | JSON object of `{tool_name: count}` |
| `skills_invoked` | string | Comma-separated list of skills used |
| `files_written` | int64 | Number of files written via the Write tool |
| `num_thinking_blocks` | int64 | Number of extended thinking blocks |
| `num_subagents` | int64 | Number of subagents spawned |
| `subagent_total_tool_uses` | int64 | Aggregate tool calls across all subagents |
| `subagent_total_duration_ms` | int64 | Aggregate subagent wall-clock time |
| `is_error` | int64 | `1` if the session errored, `0` otherwise |
| `terminal_reason` | string | `completed`, `error`, `timeout`, etc. |
| `stop_reason` | string | `end_turn`, `tool_use`, `max_tokens` |
