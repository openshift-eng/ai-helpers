# Metrics Collection for Prow Agents

## Background

### What are Prow Agents?

Prow agents are autonomous Claude Code sessions that run inside OpenShift
CI (Prow) jobs. They perform tasks that require AI reasoning — analyzing
payload failures, triaging regressions, generating reports — and produce
structured artifacts for downstream consumption. A growing number of
teams run prow agents for various CI workflows, and new agents are being
created regularly as adoption grows
([ai-helpers PR #532](https://github.com/openshift-eng/ai-helpers/pull/532)
adds a skill to scaffold new agents).

Each agent runs `claude -p` (and sometimes `--continue` for retry /
summarization) with `--output-format stream-json`. The
[prow-agent](https://github.com/openshift-eng/ai-helpers/tree/main/plugins/prow-agent)
plugin provides shared utilities for these CI sessions. As the fleet of
agents grows, the need for centralized observability becomes critical.

### Why Measure?

Without metrics, prow agents are black boxes. We need visibility into:

- **Cost attribution** — Which agents cost the most? Which skills drive
  token consumption? Are costs trending up or down as we iterate on
  prompts? Can we attribute cost to specific models (Opus vs Sonnet)?

- **Performance monitoring** — How long do sessions take? What's the
  time-to-first-token? How much time is spent in API calls vs tool
  execution? Are cache hit rates improving?

- **Behavioral patterns** — Which tools and skills are used most
  frequently? How many subagents are spawned? How many turns does the
  model take? Are there patterns that indicate the agent is stuck or
  looping?

- **Ongoing evaluation** — Unlike traditional tests, AI agent behavior is
  non-deterministic. Metrics enable continuous evaluation: tracking whether
  prompt changes actually improve outcomes, catching regressions in cost
  or quality, and comparing model performance. This complements the
  point-in-time evaluation provided by
  [agent-eval-harness](https://github.com/opendatahub-io/agent-eval-harness)
  with production-level signal.

## What is Autodl?

Autodl is the ingestion format for the team's BigQuery data pipeline. An
autodl JSON file declares a table name, schema, and rows:

```json
{
    "table_name": "claude_session_metrics",
    "schema": {
        "session_id": "string",
        "total_cost_usd": "float64",
        "input_tokens": "int64",
        ...
    },
    "rows": [{ "session_id": "abc-123", "total_cost_usd": "0.125", ... }]
}
```

Files matching `*-autodl.json` in the Prow artifact directory are
automatically picked up by the pipeline and loaded into BigQuery. This
is the same mechanism used for payload triage data
(`payload_triage` table) and other CI artifacts.

## Approach: OpenTelemetry Collection

An embedded OTLP (OpenTelemetry) collector receives structured telemetry
directly from Claude Code. This is the same approach used by
[agentic-ci](https://github.com/opendatahub-io/agentic-ci), adapted for
our Prow environment and BigQuery pipeline.

Stream-json parsing is still supported as a fallback (auto-detected),
but OTEL is preferred because it provides per-request granularity,
tool execution timing, and decouples metrics from the output format.

```
┌─────────────────────────────────────────────────────┐
│  Prow Job Container                                 │
│                                                     │
│  ┌──────────────┐     OTLP/HTTP      ┌───────────┐ │
│  │  Claude Code  │ ──────────────────▶│  OTEL     │ │
│  │  (agent)      │  metrics/logs/     │  Collector │ │
│  │               │  traces @ 10s      │  (Python)  │ │
│  └──────────────┘                     └─────┬─────┘ │
│                                             │       │
│                                    ┌────────▼──────┐│
│                                    │ claude-otel   ││
│                                    │   .jsonl      ││
│                                    └────────┬──────┘│
│                                             │       │
│                        ┌────────────────────┼───────┤
│                        │                    │       │
│                 ┌──────▼──────┐    ┌────────▼──────┐│
│                 │ autodl JSON │    │ Raw OTEL JSONL ││
│                 │ → BigQuery  │    │ → Artifact     ││
│                 └─────────────┘    │ → MLflow (TBD) ││
│                                    └───────────────┘│
└─────────────────────────────────────────────────────┘
```

### What OTEL Provides

Claude Code emits structured telemetry when
`CLAUDE_CODE_ENABLE_TELEMETRY=1` is set:

**Metrics** (`/v1/metrics`, pushed every 10 seconds):

| Metric | Attributes | Value |
|--------|-----------|-------|
| `claude_code.token.usage` | `model`, `type` (input/output/cacheRead/cacheCreation) | Token count |
| `claude_code.cost.usage` | `model` | USD cost |
| `claude_code.active_time.total` | `type` (api, tool_execution, etc.) | Seconds |

**Logs** (`/v1/logs`, per API request):

| Event | Attributes |
|-------|-----------|
| `claude_code.api_request` | `model`, `duration_ms`, `tool_name`, `tool_input`, `prompt` (with enhanced telemetry) |

**Traces** (`/v1/traces`):

Distributed trace spans covering the full session lifecycle.

### Collector Design

A minimal Python HTTP server (no external dependencies) that accepts OTLP
payloads and writes them to a JSONL file. Based on the
[agentic-ci implementation](https://github.com/opendatahub-io/agentic-ci/blob/main/src/agentic_ci/otel.py):

```python
class OTLPHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        # Accept POST on /v1/metrics, /v1/logs, /v1/traces
        # Parse JSON body
        # Append {ts, path, payload} to JSONL log file
        # Return 200 {"partialSuccess": {}}
```

Key design decisions:
- **Ephemeral port** (`0`) with port file for discovery — avoids conflicts
- **127.0.0.1 binding** — no network exposure
- **1MB max payload** — prevents memory issues
- **No external dependencies** — stdlib only (`http.server`, `json`)

### Environment Variables

Set on Claude Code before invocation:

```bash
export CLAUDE_CODE_ENABLE_TELEMETRY=1
export OTEL_METRICS_EXPORTER=otlp
export OTEL_LOGS_EXPORTER=otlp
export OTEL_TRACES_EXPORTER=otlp
export OTEL_EXPORTER_OTLP_PROTOCOL=http/json
export OTEL_EXPORTER_OTLP_ENDPOINT=http://127.0.0.1:${OTEL_PORT}
export OTEL_METRIC_EXPORT_INTERVAL=10000
export CLAUDE_CODE_ENHANCED_TELEMETRY_BETA=1
export OTEL_LOG_USER_PROMPTS=1
export OTEL_LOG_TOOL_DETAILS=1
export OTEL_LOG_TOOL_CONTENT=1
```

### CI Step Lifecycle

```bash
# 1. Start collector
OTEL_PORT_FILE=$(mktemp)
OTEL_LOG="${ARTIFACT_DIR}/claude-otel.jsonl"
python3 "${OTEL_COLLECTOR}" \
    --port-file "${OTEL_PORT_FILE}" \
    --log-file "${OTEL_LOG}" &
COLLECTOR_PID=$!

# Wait for port
while [ ! -s "${OTEL_PORT_FILE}" ]; do sleep 0.1; done
OTEL_PORT=$(cat "${OTEL_PORT_FILE}")

# 2. Set OTEL env vars (see above)

# 3. Run Claude (may include --continue invocations)
claude -p "..." --output-format stream-json ...

# 4. Stop collector
kill ${COLLECTOR_PID} 2>/dev/null; wait ${COLLECTOR_PID} 2>/dev/null

# 5. Generate BigQuery autodl from OTEL data
python3 "${EXTRACT_METRICS}" "${OTEL_LOG}" \
    "${ARTIFACT_DIR}/claude-session-metrics-autodl.json"
```

### BigQuery autodl Generation

`extract_metrics.py` parses the OTEL JSONL and produces an autodl JSON
file for the `claude_session_metrics` BigQuery table. Cost, tokens, tool
usage, and timing come from OTEL metrics and logs.

Identity fields (`session_id`, `model`, `claude_code_version`, `prompt`,
etc.) are not available in OTEL data, so they are read from the
stream-json log via `--stream-log`. The stream-json output is still
written for Slack summary extraction and real-time build log visibility.

### Raw OTEL JSONL as Artifact

The `claude-otel.jsonl` file is saved to `${ARTIFACT_DIR}` alongside
other Prow artifacts. This provides:

1. **Immediate value**: Per-request debugging — when a session is
   expensive, inspect individual API calls to understand why.

2. **Future MLflow integration**: When a centralized MLflow instance is
   available, a post-step can push `claude-otel.jsonl` traces to MLflow
   for aggregation, comparison, and visualization across runs. This is
   the same pattern used by agentic-ci (`agentic-ci mlflow-push`).

3. **Retention**: Prow artifacts are retained per the cluster's GCS
   retention policy, providing historical telemetry without additional
   infrastructure.

### Centralized MLflow (Future)

The OTEL JSONL format is the bridge to centralized observability. When an
MLflow tracking server is available:

```bash
# Post-step (future)
agentic-ci mlflow-push "${ARTIFACT_DIR}/claude-otel.jsonl" \
    --endpoint "${MLFLOW_TRACKING_URI}" \
    --experiment "prow-agents"
```

This enables:
- Cross-run cost comparison (same agent over time)
- Cross-agent comparison (payload-agent vs eval-agent)
- Per-model cost attribution across the fleet
- Trace-level drill-down into individual sessions
- Annotation and feedback loops for evaluation

The autodl/BigQuery pipeline remains the source of truth for aggregate
metrics. MLflow adds trace-level observability on top.

## Implementation

### Files

| File | Purpose |
|------|---------|
| `scripts/otel_collector.py` | OTLP HTTP server — starts on ephemeral port, writes JSONL |
| `scripts/extract_metrics.py` | Parses OTEL JSONL (or legacy stream-json) → autodl JSON for BigQuery |
| `scripts/test_otel_collector.py` | Collector tests: lifecycle, parsing, summary |
| `scripts/test_extract_metrics.py` | Extract tests: both OTEL and stream-json paths |
| `scripts/testdata/otel_metrics.jsonl` | Test fixture with sample OTLP payloads |

The autodl schema (`claude_session_metrics` table) is unchanged — no
BigQuery migration needed.

## Open Questions

1. **Should the agent-eval step also use the collector?** The eval harness
   has its own cost tracking via `RunResult.cost_usd`. Adding OTEL
   collection there would give per-request visibility into eval runs too.

2. **OTEL data volume.** With `OTEL_LOG_TOOL_CONTENT=1`, the JSONL can
   get large (tool outputs are included). Should we default to
   `OTEL_LOG_TOOL_CONTENT=0` for production runs and only enable it for
   debugging?

3. **Identity fields.** Session ID, model, version, and prompt are
   currently extracted from the stream-json `init` message. Should we
   continue reading both files, or find these in OTEL resource attributes?
