# metrics

Automatic OpenTelemetry and OpenInference telemetry for Claude Code CLI sessions.

This plugin configures an `otelcol-contrib` pipeline that receives Claude Code's native OTLP telemetry, maps it to OpenInference semantic conventions, filters sensitive content, and writes enriched spans to a local JSONL file. It optionally exports to MLflow.

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
      filter/privacy    drops accidental raw content
      batch
    exporters:
      file              ~/.local/share/claude-metrics/claude-metrics.jsonl
      otlp/mlflow       optional, uncomment in config/otelcol.yaml
        |
        v
  ~/.local/share/claude-metrics/claude-metrics.jsonl
  (queryable with jq, Arize Phoenix, Grafana Tempo, or MLflow)
```

## Setup

Run the install script once after installing the plugin:

```bash
bash ~/.claude/plugins/cache/ai-helpers/metrics/*/scripts/install.sh
```

This installs `otelcol-contrib` and adds the required OTLP env vars to your shell profile. Then source your profile (the script prints the exact command) before starting Claude Code.

From that point on, telemetry flows automatically — `otelcol-contrib` starts at session open and stops at session close. Traces are written to `~/.local/share/claude-metrics/claude-metrics.jsonl` and collector logs to `~/.local/share/claude-metrics/otelcol.log`.

To add team/repo context to every span:

```bash
export OTEL_RESOURCE_ATTRIBUTES="team.name=my-team,repo.name=my-repo,agentic_doc.version=$(git rev-parse HEAD)"
```

## MLflow Integration

Uncomment the `otlp/mlflow` exporter and the MLflow exporter in the service pipelines inside `config/otelcol.yaml`, then set the endpoint to your MLflow tracking server:

```yaml
otlp/mlflow:
  endpoint: http://localhost:5000/api/2.0/mlflow/otlp
  tls:
    insecure: true
```

MLflow 2.x supports OTLP trace ingestion natively at `/api/2.0/mlflow/otlp`.

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

### Privacy

No prompt text, tool input, tool output, or source code content is collected by default. The `filter/privacy` processor drops any span or log record that accidentally contains a `prompt`, `tool_input`, or `tool_output` attribute (these are off by default in Claude Code and require explicit opt-in env vars to enable).

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

When the `otlp/mlflow` exporter is enabled, the following dashboards can be built in MLflow's experiment tracking UI:

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

Raw prompts, source code, tool I/O, and credentials are never stored.

## Environment Variables Reference

Set by `scripts/install.sh` — no manual configuration needed.

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
