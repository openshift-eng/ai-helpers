#!/usr/bin/env python3
"""Classify Prow job failures into normalized permafail signatures.

Reads JSON input with failure_urls, job_name, and pr_info fields, fetches Prow
job artifacts from gcsweb, and writes a JSON array of normalized signatures.
"""

import argparse
import hashlib
import html.parser
import json
import re
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Any
from urllib.parse import unquote, urljoin, urlparse

try:
    import requests
except ImportError:
    print("Error: requests is required. Install with: pip install requests", file=sys.stderr)
    sys.exit(1)


GCSWEB_BASE = "https://gcsweb-ci.apps.ci.l2s4.p1.openshiftapps.com/gcs/"
TEST_PATH_PATTERNS = (
    "e2e-",
    "openshift-e2e-test",
    "openshift-tests-",
    "monitor-test-",
)
ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*m")
INFRA_ONLY_PREFIXES = (
    "ipi-install",
    "gather-",
    "pull-ci-",
)


class ArtifactError(RuntimeError):
    """Raised when a job cannot be fetched or classified."""


class LinkParser(html.parser.HTMLParser):
    """Small href extractor for gcsweb directory listings."""

    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        for key, value in attrs:
            if key == "href" and value:
                self.links.append(value)


@dataclass
class ArtifactEntry:
    path: str
    url: str
    is_dir: bool


def fetch_text(session: requests.Session, url: str, timeout: int) -> str:
    try:
        response = session.get(url, timeout=timeout)
        response.raise_for_status()
    except requests.RequestException as e:
        raise ArtifactError(f"failed to fetch {url}: {e}") from e
    return response.text


def parse_gcs_path(prow_url: str) -> str:
    parsed = urlparse(prow_url)
    if parsed.scheme not in ("http", "https"):
        raise ArtifactError(f"invalid Prow URL scheme: {prow_url}")
    marker = "/view/gs/"
    if marker not in parsed.path:
        raise ArtifactError(f"invalid Prow URL, missing /view/gs/: {prow_url}")
    gcs_path = unquote(parsed.path.split(marker, 1)[1]).strip("/")
    parts = gcs_path.split("/")
    if any(part in {".", ".."} for part in parts):
        raise ArtifactError(f"invalid traversal segment in Prow GCS path: {prow_url}")
    if not gcs_path or len(parts) < 3:
        raise ArtifactError(f"invalid Prow GCS path in URL: {prow_url}")
    return gcs_path


def gcsweb_url(gcs_path: str, suffix: str = "") -> str:
    base = urljoin(GCSWEB_BASE, gcs_path.strip("/") + "/")
    return urljoin(base, suffix)


def list_artifacts(
    session: requests.Session,
    artifacts_url: str,
    timeout: int,
    max_depth: int = 4,
    max_entries: int = 500,
) -> list[ArtifactEntry]:
    entries: list[ArtifactEntry] = []
    seen_dirs: set[str] = set()

    def walk(url: str, prefix: str, depth: int) -> None:
        if depth > max_depth or len(entries) >= max_entries or url in seen_dirs:
            return
        seen_dirs.add(url)
        try:
            html = fetch_text(session, url, timeout)
        except ArtifactError:
            if depth == 0:
                raise
            return
        parser = LinkParser()
        parser.feed(html)
        for href in parser.links:
            if len(entries) >= max_entries:
                return
            if href in ("../", "./") or href.startswith("?"):
                continue
            absolute = urljoin(url, href)
            parsed = urlparse(absolute)
            base = urlparse(artifacts_url)
            if (parsed.scheme, parsed.netloc) != (base.scheme, base.netloc):
                continue
            if not parsed.path.startswith(base.path):
                continue
            name = unquote(parsed.path.rstrip("/").rsplit("/", 1)[-1])
            if not name:
                continue
            rel_path = f"{prefix}{name}"
            is_dir = href.endswith("/") or parsed.path.endswith("/")
            if is_dir:
                rel_path = rel_path.rstrip("/") + "/"
            entries.append(ArtifactEntry(rel_path, absolute, is_dir))
            if is_dir and should_descend_artifact_dir(rel_path):
                walk(absolute, rel_path, depth + 1)

    walk(artifacts_url, "", 0)
    return entries


def should_descend_artifact_dir(path: str) -> bool:
    lower = path.lower()
    if is_gather_artifact(lower):
        return False
    if "/pods/" in lower or "/nodes/" in lower:
        return False
    return True


def has_test_artifacts(entries: list[ArtifactEntry], prow_description: str) -> bool:
    for entry in entries:
        path = entry.path.lower()
        if is_gather_artifact(path):
            continue
        if any(pattern in path for pattern in TEST_PATH_PATTERNS):
            return True
        if is_test_junit(path):
            return True
    return "monitortest" in prow_description.lower()


def is_gather_artifact(path: str) -> bool:
    return any(part.startswith("gather-") for part in path.split("/"))


def is_test_junit(path: str) -> bool:
    if "junit" not in path:
        return False
    if not is_test_runner_path(path):
        return False
    if path.endswith("/"):
        return "/junit/" in path
    if not path.endswith(".xml"):
        return False
    if path.endswith("junit_symptoms.xml") or path.endswith("junit_operator.xml"):
        return False
    return True


def is_test_runner_path(path: str) -> bool:
    return any(pattern in path for pattern in TEST_PATH_PATTERNS)


def extract_tests_from_junit(xml_text: str) -> list[str]:
    """Legacy function - kept for compatibility but not used.

    The main logic is now in extract_test_names which aggregates
    across all junit files to properly detect flakes.
    """
    return []


def extract_tests_from_log(log_text: str) -> list[str]:
    tests: list[str] = []
    for line in log_text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("[sig-") or stripped.startswith("FAIL:"):
            tests.append(re.sub(r"^FAIL:\s*", "", stripped))
    return tests


def dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        normalized = " ".join(value.split())
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    return result


def extract_test_names(
    session: requests.Session,
    entries: list[ArtifactEntry],
    timeout: int,
) -> list[str]:
    """Extract test names that failed and never passed across all junit files.

    Aggregates results from all junit files to detect flakes (tests that
    failed in one file but passed in another).
    """
    junit_entries = [
        entry for entry in entries
        if not entry.is_dir
        and not is_gather_artifact(entry.path.lower())
        and is_test_junit(entry.path.lower())
    ]

    # Collect all junit XML content
    junit_xmls: list[str] = []
    for entry in junit_entries[:20]:
        try:
            junit_xmls.append(fetch_text(session, entry.url, timeout))
        except ArtifactError:
            continue

    if not junit_xmls:
        # Fallback to log-based extraction
        log_entries = [
            entry for entry in entries
            if not entry.is_dir
            and entry.path.endswith("build-log.txt")
            and has_test_artifacts([entry], "")
        ]
        tests: list[str] = []
        for entry in log_entries[:10]:
            try:
                tests.extend(extract_tests_from_log(fetch_text(session, entry.url, timeout)))
            except ArtifactError:
                continue
        return dedupe(tests)

    # Aggregate failures and passes across all junit files
    def get_test_name(testcase: ET.Element) -> str:
        classname = testcase.attrib.get("classname", "").strip()
        name = testcase.attrib.get("name", "").strip()
        if classname and name:
            return f"{classname} {name}"
        elif name:
            return name
        elif classname:
            return classname
        return ""

    all_failures: set[str] = set()
    all_passes: set[str] = set()

    for xml_text in junit_xmls:
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError:
            continue

        for testcase in root.iter("testcase"):
            test_name = get_test_name(testcase)
            if not test_name:
                continue

            # Skip informing tests - they don't determine job pass/fail status
            lifecycle = testcase.attrib.get("lifecycle", "")
            if lifecycle == "informing":
                continue

            failed = testcase.find("failure") is not None or testcase.find("error") is not None
            skipped = testcase.find("skipped") is not None
            if failed:
                all_failures.add(test_name)
            elif not skipped:
                all_passes.add(test_name)

    # Only return tests that failed and never passed (real failures, not flakes)
    real_failures = all_failures - all_passes
    return dedupe(sorted(real_failures))


def normalize_error(message: str) -> str:
    normalized = ANSI_ESCAPE_RE.sub("", message)
    normalized = re.sub(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z?", "", normalized)
    normalized = re.sub(
        r"\b\d+\.\d+\.\d+-\d+\.ci-\d{4}-\d{2}-\d{2}-\d{6}-[A-Za-z0-9-]+\b",
        "release-*",
        normalized,
    )
    normalized = re.sub(
        r"\b\d+\.\d+\.\d+-\d+\.nightly-\d{4}-\d{2}-\d{2}-\d{6}\b",
        "release-*",
        normalized,
    )
    normalized = re.sub(r"\bci-op-[A-Za-z0-9-]+\b", "ci-op-*", normalized)
    normalized = re.sub(r"\btest-ci-op-[A-Za-z0-9-]+\b", "test-ci-op-*", normalized)
    normalized = re.sub(r"\bbuild[-_][A-Za-z0-9_.-]+\b", "build-*", normalized)
    normalized = re.sub(r"\bpod[-_][A-Za-z0-9_.-]+\b", "pod-*", normalized)
    normalized = re.sub(r"\b[0-9a-f]{8,}\b", "*", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"\b\d+(?:\.\d+)?\s*(?:m|Mi|Gi|Ki|G|M|cpu|cores?)\b", "*", normalized)
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip(" :-")


def error_hash(error: str) -> str:
    return hashlib.md5(error.encode("utf-8")).hexdigest()


def extract_infra_error(
    session: requests.Session,
    entries: list[ArtifactEntry],
    prow_description: str,
    timeout: int,
) -> str:
    candidates: list[str] = []
    if prow_description and not is_generic_error(prow_description):
        candidates.append(prow_description)
    build_logs = [
        entry for entry in entries
        if not entry.is_dir and entry.path.endswith("build-log.txt")
    ]
    build_logs.sort(key=lambda entry: infra_log_priority(entry.path))
    for entry in build_logs[:8]:
        try:
            text = fetch_text(session, entry.url, timeout)
        except ArtifactError:
            continue
        extracted = extract_error_line(text)
        if extracted:
            candidates.append(extracted)
            break
    for candidate in candidates:
        normalized = normalize_error(candidate[:400])
        if normalized:
            return normalized[:200]
    return "unknown infrastructure failure"


def is_generic_error(message: str) -> bool:
    normalized = message.strip().lower().rstrip(".")
    return normalized in {
        "job failed",
        "the test step failed",
        "build failed",
        "failed",
        "failure",
    }


def infra_log_priority(path: str) -> tuple[int, str]:
    lower = path.lower()
    if any(prefix in lower for prefix in INFRA_ONLY_PREFIXES):
        return (0, path)
    if "install" in lower or "setup" in lower:
        return (1, path)
    if "gather" in lower:
        return (3, path)
    return (2, path)


def extract_error_line(log_text: str) -> str:
    patterns = (
        re.compile(r"\b(error|failed|failure|timeout|timed out|exceeded|denied)\b", re.IGNORECASE),
    )
    candidates: list[str] = []
    for line in reversed(log_text.splitlines()[-300:]):
        stripped = ANSI_ESCAPE_RE.sub("", line).strip()
        if not stripped:
            continue
        if "Reporting job state" in stripped:
            continue
        if any(pattern.search(stripped) for pattern in patterns):
            candidates.append(stripped)
    if not candidates:
        return ""

    priority_patterns = (
        re.compile(r"failed to initialize the cluster", re.IGNORECASE),
        re.compile(r"unable to import .*release image", re.IGNORECASE),
        re.compile(r"cluster operator .*degraded", re.IGNORECASE),
        re.compile(r"\* could not run steps", re.IGNORECASE),
        re.compile(r"suite run returned error", re.IGNORECASE),
        re.compile(r"error running a test suite", re.IGNORECASE),
    )
    for priority in priority_patterns:
        for candidate in candidates:
            if priority.search(candidate):
                return candidate
    return candidates[0]


def validate_input(data: dict[str, Any]) -> None:
    urls = data.get("failure_urls")
    if not isinstance(urls, list) or not 2 <= len(urls) <= 10:
        raise ArtifactError("failure_urls must be an array with 2-10 URLs")
    if not all(isinstance(url, str) for url in urls):
        raise ArtifactError("failure_urls must contain only strings")
    if not isinstance(data.get("job_name"), str) or not data["job_name"].strip():
        raise ArtifactError("job_name must be a non-empty string")
    if not isinstance(data.get("pr_info"), dict):
        raise ArtifactError("pr_info must be an object")


def classify_job(
    session: requests.Session,
    prow_url: str,
    expected_job_name: str,
    timeout: int,
) -> dict[str, Any]:
    gcs_path = parse_gcs_path(prow_url)
    prowjob = json.loads(fetch_text(session, gcsweb_url(gcs_path, "prowjob.json"), timeout))
    spec = prowjob.get("spec") or {}
    metadata = prowjob.get("metadata") or {}
    actual_job_name = spec.get("job") or metadata.get("name", "")
    if actual_job_name and actual_job_name != expected_job_name and expected_job_name not in gcs_path:
        raise ArtifactError(
            f"job name mismatch for {prow_url}: expected {expected_job_name}, found {actual_job_name}"
        )

    status = prowjob.get("status") or {}
    description = status.get("description", "") or ""
    artifacts_url = gcsweb_url(gcs_path, "artifacts/")
    entries = list_artifacts(session, artifacts_url, timeout)
    if has_test_artifacts(entries, description):
        tests = extract_test_names(session, entries, timeout)
        if tests:
            return {
                "type": "test_failure",
                "url": prow_url,
                "tests": tests,
                "test_count": len(tests),
            }

    root_entries = [
        ArtifactEntry("build-log.txt", gcsweb_url(gcs_path, "build-log.txt"), False),
        ArtifactEntry("finished.json", gcsweb_url(gcs_path, "finished.json"), False),
    ]
    error = extract_infra_error(session, root_entries + entries, description, timeout)
    return {
        "type": "infra_failure",
        "url": prow_url,
        "error": error,
        "error_hash": error_hash(error),
    }


def load_input(json_input: str | None) -> dict[str, Any]:
    raw = json_input if json_input is not None else sys.stdin.read()
    if not raw.strip():
        raise ArtifactError("no JSON input provided")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ArtifactError(f"invalid JSON input: {e}") from e
    if not isinstance(data, dict):
        raise ArtifactError("input must be a JSON object")
    return data


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Classify consecutive Prow job failures into permafail signatures."
    )
    parser.add_argument(
        "--json-input",
        help="JSON object containing failure_urls, job_name, and pr_info. Reads stdin if omitted.",
    )
    parser.add_argument("--timeout", type=int, default=30, help="HTTP timeout in seconds.")
    args = parser.parse_args()

    try:
        data = load_input(args.json_input)
        validate_input(data)
        session = requests.Session()
        signatures = [
            classify_job(session, url, data["job_name"], args.timeout)
            for url in data["failure_urls"]
        ]
    except (ArtifactError, requests.RequestException, json.JSONDecodeError) as e:
        print(json.dumps({"success": False, "error": str(e)}, indent=2), file=sys.stderr)
        return 1

    print(json.dumps(signatures, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
