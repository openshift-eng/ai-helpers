# metrics

Automatic OpenTelemetry and OpenInference telemetry for Claude Code CLI sessions.

Receives Claude Code's native OTLP telemetry, maps it to OpenInference semantic conventions, and writes enriched spans to a local JSONL file and MLflow.

No commands. `otelcol-contrib` starts automatically on `SessionStart` and stops on `SessionEnd`.

## Architecture

```
Claude Code CLI
        | OTLP/HTTP (spans + metrics + logs)
        v
  otelcol-contrib
    receivers:   otlp/http:4318, otlp/grpc:4317
    processors:  resource → transform/openinference → batch
    exporters:   file  → ~/.local/share/claude-metrics/claude-metrics.jsonl
                 mlflow → http://localhost:5001
```

## Setup

After installing the plugin, start a Claude Code session. If setup hasn't run you'll see:

```
metrics plugin: run 'bash /path/to/plugin/scripts/install.sh' once, then restart Claude Code
```

Run that command — it installs `otelcol-contrib` and writes the required OTLP env vars to `~/.claude/settings.json`. Restart Claude Code. Traces are written to `~/.local/share/claude-metrics/claude-metrics.jsonl`; collector logs to `~/.local/share/claude-metrics/otelcol.log`.

To add team/repo context to every span:

```bash
export OTEL_RESOURCE_ATTRIBUTES="team.name=my-team,repo.name=my-repo,agentic_doc.version=$(git rev-parse HEAD)"
```

## MLflow Integration

MLflow export is enabled by default. Start MLflow before a Claude Code session:

```bash
mlflow server --host 127.0.0.1 --port 5001
```

To change the server or experiment, edit `config/otelcol.yaml`:

```yaml
otlp_http/mlflow:
  endpoint: http://localhost:5001   # base URL only — otelcol appends /v1/traces
  headers:
    x-mlflow-experiment-id: "0"    # "0" = default experiment
```

MLflow 3.x accepts OTLP/HTTP at `/v1/traces` (gRPC not supported). The `x-mlflow-experiment-id` header is required.

## What Gets Collected

Spans (requires `CLAUDE_CODE_ENHANCED_TELEMETRY_BETA=1`):

| Span | What it represents |
|---|---|
| `claude_code.interaction` | One agent turn (prompt → response) |
| `claude_code.llm_request` | One Anthropic API call — `model`, `input_tokens`, `output_tokens`, `latency_ms` |
| `claude_code.tool` | Tool invocation — `tool_name`, `tool_duration_ms` |
| `claude_code.tool.execution` | Actual tool execution |

Metrics: `claude_code.token.usage`, `claude_code.cost.usage`, `claude_code.session.count`, `claude_code.lines_of_code.count`, `claude_code.code_edit.tool_decision`.

Log events: `claude_code.user_prompt`, `claude_code.tool_result`, `claude_code.api_request`, `claude_code.api_error`.

The `transform/openinference` processor maps these to `openinference.span.kind`, `llm.token_count.*`, `tool.name`, and `input/output.value` — see `config/otelcol.yaml` for the full mapping.

## Environment Variables

Set by `scripts/install.sh` — no manual configuration needed.

| Variable | Value |
|---|---|
| `CLAUDE_CODE_ENABLE_TELEMETRY` | `1` |
| `CLAUDE_CODE_ENHANCED_TELEMETRY_BETA` | `1` |
| `OTEL_TRACES_EXPORTER` | `otlp` |
| `OTEL_METRICS_EXPORTER` | `otlp` |
| `OTEL_LOGS_EXPORTER` | `otlp` |
| `OTEL_EXPORTER_OTLP_PROTOCOL` | `http/protobuf` |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | `http://127.0.0.1:4318` |
| `OTEL_SERVICE_NAME` | `claude-code-agent` |
| `OTEL_LOG_USER_PROMPTS` | `1` — prompt text in spans |
| `OTEL_LOG_TOOL_DETAILS` | `1` — tool input arguments |
| `OTEL_LOG_TOOL_CONTENT` | `1` — full tool input/output bodies |
| `OTEL_LOG_RAW_API_BODIES` | `1` — Anthropic API request/response JSON |

Optional: `OTEL_RESOURCE_ATTRIBUTES`, `OTEL_METRIC_EXPORT_INTERVAL`, `OTEL_LOGS_EXPORT_INTERVAL`, `OTEL_TRACES_EXPORT_INTERVAL`.

## References

- [OpenInference semantic conventions](https://arize-ai.github.io/openinference/spec/semantic_conventions.html)
- [Claude Code telemetry](https://code.claude.com/docs/en/agent-sdk/observability)
- [otelcol-contrib transform processor (OTTL)](https://github.com/open-telemetry/opentelemetry-collector-contrib/tree/main/processor/transformprocessor)
