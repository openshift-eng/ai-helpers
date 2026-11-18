#!/usr/bin/env python3
"""
Deterministic checks for jira:pre-refinement.

Reads one card as JSON on stdin and prints facts the skill's judgment builds
on: whether the card is eligible, whether the stricter review for
assistant-drafted cards applies, length against the project's guidance, and
the mechanical rubric flags (completion lists over five items, long log
excerpts, long raw URLs). With a "proposed" object it also compares the
proposal with the original and lists anything the preservation rules require
that the proposal dropped, and the proposal's own rubric flags.

The values mirror plugins/jira/reference/<project>.md (only TRT has a
pre-refinement rubric today). Keep them in sync when that file changes.

Input:
    {
      "key": "TRT-123",
      "issue_type": "Story",
      "status": "New",
      "summary": "...",
      "description": "...",
      "labels": ["..."],
      "creator": "ship-help-jira",        # string, or {"name"/"emailAddress"/...}
      "proposed": {"summary": "...", "description": "..."}   # optional
    }

Usage:
    jq -n --arg d "$DESC" '{...}' | python3 check_card.py [--label ai-pre-refined]
        [--supported-types Story,Bug,Spike,Task,Ticket] [--project TRT]

Exit codes:
    0 - Checks completed (see JSON output)
    1 - Bad input
"""

import argparse
import json
import re
import sys
from typing import Dict, List, Optional, Tuple

DEFAULT_LABEL = "ai-pre-refined"
ASSISTANT_LABEL = "ai-generated-jira"
ASSISTANT_ACCOUNT = "ship-help-jira"
AI_NOTICE_RE = re.compile(r"AI-generated\.\s*Review for accuracy\.?", re.IGNORECASE)
ATTRIBUTION_RE = re.compile(r"^.*\bRequested by\b.*\bvia Chai Bot\b.*$", re.MULTILINE | re.IGNORECASE)

PROJECTS = {
    "TRT": {
        "eligible_status": "New",
        "supported_types": ["Story", "Bug", "Spike", "Task", "Ticket"],
        "summary_words": (5, 12),
        # Description length guidance in words (trt.md, "Length guidance").
        "guidance": {
            "Story": (120, 350),
            "Bug": (150, 450),
            "Task": (100, 350),
            "Ticket": (100, 350),
            "Spike": (80, 250),
        },
        # Recommended headings that count for each section, and whether the
        # section is required (True, False, or the condition that requires it).
        # A card can also satisfy a section with prose and no heading, so a
        # missing heading is a hint for the reviewer, not a verdict.
        "sections": {
            "Story": {
                "Statement": (True, ["User story", "Problem", "Summary", "Goal"]),
                "Acceptance Criteria": (True, ["Acceptance criteria", "Done when", "Success criteria",
                                               "Validation and acceptance criteria"]),
                "Additional Context": (False, ["Context", "Background", "Additional context", "References",
                                               "Related", "Out of scope"]),
            },
            "Bug": {
                "Problem": (True, ["Summary", "Description of problem", "Problem"]),
                "Reproduction or evidence": (True, ["Steps to reproduce", "How reproducible", "Evidence",
                                                    "Example", "Affected jobs", "Affected tests"]),
                "Expected vs actual": (True, ["Expected results", "Actual results", "Expected behavior",
                                              "Expected vs actual"]),
                "Impact": (True, ["Impact", "Why it matters"]),
            },
            "Spike": {
                "Question": (True, ["Research question", "Question", "Goal"]),
                "Context": (True, ["Context", "Background", "Current state"]),
                "Exit criteria": (True, ["Success criteria", "Definition of done", "Deliverable",
                                         "Findings documentation", "Follow-up actions", "Exit criteria"]),
            },
            "Task": {
                "Goal": (True, ["Goal", "Purpose", "Problem", "Summary", "Why", "Ask", "Origin"]),
                "Scope": ("multi-step work", ["Scope", "Action required", "Implementation plan",
                                  "Current behavior and scope", "Suggested remediation"]),
                "Done when": (True, ["Acceptance criteria", "Done when"]),
            },
        },
        # Headings whose lists are completion conditions (rubric check C2).
        "completion_headings": ["Acceptance criteria", "Done when", "Success criteria",
                                "Validation and acceptance criteria", "Definition of done",
                                "Exit criteria", "Additional acceptance criteria", "Deliverable",
                                "Findings documentation", "Follow-up actions"],
        "max_completion_items": 5,
        "max_log_lines": 5,
        "max_raw_url_chars": 100,
    },
}
PROJECTS["TRT"]["sections"]["Ticket"] = PROJECTS["TRT"]["sections"]["Task"]

HEADING_RE = re.compile(
    r"^\s*(?:h[1-6]\.\s+(?P<wiki>.+?)|#{1,6}\s+(?P<md>.+?)|\*\*(?P<bold>[^*]+?)\*\*:?|(?P<colon>[A-Z][^:\n]{1,60}):)\s*$",
    re.MULTILINE,
)
FENCE_RE = re.compile(r"```[^\n]*\n(.*?)```|\{(?:code|noformat)[^}]*\}(.*?)\{(?:code|noformat)\}", re.DOTALL)
# A Markdown link destination may contain one level of balanced parentheses.
MD_LINK_RE = re.compile(r"\[[^\]\n]*\]\((https?://(?:[^()\s]|\([^()\s]*\))+)\)")
WIKI_LINK_RE = re.compile(r"\[[^\]|\n]*\|(https?://[^\]\s]+)\]")
URL_RE = re.compile(r"https?://[^\s<>()\[\]|]+")
ISSUE_KEY_RE = re.compile(r"\b[A-Z][A-Z0-9]+-\d+\b")
CODE_SPAN_RE = re.compile(r"`([^`\n]+)`")
# A number may carry a hyphenated unit ("24-hour"), but not continue into a
# range, date or identifier ("3-5", "2026-10-02").
NUMBER_RE = re.compile(r"(?<![\w.-])\d+(?:\.\d+)*%?(?!\w|-\d)")
TOP_ITEM_RE = re.compile(r"^(?:[*\-+]|\d+[.)]|#)\s+")
NESTED_ITEM_RE = re.compile(r"^(?:\s{2,}(?:[*\-+]|\d+[.)])|\*\*+|##+)\s+")


def creator_ids(creator) -> List[str]:
    """Normalized identifiers of the card's creator: account name, key, email local part."""
    values = ([creator.get(k) for k in ("name", "key", "emailAddress")] if isinstance(creator, dict)
              else [creator])
    return [str(v).strip().lower().split("@")[0] for v in values if isinstance(v, str) and v.strip()]


def mask_fences(text: str) -> str:
    """Blank fenced code and log blocks, keeping offsets, so their lines are
    never read as headings or list items."""
    return FENCE_RE.sub(lambda m: re.sub(r"[^\n]", " ", m.group(0)), text)


def normalize(name: str) -> str:
    """Lower-case a heading and drop emphasis and a trailing "(...)" note."""
    name = re.sub(r"\s*\([^)]*\)\s*$", "", name.strip().strip("*").strip())
    return re.sub(r"\s+", " ", name).lower()


def headings(text: str) -> List[Tuple[str, int, int]]:
    """Return (normalized heading, start, end-of-line) for each heading line."""
    # In Jira wiki markup ("h2. Heading"), lines starting with "#" are ordered
    # list items, not Markdown headings.
    text = mask_fences(text)
    wiki = re.search(r"^\s*h[1-6]\.\s", text, re.MULTILINE) is not None
    found = []
    for m in HEADING_RE.finditer(text):
        if wiki and m.group("md"):
            continue
        name = next(g for g in (m.group("wiki"), m.group("md"), m.group("bold"), m.group("colon")) if g)
        found.append((normalize(name), m.start(), m.end()))
    return found


def section_bodies(text: str, names: List[str]) -> List[Tuple[str, str]]:
    wanted = {normalize(n) for n in names}
    text = mask_fences(text)
    marks = headings(text)
    bodies = []
    for i, (name, _, end) in enumerate(marks):
        if name in wanted:
            stop = marks[i + 1][1] if i + 1 < len(marks) else len(text)
            bodies.append((name, text[end:stop]))
    return bodies


def strip_boilerplate(text: str) -> str:
    text = AI_NOTICE_RE.sub("", text)
    return ATTRIBUTION_RE.sub("", text)


def word_count(text: str) -> int:
    text = URL_RE.sub("URL", strip_boilerplate(text or ""))
    return len(re.findall(r"[A-Za-z0-9][\w'’./:-]*", text))


def links(text: str) -> List[str]:
    found = MD_LINK_RE.findall(text) + WIKI_LINK_RE.findall(text) + URL_RE.findall(text)
    return sorted({u.rstrip(".,;:") for u in found})


def raw_urls(text: str) -> List[str]:
    masked = WIKI_LINK_RE.sub("", MD_LINK_RE.sub("", text))
    masked = re.sub(r"<(https?://[^>]+)>", "", masked)
    return [u.rstrip(".,;:") for u in URL_RE.findall(masked)]


def numbers(text: str) -> List[str]:
    masked = ISSUE_KEY_RE.sub("", URL_RE.sub("", text))
    masked = re.sub(r"^\s*\d+[.)]\s", "", masked, flags=re.MULTILINE)  # list ordinals
    return sorted(set(NUMBER_RE.findall(masked)))


def completion_lists(text: str, conf: dict) -> List[dict]:
    lists = []
    for name, body in section_bodies(text, conf["completion_headings"]):
        top = nested = 0
        for line in body.splitlines():
            if NESTED_ITEM_RE.match(line):
                nested += 1
            elif TOP_ITEM_RE.match(line):
                top += 1
        lists.append({
            "heading": name,
            "items": top,
            "nested_items": nested,
            "over_limit": top > conf["max_completion_items"],
        })
    return lists


def log_excerpts(text: str, conf: dict) -> List[int]:
    sizes = []
    for m in FENCE_RE.finditer(text):
        body = m.group(1) if m.group(1) is not None else m.group(2)
        lines = [ln for ln in body.splitlines() if ln.strip()]
        if len(lines) > conf["max_log_lines"]:
            sizes.append(len(lines))
    return sizes


def length_position(words: int, guidance: Tuple[int, int]) -> str:
    low, high = guidance
    if words < low:
        return "below"
    if words <= high:
        return "within"
    if words <= 2 * high:
        return "above"
    return "over_twice"


def stricter_review(labels: List[str], creator) -> dict:
    reasons = []
    if ASSISTANT_LABEL in labels:
        reasons.append("label")
    if ASSISTANT_ACCOUNT in creator_ids(creator):
        reasons.append("creator")
    return {"applied": bool(reasons), "reasons": reasons}


def eligibility(card: dict, conf: dict, label: str, supported: List[str]) -> Tuple[bool, Optional[str], bool]:
    issue_type = card.get("issue_type") or ""
    is_supported = issue_type.lower() in {t.lower() for t in supported}
    if label in (card.get("labels") or []):
        return False, f"already labelled {label}", is_supported
    status = card.get("status")
    if not status:
        return False, f"status unknown; cannot confirm it is {conf['eligible_status']}", is_supported
    if status.lower() != conf["eligible_status"].lower():
        return False, f"status is {status}, not {conf['eligible_status']}", is_supported
    if not is_supported:
        return False, f"unsupported type: {issue_type or 'unknown'}", is_supported
    return True, None, is_supported


def describe(card: dict, conf: dict, issue_type: str, strict: bool) -> dict:
    description = card.get("description") or ""
    summary = card.get("summary") or ""
    words = word_count(description)
    guidance = conf["guidance"].get(issue_type)
    result = {
        "summary": {
            "words": word_count(summary),
            "in_range": conf["summary_words"][0] <= word_count(summary) <= conf["summary_words"][1],
        },
        "description": {"words": words, "empty": not description.strip()},
        "sections": {},
        "completion_lists": completion_lists(description, conf),
        "long_log_excerpts": log_excerpts(description, conf),
        "long_raw_urls": [u for u in raw_urls(description) if len(u) > conf["max_raw_url_chars"]],
        "attribution_line": (ATTRIBUTION_RE.search(description).group(0).strip()
                             if ATTRIBUTION_RE.search(description) else None),
        "ai_notice_present": bool(AI_NOTICE_RE.search(description)),
    }
    if guidance:
        result["description"]["guidance"] = list(guidance)
        result["description"]["position"] = length_position(words, guidance)
        if strict:
            low, high = guidance
            result["description"]["target"] = [low, (low + high) // 2]
    present = {name for name, _, _ in headings(description)}
    for section, (required, synonyms) in conf["sections"].get(issue_type, {}).items():
        names = {normalize(section)} | {normalize(s) for s in synonyms}
        entry = {"required": required is True, "heading_found": bool(names & present)}
        if isinstance(required, str):
            entry["required_when"] = required
        result["sections"][section] = entry

    flags = []
    for lst in result["completion_lists"]:
        if lst["over_limit"]:
            flags.append(f"C2: '{lst['heading']}' has {lst['items']} items (limit {conf['max_completion_items']})")
        if lst["nested_items"]:
            flags.append(f"C2/C7: '{lst['heading']}' has {lst['nested_items']} nested sub-items")
    if len(result["completion_lists"]) > 1:
        flags.append("C1/C2: more than one list of completion conditions")
    for size in result["long_log_excerpts"]:
        flags.append(f"C4: log or code excerpt of {size} lines (limit {conf['max_log_lines']})")
    for url in result["long_raw_urls"]:
        flags.append(f"C4: raw URL of {len(url)} characters; use a labelled link to the same target")
    if guidance and result["description"]["position"] == "over_twice":
        flags.append("Length: more than twice the guidance; check C1, C3, C5 or a split")
    result["rubric_flags"] = flags
    return result


def preservation(original: dict, proposed: dict, conf: dict) -> dict:
    before = original.get("description") or ""
    after = proposed.get("description")
    after = before if after is None else after
    new_summary = proposed.get("summary") or original.get("summary") or ""
    combined_after = new_summary + "\n" + after
    combined_before = (original.get("summary") or "") + "\n" + before

    def missing(extract):
        kept = set(extract(combined_after))
        return [x for x in extract(combined_before) if x not in kept]

    attribution = ATTRIBUTION_RE.search(before)
    lines = [ln.strip() for ln in after.splitlines() if ln.strip()]
    after_items = [lst["items"] for lst in completion_lists(after, conf)]
    before_words, after_words = word_count(before), word_count(after)
    result = {
        "missing_links": missing(links),
        "missing_issue_keys": missing(lambda t: sorted(set(ISSUE_KEY_RE.findall(t)))),
        "missing_identifiers": missing(lambda t: sorted(set(CODE_SPAN_RE.findall(t)))),
        "missing_numbers": missing(numbers),
        # The attribution must stay verbatim as the description's last line.
        "attribution_kept": (bool(lines) and lines[-1] == attribution.group(0).strip()) if attribution else None,
        "ai_notice_removed": not AI_NOTICE_RE.search(after),
        "completion_items": after_items,
        "completion_over_limit": any(n > conf["max_completion_items"] for n in after_items),
        "summary_words_in_range": conf["summary_words"][0] <= word_count(new_summary) <= conf["summary_words"][1],
        "words": {
            "before": before_words,
            "after": after_words,
            "reduction_pct": round(100 * (before_words - after_words) / before_words) if before_words else 0,
        },
    }
    # Dropped identifiers and numbers are advisory: content removed under C4 or
    # C5 (a reduced log excerpt, dated search findings) takes its details with
    # it. The skill requires each one to be accounted for in the change notes.
    result["passed"] = (
        not result["missing_links"]
        and not result["missing_issue_keys"]
        and result["attribution_kept"] is not False
        and result["ai_notice_removed"]
    )
    return result


STRING_FIELDS = ("key", "issue_type", "status", "summary", "description")


def validate(card: dict) -> None:
    """Reject field values of the wrong type with a ValueError (a JSON error record)."""
    for field in STRING_FIELDS:
        if card.get(field) is not None and not isinstance(card[field], str):
            raise ValueError(f"'{field}' must be a string or null")
    labels = card.get("labels")
    if labels is not None and not (isinstance(labels, list) and all(isinstance(x, str) for x in labels)):
        raise ValueError("'labels' must be a list of strings or null")
    creator = card.get("creator")
    if creator is not None and not isinstance(creator, (str, dict)):
        raise ValueError("'creator' must be a string, an object or null")
    proposed = card.get("proposed")
    if proposed is not None:
        if not isinstance(proposed, dict):
            raise ValueError("'proposed' must be an object or null")
        for field in ("summary", "description"):
            if proposed.get(field) is not None and not isinstance(proposed[field], str):
                raise ValueError(f"'proposed.{field}' must be a string or null")


def check(card: dict, label: str = DEFAULT_LABEL, supported: Optional[List[str]] = None,
          project: Optional[str] = None) -> dict:
    project = project or (card.get("key") or "").split("-")[0] or "TRT"
    conf = PROJECTS.get(project.upper())
    if conf is None:
        raise ValueError(f"no pre-refinement conventions for project {project}")
    validate(card)
    # Only types with a template in the conventions can be reviewed; match an
    # override without regard to case and use the configured name.
    templates = {t.lower(): t for t in conf["guidance"]}
    supported = [templates[t.lower()] for t in (supported or conf["supported_types"]) if t.lower() in templates]
    issue_type = templates.get((card.get("issue_type") or "").lower(), card.get("issue_type") or "")
    eligible, reason, is_supported = eligibility(card, conf, label, supported)
    strict = stricter_review(card.get("labels") or [], card.get("creator"))
    result: Dict = {
        "key": card.get("key"),
        "issue_type": issue_type,
        "supported_type": is_supported,
        "eligible": eligible,
        "skip_reason": reason,
        "stricter_review": strict,
    }
    if is_supported:
        result.update(describe(card, conf, issue_type, strict["applied"]))
        if card.get("proposed") is not None:
            result["preservation"] = preservation(card, card["proposed"], conf)
            proposed = dict(card, summary=card["proposed"].get("summary") or card.get("summary"))
            if card["proposed"].get("description") is not None:
                proposed["description"] = card["proposed"]["description"]
            result["preservation"]["proposal_rubric_flags"] = describe(
                proposed, conf, issue_type, strict["applied"])["rubric_flags"]
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--label", default=DEFAULT_LABEL, help="Label that marks a pre-refined card")
    parser.add_argument("--supported-types", help="Comma-separated issue types to review")
    parser.add_argument("--project", help="Project key; defaults to the card key's prefix")
    args = parser.parse_args()
    try:
        card = json.loads(sys.stdin.read())
        if not isinstance(card, dict):
            raise ValueError("input must be a JSON object")
        supported = [t.strip() for t in args.supported_types.split(",") if t.strip()] if args.supported_types else None
        print(json.dumps(check(card, args.label, supported, args.project), indent=2))
    except (ValueError, json.JSONDecodeError) as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(1)


if __name__ == "__main__":
    main()
