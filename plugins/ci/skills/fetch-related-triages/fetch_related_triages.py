#!/usr/bin/env python3
"""
Fetch related triages for a Component Readiness regression.

Queries the Sippy API to find existing triage records that may be related to
a given regression, based on similarly named tests and shared last failure times.

Usage:
    python3 fetch_related_triages.py <regression_id> [--min-confidence N] [--format json|summary]

Examples:
    python3 fetch_related_triages.py 35479
    python3 fetch_related_triages.py 35479 --min-confidence 5
    python3 fetch_related_triages.py 35479 --format summary
"""

import argparse
import json
import sys
import urllib.request
import urllib.error

SIPPY_BASE_URL = "https://sippy.dptools.openshift.org"


def fetch_related_triages(regression_id: int) -> dict:
    """Fetch related triages for a regression from the Sippy API.

    Args:
        regression_id: The Component Readiness regression ID

    Returns:
        dict with success status and matches data
    """
    url = f"{SIPPY_BASE_URL}/api/component_readiness/regressions/{regression_id}/matches"

    req = urllib.request.Request(url, method="GET")
    req.add_header("Accept", "application/json")

    try:
        with urllib.request.urlopen(req, timeout=60) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8", errors="replace")
        return {
            "success": False,
            "error": f"HTTP {e.code}: {error_body}",
            "regression_id": regression_id,
        }
    except urllib.error.URLError as e:
        return {
            "success": False,
            "error": f"URL error: {e.reason}",
            "regression_id": regression_id,
        }

    if data is None:
        data = []

    return {
        "success": True,
        "regression_id": regression_id,
        "matches": data,
    }


def simplify_closed(closed) -> str:
    """Convert closed field to a simple string or None."""
    if closed is None:
        return None
    if isinstance(closed, dict):
        if closed.get("Valid", False):
            return closed.get("Time")
        return None
    return str(closed)


def simplify_last_failure(last_failure) -> str:
    """Convert last_failure field to a simple string or None."""
    if last_failure is None:
        return None
    if isinstance(last_failure, dict):
        if last_failure.get("Valid", False):
            return last_failure.get("Time")
        return None
    return str(last_failure)


def simplify_regression(reg: dict) -> dict:
    """Simplify a regression object for output."""
    reg_id = reg.get("id")
    return {
        "id": reg_id,
        "regression_id": reg_id,
        "test_name": reg.get("test_name"),
        "test_id": reg.get("test_id"),
        "component": reg.get("component"),
        "capability": reg.get("capability"),
        "variants": reg.get("variants"),
        "opened": reg.get("opened"),
        "closed": simplify_closed(reg.get("closed")),
        "triages": reg.get("triages"),
        "last_failure": simplify_last_failure(reg.get("last_failure")),
    }


def process_matches(raw_matches: list, min_confidence: int) -> dict:
    """Process raw API matches into a structured result.

    Args:
        raw_matches: Raw match list from the API
        min_confidence: Minimum confidence level to include

    Returns:
        dict with triaged_matches (existing triages) and untriaged_regressions
    """
    triaged_matches = []
    untriaged_regressions = []

    for match in raw_matches:
        confidence = match.get("confidence_level", 0)
        if confidence < min_confidence:
            continue

        triage = match.get("triage")
        if triage is None:
            continue

        triage_id = triage.get("id")
        bug = triage.get("bug", {}) or {}
        jira_key = bug.get("key", "")
        jira_url = bug.get("url") or triage.get("url", "")
        jira_status = bug.get("status", "")
        jira_summary = bug.get("summary", "")
        triage_type = triage.get("type", "")
        triage_description = triage.get("description", "")
        triage_ui_url = f"https://sippy-auth.dptools.openshift.org/sippy-ng/component_readiness/triages/{triage_id}"

        # Collect regressions already on this triage
        triage_regressions = []
        for reg in triage.get("regressions", []) or []:
            triage_regressions.append(simplify_regression(reg))

        # Collect similarly named test regressions that are untriaged
        similar_tests = match.get("similarly_named_tests") or []
        for entry in similar_tests:
            reg = entry.get("regression", {})
            if reg.get("triages") is None or len(reg.get("triages") or []) == 0:
                is_open = simplify_closed(reg.get("closed")) is None
                if is_open:
                    simplified = simplify_regression(reg)
                    simplified["match_reason"] = "similarly_named_test"
                    simplified["edit_distance"] = entry.get("edit_distance", -1)
                    untriaged_regressions.append(simplified)

        # Collect same_last_failure regressions that are untriaged
        same_failures = match.get("same_last_failures") or []
        for reg in same_failures:
            if reg.get("triages") is None or len(reg.get("triages") or []) == 0:
                is_open = simplify_closed(reg.get("closed")) is None
                if is_open:
                    simplified = simplify_regression(reg)
                    simplified["match_reason"] = "same_last_failure"
                    untriaged_regressions.append(simplified)

        triaged_matches.append({
            "triage_id": triage_id,
            "triage_ui_url": triage_ui_url,
            "jira_key": jira_key,
            "jira_url": jira_url,
            "jira_status": jira_status,
            "jira_summary": jira_summary,
            "triage_type": triage_type,
            "triage_description": triage_description,
            "confidence_level": confidence,
            "regressions_on_triage": triage_regressions,
        })

    # Deduplicate untriaged regressions by ID
    seen_ids = set()
    deduped = []
    for reg in untriaged_regressions:
        rid = reg.get("id")
        if rid not in seen_ids:
            seen_ids.add(rid)
            deduped.append(reg)
    untriaged_regressions = deduped

    # Sort triaged matches by confidence (highest first)
    triaged_matches.sort(key=lambda m: m["confidence_level"], reverse=True)

    return {
        "triaged_matches": triaged_matches,
        "untriaged_regressions": untriaged_regressions,
    }


def format_summary(regression_id: int, result: dict) -> str:
    """Format results as a human-readable summary."""
    lines = [f"Related Triages for Regression {regression_id}", "=" * 50]

    triaged = result["triaged_matches"]
    untriaged = result["untriaged_regressions"]

    if not triaged and not untriaged:
        lines.append("No related triages or untriaged regressions found.")
        return "\n".join(lines)

    if triaged:
        lines.append(f"\nExisting Triages ({len(triaged)}):")
        for m in triaged:
            lines.append(f"  Confidence {m['confidence_level']}/10: "
                         f"{m['jira_key']} ({m['jira_status']}) - {m['jira_summary']}")
            lines.append(f"    Triage ID: {m['triage_id']} | Type: {m['triage_type']}")
            lines.append(f"    Triage UI: {m['triage_ui_url']}")
            lines.append(f"    Regressions on triage: {len(m['regressions_on_triage'])}")

    if untriaged:
        lines.append(f"\nUntriaged Related Regressions ({len(untriaged)}):")
        for reg in untriaged:
            status = "open" if reg.get("closed") is None else "closed"
            lines.append(f"  Regression {reg['id']} ({status}): {reg['test_name']}")
            lines.append(f"    Match reason: {reg.get('match_reason', 'unknown')}")
            lines.append(f"    Component: {reg.get('component', 'Unknown')}")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Fetch related triages for a Component Readiness regression",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s 35479
  %(prog)s 35479 --min-confidence 5
  %(prog)s 35479 --format summary
""",
    )

    parser.add_argument(
        "regression_id",
        type=int,
        help="Regression ID to find related triages for",
    )
    parser.add_argument(
        "--min-confidence",
        type=int,
        default=1,
        help="Minimum confidence level to include (1-10, default: 1)",
    )
    parser.add_argument(
        "--format",
        choices=["json", "summary"],
        default="json",
        help="Output format (default: json)",
    )

    args = parser.parse_args()

    print(f"Fetching related triages for regression {args.regression_id}...",
          file=sys.stderr)

    raw = fetch_related_triages(args.regression_id)

    if not raw["success"]:
        if args.format == "json":
            print(json.dumps(raw, indent=2))
        else:
            print(f"Error: {raw['error']}")
        sys.exit(1)

    result = process_matches(raw["matches"], args.min_confidence)

    output = {
        "success": True,
        "regression_id": args.regression_id,
        "triaged_matches": result["triaged_matches"],
        "untriaged_regressions": result["untriaged_regressions"],
    }

    if args.format == "json":
        print(json.dumps(output, indent=2))
    else:
        print(format_summary(args.regression_id, result))


if __name__ == "__main__":
    main()
