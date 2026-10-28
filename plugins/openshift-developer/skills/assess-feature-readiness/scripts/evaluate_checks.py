#!/usr/bin/env python3
"""Deterministic helpers for assess-feature-readiness checks.

Invoke after Jira payloads are fetched. Do not reimplement R8/R1/R6 matchers
inline — import or run this script so token-boundary rules stay correct.

Examples:
  python3 evaluate_checks.py verify-fields --feature path/to/feature.json \\
      --qa-field customfield_10470
  python3 evaluate_checks.py evaluate --features-dir path/to/features \\
      --qa-field customfield_10470
  python3 evaluate_checks.py saturation --report path/to/readiness-report.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

LONG_PHRASES = ("quality", "automation", "e2e", "integration test")
SHORT_TOKEN_RE = re.compile(r"(?i)(^|[^A-Za-z0-9])(tests?|CI|QE)([^A-Za-z0-9]|$)")
QUALITY_LABELS = {"qe", "quality", "test-plan", "automation"}
EXPECTED_SECTIONS = (
    "Feature Overview",
    "Goals",
    "Requirements",
    "Use Cases",
    "Deployment Considerations",
    "Interoperability",
    "Customer Considerations",
)
PLACEHOLDER_MARKERS = ("<your text here>", "tbd", "todo", "n/a")
TEST_PLAN_TITLE_RE = re.compile(r"(?i)test.*plan")
REQUIRED_CORE_FIELDS = (
    "summary",
    "description",
    "priority",
    "status",
    "subtasks",
    "issuelinks",
    "labels",
    "components",
)


def _fields_blob(feature: dict[str, Any]) -> dict[str, Any]:
    if isinstance(feature.get("fields"), dict):
        return feature["fields"]
    return feature


def verify_fields(
    feature: dict[str, Any],
    qa_contact_field: str,
    require_comment: bool = True,
) -> dict[str, Any]:
    """Confirm requested keys were returned (absent key ≠ empty value)."""
    fields = _fields_blob(feature)
    missing: list[str] = []
    for name in REQUIRED_CORE_FIELDS:
        if name not in fields:
            missing.append(name)
    if qa_contact_field not in fields:
        missing.append(qa_contact_field)
    if require_comment and "comment" not in fields:
        missing.append("comment")
    return {
        "fields_missing": missing,
        "qa_contact_field_fetched": qa_contact_field in fields,
        "comments_available": "comment" in fields,
        "ok": len(missing) == 0,
        "stop_recommended": len(missing) >= 2,
    }


def evaluate_r6(feature: dict[str, Any], qa_contact_field: str) -> dict[str, Any]:
    fields = _fields_blob(feature)
    if qa_contact_field not in fields:
        return {
            "status": "unknown",
            "qa_contact": None,
            "qa_contact_status": "unfetched",
        }
    raw = fields.get(qa_contact_field)
    if raw is None or raw == "" or raw == []:
        return {
            "status": "empty",
            "qa_contact": None,
            "qa_contact_status": "empty",
        }
    if isinstance(raw, dict):
        name = raw.get("displayName") or raw.get("name") or raw.get("emailAddress")
        if name:
            return {
                "status": "assigned",
                "qa_contact": str(name),
                "qa_contact_status": "assigned",
            }
        return {
            "status": "empty",
            "qa_contact": None,
            "qa_contact_status": "empty",
        }
    return {
        "status": "assigned",
        "qa_contact": str(raw),
        "qa_contact_status": "assigned",
    }


def is_quality_item(
    summary: str,
    labels: list[str] | None = None,
    components: list[str] | None = None,
) -> bool:
    """R8 matcher — long phrases substring; test/CI/QE token-boundary only."""
    s = summary or ""
    low = s.lower()
    if any(p in low for p in LONG_PHRASES):
        return True
    if SHORT_TOKEN_RE.search(s):
        return True
    if any((lbl or "").lower() in QUALITY_LABELS for lbl in (labels or [])):
        return True
    for c in components or []:
        cl = (c or "").lower()
        if cl == "qe" or cl.startswith("qe "):
            return True
    return False


def evaluate_r1(
    remote_links: list[dict[str, Any]] | None,
    remote_links_status: str = "ok",
    comments_available: bool = True,
    description_available: bool = True,
) -> dict[str, Any]:
    links = remote_links or []
    for link in links:
        title = link.get("title") or ""
        url = (link.get("url") or "").lower()
        if TEST_PLAN_TITLE_RE.search(title) or "/plans/" in url or "/test-plan" in url:
            return {
                "status": "linked",
                "plan_status": "linked",
                "plan_url": link.get("url"),
            }
    # Unreadable sources that could still hold a plan URL → Unknown, not Missing
    if (
        remote_links_status == "unavailable"
        or not comments_available
        or not description_available
    ):
        return {
            "status": "unknown",
            "plan_status": "unknown",
            "plan_url": None,
        }
    return {
        "status": "missing",
        "plan_status": "missing",
        "plan_url": None,
    }


def description_to_text(description: Any) -> str | None:
    """Normalize Jira description to plain text.

    Accepts wiki/markdown strings or Atlassian Document Format (ADF) objects from
    REST v3. Never pass a raw dict into regex section matchers.
    """
    if description is None:
        return None
    if isinstance(description, str):
        return description
    if isinstance(description, (dict, list)):
        text = _adf_to_text(description).strip()
        return text if text else ""
    return None


def _adf_to_text(node: Any) -> str:
    if node is None:
        return ""
    if isinstance(node, str):
        return node
    if isinstance(node, list):
        return "".join(_adf_to_text(child) for child in node)
    if not isinstance(node, dict):
        return ""
    ntype = node.get("type")
    if ntype == "text":
        return str(node.get("text") or "")
    if ntype == "hardBreak":
        return "\n"
    parts = [_adf_to_text(child) for child in (node.get("content") or [])]
    body = "".join(parts)
    if ntype == "heading":
        level = int((node.get("attrs") or {}).get("level") or 3)
        level = max(1, min(level, 6))
        return f"\n{'#' * level} {body.strip()}\n"
    if ntype in {"paragraph", "blockquote", "bulletList", "orderedList", "listItem", "panel", "table", "tableRow", "tableCell", "tableHeader"}:
        return body + ("\n" if ntype in {"paragraph", "listItem", "blockquote"} else "")
    return body


def _section_heading_re(section: str) -> re.Pattern[str]:
    """Match a wiki/markdown heading line for an expected section name only."""
    return re.compile(
        rf"(?im)^[ \t]*(?:h[1-6]\.[ \t]*\*?|#{{1,6}}[ \t]*\*?){re.escape(section)}\*?[ \t]*$"
    )


def _find_section_headings(text: str) -> list[tuple[int, str, int]]:
    """Locate expected-section headings (heading lines only — not prose mentions)."""
    matches: list[tuple[int, str, int]] = []
    for section in EXPECTED_SECTIONS:
        m = _section_heading_re(section).search(text)
        if m:
            matches.append((m.start(), section, m.end()))
    matches.sort(key=lambda x: x[0])
    return matches


def _section_bodies(text: str) -> dict[str, str]:
    """Split description into expected-section bodies by heading order.

    Bodies run until the next *expected* section heading. Nested subsection
    headings (h4 / ####) and their content are preserved inside the parent body.
    """
    matches = _find_section_headings(text)
    bodies: dict[str, str] = {s: "" for s in EXPECTED_SECTIONS}
    for i, (_start, section, end) in enumerate(matches):
        next_start = matches[i + 1][0] if i + 1 < len(matches) else len(text)
        bodies[section] = text[end:next_start]
    return bodies


def _line_is_placeholder_only(ln: str) -> bool:
    cleaned = ln.strip().strip("*_ \t").lower()
    if not cleaned:
        return True
    if re.fullmatch(r"[|*=\-_\s]+", cleaned):
        return True
    # Nested headings inside a section are structural, not content
    if re.match(r"^(?:h[1-6]\.|#{1,6})\s*", cleaned):
        return True
    normalized = re.sub(r"[.!,;:]+$", "", cleaned).strip()
    # Whole-line placeholder only — do not match markers inside substantive prose
    return normalized in PLACEHOLDER_MARKERS


def _body_is_placeholder(body: str) -> bool:
    stripped = (body or "").strip()
    if not stripped:
        return True
    meaningful: list[str] = []
    for ln in stripped.splitlines():
        cleaned = ln.strip()
        if not cleaned:
            continue
        if _line_is_placeholder_only(cleaned):
            # placeholder-only / structural line — ignore for "has content"
            continue
        meaningful.append(cleaned)
    # Placeholder when nothing substantive remains (empty or only TBD/N/A lines)
    if not meaningful:
        return True
    return False


def evaluate_r2(description: Any) -> dict[str, Any]:
    text = description_to_text(description)
    if text is None:
        return {
            "status": "unknown",
            "template_status": "unknown",
            "sections_absent": [],
            "sections_placeholder": [],
            "unfilled_sections": [],
            "unfilled_count": 0,
        }
    absent: list[str] = []
    placeholder: list[str] = []
    headings = {section for _s, section, _e in _find_section_headings(text)}
    bodies = _section_bodies(text)
    for section in EXPECTED_SECTIONS:
        if section not in headings:
            absent.append(section)
            continue
        if _body_is_placeholder(bodies.get(section, "")):
            placeholder.append(section)
    if len(absent) == len(EXPECTED_SECTIONS):
        return {
            "status": "unknown",
            "template_status": "unknown",
            "sections_absent": absent,
            "sections_placeholder": placeholder,
            "unfilled_sections": absent,
            "unfilled_count": len(absent),
        }
    unfilled = absent + placeholder
    count = len(unfilled)
    if count == 0:
        status = "filled"
    elif count <= 3:
        status = "partial"
    else:
        status = "unfilled"
    return {
        "status": status,
        "template_status": status,
        "sections_absent": absent,
        "sections_placeholder": placeholder,
        "unfilled_sections": unfilled,
        "unfilled_count": count,
    }


def component_matches(components: list[str] | None, team: str) -> bool:
    """Case-insensitive component membership for --team."""
    needle = (team or "").strip().lower()
    if not needle:
        return True
    return any((c or "").strip().lower() == needle for c in (components or []))


def saturation_flags(
    features: list[dict[str, Any]],
    min_features: int = 10,
) -> list[str]:
    """Flag checks where one verdict is 100% across assessed features.

    Deduplicates multi-component duplicates by feature key. Skips features with
    verdict/status ``not_assessed`` (budget exhaustion) so they do not inflate
    the denominator or suppress a real calibration flag.
    """
    deduped: dict[str, dict[str, Any]] = {}
    for feat in features:
        key = feat.get("key") or id(feat)
        # Prefer first occurrence; team duplicates share the same checks
        if key not in deduped:
            deduped[str(key)] = feat
    assessed = [
        f
        for f in deduped.values()
        if str(f.get("verdict") or "").lower() != "not_assessed"
        and str((f.get("status") or "")).lower() != "not_assessed"
        and (f.get("checks") or {})
    ]
    if len(assessed) < min_features:
        return []
    by_check: dict[str, dict[str, int]] = {}
    for feat in assessed:
        checks = feat.get("checks") or {}
        for name, payload in checks.items():
            status = (payload or {}).get("status") or (payload or {}).get("qa_contact_status")
            if not status:
                continue
            by_check.setdefault(name, {})
            by_check[name][str(status)] = by_check[name].get(str(status), 0) + 1
    flags: list[str] = []
    deps = {
        "R1": "remote_links / description-comment URL merge",
        "R6": "qa_contact_field in issue payload",
        "R10": "CI remote links + feature-test association",
        "R11": "PR remote links / gh",
        "R12": "doc remote links / OSDOCS",
    }
    for check, counts in by_check.items():
        # Denominator = features that have this check evaluated
        check_n = sum(counts.values())
        if check_n < min_features:
            continue
        if len(counts) != 1:
            continue
        verdict, count = next(iter(counts.items()))
        if count != check_n:
            continue
        dep = deps.get(check, f"field/call used by {check}")
        flags.append(
            f"⚠️ CALIBRATION: {check} returned {verdict} for 100% of {check_n} features. "
            f"This is consistent with either a genuine org-wide gap or a data-acquisition "
            f"failure. Verify before acting: {dep}."
        )
    return flags


def _cmd_verify(args: argparse.Namespace) -> int:
    feature = json.loads(Path(args.feature).read_text())
    result = verify_fields(feature, args.qa_field, require_comment=not args.no_comment)
    json.dump(result, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0 if result["ok"] or not args.strict else 2


def _cmd_evaluate(args: argparse.Namespace) -> int:
    features_dir = Path(args.features_dir)
    out: list[dict[str, Any]] = []
    for path in sorted(features_dir.glob("*.json")):
        feature = json.loads(path.read_text())
        fields = _fields_blob(feature)
        verification = verify_fields(feature, args.qa_field)
        r6 = evaluate_r6(feature, args.qa_field)
        r1 = evaluate_r1(
            feature.get("remote_links") or fields.get("remote_links"),
            feature.get("remote_links_status", "ok"),
            verification["comments_available"],
            description_available="description" in fields,
        )
        if "description" not in fields:
            r2 = {
                "status": "unknown",
                "template_status": "unknown",
                "sections_absent": [],
                "sections_placeholder": [],
                "unfilled_sections": [],
                "unfilled_count": 0,
            }
        else:
            # Flattens ADF objects; string descriptions pass through.
            r2 = evaluate_r2(fields.get("description"))
        out.append(
            {
                "key": feature.get("key") or path.stem,
                "fields_verification": verification,
                "R1": r1,
                "R2": r2,
                "R6": r6,
            }
        )
    json.dump({"features": out}, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


def _cmd_saturation(args: argparse.Namespace) -> int:
    report = json.loads(Path(args.report).read_text())
    features: list[dict[str, Any]] = []
    for team in (report.get("teams") or {}).values():
        features.extend(team.get("features") or [])
    if report.get("feature"):
        features.append(report["feature"])
    flags = saturation_flags(features)
    json.dump({"calibration_flags": flags}, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


def _cmd_selftest(_: argparse.Namespace) -> int:
    assert is_quality_item("QE: e2e tests for PSA") is True
    assert is_quality_item("Update latest container image") is False
    assert is_quality_item("Implement special handling") is False
    assert is_quality_item("Add automation for builds") is True
    assert is_quality_item("run tests nightly") is True
    assert component_matches(["Networking"], "networking") is True
    assert component_matches(["Networking"], "storage") is False
    sample = {"fields": {"summary": "x"}}
    v = verify_fields(sample, "customfield_10470")
    assert v["qa_contact_field_fetched"] is False
    r6 = evaluate_r6(sample, "customfield_10470")
    assert r6["qa_contact_status"] == "unfetched"
    # R1 ordered title: "Plan for test" alone is not a plan link
    r1_bad = evaluate_r1([{"title": "Plan for test", "url": "https://example.com/x"}])
    assert r1_bad["plan_status"] == "missing"
    r1_ok = evaluate_r1([{"title": "Test Plan — PSA", "url": "https://example.com/x"}])
    assert r1_ok["plan_status"] == "linked"
    r1_nodesc = evaluate_r1([], "ok", True, description_available=False)
    assert r1_nodesc["plan_status"] == "unknown"
    # R2: all headings with TBD bodies → unfilled, not filled
    tbd_desc = "\n".join(f"h3. *{s}*\nTBD\n" for s in EXPECTED_SECTIONS)
    r2 = evaluate_r2(tbd_desc)
    assert r2["template_status"] == "unfilled"
    assert r2["unfilled_count"] == 7
    # R2: prose mention of another section must not steal the heading match
    prose_trap = (
        "h3. *Feature Overview*\nSee Requirements for limits.\n"
        "h3. *Goals*\nShip the feature.\n"
        "h3. *Requirements*\nTBD\n"
        "h3. *Use Cases*\nUsers install the operator.\n"
        "h3. *Deployment Considerations*\nStandard.\n"
        "h3. *Interoperability*\nNone.\n"
        "h3. *Customer Considerations*\nSupportable.\n"
    )
    r2_trap = evaluate_r2(prose_trap)
    assert "Requirements" in r2_trap["sections_placeholder"]
    assert r2_trap["template_status"] in ("partial", "unfilled")
    # R2: nested subsection content must count as filled
    nested = (
        "h3. *Feature Overview*\nOverview text.\n"
        "h3. *Goals*\nh4. Scope\nImplemented behavior.\n"
        "h3. *Requirements*\nMust work on AWS.\n"
        "h3. *Use Cases*\nInstall and upgrade.\n"
        "h3. *Deployment Considerations*\nHA.\n"
        "h3. *Interoperability*\nOVN.\n"
        "h3. *Customer Considerations*\nDocumented.\n"
    )
    r2_nested = evaluate_r2(nested)
    assert r2_nested["template_status"] == "filled", r2_nested
    # R2: "n/a" inside substantive prose is not a placeholder line
    na_prose = (
        "h3. *Feature Overview*\nAuthentication/authorization uses existing RBAC.\n"
        "h3. *Goals*\nSecure access.\n"
        "h3. *Requirements*\nUse platform RBAC.\n"
        "h3. *Use Cases*\nAdmin grants access.\n"
        "h3. *Deployment Considerations*\nNone special.\n"
        "h3. *Interoperability*\nWorks with SSO.\n"
        "h3. *Customer Considerations*\nNo new IAM.\n"
    )
    r2_na = evaluate_r2(na_prose)
    assert r2_na["template_status"] == "filled", r2_na
    # R2: ADF object description flattens instead of TypeError
    adf = {
        "type": "doc",
        "content": [
            {
                "type": "heading",
                "attrs": {"level": 3},
                "content": [{"type": "text", "text": "Feature Overview"}],
            },
            {
                "type": "paragraph",
                "content": [{"type": "text", "text": "ADF overview body"}],
            },
        ],
    }
    r2_adf = evaluate_r2(adf)
    assert "Feature Overview" not in (r2_adf.get("sections_absent") or []), r2_adf
    # Saturation: dedupe multi-component + ignore not_assessed
    feats = []
    for i in range(10):
        feats.append({"key": f"K{i}", "checks": {"R6": {"status": "empty"}}})
        feats.append({"key": f"K{i}", "checks": {"R6": {"status": "empty"}}})  # dupe team
    feats.append({"key": "Z", "verdict": "not_assessed", "checks": {}})
    flags = saturation_flags(feats)
    assert any("R6" in f and "10 features" in f for f in flags)
    print("selftest ok")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_verify = sub.add_parser("verify-fields")
    p_verify.add_argument("--feature", required=True)
    p_verify.add_argument("--qa-field", default="customfield_10470")
    p_verify.add_argument("--no-comment", action="store_true")
    p_verify.add_argument("--strict", action="store_true")
    p_verify.set_defaults(func=_cmd_verify)

    p_eval = sub.add_parser("evaluate")
    p_eval.add_argument("--features-dir", required=True)
    p_eval.add_argument("--qa-field", default="customfield_10470")
    p_eval.set_defaults(func=_cmd_evaluate)

    p_sat = sub.add_parser("saturation")
    p_sat.add_argument("--report", required=True)
    p_sat.set_defaults(func=_cmd_saturation)

    p_test = sub.add_parser("selftest")
    p_test.set_defaults(func=_cmd_selftest)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
