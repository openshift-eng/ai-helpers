#!/usr/bin/env python3
"""Tests for extract_metrics.py."""

import json
import os
import subprocess
import sys
import tempfile

SCRIPT = os.path.join(os.path.dirname(__file__), "extract_metrics.py")
TESTDATA = os.path.join(os.path.dirname(__file__), "testdata")


def run_script(log_file, output_file=None, extra_args=None):
    args = [sys.executable, SCRIPT, log_file]
    if output_file:
        args.append(output_file)
    if extra_args:
        args.extend(extra_args)
    result = subprocess.run(args, capture_output=True, text=True)
    return result


def load_autodl(path):
    with open(path) as f:
        return json.load(f)


def test_otel_input():
    """OTEL JSONL input should produce valid autodl with cost/token data."""
    with tempfile.NamedTemporaryFile(suffix="-autodl.json", delete=False) as tmp:
        out_path = tmp.name
    try:
        r = run_script(os.path.join(TESTDATA, "otel_metrics.jsonl"), out_path)
        assert r.returncode == 0, f"Script failed: {r.stderr}"

        data = load_autodl(out_path)
        assert data["table_name"] == "claude_session_metrics"
        assert data["schema_mapping"] is None
        assert data["chunk_size"] == 0
        assert len(data["rows"]) == 1

        row = data["rows"][0]

        # All values must be strings
        for k, v in row.items():
            assert isinstance(v, str), f"Field '{k}' is {type(v).__name__}, expected str"

        # Cost: 2.50 + 1.00 (opus) + 0.25 (sonnet) = 3.75
        assert row["total_cost_usd"] == "3.750000", f"Got {row['total_cost_usd']}"
        # Tokens: opus input 5000+3000=8000, sonnet input 2000
        assert row["input_tokens"] == "10000"  # 8000+2000
        assert row["output_tokens"] == "13500"  # 12000+1500
        assert row["cache_read_input_tokens"] == "100000"
        assert row["cache_creation_input_tokens"] == "20000"
        # Model should be opus (highest cost)
        assert row["model"] == "claude-opus-4-6"
        # Tool calls from api_request logs: Read(2) + Bash(1) = 3
        assert row["total_tool_calls"] == "3"
        breakdown = json.loads(row["tool_call_breakdown"])
        assert breakdown["Read"] == 2
        assert breakdown["Bash"] == 1
        # API duration from active_time
        assert row["duration_api_ms"] == "45500"  # 45.5s
        # Trace-derived fields
        assert row["session_id"] == "test-session-traces"
        assert row["claude_code_version"] == "2.1.185"
        assert row["prompt"] == "Analyze this payload"
        assert row["num_turns"] == "2"
        assert row["duration_ms"] == "30000"
        assert row["ttft_ms"] == "3500"
        assert row["stop_reason"] == "end_turn"
        assert row["files_written"] == "1"

        print("PASS: test_otel_input")
    finally:
        os.unlink(out_path)


def test_otel_with_stream_enrichment():
    """OTEL input enriched with stream-json identity fields."""
    with tempfile.NamedTemporaryFile(suffix="-autodl.json", delete=False) as tmp:
        out_path = tmp.name
    try:
        stream_log = os.path.join(TESTDATA, "valid_output.jsonl")
        r = run_script(
            os.path.join(TESTDATA, "otel_metrics.jsonl"),
            out_path,
            extra_args=["--stream-log", stream_log],
        )
        assert r.returncode == 0, f"Script failed: {r.stderr}"

        data = load_autodl(out_path)
        row = data["rows"][0]

        # Cost/tokens from OTEL
        assert row["total_cost_usd"] == "3.750000"
        # Trace-derived fields take priority over stream-json
        assert row["session_id"] == "test-session-traces"
        assert row["claude_code_version"] == "2.1.185"
        # Stream-json fills in fields not available from traces
        assert row["plugins_loaded"] == "ci"
        # Prompt from traces (interaction span)
        assert row["prompt"] == "Analyze this payload"
        # Duration/turns from traces
        assert row["duration_ms"] == "30000"
        assert row["num_turns"] == "2"
        # Outcome from stream results
        assert row["is_error"] == "0"
        assert row["terminal_reason"] == "completed"
        # Subagents from stream
        assert row["num_subagents"] == "0"
        assert row["skills_invoked"] == "ci:payload-analysis"
        assert row["files_written"] == "1"
        assert row["num_thinking_blocks"] == "1"

        print("PASS: test_otel_with_stream_enrichment")
    finally:
        os.unlink(out_path)


def test_otel_schema_matches_row():
    """OTEL-produced rows must match the schema exactly."""
    with tempfile.NamedTemporaryFile(suffix="-autodl.json", delete=False) as tmp:
        out_path = tmp.name
    try:
        run_script(os.path.join(TESTDATA, "otel_metrics.jsonl"), out_path)
        data = load_autodl(out_path)
        schema_fields = set(data["schema"].keys())
        row_fields = set(data["rows"][0].keys())
        assert schema_fields == row_fields, (
            f"Schema/row mismatch: "
            f"in schema only: {schema_fields - row_fields}, "
            f"in row only: {row_fields - schema_fields}"
        )
        print("PASS: test_otel_schema_matches_row")
    finally:
        os.unlink(out_path)


def test_empty_otel_log():
    """Empty OTEL log should fail with an error."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as tmp:
        log_path = tmp.name
    try:
        r = run_script(log_path)
        assert r.returncode != 0, "Should fail on empty log"
        assert "empty" in r.stderr.lower()
        print("PASS: test_empty_otel_log")
    finally:
        os.unlink(log_path)


def test_missing_stream_log():
    """Missing --stream-log should not crash, just skip enrichment."""
    with tempfile.NamedTemporaryFile(suffix="-autodl.json", delete=False) as tmp:
        out_path = tmp.name
    try:
        r = run_script(
            os.path.join(TESTDATA, "otel_metrics.jsonl"),
            out_path,
            extra_args=["--stream-log", "/nonexistent/path.jsonl"],
        )
        assert r.returncode == 0, f"Script failed: {r.stderr}"
        data = load_autodl(out_path)
        row = data["rows"][0]
        assert row["total_cost_usd"] == "3.750000"
        assert row["session_id"] == "test-session-traces"
        print("PASS: test_missing_stream_log")
    finally:
        os.unlink(out_path)


def test_tool_decision_events():
    """Tool counts should come from tool_decision events (real Claude Code format)."""
    otel_data = [
        {"ts": "2026-06-16T00:00:00Z", "path": "/v1/metrics", "payload": {
            "resourceMetrics": [{"scopeMetrics": [{"metrics": [
                {"name": "claude_code.cost.usage", "sum": {"dataPoints": [
                    {"attributes": [{"key": "model", "value": {"stringValue": "claude-opus-4-6"}}], "asDouble": 1.0}
                ]}},
                {"name": "claude_code.token.usage", "sum": {"dataPoints": [
                    {"attributes": [{"key": "model", "value": {"stringValue": "claude-opus-4-6"}},
                                    {"key": "type", "value": {"stringValue": "input"}}], "asInt": 1000},
                    {"attributes": [{"key": "model", "value": {"stringValue": "claude-opus-4-6"}},
                                    {"key": "type", "value": {"stringValue": "output"}}], "asInt": 500},
                ]}}
            ]}]}]
        }},
        {"ts": "2026-06-16T00:00:01Z", "path": "/v1/logs", "payload": {
            "resourceLogs": [{"scopeLogs": [{"logRecords": [
                {"attributes": [
                    {"key": "event.name", "value": {"stringValue": "api_request"}},
                    {"key": "model", "value": {"stringValue": "claude-opus-4-6"}},
                    {"key": "duration_ms", "value": {"intValue": 2000}},
                ]},
                {"attributes": [
                    {"key": "event.name", "value": {"stringValue": "tool_decision"}},
                    {"key": "tool_name", "value": {"stringValue": "Read"}},
                    {"key": "decision", "value": {"stringValue": "accept"}},
                ]},
                {"attributes": [
                    {"key": "event.name", "value": {"stringValue": "tool_decision"}},
                    {"key": "tool_name", "value": {"stringValue": "Read"}},
                    {"key": "decision", "value": {"stringValue": "accept"}},
                ]},
                {"attributes": [
                    {"key": "event.name", "value": {"stringValue": "tool_decision"}},
                    {"key": "tool_name", "value": {"stringValue": "Bash"}},
                    {"key": "decision", "value": {"stringValue": "accept"}},
                ]},
                {"attributes": [
                    {"key": "event.name", "value": {"stringValue": "tool_result"}},
                    {"key": "tool_name", "value": {"stringValue": "Read"}},
                ]},
            ]}]}]
        }},
        {"ts": "2026-06-16T00:00:01Z", "path": "/v1/traces", "payload": {
            "resourceSpans": [{"resource": {"attributes": [
                {"key": "service.version", "value": {"stringValue": "2.1.185"}}
            ]}, "scopeSpans": [{"spans": [
                {"traceId": "aa", "spanId": "11", "name": "claude_code.interaction", "kind": 1,
                 "startTimeUnixNano": "1718452800000000000", "endTimeUnixNano": "1718452810000000000",
                 "attributes": [
                     {"key": "session.id", "value": {"stringValue": "tool-test-session"}},
                     {"key": "user_prompt", "value": {"stringValue": "test prompt"}},
                 ]},
                {"traceId": "aa", "spanId": "22", "parentSpanId": "11", "name": "claude_code.llm_request", "kind": 1,
                 "startTimeUnixNano": "1718452800500000000", "endTimeUnixNano": "1718452805000000000",
                 "attributes": [
                     {"key": "llm_request.context", "value": {"stringValue": "interaction"}},
                     {"key": "ttft_ms", "value": {"intValue": 1000}},
                     {"key": "stop_reason", "value": {"stringValue": "end_turn"}},
                 ]},
            ]}]}]
        }},
    ]
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as tmp:
        for record in otel_data:
            tmp.write(json.dumps(record) + "\n")
        log_path = tmp.name
    with tempfile.NamedTemporaryFile(suffix="-autodl.json", delete=False) as tmp:
        out_path = tmp.name
    try:
        r = run_script(log_path, out_path)
        assert r.returncode == 0, f"Script failed: {r.stderr}"
        data = load_autodl(out_path)
        row = data["rows"][0]
        assert row["total_tool_calls"] == "3", f"Got {row['total_tool_calls']}"
        breakdown = json.loads(row["tool_call_breakdown"])
        assert breakdown["Read"] == 2, f"Got Read={breakdown.get('Read')}"
        assert breakdown["Bash"] == 1, f"Got Bash={breakdown.get('Bash')}"
        print("PASS: test_tool_decision_events")
    finally:
        os.unlink(log_path)
        os.unlink(out_path)


def test_missing_required_fields_errors():
    """OTEL data without traces should fail validation (missing session_id, prompt, etc)."""
    otel_data = [
        {"ts": "2026-06-16T00:00:00Z", "path": "/v1/metrics", "payload": {
            "resourceMetrics": [{"scopeMetrics": [{"metrics": [
                {"name": "claude_code.cost.usage", "sum": {"dataPoints": [
                    {"attributes": [{"key": "model", "value": {"stringValue": "claude-opus-4-6"}}], "asDouble": 1.0}
                ]}},
                {"name": "claude_code.token.usage", "sum": {"dataPoints": [
                    {"attributes": [{"key": "model", "value": {"stringValue": "claude-opus-4-6"}},
                                    {"key": "type", "value": {"stringValue": "input"}}], "asInt": 1000},
                    {"attributes": [{"key": "model", "value": {"stringValue": "claude-opus-4-6"}},
                                    {"key": "type", "value": {"stringValue": "output"}}], "asInt": 500},
                ]}}
            ]}]}]
        }},
    ]
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as tmp:
        for record in otel_data:
            tmp.write(json.dumps(record) + "\n")
        log_path = tmp.name
    with tempfile.NamedTemporaryFile(suffix="-autodl.json", delete=False) as tmp:
        out_path = tmp.name
    try:
        r = run_script(log_path, out_path)
        assert r.returncode != 0, "Should fail when required fields are missing"
        assert "required fields" in r.stderr.lower(), f"Expected validation error, got: {r.stderr}"
        # File should still be written for debugging
        assert os.path.exists(out_path)
        data = load_autodl(out_path)
        assert data["rows"][0]["total_cost_usd"] == "1.000000"
        print("PASS: test_missing_required_fields_errors")
    finally:
        os.unlink(log_path)
        os.unlink(out_path)


if __name__ == "__main__":
    test_otel_input()
    test_otel_with_stream_enrichment()
    test_otel_schema_matches_row()
    test_empty_otel_log()
    test_missing_stream_log()
    test_tool_decision_events()
    test_missing_required_fields_errors()
    print("\nAll tests passed.")
