#!/usr/bin/env python3
"""Validate a generic debugging evidence contract and hydrate cited excerpts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from urllib.parse import urlparse


SCHEMA_VERSION = "1.0"
INVESTIGATION_STATUSES = {"supported", "inconclusive"}
CHAIN_STATUSES = {"supported", "ruled_out", "inconclusive"}
PROOF_TYPES = {
    "code",
    "command",
    "configuration",
    "data",
    "log",
    "metric",
    "other",
    "test",
    "trace",
}
VERIFICATION_METHODS = {
    "counterfactual",
    "cross-source",
    "fix-validation",
    "other",
    "reproduction",
}
MAX_EXCERPT_LINES = 200


def _text(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def _markdown_code(value: str) -> str:
    fence = "`" if "`" not in value else "``"
    return f"{fence}{value}{fence}"


def _markdown_link_label(value: str) -> str:
    return value.replace("\\", "\\\\").replace("[", "\\[").replace("]", "\\]")


def _resolve_artifact(root: Path, value: object) -> tuple[Path | None, str | None]:
    artifact = _text(value)
    if not artifact:
        return None, "missing non-empty 'artifact'"
    if "\n" in artifact or "\r" in artifact:
        return None, "'artifact' must not contain newlines"

    candidate = Path(artifact)
    if candidate.is_absolute():
        return None, "'artifact' must be relative to --root"

    resolved_root = root.resolve()
    resolved = (resolved_root / candidate).resolve()
    try:
        resolved.relative_to(resolved_root)
    except ValueError:
        return None, f"artifact escapes evidence root: {artifact!r}"
    if not resolved.is_file():
        return None, f"artifact does not exist or is not a file: {artifact!r}"
    return resolved, None


def _validate_url(value: object) -> str | None:
    url = _text(value)
    if not url:
        return None
    if any(character.isspace() for character in url) or "<" in url or ">" in url:
        return "'artifact_url' must not contain whitespace or angle brackets"
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return "'artifact_url' must be an http or https URL"
    return None


def _hydrate_proofs(
    proofs: object,
    at: str,
    root: Path,
    errors: list[str],
) -> list[str]:
    rendered: list[str] = []
    if not isinstance(proofs, list) or not proofs:
        errors.append(f"{at} must be a non-empty array")
        return rendered

    for proof_index, proof in enumerate(proofs):
        proof_at = f"{at}[{proof_index}]"
        if not isinstance(proof, dict):
            errors.append(f"{proof_at} must be an object")
            continue

        proof_type = _text(proof.get("type"))
        if proof_type not in PROOF_TYPES:
            errors.append(f"{proof_at}.type must be one of {sorted(PROOF_TYPES)}")

        note = _text(proof.get("note"))
        if not note:
            errors.append(f"{proof_at} missing non-empty 'note'")

        url_error = _validate_url(proof.get("artifact_url"))
        if url_error:
            errors.append(f"{proof_at}: {url_error}")

        artifact, artifact_error = _resolve_artifact(root, proof.get("artifact"))
        if artifact_error:
            errors.append(f"{proof_at}: {artifact_error}")
            continue

        lines = proof.get("lines")
        if (
            not isinstance(lines, list)
            or len(lines) != 2
            or any(
                not isinstance(number, int) or isinstance(number, bool)
                for number in lines
            )
            or lines[0] < 1
            or lines[1] < lines[0]
        ):
            errors.append(
                f"{proof_at}.lines must be two 1-indexed integers with start <= end"
            )
            continue

        start, end = lines
        if end - start + 1 > MAX_EXCERPT_LINES:
            errors.append(
                f"{proof_at}.lines must cite no more than {MAX_EXCERPT_LINES} lines"
            )
            continue

        try:
            artifact_lines = artifact.read_text(
                encoding="utf-8", errors="strict"
            ).splitlines()
        except (OSError, UnicodeError) as exc:
            errors.append(f"{proof_at}: cannot read UTF-8 artifact: {exc}")
            continue

        if end > len(artifact_lines):
            errors.append(
                f"{proof_at}.lines [{start}, {end}] exceed artifact length "
                f"({len(artifact_lines)} lines)"
            )
            continue

        artifact_label = _text(proof.get("artifact"))
        artifact_url = _text(proof.get("artifact_url"))
        if artifact_url and not url_error:
            source = f"[{_markdown_link_label(artifact_label)}](<{artifact_url}>)"
        else:
            source = _markdown_code(artifact_label)
        rendered.extend(
            [
                f"Proof {proof_index + 1} ({proof_type or 'unknown'}, {source}, "
                f"lines {start}-{end}):",
                "",
                "```text",
            ]
        )
        width = len(str(end))
        for number in range(start, end + 1):
            rendered.append(f"{number:>{width}} | {artifact_lines[number - 1]}")
        rendered.extend(["```", "", f"Why it supports the claim: {note}", ""])

    return rendered


def validate_and_render(document: Path, root: Path) -> tuple[list[str], str]:
    errors: list[str] = []
    rendered: list[str] = []

    try:
        data = json.loads(document.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return [f"document not found: {document}"], ""
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return [f"cannot read JSON document: {exc}"], ""

    if not isinstance(data, dict):
        return ["document root must be an object"], ""

    if data.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"'schema_version' must be {SCHEMA_VERSION!r}")

    investigation = data.get("investigation")
    if not isinstance(investigation, dict):
        errors.append("'investigation' must be an object")
        investigation = {}
    question = _text(investigation.get("question"))
    scope = _text(investigation.get("scope"))
    status = _text(investigation.get("status"))
    if not question:
        errors.append("investigation missing non-empty 'question'")
    if not scope:
        errors.append("investigation missing non-empty 'scope'")
    if status not in INVESTIGATION_STATUSES:
        errors.append(
            f"investigation.status must be one of {sorted(INVESTIGATION_STATUSES)}"
        )

    rendered.extend(
        [
            f"# Validated debugging evidence: {question or 'Unknown question'}",
            "",
            f"**Scope:** {scope or 'Missing scope'}",
            "",
            f"**Status:** {status or 'unknown'}",
            "",
        ]
    )

    chains = data.get("chains")
    if not isinstance(chains, list):
        errors.append("'chains' must be an array")
        chains = []
    elif status == "supported" and not chains:
        errors.append("supported investigation requires at least one evidence chain")
    if not chains:
        rendered.extend(["## Evidence chains", "", "No evidence chains recorded.", ""])

    seen_chain_ids: set[str] = set()
    supported_chain_ids: set[str] = set()
    for chain_index, chain in enumerate(chains):
        chain_at = f"chains[{chain_index}]"
        if not isinstance(chain, dict):
            errors.append(f"{chain_at} must be an object")
            continue

        chain_id = _text(chain.get("id"))
        hypothesis = _text(chain.get("hypothesis"))
        chain_status = _text(chain.get("status"))
        if not chain_id:
            errors.append(f"{chain_at} missing non-empty 'id'")
            chain_id = f"chain-{chain_index + 1}"
        elif chain_id in seen_chain_ids:
            errors.append(f"duplicate chain id: {chain_id!r}")
        else:
            seen_chain_ids.add(chain_id)
        if not hypothesis:
            errors.append(f"{chain_at} missing non-empty 'hypothesis'")
        if chain_status not in CHAIN_STATUSES:
            errors.append(f"{chain_at}.status must be one of {sorted(CHAIN_STATUSES)}")
        elif chain_status == "supported":
            supported_chain_ids.add(chain_id)

        rendered.extend(
            [
                f"## Chain: {_markdown_code(chain_id)}",
                "",
                f"**Hypothesis:** {hypothesis or 'Missing hypothesis'}",
                "",
                f"**Chain status:** {chain_status or 'unknown'}",
                "",
            ]
        )

        links = chain.get("links")
        if not isinstance(links, list) or not links:
            errors.append(f"{chain_at}.links must be a non-empty array")
            continue

        for link_index, link in enumerate(links):
            link_at = f"{chain_at}.links[{link_index}]"
            if not isinstance(link, dict):
                errors.append(f"{link_at} must be an object")
                continue
            link_question = _text(link.get("question"))
            answer = _text(link.get("answer"))
            if not link_question:
                errors.append(f"{link_at} missing non-empty 'question'")
            if not answer:
                errors.append(f"{link_at} missing non-empty 'answer'")

            rendered.extend(
                [
                    f"### {link_index + 1}. {link_question or 'Missing question'}",
                    "",
                    answer or "Missing answer",
                    "",
                ]
            )
            rendered.extend(
                _hydrate_proofs(link.get("proof"), f"{link_at}.proof", root, errors)
            )

    conclusion = data.get("conclusion")
    if not isinstance(conclusion, dict):
        errors.append("'conclusion' must be an object")
        conclusion = {}
    conclusion_answer = _text(conclusion.get("answer"))
    if not conclusion_answer:
        errors.append("conclusion missing non-empty 'answer'")

    chain_ids = conclusion.get("chain_ids")
    referenced_chain_ids: list[str] = []
    if not isinstance(chain_ids, list):
        errors.append("conclusion.chain_ids must be an array")
    else:
        for index, value in enumerate(chain_ids):
            chain_id = _text(value)
            if not chain_id:
                errors.append(f"conclusion.chain_ids[{index}] must be a non-empty string")
            elif chain_id in referenced_chain_ids:
                errors.append(f"duplicate conclusion chain reference: {chain_id!r}")
            else:
                referenced_chain_ids.append(chain_id)
        unknown = sorted(set(referenced_chain_ids) - seen_chain_ids)
        if unknown:
            errors.append(f"conclusion references unknown chain(s): {', '.join(unknown)}")
        if status == "supported" and not referenced_chain_ids:
            errors.append("supported conclusion requires at least one chain reference")

    verification = conclusion.get("verification")
    if not isinstance(verification, list):
        errors.append("conclusion.verification must be an array")
        verification = []
    if status == "supported":
        if not supported_chain_ids:
            errors.append("supported investigation requires at least one supported chain")
        elif not supported_chain_ids.intersection(referenced_chain_ids):
            errors.append(
                "supported conclusion must reference at least one supported chain"
            )
        if not verification:
            errors.append("supported investigation requires at least one verification")

    limitations = conclusion.get("limitations")
    if not isinstance(limitations, list) or any(
        not _text(limitation) for limitation in limitations
    ):
        errors.append("conclusion.limitations must be an array of non-empty strings")
        limitations = []
    if status == "inconclusive" and not limitations:
        errors.append("inconclusive investigation requires at least one limitation")

    rendered.extend(["## Conclusion", "", conclusion_answer or "Missing conclusion", ""])
    rendered.extend(
        [
            "**Supporting chains:** "
            + ", ".join(_markdown_code(value) for value in referenced_chain_ids),
            "",
            "## Verification",
            "",
        ]
    )
    if not verification:
        rendered.extend(["No independent verification recorded.", ""])
    for verification_index, check in enumerate(verification):
        check_at = f"conclusion.verification[{verification_index}]"
        if not isinstance(check, dict):
            errors.append(f"{check_at} must be an object")
            continue
        method = _text(check.get("method"))
        claim = _text(check.get("claim"))
        if method not in VERIFICATION_METHODS:
            errors.append(
                f"{check_at}.method must be one of {sorted(VERIFICATION_METHODS)}"
            )
        if not claim:
            errors.append(f"{check_at} missing non-empty 'claim'")
        rendered.extend(
            [
                f"### {verification_index + 1}. {method or 'Unknown method'}",
                "",
                claim or "Missing verification claim",
                "",
            ]
        )
        rendered.extend(
            _hydrate_proofs(check.get("proof"), f"{check_at}.proof", root, errors)
        )

    rendered.extend(["## Limitations", ""])
    if limitations:
        rendered.extend(f"- {limitation}" for limitation in limitations)
        rendered.append("")
    else:
        rendered.extend(["None recorded.", ""])

    return errors, "\n".join(rendered).rstrip() + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("document", type=Path)
    parser.add_argument(
        "--root",
        type=Path,
        default=None,
        help="Allowed artifact root (defaults to the document directory)",
    )
    parser.add_argument("--render", type=Path, help="Write hydrated Markdown here")
    args = parser.parse_args(argv)

    root = args.root or args.document.parent
    errors, markdown = validate_and_render(args.document, root)
    if errors:
        print(f"FAIL: {len(errors)} evidence error(s)")
        for error in errors:
            print(f"  - {error}")
        return 1

    if args.render:
        try:
            args.render.parent.mkdir(parents=True, exist_ok=True)
            args.render.write_text(markdown, encoding="utf-8")
        except OSError as exc:
            print(f"FAIL: cannot write hydrated report: {exc}")
            return 1
        print(f"OK: evidence validated; hydrated report written to {args.render}")
    else:
        print("OK: evidence validated")
    return 0


if __name__ == "__main__":
    sys.exit(main())
