#!/usr/bin/env python3
"""Deterministic helpers for assess-feature-readiness checks.

Invoke after Jira payloads are fetched. Do not reimplement R8/R1/R6 matchers
inline — import or run this script so token-boundary rules stay correct.

Examples:
  python3 evaluate_checks.py verify-fields --feature path/to/feature.json \\
      --qa-field customfield_12319243
  python3 evaluate_checks.py evaluate --features-dir path/to/features \\
      --qa-field customfield_12319243
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


def _section_bodies(text: str) -> dict[str, str]:
    """Split description into expected-section bodies by heading occurrence order."""
    matches: list[tuple[int, str, int]] = []
    for section in EXPECTED_SECTIONS:
        for m in re.finditer(rf"(?i){re.escape(section)}", text):
            matches.append((m.start(), section, m.end()))
            break
    matches.sort(key=lambda x: x[0])
    bodies: dict[str, str] = {s: "" for s in EXPECTED_SECTIONS}
    for i, (_start, section, end) in enumerate(matches):
        next_start = matches[i + 1][0] if i + 1 < len(matches) else len(text)
        raw = text[end:next_start]
        # Drop trailing wiki/markdown heading crumbs that belong to the next section
        raw = re.sub(r"(?is)(?:^|\n)\s*h[1-6]\.\s*.*$", "", raw)
        raw = re.sub(r"(?is)(?:^|\n)\s*#{1,6}\s*.*$", "", raw)
        bodies[section] = raw
    return bodies


def _body_is_placeholder(body: str) -> bool:
    stripped = (body or "").strip()
    if not stripped:
        return True
    low = stripped.lower()
    lines = []
    for ln in low.splitlines():
        cleaned = ln.strip().strip("*_ \t")
        if cleaned:
            lines.append(cleaned)
    if not lines:
        return True
    meaningful = []
    for ln in lines:
        if re.fullmatch(r"[|*=\-_\s]+", ln):
            continue
        if re.fullmatch(r"h[1-6]\..*", ln):
            continue
        meaningful.append(ln)
    if not meaningful:
        return True
    return all(
        any(m == ln or m in ln for m in PLACEHOLDER_MARKERS)
        or re.fullmatch(r"[|*=\-_\s]+", ln)
        for ln in meaningful
    )


def evaluate_r2(description: str | None) -> dict[str, Any]:
    text = description or ""
    absent: list[str] = []
    placeholder: list[str] = []
    bodies = _section_bodies(text)
    for section in EXPECTED_SECTIONS:
        if not re.search(rf"(?i){re.escape(section)}", text):
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
        r2 = (
            evaluate_r2(fields.get("description"))
            if "description" in fields
            else {
                "status": "unknown",
                "template_status": "unknown",
                "sections_absent": [],
                "sections_placeholder": [],
                "unfilled_sections": [],
                "unfilled_count": 0,
            }
        )
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
    v = verify_fields(sample, "customfield_12319243")
    assert v["qa_contact_field_fetched"] is False
    r6 = evaluate_r6(sample, "customfield_12319243")
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
    p_verify.add_argument("--qa-field", default="customfield_12319243")
    p_verify.add_argument("--no-comment", action="store_true")
    p_verify.add_argument("--strict", action="store_true")
    p_verify.set_defaults(func=_cmd_verify)

    p_eval = sub.add_parser("evaluate")
    p_eval.add_argument("--features-dir", required=True)
    p_eval.add_argument("--qa-field", default="customfield_12319243")
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
