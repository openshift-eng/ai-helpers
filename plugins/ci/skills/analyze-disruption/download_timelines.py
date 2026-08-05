"""Download prowjob.json and timeline files for multiple job runs in parallel.

Takes job_name:build_id pairs, downloads prowjob.json to extract the --target,
then finds and downloads e2e-timelines_spyglass_*.json files from GCS.

Usage:
    python3 download_timelines.py \
      --runs "periodic-ci-...-e2e-gcp-upgrade:2084417286357127168,periodic-ci-...-e2e-gcp-ovn-upgrade:2084701838124257280" \
      --output-dir .work/disruption-analysis/2026-08-04

Output formats:
    --format text   (default) Human-readable summary with downloaded file paths
    --format json   Machine-readable JSON array
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

GCS_BUCKET = "test-platform-results"


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
        runs.append((job, build_id))
    return runs


def download_file(gcs_path, local_path):
    """Download a single file from GCS. Returns True on success."""
    try:
        result = subprocess.run(
            ["gcloud", "storage", "cp", gcs_path, local_path, "--no-user-output-enabled"],
            capture_output=True, text=True, timeout=120,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, OSError):
        return False


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
    """List e2e-timelines_spyglass_*.json files in GCS for a job run."""
    gcs_pattern = "gs://%s/logs/%s/%s/artifacts/**/e2e-timelines_spyglass_*.json" % (
        GCS_BUCKET, job, build_id)
    try:
        result = subprocess.run(
            ["gcloud", "storage", "ls", gcs_pattern],
            capture_output=True, text=True, timeout=120,
        )
    except (subprocess.TimeoutExpired, OSError):
        return []
    if result.returncode != 0:
        return []
    return [line.strip() for line in result.stdout.strip().split("\n") if line.strip()]


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

    if not download_file(prowjob_gcs, prowjob_local):
        result["error"] = "failed to download prowjob.json"
        return result

    target = extract_target(prowjob_local)
    result["target"] = target

    gcs_files = list_timeline_files(job, build_id)
    if not gcs_files:
        result["error"] = "no timeline files found"
        return result

    failed_count = 0
    for gcs_path in gcs_files:
        filename = os.path.basename(gcs_path)
        local_path = os.path.join(logs_dir, filename)
        if download_file(gcs_path, local_path):
            result["timeline_files"].append(local_path)
        else:
            failed_count += 1

    if not result["timeline_files"]:
        result["error"] = "all %d timeline file downloads failed" % len(gcs_files)
    elif failed_count:
        result["error"] = "%d of %d timeline file downloads failed" % (failed_count, len(gcs_files))

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


if __name__ == "__main__":
    main()
