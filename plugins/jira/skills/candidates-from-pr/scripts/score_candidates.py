#!/usr/bin/env python3
"""Score candidate Jiras against PR signals.

Reads two files and produces a ranked candidates JSON for rendering. All
scoring is local string matching; no API calls.

Usage:
    score_candidates.py \
        --signals signals.json \
        --candidates candidates.json \
        --components-derived "Networking / ovn-kubernetes,..." \
        [--min-score 40] [--limit 10]

Inputs:
    signals.json     — output of extract_signals.py
    candidates.json  — JSON list, each element with keys:
                         key, summary, status, issuetype, priority, assignee,
                         components, fix_versions, target_release, description,
                         updated, url
                       (skill caller fills this from mcp__atlassian__jira_search)

Output (stdout):
    [
      {
        "key": "...", "summary": "...", "url": "...",
        "status": "...", "issuetype": "...", "priority": "...",
        "assignee": "...", "components": [...],
        "target_release": "...", "fix_versions": [...],
        "score": 82, "verdict": "likely",
        "matched_signals": [{"type": "...", "value": "..."}],
      },
      ...
    ]

The skill caller is responsible for turning matched_signals into a 1-2
sentence rationale.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone

DROPLIKE_TYPES = {"Epic", "Feature", "Initiative"}
DROP_STATUSES = {"Verified", "Closed"}


def load(path: str) -> object:
    with open(path) as f:
        return json.load(f)


def find_in_text(needles: list[str], text: str) -> list[str]:
    """Return needles that appear verbatim in text. Case-sensitive for
    symbols and error strings (they tend to be exact tokens)."""
    if not needles or not text:
        return []
    return [n for n in needles if n and n in text]


def find_lower(needles: list[str], text_lower: str) -> list[str]:
    if not needles or not text_lower:
        return []
    return [n for n in needles if n and n.lower() in text_lower]


def score_one(
    cand: dict,
    signals: dict,
    derived_components: set[str],
    component_filter_used: bool,
) -> tuple[int, list[dict]]:
    matched: list[dict] = []

    summary = cand.get("summary") or ""
    description = cand.get("description") or ""
    haystack = summary + "\n" + description
    haystack_lower = haystack.lower()

    err_values = [s["value"] for s in signals.get("error_strings", [])]
    sym_values = [s["value"] for s in signals.get("symbols", [])]
    title_values = [s["value"] for s in signals.get("title_keywords", [])]
    path_values = [s["value"] for s in signals.get("path_tags", [])]
    commit_values = [s["value"] for s in signals.get("commit_keywords", [])]

    score = 0

    # Error strings: +35 for any match.
    err_hits = find_in_text(err_values, haystack)
    if err_hits:
        score += 35
        for v in err_hits[:3]:
            matched.append({"type": "error_string", "value": v})

    # Symbols: +25 per unique match, capped at +40.
    sym_hits = find_in_text(sym_values, haystack)
    if sym_hits:
        score += min(40, 25 * len(sym_hits))
        for v in sym_hits[:5]:
            matched.append({"type": "symbol", "value": v})

    # Title keyword overlap: +15 if 2+ unique 4+ char tokens match.
    title_hits = find_lower(title_values, haystack_lower)
    if len(title_hits) >= 2:
        score += 15
        for v in title_hits[:3]:
            matched.append({"type": "title_keyword", "value": v})

    # Component agreement: +10. Required for non-zero unless filter skipped.
    cand_components = {c for c in cand.get("components") or []}
    if cand_components & derived_components:
        score += 10
        matched.append(
            {
                "type": "component_match",
                "value": next(iter(cand_components & derived_components)),
            }
        )
    elif component_filter_used:
        # JQL should have prevented this; guard anyway.
        score = 0
        return score, matched

    # Recency: updated within last 90 days.
    updated_raw = cand.get("updated")
    if updated_raw:
        try:
            updated = datetime.fromisoformat(updated_raw.replace("Z", "+00:00"))
            if datetime.now(timezone.utc) - updated < timedelta(days=90):
                score += 5
                matched.append({"type": "recency", "value": "updated<=90d"})
        except (ValueError, AttributeError):
            pass

    # Path-tag overlap: +5 capped at +10.
    path_hits = find_lower(path_values, haystack_lower)
    if path_hits:
        score += min(10, 5 * len(path_hits))
        for v in path_hits[:3]:
            matched.append({"type": "path_tag", "value": v})

    # Commit-keyword overlap: +5 if 3+ unique commit headline tokens match.
    # Useful for downstream-merge / large PRs where the diff is unavailable.
    commit_hits = find_lower(commit_values, haystack_lower)
    if len(commit_hits) >= 3:
        score += 5
        for v in commit_hits[:3]:
            matched.append({"type": "commit_keyword", "value": v})

    # Penalties.
    if cand.get("issuetype") in DROPLIKE_TYPES:
        score -= 15
    if cand.get("status") in DROP_STATUSES:
        return -1, matched  # caller drops
    if not derived_components and not (err_hits or sym_hits):
        score -= 20

    return max(0, min(100, score)), matched


def verdict_for(score: int, min_score: int) -> str | None:
    if score >= 75:
        return "likely"
    if score >= 50:
        return "possible"
    if score >= min_score:
        return "unlikely"
    return None


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--signals", required=True)
    p.add_argument("--candidates", required=True)
    p.add_argument(
        "--components-derived",
        default="",
        help="Comma-separated derived components (used for component-agreement scoring)",
    )
    p.add_argument(
        "--component-filter-used",
        action="store_true",
        help="Pass when the JQL included a component clause",
    )
    p.add_argument("--min-score", type=int, default=40)
    p.add_argument("--limit", type=int, default=10)
    args = p.parse_args()

    signals = load(args.signals)
    cands = load(args.candidates)
    derived = {c.strip() for c in args.components_derived.split(",") if c.strip()}

    scored: list[dict] = []
    for cand in cands:
        score, matched = score_one(cand, signals, derived, args.component_filter_used)
        if score < 0:
            continue
        v = verdict_for(score, args.min_score)
        if v is None:
            continue
        scored.append(
            {
                "key": cand.get("key"),
                "summary": cand.get("summary"),
                "url": cand.get("url"),
                "status": cand.get("status"),
                "issuetype": cand.get("issuetype"),
                "priority": cand.get("priority"),
                "assignee": cand.get("assignee"),
                "components": cand.get("components") or [],
                "target_release": cand.get("target_release"),
                "fix_versions": cand.get("fix_versions") or [],
                "score": score,
                "verdict": v,
                "matched_signals": matched,
            }
        )

    scored.sort(key=lambda x: x["score"], reverse=True)
    json.dump(scored[: args.limit], sys.stdout)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
