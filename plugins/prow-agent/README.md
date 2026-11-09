# prow-agent

Utilities for Claude Code and Codex sessions running inside Prow CI jobs.

## Session Metrics

Extracts cost, token, duration, and tool-usage metrics from Claude Code and
Codex sessions and writes an autodl JSON file for BigQuery ingestion.

### With agentic-ci (Preferred)

When using `agentic-ci run --backend local`, the OTEL collector is
managed automatically per invocation. Concatenate the per-run JSONL
files and pass them to `extract_metrics.py`:

```bash
EXTRACT_METRICS="/opt/ai-helpers/plugins/prow-agent/scripts/extract_metrics.py"
OTEL_LOG="${ARTIFACT_DIR}/claude-otel.jsonl"
PROMPT_ARGS=()

# Optional fallback when telemetry redacts the prompt. The file must contain
# the real initial harness prompt, not a placeholder.
if [[ -n "${INITIAL_PROMPT_FILE:-}" ]]; then
    PROMPT_ARGS=(--prompt-file "${INITIAL_PROMPT_FILE}")
fi

# agentic-ci writes OTEL JSONL to /tmp/agentic-ci-run.*/claude-otel.jsonl
# Concatenate after each invocation (see run_claude wrapper pattern)

python3 "${EXTRACT_METRICS}" "${OTEL_LOG}" \
    "${ARTIFACT_DIR}/claude-session-metrics-autodl.json" \
    "${PROMPT_ARGS[@]}"
```

Keep the full prompt file private, outside the artifact directory, and remove
it after extraction. When telemetry omits or redacts the prompt, the extractor
intentionally copies the first 500 characters into the exported `prompt` field,
so the prompt must not contain secrets. Claude Code and Codex telemetry prompts
still take precedence over this fallback.

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
