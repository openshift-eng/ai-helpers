#!/usr/bin/env python3
"""Tests for extract_metrics.py."""

import json
import os
import subprocess
import sys
import tempfile

import extract_metrics

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


def otel_attributes(values):
    """Build sanitized OTLP attributes for synthetic fixtures."""
    result = []
    for key, value in values.items():
        value_key = "intValue" if isinstance(value, int) else "stringValue"
        result.append({"key": key, "value": {value_key: value}})
    return result


def codex_metric_record(start, timestamp, main_cost, tokens, auxiliary_cost=0):
    """Build one cumulative agentic-ci Codex metric snapshot."""
    cost_points = [{
        "asDouble": main_cost,
        "startTimeUnixNano": start,
        "timeUnixNano": timestamp,
        "attributes": otel_attributes({"model": "gpt-main"}),
    }]
    if auxiliary_cost:
        cost_points.append({
            "asDouble": auxiliary_cost,
            "startTimeUnixNano": start,
            "timeUnixNano": timestamp,
            "attributes": otel_attributes({"model": "gpt-auxiliary"}),
        })
    token_points = []
    for token_type, value in tokens.items():
        token_points.append({
            "asInt": value,
            "startTimeUnixNano": start,
            "timeUnixNano": timestamp,
            "attributes": otel_attributes({"model": "gpt-main", "type": token_type}),
        })
    return {"path": "/v1/metrics", "payload": {
        "resourceMetrics": [{"scopeMetrics": [{"metrics": [
            {"name": "agentic_ci.codex.cost.usage", "sum": {
                "aggregationTemporality": 2, "isMonotonic": True,
                "dataPoints": cost_points,
            }},
            {"name": "agentic_ci.codex.token.usage", "sum": {
                "aggregationTemporality": 2, "isMonotonic": True,
                "dataPoints": token_points,
            }},
        ]}]}],
    }}


def metric_record(metrics, resource=None, scope=None):
    """Build a sanitized OTLP metrics record with explicit producer identity."""
    resource_metrics = {
        "resource": resource or {},
        "scopeMetrics": [{"scope": scope or {}, "metrics": metrics}],
    }
    return {"path": "/v1/metrics", "payload": {"resourceMetrics": [resource_metrics]}}


def cumulative_metric(name, value, attrs=None, start="100", timestamp="200"):
    """Build one cumulative OTLP sum metric for focused accumulator tests."""
    return {
        "name": name,
        "sum": {
            "aggregationTemporality": 2,
            "isMonotonic": True,
            "dataPoints": [{
                "asDouble": value,
                "startTimeUnixNano": start,
                "timeUnixNano": timestamp,
                "attributes": otel_attributes(attrs or {}),
            }],
        },
    }


def codex_log_record(timestamp, event, model, session, **extra):
    """Build one sanitized Codex OTEL log record."""
    attrs = {
        "event.timestamp": timestamp,
        "event.name": event,
        "model": model,
        "conversation.id": session,
        "app.version": "0.164.0",
    }
    attrs.update(extra)
    return {"attributes": otel_attributes(attrs)}


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


def test_trace_accumulator_skill_and_agent_spans():
    """TraceAccumulator should count Skill, Write, and Agent tool spans."""
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
        {"ts": "2026-06-16T00:00:01Z", "path": "/v1/traces", "payload": {
            "resourceSpans": [{"resource": {"attributes": [
                {"key": "service.version", "value": {"stringValue": "2.1.185"}}
            ]}, "scopeSpans": [{"spans": [
                {"traceId": "aa", "spanId": "11", "name": "claude_code.interaction", "kind": 1,
                 "startTimeUnixNano": "1718452800000000000", "endTimeUnixNano": "1718452810000000000",
                 "attributes": [
                     {"key": "session.id", "value": {"stringValue": "tool-spans-session"}},
                     {"key": "user_prompt", "value": {"stringValue": "test prompt"}},
                 ]},
                {"traceId": "aa", "spanId": "22", "parentSpanId": "11", "name": "claude_code.llm_request", "kind": 1,
                 "startTimeUnixNano": "1718452800500000000", "endTimeUnixNano": "1718452805000000000",
                 "attributes": [
                     {"key": "llm_request.context", "value": {"stringValue": "interaction"}},
                     {"key": "ttft_ms", "value": {"intValue": 1000}},
                     {"key": "stop_reason", "value": {"stringValue": "end_turn"}},
                 ]},
                {"traceId": "aa", "spanId": "30", "parentSpanId": "11", "name": "claude_code.tool", "kind": 1,
                 "startTimeUnixNano": "1718452801000000000", "endTimeUnixNano": "1718452802000000000",
                 "attributes": [
                     {"key": "tool_name", "value": {"stringValue": "Skill"}},
                     {"key": "skill_name", "value": {"stringValue": "code-review"}},
                 ]},
                {"traceId": "aa", "spanId": "31", "parentSpanId": "11", "name": "claude_code.tool", "kind": 1,
                 "startTimeUnixNano": "1718452802000000000", "endTimeUnixNano": "1718452803000000000",
                 "attributes": [
                     {"key": "tool_name", "value": {"stringValue": "Skill"}},
                     {"key": "skill_name", "value": {"stringValue": "simplify"}},
                 ]},
                {"traceId": "aa", "spanId": "32", "parentSpanId": "11", "name": "claude_code.tool", "kind": 1,
                 "startTimeUnixNano": "1718452803000000000", "endTimeUnixNano": "1718452804000000000",
                 "attributes": [
                     {"key": "tool_name", "value": {"stringValue": "Write"}},
                 ]},
                {"traceId": "aa", "spanId": "33", "parentSpanId": "11", "name": "claude_code.tool", "kind": 1,
                 "startTimeUnixNano": "1718452804000000000", "endTimeUnixNano": "1718452805000000000",
                 "attributes": [
                     {"key": "tool_name", "value": {"stringValue": "Write"}},
                 ]},
                {"traceId": "aa", "spanId": "34", "parentSpanId": "11", "name": "claude_code.tool", "kind": 1,
                 "startTimeUnixNano": "1718452805000000000", "endTimeUnixNano": "1718452806000000000",
                 "attributes": [
                     {"key": "tool_name", "value": {"stringValue": "Agent"}},
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
        assert row["skills_invoked"] == "code-review,simplify", f"Got {row['skills_invoked']}"
        assert row["files_written"] == "2", f"Got {row['files_written']}"
        assert row["num_subagents"] == "1", f"Got {row['num_subagents']}"
        print("PASS: test_trace_accumulator_skill_and_agent_spans")
    finally:
        os.unlink(log_path)
        os.unlink(out_path)


def test_trace_accumulator_multi_batch():
    """TraceAccumulator should accumulate across multiple /v1/traces payloads."""
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
        {"ts": "2026-06-16T00:00:01Z", "path": "/v1/traces", "payload": {
            "resourceSpans": [{"resource": {"attributes": [
                {"key": "service.version", "value": {"stringValue": "2.1.185"}}
            ]}, "scopeSpans": [{"spans": [
                {"traceId": "aa", "spanId": "11", "name": "claude_code.interaction", "kind": 1,
                 "startTimeUnixNano": "1718452800000000000", "endTimeUnixNano": "1718452810000000000",
                 "attributes": [
                     {"key": "session.id", "value": {"stringValue": "multi-batch-session"}},
                     {"key": "user_prompt", "value": {"stringValue": "first prompt"}},
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
        {"ts": "2026-06-16T00:00:02Z", "path": "/v1/traces", "payload": {
            "resourceSpans": [{"resource": {"attributes": [
                {"key": "service.version", "value": {"stringValue": "2.1.185"}}
            ]}, "scopeSpans": [{"spans": [
                {"traceId": "bb", "spanId": "33", "name": "claude_code.llm_request", "kind": 1,
                 "startTimeUnixNano": "1718452815000000000", "endTimeUnixNano": "1718452820000000000",
                 "attributes": [
                     {"key": "llm_request.context", "value": {"stringValue": "interaction"}},
                     {"key": "ttft_ms", "value": {"intValue": 2000}},
                     {"key": "stop_reason", "value": {"stringValue": "tool_use"}},
                 ]},
                {"traceId": "bb", "spanId": "34", "parentSpanId": "33", "name": "claude_code.tool", "kind": 1,
                 "startTimeUnixNano": "1718452816000000000", "endTimeUnixNano": "1718452817000000000",
                 "attributes": [
                     {"key": "tool_name", "value": {"stringValue": "Agent"}},
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
        assert row["num_turns"] == "2", f"Got {row['num_turns']}"
        assert row["num_subagents"] == "1", f"Got {row['num_subagents']}"
        # Duration spans from first batch start to second batch end
        assert int(row["duration_ms"]) == 20000, f"Got {row['duration_ms']}"
        # ttft should be from the first interaction span (earlier start_ns)
        assert row["ttft_ms"] == "1000", f"Got {row['ttft_ms']}"
        # stop_reason should be the last one seen
        assert row["stop_reason"] == "tool_use", f"Got {row['stop_reason']}"
        print("PASS: test_trace_accumulator_multi_batch")
    finally:
        os.unlink(log_path)
        os.unlink(out_path)


def test_trace_accumulator_prompt_ordering():
    """TraceAccumulator should use the prompt from the earliest interaction span."""
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
        {"ts": "2026-06-16T00:00:01Z", "path": "/v1/traces", "payload": {
            "resourceSpans": [{"resource": {"attributes": [
                {"key": "service.version", "value": {"stringValue": "2.1.185"}}
            ]}, "scopeSpans": [{"spans": [
                # Second interaction (later timestamp, but appears first in the payload)
                {"traceId": "aa", "spanId": "22", "name": "claude_code.interaction", "kind": 1,
                 "startTimeUnixNano": "1718452820000000000", "endTimeUnixNano": "1718452830000000000",
                 "attributes": [
                     {"key": "session.id", "value": {"stringValue": "prompt-order-session"}},
                     {"key": "user_prompt", "value": {"stringValue": "second prompt"}},
                 ]},
                # First interaction (earlier timestamp)
                {"traceId": "aa", "spanId": "11", "name": "claude_code.interaction", "kind": 1,
                 "startTimeUnixNano": "1718452800000000000", "endTimeUnixNano": "1718452810000000000",
                 "attributes": [
                     {"key": "session.id", "value": {"stringValue": "prompt-order-session"}},
                     {"key": "user_prompt", "value": {"stringValue": "first prompt"}},
                 ]},
                {"traceId": "aa", "spanId": "33", "parentSpanId": "11", "name": "claude_code.llm_request", "kind": 1,
                 "startTimeUnixNano": "1718452800500000000", "endTimeUnixNano": "1718452805000000000",
                 "attributes": [
                     {"key": "llm_request.context", "value": {"stringValue": "interaction"}},
                     {"key": "ttft_ms", "value": {"intValue": 1500}},
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
        assert row["prompt"] == "first prompt", f"Got {row['prompt']}"
        print("PASS: test_trace_accumulator_prompt_ordering")
    finally:
        os.unlink(log_path)
        os.unlink(out_path)


def test_stream_log_fallback_when_traces_zero():
    """Redacted traces allow user-message and queued stream prompt fallbacks."""
    # The interaction supplies timing and identity but only a redacted prompt.
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
        {"ts": "2026-06-16T00:00:01Z", "path": "/v1/traces", "payload": {
            "resourceSpans": [{"resource": {"attributes": [
                {"key": "service.version", "value": {"stringValue": "2.1.185"}}
            ]}, "scopeSpans": [{"spans": [
                {"traceId": "aa", "spanId": "11", "name": "claude_code.interaction", "kind": 1,
                 "startTimeUnixNano": "1718452800000000000", "endTimeUnixNano": "1718452801000000000",
                 "attributes": [
                     {"key": "session.id", "value": {"stringValue": "fallback-session"}},
                     {"key": "user_prompt", "value": {"stringValue": "[REDACTED]"}},
                 ]},
            ]}]}]
        }},
    ]
    stream_cases = [
        ("user-message", {"type": "user", "message": {"role": "user", "content": [
            {"type": "text", "text": "fallback user prompt"},
        ]}}, "fallback user prompt"),
        ("queue-operation", {"type": "queue-operation", "operation": "enqueue",
                             "content": "fallback queued prompt"},
         "fallback queued prompt"),
    ]
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as tmp:
        for record in otel_data:
            tmp.write(json.dumps(record) + "\n")
        log_path = tmp.name
    try:
        for case_name, prompt_record, expected_prompt in stream_cases:
            stream_data = [
                {"type": "system", "subtype": "init", "session_id": "fallback-session",
                 "model": "claude-opus-4-6", "claude_code_version": "2.1.185",
                 "permissionMode": "plan", "plugins": []},
                prompt_record,
                {"type": "result", "duration_ms": 45000, "ttft_ms": 2500,
                 "num_turns": 3, "is_error": False, "terminal_reason": "completed",
                 "stop_reason": "end_turn"},
            ]
            with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl",
                                             delete=False) as tmp:
                for record in stream_data:
                    tmp.write(json.dumps(record) + "\n")
                stream_path = tmp.name
            with tempfile.NamedTemporaryFile(suffix="-autodl.json", delete=False) as tmp:
                out_path = tmp.name
            try:
                result = run_script(log_path, out_path,
                                    extra_args=["--stream-log", stream_path])
                assert result.returncode == 0, f"{case_name}: {result.stderr}"
                row = load_autodl(out_path)["rows"][0]
                assert row["duration_ms"] == "1000", row["duration_ms"]
                assert row["ttft_ms"] == "2500", row["ttft_ms"]
                assert row["num_turns"] == "3", row["num_turns"]
                assert row["session_id"] == "fallback-session"
                assert row["prompt"] == expected_prompt, row["prompt"]
            finally:
                os.unlink(stream_path)
                os.unlink(out_path)
        print("PASS: test_stream_log_fallback_when_traces_zero")
    finally:
        os.unlink(log_path)


def test_claude_trace_prompt_precedes_stream_prompts():
    """A real Claude trace prompt takes priority over stream fallbacks."""
    stream = [
        {"type": "user", "message": {"role": "user", "content": "stream prompt"}},
        {"type": "queue-operation", "operation": "enqueue", "content": "queued prompt"},
    ]
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as tmp:
        for record in stream:
            tmp.write(json.dumps(record) + "\n")
        stream_path = tmp.name
    try:
        row = extract_metrics.parse_otel(os.path.join(TESTDATA, "otel_metrics.jsonl"))
        assert row["prompt"] == "Analyze this payload"
        extract_metrics.enrich_from_stream_log(row, stream_path)
        assert row["prompt"] == "Analyze this payload"
    finally:
        os.unlink(stream_path)
    print("PASS: test_claude_trace_prompt_precedes_stream_prompts")


def test_codex_metrics_identity_and_cumulative_snapshots():
    """Codex uses observed cost, primary identity, and de-duplicated snapshots."""
    records = [
        # Two cumulative snapshots for one invocation: only the later values count.
        codex_metric_record("100", "200", 1.0, {
            "input": 100, "cacheRead": 900, "cacheCreation": 100, "output": 50,
        }, auxiliary_cost=0.10),
        codex_metric_record("100", "300", 1.5, {
            "input": 150, "cacheRead": 1350, "cacheCreation": 150, "output": 80,
        }, auxiliary_cost=0.25),
        # A resumed invocation has a distinct start time and remains additive.
        codex_metric_record("400", "500", 0.5, {
            "input": 50, "cacheRead": 450, "cacheCreation": 50, "output": 20,
        }),
        {"path": "/v1/logs", "payload": {"resourceLogs": [{"scopeLogs": [{
            "logRecords": [
                # Auxiliary activity appears first and must not supply row identity/prompt.
                codex_log_record("2026-11-06T00:00:00Z", "codex.conversation_starts",
                                 "gpt-auxiliary", "aux-session"),
                codex_log_record("2026-11-06T00:00:01Z", "codex.user_prompt",
                                 "gpt-auxiliary", "aux-session", prompt="auxiliary prompt"),
                codex_log_record("2026-11-06T00:00:02Z", "codex.conversation_starts",
                                 "gpt-main", "main-session"),
                codex_log_record("2026-11-06T00:00:03Z", "codex.user_prompt",
                                 "gpt-main", "main-session", prompt="[REDACTED]"),
                codex_log_record("2026-11-06T00:00:04Z", "codex.turn_ttft",
                                 "gpt-main", "main-session", duration_ms=1250),
                codex_log_record("2026-11-06T00:00:05Z", "codex.sse_event",
                                 "gpt-main", "main-session",
                                 **{"event.kind": "response.completed"}),
                codex_log_record("2026-11-06T00:00:06Z", "codex.sse_event",
                                 "gpt-main", "main-session",
                                 **{"event.kind": "response.completed"}),
                codex_log_record("2026-11-06T00:00:07Z", "codex.tool_decision",
                                 "gpt-main", "main-session", tool_name="Shell"),
            ],
        }]}]}},
    ]
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as tmp:
        for record in records:
            tmp.write(json.dumps(record) + "\n")
        log_path = tmp.name
    with tempfile.NamedTemporaryFile(suffix="-autodl.json", delete=False) as tmp:
        out_path = tmp.name
    with tempfile.NamedTemporaryFile(mode="w", suffix="-prompt.txt", delete=False) as tmp:
        tmp.write("Fix the metrics parser")
        prompt_path = tmp.name
    try:
        redacted = run_script(log_path, out_path)
        assert redacted.returncode != 0, "A redacted prompt must not pass validation"
        assert load_autodl(out_path)["rows"][0]["prompt"] == ""
        result = run_script(log_path, out_path, extra_args=["--prompt-file", prompt_path])
        assert result.returncode == 0, f"Script failed: {result.stderr}"
        row = load_autodl(out_path)["rows"][0]
        assert row["model"] == "gpt-main"
        assert row["session_id"] == "main-session"
        assert row["claude_code_version"] == "0.164.0"
        assert row["prompt"] == "Fix the metrics parser"
        assert row["num_turns"] == "2"
        assert row["ttft_ms"] == "1250"
        # Session total includes the observed auxiliary-model cost. No prices guessed.
        assert row["total_cost_usd"] == "2.250000"
        # Primary-model tokens add the final first-invocation snapshot and resume once.
        assert row["input_tokens"] == "200"
        assert row["output_tokens"] == "100"
        assert row["cache_read_input_tokens"] == "1800"
        assert row["cache_creation_input_tokens"] == "200"
        assert row["cache_hit_rate_pct"] == "81.8"
        assert row["total_tool_calls"] == "1"
        print("PASS: test_codex_metrics_identity_and_cumulative_snapshots")
    finally:
        os.unlink(log_path)
        os.unlink(out_path)
        os.unlink(prompt_path)


def test_codex_prompt_precedes_trace_and_stream_prompts():
    """A real Codex prompt takes priority over Claude trace and stream prompts."""
    records = [
        codex_metric_record("100", "200", 1.0, {"input": 10, "output": 5}),
        {"path": "/v1/logs", "payload": {"resourceLogs": [{"scopeLogs": [{
            "logRecords": [
                codex_log_record("2026-11-06T00:00:00Z", "codex.conversation_starts",
                                 "gpt-main", "main-session"),
                codex_log_record("2026-11-06T00:00:01Z", "codex.user_prompt",
                                 "gpt-main", "main-session", prompt="real Codex prompt"),
            ],
        }]}]}},
        {"path": "/v1/traces", "payload": {"resourceSpans": [{"scopeSpans": [{
            "spans": [{
                "name": "claude_code.interaction",
                "startTimeUnixNano": "100",
                "endTimeUnixNano": "200",
                "attributes": [
                    {"key": "user_prompt", "value": {"stringValue": "Claude trace prompt"}},
                ],
            }],
        }]}]}},
    ]
    stream = [
        {"type": "user", "message": {"role": "user", "content": "stream prompt"}},
        {"type": "queue-operation", "operation": "enqueue", "content": "queued prompt"},
    ]
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as tmp:
        for record in records:
            tmp.write(json.dumps(record) + "\n")
        log_path = tmp.name
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as tmp:
        for record in stream:
            tmp.write(json.dumps(record) + "\n")
        stream_path = tmp.name
    try:
        row = extract_metrics.parse_otel(log_path)
        assert row["prompt"] == "real Codex prompt"
        extract_metrics.enrich_from_stream_log(row, stream_path)
        assert row["prompt"] == "real Codex prompt"
    finally:
        os.unlink(log_path)
        os.unlink(stream_path)
    print("PASS: test_codex_prompt_precedes_trace_and_stream_prompts")


def test_redacted_prompt_placeholders_are_rejected():
    """Prompt validation must not accept redaction markers in any common case."""
    for prompt in ("[REDACTED]", " [redacted] ", "<REDACTED>", "Redacted"):
        assert not extract_metrics._is_real_prompt(prompt), prompt
    assert extract_metrics._is_real_prompt("Explain why this metric is missing")
    print("PASS: test_redacted_prompt_placeholders_are_rejected")


def test_whitespace_prompts_are_rejected_without_stripping_valid_content():
    """Whitespace is empty, while valid prompt contents retain their spacing."""
    for prompt in (" ", "\t", "\n", "\u00a0", "\u2003", " \t\n\u2003"):
        assert not extract_metrics._is_real_prompt(prompt), repr(prompt)

    prompt = "  sanitized prompt with surrounding whitespace\t"
    assert extract_metrics._is_real_prompt(prompt)
    accumulator = extract_metrics.CodexLogAccumulator()
    accumulator.add({
        "event.name": "codex.user_prompt",
        "event.timestamp": "2026-11-09T15:00:00Z",
        "model": "gpt-main",
        "conversation.id": "synthetic-session",
        "prompt": prompt,
    })
    assert accumulator.result("gpt-main")["prompt"] == prompt
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", delete=False) as tmp:
        tmp.write("different sanitized file prompt")
        prompt_path = tmp.name
    try:
        row = {"prompt": prompt}
        extract_metrics.enrich_from_prompt_file(row, prompt_path)
        assert row["prompt"] == prompt
    finally:
        os.unlink(prompt_path)
    print("PASS: test_whitespace_prompts_are_rejected_without_stripping_valid_content")


def test_whitespace_telemetry_uses_stream_then_file_fallbacks():
    """Blank prompt sources fall through in CLI order and never validate a row."""
    whitespace = " \t\n\u2003"
    records = [
        codex_metric_record("100", "200", 1.0, {"input": 10, "output": 5}),
        {"path": "/v1/logs", "payload": {"resourceLogs": [{"scopeLogs": [{
            "logRecords": [
                codex_log_record("2026-11-09T15:00:00Z", "codex.user_prompt",
                                 "gpt-main", "synthetic-session", prompt=whitespace),
                codex_log_record("2026-11-09T15:00:01Z", "codex.sse_event",
                                 "gpt-main", "synthetic-session",
                                 **{"event.kind": "response.completed"}),
            ],
        }]}]}},
    ]
    cases = [
        ("sanitized stream fallback", "sanitized file fallback", 0,
         "sanitized stream fallback"),
        (whitespace, "sanitized file fallback", 0, "sanitized file fallback"),
        (whitespace, whitespace, 1, ""),
    ]
    with tempfile.TemporaryDirectory() as tmp_dir:
        log_path = os.path.join(tmp_dir, "otel.jsonl")
        with open(log_path, "w", encoding="utf-8") as log_file:
            for record in records:
                log_file.write(json.dumps(record) + "\n")
        for index, (stream_prompt, file_prompt, exit_code, expected) in enumerate(cases):
            stream_path = os.path.join(tmp_dir, f"stream-{index}.jsonl")
            prompt_path = os.path.join(tmp_dir, f"prompt-{index}.txt")
            output_path = os.path.join(tmp_dir, f"output-{index}.json")
            with open(stream_path, "w", encoding="utf-8") as stream_file:
                stream_file.write(json.dumps({
                    "type": "user", "message": {"content": stream_prompt},
                }) + "\n")
            with open(prompt_path, "w", encoding="utf-8") as prompt_file:
                prompt_file.write(file_prompt)
            result = run_script(
                log_path,
                output_path,
                extra_args=["--stream-log", stream_path, "--prompt-file", prompt_path],
            )
            assert result.returncode == exit_code, (index, result.stderr)
            assert load_autodl(output_path)["rows"][0]["prompt"] == expected, index
    print("PASS: test_whitespace_telemetry_uses_stream_then_file_fallbacks")


def test_prompt_file_errors_and_real_prompt_precedence():
    """Prompt-file failures preserve the row, and real telemetry wins."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        missing_path = os.path.join(tmp_dir, "missing-prompt.txt")
        invalid_path = os.path.join(tmp_dir, "invalid-prompt.txt")
        with open(invalid_path, "wb") as prompt_file:
            prompt_file.write(b"\xff\xfe")

        for prompt_path in (missing_path, tmp_dir, invalid_path):
            row = {"prompt": ""}
            result = extract_metrics.enrich_from_prompt_file(row, prompt_path)
            assert result is row
            assert row == {"prompt": ""}, prompt_path

        valid_path = os.path.join(tmp_dir, "valid-prompt.txt")
        with open(valid_path, "w", encoding="utf-8") as prompt_file:
            prompt_file.write("prompt-file fallback")
        row = {"prompt": "real telemetry prompt"}
        extract_metrics.enrich_from_prompt_file(row, valid_path)
        assert row["prompt"] == "real telemetry prompt"
    print("PASS: test_prompt_file_errors_and_real_prompt_precedence")


def test_metric_filtering_and_malformed_points():
    """Only finite supported metric points should reach numeric aggregation."""
    accumulator = extract_metrics.MetricAccumulator()
    accumulator.add({
        "name": "unrelated.metric",
        "sum": {"dataPoints": [{"asInt": 10 ** 400}]},
    }, {}, {})
    for value in (10 ** 400, "NaN", "Infinity", None, "not-a-number"):
        accumulator.add(cumulative_metric(
            "agentic_ci.codex.cost.usage", value, {"model": "gpt-synthetic"},
        ), {}, {})
    accumulator.add(cumulative_metric(
        "agentic_ci.codex.cost.usage", 2.5, {"model": "gpt-synthetic"},
    ), {}, {})
    assert accumulator.values() == [
        ("agentic_ci.codex.cost.usage", {"model": "gpt-synthetic"}, 2.5),
    ]
    print("PASS: test_metric_filtering_and_malformed_points")


def test_metric_producer_identity_and_alias_canonicalization():
    """Cumulative aliases deduplicate per producer but distinct producers add."""
    attrs = {"model": "gpt-synthetic"}
    producer_a = {"attributes": otel_attributes({
        "service.name": "producer-a", "service.version": "1",
    })}
    producer_a_reordered = {"attributes": list(reversed(producer_a["attributes"]))}
    producer_b = {"attributes": otel_attributes({"service.name": "producer-b"})}
    scope_a = {"name": "agentic-ci", "version": "1"}
    scope_b = {"version": "1", "name": "agentic-ci-other"}
    records = [
        metric_record([
            cumulative_metric("codex.cost.usage", 2.0, attrs),
            cumulative_metric("agentic_ci.codex.cost.usage", 2.0, attrs),
            cumulative_metric("codex.token.usage", 11.0,
                              {"model": "gpt-synthetic", "type": "output"}),
            cumulative_metric("agentic_ci.codex.token.usage", 11.0,
                              {"model": "gpt-synthetic", "type": "output"}),
        ], producer_a, scope_a),
        metric_record([
            cumulative_metric("agentic_ci.codex.cost.usage", 3.0, attrs),
        ], producer_b, scope_a),
        metric_record([
            cumulative_metric("agentic_ci.codex.cost.usage", 5.0, attrs),
        ], producer_a, scope_b),
        # Attribute/dict order is not producer identity, so this is the same
        # cumulative observation as producer A above and remains de-duplicated.
        metric_record([
            cumulative_metric("codex.cost.usage", 2.0, attrs),
        ], producer_a_reordered, {"version": "1", "name": "agentic-ci"}),
        # A new cumulative start is a real resumed observation and remains additive.
        metric_record([
            cumulative_metric("codex.cost.usage", 7.0, attrs, start="300", timestamp="400"),
        ], producer_a, scope_a),
    ]
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as tmp:
        for record in records:
            tmp.write(json.dumps(record) + "\n")
        log_path = tmp.name
    try:
        row = extract_metrics.parse_otel(log_path)
        assert row["total_cost_usd"] == "17.000000", row
        assert row["output_tokens"] == "11", row
    finally:
        os.unlink(log_path)
    print("PASS: test_metric_producer_identity_and_alias_canonicalization")


def test_modelless_metrics_join_modelless_logs():
    """Model-less Codex metrics and logs should share the unknown-model row."""
    records = [
        metric_record([
            cumulative_metric("agentic_ci.codex.cost.usage", 1.0),
            cumulative_metric("agentic_ci.codex.token.usage", 7, {"type": "output"}),
        ]),
        {"path": "/v1/logs", "payload": {"resourceLogs": [{"scopeLogs": [{
            "logRecords": [
                codex_log_record("2026-11-06T00:00:00Z", "codex.user_prompt",
                                 "", "synthetic-session", prompt="synthetic prompt"),
                codex_log_record("2026-11-06T00:00:01Z", "codex.sse_event",
                                 "", "synthetic-session",
                                 **{"event.kind": "response.completed"}),
            ],
        }]}]}},
    ]
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as tmp:
        for record in records:
            tmp.write(json.dumps(record) + "\n")
        log_path = tmp.name
    try:
        row = extract_metrics.parse_otel(log_path)
        assert row["model"] == "unknown"
        assert row["session_id"] == "synthetic-session"
        assert row["prompt"] == "synthetic prompt"
        assert row["num_turns"] == "1"
    finally:
        os.unlink(log_path)
    print("PASS: test_modelless_metrics_join_modelless_logs")


def test_codex_log_chronology_and_identity():
    """Chronology should ignore unsafe timestamps and bind identity to first prompt."""
    accumulator = extract_metrics.CodexLogAccumulator()
    events = [
        {
            "event.name": "codex.user_prompt",
            "event.timestamp": "2026-11-06T00:00:05Z",
            "model": "gpt-synthetic",
            "conversation.id": "later-session",
            "app.version": "later-version",
            "prompt": "later prompt",
        },
        {
            "event.name": "codex.user_prompt",
            "event.timestamp": "2026-11-06T00:00:01Z",
            "model": "gpt-synthetic",
            "conversation.id": "earliest-session",
            "app.version": "earliest-version",
            "prompt": "earliest prompt",
        },
        {
            "event.name": "codex.turn_ttft",
            "event.timestamp": "2026-11-06T00:00:00",
            "model": "gpt-synthetic",
            "conversation.id": "naive-session",
            "app.version": "naive-version",
            "duration_ms": 999,
        },
        {
            "event.name": "codex.turn_ttft",
            "event.timestamp": "not-a-timestamp",
            "model": "gpt-synthetic",
            "duration_ms": 888,
        },
        {
            "event.name": "codex.turn_ttft",
            "event.timestamp": "2026-11-06T00:00:02Z",
            "model": "gpt-synthetic",
            "duration_ms": 123,
        },
    ]
    for event in events:
        accumulator.add(event)
    result = accumulator.result("gpt-synthetic")
    assert result["session_id"] == "earliest-session", result
    assert result["claude_code_version"] == "earliest-version", result
    assert result["prompt"] == "earliest prompt", result
    assert result["ttft_ms"] == 123, result
    assert result["duration_ms"] == 4000, result

    fallback = extract_metrics.CodexLogAccumulator()
    fallback.add({
        "event.name": "codex.conversation_starts",
        "event.timestamp": "2026-11-06T00:00:00Z",
        "model": "gpt-synthetic",
        "conversation.id": "fallback-session",
        "app.version": "fallback-version",
    })
    fallback.add({
        "event.name": "codex.user_prompt",
        "event.timestamp": "2026-11-06T00:00:01Z",
        "model": "gpt-synthetic",
        "conversation.id": "",
        "app.version": "",
        "prompt": "prompt without identity",
    })
    result = fallback.result("gpt-synthetic")
    assert result["session_id"] == "fallback-session", result
    assert result["claude_code_version"] == "fallback-version", result
    print("PASS: test_codex_log_chronology_and_identity")


def test_prompt_file_utf8_prefix_boundaries():
    """Prompt fallback strictly decodes at most the first 500 characters."""
    cases = [
        (b"a" * 500 + b"\xff", "a" * 500),
        (("a" * 499 + "é").encode("utf-8") + b"\xff", "a" * 499 + "é"),
        (("é" * 500).encode("utf-8"), "é" * 500),
        (b"a" * 500, "a" * 500),
        (b"a" * 501, "a" * 500),
        ("x".encode("utf-8") * 499 + b"\xff", ""),
    ]
    with tempfile.TemporaryDirectory() as tmp_dir:
        for index, (content, expected) in enumerate(cases):
            prompt_path = os.path.join(tmp_dir, f"prompt-{index}.txt")
            with open(prompt_path, "wb") as prompt_file:
                prompt_file.write(content)
            row = {"prompt": ""}
            extract_metrics.enrich_from_prompt_file(row, prompt_path)
            assert row["prompt"] == expected, (index, row)
    print("PASS: test_prompt_file_utf8_prefix_boundaries")


if __name__ == "__main__":
    test_otel_input()
    test_otel_with_stream_enrichment()
    test_otel_schema_matches_row()
    test_empty_otel_log()
    test_missing_stream_log()
    test_tool_decision_events()
    test_missing_required_fields_errors()
    test_trace_accumulator_skill_and_agent_spans()
    test_trace_accumulator_multi_batch()
    test_trace_accumulator_prompt_ordering()
    test_stream_log_fallback_when_traces_zero()
    test_claude_trace_prompt_precedes_stream_prompts()
    test_codex_metrics_identity_and_cumulative_snapshots()
    test_codex_prompt_precedes_trace_and_stream_prompts()
    test_redacted_prompt_placeholders_are_rejected()
    test_whitespace_prompts_are_rejected_without_stripping_valid_content()
    test_whitespace_telemetry_uses_stream_then_file_fallbacks()
    test_prompt_file_errors_and_real_prompt_precedence()
    test_metric_filtering_and_malformed_points()
    test_metric_producer_identity_and_alias_canonicalization()
    test_modelless_metrics_join_modelless_logs()
    test_codex_log_chronology_and_identity()
    test_prompt_file_utf8_prefix_boundaries()
    print("\nAll tests passed.")
