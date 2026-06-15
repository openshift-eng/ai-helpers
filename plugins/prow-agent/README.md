# prow-agent

Utilities for Claude Code sessions running inside Prow CI jobs.

## Session Metrics

Extracts cost, token, duration, and tool-usage metrics from a Claude
streaming output log and writes an autodl JSON file for BigQuery ingestion.

### Usage

Call the script after `claude` exits, passing the streaming output log
(`--output-format stream-json`) and the desired output path:

```bash
export CLAUDE_OUTPUT_LOG="${ARTIFACT_DIR}/claude-output.log"
claude -p "..." --output-format stream-json --verbose 2>&1 | tee "${CLAUDE_OUTPUT_LOG}"

EXTRACT_METRICS=$(find ~/.claude/plugins -type f -path "*/prow-agent/scripts/extract_metrics.py" 2>/dev/null | head -1)
python3 "${EXTRACT_METRICS}" "${CLAUDE_OUTPUT_LOG}" "${ARTIFACT_DIR}/claude-session-metrics-autodl.json"
```

For `--continue` workflows, run the extraction once after the final invocation.
The `result` message in the log accumulates totals across the full session.
