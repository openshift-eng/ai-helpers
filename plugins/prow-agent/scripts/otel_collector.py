#!/usr/bin/env python3
"""Lightweight OTLP HTTP/JSON receiver for Claude Code telemetry.

Starts an HTTP server that accepts OTLP metric, log, and trace exports
from Claude Code and writes each payload as a JSONL record. Designed to
run as a sidecar process in Prow CI jobs.

Based on the collector in https://github.com/opendatahub-io/agentic-ci

Usage:
    python3 otel_collector.py --port-file /tmp/otel-port --log-file /tmp/claude-otel.jsonl

The server binds to an ephemeral port on 127.0.0.1 and writes the
assigned port number to --port-file for the caller to read.
"""

import argparse
import json
import os
import signal
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer

MAX_BODY_SIZE = 1_048_576  # 1 MB


class OTLPHandler(BaseHTTPRequestHandler):
    log_file = None

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
        except ValueError:
            self.send_error(400, "Invalid Content-Length")
            return
        if length > MAX_BODY_SIZE:
            self.send_error(413, "Payload Too Large")
            return

        body = self.rfile.read(length) if length else b""
        try:
            payload = json.loads(body) if body else {}
        except json.JSONDecodeError:
            payload = {"raw": body.decode("utf-8", errors="replace")}

        record = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "path": self.path,
            "payload": payload,
        }
        with open(self.log_file, "a") as f:
            f.write(json.dumps(record) + "\n")

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"partialSuccess":{}}')

    def log_message(self, format, *args):
        pass  # suppress request logging


def parse_metrics(log_file):
    """Parse an OTEL JSONL log file and return structured metrics.

    Returns (token_totals, cost_totals, api_requests, active_time) where:
      - token_totals: dict[(model, type)] -> count
      - cost_totals: dict[model] -> usd
      - api_requests: list of dicts with request-level attributes
      - active_time: dict[time_type] -> seconds
    """
    records = []
    try:
        with open(log_file) as f:
            for line in f:
                line = line.strip()
                if line:
                    records.append(json.loads(line))
    except FileNotFoundError:
        return {}, {}, [], {}

    token_totals = defaultdict(float)
    cost_totals = defaultdict(float)
    api_requests = []
    active_time = defaultdict(float)

    for rec in records:
        path = rec.get("path", "")
        payload = rec.get("payload", {})

        if "/v1/metrics" in path:
            for rm in payload.get("resourceMetrics", []):
                for sm in rm.get("scopeMetrics", []):
                    for metric in sm.get("metrics", []):
                        name = metric.get("name", "")
                        data = metric.get("sum", metric.get("gauge", metric.get("histogram", {})))
                        for dp in data.get("dataPoints", []):
                            attrs = {
                                a["key"]: a["value"].get(
                                    "stringValue",
                                    a["value"].get("intValue", a["value"].get("doubleValue")),
                                )
                                for a in dp.get("attributes", [])
                            }
                            value = dp.get("asDouble", dp.get("asInt", 0))

                            if name == "claude_code.token.usage":
                                model = attrs.get("model", "unknown")
                                token_type = attrs.get("type", "unknown")
                                token_totals[(model, token_type)] += value
                            elif name == "claude_code.cost.usage":
                                model = attrs.get("model", "unknown")
                                cost_totals[model] += value
                            elif name == "claude_code.active_time.total":
                                time_type = attrs.get("type", "unknown")
                                active_time[time_type] += value

        elif "/v1/logs" in path:
            for rl in payload.get("resourceLogs", []):
                for sl in rl.get("scopeLogs", []):
                    for lr in sl.get("logRecords", []):
                        event_name = ""
                        event_attrs = {}
                        for a in lr.get("attributes", []):
                            key = a["key"]
                            val = a["value"]
                            v = val.get("stringValue", val.get("intValue", val.get("doubleValue")))
                            event_attrs[key] = v
                            if key == "event.name":
                                event_name = v
                        if event_name == "claude_code.api_request":
                            api_requests.append(event_attrs)

    return dict(token_totals), dict(cost_totals), api_requests, dict(active_time)


def print_summary(log_file):
    """Print a human-readable token/cost summary from an OTEL JSONL log."""
    token_totals, cost_totals, api_requests, active_time = parse_metrics(log_file)

    if not token_totals and not cost_totals:
        print("No OTEL data collected.")
        return

    if token_totals:
        models = sorted(set(m for m, _ in token_totals.keys()))
        for model in models:
            print(f"\n  Model: {model}")
            print(f"  {'Token Type':<25} {'Count':>12}")
            print(f"  {'-' * 25} {'-' * 12}")
            model_tokens = {t: c for (m, t), c in token_totals.items() if m == model}
            total = 0
            for token_type in ["input", "cacheRead", "cacheCreation", "output"]:
                if token_type in model_tokens:
                    count = model_tokens[token_type]
                    total += count
                    print(f"  {token_type:<25} {count:>12,.0f}")
            print(f"  {'TOTAL':<25} {total:>12,.0f}")

    if cost_totals:
        print(f"\n  {'Model':<30} {'Cost (USD)':>12}")
        print(f"  {'-' * 30} {'-' * 12}")
        grand_total = 0.0
        for model in sorted(cost_totals.keys()):
            cost = cost_totals[model]
            grand_total += cost
            print(f"  {model:<30} ${cost:>11.4f}")
        if len(cost_totals) > 1:
            print(f"  {'TOTAL':<30} ${grand_total:>11.4f}")

    if active_time:
        print("\n  Active Time:")
        for time_type, seconds in sorted(active_time.items()):
            mins, secs = divmod(int(seconds), 60)
            print(f"    {time_type}: {mins}m {secs}s")

    if api_requests:
        print(f"\n  API Requests: {len(api_requests)}")


def main():
    parser = argparse.ArgumentParser(description="OTLP HTTP/JSON collector for Claude Code telemetry")
    parser.add_argument("--port-file", required=True, help="File to write the assigned port number to")
    parser.add_argument("--log-file", default="/tmp/claude-otel.jsonl", help="JSONL output file")
    parser.add_argument("--bind", default="127.0.0.1", help="Bind address (default: 127.0.0.1)")
    parser.add_argument("--summary", action="store_true", help="Print summary from existing log file and exit")
    args = parser.parse_args()

    if args.summary:
        print_summary(args.log_file)
        return

    OTLPHandler.log_file = args.log_file

    server = HTTPServer((args.bind, 0), OTLPHandler)
    port = server.server_address[1]

    with open(args.port_file, "w") as f:
        f.write(str(port))

    def shutdown(signum, frame):
        server.shutdown()

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    print(f"OTEL collector listening on {args.bind}:{port}", file=sys.stderr)
    server.serve_forever()


if __name__ == "__main__":
    main()
