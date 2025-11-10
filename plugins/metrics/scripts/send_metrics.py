#!/usr/bin/env python3
"""
AI Helpers Metrics Tracking Script

Reads a JSON payload from stdin (including session_id), processes it for specific hook events,
and sends anonymous usage metrics in the background.

A persistent anonymous user ID (UUID) is generated on first run and stored in the metrics
directory to allow tracking unique users across sessions while preserving privacy.

Logs all attempts locally.
"""

import sys
import json
import os
import pathlib
import datetime
import hashlib
import platform
import threading
import argparse
import uuid
from urllib import request, error

# --- Constants ---

# Allow overriding metrics URL via environment variable
# If CLAUDE_METRICS_URL is set, use it as a prefix and append /events
# Otherwise use production URL
METRICS_BASE_URL = os.environ.get('CLAUDE_METRICS_URL', 'https://us-central1-openshift-ci-data-analysis.cloudfunctions.net/metrics-upload')
METRICS_URL = f"{METRICS_BASE_URL}/events"

NETWORK_TIMEOUT_SECONDS = 2
LOG_FILE_NAME = "metrics.log"
ANONYMOUS_ID_FILE_NAME = ".anonymous_id"

# --- Core Logic ---

def calculate_mac(session_id: str, timestamp: str) -> str:
    """
    Computes a SHA256 MAC from the session ID and timestamp.
    """
    mac_input = f"{session_id}{timestamp}"
    return hashlib.sha256(mac_input.encode('utf-8')).hexdigest()

def get_or_create_anonymous_id(metrics_dir: pathlib.Path) -> str | None:
    """
    Get or create a persistent anonymous user ID stored in the metrics directory.
    Returns None if unable to read or create the ID.
    """
    try:
        id_file = metrics_dir / ANONYMOUS_ID_FILE_NAME

        if id_file.exists():
            return id_file.read_text().strip()

        # Generate new random UUID
        anonymous_id = str(uuid.uuid4())
        id_file.write_text(anonymous_id)
        return anonymous_id
    except Exception:
        # Failed to read/write ID file, return None
        return None

def log_message(log_file: pathlib.Path | None, timestamp: str, message: str, verbose: bool = False):
    """
    Appends a formatted message to the local log file if verbose is True.
    """
    if not verbose or log_file is None:
        return

    try:
        with log_file.open('a', encoding='utf-8') as f:
            f.write(f"[{timestamp}] {message}\n")
    except OSError:
        # Failed to write to log, but don't crash the script
        pass

def send_metrics(payload: dict, log_file: pathlib.Path | None, timestamp: str, verbose: bool = False):
    """
    Sends the metrics payload to the endpoint.
    This function is designed to be run in a background thread.
    """
    try:
        data = json.dumps(payload).encode('utf-8')
        headers = {"Content-Type": "application/json", "User-Agent": "ai-helpers-metrics-py"}

        req = request.Request(METRICS_URL, data=data, headers=headers, method="POST")

        # Log full API call details when verbose
        if verbose:
            log_message(log_file, timestamp, f"API Request: POST {METRICS_URL}", verbose)
            log_message(log_file, timestamp, f"Headers: {json.dumps(headers)}", verbose)
            log_message(log_file, timestamp, f"Payload: {json.dumps(payload, indent=2)}", verbose)

        with request.urlopen(req, timeout=NETWORK_TIMEOUT_SECONDS) as response:
            body = response.read().decode('utf-8', 'ignore')
            log_message(log_file, timestamp, f"Response: HTTP {response.status} - {body}", verbose)

    except error.HTTPError as e:
        # Handle HTTP errors (e.g., 4xx, 5xx)
        try:
            body = e.read().decode('utf-8', 'ignore')
        except Exception:
            body = "(could not read error body)"
        log_message(log_file, timestamp, f"ERROR: HTTP {e.code} - {body}", verbose)

    except Exception as e:
        # Handle network/timeout errors
        error_detail = f"{type(e).__name__}: {str(e)}"
        log_message(log_file, timestamp, f"ERROR: Failed to send ({error_detail})", verbose)

# --- Main Execution ---

def main():
    # --- 0. Parse Command-Line Arguments ---
    parser = argparse.ArgumentParser(description="AI Helpers Metrics Tracking")
    parser.add_argument('-v', '--verbose', action='store_true', help='Enable verbose logging')
    args = parser.parse_args()
    verbose = args.verbose

    # --- 1. Setup Paths ---
    log_file = None
    anonymous_id = None
    try:
        # Use CLAUDE_PLUGIN_ROOT for storing metrics
        plugin_root = os.environ.get('CLAUDE_PLUGIN_ROOT')
        if plugin_root:
            metrics_dir = pathlib.Path(plugin_root).resolve()  # Use absolute path

            # Ensure the directory exists
            metrics_dir.mkdir(parents=True, exist_ok=True)

            log_file = metrics_dir / LOG_FILE_NAME
            anonymous_id = get_or_create_anonymous_id(metrics_dir)

    except Exception:
        # Failed to access/create directory files, but continue without logging
        log_file = None
        anonymous_id = None

    # --- 2. Read and Parse Input ---
    try:
        input_data = json.load(sys.stdin)
        prompt = input_data.get("prompt")
        hook_event = input_data.get("hook_event_name")
        session_id = input_data.get("session_id")
        tool = input_data.get("tool_name")  # PreToolUse sends "tool_name"
        parameters = input_data.get("tool_input", {})  # PreToolUse sends "tool_input"
    except json.JSONDecodeError:
        # Input was not valid JSON
        sys.exit(1)

    # Require session_id in input
    if not session_id:
        sys.exit(1)

    # --- 3. Check Event and Prompt Condition ---
    metric_type = None
    metric_name = None
    prompt_length = 0

    if hook_event == "UserPromptSubmit" and prompt and prompt.startswith('/'):
        metric_type = "slash_command"
        prompt_length = len(prompt)

        # Extract command name (part after / up to first space)
        parts = prompt[1:].split(maxsplit=1)
        metric_name = parts[0]

    elif hook_event == "PreToolUse" and tool == "Skill":
        metric_type = "skill"
        metric_name = parameters.get("skill")  # tool_input has a "skill" field

    # If conditions not met, exit silently
    if not metric_name:
        sys.exit(0)

    # --- 4. Prepare and Send Metrics ---
    # Use RFC3339 format (ISO 8601 with timezone)
    timestamp = datetime.datetime.now(datetime.UTC).isoformat(timespec='seconds')
    os_name = platform.system().lower()

    # Simple hash of session_id + timestamp
    mac = calculate_mac(session_id, timestamp)

    payload = {
        "type": metric_type,
        "name": metric_name,
        "engine": "claude",
        "version": "1.0",
        "timestamp": timestamp,
        "session_id": session_id,
        "os": os_name,
        "mac": mac,
        "prompt_length": prompt_length,
        "user_id": anonymous_id  # Persistent anonymous user identifier
    }

    # Log locally (synchronous)
    log_message(log_file, timestamp, f"Sending metrics: {json.dumps(payload)}", verbose)

    # Send metrics (asynchronous in a non-daemon thread)
    # The script will exit, but the thread will continue
    # running until the network request finishes or times out.
    thread = threading.Thread(
        target=send_metrics,
        args=(payload, log_file, timestamp, verbose),
        daemon=False # Allows thread to outlive main script exit
    )
    thread.start()

if __name__ == "__main__":
    main()
