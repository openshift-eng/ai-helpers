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


def test_valid_output():
    with tempfile.NamedTemporaryFile(suffix="-autodl.json", delete=False) as tmp:
        out_path = tmp.name
    try:
        r = run_script(os.path.join(TESTDATA, "valid_output.jsonl"), out_path)
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

        assert row["session_id"] == "test-session-001"
        assert row["model"] == "claude-opus-4-6"
        assert row["claude_code_version"] == "2.1.153"
        assert row["duration_ms"] == "30000"
        assert row["duration_api_ms"] == "28000"
        assert row["ttft_ms"] == "1500"
        assert row["num_turns"] == "4"
        assert row["total_cost_usd"] == "0.125000"
        assert row["input_tokens"] == "180"
        assert row["output_tokens"] == "250"
        assert row["cache_read_input_tokens"] == "17500"
        assert row["cache_creation_input_tokens"] == "6700"
        assert row["is_error"] == "0"
        assert row["terminal_reason"] == "completed"
        assert row["plugins_loaded"] == "ci"

        # Tool calls: Skill(1) + Read(2) + Write(1) = 4
        assert row["total_tool_calls"] == "4"
        breakdown = json.loads(row["tool_call_breakdown"])
        assert breakdown["Read"] == 2
        assert breakdown["Write"] == 1
        assert breakdown["Skill"] == 1

        assert row["skills_invoked"] == "ci:payload-analysis"
        assert row["files_written"] == "1"
        assert row["num_thinking_blocks"] == "1"
        assert row["num_subagents"] == "0"

        # Prompt inferred from first Skill call
        assert "ci:payload-analysis" in row["prompt"]

        print("PASS: test_valid_output")
    finally:
        os.unlink(out_path)


def test_error_output():
    with tempfile.NamedTemporaryFile(suffix="-autodl.json", delete=False) as tmp:
        out_path = tmp.name
    try:
        r = run_script(os.path.join(TESTDATA, "error_output.jsonl"), out_path)
        assert r.returncode == 0, f"Script failed: {r.stderr}"

        data = load_autodl(out_path)
        row = data["rows"][0]

        assert row["is_error"] == "1"
        assert row["terminal_reason"] == "error"
        assert row["total_cost_usd"] == "0.010000"
        assert row["num_turns"] == "1"
        assert row["total_tool_calls"] == "0"
        assert row["plugins_loaded"] == ""

        print("PASS: test_error_output")
    finally:
        os.unlink(out_path)


def test_with_subagents():
    with tempfile.NamedTemporaryFile(suffix="-autodl.json", delete=False) as tmp:
        out_path = tmp.name
    try:
        r = run_script(os.path.join(TESTDATA, "with_subagent.jsonl"), out_path)
        assert r.returncode == 0, f"Script failed: {r.stderr}"

        data = load_autodl(out_path)
        row = data["rows"][0]

        assert row["num_subagents"] == "2"
        assert row["subagent_total_tool_uses"] == "15"  # 12 + 3
        assert row["subagent_total_duration_ms"] == "85000"  # 60000 + 25000
        assert row["plugins_loaded"] == "ci,jira"

        # Main session tool calls: Agent(2) = 2
        assert row["total_tool_calls"] == "2"
        breakdown = json.loads(row["tool_call_breakdown"])
        assert breakdown["Agent"] == 2

        print("PASS: test_with_subagents")
    finally:
        os.unlink(out_path)


def test_no_result_message():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as tmp:
        tmp.write('{"type":"system","subtype":"init","session_id":"x","model":"test"}\n')
        tmp.write('{"type":"assistant","message":{"id":"m1","content":[{"type":"text","text":"hi"}],"usage":{"input_tokens":1}},"uuid":"a1","type":"assistant"}\n')
        log_path = tmp.name
    try:
        r = run_script(log_path)
        assert r.returncode != 0, "Should fail without result message"
        assert "no result message" in r.stderr.lower()
        print("PASS: test_no_result_message")
    finally:
        os.unlink(log_path)


def test_multi_continue():
    """Multiple --continue invocations: costs/tokens/duration/turns should be summed."""
    with tempfile.NamedTemporaryFile(suffix="-autodl.json", delete=False) as tmp:
        out_path = tmp.name
    try:
        r = run_script(os.path.join(TESTDATA, "multi_continue.jsonl"), out_path)
        assert r.returncode == 0, f"Script failed: {r.stderr}"

        data = load_autodl(out_path)
        row = data["rows"][0]

        # Cost: 3.50 + 0.75 + 0.25 = 4.50
        assert row["total_cost_usd"] == "4.500000", f"Expected 4.500000, got {row['total_cost_usd']}"
        # Duration: 60000 + 15000 + 5000 = 80000
        assert row["duration_ms"] == "80000", f"Expected 80000, got {row['duration_ms']}"
        # API duration: 55000 + 12000 + 4000 = 71000
        assert row["duration_api_ms"] == "71000", f"Expected 71000, got {row['duration_api_ms']}"
        # Turns: 10 + 3 + 1 = 14
        assert row["num_turns"] == "14", f"Expected 14, got {row['num_turns']}"
        # TTFT: from first result only
        assert row["ttft_ms"] == "1200", f"Expected 1200, got {row['ttft_ms']}"
        # Tokens: summed across all results
        assert row["input_tokens"] == "8000"  # 5000+2000+1000
        assert row["output_tokens"] == "12500"  # 8000+3000+1500
        assert row["cache_read_input_tokens"] == "180000"  # 100000+50000+30000
        assert row["cache_creation_input_tokens"] == "27000"  # 20000+5000+2000

        # Identity from first init
        assert row["session_id"] == "test-session-multi"
        assert row["model"] == "claude-opus-4-6"

        # Tool calls: Skill(1) + Read(1) + Write(1) = 3 across all invocations
        assert row["total_tool_calls"] == "3"

        # Outcome from last result
        assert row["is_error"] == "0"

        print("PASS: test_multi_continue")
    finally:
        os.unlink(out_path)


def test_otel_input():
    """OTEL JSONL input should produce valid autodl with cost/token data."""
    with tempfile.NamedTemporaryFile(suffix="-autodl.json", delete=False) as tmp:
        out_path = tmp.name
    try:
        r = run_script(os.path.join(TESTDATA, "otel_metrics.jsonl"), out_path)
        assert r.returncode == 0, f"Script failed: {r.stderr}"
        assert "format=otel" in r.stdout

        data = load_autodl(out_path)
        row = data["rows"][0]

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
        # Identity from stream-json
        assert row["session_id"] == "test-session-001"
        assert row["claude_code_version"] == "2.1.153"
        assert row["plugins_loaded"] == "ci"
        assert "ci:payload-analysis" in row["prompt"]
        # Duration/turns from stream results
        assert row["duration_ms"] == "30000"
        assert row["num_turns"] == "4"

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


def test_schema_matches_row_fields():
    with tempfile.NamedTemporaryFile(suffix="-autodl.json", delete=False) as tmp:
        out_path = tmp.name
    try:
        run_script(os.path.join(TESTDATA, "valid_output.jsonl"), out_path)
        data = load_autodl(out_path)
        schema_fields = set(data["schema"].keys())
        row_fields = set(data["rows"][0].keys())
        assert schema_fields == row_fields, (
            f"Schema/row mismatch: "
            f"in schema only: {schema_fields - row_fields}, "
            f"in row only: {row_fields - schema_fields}"
        )
        print("PASS: test_schema_matches_row_fields")
    finally:
        os.unlink(out_path)


if __name__ == "__main__":
    test_valid_output()
    test_error_output()
    test_with_subagents()
    test_multi_continue()
    test_no_result_message()
    test_schema_matches_row_fields()
    test_otel_input()
    test_otel_with_stream_enrichment()
    test_otel_schema_matches_row()
    print("\nAll tests passed.")
