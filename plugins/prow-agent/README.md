# prow-agent

Utilities for Claude Code sessions running inside Prow CI jobs.

## Session Metrics

Extracts cost, token, duration, and tool-usage metrics from Claude Code
sessions and writes an autodl JSON file for BigQuery ingestion.

Two collection modes are supported:

### OTEL Collection (Preferred)

An embedded OTLP collector receives structured telemetry directly from
Claude Code, providing per-request granularity, per-model cost breakdown,
and a path to MLflow integration. See
[docs/metrics-collection.md](docs/metrics-collection.md) for the full
design.

```bash
PLUGIN_DIR=$(find ~/.claude/plugins -type d -name "prow-agent" 2>/dev/null | head -1)
OTEL_COLLECTOR="${PLUGIN_DIR}/scripts/otel_collector.py"
EXTRACT_METRICS="${PLUGIN_DIR}/scripts/extract_metrics.py"

# 1. Start collector
OTEL_PORT_FILE=$(mktemp)
OTEL_LOG="${ARTIFACT_DIR}/claude-otel.jsonl"
python3 "${OTEL_COLLECTOR}" \
    --port-file "${OTEL_PORT_FILE}" \
    --log-file "${OTEL_LOG}" &
COLLECTOR_PID=$!
while [ ! -s "${OTEL_PORT_FILE}" ]; do sleep 0.1; done
OTEL_PORT=$(cat "${OTEL_PORT_FILE}")

# 2. Set OTEL env vars
export CLAUDE_CODE_ENABLE_TELEMETRY=1
export OTEL_METRICS_EXPORTER=otlp
export OTEL_LOGS_EXPORTER=otlp
export OTEL_TRACES_EXPORTER=otlp
export OTEL_EXPORTER_OTLP_PROTOCOL=http/json
export OTEL_EXPORTER_OTLP_ENDPOINT="http://127.0.0.1:${OTEL_PORT}"
export OTEL_METRIC_EXPORT_INTERVAL=10000

# 3. Run Claude
claude -p "..." --output-format stream-json | tee "${CLAUDE_OUTPUT_LOG}"

# 4. Stop collector and extract metrics
kill ${COLLECTOR_PID} 2>/dev/null; wait ${COLLECTOR_PID} 2>/dev/null
python3 "${EXTRACT_METRICS}" "${OTEL_LOG}" \
    "${ARTIFACT_DIR}/claude-session-metrics-autodl.json" \
    --stream-log "${CLAUDE_OUTPUT_LOG}"
```

The `--stream-log` flag supplements OTEL metrics with identity fields
(session ID, model, version, prompt) from the stream-json output.

### Legacy Stream-JSON Parsing

The script also accepts a stream-json output log directly (auto-detected):

```bash
python3 "${EXTRACT_METRICS}" "${CLAUDE_OUTPUT_LOG}" \
    "${ARTIFACT_DIR}/claude-session-metrics-autodl.json"
```

For `--continue` workflows, run extraction once after the final
invocation. Each `result` message contains per-invocation totals; the
script sums across all result messages.
