# metrics

Automatic OpenTelemetry and OpenInference telemetry for Claude Code CLI sessions.

This plugin configures an `otelcol-contrib` pipeline that receives Claude Code's native OTLP telemetry, maps it to OpenInference semantic conventions, and writes enriched spans to a local JSONL file and MLflow.

No commands. The `otelcol-contrib` binary starts automatically when a Claude Code session begins and terminates when the session ends via `SessionStart`/`SessionEnd` hooks.

## Architecture

```
Claude Code CLI  (native OTLP emission)
        |
        | OTLP/HTTP  spans + metrics + log events
        v
  otelcol-contrib  (user-level background service)
    receivers:   otlp/http:4318, otlp/grpc:4317
    processors:
      resource          adds service.name, environment, team/repo metadata
      transform         maps Claude Code spans to OpenInference kinds/attributes
      batch
    exporters:
      file              ~/.local/share/claude-metrics/claude-metrics.jsonl
      otlp_http/mlflow  http://localhost:5000 (see MLflow Integration)
        |
        v
  ~/.local/share/claude-metrics/claude-metrics.jsonl
  (queryable with jq, Arize Phoenix, Grafana Tempo, or MLflow)
```

## Setup

After installing the plugin, start a Claude Code session. If setup has not been run you will see a hook error with the exact command to run:

```
metrics plugin: run 'bash /path/to/plugin/scripts/install.sh' once, then restart Claude Code
```

Run that command. It installs `otelcol-contrib` (if needed) and writes the required OTLP env vars into the `env` section of `~/.claude/settings.json`. Then restart Claude Code — the env vars take effect on the next startup.

From that point on, telemetry flows automatically — `otelcol-contrib` starts at session open and stops at session close. Traces are written to `~/.local/share/claude-metrics/claude-metrics.jsonl` and collector logs to `~/.local/share/claude-metrics/otelcol.log`.

To add team/repo context to every span:

```bash
export OTEL_RESOURCE_ATTRIBUTES="team.name=my-team,repo.name=my-repo,agentic_doc.version=$(git rev-parse HEAD)"
```

## MLflow Integration

MLflow export is enabled by default. Start an MLflow server before starting a Claude Code session:

```bash
mlflow server --host 127.0.0.1 --port 5000
```

The collector posts traces to `http://localhost:5000/v1/traces` with `x-mlflow-experiment-id: "0"` (the default experiment). To change the server or experiment, update `config/otelcol.yaml`:

```yaml
otlp_http/mlflow:
  endpoint: http://localhost:5000
  headers:
    x-mlflow-experiment-id: "0"   # "0" = default experiment; use your experiment ID
  tls:
    insecure: true
```

MLflow 3.x accepts OTLP/HTTP traces at `/v1/traces` (gRPC is not supported). The `x-mlflow-experiment-id` header is required — MLflow rejects requests without it. MLflow natively understands OpenInference span kinds and token-count attributes mapped by this pipeline's `transform/openinference` processor.

## What Gets Collected

### Native Claude Code Telemetry

Spans (requires `CLAUDE_CODE_ENHANCED_TELEMETRY_BETA=1`):

| Span name | What it represents | Key attributes |
|---|---|---|
| `claude_code.interaction` | One agent turn (prompt → response) | `session.id`, `prompt_length` |
| `claude_code.llm_request` | One Anthropic API call | `model`, `input_tokens`, `output_tokens`, `cache_read_input_tokens`, `cache_creation_input_tokens`, `latency_ms` |
| `claude_code.tool` | Tool invocation | `tool_name`, `tool_duration_ms` |
| `claude_code.tool.execution` | Actual tool execution | `tool_name`, `tool_duration_ms` |

Metrics (counters):

| Metric name | Labels |
|---|---|
| `claude_code.token.usage` | `token_type`, `model`, `query_source` |
| `claude_code.cost.usage` | `model`, `agent.name`, `skill.name` |
| `claude_code.session.count` | — |
| `claude_code.lines_of_code.count` | `action`, `language` |
| `claude_code.code_edit.tool_decision` | `language`, `decision` |

Log events (always emitted, no prompt/code content by default):

| Event name | Key attributes |
|---|---|
| `claude_code.user_prompt` | `prompt_length`, `session.id`, `prompt.id` |
| `claude_code.tool_result` | `tool_name`, `tool_result_success`, `tool_result_size_bytes`, `tool_duration_ms` |
| `claude_code.api_request` | `cost_usd`, `model`, `status_code`, `latency_ms` |
| `claude_code.api_error` | `error_type`, `error_message`, `model` |

### OpenInference Enrichment Applied by the Pipeline

After the `transform/openinference` processor, spans also carry:

| Attribute | Value |
|---|---|
| `openinference.span.kind` | `CHAIN` (interaction), `LLM` (llm_request), `TOOL` (tool/tool.execution) |
| `llm.model_name` | Model name (copied from `model`) |
| `llm.token_count.prompt` | Input tokens |
| `llm.token_count.completion` | Output tokens |
| `llm.token_count.total` | Input + output |
| `llm.token_count.prompt_details.cache_read` | Cache-read tokens |
| `llm.token_count.prompt_details.cache_write` | Cache-creation tokens |
| `tool.name` | Tool name (copied from `tool_name`) |
| `agent.name` | `claude-code` |

## Core Metrics by Category

### Documentation Effectiveness

Derived from span attribute correlations: sessions with agentic documentation loaded (CLAUDE.md, AGENTS.md detected as `claude_code.tool` Read spans) vs. task outcomes.

Key signals: `claude_code.code_edit.tool_decision` (accept/reject rates by language), `claude_code.cost.usage` per task type, tool call sequences relative to documentation presence.

### Agent Performance

- Task completion: `claude_code.session.count` over time, error events in `claude_code.api_error`
- Execution efficiency: `tool_duration_ms` distribution from `claude_code.tool` spans, `claude_code.lines_of_code.count`
- Failure modes: `tool_result_success=false` from `claude_code.tool_result` log events

### Model Performance

- Latency: `latency_ms` on `claude_code.llm_request` spans
- Token efficiency: `llm.token_count.prompt_details.cache_read` vs. `llm.token_count.prompt` (cache hit ratio)
- Cost: `claude_code.cost.usage` counter by model

### Productivity

- `claude_code.lines_of_code.count` with `action=add` and `action=remove`
- `claude_code.code_edit.tool_decision` with `decision=accept`

## MLflow Dashboards

The following dashboards can be built in MLflow's experiment tracking UI:

1. Executive Agent Adoption — sessions, tasks completed, cost, productivity impact
2. Agentic Documentation Intelligence — documentation usage rate, unused sections, failing documentation versions
3. Agent Performance — completion rate, latency, retries, tool efficiency
4. AI Cost — cost per repository, cost per task type, token trends
5. Agent Reliability — failure modes, permission failures, looping behavior, regression patterns

## Data Retention

| Data type | Retention |
|---|---|
| Raw traces (file exporter) | 30 days (controlled by `max_days: 30` rotation in otelcol config) |
| Metrics (MLflow) | 1 year |
| Aggregated productivity metrics | 3+ years |

Prompt text, tool input/output, and source code content are opt-in — set `OTEL_LOG_USER_PROMPTS=1`, `OTEL_LOG_TOOL_DETAILS=1`, and `OTEL_LOG_TOOL_CONTENT=1` (all enabled by `scripts/install.sh`). No additional filtering is applied by this pipeline.

## Environment Variables Reference

Set by `scripts/install.sh` in the `env` section of `~/.claude/settings.json` — no manual configuration needed.

| Variable | Value | Purpose |
|---|---|---|
| `CLAUDE_CODE_ENABLE_TELEMETRY` | `1` | Master enable switch |
| `CLAUDE_CODE_ENHANCED_TELEMETRY_BETA` | `1` | Enable distributed tracing (spans) |
| `OTEL_TRACES_EXPORTER` | `otlp` | Export traces via OTLP |
| `OTEL_METRICS_EXPORTER` | `otlp` | Export metrics via OTLP |
| `OTEL_LOGS_EXPORTER` | `otlp` | Export log events via OTLP |
| `OTEL_EXPORTER_OTLP_PROTOCOL` | `http/protobuf` | Transport protocol |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | `http://127.0.0.1:4318` | Collector endpoint |
| `OTEL_SERVICE_NAME` | `claude-code-agent` | Service name in traces |
| `OTEL_LOG_USER_PROMPTS` | `1` | Include prompt text in `claude_code.interaction` spans (`input.value` in MLflow) |
| `OTEL_LOG_TOOL_DETAILS` | `1` | Include tool input arguments (file paths, commands) in `claude_code.tool` spans (`input.value` in MLflow) |
| `OTEL_LOG_TOOL_CONTENT` | `1` | Include full tool input/output bodies as span events on `claude_code.tool` (`output.value` in MLflow) |
| `OTEL_LOG_RAW_API_BODIES` | `1` | Include full Anthropic API request/response JSON as log events |

Optional overrides:

| Variable | Purpose |
|---|---|
| `OTEL_RESOURCE_ATTRIBUTES` | Adds team.name, repo.name, agentic_doc.version to every signal |
| `OTEL_METRIC_EXPORT_INTERVAL` | Metrics export interval in ms (default: 60000) |
| `OTEL_LOGS_EXPORT_INTERVAL` | Log events export interval in ms (default: 5000) |
| `OTEL_TRACES_EXPORT_INTERVAL` | Traces export interval in ms (default: 5000) |

## References

- OpenInference semantic conventions: https://arize-ai.github.io/openinference/spec/semantic_conventions.html
- Claude Code telemetry documentation: https://code.claude.com/docs/en/agent-sdk/observability
- otelcol-contrib transform processor (OTTL): https://github.com/open-telemetry/opentelemetry-collector-contrib/tree/main/processor/transformprocessor
