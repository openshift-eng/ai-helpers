#!/usr/bin/env python3
"""
AI Helpers Session Metrics Tracking Script

Reads session end event from stdin, parses the transcript JSONL file,
extracts session-level metrics, and sends them to the metrics endpoint.

Logs all attempts locally if verbose mode is enabled.
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
from typing import Optional
from urllib import request, error

# --- Constants ---

# Allow overriding metrics URL via environment variable
# If CLAUDE_METRICS_URL is set, use it as a prefix and append /sessions
# Otherwise use production URL
METRICS_BASE_URL = os.environ.get('CLAUDE_METRICS_URL', 'https://us-central1-openshift-ci-data-analysis.cloudfunctions.net/metrics-upload')
METRICS_URL = f"{METRICS_BASE_URL}/sessions"

NETWORK_TIMEOUT_SECONDS = 2
LOG_FILE_NAME = "metrics.log"
ANONYMOUS_ID_FILE_NAME = ".anonymous_id"

# --- Helper Functions ---

def get_or_create_anonymous_id(metrics_dir: pathlib.Path) -> Optional[str]:
    """
    Get or create a persistent anonymous user ID stored in the metrics directory.
    Returns None if unable to read or create the ID.
    """
    try:
        id_file = metrics_dir / ANONYMOUS_ID_FILE_NAME

        if id_file.exists():
            return id_file.read_text().strip()

        # Generate new random UUID
        import uuid
        anonymous_id = str(uuid.uuid4())
        id_file.write_text(anonymous_id)
        return anonymous_id
    except Exception:
        # Failed to read/write ID file, return None
        return None

def log_message(log_file: Optional[pathlib.Path], timestamp: str, message: str, verbose: bool = False, is_error: bool = False):
    """
    Appends a formatted message to the local log file.
    In normal mode (verbose=False), only logs errors (is_error=True).
    In verbose mode (verbose=True), logs all messages.
    """
    if log_file is None:
        return

    # Only log if verbose is enabled OR this is an error message
    if not verbose and not is_error:
        return

    try:
        with log_file.open('a', encoding='utf-8') as f:
            f.write(f"[{timestamp}] {message}\n")
    except OSError:
        # Failed to write to log, but don't crash the script
        pass

def parse_transcript(transcript_path: str, log_file: Optional[pathlib.Path] = None, verbose: bool = False) -> dict:
    """
    Parse the transcript JSONL file and extract session metrics.
    Returns a dict with all the session metrics.
    """
    metrics = {
        'turn_count': 0,
        'user_message_count': 0,
        'assistant_message_count': 0,
        'total_tool_calls': 0,
        'tool_error_count': 0,
        'bash_call_count': 0,
        'file_read_count': 0,
        'file_edit_count': 0,
        'file_write_count': 0,
        'grep_call_count': 0,
        'glob_call_count': 0,
        'web_fetch_call_count': 0,
        'web_search_call_count': 0,
        'total_input_tokens': 0,
        'total_output_tokens': 0,
        'cache_creation_tokens': 0,
        'cache_read_tokens': 0,
        'had_errors': False,
        'start_timestamp': None,
        'end_timestamp': None,
    }

    # Check if file exists
    if not os.path.exists(transcript_path):
        timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds')
        log_message(log_file, timestamp, f"ERROR: Transcript file does not exist: {transcript_path}", verbose=verbose, is_error=True)
        return metrics

    line_count = 0  # Initialize outside try block so it's accessible later
    try:
        with open(transcript_path, 'r', encoding='utf-8') as f:
            for line in f:
                line_count += 1
                try:
                    entry = json.loads(line.strip())
                except json.JSONDecodeError:
                    continue

                # Extract timestamp
                ts = entry.get('timestamp')
                if ts:
                    if metrics['start_timestamp'] is None:
                        metrics['start_timestamp'] = ts
                    metrics['end_timestamp'] = ts

                # Count messages by type
                entry_type = entry.get('type')
                if entry_type == 'user':
                    metrics['user_message_count'] += 1
                    # Count turns (user-assistant exchanges)
                    # We count user messages as proxy for turns
                    metrics['turn_count'] += 1
                elif entry_type == 'assistant':
                    metrics['assistant_message_count'] += 1

                    # Extract token usage from assistant messages
                    message = entry.get('message', {})
                    usage = message.get('usage', {})
                    if usage:
                        metrics['total_input_tokens'] += usage.get('input_tokens', 0)
                        metrics['total_output_tokens'] += usage.get('output_tokens', 0)
                        metrics['cache_creation_tokens'] += usage.get('cache_creation_input_tokens', 0)
                        metrics['cache_read_tokens'] += usage.get('cache_read_input_tokens', 0)

                    # Count tool calls
                    content = message.get('content', [])
                    if isinstance(content, list):
                        for item in content:
                            if isinstance(item, dict) and item.get('type') == 'tool_use':
                                metrics['total_tool_calls'] += 1
                                tool_name = item.get('name', '')

                                # Count specific tool types
                                if tool_name == 'Bash':
                                    metrics['bash_call_count'] += 1
                                elif tool_name == 'Read':
                                    metrics['file_read_count'] += 1
                                elif tool_name == 'Edit':
                                    metrics['file_edit_count'] += 1
                                elif tool_name == 'Write':
                                    metrics['file_write_count'] += 1
                                elif tool_name == 'Grep':
                                    metrics['grep_call_count'] += 1
                                elif tool_name == 'Glob':
                                    metrics['glob_call_count'] += 1
                                elif tool_name == 'WebFetch':
                                    metrics['web_fetch_call_count'] += 1
                                elif tool_name == 'WebSearch':
                                    metrics['web_search_call_count'] += 1

                # Check for errors in tool results
                tool_result = entry.get('toolUseResult', {})
                has_error = False

                # Check toolUseResult for errors
                if isinstance(tool_result, dict) and tool_result.get('is_error'):
                    has_error = True

                # Check message content for errors (safely)
                message = entry.get('message', {})
                if isinstance(message, dict):
                    content = message.get('content', [])
                    if isinstance(content, list) and len(content) > 0:
                        first_item = content[0]
                        if isinstance(first_item, dict) and first_item.get('is_error'):
                            has_error = True

                if has_error:
                    metrics['had_errors'] = True
                    metrics['tool_error_count'] += 1

    except Exception as e:
        # Failed to parse transcript, return partial metrics
        timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds')
        log_message(log_file, timestamp, f"ERROR parsing transcript: {type(e).__name__}: {str(e)}", verbose=verbose, is_error=True)

    return metrics

def send_session_metrics(payload: dict, log_file: Optional[pathlib.Path], timestamp: str, verbose: bool = False):
    """
    Sends the session metrics payload to the endpoint.
    This function is designed to be run in a background thread.
    """
    try:
        data = json.dumps(payload).encode('utf-8')
        headers = {"Content-Type": "application/json", "User-Agent": "ai-helpers-metrics-py"}

        req = request.Request(METRICS_URL, data=data, headers=headers, method="POST")

        # Log full API call details when verbose
        if verbose:
            log_message(log_file, timestamp, f"API Request: POST {METRICS_URL}", verbose=verbose)
            log_message(log_file, timestamp, f"Headers: {json.dumps(headers)}", verbose=verbose)
            log_message(log_file, timestamp, f"Payload: {json.dumps(payload, indent=2)}", verbose=verbose)

        with request.urlopen(req, timeout=NETWORK_TIMEOUT_SECONDS) as response:
            body = response.read().decode('utf-8', 'ignore')
            log_message(log_file, timestamp, f"Response: HTTP {response.status} - {body}", verbose=verbose)

    except error.HTTPError as e:
        # Handle HTTP errors (e.g., 4xx, 5xx) - Always log errors
        try:
            body = e.read().decode('utf-8', 'ignore')
        except Exception:
            body = "(could not read error body)"
        error_msg = f"ERROR: HTTP {e.code} - {body}\nData sent: {json.dumps(payload, indent=2)}"
        log_message(log_file, timestamp, error_msg, verbose=verbose, is_error=True)

    except Exception as e:
        # Handle network/timeout errors - Always log errors
        error_detail = f"{type(e).__name__}: {str(e)}"
        error_msg = f"ERROR: Failed to send ({error_detail})\nData sent: {json.dumps(payload, indent=2)}"
        log_message(log_file, timestamp, error_msg, verbose=verbose, is_error=True)

# --- Main Execution ---

def main():
    # --- 0. Parse Command-Line Arguments and Environment ---
    parser = argparse.ArgumentParser(description="AI Helpers Session Metrics Tracking")
    parser.add_argument('-v', '--verbose', action='store_true', help='Enable verbose logging')
    args = parser.parse_args()

    # Check environment variable for verbose mode (takes precedence over --verbose flag)
    verbose = os.environ.get('CLAUDE_METRICS_VERBOSE', '').lower() in ('1', 'true', 'yes')
    if args.verbose:
        verbose = True

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
        hook_event = input_data.get("hook_event_name")
        session_id = input_data.get("session_id")
        transcript_path = input_data.get("transcript_path")
        exit_reason = input_data.get("reason", "other")
    except json.JSONDecodeError:
        # Input was not valid JSON
        sys.exit(1)

    # Require session_id and transcript_path
    if not session_id or not transcript_path:
        sys.exit(1)

    # Only process SessionEnd events
    if hook_event != "SessionEnd":
        sys.exit(0)

    # --- 3. Parse Transcript ---
    session_metrics = parse_transcript(transcript_path, log_file, verbose)

    # Calculate session duration
    session_duration = 0
    if session_metrics['start_timestamp'] and session_metrics['end_timestamp']:
        try:
            start = datetime.datetime.fromisoformat(session_metrics['start_timestamp'].replace('Z', '+00:00'))
            end = datetime.datetime.fromisoformat(session_metrics['end_timestamp'].replace('Z', '+00:00'))
            session_duration = int((end - start).total_seconds())
        except Exception:
            pass

    # --- 4. Prepare and Send Metrics ---
    # Use RFC3339 format (ISO 8601 with timezone)
    timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds')
    os_name = platform.system().lower()

    # Calculate MAC: SHA256(session_id + start_timestamp)
    start_ts = session_metrics['start_timestamp'] or timestamp
    mac_input = f"{session_id}{start_ts}"
    mac = hashlib.sha256(mac_input.encode('utf-8')).hexdigest()

    payload = {
        "session_id": session_id,
        "user_id": anonymous_id,
        "os": os_name,
        "engine": "claude",

        "start_timestamp": start_ts,
        "end_timestamp": session_metrics['end_timestamp'] or timestamp,
        "session_duration": session_duration,
        "exit_reason": exit_reason,
        "mac": mac,

        "turn_count": session_metrics['turn_count'],
        "user_message_count": session_metrics['user_message_count'],
        "assistant_message_count": session_metrics['assistant_message_count'],

        "total_tool_calls": session_metrics['total_tool_calls'],
        "tool_error_count": session_metrics['tool_error_count'],
        "bash_call_count": session_metrics['bash_call_count'],
        "file_read_count": session_metrics['file_read_count'],
        "file_edit_count": session_metrics['file_edit_count'],
        "file_write_count": session_metrics['file_write_count'],
        "grep_call_count": session_metrics['grep_call_count'],
        "glob_call_count": session_metrics['glob_call_count'],
        "web_fetch_call_count": session_metrics['web_fetch_call_count'],
        "web_search_call_count": session_metrics['web_search_call_count'],

        "had_errors": session_metrics['had_errors'],
    }

    # Only include token metrics if they're non-zero (for privacy)
    if session_metrics['total_input_tokens'] > 0:
        payload['total_input_tokens'] = session_metrics['total_input_tokens']
    if session_metrics['total_output_tokens'] > 0:
        payload['total_output_tokens'] = session_metrics['total_output_tokens']
    if session_metrics['cache_creation_tokens'] > 0:
        payload['cache_creation_tokens'] = session_metrics['cache_creation_tokens']
    if session_metrics['cache_read_tokens'] > 0:
        payload['cache_read_tokens'] = session_metrics['cache_read_tokens']

    # Log locally (synchronous) - only in verbose mode
    log_message(log_file, timestamp, f"Sending session metrics: {json.dumps(payload)}", verbose=verbose)

    # Send metrics (asynchronous in a non-daemon thread)
    # The script will exit, but the thread will continue
    # running until the network request finishes or times out.
    thread = threading.Thread(
        target=send_session_metrics,
        args=(payload, log_file, timestamp, verbose),
        daemon=False  # Allows thread to outlive main script exit
    )
    thread.start()

if __name__ == "__main__":
    main()
