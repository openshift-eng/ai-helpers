# prow-agent

Utilities for Claude Code sessions running inside Prow CI jobs.

## Session Metrics

Extracts cost, token, duration, and tool-usage metrics from Claude Code
sessions and writes an autodl JSON file for BigQuery ingestion.

### With agentic-ci (Preferred)

When using `agentic-ci run --backend local`, the OTEL collector is
managed automatically per invocation. Concatenate the per-run JSONL
files and pass them to `extract_metrics.py`:

```bash
EXTRACT_METRICS="/opt/ai-helpers/plugins/prow-agent/scripts/extract_metrics.py"
OTEL_LOG="${ARTIFACT_DIR}/claude-otel.jsonl"

# agentic-ci writes OTEL JSONL to /tmp/agentic-ci-run.*/claude-otel.jsonl
# Concatenate after each invocation (see run_claude wrapper pattern)

python3 "${EXTRACT_METRICS}" "${OTEL_LOG}" \
    "${ARTIFACT_DIR}/claude-session-metrics-autodl.json"
```

See [docs/metrics-collection.md](docs/metrics-collection.md) for the
full design and BigQuery schema.

### Legacy Stream-JSON Parsing

The script also accepts a stream-json output log directly (auto-detected):

```bash
python3 "${EXTRACT_METRICS}" "${CLAUDE_OUTPUT_LOG}" \
    "${ARTIFACT_DIR}/claude-session-metrics-autodl.json"
```

For `--continue` workflows, run extraction once after the final
invocation. Each `result` message contains per-invocation totals; the
script sums across all result messages.
