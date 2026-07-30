#!/usr/bin/env python3
"""Render a safe, self-contained payload analysis comparison report."""

from __future__ import annotations

import argparse
import html
import json
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


ASSESSMENTS = {
    "correct": ("Supported", "status-correct"),
    "mixed": ("Mixed", "status-mixed"),
    "incorrect": ("Unsupported", "status-incorrect"),
}
REQUIRED_ROW_FIELDS = ("topic", "assessment", "right", "wrong", "combined")


class RenderError(RuntimeError):
    """Invalid comparison input or template."""


def escaped(value: Any) -> str:
    if not isinstance(value, str):
        raise RenderError(f"Expected a string, got {type(value).__name__}")
    return html.escape(value, quote=True).replace("\n", "<br>")


def safe_url(value: Any) -> str:
    if not isinstance(value, str):
        raise RenderError("Report and evidence URLs must be strings")
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise RenderError(f"Only http(s) URLs are allowed: {value}")
    return html.escape(value, quote=True)


def source_link(source: Any) -> str:
    if source is None:
        return ""
    if not isinstance(source, dict):
        raise RenderError("Report source must be an object")
    label = escaped(source.get("label"))
    if source.get("url"):
        return (
            f'<a href="{safe_url(source.get("url"))}" target="_blank" '
            f'rel="noopener noreferrer">{label}</a>'
        )
    if source.get("path"):
        return f"{label} (<code>{escaped(source.get('path'))}</code>)"
    raise RenderError("Report source must contain url or path")


def evidence_links(evidence: Any) -> str:
    if evidence is None:
        return ""
    if not isinstance(evidence, list):
        raise RenderError("Row evidence must be a list")
    links = []
    for item in evidence:
        if not isinstance(item, dict):
            raise RenderError("Each evidence entry must be an object")
        links.append(
            f'<a href="{safe_url(item.get("url"))}" target="_blank" '
            f'rel="noopener noreferrer">{escaped(item.get("label"))}</a>'
        )
    if not links:
        return ""
    return (
        '<div class="evidence"><strong>Evidence:</strong> '
        + " · ".join(links)
        + "</div>"
    )


def render_rows(rows: Any) -> tuple[str, dict[str, int]]:
    if not isinstance(rows, list) or not rows:
        raise RenderError("rows must be a non-empty list")
    rendered: list[str] = []
    counts = {assessment: 0 for assessment in ASSESSMENTS}
    for row in rows:
        if not isinstance(row, dict):
            raise RenderError("Each row must be an object")
        missing = [field for field in REQUIRED_ROW_FIELDS if field not in row]
        if missing:
            raise RenderError(f"Comparison row is missing: {', '.join(missing)}")
        assessment = row["assessment"]
        if assessment not in ASSESSMENTS:
            raise RenderError(
                f"assessment must be one of {', '.join(ASSESSMENTS)}, got {assessment}"
            )
        counts[assessment] += 1
        label, css_class = ASSESSMENTS[assessment]
        rendered.append(
            "<tr>"
            f'<th scope="row"><span class="status {css_class}">{label}</span>'
            f'<span class="topic">{escaped(row["topic"])}</span></th>'
            f'<td class="right">{escaped(row["right"])}</td>'
            f'<td class="wrong">{escaped(row["wrong"])}</td>'
            f'<td class="combined">{escaped(row["combined"])}'
            f"{evidence_links(row.get('evidence'))}</td>"
            "</tr>"
        )
    return "\n".join(rendered), counts


def render(data: dict[str, Any], template: str) -> str:
    for key in ("payload_tag", "verdict", "rows"):
        if key not in data:
            raise RenderError(f"Missing top-level field: {key}")
    rows, counts = render_rows(data["rows"])
    sources = [
        link
        for link in (
            source_link(data.get("independent_report")),
            source_link(data.get("other_report")),
        )
        if link
    ]
    replacements = {
        "@@PAYLOAD_TAG@@": escaped(data["payload_tag"]),
        "@@VERDICT@@": escaped(data["verdict"]),
        "@@ROWS@@": rows,
        "@@CORRECT_COUNT@@": str(counts["correct"]),
        "@@MIXED_COUNT@@": str(counts["mixed"]),
        "@@INCORRECT_COUNT@@": str(counts["incorrect"]),
        "@@SOURCES@@": " · ".join(sources) if sources else "No report links supplied",
    }
    output = template
    for marker, value in replacements.items():
        output = output.replace(marker, value)
    leftovers = [marker for marker in replacements if marker in output]
    if leftovers:
        raise RenderError(f"Template markers were not replaced: {leftovers}")
    return output


def self_test(template: str) -> None:
    data = {
        "payload_tag": "5.0.0-0.ci-test",
        "verdict": "No product regression <script>alert(1)</script>",
        "independent_report": {
            "label": "Independent",
            "url": "https://example.com/independent.html",
        },
        "other_report": {
            "label": "Other",
            "url": "https://example.com/other.html",
        },
        "rows": [
            {
                "topic": "AWS upgrade",
                "assessment": "mixed",
                "right": "Upgrade disruption was real.",
                "wrong": "The run ID was wrong.",
                "combined": "Use build 09.",
                "evidence": [{"label": "Prow", "url": "https://example.com/prow"}],
            }
        ],
    }
    output = render(data, template)
    assert "<script>alert(1)</script>" not in output
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in output
    assert "AWS upgrade" in output
    assert "@@ROWS@@" not in output


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Render a payload analysis comparison JSON file as HTML"
    )
    parser.add_argument("input", type=Path, nargs="?")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--self-test", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    template_path = (
        Path(__file__).resolve().parent.parent / "assets" / "comparison-report.html"
    )
    try:
        template = template_path.read_text(encoding="utf-8")
        if args.self_test:
            self_test(template)
            print("self-test passed")
            return 0
        if args.input is None:
            raise RenderError("input JSON is required unless --self-test is used")
        data = json.loads(args.input.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise RenderError("Top-level comparison input must be an object")
        output = args.output
        if output is None:
            tag = data.get("payload_tag", "payload")
            output = Path(f"payload-analysis-comparison-{tag}.html")
        rendered = render(data, template)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered, encoding="utf-8")
    except (OSError, json.JSONDecodeError, RenderError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(output.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
