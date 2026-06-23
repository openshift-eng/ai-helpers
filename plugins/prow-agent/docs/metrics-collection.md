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

Each agent uses `agentic-ci run --backend local` to execute Claude Code
with automatic OTEL telemetry collection. The
[prow-agent](https://github.com/openshift-eng/ai-helpers/tree/main/plugins/prow-agent)
plugin provides `extract_metrics.py` for producing BigQuery autodl from
the collected OTEL data.

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

## Approach: OpenTelemetry via agentic-ci

[agentic-ci](https://github.com/opendatahub-io/agentic-ci) manages the
OTEL collector lifecycle automatically. Each `agentic-ci run` starts an
ephemeral OTLP HTTP collector, configures the Claude Code OTEL env vars,
and writes telemetry to a JSONL file. For multi-invocation flows (e.g.
main analysis → nudge → validation retries), the per-run JSONL files are
concatenated into a single log for metrics extraction.

```
┌───────────────────────────────────────────────────────┐
│  Prow Job Container                                   │
│                                                       │
│  ┌──────────────┐                                     │
│  │ agentic-ci   │ starts/stops OTEL collector per run │
│  │ run --backend│                                     │
│  │ local        │                                     │
│  │  ┌──────────┐│     OTLP/HTTP       ┌─────────────┐│
│  │  │Claude    ││ ──────────────────▶ │  OTEL       ││
│  │  │Code      ││   metrics/logs/     │  Collector  ││
│  │  │          ││   traces @ 10s      │  (agentic-  ││
│  │  └──────────┘│                     │   ci)       ││
│  └──────────────┘                     └──────┬──────┘│
│                                              │        │
│                                     ┌────────▼──────┐ │
│                                     │ claude-otel   │ │
│                                     │   .jsonl      │ │
│                                     └────────┬──────┘ │
│                                              │        │
│                        ┌─────────────────────┼        │
│                        │                     │        │
│                 ┌──────▼──────┐     ┌────────▼────┐   │
│                 │ autodl JSON │     │ Raw OTEL    │   │
│                 │ → BigQuery  │     │ JSONL       │   │
│                 └─────────────┘     │ → Artifact  │   │
│                                     │ → MLflow    │   │
│                                     └─────────────┘   │
│                                                       │
└───────────────────────────────────────────────────────┘
```

### What OTEL Provides

Claude Code emits structured telemetry when
`CLAUDE_CODE_ENABLE_TELEMETRY=1` is set (configured automatically by
agentic-ci):

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

### CI Step Lifecycle

```bash
# agentic-ci manages OTEL collector per invocation
OTEL_LOG="${ARTIFACT_DIR}/claude-otel.jsonl"

run_claude() {
    local prompt="$1"; shift
    agentic-ci run --backend local --harness claude-code \
        --model "${CLAUDE_MODEL}" --workdir "${WORKDIR}" \
        "${prompt}" -- --allowedTools "${ALLOWED_TOOLS}" --verbose "$@"
    local rc=$?
    # Concatenate per-invocation OTEL JSONL
    for f in /tmp/agentic-ci-run.*/claude-otel.jsonl; do
        [ -f "$f" ] && cat "$f" >> "${OTEL_LOG}"
    done
    rm -rf /tmp/agentic-ci-run.*
    return $rc
}

# Run agent (may include --continue invocations)
run_claude "Analyze payload" --max-turns 100
run_claude "Wrap up" --continue --max-turns 20

# Generate BigQuery autodl from collected OTEL data
python3 "${EXTRACT_METRICS}" "${OTEL_LOG}" \
    "${ARTIFACT_DIR}/claude-session-metrics-autodl.json"
```

### BigQuery autodl Generation

`extract_metrics.py` parses the OTEL JSONL and produces an autodl JSON
file for the `claude_session_metrics` BigQuery table. Cost, tokens, tool
usage, and timing come from OTEL metrics and logs.

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
| `scripts/extract_metrics.py` | Parses OTEL JSONL → autodl JSON for BigQuery |
| `scripts/test_extract_metrics.py` | Extract tests: OTEL parsing paths |
| `scripts/testdata/otel_metrics.jsonl` | Test fixture with sample OTLP payloads |

The autodl schema (`claude_session_metrics` table) is unchanged — no
BigQuery migration needed.
