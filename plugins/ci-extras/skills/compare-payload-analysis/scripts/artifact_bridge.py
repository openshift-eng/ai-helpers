#!/usr/bin/env python3
"""Enforce CI Extras' blind stage/unseal boundary for payload-agent artifacts."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any


ASYNC_JOB_NAME = "claude-payload-agent"
PHASE_STAGED = "staged"
PHASE_UNSEALED = "unsealed"
TAG_RE = re.compile(
    r"^(?P<stream_name>(?P<version>\d+\.\d+)\.0-0\."
    r"(?P<stream>[\w-]+?)(?:-(?P<arch>arm64|ppc64le|s390x|multi))?)"
    r"-(?P<timestamp>\d{4}-\d{2}-\d{2}-\d{6})$"
)


class BridgeError(RuntimeError):
    """A user-actionable staging or unsealing failure."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_tag(tag: str) -> dict[str, str]:
    match = TAG_RE.fullmatch(tag)
    if not match:
        raise BridgeError(f"Cannot parse payload tag: {tag}")
    values = match.groupdict()
    return {
        "stream_name": values["stream_name"],
        "version": values["version"],
        "stream": values["stream"],
        "architecture": values["arch"] or "amd64",
    }


def sanitize_tag(tag: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "-", tag).strip("-")


def default_work_dir(tag: str) -> Path:
    return Path(".work") / "compare-payload-analysis" / sanitize_tag(tag)


def release_api_url(tag: str) -> str:
    parsed = parse_tag(tag)
    product = "origin" if parsed["stream"].startswith("okd") else "ocp"
    host = f"{parsed['architecture']}.{product}.releases.ci.openshift.org"
    stream = urllib.parse.quote(parsed["stream_name"], safe="")
    encoded_tag = urllib.parse.quote(tag, safe="")
    return f"https://{host}/api/v1/releasestream/{stream}/release/{encoded_tag}"


def fetch_json(url: str) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        raise BridgeError(f"Could not read release metadata from {url}: {exc}") from exc


def discover_job_url(tag: str) -> str:
    payload = fetch_json(release_api_url(tag))
    async_jobs = payload.get("results", {}).get("asyncJobs")
    if not isinstance(async_jobs, dict):
        async_jobs = payload.get("asyncJobs", {})
    job = async_jobs.get(ASYNC_JOB_NAME) if isinstance(async_jobs, dict) else None
    if not isinstance(job, dict):
        raise BridgeError(
            f"No {ASYNC_JOB_NAME!r} async job is recorded for payload {tag}"
        )
    if job.get("state") != "Succeeded":
        raise BridgeError(
            f"{ASYNC_JOB_NAME} is {job.get('state', 'unknown')}, not Succeeded"
        )
    url = job.get("url")
    if not isinstance(url, str) or not url:
        raise BridgeError(f"{ASYNC_JOB_NAME} has no Prow URL")
    return url


def prow_to_gs_prefix(url: str) -> str:
    marker = "/view/gs/"
    if marker in url:
        suffix = url.split(marker, 1)[1].strip("/")
        return f"gs://{suffix}"
    if url.startswith("gs://"):
        return url.rstrip("/")
    raise BridgeError("Other job URL must be a Prow /view/gs/ URL or a gs:// prefix")


def run_gcloud(arguments: list[str]) -> str:
    if shutil.which("gcloud") is None:
        raise BridgeError("gcloud is required to access the public CI artifacts")
    command = ["gcloud", "storage", *arguments]
    process = subprocess.run(command, text=True, capture_output=True, check=False)
    if process.returncode != 0:
        detail = process.stderr.strip() or process.stdout.strip()
        raise BridgeError(f"{' '.join(command)} failed: {detail}")
    return process.stdout


def list_artifacts(prefix: str) -> list[str]:
    output = run_gcloud(["ls", "--recursive", f"{prefix}/**"])
    return [line.strip() for line in output.splitlines() if line.startswith("gs://")]


def select_artifacts(uris: list[str], tag: str) -> tuple[str, str]:
    snapshot_names = {
        f"snapshot-{tag}.tar",
        f"snapshot-{tag}.tar.gz",
        f"snapshot-{tag}.tgz",
    }
    report_name = f"payload-analysis-{tag}-summary.html"
    snapshots = [uri for uri in uris if PurePosixPath(uri).name in snapshot_names]
    reports = [uri for uri in uris if PurePosixPath(uri).name == report_name]
    if len(snapshots) != 1:
        raise BridgeError(
            f"Expected one snapshot archive for {tag}, found {len(snapshots)}"
        )
    if len(reports) != 1:
        raise BridgeError(
            f"Expected one sealed HTML report for {tag}, found {len(reports)}"
        )
    return snapshots[0], reports[0]


def safe_member_path(name: str) -> PurePosixPath:
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts:
        raise BridgeError(f"Unsafe archive path: {name}")
    if path.suffix.lower() in {".html", ".htm"}:
        raise BridgeError(
            f"Snapshot archive contains HTML and cannot stay blind: {name}"
        )
    return path


def extract_snapshot(archive: Path, destination: Path) -> None:
    if destination.exists() and any(destination.iterdir()):
        raise BridgeError(f"Snapshot destination is not empty: {destination}")
    destination.mkdir(parents=True, exist_ok=True)
    destination_root = destination.resolve()
    with tarfile.open(archive, mode="r:*") as bundle:
        for member in bundle.getmembers():
            relative = safe_member_path(member.name)
            target = (destination / Path(*relative.parts)).resolve()
            if os.path.commonpath((destination_root, target)) != str(destination_root):
                raise BridgeError(f"Archive member escapes destination: {member.name}")
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            if not member.isfile():
                raise BridgeError(
                    f"Snapshot archive contains unsupported member: {member.name}"
                )
            target.parent.mkdir(parents=True, exist_ok=True)
            source = bundle.extractfile(member)
            if source is None:
                raise BridgeError(f"Could not read archive member: {member.name}")
            with source, target.open("wb") as output:
                shutil.copyfileobj(source, output)


def find_snapshot_dir(root: Path, tag: str) -> Path:
    matches: list[Path] = []
    for summary in root.rglob("summary.json"):
        try:
            data = json.loads(summary.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if data.get("payload_tag") == tag:
            matches.append(summary.parent.resolve())
    if len(matches) != 1:
        raise BridgeError(f"Expected one summary.json for {tag}, found {len(matches)}")
    return matches[0]


def atomic_write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


def load_manifest(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise BridgeError(f"Blind-state manifest not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise BridgeError(f"Blind-state manifest is invalid: {path}") from exc


def hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def expected_independent_names(tag: str) -> dict[str, str]:
    safe_tag = sanitize_tag(tag)
    return {
        "html": f"payload-analysis-{safe_tag}-summary.html",
        "json": f"payload-analysis-{safe_tag}-autodl.json",
        "yaml": f"payload-results-{safe_tag}.yaml",
    }


def validate_independent_outputs(
    tag: str,
    html: Path,
    autodl_json: Path,
    results_yaml: Path,
    independent_root: Path,
    staged_at: str,
) -> dict[str, dict[str, Any]]:
    paths = {"html": html, "json": autodl_json, "yaml": results_yaml}
    expected = expected_independent_names(tag)
    try:
        staged_timestamp = datetime.fromisoformat(staged_at).timestamp()
    except (TypeError, ValueError) as exc:
        raise BridgeError("Manifest has an invalid staged_at timestamp") from exc
    frozen: dict[str, dict[str, Any]] = {}
    for kind, path in paths.items():
        resolved = path.resolve()
        if not resolved.is_relative_to(independent_root):
            raise BridgeError(
                f"Independent {kind} must be under {independent_root}, got {resolved}"
            )
        if resolved.name != expected[kind]:
            raise BridgeError(
                f"Independent {kind} must be named {expected[kind]}, got {resolved.name}"
            )
        if not resolved.is_file() or resolved.stat().st_size == 0:
            raise BridgeError(f"Independent {kind} is missing or empty: {resolved}")
        if resolved.stat().st_mtime < staged_timestamp:
            raise BridgeError(
                f"Independent {kind} predates snapshot staging: {resolved}"
            )
        frozen[kind] = {
            "path": str(resolved),
            "bytes": resolved.stat().st_size,
            "modified_at": datetime.fromtimestamp(
                resolved.stat().st_mtime, timezone.utc
            ).isoformat(),
            "sha256": hash_file(resolved),
        }
    return frozen


def stage(args: argparse.Namespace) -> dict[str, Any]:
    work_dir = args.work_dir.resolve()
    manifest_path = work_dir / "blind-state.json"
    if manifest_path.exists():
        manifest = load_manifest(manifest_path)
        if manifest.get("payload_tag") != args.payload_tag:
            raise BridgeError("Existing manifest belongs to another payload")
        if manifest.get("phase") in {PHASE_STAGED, PHASE_UNSEALED}:
            return {
                "manifest": str(manifest_path),
                "phase": manifest["phase"],
                "snapshot_dir": manifest["snapshot_dir"],
            }
        raise BridgeError(f"Unexpected manifest phase: {manifest.get('phase')}")

    job_url = args.job_url or discover_job_url(args.payload_tag)
    prefix = prow_to_gs_prefix(job_url)
    snapshot_uri, sealed_report_uri = select_artifacts(
        list_artifacts(prefix), args.payload_tag
    )

    work_dir.mkdir(parents=True, exist_ok=True)
    archive_name = PurePosixPath(snapshot_uri).name
    archive_path = work_dir / archive_name
    run_gcloud(["cp", snapshot_uri, str(archive_path)])
    snapshot_extract_root = work_dir / "snapshot"
    if snapshot_extract_root.exists():
        raise BridgeError(
            f"Snapshot destination already exists without a manifest: "
            f"{snapshot_extract_root}"
        )
    with tempfile.TemporaryDirectory(dir=work_dir) as temporary:
        temporary_root = Path(temporary) / "snapshot"
        extract_snapshot(archive_path, temporary_root)
        relative_snapshot_dir = find_snapshot_dir(
            temporary_root, args.payload_tag
        ).relative_to(temporary_root.resolve())
        temporary_root.replace(snapshot_extract_root)
    snapshot_dir = (snapshot_extract_root / relative_snapshot_dir).resolve()

    manifest = {
        "schema_version": 1,
        "payload_tag": args.payload_tag,
        "phase": PHASE_STAGED,
        "staged_at": utc_now(),
        "other_job_url": job_url,
        "artifact_prefix": prefix,
        "snapshot_uri": snapshot_uri,
        "snapshot_archive": str(archive_path.resolve()),
        "snapshot_dir": str(snapshot_dir),
        "sealed_report_uri": sealed_report_uri,
        "other_report": None,
        "independent_outputs": None,
    }
    atomic_write_json(manifest_path, manifest)
    return {
        "manifest": str(manifest_path.resolve()),
        "phase": PHASE_STAGED,
        "snapshot_dir": str(snapshot_dir),
    }


def unseal(args: argparse.Namespace) -> dict[str, Any]:
    work_dir = args.work_dir.resolve()
    manifest_path = work_dir / "blind-state.json"
    manifest = load_manifest(manifest_path)
    if manifest.get("payload_tag") != args.payload_tag:
        raise BridgeError("Blind-state manifest belongs to another payload")
    if manifest.get("phase") == PHASE_UNSEALED:
        return {
            "manifest": str(manifest_path),
            "phase": PHASE_UNSEALED,
            "other_report": manifest["other_report"],
            "independent_outputs": manifest["independent_outputs"],
        }
    if manifest.get("phase") != PHASE_STAGED:
        raise BridgeError(f"Cannot unseal from phase {manifest.get('phase')!r}")

    independent_root = (work_dir / "independent").resolve()
    frozen = validate_independent_outputs(
        args.payload_tag,
        args.independent_html,
        args.independent_json,
        args.independent_yaml,
        independent_root,
        manifest.get("staged_at"),
    )
    report_uri = manifest.get("sealed_report_uri")
    if not isinstance(report_uri, str) or not report_uri.endswith(".html"):
        raise BridgeError("Manifest does not contain a sealed HTML report URI")
    report_path = work_dir / f"other-agent-{PurePosixPath(report_uri).name}"
    run_gcloud(["cp", report_uri, str(report_path)])
    if not report_path.is_file() or report_path.stat().st_size == 0:
        raise BridgeError(f"Downloaded other report is empty: {report_path}")

    manifest.update(
        {
            "phase": PHASE_UNSEALED,
            "unsealed_at": utc_now(),
            "independent_outputs": frozen,
            "other_report": {
                "path": str(report_path.resolve()),
                "bytes": report_path.stat().st_size,
                "sha256": hash_file(report_path),
                "source_uri": report_uri,
            },
        }
    )
    atomic_write_json(manifest_path, manifest)
    return {
        "manifest": str(manifest_path),
        "phase": PHASE_UNSEALED,
        "other_report": manifest["other_report"],
        "independent_outputs": frozen,
    }


def self_test() -> dict[str, Any]:
    tag = "5.0.0-0.ci-2026-07-30-113831"
    parsed = parse_tag(tag)
    assert parsed["architecture"] == "amd64"
    assert parsed["stream_name"] == "5.0.0-0.ci"
    arm = parse_tag("4.22.0-0.nightly-arm64-2026-07-30-113831")
    assert arm["architecture"] == "arm64"
    assert arm["stream"] == "nightly"
    assert (
        prow_to_gs_prefix("https://prow.ci.openshift.org/view/gs/bucket/logs/job/123")
        == "gs://bucket/logs/job/123"
    )
    snapshot, report = select_artifacts(
        [
            f"gs://bucket/path/snapshot-{tag}.tar",
            f"gs://bucket/path/payload-analysis-{tag}-summary.html",
        ],
        tag,
    )
    assert snapshot.endswith(".tar")
    assert report.endswith(".html")

    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        archive = root / "snapshot.tar"
        summary = json.dumps({"payload_tag": tag}).encode()
        with tarfile.open(archive, "w") as bundle:
            info = tarfile.TarInfo("5.0/ci/summary.json")
            info.size = len(summary)
            bundle.addfile(info, io.BytesIO(summary))
        destination = root / "out"
        extract_snapshot(archive, destination)
        assert find_snapshot_dir(destination, tag) == (destination / "5.0/ci").resolve()

        independent_root = root / "independent"
        independent_root.mkdir()
        expected = expected_independent_names(tag)
        outputs = {}
        for kind, name in expected.items():
            output = independent_root / name
            output.write_text(f"{kind} output", encoding="utf-8")
            outputs[kind] = output
        frozen = validate_independent_outputs(
            tag,
            outputs["html"],
            outputs["json"],
            outputs["yaml"],
            independent_root.resolve(),
            datetime.fromtimestamp(0, timezone.utc).isoformat(),
        )
        assert all(len(item["sha256"]) == 64 for item in frozen.values())

        bad_archive = root / "bad.tar"
        with tarfile.open(bad_archive, "w") as bundle:
            info = tarfile.TarInfo("../findings.html")
            info.size = 0
            bundle.addfile(info, io.BytesIO())
        try:
            extract_snapshot(bad_archive, root / "bad-out")
        except BridgeError:
            pass
        else:
            raise AssertionError("unsafe archive was accepted")
    return {"self_test": "passed"}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Blindly stage a payload snapshot, then unseal the other report"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    stage_parser = subparsers.add_parser(
        "stage", help="Download only the other agent's snapshot"
    )
    stage_parser.add_argument("payload_tag")
    stage_parser.add_argument("--job-url")
    stage_parser.add_argument("--work-dir", type=Path)

    unseal_parser = subparsers.add_parser(
        "unseal", help="Freeze independent outputs and download the other report"
    )
    unseal_parser.add_argument("payload_tag")
    unseal_parser.add_argument("--work-dir", type=Path)
    unseal_parser.add_argument("--independent-html", type=Path, required=True)
    unseal_parser.add_argument("--independent-json", type=Path, required=True)
    unseal_parser.add_argument("--independent-yaml", type=Path, required=True)

    subparsers.add_parser("self-test", help="Run offline safety checks")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        if args.command == "self-test":
            result = self_test()
        else:
            if args.work_dir is None:
                args.work_dir = default_work_dir(args.payload_tag)
            result = stage(args) if args.command == "stage" else unseal(args)
    except BridgeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
