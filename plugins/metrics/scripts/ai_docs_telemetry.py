#!/usr/bin/env python3
"""
AI Docs Telemetry Analysis Script

Analyzes Claude Code session logs to track ai-docs usage patterns.
Parses session JSONL files to extract tool calls (Read, Grep, Glob)
that reference ai-docs files.

Usage:
  ai_docs_telemetry.py -scan [-project <name>]
  ai_docs_telemetry.py -session <path-to-session.jsonl>
"""

import sys
import json
import pathlib
import datetime
import argparse
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, asdict


@dataclass
class FileAccess:
    path: str
    sequence: int
    time: str
    tool: str = "Read"


@dataclass
class PlatformInfo:
    name: str = "claude-code"
    version: str = "unknown"


@dataclass
class RepositoryInfo:
    name: str
    path: str


@dataclass
class TelemetryEvent:
    event_type: str
    version: str
    timestamp: str
    session_id: str
    platform: Dict[str, str]
    repository: Dict[str, str]
    documentation: Dict[str, Any]


_AI_DOCS_MARKERS = ("ai-docs", "AGENTS.md", "CLAUDE.md")


def _is_ai_docs_ref(value: str) -> bool:
    return any(marker in value for marker in _AI_DOCS_MARKERS)


def extract_repo_info(session_path: str) -> RepositoryInfo:
    # Path format: ~/.claude/projects/<repo-path-hash>/<session-id>.jsonl
    parts = session_path.split("/projects/")
    if len(parts) < 2:
        return RepositoryInfo(name="unknown", path="unknown")

    project_dir = parts[-1].split("/")[0]

    return RepositoryInfo(name=project_dir, path=project_dir)


def process_session(session_path: str, content: Optional[str] = None) -> Optional[TelemetryEvent]:
    if content is None:
        try:
            with open(session_path, 'r') as f:
                content = f.read()
        except Exception as e:
            print(f"Error reading session: {e}", file=sys.stderr)
            return None

    lines = content.split('\n')
    ai_docs_files: List[FileAccess] = []
    sub_agents: List[Dict] = []
    session_id = pathlib.Path(session_path).stem

    for line in lines:
        if not line.strip():
            continue

        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue

        if not isinstance(event, dict) or event.get("type") != "assistant":
            continue

        msg = event.get("message") or {}
        content_arr = msg.get("content") or []

        for item in content_arr:
            if not isinstance(item, dict) or item.get("type") != "tool_use":
                continue

            tool_name = item.get("name", "")
            inp = item.get("input") or {}

            if tool_name == "Agent":
                sub_agents.append({
                    "spawned_at":  event.get("timestamp", ""),
                    "description": inp.get("description", ""),
                })
                continue

            if tool_name == "Read":
                target = inp.get("file_path", "")
            elif tool_name == "Grep":
                target = inp.get("path", "")
            elif tool_name == "Glob":
                target = inp.get("pattern", "")
            else:
                continue

            if target and _is_ai_docs_ref(target):
                timestamp = event.get("timestamp", datetime.datetime.now().isoformat())
                ai_docs_files.append(FileAccess(
                    path=target,
                    sequence=len(ai_docs_files) + 1,
                    time=timestamp,
                    tool=tool_name,
                ))

    if not ai_docs_files:
        return None

    seen_paths: set = set()
    unique_files: List[FileAccess] = []
    for f in ai_docs_files:
        if f.path not in seen_paths:
            seen_paths.add(f.path)
            unique_files.append(f)

    repo_info = extract_repo_info(session_path)

    telemetry = TelemetryEvent(
        event_type="ai_docs_usage",
        version="1.0",
        timestamp=datetime.datetime.now().isoformat(),
        session_id=session_id,
        platform=asdict(PlatformInfo()),
        repository=asdict(repo_info),
        documentation={
            "files_accessed":    [asdict(f) for f in ai_docs_files],
            "unique_files":      [asdict(f) for f in unique_files],
            "total_accesses":    len(ai_docs_files),
            "unique_file_count": len(unique_files),
            "total_files":       len(unique_files),
            "sub_agents":        sub_agents,
        }
    )

    return telemetry


def scan_recent_sessions(project_filter: Optional[str] = None) -> List[TelemetryEvent]:
    home_dir = pathlib.Path.home()
    projects_dir = home_dir / ".claude" / "projects"

    if not projects_dir.exists():
        print(f"Projects directory not found: {projects_dir}", file=sys.stderr)
        return []

    events = []
    processed_count = 0
    seven_days_ago = datetime.datetime.now() - datetime.timedelta(days=7)

    for session_file in projects_dir.glob("**/*.jsonl"):
        mtime = datetime.datetime.fromtimestamp(session_file.stat().st_mtime)
        if mtime < seven_days_ago:
            continue

        if project_filter and project_filter not in str(session_file):
            continue

        processed_count += 1

        # Pre-filter: skip files that contain no ai-docs markers (avoids full parse)
        try:
            content = session_file.read_text()
            if not any(marker in content for marker in _AI_DOCS_MARKERS):
                continue
        except Exception as e:
            print(f"Warning: skipping {session_file}: {e}", file=sys.stderr)
            continue

        event = process_session(str(session_file), content=content)
        if event:
            events.append(event)

    print(f"\n📊 Summary: {processed_count} sessions scanned, {len(events)} with ai-docs usage",
          file=sys.stderr)

    return events


def main():
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
