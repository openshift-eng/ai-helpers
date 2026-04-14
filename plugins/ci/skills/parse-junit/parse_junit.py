#!/usr/bin/env python3
"""Parse JUnit XML files from OpenShift CI jobs.

Extracts test results, failure messages, and metadata from JUnit XML files
produced by CI test steps. Supports standard JUnit, aggregated JUnit
(with system-out YAML containing per-run results), gzip-compressed files,
and stdin input.
"""

import argparse
import gzip
import io
import json
import re
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path


# ---------------------------------------------------------------------------
# Lifecycle detection
# ---------------------------------------------------------------------------

# Patterns in the file path or suite name that indicate informing tests.
# Informing tests do NOT cause job failures on their own, but badly-behaved
# informing tests can still impact the cluster and are worth investigating.
_INFORMING_RE = re.compile(r"informing", re.IGNORECASE)


def _detect_lifecycle(filename: str, suite_name: str) -> str:
    """Return 'informing' or 'blocking' based on filename/suite heuristics."""
    if _INFORMING_RE.search(filename or "") or _INFORMING_RE.search(suite_name or ""):
        return "informing"
    return "blocking"


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class TestResult:
    name: str
    status: str  # passed, failed, error, skipped
    suite_name: str = ""
    classname: str = ""
    time_seconds: float = 0.0
    failure_message: str = ""
    failure_text: str = ""
    error_message: str = ""
    error_text: str = ""
    skipped_message: str = ""
    system_out: str = ""
    lifecycle: str = "blocking"
    source_file: str = ""
    # Aggregated JUnit fields (parsed from system-out YAML)
    agg_passes: list = field(default_factory=list)
    agg_failures: list = field(default_factory=list)
    agg_skips: list = field(default_factory=list)


# ---------------------------------------------------------------------------
# Aggregated system-out YAML parser
# ---------------------------------------------------------------------------

def _parse_system_out_yaml(text: str) -> dict:
    """Parse the YAML-like system-out from aggregated JUnit XML.

    Aggregated JUnit files (from release-analysis-aggregator) embed per-run
    results in ``<system-out>`` as simple YAML with sections ``passes:``,
    ``failures:``, and ``skips:``.  Each entry contains ``jobRunID``,
    ``humanURL``, and ``gcsArtifactURL``.

    Returns dict with keys 'passes', 'failures', 'skips', each a list of
    dicts.
    """
    result = {"passes": [], "failures": [], "skips": []}
    if not text:
        return result

    current_section = None
    current_entry = {}

    for line in text.strip().splitlines():
        stripped = line.strip()

        # Section headers
        if stripped in ("passes:", "failures:", "skips:"):
            if current_entry and current_section:
                result[current_section].append(current_entry)
                current_entry = {}
            current_section = stripped.rstrip(":")
            continue

        if current_section is None:
            continue

        # New list item (``- key: value``)
        if stripped.startswith("- "):
            if current_entry:
                result[current_section].append(current_entry)
            current_entry = {}
            kv = stripped[2:]
            if ":" in kv:
                key, val = kv.split(":", 1)
                current_entry[key.strip()] = val.strip().strip('"')
        elif ":" in stripped:
            # Continuation key
            key, val = stripped.split(":", 1)
            current_entry[key.strip()] = val.strip().strip('"')

    if current_entry and current_section:
        result[current_section].append(current_entry)

    return result


# ---------------------------------------------------------------------------
# JUnit XML parsing
# ---------------------------------------------------------------------------

def parse_junit_xml(source, source_name: str = "<stdin>") -> list:
    """Parse a JUnit XML file or stream, returning a list of TestResult."""
    try:
        tree = ET.parse(source)
    except ET.ParseError as e:
        print(f"Error: Failed to parse XML from {source_name}: {e}", file=sys.stderr)
        return []

    root = tree.getroot()

    # Handle <testsuites>, <testsuite>, or other root elements
    if root.tag == "testsuites":
        suites = root.findall("testsuite")
    elif root.tag == "testsuite":
        suites = [root]
    else:
        suites = root.findall(".//testsuite")
        if not suites:
            # Treat root as a single implicit suite
            suites = [root]

    results = []

    for suite in suites:
        suite_name = suite.get("name", "")
        lifecycle = _detect_lifecycle(source_name, suite_name)

        for tc in suite.findall("testcase"):
            name = tc.get("name", "")
            classname = tc.get("classname", "")
            try:
                time_s = float(tc.get("time", "0"))
            except (ValueError, TypeError):
                time_s = 0.0

            # Determine status --------------------------------------------------
            failure_el = tc.find("failure")
            error_el = tc.find("error")
            skipped_el = tc.find("skipped")

            status = "passed"
            failure_message = failure_text = ""
            error_message = error_text = ""
            skipped_message = ""

            if failure_el is not None:
                status = "failed"
                failure_message = failure_el.get("message", "")
                failure_text = failure_el.text or ""
            if error_el is not None:
                status = "error"
                error_message = error_el.get("message", "")
                error_text = error_el.text or ""
            if skipped_el is not None:
                status = "skipped"
                skipped_message = skipped_el.get("message", "")

            # System-out --------------------------------------------------------
            sysout_el = tc.find("system-out")
            system_out = (sysout_el.text or "") if sysout_el is not None else ""

            # Parse aggregated YAML from system-out
            agg_passes = []
            agg_failures = []
            agg_skips = []
            if system_out and any(
                k in system_out for k in ("passes:", "failures:", "skips:")
            ):
                parsed = _parse_system_out_yaml(system_out)
                agg_passes = parsed["passes"]
                agg_failures = parsed["failures"]
                agg_skips = parsed["skips"]

            results.append(
                TestResult(
                    name=name,
                    status=status,
                    suite_name=suite_name,
                    classname=classname,
                    time_seconds=time_s,
                    failure_message=failure_message,
                    failure_text=failure_text,
                    error_message=error_message,
                    error_text=error_text,
                    skipped_message=skipped_message,
                    system_out=system_out,
                    lifecycle=lifecycle,
                    source_file=source_name,
                    agg_passes=agg_passes,
                    agg_failures=agg_failures,
                    agg_skips=agg_skips,
                )
            )

    return results


def parse_file(filepath: str) -> list:
    """Parse a JUnit XML file, handling gzip transparently."""
    p = Path(filepath)
    if not p.exists():
        print(f"Error: File not found: {filepath}", file=sys.stderr)
        return []

    if p.suffix == ".gz" or filepath.endswith(".xml.gz"):
        with gzip.open(filepath, "rt", encoding="utf-8", errors="replace") as f:
            return parse_junit_xml(f, source_name=filepath)

    return parse_junit_xml(filepath, source_name=filepath)


# ---------------------------------------------------------------------------
# Filtering
# ---------------------------------------------------------------------------

def filter_results(results, name_pattern=None, status_filter=None,
                   lifecycle_filter=None):
    """Filter results by name regex, status, and/or lifecycle."""
    filtered = results
    if name_pattern:
        regex = re.compile(name_pattern, re.IGNORECASE)
        filtered = [r for r in filtered if regex.search(r.name)]
    if status_filter:
        statuses = {s.strip() for s in status_filter.split(",")}
        filtered = [r for r in filtered if r.status in statuses]
    if lifecycle_filter:
        filtered = [r for r in filtered if r.lifecycle == lifecycle_filter]
    return filtered


# ---------------------------------------------------------------------------
# Output formatters
# ---------------------------------------------------------------------------

def _format_summary(results, show_output=False):
    """Human-readable overview of all test results."""
    if not results:
        return "No test results found."

    lines = []
    counts = Counter(r.status for r in results)
    total = len(results)

    lines.append("Test Results Summary")
    lines.append("=" * 60)
    lines.append(f"  Total:   {total}")
    lines.append(f"  Passed:  {counts.get('passed', 0)}")
    lines.append(f"  Failed:  {counts.get('failed', 0)}")
    lines.append(f"  Errors:  {counts.get('error', 0)}")
    lines.append(f"  Skipped: {counts.get('skipped', 0)}")
    lines.append("")

    # Lifecycle breakdown
    informing = [r for r in results if r.lifecycle == "informing"]
    if informing:
        inf_failed = sum(
            1 for r in informing if r.status in ("failed", "error")
        )
        lines.append(f"  Informing tests: {len(informing)} ({inf_failed} failed)")
        lines.append(
            "  Note: Informing test failures do not cause job failures on their own."
        )
        lines.append("")

    # Test sources (suites / binaries)
    suites = sorted({r.suite_name for r in results if r.suite_name})
    if suites:
        lines.append("Test Sources (suites / binaries):")
        for s in suites:
            cnt = sum(1 for r in results if r.suite_name == s)
            lines.append(f"  - {s} ({cnt} tests)")
        lines.append("")

    # Source files
    files = sorted({r.source_file for r in results if r.source_file})
    if len(files) > 1:
        lines.append("Source Files:")
        for f in files:
            cnt = sum(1 for r in results if r.source_file == f)
            lines.append(f"  - {f} ({cnt} tests)")
        lines.append("")

    # Failed tests grouped by lifecycle
    failed = [r for r in results if r.status in ("failed", "error")]
    if failed:
        blocking_f = [r for r in failed if r.lifecycle == "blocking"]
        informing_f = [r for r in failed if r.lifecycle == "informing"]

        if blocking_f:
            lines.append(f"Failed Tests - blocking ({len(blocking_f)}):")
            lines.append("-" * 60)
            for r in blocking_f:
                _append_failure(lines, r, show_output)

        if informing_f:
            lines.append(f"Failed Tests - informing ({len(informing_f)}):")
            lines.append(
                "  (These do not cause job failures on their own, but badly"
            )
            lines.append(
                "   behaved informing tests could impact the cluster.)"
            )
            lines.append("-" * 60)
            for r in informing_f:
                _append_failure(lines, r, show_output)

    return "\n".join(lines)


def _append_failure(lines, r, show_output):
    """Append a single failure entry to ``lines``."""
    lines.append(f"  {r.name}")
    if r.suite_name:
        lines.append(f"    Source: {r.suite_name}")
    if r.classname and r.classname != r.suite_name:
        lines.append(f"    Class:  {r.classname}")
    msg = r.failure_message or r.error_message
    if msg:
        lines.append(f"    Message: {msg[:300]}")
    if show_output:
        text = r.failure_text or r.error_text
        if text:
            lines.append("    Output:")
            for line in text.strip().splitlines()[:30]:
                lines.append(f"      {line}")
    if r.agg_passes or r.agg_failures or r.agg_skips:
        lines.append(
            f"    Aggregated: {len(r.agg_passes)} passes, "
            f"{len(r.agg_failures)} failures, {len(r.agg_skips)} skips"
        )
    lines.append("")


def _format_failures(results, show_output=False):
    """Show only failed/error tests with full details."""
    failed = [r for r in results if r.status in ("failed", "error")]
    if not failed:
        return "No test failures found."

    lines = []
    lines.append(f"Test Failures ({len(failed)})")
    lines.append("=" * 60)

    for r in failed:
        tag = " [INFORMING]" if r.lifecycle == "informing" else ""
        lines.append(f"\n{r.name}{tag}")
        if r.suite_name:
            lines.append(f"  Source: {r.suite_name}")
        if r.classname and r.classname != r.suite_name:
            lines.append(f"  Class:  {r.classname}")
        lines.append(f"  Status: {r.status}")
        lines.append(f"  Lifecycle: {r.lifecycle}")
        if r.failure_message:
            lines.append(f"  Message: {r.failure_message}")
        if r.error_message:
            lines.append(f"  Error: {r.error_message}")
        if show_output:
            text = r.failure_text or r.error_text
            if text:
                lines.append("  Output:")
                for line in text.strip().splitlines()[:30]:
                    lines.append(f"    {line}")
        if r.agg_passes or r.agg_failures or r.agg_skips:
            lines.append("  Aggregated runs:")
            lines.append(f"    Passes: {len(r.agg_passes)}")
            lines.append(f"    Failures: {len(r.agg_failures)}")
            lines.append(f"    Skips: {len(r.agg_skips)}")
            for entry in r.agg_failures:
                url = entry.get("humanURL") or entry.get("humanUrl") or ""
                run_id = entry.get("jobRunID") or entry.get("jobrunid") or ""
                if url:
                    lines.append(f"      - Run {run_id}: {url}")
        lines.append("")

    informing_count = sum(1 for r in failed if r.lifecycle == "informing")
    if informing_count:
        lines.append(
            f"Note: {informing_count} of {len(failed)} failure(s) are from "
            f"informing tests."
        )
        lines.append(
            "Informing test failures do not cause job failures on their own,"
        )
        lines.append("but badly behaved informing tests could impact the cluster.")

    return "\n".join(lines)


def _to_json(results):
    """Convert results to a JSON-serializable list of dicts."""
    output = []
    for r in results:
        d = {
            "name": r.name,
            "status": r.status,
            "suite_name": r.suite_name,
            "classname": r.classname,
            "time_seconds": r.time_seconds,
            "lifecycle": r.lifecycle,
            "source_file": r.source_file,
        }
        if r.failure_message:
            d["failure_message"] = r.failure_message
        if r.failure_text:
            d["failure_text"] = r.failure_text
        if r.error_message:
            d["error_message"] = r.error_message
        if r.error_text:
            d["error_text"] = r.error_text
        if r.skipped_message:
            d["skipped_message"] = r.skipped_message
        if r.system_out:
            d["system_out"] = r.system_out
        if r.agg_passes or r.agg_failures or r.agg_skips:
            d["aggregated"] = {
                "passes": r.agg_passes,
                "failures": r.agg_failures,
                "skips": r.agg_skips,
            }
        output.append(d)
    return output


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Parse JUnit XML files from OpenShift CI jobs.",
        epilog=(
            "Examples:\n"
            "  python3 parse_junit.py junit.xml\n"
            "  python3 parse_junit.py junit.xml.gz --format failures --show-output\n"
            "  python3 parse_junit.py *.xml --filter 'sig-network' --status failed\n"
            "  cat junit.xml | python3 parse_junit.py --stdin --format summary\n"
            "  gcloud storage cat gs://bucket/junit.xml | python3 parse_junit.py --stdin\n"
            "  python3 parse_junit.py junit*.xml --lifecycle informing --format failures\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "files",
        nargs="*",
        help="JUnit XML file(s) to parse (supports .xml and .xml.gz)",
    )
    parser.add_argument(
        "--stdin",
        action="store_true",
        help="Read JUnit XML from stdin (supports gzip-compressed input)",
    )
    parser.add_argument(
        "--format",
        choices=["json", "summary", "failures", "names"],
        default="json",
        help=(
            "Output format (default: json). "
            "summary: human-readable overview with counts and failure details. "
            "failures: only failed/error tests with full details. "
            "names: just test names, one per line."
        ),
    )
    parser.add_argument(
        "--filter",
        default=None,
        help="Filter tests by name pattern (regex, case-insensitive)",
    )
    parser.add_argument(
        "--status",
        default=None,
        help=(
            "Filter by status (comma-separated): "
            "passed, failed, error, skipped"
        ),
    )
    parser.add_argument(
        "--show-output",
        action="store_true",
        help="Include failure output text in summary/failures format",
    )
    parser.add_argument(
        "--lifecycle",
        choices=["informing", "blocking"],
        default=None,
        help=(
            "Filter by lifecycle. 'informing' tests do not cause job failures "
            "on their own. Lifecycle is auto-detected from filename/suite name "
            "when not specified as a filter."
        ),
    )

    args = parser.parse_args()

    if not args.files and not args.stdin:
        parser.error("Provide file paths or use --stdin")

    all_results = []

    # Read from stdin
    if args.stdin:
        data = sys.stdin.buffer.read()
        # Transparently decompress gzip
        if data[:2] == b"\x1f\x8b":
            data = gzip.decompress(data)
        text = data.decode("utf-8", errors="replace")
        all_results.extend(parse_junit_xml(io.StringIO(text), source_name="<stdin>"))

    # Read from file arguments
    for filepath in args.files or []:
        all_results.extend(parse_file(filepath))

    # Apply filters
    all_results = filter_results(
        all_results,
        name_pattern=args.filter,
        status_filter=args.status,
        lifecycle_filter=args.lifecycle,
    )

    # Output
    if args.format == "json":
        print(json.dumps(_to_json(all_results), indent=2))
    elif args.format == "summary":
        print(_format_summary(all_results, show_output=args.show_output))
    elif args.format == "failures":
        print(_format_failures(all_results, show_output=args.show_output))
    elif args.format == "names":
        for r in all_results:
            print(r.name)


if __name__ == "__main__":
    main()
