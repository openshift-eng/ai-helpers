"""Download prowjob.json and timeline files for multiple job runs in parallel.

Takes job_name:build_id pairs, downloads prowjob.json to extract the --target,
then finds and downloads e2e-timelines_spyglass_*.json files from GCS.

Each run also reports its initial and target payload. They come from the
prowjob's RELEASE_IMAGE_INITIAL / RELEASE_IMAGE_LATEST env, then from its
release.openshift.io/from-tag and /tag annotations. When the prowjob has
neither (for example ci-operator jobs that build their own release), the
script downloads gather-extra clusterversion.json and reads its update
history. A payload lookup failure is reported as payload_warning and does not
change the exit status.

--gather also downloads gather-extra events.json, configmaps.json,
releaseinfo.json and clusterversion.json into {output-dir}/{build_id}/gather/
for revision_triggers.py and payload_diff.py.

The artifacts live in the public test-platform-results-public bucket. Every
gcloud subprocess is run with CLOUDSDK_AUTH_DISABLE_CREDENTIALS=true so an
expired local login is not refreshed and the user's gcloud config is left
unchanged. That environment is set on each subprocess, including the ones
started from the parallel worker threads.

Usage:
    python3 download_timelines.py \
      --runs "periodic-ci-...-e2e-gcp-upgrade:2084417286357127168,periodic-ci-...-e2e-gcp-ovn-upgrade:2084701838124257280" \
      --output-dir .work/disruption-analysis/2026-08-04 [--gather]

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
import shutil
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

_HERE = os.path.dirname(os.path.abspath(__file__))
# disruption_common is in the disruption plugin's scripts/ directory: two levels
# up when the whole plugin is installed (Claude Code), and inside each skill's
# scripts/ when Chai installs the skill, because it copies the plugin's scripts/
# tree into every skill.
# Search from the skill directory as reached, then from its resolved target,
# since a symlinked skill directory can sit outside the plugin checkout. abspath
# keeps ".." textual, the way sys.path entries resolve it.
_LIB_PARENTS = list(dict.fromkeys(
    os.path.abspath(os.path.join(base, *rel))
    for base in (_HERE, os.path.realpath(_HERE))
    for rel in (("scripts",), ("..", "..", "scripts"))))
for _parent in _LIB_PARENTS:
    if os.path.isfile(os.path.join(_parent, "disruption_common", "__init__.py")):
        sys.path.insert(0, _parent)
        break
else:
    sys.exit("Error: disruption_common library not found. Install the whole disruption plugin; "
             "the library is its scripts/disruption_common. Looked in: %s" % ", ".join(_LIB_PARENTS))

from disruption_common.gcs import (  # noqa: E402
    GCS_BUCKET,
    _matched_nothing,
    run_gcloud,
    download_file,
    extract_target,
    gather_gcs_path,
)

# gather-extra files saved by --gather, relative to artifacts/{target}/gather-extra/artifacts/.
GATHER_FILES = ("events.json", "configmaps.json", "releaseinfo.json", "clusterversion.json")


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


def _prowjob_containers(data):
    return data.get("spec", {}).get("pod_spec", {}).get("containers", []) or []


def extract_payloads(prowjob_path):
    """Initial and target payload from prowjob.json.

    Returns {"initial", "target", "source"}. RELEASE_IMAGE_INITIAL and
    RELEASE_IMAGE_LATEST pullspecs win; the release controller's from-tag and
    tag annotations are the fallback. Missing values are None.
    """
    payloads = {"initial": None, "target": None, "source": None}
    try:
        with open(prowjob_path) as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return payloads
    if not isinstance(data, dict):
        return payloads

    env = {}
    for container in _prowjob_containers(data):
        for var in container.get("env", []) or []:
            if var.get("value"):
                env.setdefault(var.get("name"), var["value"])
    if env.get("RELEASE_IMAGE_INITIAL") or env.get("RELEASE_IMAGE_LATEST"):
        payloads["initial"] = env.get("RELEASE_IMAGE_INITIAL")
        payloads["target"] = env.get("RELEASE_IMAGE_LATEST")
        payloads["source"] = "prowjob-env"
        return payloads

    annotations = data.get("metadata", {}).get("annotations", {}) or {}
    if annotations.get("release.openshift.io/tag"):
        payloads["initial"] = annotations.get("release.openshift.io/from-tag")
        payloads["target"] = annotations["release.openshift.io/tag"]
        payloads["source"] = "prowjob-annotations"
    return payloads


def payloads_from_clusterversion(path):
    """Initial and target version from a gather-extra clusterversion.json.

    status.history is newest first: the last entry is the installed payload
    and the first is the last update target. Returns {"initial", "target",
    "source", "initial_image", "target_image", "target_state"}, with None
    values when the file is missing or has no history.
    """
    payloads = {"initial": None, "target": None, "source": None}
    try:
        with open(path) as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return payloads
    if not isinstance(data, dict):
        return payloads
    items = data.get("items") if data.get("kind") == "List" else [data]
    history = []
    for item in items or []:
        if isinstance(item, dict):
            history = item.get("status", {}).get("history", []) or []
            if history:
                break
    if not history:
        return payloads
    newest, oldest = history[0], history[-1]
    payloads.update({
        "initial": oldest.get("version") or oldest.get("image"),
        "target": newest.get("version") or newest.get("image"),
        "source": "clusterversion-history",
        "initial_image": oldest.get("image"),
        "target_image": newest.get("image"),
        "target_state": newest.get("state"),
    })
    return payloads


def payload_tag(pullspec):
    """Short payload name: the tag of a pullspec, or the value unchanged.

    registry.ci.openshift.org/ocp/release-5:5.1.0-0.nightly-2026-11-09-143447
    becomes 5.1.0-0.nightly-2026-11-09-143447. Digest pullspecs are kept whole.
    """
    if not pullspec:
        return pullspec
    if "@" in pullspec:
        return pullspec
    last = pullspec.rsplit("/", 1)[-1]
    if ":" in last:
        return last.split(":", 1)[1]
    return pullspec


def download_gather_files(job, build_id, target, gather_dir, filenames):
    """Download gather-extra files. Returns (saved_paths, failures)."""
    os.makedirs(gather_dir, exist_ok=True)
    saved, failures = [], []
    for filename in filenames:
        local_path = os.path.join(gather_dir, filename)
        ok, detail = download_file(gather_gcs_path(job, build_id, target, filename), local_path)
        if ok:
            saved.append(local_path)
        else:
            failures.append("%s: %s" % (filename, detail))
    return saved, failures


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


def process_run(job, build_id, output_dir, gather=False):
    """Process a single run: download prowjob.json, find and download timelines.

    Returns a dict with build_id, job, target, timeline_files, initial_payload,
    target_payload, payload_source, and any error. payload_warning, and with
    gather=True gather_files and gather_error, report problems that do not
    affect the exit status.
    """
    result = {
        "build_id": build_id,
        "job": job,
        "target": None,
        "timeline_files": [],
        "initial_payload": None,
        "target_payload": None,
        "payload_source": None,
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

    payloads = extract_payloads(prowjob_local)
    result["initial_payload"] = payloads["initial"]
    result["target_payload"] = payloads["target"]
    result["payload_source"] = payloads["source"]
    # Before the timeline listing, so runs without timelines still get gather files and payloads.
    add_gather_and_payloads(result, job, build_id, target, output_dir, gather)

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


def add_gather_and_payloads(result, job, build_id, target, output_dir, gather):
    """Download gather-extra files when asked, and fill payloads from clusterversion.json.

    clusterversion.json is fetched without --gather only when the prowjob gave
    no target payload.
    """
    gather_dir = os.path.join(output_dir, build_id, "gather")
    need_cv = not result["target_payload"]
    if not target:
        message = "no --target in prowjob.json; cannot locate gather-extra artifacts"
        if gather:
            result["gather_files"] = []
            result["gather_error"] = message
        if need_cv:
            result["payload_warning"] = message
        return
    filenames = list(GATHER_FILES) if gather else (["clusterversion.json"] if need_cv else [])
    if not filenames:
        return
    saved, failures = download_gather_files(job, build_id, target, gather_dir, filenames)
    if gather:
        result["gather_files"] = saved
        result["gather_error"] = "; ".join(failures)[:500] or None
    if need_cv:
        cv_path = os.path.join(gather_dir, "clusterversion.json")
        payloads = payloads_from_clusterversion(cv_path) if cv_path in saved else {}
        if payloads.get("target"):
            result["initial_payload"] = payloads["initial"]
            result["target_payload"] = payloads["target"]
            result["payload_source"] = payloads["source"]
        else:
            result["payload_warning"] = (
                "prowjob.json has no RELEASE_IMAGE_* env or release tag annotations, and "
                "gather-extra clusterversion.json gave no update history")


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
        if r.get("initial_payload") or r.get("target_payload"):
            print("  payloads: %s -> %s (from %s)" % (
                payload_tag(r.get("initial_payload")) or "?",
                payload_tag(r.get("target_payload")) or "?",
                r.get("payload_source")))
        if r.get("payload_warning"):
            print("  payloads: unknown (%s)" % r["payload_warning"])
        for f in r.get("gather_files") or []:
            print("  %s" % f)
        if r.get("gather_error"):
            print("  WARNING: gather-extra: %s" % r["gather_error"])
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
    parser.add_argument("--gather", action="store_true",
                        help="Also download gather-extra %s into {build_id}/gather/"
                        % ", ".join(GATHER_FILES))
    args = parser.parse_args(argv)

    check_gcloud()
    runs = parse_runs(args.runs)
    if not runs:
        print("Error: no valid runs provided", file=sys.stderr)
        sys.exit(1)

    results = []
    with ThreadPoolExecutor(max_workers=min(len(runs), 8)) as executor:
        futures = {
            executor.submit(process_run, job, build_id, args.output_dir, gather=args.gather): (job, build_id)
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
