#!/usr/bin/env python3
"""Minimal OTLP HTTP/JSON receiver for local Claude Code telemetry.

Listens on a fixed port (default 4318, the standard OTLP HTTP port) and
appends each OTLP payload as a JSONL record. Designed for interactive
local use alongside Claude Code plugins.

Unlike prow-agent's otel_collector.py (ephemeral port + port-file handshake
for CI), this collector uses a fixed port so Claude Code's OTEL endpoint
can be pre-configured once in settings.json without any env var exports.

Usage:
    python3 collector.py [--port 4318] [--log-file ~/.claude/metrics/otel.jsonl]
    python3 collector.py --daemon --fresh   # background, fresh log (SessionStart)
    python3 collector.py --stop             # send SIGTERM to running collector
"""

import argparse
import json
import os
import signal
import sys
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer

MAX_BODY_SIZE = 1_048_576  # 1 MB


class OTLPServer(HTTPServer):
    allow_reuse_address = True


DEFAULT_PID_FILE = "/tmp/claude-otel-collector.pid"


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
        pass  # suppress per-request logging


def stop_collector(pid_file):
    if not os.path.exists(pid_file):
        return
    try:
        pid = int(open(pid_file).read().strip())
        os.kill(pid, signal.SIGTERM)
    except (ValueError, ProcessLookupError, OSError):
        pass
    finally:
        try:
            os.remove(pid_file)
        except OSError:
            pass


def main():
    parser = argparse.ArgumentParser(description="Local OTLP collector for Claude Code")
    parser.add_argument("--port", type=int, default=4318, help="Port to listen on (default: 4318)")
    parser.add_argument(
        "--log-file",
        default=os.path.expanduser("~/.claude/metrics/otel-current.jsonl"),
        help="JSONL output file",
    )
    parser.add_argument("--pid-file", default=DEFAULT_PID_FILE, help="PID file for lifecycle management")
    parser.add_argument("--daemon", action="store_true", help="Fork into background and return immediately")
    parser.add_argument("--fresh", action="store_true", help="Truncate log file before starting")
    parser.add_argument("--stop", action="store_true", help="Stop a running collector via its PID file")
    args = parser.parse_args()

    if args.stop:
        stop_collector(args.pid_file)
        return

    if args.daemon:
        # Stop any existing collector on this pid-file before forking so the
        # port is free and the old JSONL is closed cleanly.
        import time
        stop_collector(args.pid_file)
        time.sleep(0.6)  # wait for serve_forever's select loop (0.5s timeout) to exit

    if args.fresh and os.path.exists(args.log_file):
        os.remove(args.log_file)

    os.makedirs(os.path.dirname(os.path.abspath(args.log_file)), exist_ok=True)

    if args.daemon:
        pid = os.fork()
        if pid > 0:
            sys.exit(0)  # parent exits immediately; child continues below
        os.setsid()
        devnull = os.open(os.devnull, os.O_RDWR)
        for fd in (0, 1, 2):
            os.dup2(devnull, fd)
        os.close(devnull)

    OTLPHandler.log_file = args.log_file
    try:
        server = OTLPServer(("127.0.0.1", args.port), OTLPHandler)
    except OSError as e:
        print(f"Error: cannot bind to port {args.port}: {e}", file=sys.stderr)
        sys.exit(1)

    with open(args.pid_file, "w") as f:
        f.write(str(os.getpid()))

    def shutdown(signum, frame):
        def _stop():
            server.shutdown()
            server.server_close()
        threading.Thread(target=_stop).start()
        if os.path.exists(args.pid_file):
            os.remove(args.pid_file)

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    server.serve_forever()


if __name__ == "__main__":
    main()
