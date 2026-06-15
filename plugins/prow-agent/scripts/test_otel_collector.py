#!/usr/bin/env python3
"""Tests for otel_collector.py."""

import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.request

SCRIPT = os.path.join(os.path.dirname(__file__), "otel_collector.py")
TESTDATA = os.path.join(os.path.dirname(__file__), "testdata")


def test_server_lifecycle():
    """Start collector, POST a payload, verify JSONL, stop."""
    with tempfile.TemporaryDirectory() as tmpdir:
        port_file = os.path.join(tmpdir, "port")
        log_file = os.path.join(tmpdir, "otel.jsonl")

        proc = subprocess.Popen(
            [sys.executable, SCRIPT,
             "--port-file", port_file,
             "--log-file", log_file],
            stderr=subprocess.DEVNULL,
        )
        try:
            for _ in range(50):
                if os.path.exists(port_file):
                    break
                time.sleep(0.1)
            else:
                raise RuntimeError("Collector did not write port file")

            with open(port_file) as f:
                port = int(f.read().strip())

            payload = {
                "resourceMetrics": [{
                    "scopeMetrics": [{
                        "metrics": [{
                            "name": "claude_code.cost.usage",
                            "sum": {
                                "dataPoints": [{
                                    "attributes": [
                                        {"key": "model", "value": {"stringValue": "test-model"}}
                                    ],
                                    "asDouble": 1.23,
                                }]
                            }
                        }]
                    }]
                }]
            }

            data = json.dumps(payload).encode()
            req = urllib.request.Request(
                f"http://127.0.0.1:{port}/v1/metrics",
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            resp = urllib.request.urlopen(req)
            assert resp.status == 200

            # Give it a moment to flush
            time.sleep(0.2)

            with open(log_file) as f:
                records = [json.loads(line) for line in f]

            assert len(records) == 1
            assert records[0]["path"] == "/v1/metrics"
            assert records[0]["payload"] == payload
            assert "ts" in records[0]

            print("PASS: test_server_lifecycle")
        finally:
            proc.kill()
            proc.wait(timeout=5)


def test_parse_metrics():
    """Parse the OTEL test fixture and verify extracted metrics."""
    from otel_collector import parse_metrics

    token_totals, cost_totals, api_requests, active_time = parse_metrics(
        os.path.join(TESTDATA, "otel_metrics.jsonl")
    )

    # Tokens: 5000+3000=8000 input for opus, 2000 for sonnet
    assert token_totals[("claude-opus-4-6", "input")] == 8000
    assert token_totals[("claude-opus-4-6", "output")] == 12000  # 8000+4000
    assert token_totals[("claude-opus-4-6", "cacheRead")] == 100000
    assert token_totals[("claude-opus-4-6", "cacheCreation")] == 20000
    assert token_totals[("claude-sonnet-4-5", "input")] == 2000
    assert token_totals[("claude-sonnet-4-5", "output")] == 1500

    # Cost: 2.50 + 1.00 = 3.50 for opus, 0.25 for sonnet
    assert abs(cost_totals["claude-opus-4-6"] - 3.50) < 0.001
    assert abs(cost_totals["claude-sonnet-4-5"] - 0.25) < 0.001

    # API requests: 3 (Read, Bash, Read)
    assert len(api_requests) == 3
    tool_names = [r.get("tool_name") for r in api_requests]
    assert tool_names.count("Read") == 2
    assert tool_names.count("Bash") == 1

    # Active time
    assert abs(active_time["api"] - 45.5) < 0.001

    print("PASS: test_parse_metrics")


def test_print_summary():
    """Smoke test that print_summary doesn't crash."""
    from otel_collector import print_summary
    print_summary(os.path.join(TESTDATA, "otel_metrics.jsonl"))
    print("PASS: test_print_summary")


def test_missing_log_file():
    """parse_metrics returns empty dicts for missing file."""
    from otel_collector import parse_metrics
    token_totals, cost_totals, api_requests, active_time = parse_metrics("/nonexistent")
    assert token_totals == {}
    assert cost_totals == {}
    assert api_requests == []
    assert active_time == {}
    print("PASS: test_missing_log_file")


if __name__ == "__main__":
    # Add scripts dir to path for imports
    sys.path.insert(0, os.path.dirname(__file__))
    test_parse_metrics()
    test_missing_log_file()
    test_print_summary()
    test_server_lifecycle()
    print("\nAll OTEL collector tests passed.")
