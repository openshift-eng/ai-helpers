#!/usr/bin/env python3
"""Validate payload causal-chain citations and render their exact excerpts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


FIRST_QUESTION = "Why did this job fail?"
PROOF_TYPES = {"log", "code"}


def _text(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def _resolve_artifact(root: Path, value: object) -> tuple[Path | None, str | None]:
    artifact = _text(value)
    if not artifact:
        return None, "missing non-empty 'artifact'"
    candidate = Path(artifact)
    if candidate.is_absolute():
        return None, "'artifact' must be relative to --root"

    root = root.resolve()
    resolved = (root / candidate).resolve()
    try:
        resolved.relative_to(root)
    except ValueError:
        return None, f"artifact escapes evidence root: {artifact!r}"
    if not resolved.is_file():
        return None, f"artifact does not exist or is not a file: {artifact!r}"
    return resolved, None


def validate_and_render(
    document: Path, root: Path, expected_jobs: set[str] | None = None
) -> tuple[list[str], str]:
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

    payload_tag = _text(data.get("payload_tag"))
    if not payload_tag:
        errors.append("missing non-empty 'payload_tag'")
    rendered.extend([f"# Validated evidence for `{payload_tag or 'unknown payload'}`", ""])

    jobs = data.get("jobs")
    if not isinstance(jobs, list) or not jobs:
        errors.append("'jobs' must be a non-empty array")
        jobs = []

    seen_jobs: list[str] = []
    for job_index, job in enumerate(jobs):
        job_at = f"jobs[{job_index}]"
        if not isinstance(job, dict):
            errors.append(f"{job_at} must be an object")
            continue

        job_name = _text(job.get("job_name"))
        if not job_name:
            errors.append(f"{job_at} missing non-empty 'job_name'")
            job_name = f"job {job_index + 1}"
        else:
            seen_jobs.append(job_name)
        rendered.extend([f"## `{job_name}`", ""])

        chain = job.get("causal_chain")
        if not isinstance(chain, list) or not chain:
            errors.append(f"{job_at}.causal_chain must be a non-empty array")
            continue

        for link_index, link in enumerate(chain):
            link_at = f"{job_at}.causal_chain[{link_index}]"
            if not isinstance(link, dict):
                errors.append(f"{link_at} must be an object")
                continue

            question = _text(link.get("question"))
            answer = _text(link.get("answer"))
            if not question:
                errors.append(f"{link_at} missing non-empty 'question'")
            elif link_index == 0 and question != FIRST_QUESTION:
                errors.append(
                    f"{link_at}.question must be exactly {FIRST_QUESTION!r}"
                )
            if not answer:
                errors.append(f"{link_at} missing non-empty 'answer'")

            rendered.extend(
                [f"### {link_index + 1}. {question or 'Missing question'}", "", answer, ""]
            )

            proofs = link.get("proof")
            if not isinstance(proofs, list) or not proofs:
                errors.append(f"{link_at}.proof must be a non-empty array")
                continue

            for proof_index, proof in enumerate(proofs):
                proof_at = f"{link_at}.proof[{proof_index}]"
                if not isinstance(proof, dict):
                    errors.append(f"{proof_at} must be an object")
                    continue

                proof_type = _text(proof.get("type"))
                if proof_type not in PROOF_TYPES:
                    errors.append(
                        f"{proof_at}.type must be one of {sorted(PROOF_TYPES)}"
                    )

                note = _text(proof.get("note"))
                if not note:
                    errors.append(f"{proof_at} missing non-empty 'note'")

                artifact, artifact_error = _resolve_artifact(root, proof.get("artifact"))
                if artifact_error:
                    errors.append(f"{proof_at}: {artifact_error}")
                    continue

                lines = proof.get("lines")
                if (
                    not isinstance(lines, list)
                    or len(lines) != 2
                    or any(not isinstance(number, int) or isinstance(number, bool) for number in lines)
                    or lines[0] < 1
                    or lines[1] < lines[0]
                ):
                    errors.append(
                        f"{proof_at}.lines must be two 1-indexed integers with start <= end"
                    )
                    continue

                try:
                    artifact_lines = artifact.read_text(encoding="utf-8", errors="replace").splitlines()
                except OSError as exc:
                    errors.append(f"{proof_at}: cannot read artifact: {exc}")
                    continue

                start, end = lines
                if end > len(artifact_lines):
                    errors.append(
                        f"{proof_at}.lines [{start}, {end}] exceed artifact length "
                        f"({len(artifact_lines)} lines)"
                    )
                    continue

                artifact_label = _text(proof.get("artifact"))
                artifact_url = _text(proof.get("artifact_url"))
                source = f"[{artifact_label}]({artifact_url})" if artifact_url else f"`{artifact_label}`"
                rendered.extend(
                    [
                        f"Proof {proof_index + 1} ({proof_type or 'unknown'}, {source}, lines {start}-{end}):",
                        "",
                        "```text",
                    ]
                )
                width = len(str(end))
                for number in range(start, end + 1):
                    rendered.append(f"{number:>{width}} | {artifact_lines[number - 1]}")
                rendered.extend(["```", "", f"Why it supports the answer: {note}", ""])

    duplicates = sorted({name for name in seen_jobs if seen_jobs.count(name) > 1})
    if duplicates:
        errors.append(f"duplicate job evidence entries: {', '.join(duplicates)}")
    if expected_jobs is not None:
        actual_jobs = set(seen_jobs)
        missing = sorted(expected_jobs - actual_jobs)
        unexpected = sorted(actual_jobs - expected_jobs)
        if missing:
            errors.append(f"missing evidence for failed job(s): {', '.join(missing)}")
        if unexpected:
            errors.append(f"evidence contains unexpected job(s): {', '.join(unexpected)}")

    return errors, "\n".join(rendered).rstrip() + "\n"


def expected_jobs_from_summary(path: Path) -> tuple[set[str] | None, str | None]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None, f"summary not found: {path}"
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return None, f"cannot read summary JSON: {exc}"

    try:
        jobs = data["blocking_jobs"]["failed_jobs"]
    except (KeyError, TypeError):
        return None, "summary missing blocking_jobs.failed_jobs"
    if not isinstance(jobs, list):
        return None, "summary blocking_jobs.failed_jobs must be an array"

    names = {
        _text(job.get("name"))
        for job in jobs
        if isinstance(job, dict) and _text(job.get("name"))
    }
    if len(names) != len(jobs):
        return None, "every summary blocking_jobs.failed_jobs entry must have a unique name"
    return names, None


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
    parser.add_argument(
        "--summary",
        type=Path,
        help="Snapshot summary.json; require evidence for every failed blocking job",
    )
    args = parser.parse_args(argv)

    root = args.root or args.document.parent
    expected_jobs = None
    if args.summary:
        expected_jobs, summary_error = expected_jobs_from_summary(args.summary)
        if summary_error:
            print(f"FAIL: {summary_error}")
            return 1
    errors, markdown = validate_and_render(args.document, root, expected_jobs)
    if errors:
        print(f"FAIL: {len(errors)} evidence error(s)")
        for error in errors:
            print(f"  - {error}")
        return 1

    if args.render:
        args.render.write_text(markdown, encoding="utf-8")
        print(f"OK: evidence validated; hydrated report written to {args.render}")
    else:
        print("OK: evidence validated")
    return 0


if __name__ == "__main__":
    sys.exit(main())
