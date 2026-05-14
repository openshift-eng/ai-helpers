#!/usr/bin/env python3
"""
AI Docs Telemetry Analysis Script

Analyzes Claude Code session logs to track ai-docs usage patterns.
Parses session JSONL files to extract Read tool calls to ai-docs files.

Usage:
  ai_docs_telemetry.py -scan [-project <name>]
  ai_docs_telemetry.py -session <path-to-session.jsonl>
"""

import sys
import json
import os
import pathlib
import datetime
import argparse
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, asdict


@dataclass
class FileAccess:
    """Represents a single file access in the session."""
    path: str
    sequence: int
    time: str


@dataclass
class PlatformInfo:
    """Platform information."""
    name: str = "claude-code"
    version: str = "unknown"


@dataclass
class RepositoryInfo:
    """Repository information extracted from session path."""
    name: str
    path: str


@dataclass
class DocumentationInfo:
    """Documentation usage information."""
    entry_point: str
    files_accessed: List[Dict[str, Any]]
    total_files: int


@dataclass
class TelemetryEvent:
    """Complete telemetry event."""
    event_type: str
    version: str
    timestamp: str
    session_id: str
    platform: Dict[str, str]
    repository: Dict[str, str]
    documentation: Dict[str, Any]


def extract_repo_info(session_path: str) -> RepositoryInfo:
    """
    Extract repository information from session path.
    Path format: ~/.claude/projects/<repo-path-hash>/<session-id>.jsonl
    """
    parts = session_path.split("/projects/")
    if len(parts) < 2:
        return RepositoryInfo(name="unknown", path="unknown")

    # Get the project directory name
    project_dir = parts[1].split("/")[0]

    # Decode project name (simplified - just replace dashes with slashes)
    repo_name = project_dir.replace("-", "/")

    return RepositoryInfo(name=repo_name, path=project_dir)


def detect_entry_point(files: List[FileAccess]) -> str:
    """Determine how user discovered ai-docs."""
    if not files:
        return "unknown"

    first = files[0].path
    if first.endswith("AGENTS.md") or first.endswith("CLAUDE.md"):
        return "AGENTS.md"
    if first.endswith("README.md"):
        return "README.md"

    return "direct-search"


def process_session(session_path: str) -> Optional[TelemetryEvent]:
    """
    Analyze a Claude Code session log and extract ai-docs usage.
    Returns None if no ai-docs usage detected.
    """
    try:
        with open(session_path, 'r') as f:
            content = f.read()
    except Exception as e:
        print(f"Error reading session: {e}", file=sys.stderr)
        return None

    lines = content.split('\n')
    ai_docs_files: List[FileAccess] = []
    session_id = pathlib.Path(session_path).stem

    for line in lines:
        if not line.strip():
            continue

        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue

        # Look for Read tool calls to ai-docs files
        if event.get("type") != "assistant":
            continue

        msg = event.get("message", {})
        content_arr = msg.get("content", [])

        for item in content_arr:
            if not isinstance(item, dict):
                continue

            if item.get("type") == "tool_use" and item.get("name") == "Read":
                input_data = item.get("input", {})
                file_path = input_data.get("file_path", "")

                # Check if it's an ai-docs file or AGENTS.md
                if ("ai-docs/" in file_path or
                    file_path.endswith("AGENTS.md") or
                    file_path.endswith("CLAUDE.md")):

                    timestamp = event.get("timestamp", datetime.datetime.now().isoformat())

                    ai_docs_files.append(FileAccess(
                        path=file_path,
                        sequence=len(ai_docs_files) + 1,
                        time=timestamp
                    ))

    if not ai_docs_files:
        return None

    # Extract repository info
    repo_info = extract_repo_info(session_path)

    # Build telemetry event
    event = TelemetryEvent(
        event_type="ai_docs_usage",
        version="1.0",
        timestamp=datetime.datetime.now().isoformat(),
        session_id=session_id,
        platform=asdict(PlatformInfo()),
        repository=asdict(repo_info),
        documentation={
            "entry_point": detect_entry_point(ai_docs_files),
            "files_accessed": [asdict(f) for f in ai_docs_files],
            "total_files": len(ai_docs_files)
        }
    )

    return event


def scan_recent_sessions(project_filter: Optional[str] = None) -> List[TelemetryEvent]:
    """
    Scan ~/.claude/projects/ for recent sessions with ai-docs usage.
    Returns list of telemetry events.
    """
    home_dir = pathlib.Path.home()
    projects_dir = home_dir / ".claude" / "projects"

    if not projects_dir.exists():
        print(f"Projects directory not found: {projects_dir}", file=sys.stderr)
        return []

    events = []
    processed_count = 0
    seven_days_ago = datetime.datetime.now() - datetime.timedelta(days=7)

    # Walk through all project directories
    for session_file in projects_dir.glob("**/*.jsonl"):
        # Skip files older than 7 days
        mtime = datetime.datetime.fromtimestamp(session_file.stat().st_mtime)
        if mtime < seven_days_ago:
            continue

        # Filter by project if specified
        if project_filter and project_filter not in str(session_file):
            continue

        processed_count += 1

        # Quick pre-filter: check if file contains ai-docs markers
        try:
            content = session_file.read_text()
            if not ("ai-docs/" in content or "AGENTS.md" in content):
                continue
        except Exception:
            continue

        # Process session
        event = process_session(str(session_file))
        if event:
            events.append(event)

    print(f"\n📊 Summary: {processed_count} sessions scanned, {len(events)} with ai-docs usage",
          file=sys.stderr)

    return events


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Analyze Claude Code session logs for ai-docs usage"
    )
    parser.add_argument("-scan", action="store_true",
                       help="Scan all recent Claude Code sessions (last 7 days)")
    parser.add_argument("-project", type=str,
                       help="Filter by project name (e.g., 'enhancements', 'machine-config-operator')")
    parser.add_argument("-session", type=str,
                       help="Analyze a specific session JSONL file")

    args = parser.parse_args()

    if args.scan:
        events = scan_recent_sessions(args.project)
        if events:
            # Output as JSON array
            print(json.dumps([asdict(e) for e in events], indent=2))
    elif args.session:
        event = process_session(args.session)
        if event:
            print(json.dumps(asdict(event), indent=2))
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
