"""Download prowjob.json and timeline files for multiple job runs in parallel.

Takes job_name:build_id pairs, downloads prowjob.json to extract the --target,
then finds and downloads e2e-timelines_spyglass_*.json files from GCS.

The artifacts live in the public test-platform-results-public bucket. Every
gcloud subprocess is run with CLOUDSDK_AUTH_DISABLE_CREDENTIALS=true so an
expired local login is not refreshed and the user's gcloud config is left
unchanged. That environment is set on each subprocess, including the ones
started from the parallel worker threads.

Usage:
    python3 download_timelines.py \
      --runs "periodic-ci-...-e2e-gcp-upgrade:2084417286357127168,periodic-ci-...-e2e-gcp-ovn-upgrade:2084701838124257280" \
      --output-dir .work/disruption-analysis/2026-08-04

Output formats:
    --format text   (default) Human-readable summary with downloaded file paths
    --format json   Machine-readable JSON array

Exit status:
    0  every run downloaded its timeline files
    2  at least one timeline file downloaded, and at least one run or file failed
    1  no timeline file downloaded
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

GCS_BUCKET = "test-platform-results-public"
GCLOUD_TIMEOUT_SECONDS = 120

# Values that look like credentials. The reauthentication message gcloud prints
# for an expired login does not match these and is kept.
_SECRET_PATTERNS = (
    re.compile(r"(?i)\b(?:proxy-)?authorization\s*:.*", re.MULTILINE),
    re.compile(r"ya29\.[A-Za-z0-9_\-]+"),
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9_\-\.]+"),
    re.compile(r"(?i)\b(authorization|refresh_token|access_token|id_token|client_secret)\b\s*[=:]\s*\S+"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.DOTALL),
)


def check_gcloud():
    """Verify gcloud CLI is available."""
    if not shutil.which("gcloud"):
        print("Error: gcloud CLI not found. Install it from https://cloud.google.com/sdk/docs/install", file=sys.stderr)
        sys.exit(1)


def parse_runs(runs_str):
    """Parse comma-separated job_name:build_id pairs."""
    runs = []
    for pair in runs_str.split(","):
        pair = pair.strip()
        if not pair:
            continue
        if ":" not in pair:
            print("Error: invalid run format %r — expected job_name:build_id" % pair, file=sys.stderr)
            sys.exit(1)
        job, build_id = pair.rsplit(":", 1)
        if not job or not build_id:
            print("Error: empty job or build_id in %r" % pair, file=sys.stderr)
            sys.exit(1)
        if os.sep in build_id or "/" in build_id or build_id.startswith("."):
            print("Error: invalid build_id in %r" % pair, file=sys.stderr)
            sys.exit(1)
        runs.append((job, build_id))
    return runs


def gcloud_env():
    """Environment for one gcloud subprocess.

    Copies the current environment and disables credential lookup for that
    process only. os.environ and the gcloud config files are not modified.
    """
    env = os.environ.copy()
    env["CLOUDSDK_AUTH_DISABLE_CREDENTIALS"] = "true"
    return env


def sanitize_process_output(text):
    """Collapse process output into one line with credential-like values removed."""
    if not text:
        return ""
    cleaned = str(text)
    for pattern in _SECRET_PATTERNS:
        cleaned = pattern.sub("[redacted]", cleaned)
    lines = [line.strip() for line in cleaned.splitlines() if line.strip()]
    message = " ".join(lines)
    if len(message) > 500:
        message = message[:500].rstrip() + "..."
    return message


def _matched_nothing(stdout, stderr):
    """True when gcloud ls failed because the pattern matched no objects."""
    blob = ((stdout or "") + "\n" + (stderr or "")).lower()
    return "matched no objects" in blob or "matched no files" in blob


def _failure_detail(result, command_name):
    """Human-readable reason for a non-zero gcloud exit, without credentials."""
    parts = []
    for chunk in (getattr(result, "stderr", None), getattr(result, "stdout", None)):
        text = sanitize_process_output(chunk or "")
        if text and text not in parts:
            parts.append(text)
    if parts:
        return " ".join(parts)
    return "%s exited %s" % (command_name, result.returncode)


def run_gcloud(args, timeout=GCLOUD_TIMEOUT_SECONDS):
    """Run gcloud anonymously.

    Returns (result, error). result is the CompletedProcess on a finished
    process, or None when the process timed out or could not be started.
    error is None when returncode is 0.
    """
    command_name = " ".join(args[:3]) if len(args) >= 3 else "gcloud"
    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=gcloud_env(),
        )
    except subprocess.TimeoutExpired:
        return None, "timed out after %ds" % timeout
    except OSError as exc:
        detail = exc.strerror or "unknown error"
        return None, "failed to start gcloud: %s" % detail
    if result.returncode != 0:
        return result, _failure_detail(result, command_name)
    return result, None


def download_file(gcs_path, local_path):
    """Download a single file from GCS.

    Returns (ok, error). error is None on success and otherwise a short
    diagnostic safe to print.
    """
    _result, error = run_gcloud(
        ["gcloud", "storage", "cp", gcs_path, local_path, "--no-user-output-enabled"])
    return error is None, error


def extract_target(prowjob_path):
    """Extract --target= value from prowjob.json."""
    try:
        with open(prowjob_path) as f:
            data = json.load(f)
        args = data.get("spec", {}).get("pod_spec", {}).get("containers", [{}])[0].get("args", [])
        for arg in args:
            if arg.startswith("--target="):
                return arg[len("--target="):]
    except (json.JSONDecodeError, IndexError, KeyError, OSError):
        pass
    return None


def list_timeline_files(job, build_id):
    """List e2e-timelines_spyglass_*.json files in GCS for a job run.

    Returns (paths, error). error is None when the listing command succeeded,
    including when it matched nothing. A command, auth, network, timeout, or
    launch failure sets error and returns no paths.
    """
    gcs_pattern = "gs://%s/logs/%s/%s/artifacts/**/e2e-timelines_spyglass_*.json" % (
        GCS_BUCKET, job, build_id)
    result, error = run_gcloud(["gcloud", "storage", "ls", gcs_pattern])
    if error is None:
        stdout = result.stdout if result is not None else ""
        return [line.strip() for line in (stdout or "").split("\n") if line.strip()], None
    stdout = result.stdout if result is not None else ""
    stderr = result.stderr if result is not None else ""
    if result is not None and _matched_nothing(stdout, stderr):
        return [], None
    return [], error


def process_run(job, build_id, output_dir):
    """Process a single run: download prowjob.json, find and download timelines.

    Returns a dict with build_id, job, target, timeline_files, and any error.
    """
    result = {
        "build_id": build_id,
        "job": job,
        "target": None,
        "timeline_files": [],
        "error": None,
    }

    logs_dir = os.path.join(output_dir, build_id, "logs")
    os.makedirs(logs_dir, exist_ok=True)

    prowjob_local = os.path.join(logs_dir, "prowjob.json")
    prowjob_gcs = "gs://%s/logs/%s/%s/prowjob.json" % (GCS_BUCKET, job, build_id)

    ok, detail = download_file(prowjob_gcs, prowjob_local)
    if not ok:
        result["error"] = "failed to download prowjob.json: %s" % detail
        return result

    target = extract_target(prowjob_local)
    result["target"] = target

    gcs_files, list_error = list_timeline_files(job, build_id)
    if list_error:
        result["error"] = "failed to list timeline files: %s" % list_error
        return result
    if not gcs_files:
        result["error"] = "no timeline files found"
        return result

    failures = []
    for gcs_path in gcs_files:
        filename = os.path.basename(gcs_path)
        local_path = os.path.join(logs_dir, filename)
        file_ok, file_detail = download_file(gcs_path, local_path)
        if file_ok:
            result["timeline_files"].append(local_path)
        else:
            failures.append("%s: %s" % (filename, file_detail))

    if failures:
        summary = "; ".join(failures)
        if len(summary) > 500:
            summary = summary[:500].rstrip() + "..."
        if not result["timeline_files"]:
            result["error"] = "all %d timeline file downloads failed: %s" % (len(gcs_files), summary)
        else:
            result["error"] = "%d of %d timeline file downloads failed: %s" % (
                len(failures), len(gcs_files), summary)

    return result


def print_text(results):
    """Print human-readable summary."""
    for r in results:
        target_str = "target=%s" % r["target"] if r["target"] else "target=unknown"
        if r["error"] and not r["timeline_files"]:
            print("%s: %s — ERROR: %s" % (r["build_id"], target_str, r["error"]))
        else:
            print("%s: %s" % (r["build_id"], target_str))
            for f in r["timeline_files"]:
                print("  %s" % f)
            if r["error"]:
                print("  WARNING: %s" % r["error"])
        print()


def print_json(results):
    """Print machine-readable JSON."""
    print(json.dumps(results, indent=2))


def exit_code(results):
    """0 when every run succeeded, 2 on partial success, 1 when nothing was downloaded.

    A run counts as downloaded when at least one timeline file was saved.
    Partial file failures on an otherwise downloaded run are still partial success.
    """
    any_error = any(r.get("error") for r in results)
    any_files = any(r.get("timeline_files") for r in results)
    if not any_error:
        return 0
    if any_files:
        return 2
    return 1


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Download prowjob.json and timeline files for multiple job runs")
    parser.add_argument("--runs", required=True,
                        help="Comma-separated job_name:build_id pairs")
    parser.add_argument("--output-dir", required=True,
                        help="Base output directory")
    parser.add_argument("--format", choices=["text", "json"], default="text",
                        help="Output format (default: text)")
    args = parser.parse_args(argv)

    check_gcloud()
    runs = parse_runs(args.runs)
    if not runs:
        print("Error: no valid runs provided", file=sys.stderr)
        sys.exit(1)

    results = []
    with ThreadPoolExecutor(max_workers=min(len(runs), 8)) as executor:
        futures = {
            executor.submit(process_run, job, build_id, args.output_dir): (job, build_id)
            for job, build_id in runs
        }
        for future in as_completed(futures):
            try:
                results.append(future.result())
            except Exception as exc:
                job, build_id = futures[future]
                results.append({
                    "build_id": build_id, "job": job, "target": None,
                    "timeline_files": [], "error": str(exc),
                })

    results.sort(key=lambda r: r["build_id"])

    if args.format == "json":
        print_json(results)
    else:
        print_text(results)

    code = exit_code(results)
    if code == 1:
        print("Error: no timeline files downloaded (%d runs)." % len(results), file=sys.stderr)
    elif code == 2:
        downloaded = sum(1 for r in results if r.get("timeline_files"))
        print("Warning: timelines downloaded for %d of %d runs." % (downloaded, len(results)),
              file=sys.stderr)
    if code:
        sys.exit(code)


if __name__ == "__main__":
    main()
