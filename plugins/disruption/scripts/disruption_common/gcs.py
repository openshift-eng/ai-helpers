"""Anonymous reads from the public CI results bucket.

gcloud runs with credential lookup disabled for that process only, and any
diagnostic it prints has credential-like values removed before it is shown.
"""
import json
import os
import re
import subprocess

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


def gather_gcs_path(job, build_id, target, filename):
    return "gs://%s/logs/%s/%s/artifacts/%s/gather-extra/artifacts/%s" % (
        GCS_BUCKET, job, build_id, target, filename)
