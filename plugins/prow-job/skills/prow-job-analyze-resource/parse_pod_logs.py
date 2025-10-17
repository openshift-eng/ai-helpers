#!/usr/bin/env python3
"""
Parse unstructured pod logs and search for resource references.
"""

import re
import sys
import json
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime


@dataclass
class ResourceSpec:
    """Specification for a resource to search for."""
    name: str
    kind: Optional[str] = None
    namespace: Optional[str] = None

    @classmethod
    def from_string(cls, spec_str: str) -> 'ResourceSpec':
        """Parse resource spec from string format: [namespace:][kind/]name"""
        namespace = None
        kind = None
        name = spec_str

        if ':' in spec_str:
            namespace, rest = spec_str.split(':', 1)
            spec_str = rest

        if '/' in spec_str:
            kind, name = spec_str.split('/', 1)

        return cls(name=name, kind=kind, namespace=namespace)


@dataclass
class PodLogEntry:
    """Parsed pod log entry with metadata."""
    filename: str
    line_number: int
    timestamp: Optional[str]
    level: str  # info, warn, error
    content: str  # Full line
    summary: str


# Common timestamp patterns
TIMESTAMP_PATTERNS = [
    # glog: I1016 21:35:33.920070
    (r'^([IWEF])(\d{4})\s+(\d{2}:\d{2}:\d{2}\.\d+)', 'glog'),
    # RFC3339: 2025-10-16T21:35:33.920070Z
    (r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z?)', 'rfc3339'),
    # Common: 2025-10-16 21:35:33
    (r'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})', 'common'),
    # Syslog: Oct 16 21:35:33
    (r'((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2}\s+\d{2}:\d{2}:\d{2})', 'syslog'),
]


# Log level patterns
LEVEL_PATTERNS = [
    # glog levels
    (r'^[I]', 'info'),
    (r'^[W]', 'warn'),
    (r'^[EF]', 'error'),
    # Standard levels
    (r'\bINFO\b', 'info'),
    (r'\b(?:WARN|WARNING)\b', 'warn'),
    (r'\b(?:ERROR|ERR|FATAL)\b', 'error'),
]


def parse_timestamp(line: str) -> Tuple[Optional[str], str]:
    """
    Parse timestamp from log line.

    Returns:
        Tuple of (timestamp_str, timestamp_format) or (None, 'unknown')
    """
    for pattern, fmt in TIMESTAMP_PATTERNS:
        match = re.search(pattern, line)
        if match:
            if fmt == 'glog':
                # glog format: LMMDD HH:MM:SS.microseconds
                # Extract date and time parts
                month_day = match.group(2)
                time_part = match.group(3)
                # Approximate year (use current year)
                year = datetime.now().year
                # Parse MMDD
                month = month_day[:2]
                day = month_day[2:]
                timestamp = f"{year}-{month}-{day} {time_part}"
                return timestamp, fmt
            else:
                return match.group(1), fmt

    return None, 'unknown'


def parse_level(line: str) -> str:
    """Parse log level from line. Returns 'info' if not detected."""
    for pattern, level in LEVEL_PATTERNS:
        if re.search(pattern, line, re.IGNORECASE):
            return level
    return 'info'


def build_search_pattern(spec: ResourceSpec) -> re.Pattern:
    """
    Build regex pattern for searching pod logs.

    Args:
        spec: ResourceSpec to build pattern for

    Returns:
        Compiled regex pattern (case-insensitive)
    """
    if spec.kind:
        # Pattern: {kind}i?e?s?/{name}
        # This matches: pod/etcd-0, pods/etcd-0
        kind_pattern = spec.kind + r'i?e?s?'
        pattern = rf'{kind_pattern}/{re.escape(spec.name)}'
    else:
        # Just search for name
        pattern = re.escape(spec.name)

    return re.compile(pattern, re.IGNORECASE)


def generate_summary(line: str, spec: ResourceSpec) -> str:
    """
    Generate a contextual summary from the log line.

    Args:
        line: Full log line
        spec: ResourceSpec that matched

    Returns:
        Summary string
    """
    # Remove common prefixes (timestamps, log levels)
    clean_line = line

    # Remove timestamps
    for pattern, _ in TIMESTAMP_PATTERNS:
        clean_line = re.sub(pattern, '', clean_line)

    # Remove log level markers
    clean_line = re.sub(r'^[IWEF]\s*', '', clean_line)
    clean_line = re.sub(r'\b(?:INFO|WARN|WARNING|ERROR|ERR|FATAL)\b:?\s*', '', clean_line, flags=re.IGNORECASE)

    # Trim and limit length
    clean_line = clean_line.strip()
    if len(clean_line) > 200:
        clean_line = clean_line[:197] + '...'

    return clean_line if clean_line else "Log entry mentioning resource"


def parse_pod_log_file(filepath: Path, resource_specs: List[ResourceSpec]) -> List[PodLogEntry]:
    """
    Parse a single pod log file and extract matching entries.

    Args:
        filepath: Path to pod log file
        resource_specs: List of resource specifications to match

    Returns:
        List of matching PodLogEntry objects
    """
    entries = []

    # Build search patterns for each resource spec
    patterns = [(spec, build_search_pattern(spec)) for spec in resource_specs]

    try:
        with open(filepath, 'r', errors='ignore') as f:
            for line_num, line in enumerate(f, start=1):
                line = line.rstrip('\n')
                if not line:
                    continue

                # Check if line matches any pattern
                for spec, pattern in patterns:
                    if pattern.search(line):
                        # Parse timestamp
                        timestamp, _ = parse_timestamp(line)

                        # Parse level
                        level = parse_level(line)

                        # Generate summary
                        summary = generate_summary(line, spec)

                        # Trim content if too long
                        content = line
                        if len(content) > 500:
                            content = content[:497] + '...'

                        entry = PodLogEntry(
                            filename=str(filepath),
                            line_number=line_num,
                            timestamp=timestamp,
                            level=level,
                            content=content,
                            summary=summary
                        )
                        entries.append(entry)
                        break  # Only match once per line

    except Exception as e:
        print(f"Warning: Error reading {filepath}: {e}", file=sys.stderr)

    return entries


def find_pod_log_files(base_path: Path) -> List[Path]:
    """Find all .log files in pods directory recursively."""
    log_files = []

    artifacts_path = base_path / "artifacts"
    if artifacts_path.exists():
        for target_dir in artifacts_path.iterdir():
            if target_dir.is_dir():
                pods_dir = target_dir / "gather-extra" / "artifacts" / "pods"
                if pods_dir.exists():
                    log_files.extend(pods_dir.rglob("*.log"))

    return sorted(log_files)


def main():
    """
    Parse pod logs from command line arguments.

    Usage: parse_pod_logs.py <base_path> <resource_spec1> [<resource_spec2> ...]

    Example: parse_pod_logs.py ./1978913325970362368/logs pod/etcd-0 configmap/cluster-config
    """
    if len(sys.argv) < 3:
        print("Usage: parse_pod_logs.py <base_path> <resource_spec1> [<resource_spec2> ...]", file=sys.stderr)
        print("Example: parse_pod_logs.py ./1978913325970362368/logs pod/etcd-0", file=sys.stderr)
        sys.exit(1)

    base_path = Path(sys.argv[1])
    resource_spec_strs = sys.argv[2:]

    # Parse resource specs
    resource_specs = [ResourceSpec.from_string(spec) for spec in resource_spec_strs]

    # Find pod log files
    log_files = find_pod_log_files(base_path)

    if not log_files:
        print(f"Warning: No pod log files found in {base_path}", file=sys.stderr)
        print(json.dumps([]))
        return 0

    print(f"Found {len(log_files)} pod log files", file=sys.stderr)

    # Parse all log files
    all_entries = []
    for log_file in log_files:
        entries = parse_pod_log_file(log_file, resource_specs)
        all_entries.extend(entries)

    print(f"Found {len(all_entries)} matching pod log entries", file=sys.stderr)

    # Output as JSON
    entries_json = [asdict(entry) for entry in all_entries]
    print(json.dumps(entries_json, indent=2))

    return 0


if __name__ == '__main__':
    sys.exit(main())
