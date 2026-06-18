# Metrics Plugin

Local OTEL telemetry collection for Claude Code sessions. Captures tokens, cost, timing, and tool usage per session — all data stays on your machine.

## One-Time Setup

Add to `~/.claude/settings.json`:

```json
{
  "env": {
    "CLAUDE_CODE_ENABLE_TELEMETRY": "1",
    "OTEL_METRICS_EXPORTER": "otlp",
    "OTEL_LOGS_EXPORTER": "otlp",
    "OTEL_EXPORTER_OTLP_PROTOCOL": "http/json",
    "OTEL_EXPORTER_OTLP_ENDPOINT": "http://127.0.0.1:4318",
    "OTEL_METRIC_EXPORT_INTERVAL": "10000"
  }
}
```

Port `4318` is the standard OTLP HTTP port. The `SessionStart` hook starts `collector.py` on this port automatically.

## How It Works

```
Claude Code  →  HTTP POST every 10s  →  collector.py (port 4318)
                                              ↓ appends records
                                        otel-current.jsonl
                                              ↓ on SessionEnd
                                          ingest.py
                                              ↓
                                    <session-id>.json
```

## Scripts

- **`scripts/collector.py`** — Minimal OTLP HTTP/JSON receiver. Listens on port 4318, appends each payload to `otel-current.jsonl`. Runs as a background daemon via the `SessionStart` hook; stopped cleanly by `SessionEnd`.

- **`scripts/ingest.py`** — Reads `otel-current.jsonl`, extracts structured metrics, writes a JSON file. Consumes three OTEL metric names only: `claude_code.token.usage`, `claude_code.cost.usage`, `claude_code.active_time.total`, and `tool_decision` log events.

## Output Format

```json
{
  "ingested_at": "2026-06-19T12:34:56Z",
  "session_start": "2026-06-19T12:00:00Z",
  "session_end": "2026-06-19T12:34:50Z",
  "model": "claude-sonnet-4-6",
  "cost_usd": 0.047,
  "tokens": {
    "input": 42500,
    "output": 8200,
    "cache_read": 30000,
    "cache_creation": 12500,
    "cache_hit_rate": 0.7143
  },
  "timing": {
    "api_s": 43.2,
    "tool_execution_s": 18.6
  },
  "tools": {
    "total": 84,
    "breakdown": {"Read": 32, "Edit": 18, "Bash": 24, "Grep": 10}
  }
}
```

## Manual Usage

```bash
# Start collector (foreground)
python3 plugins/metrics/scripts/collector.py

# Start as daemon
python3 plugins/metrics/scripts/collector.py --daemon --fresh

# Stop running collector
python3 plugins/metrics/scripts/collector.py --stop

# Ingest OTEL data
python3 plugins/metrics/scripts/ingest.py \
  --otel-log plugins/metrics/otel-current.jsonl \
  --out /tmp/session-metrics.json
```

## Enabling the Plugin

```bash
/plugin enable metrics@ai-helpers
```

## Source Code

- `plugins/metrics/hooks/hooks.json` — SessionStart/SessionEnd hook definitions
- `plugins/metrics/scripts/collector.py` — OTLP HTTP receiver
- `plugins/metrics/scripts/ingest.py` — OTEL JSONL → metrics JSON
- `plugins/metrics/.claude-plugin/plugin.json` — plugin metadata
