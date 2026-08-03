#!/usr/bin/env python3
"""Snapshot OpenShift payload data to a local directory for offline analysis.

Downloads release controller data, PR diffs, comments, and CI job links
for a payload and its predecessors, building a complete local archive
that an AI agent can navigate without live API calls.
"""

import argparse
import gzip
import io
import json
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

KNOWN_ARCHITECTURES = ("amd64", "arm64", "ppc64le", "s390x", "multi")
STREAM_TYPES = ("nightly", "ci")

GCSWEB_BASE = "https://gcsweb-ci.apps.ci.l2s4.p1.openshiftapps.com/gcs"
PROW_VIEW_PREFIX = "https://prow.ci.openshift.org/view/gs/"

PROW_STATE_MAP = {
    "success": "Succeeded",
    "failure": "Failed",
    "aborted": "Failed",
    "error": "Failed",
}

FALLBACK_FETCH_ERRORS = (
    urllib.error.HTTPError,
    urllib.error.URLError,
    json.JSONDecodeError,
    TimeoutError,
    SystemExit,
)


# ---------------------------------------------------------------------------
# PayloadTag — immutable value object for parsed payload tags
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PayloadTag:
    """Parsed representation of an OpenShift payload tag.

    Example tags:
        4.22.0-0.nightly-2026-02-25-152806              -> amd64, OCP
        4.22.0-0.nightly-arm64-2026-02-25-152806        -> arm64, OCP
        4.18.0-0.ci-2026-01-15-114134                   -> amd64, OCP ci stream
        4.22.0-0.okd-scos-nightly-2026-06-10-015300     -> amd64, OKD SCOS nightly
        4.22.0-0.okd-scos-2026-06-10-003203             -> amd64, OKD SCOS ci stream
    """

    raw: str
    version: str
    stream: str
    architecture: str
    stream_name: str
    timestamp: str

    @classmethod
    def parse(cls, tag: str) -> "PayloadTag":
        """Parse a payload tag string into its components."""
        m = re.match(r"^(.+)-(\d{4}-\d{2}-\d{2}-\d{6})$", tag)
        if not m:
            raise ValueError(f"Cannot parse payload tag: {tag}")

        stream_name = m.group(1)
        timestamp = m.group(2)

        sm = re.match(
            r"^(\d+\.\d+)\.0-0\.([\w-]+?)(?:-(arm64|ppc64le|s390x|multi))?$",
            stream_name,
        )
        if not sm:
            raise ValueError(f"Cannot parse stream name: {stream_name}")

        version = sm.group(1)
        stream = sm.group(2)
        architecture = sm.group(3) or "amd64"

        return cls(
            raw=tag,
            version=version,
            stream=stream,
            architecture=architecture,
            stream_name=stream_name,
            timestamp=timestamp,
        )


# ---------------------------------------------------------------------------
# JobInfo — metadata for a single CI job
# ---------------------------------------------------------------------------

@dataclass
class JobInfo:
    """Metadata for a CI job extracted from payload.json."""

    name: str
    state: str
    lifecycle: str  # "blocking" or "informing"
    url: str
    retries: int
    previous_attempt_urls: list[str]
    is_aggregated: bool
    gcs_bucket_path: str
    gcs_url: str = ""
    rhcos_version: str = ""


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def _retry_delay(attempt: int, http_error=None) -> float:
    """Compute retry delay with exponential backoff.

    Base delay doubles each attempt: 60, 120, 240, 480, 960, 1920 seconds
    (1, 2, 4, 8, 16, 32 minutes).  A small random jitter is added.

    For 429 responses with a Retry-After header, the delay is the greater
    of the Retry-After value and the exponential backoff (the backoff acts
    as a minimum floor to avoid hammering the server).
    """
    base_delay = 60 * (2 ** attempt) + random.uniform(0, 1)
    if http_error and http_error.code == 429:
        retry_after = http_error.headers.get("Retry-After")
        if retry_after:
            try:
                return max(float(retry_after), base_delay)
            except ValueError:
                pass
    return base_delay


def fetch_json(url: str, timeout: int = 30, max_retries: int = 6) -> dict:
    """Fetch JSON from a URL with retries for transient errors."""
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    for attempt in range(max_retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 404:
                raise SystemExit(f"Payload not found (HTTP 404): {url}") from e
            retryable = e.code >= 500 or e.code == 429
            if not retryable or attempt >= max_retries:
                raise
            delay = _retry_delay(attempt, e)
            reason = f"HTTP {e.code}"
        except urllib.error.URLError:
            if attempt >= max_retries:
                raise
            delay = _retry_delay(attempt)
            reason = "connection error"
        else:
            continue
        print(f"  Retry {attempt + 1}/{max_retries}: {reason} from {url}, waiting {delay:.1f}s", file=sys.stderr)
        time.sleep(delay)


def try_fetch_json(url: str, timeout: int = 10) -> Optional[dict]:
    """Fetch JSON from a URL, returning None on any failure."""
    try:
        return fetch_json(url, timeout=timeout)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# ReleaseController — API client
# ---------------------------------------------------------------------------

class ReleaseController:
    """Client for the OpenShift release controller API."""

    def __init__(self, architecture: str = "amd64", stream: str = ""):
        self.architecture = architecture
        if stream.startswith("okd"):
            self.domain = f"{architecture}.origin.releases.ci.openshift.org"
        else:
            self.domain = f"{architecture}.ocp.releases.ci.openshift.org"
        self._base = f"https://{self.domain}/api/v1"

    def fetch_tags(self, stream_name: str) -> list[dict]:
        """Fetch all tags for a release stream, newest first."""
        url = f"{self._base}/releasestream/{urllib.parse.quote(stream_name)}/tags"
        data = fetch_json(url)
        return data.get("tags", [])

    def fetch_release(self, stream_name: str, tag: str) -> dict:
        """Fetch full release details for a specific tag."""
        url = (
            f"{self._base}/releasestream/{urllib.parse.quote(stream_name)}"
            f"/release/{urllib.parse.quote(tag)}"
        )
        return fetch_json(url, timeout=60)

    def fetch_changelog(
        self, stream_name: str, tag: str, from_tag: str
    ) -> dict:
        """Fetch the diff/changelog between two tags."""
        url = (
            f"{self._base}/releasestream/{urllib.parse.quote(stream_name)}"
            f"/release/{urllib.parse.quote(tag)}"
            f"?from={urllib.parse.quote(from_tag)}"
        )
        return fetch_json(url, timeout=60)

    def release_url(self, stream_name: str, tag: str) -> str:
        """Build the human-readable release controller page URL."""
        return (
            f"https://{self.domain}"
            f"/releasestream/{urllib.parse.quote(stream_name)}"
            f"/release/{urllib.parse.quote(tag)}"
        )

    def resolve_prow_state(self, prow_url: str) -> Optional[str]:
        """Cross-check a Prow job's actual state via its GCS artifact."""
        if not prow_url or not prow_url.startswith(PROW_VIEW_PREFIX):
            return None
        gcs_path = prow_url[len(PROW_VIEW_PREFIX):]
        prowjob_url = f"{GCSWEB_BASE}/{gcs_path}/prowjob.json"
        data = try_fetch_json(prowjob_url)
        if not data:
            return None
        prow_state = data.get("status", {}).get("state", "")
        return PROW_STATE_MAP.get(prow_state)


# ---------------------------------------------------------------------------
# SippyClient — fallback API client for historical payloads
# ---------------------------------------------------------------------------

class SippyClient:
    """Client for Sippy's release-controller mirror APIs."""

    SIPPY_BASE = "https://sippy.dptools.openshift.org/api"
    SIPPY_UI = "https://sippy.dptools.openshift.org/sippy-ng"

    def __init__(
        self, release: str, architecture: str = "amd64", stream: str = "nightly"
    ):
        self.release = release
        self.architecture = architecture
        self.stream = stream
        self._tags_cache: Optional[list] = None
        self._job_runs_cache: dict[str, list[dict]] = {}

    @staticmethod
    def _filter(column: str, value: str) -> dict:
        return {
            "columnField": column,
            "operatorValue": "equals",
            "value": value,
        }

    @classmethod
    def _encoded_filter(cls, *items: tuple[str, str]) -> str:
        filter_json = {
            "items": [cls._filter(column, value) for column, value in items]
        }
        return urllib.parse.quote(json.dumps(filter_json))

    def _get_tags(self) -> list[dict]:
        if self._tags_cache is None:
            filter_value = self._encoded_filter(
                ("architecture", self.architecture),
                ("stream", self.stream),
            )
            url = (
                f"{self.SIPPY_BASE}/releases/tags"
                f"?filter={filter_value}"
                f"&release={urllib.parse.quote(self.release)}"
                "&sortField=release_time&sort=desc"
            )
            self._tags_cache = fetch_json(url, timeout=60)
        return self._tags_cache

    def find_tag(self, tag_name: str) -> Optional[dict]:
        for t in self._get_tags():
            if t.get("release_tag") == tag_name:
                return t
        return None

    def fetch_tags(self) -> list[dict]:
        """Fetch release tags newest first for this release/arch/stream."""
        return self._get_tags()

    def fetch_job_runs(self, tag_name: str) -> list[dict]:
        if tag_name in self._job_runs_cache:
            return self._job_runs_cache[tag_name]
        filter_value = self._encoded_filter(("release_tag", tag_name))
        url = (f"{self.SIPPY_BASE}/releases/job_runs"
               f"?filter={filter_value}"
               f"&sortField=kind&sort=asc&limit=1000")
        runs = fetch_json(url, timeout=60)
        self._job_runs_cache[tag_name] = runs
        return runs

    def fetch_pull_requests(self, tag_name: str) -> list[dict]:
        """Fetch PRs introduced by a payload from Sippy."""
        filter_value = self._encoded_filter(("release_tag", tag_name))
        url = (
            f"{self.SIPPY_BASE}/releases/pull_requests"
            f"?filter={filter_value}"
            "&sortField=pull_request_id&sort=asc&limit=1000"
        )
        return fetch_json(url, timeout=60)

    def fetch_changelog(
        self, tag_name: str, from_tag: Optional[str] = None
    ) -> list[dict]:
        """Fetch the incremental PR diff, with per-payload PR fallback."""
        if from_tag:
            url = (
                f"{self.SIPPY_BASE}/payloads/diff"
                f"?toPayload={urllib.parse.quote(tag_name)}"
                f"&fromPayload={urllib.parse.quote(from_tag)}"
            )
            try:
                return fetch_json(url, timeout=60)
            except FALLBACK_FETCH_ERRORS as exc:
                _log(
                    "  Sippy incremental payload diff unavailable; "
                    f"using per-payload PR data: {exc}"
                )
        return self.fetch_pull_requests(tag_name)

    def release_url(self, tag_name: str) -> str:
        return (
            f"{self.SIPPY_UI}/release/{urllib.parse.quote(self.release)}"
            f"/tags/{urllib.parse.quote(tag_name)}"
        )

    def build_synthetic_payload(self, tag_name: str, tag: "PayloadTag") -> dict:
        tag_meta = self.find_tag(tag_name)
        job_runs = self.fetch_job_runs(tag_name)

        phase = tag_meta.get("phase", "Unknown") if tag_meta else "Unknown"

        blocking_jobs: dict = {}
        informing_jobs: dict = {}
        for jr in job_runs:
            name = jr.get("job_name", "")
            if not name:
                continue
            prow_url = jr.get("url", "")
            entry = {
                "state": jr.get("state", ""),
                "url": prow_url,
                "retries": jr.get("retries", 0),
            }
            if jr.get("kind") == "Blocking":
                blocking_jobs[name] = entry
            else:
                informing_jobs[name] = entry

        return {
            "phase": phase,
            "results": {
                "blockingJobs": blocking_jobs,
                "informingJobs": informing_jobs,
            },
            "_release_url": self.release_url(tag_name),
            "_source": "sippy",
        }

    def build_synthetic_changelog(
        self, tag_name: str, from_tag: Optional[str] = None
    ) -> dict:
        prs = self.fetch_changelog(tag_name, from_tag=from_tag)
        if not isinstance(prs, list):
            return {"changeLogJson": {"updatedImages": []}, "_source": "sippy"}

        by_component: dict = {}
        for pr in prs:
            comp = pr.get("name", "unknown")
            if comp not in by_component:
                by_component[comp] = {"name": comp, "commits": []}
            pr_url = pr.get("url", "")
            pr_id = pr.get("pull_request_id", "")
            by_component[comp]["commits"].append({
                "pullURL": pr_url,
                "pullID": int(pr_id) if pr_id and str(pr_id).isdigit() else 0,
                "subject": pr.get("description", ""),
            })

        return {
            "changeLogJson": {
                "updatedImages": list(by_component.values()),
            },
            "_source": "sippy",
        }


# ---------------------------------------------------------------------------
# PayloadChain — backward walk to find all-green baseline
# ---------------------------------------------------------------------------

class PayloadChain:
    """Walks backwards through payloads to find the all-green baseline."""

    def __init__(self, rc: ReleaseController, stream_name: str, max_depth: int = 20):
        self.rc = rc
        self.stream_name = stream_name
        self.max_depth = max_depth

    def build(self, start_tag: str) -> list[str]:
        """Return an ordered list of tags from start_tag back to the baseline.

        The baseline (last element) is the first payload where all blocking
        jobs succeeded.  The start_tag is always the first element.
        """
        all_tags = self.rc.fetch_tags(self.stream_name)
        tag_names = [t["name"] for t in all_tags]

        try:
            start_idx = tag_names.index(start_tag)
        except ValueError as exc:
            raise ValueError(
                f"Tag {start_tag} not found in stream {self.stream_name}"
            ) from exc

        chain = []
        for i in range(start_idx, min(start_idx + self.max_depth, len(tag_names))):
            tag = tag_names[i]
            chain.append(tag)

            details = self.rc.fetch_release(self.stream_name, tag)
            if self._all_blocking_passed(details):
                break

        return chain

    def _all_blocking_passed(self, details: dict) -> bool:
        """Check if every blocking job in a payload succeeded."""
        phase = details.get("phase", "")
        blocking = details.get("results", {}).get("blockingJobs", {})
        if not blocking:
            return True

        for job_name, job_info in blocking.items():
            state = job_info.get("state", "")
            if state == "Pending" and phase in ("Accepted", "Rejected"):
                resolved = self.rc.resolve_prow_state(job_info.get("url", ""))
                if resolved:
                    state = resolved
            if state != "Succeeded":
                return False
        return True


class SippyPayloadChain:
    """Walks backwards through Sippy's time-ordered payload tags."""

    def __init__(self, sippy: SippyClient, max_depth: int = 20):
        self.sippy = sippy
        self.max_depth = max_depth

    def _all_blocking_passed(self, tag_name: str) -> bool:
        """Check whether every blocking job in a payload succeeded."""
        runs = self.sippy.fetch_job_runs(tag_name)
        blocking = [r for r in runs if r.get("kind") == "Blocking"]
        if not blocking:
            tag_meta = self.sippy.find_tag(tag_name)
            return bool(
                tag_meta
                and tag_meta.get("phase") == "Accepted"
                and not tag_meta.get("forced", False)
                and tag_meta.get("failed_job_names") == []
            )
        return all(
            r.get("state") == "Succeeded" for r in blocking
        )

    def build(self, start_tag: str) -> list[str]:
        tag_names = [
            tag["release_tag"] for tag in self.sippy.fetch_tags()
            if tag.get("release_tag")
        ]
        try:
            start_index = tag_names.index(start_tag)
        except ValueError as exc:
            raise ValueError(f"Tag {start_tag} not found in Sippy") from exc

        chain = []
        for tag_name in tag_names[
            start_index:start_index + self.max_depth
        ]:
            chain.append(tag_name)
            if self._all_blocking_passed(tag_name):
                break
        return chain


class HybridPayloadChain:
    """Build a complete payload chain from RC data plus Sippy history.

    Release-controller details remain authoritative for retained tags. Sippy's
    time-ordered tag list identifies payloads that were garbage collected
    between retained release-controller entries.
    """

    def __init__(
        self,
        rc: ReleaseController,
        sippy: SippyClient,
        stream_name: str,
        max_depth: int = 20,
    ):
        self.rc = rc
        self.sippy = sippy
        self.stream_name = stream_name
        self.max_depth = max_depth
        self.sources: dict[str, str] = {}
        self._rc_tags: list[str] = []
        self._sippy_tags: list[str] = []
        self._sippy_available = True
        self._warned_sippy = False

    def _load_sippy_tags(self) -> list[str]:
        if not self._sippy_available:
            return []
        try:
            self._sippy_tags = [
                tag["release_tag"] for tag in self.sippy.fetch_tags()
                if tag.get("release_tag")
            ]
            return self._sippy_tags
        except FALLBACK_FETCH_ERRORS as exc:
            self._sippy_available = False
            if not self._warned_sippy:
                _log(
                    "Warning: Sippy release ancestry is unavailable; "
                    f"falling back to release-controller ordering: {exc}"
                )
                self._warned_sippy = True
            return []

    @staticmethod
    def _previous(tag_names: list[str], tag_name: str) -> str:
        try:
            index = tag_names.index(tag_name)
        except ValueError:
            return ""
        if index + 1 >= len(tag_names):
            return ""
        return tag_names[index + 1]

    def _fetch_details(self, tag_name: str, rc_tag_names: set[str]) -> dict:
        if tag_name in rc_tag_names:
            self.sources[tag_name] = "release-controller"
            return self.rc.fetch_release(self.stream_name, tag_name)

        tag = PayloadTag.parse(tag_name)
        self.sources[tag_name] = "sippy"
        return self.sippy.build_synthetic_payload(tag_name, tag)

    def build(self, start_tag: str) -> list[str]:
        rc_tags = self.rc.fetch_tags(self.stream_name)
        self._rc_tags = [t["name"] for t in rc_tags]
        rc_tag_names = set(self._rc_tags)
        sippy_tag_names = set(self._load_sippy_tags())

        if start_tag not in rc_tag_names and start_tag not in sippy_tag_names:
            raise ValueError(
                f"Tag {start_tag} not found in release controller or Sippy"
            )

        chain: list[str] = []
        current = start_tag
        for _ in range(self.max_depth):
            if current in chain:
                _log(f"Warning: payload ancestry cycle detected at {current}")
                break
            chain.append(current)

            details = self._fetch_details(current, rc_tag_names)
            rc_chain = PayloadChain(self.rc, self.stream_name)
            if rc_chain._all_blocking_passed(details):
                break

            sippy_previous = self._previous(self._sippy_tags, current)
            rc_previous = self._previous(self._rc_tags, current)
            previous = sippy_previous or rc_previous
            if not previous:
                break

            if sippy_previous and sippy_previous not in rc_tag_names:
                _log(
                    "  Sippy history restored garbage-collected payload "
                    f"{sippy_previous} before {current}"
                )
            current = previous

        return chain


# ---------------------------------------------------------------------------
# Collector base class
# ---------------------------------------------------------------------------

class Collector(ABC):
    """Base class for artifact collectors.

    Subclasses implement ``_fetch()`` to retrieve data and return it.
    The base ``collect()`` handles idempotency (skip if file exists) and
    writing the result to disk.
    """

    def __init__(self, output_path: str):
        self.output_path = output_path

    def collect(self) -> bool:
        """Fetch and write the artifact.  Returns True if new data was written."""
        if os.path.exists(self.output_path):
            _log(f"  skip (exists): {self.output_path}")
            return False

        data = self._fetch()
        if data is None:
            return False

        os.makedirs(os.path.dirname(self.output_path), exist_ok=True)
        if isinstance(data, (dict, list)):
            _write_json(self.output_path, data)
        else:
            _write_text(self.output_path, str(data))
        return True

    @abstractmethod
    def _fetch(self) -> Any:
        """Retrieve the artifact data.  Return None to skip writing."""


# ---------------------------------------------------------------------------
# Concrete collectors
# ---------------------------------------------------------------------------

class StreamsCollector(Collector):
    """Probes all stream/architecture combinations for a version."""

    def __init__(self, output_path: str, version: str):
        super().__init__(output_path)
        self.version = version

    def _fetch(self) -> list[dict]:
        _log("Fetching streams list...")
        streams = []
        for arch in KNOWN_ARCHITECTURES:
            for stream_type in STREAM_TYPES:
                if stream_type == "ci" and arch != "amd64":
                    continue
                stream_name = _build_stream_name(self.version, stream_type, arch)
                rc = ReleaseController(arch)
                url = f"{rc._base}/releasestream/{urllib.parse.quote(stream_name)}/tags"
                data = try_fetch_json(url)
                if data and data.get("tags"):
                    latest = data["tags"][0] if data["tags"] else {}
                    streams.append({
                        "architecture": arch,
                        "stream": stream_type,
                        "stream_name": stream_name,
                        "tag_count": len(data["tags"]),
                        "latest_tag": latest.get("name", ""),
                        "latest_phase": latest.get("phase", ""),
                    })
        return streams


class PayloadDetailCollector(Collector):
    """Fetches release controller details for a single payload tag."""

    def __init__(self, output_path: str, rc: ReleaseController,
                 stream_name: str, tag: str):
        super().__init__(output_path)
        self.rc = rc
        self.stream_name = stream_name
        self.tag = tag

    def _fetch(self) -> dict:
        _log(f"  Fetching payload details: {self.tag}")
        details = self.rc.fetch_release(self.stream_name, self.tag)
        details["_release_url"] = self.rc.release_url(self.stream_name, self.tag)
        details["_source"] = "release-controller"
        return details


class ChangelogCollector(Collector):
    """Fetches the changelog (PR diff) between two consecutive payload tags."""

    def __init__(self, output_path: str, rc: ReleaseController,
                 stream_name: str, tag: str, from_tag: str):
        super().__init__(output_path)
        self.rc = rc
        self.stream_name = stream_name
        self.tag = tag
        self.from_tag = from_tag

    def _fetch(self) -> dict:
        _log(f"  Fetching changelog: {self.tag} from {self.from_tag}")
        changelog = self.rc.fetch_changelog(
            self.stream_name, self.tag, self.from_tag
        )
        changelog["_source"] = "release-controller"
        return changelog


class PullRequestCollector(Collector):
    """Fetches diff, comments, and job data for a single GitHub PR.

    Unlike other collectors that produce a single file, this writes three
    files into a directory.  ``output_path`` is the PR directory.
    """

    def __init__(self, output_path: str, org: str, repo: str, pr_number: int):
        super().__init__(output_path)
        self.org = org
        self.repo = repo
        self.pr_number = pr_number

    def collect(self) -> bool:
        """Fetch all three PR artifacts independently."""
        os.makedirs(self.output_path, exist_ok=True)
        wrote_any = False

        artifacts = [
            (
                "code.diff",
                ["gh", "pr", "diff", str(self.pr_number),
                 "--repo", f"{self.org}/{self.repo}"],
            ),
            (
                "comments.json",
                ["gh", "pr", "view", str(self.pr_number),
                 "--repo", f"{self.org}/{self.repo}",
                 "--json", "comments,reviews"],
            ),
            (
                "jobs.json",
                ["gh", "pr", "view", str(self.pr_number),
                 "--repo", f"{self.org}/{self.repo}",
                 "--json", "statusCheckRollup"],
            ),
        ]

        for filename, cmd in artifacts:
            path = os.path.join(self.output_path, filename)
            if os.path.exists(path):
                continue
            result = _run_gh(cmd)
            if result is not None:
                _write_text(path, result)
                wrote_any = True
            elif filename == "code.diff":
                result = self._git_diff_fallback()
                if result is not None:
                    _write_text(path, result)
                    wrote_any = True

        return wrote_any

    def _git_diff_fallback(self) -> Optional[str]:
        """Clone repo and generate diff locally when gh pr diff fails."""
        meta_str = _run_gh(
            ["gh", "pr", "view", str(self.pr_number),
             "--repo", f"{self.org}/{self.repo}",
             "--json", "baseRefName"],
            timeout=30,
        )
        if not meta_str:
            return None
        try:
            base_ref = json.loads(meta_str).get("baseRefName", "main")
        except json.JSONDecodeError:
            return None

        repo_url = f"https://github.com/{self.org}/{self.repo}.git"
        tmpdir = tempfile.mkdtemp(prefix="snapshot-diff-")
        try:
            _log(f"    fallback: cloning {self.org}/{self.repo} "
                 f"for PR #{self.pr_number}")

            # Blobless clone — fetches commit/tree objects only, blobs
            # are pulled on demand when git diff needs them.
            clone = subprocess.run(
                ["git", "clone", "--filter=blob:none", "--bare",
                 "--single-branch", "--branch", base_ref,
                 "--no-tags", repo_url, tmpdir],
                capture_output=True, text=True, timeout=300,
            )
            if clone.returncode != 0:
                return None

            fetch = subprocess.run(
                ["git", "-C", tmpdir, "fetch", "origin",
                 f"refs/pull/{self.pr_number}/head:refs/heads/pr"],
                capture_output=True, text=True, timeout=120,
            )
            if fetch.returncode != 0:
                return None

            # Use merge-base for a correct diff against where the PR
            # branched off, not the current branch tip.
            mb = subprocess.run(
                ["git", "-C", tmpdir, "merge-base", base_ref, "pr"],
                capture_output=True, text=True, timeout=30,
            )
            if mb.returncode != 0:
                return None

            result = subprocess.run(
                ["git", "-C", tmpdir, "diff",
                 mb.stdout.strip(), "pr"],
                capture_output=True, text=True, timeout=120,
            )
            if result.returncode == 0:
                return result.stdout
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return None
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)
        return None

    def _fetch(self) -> Any:
        pass  # not used — collect() is overridden


class JobCollector(Collector):
    """Writes job metadata to an individual job.json file."""

    def __init__(self, output_path: str, job: JobInfo):
        super().__init__(output_path)
        self.job = job

    def _fetch(self) -> dict:
        data = {
            "name": self.job.name,
            "state": self.job.state,
            "lifecycle": self.job.lifecycle,
            "url": self.job.url,
            "gcs_url": self.job.gcs_url,
            "retries": self.job.retries,
            "previousAttemptURLs": self.job.previous_attempt_urls,
            "is_aggregated": self.job.is_aggregated,
            "gcs_bucket_path": self.job.gcs_bucket_path,
        }
        if self.job.rhcos_version:
            data["rhcos_version"] = self.job.rhcos_version
        return data


class JUnitCollector(Collector):
    """Downloads and parses JUnit artifacts for a failed CI job."""

    def __init__(self, output_dir: str, job: JobInfo, payload_tag: str):
        super().__init__(os.path.join(output_dir, "results.json"))
        self.output_dir = output_dir
        self.job = job
        self.payload_tag = payload_tag

    def collect(self) -> bool:
        if os.path.exists(self.output_path):
            _log(f"  skip (exists): {self.output_path}")
            return False

        if not self.job.gcs_bucket_path:
            return False

        os.makedirs(self.output_dir, exist_ok=True)
        all_results: list[_TestResult] = []

        with _error_scope() as own_errors:
            junit_files = self._list_junit_files()
            downloaded, failed_downloads = self._download_and_parse(
                junit_files, all_results
            )
        gcloud_failed = any(
            not e.get("recovered") for e in own_errors
        )

        # Nothing was discovered at all.  These collectors only run for
        # jobs that FAILED, so "no JUnit anywhere" is not evidence of a
        # clean run — it is an unknown.  Publishing [] here would report a
        # verified zero for a job whose tests may never have run.
        if not junit_files:
            _record_collection_error(
                "junit_missing",
                ["gcloud", "storage", "ls", "<junit>"],
                detail=(
                    "no JUnit artifacts discovered for a failed job; "
                    "test results are unknown, not zero"
                ),
                stage="junit",
                job=self.job.name,
                payload_tag=self.payload_tag,
            )
            _log(
                f"  ERROR: no JUnit discovered for {self.job.name} — "
                f"leaving results.json absent (unknown, not zero)"
            )
            return False

        return self._publish(
            junit_files, all_results, downloaded, failed_downloads,
            gcloud_failed,
        )

    def _download_and_parse(
        self, junit_files: list[str], all_results: list
    ) -> tuple[int, int]:
        """Fetch each JUnit file and parse it; count successes/failures."""
        downloaded = 0
        failed_downloads = 0
        for gcs_uri in junit_files:
            filename = os.path.basename(gcs_uri)
            local_path = os.path.join(self.output_dir, filename)
            if not os.path.exists(local_path):
                data = _run_gcloud_bytes(
                    ["gcloud", "storage", "cat", gcs_uri], timeout=60
                )
                if data:
                    with open(local_path, "wb") as f:
                        f.write(data)

            if os.path.exists(local_path):
                results = _parse_junit_xml(local_path, source_name=filename)
                if results is None:
                    # Downloaded but unparseable.  Treated as unread, not as
                    # "no failures" — corrupt XML must never become a zero.
                    failed_downloads += 1
                    _record_collection_error(
                        "junit_unparseable",
                        ["parse", filename],
                        detail=f"{filename} is not valid JUnit XML",
                        stage="junit",
                        job=self.job.name,
                        payload_tag=self.payload_tag,
                    )
                    continue
                downloaded += 1
                all_results.extend(results)
            else:
                failed_downloads += 1
        return downloaded, failed_downloads

    def _publish(
        self, junit_files: list[str], all_results: list,
        downloaded: int, failed_downloads: int, gcloud_failed: bool,
    ) -> bool:
        """Write results.json unless doing so would misreport the data."""
        # Refuse to publish an empty result set that was caused by a read
        # failure.  Writing `[]` here makes the job look clean, and
        # downstream consumers report "0 test failures" for a job that
        # actually failed.  Leaving results.json absent means "unknown",
        # which the summary and the analysis skill treat as such.
        if gcloud_failed and downloaded == 0:
            _record_collection_error(
                "junit_unavailable",
                ["gcloud", "storage", "cat", "<junit>"],
                detail=(
                    "no JUnit XML could be read; results.json intentionally "
                    "not written so this is not mistaken for zero failures"
                ),
                stage="junit",
                job=self.job.name,
                payload_tag=self.payload_tag,
            )
            _log(
                f"  ERROR: could not read JUnit for {self.job.name} — "
                f"leaving results.json absent (unknown, not zero)"
            )
            return False

        # Some files read, others not.  The results are real but partial, so
        # publish them and mark them partial — a count derived from half the
        # JUnit is not authoritative and must not read as one that is.
        if failed_downloads:
            _record_collection_error(
                "junit_partial",
                ["gcloud", "storage", "cat", "<junit>"],
                detail=(
                    f"{failed_downloads} of {len(junit_files)} JUnit file(s) "
                    f"could not be read; test_failure_count is a lower bound"
                ),
                stage="junit",
                job=self.job.name,
                payload_tag=self.payload_tag,
            )
            _log(
                f"  WARNING: partial JUnit for {self.job.name} — "
                f"{failed_downloads}/{len(junit_files)} file(s) unread"
            )

        failures = _test_results_to_json(all_results)
        _write_json(self.output_path, failures)

        underlying = self._detect_underlying_job_name()
        if underlying:
            job_json_path = os.path.join(
                os.path.dirname(self.output_dir), "job.json"
            )
            job_data = _read_json(job_json_path)
            if job_data:
                job_data["underlying_job_name"] = underlying
                _write_json(job_json_path, job_data)

        return True

    def _list_junit_files(self) -> list[str]:
        """Discover JUnit XML files in GCS for this job.

        Tries a recursive glob first, then falls back to bounded-depth
        probes.  Jobs that emit very large artifact trees (Hypershift e2e
        can produce 10,000+ cluster resource dumps) make the ``**`` glob
        slow enough to time out, and a timeout here previously produced a
        silently empty result set.
        """
        bucket_path = self.job.gcs_bucket_path
        base = f"gs://{bucket_path}"

        with _error_scope() as glob_errors:
            output = _run_gcloud(
                ["gcloud", "storage", "ls",
                 f"{base}/artifacts/**/junit*.xml"],
                timeout=120,
            )

        files = [line.strip() for line in (output or "").strip().splitlines()
                 if line.strip()]

        if not files:
            _log(
                f"  warn: recursive glob found no JUnit for {self.job.name} "
                f"— trying bounded-depth fallback"
            )
            files = self._list_junit_files_fallback(base)
            if files:
                # The glob's failure is recovered; any probe failures the
                # fallback itself hit are NOT — they may be missing data.
                _mark_errors_recovered(glob_errors)

        if not files:
            return []

        if self.job.is_aggregated:
            # For aggregated jobs, keep junit_operator.xml and the
            # junit-aggregated.xml. Filter out other junit files that are
            # less useful.
            keep = []
            for f in files:
                bn = os.path.basename(f)
                if bn == "junit_operator.xml" or bn == "junit-aggregated.xml":
                    keep.append(f)
            return keep if keep else files

        # For regular jobs, keep junit_operator.xml and the main test
        # results file (largest non-operator junit file).
        operator = [f for f in files if f.endswith("/junit_operator.xml")]
        others = [f for f in files if not f.endswith("/junit_operator.xml")]
        # Prefer files with "e2e" or "analysis" in the name
        preferred = [f for f in others
                     if "e2e" in os.path.basename(f)
                     or "analysis" in os.path.basename(f)]
        keep = operator + (preferred if preferred else others[:1])
        return keep if keep else files

    def _list_junit_files_fallback(self, base: str) -> list[str]:
        """Targeted JUnit discovery that avoids a full recursive glob.

        Lists the top-level step directories under ``artifacts/`` and
        probes each at the depths JUnit files actually appear, rather
        than enumerating every object in the tree:

          - ``{step}/junit*.xml``
          - ``{step}/artifacts/junit*.xml``
          - ``{step}/*/artifacts/junit*.xml``

        Aggregated jobs keep ``junit-aggregated.xml`` far deeper than
        that, so the aggregator subtree gets its own scoped recursive
        probe — scoped to one small directory, it stays fast.
        """
        dir_output = _run_gcloud(
            ["gcloud", "storage", "ls", f"{base}/artifacts/"],
            timeout=60,
        )
        if not dir_output:
            return []

        # Each line is a directory like gs://bucket/path/artifacts/step-name/
        step_dirs = [
            d.strip().rstrip("/").split("/")[-1]
            for d in dir_output.strip().splitlines()
            if d.strip()
        ]

        # junit_operator.xml sits directly in artifacts/, not in a step dir.
        found: list[str] = []
        top = _run_gcloud(
            ["gcloud", "storage", "ls", f"{base}/artifacts/junit*.xml"],
            timeout=60,
        )
        if top:
            found.extend(line.strip() for line in top.strip().splitlines()
                         if line.strip())

        for step in step_dirs:
            patterns = [
                f"{base}/artifacts/{step}/junit*.xml",
                f"{base}/artifacts/{step}/artifacts/junit*.xml",
                f"{base}/artifacts/{step}/*/artifacts/junit*.xml",
            ]
            # The aggregated report lives several levels below the
            # aggregator step; a scoped ** over that one subtree is cheap.
            if "aggregator" in step:
                patterns.append(f"{base}/artifacts/{step}/**/junit*.xml")

            for pattern in patterns:
                probe = _run_gcloud(
                    ["gcloud", "storage", "ls", pattern], timeout=60
                )
                if probe:
                    found.extend(
                        line.strip() for line in probe.strip().splitlines()
                        if line.strip()
                    )

        found = sorted(set(found))
        if found:
            _log(f"  fallback found {len(found)} JUnit file(s)")
        return found

    def _detect_underlying_job_name(self) -> Optional[str]:
        """For aggregated jobs, extract the underlying job name from GCS paths."""
        if not self.job.is_aggregated:
            return None
        agg_xml = os.path.join(self.output_dir, "junit-aggregated.xml")
        if not os.path.exists(agg_xml):
            # Try to find it from GCS path structure
            bucket_path = self.job.gcs_bucket_path
            output = _run_gcloud(
                ["gcloud", "storage", "ls",
                 f"gs://{bucket_path}/artifacts/release-analysis-aggregator/"
                 f"openshift-release-analysis-aggregator/artifacts/"
                 f"release-analysis-aggregator/*/"],
                timeout=30,
            )
            if output:
                for line in output.strip().splitlines():
                    parts = line.rstrip("/").split("/")
                    if parts:
                        return parts[-1]
        return None

    def _fetch(self) -> Any:
        pass  # not used — collect() is overridden


class BuildLogCollector(Collector):
    """Downloads build-log.txt from GCS and extracts error/warning lines."""

    _ERROR_RE = re.compile(
        r"(?:^|\s)(?:error|ERROR|Error|warning|WARNING|Warning"
        r"|FATAL|fatal|panic|PANIC)[:\s\[]",
    )

    def __init__(self, output_path: str, job: JobInfo):
        super().__init__(output_path)
        self.job = job

    def _fetch(self) -> Optional[dict]:
        if not self.job.gcs_bucket_path:
            return None

        gcs_uri = f"gs://{self.job.gcs_bucket_path}/build-log.txt"
        with _error_scope() as own_errors:
            raw = _run_gcloud_bytes(
                ["gcloud", "storage", "cat", gcs_uri], timeout=120
            )
        if not raw:
            if any(not e.get("recovered") for e in own_errors):
                _record_collection_error(
                    "build_log_unavailable",
                    ["gcloud", "storage", "cat", gcs_uri],
                    detail="build-log.txt could not be read",
                    stage="build_log",
                    job=self.job.name,
                )
            return None

        try:
            text = gzip.decompress(raw).decode("utf-8", errors="replace")
        except (gzip.BadGzipFile, OSError):
            text = raw.decode("utf-8", errors="replace")

        lines = text.splitlines()
        total = len(lines)
        if total == 0:
            return {"error_warning_lines": [], "tail_lines": [],
                    "total_lines": 0}

        error_warning = []
        for i, line in enumerate(lines):
            if self._ERROR_RE.search(line):
                error_warning.append({
                    "line_number": i + 1,
                    "text": line.rstrip(),
                })

        tail_start = max(0, total - total // 5)
        tail_lines = [l.rstrip() for l in lines[tail_start:]]

        return {
            "total_lines": total,
            "error_warning_count": len(error_warning),
            "error_warning_lines": error_warning,
            "tail_start_line": tail_start + 1,
            "tail_lines": tail_lines,
        }


# ---------------------------------------------------------------------------
# RpmdbCollector — extracts full RPM database from RHCOS images
# ---------------------------------------------------------------------------

class RpmdbCollector:
    """Extracts rpmdb.sqlite from RHCOS images in a release payload."""

    RPMDB_PATH = "/usr/lib/sysimage/rpm/rpmdb.sqlite"

    def __init__(self, rpmdb_dir: str, release_pullspec: str, payload_tag: str):
        self.rpmdb_dir = rpmdb_dir
        self.release_pullspec = release_pullspec
        self.payload_tag = payload_tag
        self._marker = os.path.join(rpmdb_dir, ".complete")

    def collect(self) -> list[dict]:
        """Extract rpmdb.sqlite from RHCOS images. Returns summary entries."""
        if os.path.exists(self._marker):
            _log(f"    {self.payload_tag}: skip (exists): rpmdb/")
            return self._read_existing()

        image_refs = self._fetch_image_references()
        if image_refs is None:
            return []

        rhcos_images = self._filter_rhcos(image_refs)
        if not rhcos_images:
            _log(f"    {self.payload_tag}: No RHCOS images found in "
                 f"image-references")
            return []

        os.makedirs(self.rpmdb_dir, exist_ok=True)
        summaries = []

        for tag_name, pullspec, display_name in rhcos_images:
            variant_dir = os.path.join(self.rpmdb_dir, tag_name)
            os.makedirs(variant_dir, exist_ok=True)
            output_path = os.path.join(variant_dir, "rpmdb.sqlite")
            ok = self._extract_rpmdb(pullspec, output_path)
            if not ok:
                _log(f"    {self.payload_tag}: Warning: failed to extract "
                     f"rpmdb from {tag_name}")
                continue
            _log(f"    {self.payload_tag}: {tag_name}: rpmdb.sqlite extracted")

            summaries.append({
                "tag": tag_name,
                "name": display_name,
                "pullspec": pullspec,
            })

        if summaries:
            metadata_path = os.path.join(self.rpmdb_dir, "metadata.json")
            _write_text(metadata_path, json.dumps(summaries, indent=2))
            _write_text(self._marker, "")
        return summaries

    def _fetch_image_references(self) -> Optional[dict]:
        """Read /release-manifests/image-references from the release image."""
        result = _run_podman([
            "podman", "run", "--rm", "--entrypoint", "cat",
            self.release_pullspec,
            "/release-manifests/image-references",
        ], timeout=300)
        if result is None or result.returncode != 0:
            return None
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError:
            _log(f"    {self.payload_tag}: Warning: invalid JSON in "
                 f"image-references")
            return None

    def _filter_rhcos(
        self, image_refs: dict
    ) -> list[tuple[str, str, str]]:
        """Filter RHCOS image tags (excluding extensions).

        Returns (tag_name, pullspec, display_name) tuples.
        """
        results = []
        for tag in image_refs.get("spec", {}).get("tags", []):
            name = tag.get("name", "")
            if not name.startswith("rhel-coreos"):
                continue
            if name.endswith("-extensions"):
                continue
            pullspec = tag.get("from", {}).get("name", "")
            if not pullspec:
                continue
            annotations = tag.get("annotations", {})
            display_name = self._parse_display_name(annotations, name)
            results.append((name, pullspec, display_name))
        return results

    @staticmethod
    def _parse_display_name(annotations: dict, fallback: str) -> str:
        """Extract display name from image annotations."""
        raw = annotations.get("io.openshift.build.version-display-names", "")
        for part in raw.split(","):
            part = part.strip()
            if part.startswith("machine-os="):
                return part[len("machine-os="):]
        return fallback

    def _extract_rpmdb(self, pullspec: str, output_path: str) -> bool:
        """Extract rpmdb.sqlite from the RHCOS image via podman cp."""
        create = _run_podman(
            ["podman", "create", "--rm", pullspec, "/bin/true"], timeout=300
        )
        if create is None or create.returncode != 0:
            return False
        cid = create.stdout.strip()

        try:
            cp = _run_podman(
                ["podman", "cp", f"{cid}:{self.RPMDB_PATH}", output_path],
                timeout=120,
            )
            return cp is not None and cp.returncode == 0
        finally:
            _run_podman(["podman", "rm", "-f", cid], timeout=30)

    def _read_existing(self) -> list[dict]:
        """Read summaries from already-extracted rpmdb files."""
        metadata_path = os.path.join(self.rpmdb_dir, "metadata.json")
        if os.path.isfile(metadata_path):
            try:
                with open(metadata_path) as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                pass
        summaries = []
        if not os.path.isdir(self.rpmdb_dir):
            return summaries
        for entry in sorted(os.listdir(self.rpmdb_dir)):
            variant_dir = os.path.join(self.rpmdb_dir, entry)
            if not os.path.isdir(variant_dir):
                continue
            if os.path.isfile(os.path.join(variant_dir, "rpmdb.sqlite")):
                summaries.append({
                    "tag": entry,
                    "name": entry,
                    "pullspec": "",
                })
        return summaries


# ---------------------------------------------------------------------------
# RegressionTracker — traces test failures across the payload chain
# ---------------------------------------------------------------------------

class RegressionTracker:
    """Identifies when each test failure first appeared in the payload chain."""

    def __init__(self, base_dir: str, chain: list[str], target_tag: str):
        self.base_dir = base_dir
        self.chain = chain
        self.target_tag = target_tag
        self._skipped = {"flake": 0, "informing": 0}

    def non_gating_counts(self) -> dict[str, int]:
        """Counts of target-payload results excluded from onset tracking."""
        return dict(self._skipped)

    def track(self) -> list[dict]:
        """Analyze failures in the target payload and trace their origins."""
        target_dir = os.path.join(self.base_dir, self.target_tag)
        target_failures = self._load_all_failures(target_dir)

        if not target_failures:
            return []

        regressions = []
        for test_name, info in sorted(target_failures.items()):
            first_failed_in = self.target_tag
            for i in range(1, len(self.chain)):
                prior_tag = self.chain[i]
                prior_dir = os.path.join(self.base_dir, prior_tag)
                prior_failures = self._load_all_failures(prior_dir)
                if test_name in prior_failures:
                    first_failed_in = prior_tag
                else:
                    break

            chain_idx_first = self.chain.index(first_failed_in)
            regressions.append({
                "test_name": test_name,
                "jobs": info["jobs"],
                "lifecycle": info["lifecycle"],
                "first_failed_in": first_failed_in,
                "payloads_failing": chain_idx_first + 1,
                "failure_message": info.get("failure_message", ""),
                "failure_text": info.get("failure_text", ""),
            })
        return regressions

    def _load_all_failures(self, tag_dir: str) -> dict[str, dict]:
        """Load all test failures from all jobs in a payload directory."""
        failures: dict[str, dict] = {}
        jobs_dir = os.path.join(tag_dir, "jobs")
        if not os.path.isdir(jobs_dir):
            return failures

        for lifecycle in ("blocking",):
            lifecycle_dir = os.path.join(jobs_dir, lifecycle)
            if not os.path.isdir(lifecycle_dir):
                continue
            for job_name in os.listdir(lifecycle_dir):
                results_path = os.path.join(
                    lifecycle_dir, job_name, "junit", "results.json"
                )
                results = _read_json(results_path)
                if not results:
                    continue
                for test in results:
                    name = test.get("name", "")
                    if not name:
                        continue
                    # Only gating results establish a regression onset.  A
                    # flake or an informing test cannot reject a payload, so
                    # letting one set first_failed_in sends the analysis
                    # hunting for a culprit that never existed.
                    if not _is_gating(test):
                        if tag_dir.endswith(self.target_tag):
                            if test.get("status") == "flake":
                                self._skipped["flake"] += 1
                            else:
                                self._skipped["informing"] += 1
                        continue
                    if name in failures:
                        if job_name not in failures[name]["jobs"]:
                            failures[name]["jobs"].append(job_name)
                    else:
                        failures[name] = {
                            "jobs": [job_name],
                            "lifecycle": lifecycle,
                            "failure_message": test.get("failure_message", "")
                                or test.get("error_message", ""),
                            "failure_text": test.get("failure_text", "")
                                or test.get("error_text", ""),
                        }
        return failures


# ---------------------------------------------------------------------------
# JobStreakTracker — per-job failure streaks across the payload chain
# ---------------------------------------------------------------------------

class JobStreakTracker:
    """Tracks per-job failure streaks across the payload chain."""

    def __init__(self, base_dir: str, chain: list[str]):
        self.base_dir = base_dir
        self.chain = chain

    def track(self) -> dict[str, dict]:
        """Return a dict keyed by job name with streak data.

        Only tracks failed blocking jobs in the target (first) payload.
        """
        if not self.chain:
            return {}

        target_tag = self.chain[0]
        target_dir = os.path.join(self.base_dir, target_tag)

        failed_jobs = self._get_failed_jobs(target_dir)
        if not failed_jobs:
            return {}

        streaks: dict[str, dict] = {}
        for job_name in failed_jobs:
            pattern = []
            for tag in self.chain:
                tag_dir = os.path.join(self.base_dir, tag)
                state = self._get_job_state(tag_dir, job_name)
                if state == "Succeeded":
                    pattern.append("S")
                elif state:
                    pattern.append("F")
                else:
                    pattern.append("?")

            streak = 0
            for p in pattern:
                if p == "F":
                    streak += 1
                else:
                    break

            originating_idx = min(streak - 1, len(self.chain) - 1)
            originating_tag = self.chain[originating_idx]

            streaks[job_name] = {
                "streak_length": streak,
                "originating_payload": originating_tag,
                "is_new_failure": streak == 1,
                "failure_pattern": " ".join(pattern),
            }

        return streaks

    def _get_failed_jobs(self, tag_dir: str) -> list[str]:
        blocking_dir = os.path.join(tag_dir, "jobs", "blocking")
        if not os.path.isdir(blocking_dir):
            return []
        failed = []
        for job_name in os.listdir(blocking_dir):
            job_data = _read_json(
                os.path.join(blocking_dir, job_name, "job.json")
            )
            if job_data and job_data.get("state") != "Succeeded":
                failed.append(job_name)
        return sorted(failed)

    def _get_job_state(self, tag_dir: str, job_name: str) -> Optional[str]:
        job_path = os.path.join(
            tag_dir, "jobs", "blocking", job_name, "job.json"
        )
        job_data = _read_json(job_path)
        if job_data:
            return job_data.get("state", "")
        return None


# ---------------------------------------------------------------------------
# SummaryGenerator — produces stream-level roll-up
# ---------------------------------------------------------------------------

class SummaryGenerator:
    """Generates summary.json and summary.md for the stream."""

    def __init__(self, base_dir: str, chain: list[str], target_tag: str,
                 tag: "PayloadTag", streaks: Optional[dict] = None,
                 rpmdb_data: Optional[dict[str, list[dict]]] = None):
        self.base_dir = base_dir
        self.chain = chain
        self.target_tag = target_tag
        self.tag = tag
        self.streaks = streaks or {}
        self.rpmdb_data = rpmdb_data or {}

    def generate(self) -> None:
        target_dir = os.path.join(self.base_dir, self.target_tag)
        payload_data = _read_json(os.path.join(target_dir, "payload.json"))
        regressions = _read_json(
            os.path.join(target_dir, "regressions.json")
        ) or []

        phase = payload_data.get("phase", "Unknown") if payload_data else "Unknown"
        release_url = (payload_data.get("_release_url", "")
                       if payload_data else "")
        source = (payload_data.get("_source", "release-controller")
                  if payload_data else "unknown")
        results = payload_data.get("results", {}) if payload_data else {}

        blocking = results.get("blockingJobs", {}) or {}
        informing = results.get("informingJobs", {}) or {}

        blocking_passed = sum(
            1 for v in blocking.values() if v.get("state") == "Succeeded"
        )
        informing_passed = sum(
            1 for v in informing.values() if v.get("state") == "Succeeded"
        )

        hours_since = self._compute_hours_since_baseline()

        failed_blocking_detail = self._build_failed_job_details(
            "blocking"
        )
        failed_informing_names = sorted(
            k for k, v in informing.items() if v.get("state") != "Succeeded"
        )

        payloads = self._build_payload_entries()

        summary = {
            "payload_tag": self.target_tag,
            "phase": phase,
            "release_url": release_url,
            "source": source,
            "architecture": self.tag.architecture,
            "stream": self.tag.stream,
            "version": self.tag.version,
            "chain_length": len(self.chain),
            "baseline_tag": self.chain[-1] if self.chain else "",
            "hours_since_baseline": hours_since,
            "blocking_jobs": {
                "total": len(blocking),
                "passed": blocking_passed,
                "failed": len(blocking) - blocking_passed,
                "failed_jobs": failed_blocking_detail,
            },
            "informing_jobs": {
                "total": len(informing),
                "passed": informing_passed,
                "failed": len(informing) - informing_passed,
                "failed_jobs": failed_informing_names,
            },
            "test_failures": {
                # Gating failures only — these are what can fail a job and
                # therefore reject the payload.
                "blocking": [
                    r for r in regressions if r.get("lifecycle") == "blocking"
                ],
                # Neither of the following can fail a job or reject a
                # payload.  They are surfaced for visibility, not for blame.
                "informing": self._collect_non_gating("informing"),
                "flakes": self._collect_non_gating("flake"),
            },
            "payloads": payloads,
        }

        target_rpms = self.rpmdb_data.get(self.target_tag)
        if target_rpms:
            summary["rhcos_rpms"] = [
                {**entry, "rpmdb": f"{self.target_tag}/rpmdb/{entry['tag']}/rpmdb.sqlite"}
                for entry in target_rpms
            ]

        # Surface any data that could not be collected.  An empty snapshot
        # section must never be silently indistinguishable from a clean one.
        if _COLLECTION_ERRORS:
            summary["collection_errors"] = list(_COLLECTION_ERRORS)
        summary["data_complete"] = not _unrecovered_errors()

        _write_json(os.path.join(self.base_dir, "summary.json"), summary)
        _write_collection_state(self.base_dir)
        self._write_agents_md(summary)
        _log("  Generated summary.json, AGENTS.md, and CLAUDE.md")

    def _write_agents_md(self, summary: dict) -> None:
        """Write AGENTS.md and CLAUDE.md into the snapshot directory."""
        tag = summary["payload_tag"]
        phase = summary["phase"]
        version = summary["version"]
        stream = summary["stream"]
        arch = summary["architecture"]
        chain_len = summary["chain_length"]
        baseline = summary["baseline_tag"]
        hours = summary.get("hours_since_baseline")
        bj = summary["blocking_jobs"]
        ij = summary["informing_jobs"]

        failed_names = [
            j["name"] if isinstance(j, dict) else j
            for j in bj.get("failed_jobs", [])
        ]

        hours_str = f" ({hours}h ago)" if hours is not None else ""
        chain_tags = "\n".join(f"  - {t}" for t in self.chain)

        lines = [
            f"# Payload Snapshot: {tag}",
            "",
            f"OpenShift {version} {stream} ({arch}) — **{phase}**",
            "",
            "## Quick Start",
            "",
            "Read `summary.json` first. It contains everything you need for",
            "triage: job states, failure streaks, test regressions, build-log",
            "error counts, and relative paths to all detailed data files.",
            "Only drill into per-job or per-PR files when you need specifics.",
            "",
            "## This Snapshot",
            "",
            f"- **Target payload**: `{tag}`",
            f"- **Phase**: {phase}",
            f"- **Blocking jobs**: {bj['failed']}/{bj['total']} failed",
            f"- **Informing jobs**: {ij['failed']}/{ij['total']} failed",
            f"- **Chain depth**: {chain_len} payloads back to baseline",
            f"- **Baseline**: `{baseline}`{hours_str}",
            "",
            "### Payload chain (newest first)",
            "",
            chain_tags,
            "",
        ]

        if not summary.get("data_complete", True):
            errs = [e for e in summary.get("collection_errors", [])
                    if not e.get("recovered")]
            reasons = sorted({e.get("reason", "unknown") for e in errs})
            lines.extend([
                "## ⚠️  INCOMPLETE SNAPSHOT",
                "",
                f"{len(errs)} collection error(s) occurred: "
                f"{', '.join(reasons)}.",
                "See `collection_errors` in `summary.json`.",
                "",
                "Data that could not be read is **absent, not empty**. A job",
                "with `junit_collection_failed: true` and no",
                "`test_failure_count` has an *unknown* number of test",
                "failures — do NOT report it as zero, and do not conclude a",
                "job failed for reasons other than its tests on this basis.",
                "",
            ])

        if failed_names:
            lines.append("### Failed blocking jobs")
            lines.append("")
            for n in failed_names:
                lines.append(f"  - `{n}`")
            lines.append("")

        lines.extend([
            "## File Layout",
            "",
            "```",
            f"{version}/{stream}/",
            "  summary.json              # START HERE — full triage data",
            "  CLAUDE.md                  # This file",
            "  streams.json              # All streams for this OCP version",
            f"  {tag}/                    # Target payload",
            "    payload.json            # Release controller API response",
            "    changelog.json          # PRs changed vs previous payload",
            "    regressions.json        # Test failure regression tracking",
            "    jobs/",
            "      blocking/",
            "        <job-name>/",
            "          job.json          # State, prow URL, GCS URL, retries",
            "          build_log.json    # Error/warning lines + log tail",
            "          junit/",
            "            results.json    # Parsed test failures",
            "            *.xml           # Raw JUnit XML",
            "      informing/",
            "        <job-name>/",
            "          job.json          # State and URLs only (no junit)",
            "    <component>/",
            "      prs/",
            "        <number>/",
            "          code.diff         # Full git diff",
            "          comments.json     # PR comments and reviews",
            "          jobs.json         # CI check runs",
            "    rpmdb/                    # RPMDB from RHCOS images",
            "      rhel-coreos/           # queryable with rpm --dbpath",
            "        rpmdb.sqlite",
            "      rhel-coreos-10/",
            "        rpmdb.sqlite",
            "  <older-payload-tag>/      # Each prior payload in the chain",
            "    ...                     # Same structure",
            "```",
            "",
            "## Key Concepts",
            "",
            "- **Blocking vs informing**: Only blocking job failures prevent",
            "  payload acceptance. Informing jobs are tracked but don't block.",
            "- **Chain**: The sequence of payloads walking backwards from the",
            "  target until one where all blocking jobs passed (the baseline).",
            "  Sippy's time-ordered tag list restores garbage-collected tags;",
            "  retained payload data comes from the release controller.",
            "- **Streaks**: Per-job consecutive failure count from the target",
            "  backwards. `failure_pattern` shows the full history (F=fail,",
            "  S=succeed) across the chain.",
            "- **Regressions**: Per-test tracking — when did each test failure",
            "  first appear? `first_failed_in` identifies the originating",
            "  payload, `payloads_failing` counts how many payloads it spans.",
            "- **Build log**: Error/warning lines extracted from the Prow",
            "  build-log.txt, plus the last 20% of the log for context.",
            "",
            "## summary.json Schema",
            "",
            "Top-level fields:",
            "- `payload_tag`, `phase`, `release_url`, `source`,",
            "  `architecture`, `stream`, `version`",
            "- `chain_length`, `baseline_tag`, `hours_since_baseline`",
            "- `blocking_jobs.failed_jobs[]` — each entry has: `name`,",
            "  `state`, `prow_url`, `gcs_url`, `streak` (with",
            "  `streak_length`, `originating_payload`, `is_new_failure`,",
            "  `failure_pattern`), `build_log_errors`, `test_failure_count`,",
            "  and relative paths to `job_json`, `junit_results`, `build_log`",
            "- `informing_jobs.failed_jobs[]` — job name strings only",
            "- `test_failures.blocking[]` — `test_name`, `jobs`,",
            "  `first_failed_in`, `payloads_failing`, `failure_message`,",
            "  `failure_text`",
            "- `payloads[]` — per-payload entries with `tag`, `phase`,",
            "  `source`, `changelog_source`, relative paths, `prs[]` with",
            "  component/diff/comments paths,",
            "  `rhcos_changes[]` with RPM diffs per RHCOS variant, and",
            "  `rhcos_rpms[]` with rpmdb.sqlite per variant",
            "- `rhcos_rpms[]` — RPMDB per RHCOS variant for the target",
            "  payload: `tag`, `name`, `pullspec`, `rpmdb` (relative path",
            "  to rpmdb.sqlite — queryable with rpm --dbpath <dir> or sqlite3)",
            "",
        ])

        _write_text(
            os.path.join(self.base_dir, "AGENTS.md"),
            "\n".join(lines),
        )
        _write_text(
            os.path.join(self.base_dir, "CLAUDE.md"),
            "@AGENTS.md\n",
        )

    def _compute_hours_since_baseline(self) -> Optional[float]:
        """Compute hours between target and baseline payload timestamps."""
        if len(self.chain) < 2:
            return None
        try:
            target_ts = _parse_tag_timestamp(self.chain[0])
            baseline_ts = _parse_tag_timestamp(self.chain[-1])
            if target_ts and baseline_ts:
                delta = target_ts - baseline_ts
                return round(delta.total_seconds() / 3600, 1)
        except (ValueError, IndexError):
            pass
        return None

    def _build_failed_job_details(self, lifecycle: str) -> list[dict]:
        """Build detailed entries for each failed job."""
        target_dir = os.path.join(self.base_dir, self.target_tag)
        lifecycle_dir = os.path.join(target_dir, "jobs", lifecycle)
        if not os.path.isdir(lifecycle_dir):
            return []

        details = []
        for job_name in sorted(os.listdir(lifecycle_dir)):
            job_data = _read_json(
                os.path.join(lifecycle_dir, job_name, "job.json")
            )
            if not job_data or job_data.get("state") == "Succeeded":
                continue

            tag_rel = self.target_tag
            entry: dict = {
                "name": job_name,
                "state": job_data.get("state", ""),
                "prow_url": job_data.get("url", ""),
                "gcs_url": job_data.get("gcs_url", ""),
                "is_aggregated": job_data.get("is_aggregated", False),
                "retries": job_data.get("retries", 0),
                "job_json": (
                    f"{tag_rel}/jobs/{lifecycle}/{job_name}/job.json"
                ),
            }

            rhcos = job_data.get("rhcos_version", "")
            if rhcos:
                entry["rhcos_version"] = rhcos

            streak_data = self.streaks.get(job_name)
            if streak_data:
                entry["streak"] = streak_data

            results_path = os.path.join(
                lifecycle_dir, job_name, "junit", "results.json"
            )
            if os.path.exists(results_path):
                entry["junit_results"] = (
                    f"{tag_rel}/jobs/{lifecycle}/{job_name}/junit/results.json"
                )
                results_data = _read_json(results_path) or []
                # Counts only results that could fail the job.  Flakes and
                # informing tests are listed by name under `test_failures`
                # but are deliberately not counted here — this number is the
                # failure count that drives triage.
                entry["test_failure_count"] = sum(
                    1 for t in results_data if _is_gating(t)
                )
                if _job_junit_state(
                    job_name, self.target_tag, "junit_partial"
                ):
                    # Real results, but not all of them: the count is a
                    # lower bound, not an authoritative total.
                    entry["junit_collection_partial"] = True
            elif any(
                _job_junit_state(job_name, self.target_tag, r)
                for r in ("junit_unavailable", "junit_missing",
                          "junit_unparseable")
            ):
                # Data could not be read.  Do NOT emit test_failure_count —
                # its absence means "unknown", where 0 would mean "clean".
                entry["junit_collection_failed"] = True

            build_log_path = os.path.join(
                lifecycle_dir, job_name, "build_log.json"
            )
            if os.path.exists(build_log_path):
                entry["build_log"] = (
                    f"{tag_rel}/jobs/{lifecycle}/{job_name}/build_log.json"
                )
                bl_data = _read_json(build_log_path)
                if bl_data:
                    entry["build_log_errors"] = bl_data.get(
                        "error_warning_count", 0
                    )

            details.append(entry)
        return details

    def _collect_non_gating(self, kind: str) -> list[dict]:
        """Collect the target payload's non-gating test results.

        ``kind`` is "flake" (failed then passed) or "informing" (opted out
        of gating via lifecycle). Neither can fail a job, so no regression
        onset is computed for them — an onset implies a culprit to find.
        """
        found: dict[str, dict] = {}
        lifecycle_dir = os.path.join(
            self.base_dir, self.target_tag, "jobs", "blocking"
        )
        if not os.path.isdir(lifecycle_dir):
            return []
        for job_name in sorted(os.listdir(lifecycle_dir)):
            results = _read_json(os.path.join(
                lifecycle_dir, job_name, "junit", "results.json"
            ))
            if not results:
                continue
            for test in results:
                name = test.get("name", "")
                if not name:
                    continue
                if kind == "flake":
                    match = test.get("status") == "flake"
                else:
                    match = (
                        test.get("status") in ("failed", "error")
                        and test.get("test_lifecycle") == "informing"
                    )
                if not match:
                    continue
                if name in found:
                    if job_name not in found[name]["jobs"]:
                        found[name]["jobs"].append(job_name)
                else:
                    found[name] = {"test_name": name, "jobs": [job_name]}
        return sorted(found.values(), key=lambda e: e["test_name"])

    def _build_payload_entries(self) -> list[dict]:
        """Build the payloads array with all path references."""
        payloads = []
        for tag_name in self.chain:
            tag_rel = tag_name
            entry: dict = {
                "tag": tag_name,
                "payload": f"{tag_rel}/payload.json",
            }

            pd = _read_json(
                os.path.join(self.base_dir, tag_name, "payload.json")
            )
            if pd:
                entry["phase"] = pd.get("phase", "")
                entry["source"] = pd.get("_source", "release-controller")

            changelog_path = os.path.join(
                self.base_dir, tag_name, "changelog.json"
            )
            if os.path.exists(changelog_path):
                entry["changelog"] = f"{tag_rel}/changelog.json"
                changelog = _read_json(changelog_path)
                if changelog:
                    entry["changelog_source"] = changelog.get(
                        "_source", "release-controller"
                    )
                prs = _extract_prs(changelog) if changelog else []
                if prs:
                    entry["prs"] = [
                        {
                            "url": p["url"],
                            "component": p["component"],
                            "number": p["number"],
                            "description": p["description"],
                            "diff": f"{tag_rel}/{p['component']}/prs/{p['number']}/code.diff",
                            "comments": f"{tag_rel}/{p['component']}/prs/{p['number']}/comments.json",
                            "jobs": f"{tag_rel}/{p['component']}/prs/{p['number']}/jobs.json",
                        }
                        for p in prs
                    ]
                rhcos_changes = _extract_rhcos_changes(changelog)
                if rhcos_changes:
                    entry["rhcos_changes"] = rhcos_changes
            regressions_path = os.path.join(
                self.base_dir, tag_name, "regressions.json"
            )
            if os.path.exists(regressions_path):
                entry["regressions"] = f"{tag_rel}/regressions.json"

            job_paths = self._collect_job_paths(tag_name)
            if job_paths:
                entry["jobs"] = job_paths

            rpmdb_entries = self.rpmdb_data.get(tag_name)
            if rpmdb_entries:
                entry["rhcos_rpms"] = [
                    {**e, "rpmdb": f"{tag_rel}/rpmdb/{e['tag']}/rpmdb.sqlite"}
                    for e in rpmdb_entries
                ]

            payloads.append(entry)
        return payloads

    def _collect_job_paths(self, tag_name: str) -> dict:
        """Build path references for jobs in a payload."""
        tag_rel = tag_name
        job_paths: dict = {"blocking": [], "informing": []}
        jobs_dir = os.path.join(self.base_dir, tag_name, "jobs")
        if not os.path.isdir(jobs_dir):
            return job_paths

        for lifecycle in ("blocking", "informing"):
            lifecycle_dir = os.path.join(jobs_dir, lifecycle)
            if not os.path.isdir(lifecycle_dir):
                continue
            for job_name in sorted(os.listdir(lifecycle_dir)):
                job_entry: dict = {
                    "name": job_name,
                    "job_json": f"{tag_rel}/jobs/{lifecycle}/{job_name}/job.json",
                }
                results_path = os.path.join(
                    lifecycle_dir, job_name, "junit", "results.json"
                )
                if os.path.exists(results_path):
                    job_entry["junit_results"] = (
                        f"{tag_rel}/jobs/{lifecycle}/{job_name}/junit/results.json"
                    )
                build_log_path = os.path.join(
                    lifecycle_dir, job_name, "build_log.json"
                )
                if os.path.exists(build_log_path):
                    job_entry["build_log"] = (
                        f"{tag_rel}/jobs/{lifecycle}/{job_name}/build_log.json"
                    )
                job_data = _read_json(
                    os.path.join(lifecycle_dir, job_name, "job.json")
                )
                if job_data:
                    job_entry["state"] = job_data.get("state", "")
                    job_entry["gcs_url"] = job_data.get("gcs_url", "")
                    rhcos = job_data.get("rhcos_version", "")
                    if rhcos:
                        job_entry["rhcos_version"] = rhcos
                job_paths[lifecycle].append(job_entry)

        return job_paths



# ---------------------------------------------------------------------------
# Snapshotter — top-level orchestrator
# ---------------------------------------------------------------------------

class Snapshotter:
    """Orchestrates the full payload snapshot."""

    def __init__(self, tag: PayloadTag, output_dir: str = "payload",
                 max_chain: int = 20, workers: int = 8,
                 collect_junit: bool = True, use_sippy: bool = False,
                 collect_rpmdb: bool = True):
        self.tag = tag
        self.output_dir = output_dir
        self.max_chain = max_chain
        self.workers = workers
        self.collect_junit = collect_junit
        self.use_sippy = use_sippy
        self.collect_rpmdb = collect_rpmdb
        self.rc = ReleaseController(tag.architecture, stream=tag.stream)
        self.sippy = SippyClient(
            tag.version, architecture=tag.architecture, stream=tag.stream
        )
        self._payload_sources: dict[str, str] = {}

    def run(self) -> None:
        """Execute the full snapshot."""
        base_dir = os.path.join(
            self.output_dir, self.tag.version, self.tag.stream
        )
        os.makedirs(base_dir, exist_ok=True)

        # A previous run over this directory may have left JUnit output it
        # recorded as incomplete.  Drop it so it is re-collected rather than
        # inherited as trustworthy — but only when we will actually
        # re-collect, otherwise we would delete the only copy and then
        # report the result as complete.
        if self.collect_junit:
            _invalidate_suspect_junit(base_dir)
        else:
            _carry_forward_junit_errors(base_dir)

        self._collect_streams(base_dir)

        chain = self._build_chain()
        _log(f"Payload chain: {len(chain)} payloads")
        for t in chain:
            _log(f"  {t}")

        pr_tasks = self._collect_payloads(base_dir, chain)

        self._collect_jobs(base_dir, chain)

        self._collect_prs(pr_tasks)

        if self.collect_junit:
            self._collect_junit(base_dir, chain)
            self._collect_build_logs(base_dir, chain)
            self._track_regressions(base_dir, chain)

        streaks = self._track_job_streaks(base_dir, chain)

        rpmdb_data = self._collect_rpmdb(base_dir, chain)

        self._generate_summary(base_dir, chain, streaks,
                               rpmdb_data=rpmdb_data)

        _log(f"\nSnapshot complete: {base_dir}/")

    def _collect_streams(self, base_dir: str) -> None:
        """Collect the streams list for this version."""
        path = os.path.join(base_dir, "streams.json")
        if self.use_sippy:
            if os.path.exists(path):
                return
            _log("Skipping streams collection in Sippy mode (RC-only feature)")
            _write_json(path, [])
            return
        StreamsCollector(path, self.tag.version).collect()

    def _build_chain(self) -> list[str]:
        """Build the backward payload chain."""
        if self.use_sippy:
            chain_builder = SippyPayloadChain(self.sippy, self.max_chain)
            chain = chain_builder.build(self.tag.raw)
            self._payload_sources = {tag: "sippy" for tag in chain}
            return chain
        chain_builder = HybridPayloadChain(
            self.rc, self.sippy, self.tag.stream_name, self.max_chain
        )
        chain = chain_builder.build(self.tag.raw)
        self._payload_sources = chain_builder.sources
        return chain

    def _payload_source(self, tag_name: str) -> str:
        if self.use_sippy:
            return "sippy"
        return self._payload_sources.get(tag_name, "release-controller")

    def _collect_payloads(
        self, base_dir: str, chain: list[str]
    ) -> list[PullRequestCollector]:
        """Collect payload details and changelogs; return PR collectors."""
        seen_prs: set[tuple[str, str, int]] = set()
        pr_collectors: list[PullRequestCollector] = []

        for i, tag_name in enumerate(chain):
            tag_dir = os.path.join(base_dir, tag_name)
            _log(f"\nProcessing payload: {tag_name}")

            payload_path = os.path.join(tag_dir, "payload.json")
            payload_source = self._payload_source(tag_name)
            if payload_source == "sippy":
                if not os.path.exists(payload_path):
                    _log(f"  Fetching payload details from Sippy: {tag_name}")
                    tag_obj = PayloadTag.parse(tag_name)
                    data = self.sippy.build_synthetic_payload(tag_name, tag_obj)
                    os.makedirs(os.path.dirname(payload_path), exist_ok=True)
                    _write_json(payload_path, data)
                else:
                    _log(f"  skip (exists): {payload_path}")
            else:
                PayloadDetailCollector(
                    payload_path,
                    self.rc, self.tag.stream_name, tag_name,
                ).collect()

            if i >= len(chain) - 1:
                continue

            prev_tag = chain[i + 1]
            changelog_path = os.path.join(tag_dir, "changelog.json")
            # The release controller cannot diff across a tag it has already
            # garbage collected. Use Sippy's incremental diff (with its
            # per-payload PR fallback) whenever either side is unavailable.
            changelog_source = (
                "release-controller"
                if payload_source == "release-controller"
                and self._payload_source(prev_tag) == "release-controller"
                else "sippy"
            )
            if changelog_source == "sippy":
                if not os.path.exists(changelog_path):
                    _log(f"  Fetching changelog from Sippy: {tag_name}")
                    data = self.sippy.build_synthetic_changelog(
                        tag_name, from_tag=prev_tag
                    )
                    os.makedirs(os.path.dirname(changelog_path), exist_ok=True)
                    _write_json(changelog_path, data)
                else:
                    _log(f"  skip (exists): {changelog_path}")
            else:
                ChangelogCollector(
                    changelog_path, self.rc,
                    self.tag.stream_name, tag_name, prev_tag,
                ).collect()

            changelog = _read_json(changelog_path)
            if not changelog:
                continue

            prs = _extract_prs(changelog)
            for pr in prs:
                key = (pr["org"], pr["repo"], pr["number"])
                if key in seen_prs:
                    continue
                seen_prs.add(key)
                pr_dir = os.path.join(
                    tag_dir, pr["component"], "prs", str(pr["number"])
                )
                pr_collectors.append(
                    PullRequestCollector(pr_dir, pr["org"], pr["repo"], pr["number"])
                )

        return pr_collectors

    def _collect_prs(self, collectors: list[PullRequestCollector]) -> None:
        """Fetch PR artifacts in parallel."""
        if not collectors:
            _log("\nNo PRs to fetch.")
            return

        _log(f"\nFetching {len(collectors)} unique PRs ({self.workers} workers)...")

        with ThreadPoolExecutor(max_workers=self.workers) as pool:
            futures = {
                pool.submit(c.collect): c for c in collectors
            }
            done = 0
            for future in as_completed(futures):
                done += 1
                collector = futures[future]
                label = f"{collector.org}/{collector.repo}#{collector.pr_number}"
                try:
                    future.result()
                    _log(f"  [{done}/{len(collectors)}] {label}")
                except Exception as e:
                    _log(f"  [{done}/{len(collectors)}] {label}: error: {e}")

    def _collect_jobs(self, base_dir: str, chain: list[str]) -> None:
        """Split payload.json jobs into individual job directories."""
        _log("\nSplitting jobs into directories...")
        for tag_name in chain:
            tag_dir = os.path.join(base_dir, tag_name)
            payload_path = os.path.join(tag_dir, "payload.json")
            payload_data = _read_json(payload_path)
            if not payload_data:
                continue

            jobs = _extract_jobs(payload_data, self.tag.version)
            for job in jobs:
                job_path = os.path.join(
                    tag_dir, "jobs", job.lifecycle, job.name, "job.json"
                )
                JobCollector(job_path, job).collect()

            blocking_count = sum(1 for j in jobs if j.lifecycle == "blocking")
            informing_count = sum(1 for j in jobs if j.lifecycle == "informing")
            _log(f"  {tag_name}: {blocking_count} blocking, "
                 f"{informing_count} informing")

    def _find_failed_jobs(
        self, base_dir: str, chain: list[str],
        lifecycles: tuple[str, ...] = ("blocking",),
    ) -> list[tuple[str, str, JobInfo]]:
        """Find failed jobs across the chain for the given lifecycles.

        Returns (tag_name, job_dir, JobInfo) tuples.
        """
        results = []
        for tag_name in chain:
            tag_dir = os.path.join(base_dir, tag_name)
            for lifecycle in lifecycles:
                jobs_dir = os.path.join(tag_dir, "jobs", lifecycle)
                if not os.path.isdir(jobs_dir):
                    continue
                for job_name in os.listdir(jobs_dir):
                    job_json_path = os.path.join(
                        jobs_dir, job_name, "job.json"
                    )
                    job_data = _read_json(job_json_path)
                    if not job_data:
                        continue
                    if job_data.get("state") == "Succeeded":
                        continue
                    job_info = JobInfo(
                        name=job_data["name"],
                        state=job_data["state"],
                        lifecycle=job_data["lifecycle"],
                        url=job_data["url"],
                        retries=job_data.get("retries", 0),
                        previous_attempt_urls=job_data.get(
                            "previousAttemptURLs", []
                        ),
                        is_aggregated=job_data.get("is_aggregated", False),
                        gcs_bucket_path=job_data.get("gcs_bucket_path", ""),
                        gcs_url=job_data.get("gcs_url", ""),
                    )
                    job_dir = os.path.join(jobs_dir, job_name)
                    results.append((tag_name, job_dir, job_info))
        return results

    def _collect_junit(self, base_dir: str, chain: list[str]) -> None:
        """Download and parse JUnit for failed jobs across the chain.

        Blocking jobs: all payloads in chain (for streak/regression tracking).
        Informing jobs: target payload only (first in chain).
        """
        collectors: list[JUnitCollector] = []

        for tag_name, job_dir, job_info in self._find_failed_jobs(
            base_dir, chain, ("blocking",)
        ):
            junit_dir = os.path.join(job_dir, "junit")
            collectors.append(
                JUnitCollector(junit_dir, job_info, tag_name)
            )

        for tag_name, job_dir, job_info in self._find_failed_jobs(
            base_dir, chain[:1], ("informing",)
        ):
            junit_dir = os.path.join(job_dir, "junit")
            collectors.append(
                JUnitCollector(junit_dir, job_info, tag_name)
            )

        if not collectors:
            _log("\nNo failed jobs to fetch JUnit for.")
            return

        _log(f"\nFetching JUnit for {len(collectors)} failed jobs "
             f"({self.workers} workers)...")

        with ThreadPoolExecutor(max_workers=self.workers) as pool:
            futures = {
                pool.submit(c.collect): c for c in collectors
            }
            done = 0
            for future in as_completed(futures):
                done += 1
                collector = futures[future]
                try:
                    future.result()
                    _log(f"  [{done}/{len(collectors)}] {collector.job.name}")
                except Exception as e:
                    _log(f"  [{done}/{len(collectors)}] "
                         f"{collector.job.name}: error: {e}")

    def _track_regressions(self, base_dir: str, chain: list[str]) -> None:
        """Track test failure regressions across the payload chain."""
        _log("\nTracking test failure regressions...")
        target_tag = chain[0]
        regressions_path = os.path.join(
            base_dir, target_tag, "regressions.json"
        )

        if os.path.exists(regressions_path):
            _log(f"  skip (exists): {regressions_path}")
            return

        tracker = RegressionTracker(base_dir, chain, target_tag)
        regressions = tracker.track()
        _write_json(regressions_path, regressions)

        new_count = sum(1 for r in regressions if r["payloads_failing"] == 1)
        persistent_count = len(regressions) - new_count
        _log(f"  Found {len(regressions)} gating test failures: "
             f"{new_count} new, {persistent_count} persistent")
        skipped = tracker.non_gating_counts()
        if skipped["flake"] or skipped["informing"]:
            _log(f"  Excluded from regression tracking: "
                 f"{skipped['flake']} flake(s), "
                 f"{skipped['informing']} informing failure(s) — neither can "
                 f"fail a job")

    def _collect_build_logs(self, base_dir: str, chain: list[str]) -> None:
        """Download and parse build-log.txt for failed jobs.

        Blocking jobs: all payloads in chain.
        Informing jobs: target payload only (first in chain).
        """
        collectors: list[BuildLogCollector] = []

        for _tag_name, job_dir, job_info in self._find_failed_jobs(
            base_dir, chain, ("blocking",)
        ):
            build_log_path = os.path.join(job_dir, "build_log.json")
            collectors.append(
                BuildLogCollector(build_log_path, job_info)
            )

        for _tag_name, job_dir, job_info in self._find_failed_jobs(
            base_dir, chain[:1], ("informing",)
        ):
            build_log_path = os.path.join(job_dir, "build_log.json")
            collectors.append(
                BuildLogCollector(build_log_path, job_info)
            )

        if not collectors:
            _log("\nNo failed jobs for build-log extraction.")
            return

        _log(f"\nExtracting build logs for {len(collectors)} failed "
             f"jobs ({self.workers} workers)...")

        with ThreadPoolExecutor(max_workers=self.workers) as pool:
            futures = {
                pool.submit(c.collect): c for c in collectors
            }
            done = 0
            for future in as_completed(futures):
                done += 1
                collector = futures[future]
                try:
                    future.result()
                    _log(f"  [{done}/{len(collectors)}] {collector.job.name}")
                except Exception as e:
                    _log(f"  [{done}/{len(collectors)}] "
                         f"{collector.job.name}: error: {e}")

    def _track_job_streaks(
        self, base_dir: str, chain: list[str]
    ) -> dict[str, dict]:
        """Track per-job failure streaks across the payload chain."""
        _log("\nTracking job failure streaks...")
        tracker = JobStreakTracker(base_dir, chain)
        streaks = tracker.track()
        new_count = sum(1 for s in streaks.values() if s["is_new_failure"])
        _log(f"  {len(streaks)} failed jobs: {new_count} new, "
             f"{len(streaks) - new_count} persistent")
        return streaks

    def _get_pullspec_map(self, chain: list[str]) -> dict[str, str]:
        """Map tag names to release image pullSpecs via the tags API."""
        chain_set = set(chain)
        tags = self.rc.fetch_tags(self.tag.stream_name)
        return {
            t["name"]: t["pullSpec"]
            for t in tags
            if t.get("name") in chain_set and t.get("pullSpec")
        }

    def _collect_rpmdb(
        self, base_dir: str, chain: list[str]
    ) -> dict[str, list[dict]]:
        """Extract RPMDB from RHCOS images for each payload in the chain."""
        if not self.collect_rpmdb:
            return {}
        if self.use_sippy:
            _log("\nSkipping RPMDB: not available in Sippy mode")
            return {}

        try:
            pullspec_map = self._get_pullspec_map(chain)
        except (urllib.error.HTTPError, urllib.error.URLError) as e:
            _log(f"\nSkipping RPMDB: could not fetch pullSpecs: {e}")
            return {}
        if not pullspec_map:
            _log("\nSkipping RPMDB: no pullSpecs found")
            return {}

        items = []
        for tag_name in chain:
            pullspec = pullspec_map.get(tag_name)
            if not pullspec:
                continue
            rpmdb_dir = os.path.join(base_dir, tag_name, "rpmdb")
            items.append(
                (tag_name, RpmdbCollector(rpmdb_dir, pullspec, tag_name))
            )

        if not items:
            return {}

        workers = min(self.workers, 4)
        _log(f"\nExtracting RPMDB from RHCOS images "
             f"({len(items)} payloads, {workers} workers)...")
        rpmdb_data: dict[str, list[dict]] = {}

        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {
                pool.submit(c.collect): (tag_name, c)
                for tag_name, c in items
            }
            done = 0
            for future in as_completed(futures):
                done += 1
                tag_name, _ = futures[future]
                try:
                    summaries = future.result()
                    if summaries:
                        rpmdb_data[tag_name] = summaries
                    _log(f"  [{done}/{len(items)}] {tag_name}")
                except Exception as e:
                    _log(f"  [{done}/{len(items)}] {tag_name}: error: {e}")

        return rpmdb_data

    def _generate_summary(
        self, base_dir: str, chain: list[str],
        streaks: Optional[dict] = None,
        rpmdb_data: Optional[dict[str, list[dict]]] = None,
    ) -> None:
        """Generate the stream-level summary."""
        _log("\nGenerating summary...")
        summary_path = os.path.join(base_dir, "summary.json")
        if os.path.exists(summary_path):
            os.remove(summary_path)

        generator = SummaryGenerator(
            base_dir, chain, chain[0], self.tag, streaks=streaks,
            rpmdb_data=rpmdb_data,
        )
        generator.generate()


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------

def _log(msg: str) -> None:
    """Print a progress message to stderr."""
    print(msg, file=sys.stderr)


def _write_json(path: str, data: Any) -> None:
    """Write JSON data to a file."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


def _write_text(path: str, text: str) -> None:
    """Write text to a file."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def _read_json(path: str) -> Optional[dict]:
    """Read a JSON file, returning None if it doesn't exist."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def _parse_tag_timestamp(tag: str) -> Optional[datetime]:
    """Extract and parse the timestamp from a payload tag name."""
    m = re.search(r"(\d{4}-\d{2}-\d{2}-\d{6})$", tag)
    if not m:
        return None
    try:
        return datetime.strptime(m.group(1), "%Y-%m-%d-%H%M%S").replace(
            tzinfo=timezone.utc
        )
    except ValueError:
        return None


def _build_stream_name(version: str, stream: str, architecture: str) -> str:
    """Build the release stream name from components."""
    name = f"{version}.0-0.{stream}"
    if architecture != "amd64":
        name += f"-{architecture}"
    return name


def _run_gh(args: list[str], timeout: int = 60) -> Optional[str]:
    """Run a gh CLI command, returning stdout or None on error."""
    try:
        result = subprocess.run(
            args, capture_output=True, text=True, timeout=timeout
        )
        if result.returncode != 0:
            _log(f"    warning: {' '.join(args[:5])}... failed: "
                 f"{result.stderr.strip()[:200]}")
            return None
        return result.stdout
    except subprocess.TimeoutExpired:
        _log(f"    warning: {' '.join(args[:5])}... timed out")
        return None
    except FileNotFoundError:
        _log("    error: 'gh' CLI not found — install it or run 'gh auth login'")
        return None


def _extract_prs(changelog: dict) -> list[dict]:
    """Extract PR info from a release controller changelog response."""
    prs = []
    images = changelog.get("changeLogJson", {}).get("updatedImages", []) or []
    for image in images:
        component = image.get("name", "")
        for commit in image.get("commits", []):
            pull_url = commit.get("pullURL", "")
            parsed = _parse_pr_url(pull_url)
            if parsed:
                org, repo, number = parsed
                prs.append({
                    "org": org,
                    "repo": repo,
                    "number": number,
                    "component": component,
                    "description": commit.get("subject", ""),
                    "url": pull_url,
                })
    return prs


def _extract_rhcos_changes(changelog: dict) -> list[dict]:
    """Extract RHCOS RPM diff data from the changelog's nodeImageStreams."""
    if not changelog:
        return []

    results = []
    for stream in changelog.get("nodeImageStreams") or []:
        rpm_diff = stream.get("rpmDiff") or {}
        if not any(rpm_diff.get(k) for k in ("changed", "added", "removed")):
            continue
        results.append({
            "name": stream.get("name", ""),
            "tag": stream.get("tag", ""),
            "changed": rpm_diff.get("changed", {}),
            "added": rpm_diff.get("added", {}),
            "removed": rpm_diff.get("removed", {}),
        })
    return results


def _parse_pr_url(url: str) -> Optional[tuple[str, str, int]]:
    """Parse a GitHub PR URL into (org, repo, pr_number)."""
    m = re.match(r"https://github\.com/([^/]+)/([^/]+)/pull/(\d+)", url)
    if m:
        return m.group(1), m.group(2), int(m.group(3))
    return None


def _check_gh_auth() -> bool:
    """Verify that gh CLI is authenticated."""
    try:
        result = subprocess.run(
            ["gh", "auth", "status"],
            capture_output=True, text=True, timeout=10,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


# Records every gcloud failure that could hide real data.  A "no match"
# result is normal (the object simply does not exist) and is NOT recorded.
# Anything else — a missing binary, a timeout, an auth failure — means the
# snapshot could not read data that may well exist, and callers must be able
# to tell that apart from "there was nothing to find".
_COLLECTION_ERRORS: list[dict] = []
_COLLECTION_ERRORS_LOCK = threading.Lock()

# Per-thread stack of "operation scopes".  Every recorded error is appended
# to each active scope as well as the global ledger, so a caller can act on
# exactly the errors *its own* calls produced.  Positional indexes into the
# global list are not safe here: collectors run concurrently, so another
# worker can append between one collector's start and end offsets.
_ERROR_SCOPES = threading.local()

# stderr fragments that mean "the object does not exist", not "I failed".
# Keep this narrow: only the specific gcloud "URLs matched no objects"
# outcome is benign.  Broad tokens like "not found" would swallow 404s
# and bucket-not-found errors that should be recorded.
_GCLOUD_NO_MATCH_PATTERNS = (
    "matched no objects",
    "matched no such objects",
)

# stderr fragments that indicate a credentials/permission problem.
_GCLOUD_AUTH_PATTERNS = (
    "does not have storage.objects",
    "anonymous caller",
    "reauthentication",
    "credentials",
    "unauthorized",
    "forbidden",
    "403",
    "401",
)


def _error_scope():
    """Collect errors recorded by this thread inside the ``with`` body."""
    return _ErrorScope()


class _ErrorScope:
    """Context manager yielding the list of errors recorded inside it."""

    def __init__(self) -> None:
        self.entries: list[dict] = []

    def __enter__(self) -> list[dict]:
        stack = getattr(_ERROR_SCOPES, "stack", None)
        if stack is None:
            stack = []
            _ERROR_SCOPES.stack = stack
        stack.append(self.entries)
        return self.entries

    def __exit__(self, *exc) -> None:
        getattr(_ERROR_SCOPES, "stack", []).pop()
        return None


def _sanitize_detail(text: str) -> str:
    """Make tool stderr safe to persist in a shareable summary.

    Strips control characters (which can spoof terminal output when the
    summary is read back) and collapses whitespace.  Diagnostics are
    truncated: they exist to identify a failure class, not to carry full
    tool output.
    """
    cleaned = "".join(
        ch if ch.isprintable() else " " for ch in (text or "")
    )
    # These diagnostics are persisted into a summary this skill exists to
    # hand to agents and share.  gcloud auth errors routinely name the
    # active account, and URLs can carry signed-request parameters; neither
    # should leave the local environment.
    cleaned = re.sub(
        r"[\w.+-]+@[\w-]+\.[\w.-]+", "<redacted-account>", cleaned
    )
    cleaned = re.sub(r"\?\S+", "?<redacted-query>", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()[:300]


def _classify_gcloud_stderr(stderr: str) -> str:
    """Classify a failed gcloud invocation from its stderr."""
    low = (stderr or "").lower()
    if any(p in low for p in _GCLOUD_AUTH_PATTERNS):
        return "auth"
    if any(p in low for p in _GCLOUD_NO_MATCH_PATTERNS):
        return "no_match"
    return "command_failed"


def _record_collection_error(
    reason: str,
    command: list[str],
    detail: str = "",
    stage: str = "",
    job: str = "",
    payload_tag: str = "",
) -> None:
    """Record a data-collection failure so it can be surfaced, not swallowed.

    Silently returning empty data makes "I could not read this" look
    identical to "there is nothing here", which invites downstream
    consumers to report zero failures for a job that actually failed.
    """
    entry: dict = {"reason": reason, "command": " ".join(command[:4])}
    if detail:
        entry["detail"] = _sanitize_detail(detail)
    if stage:
        entry["stage"] = stage
    if job:
        entry["job"] = job
    if payload_tag:
        entry["payload_tag"] = payload_tag
    with _COLLECTION_ERRORS_LOCK:
        _COLLECTION_ERRORS.append(entry)
    for scope in getattr(_ERROR_SCOPES, "stack", []):
        scope.append(entry)


def _collection_error_count() -> int:
    """Number of collection errors recorded so far."""
    return len(_COLLECTION_ERRORS)


COLLECTION_STATE_FILE = "collection_errors.json"

# Reasons that make a job's persisted JUnit output untrustworthy.
_JUNIT_SUSPECT_REASONS = (
    "junit_unavailable", "junit_partial", "junit_missing",
    "junit_unparseable",
)


def _is_within(base: str, target: str) -> bool:
    """True when ``target`` resolves inside ``base``."""
    base_r = os.path.realpath(base)
    target_r = os.path.realpath(target)
    return target_r == base_r or target_r.startswith(base_r + os.sep)


def _safe_component(value: str) -> bool:
    """True when ``value`` is usable as a single path component."""
    return bool(value) and value not in (".", "..") and not any(
        sep in value for sep in (os.sep, "/", "\\")
    )


def _invalidate_suspect_junit(base_dir: str) -> int:
    """Discard JUnit output that a previous run recorded as incomplete.

    Collection errors live in process memory but ``results.json`` persists,
    and collectors skip any job whose output already exists.  Without this,
    re-running over the same directory regenerates the summary from an empty
    ledger and promotes a partial snapshot to "complete".  Dropping the
    suspect output forces it to be re-collected and re-judged.
    """
    state_path = os.path.join(base_dir, COLLECTION_STATE_FILE)
    previous = _read_json(state_path)
    if not previous:
        return 0

    invalidated = 0
    invalidated_tags: set[str] = set()
    for entry in previous:
        if entry.get("recovered"):
            continue
        if entry.get("reason") not in _JUNIT_SUSPECT_REASONS:
            continue
        tag, job = entry.get("payload_tag"), entry.get("job")
        # The ledger is data read back from disk; never let it aim a
        # recursive delete at a path outside the snapshot directory.
        if not _safe_component(tag or "") or not _safe_component(job or ""):
            _log(f"  warn: ignoring unsafe collection-state entry "
                 f"(tag={tag!r}, job={job!r})")
            continue
        for lifecycle in ("blocking", "informing"):
            junit_dir = os.path.join(
                base_dir, tag, "jobs", lifecycle, job, "junit"
            )
            if not _is_within(base_dir, junit_dir):
                continue
            if os.path.isdir(junit_dir):
                shutil.rmtree(junit_dir, ignore_errors=True)
                invalidated += 1
                invalidated_tags.add(tag)
    for tag in invalidated_tags:
        reg_path = os.path.join(base_dir, tag, "regressions.json")
        if _is_within(base_dir, reg_path) and os.path.exists(reg_path):
            os.remove(reg_path)
            _log(f"  removed stale regressions.json for {tag}")
    if invalidated:
        _log(f"  re-collecting {invalidated} job(s) whose previous JUnit "
             f"collection was incomplete")
    return invalidated


def _carry_forward_junit_errors(base_dir: str) -> int:
    """Re-record persisted JUnit failures when JUnit is not re-collected.

    With ``--no-junit`` nothing re-reads the artifacts, so a previous run's
    partial or unreadable JUnit is still exactly as incomplete as it was.
    Without carrying those errors forward, the ledger would be rewritten
    from an empty in-memory list and the stale output would be reported as
    a complete snapshot.
    """
    previous = _read_json(
        os.path.join(base_dir, COLLECTION_STATE_FILE)
    ) or []
    carried = 0
    for entry in previous:
        if entry.get("recovered"):
            continue
        if entry.get("reason") not in _JUNIT_SUSPECT_REASONS:
            continue
        forwarded = dict(entry)
        forwarded["carried_forward"] = True
        with _COLLECTION_ERRORS_LOCK:
            _COLLECTION_ERRORS.append(forwarded)
        carried += 1
    if carried:
        _log(f"  carrying forward {carried} unresolved JUnit collection "
             f"error(s) from a previous run (JUnit collection is disabled)")
    return carried


def _write_collection_state(base_dir: str) -> None:
    """Persist the error ledger so a later process can see it."""
    state_path = os.path.join(base_dir, COLLECTION_STATE_FILE)
    if _COLLECTION_ERRORS:
        _write_json(state_path, list(_COLLECTION_ERRORS))
    elif os.path.exists(state_path):
        # Everything was collected this time; drop the stale ledger.
        os.remove(state_path)


def _mark_errors_recovered(entries: list[dict]) -> None:
    """Mark the given error entries as recovered.

    A first-choice read can fail (e.g. a glob times out) and a fallback
    can then succeed.  The failure is still worth reporting — it is how
    you learn a timeout needs tuning — but it must not make the snapshot
    look incomplete when the data was in fact obtained.

    Entries are identified by object, not by position: only the specific
    failures handed in are recovered, never a concurrent collector's.
    """
    for entry in entries:
        entry["recovered"] = True


def _unrecovered_errors() -> list[dict]:
    """Collection errors that were not resolved by a fallback."""
    return [e for e in _COLLECTION_ERRORS if not e.get("recovered")]


def _unrecovered_error_count() -> int:
    """Number of unrecovered collection errors."""
    return len(_unrecovered_errors())


def _job_junit_state(job_name: str, payload_tag: str, reason: str) -> bool:
    """True when this payload's collection of this job hit ``reason``.

    Scoped by payload tag: the same job name recurs in every payload of
    the chain, so an unscoped match would stamp one payload's job entry
    with another payload's failure.
    """
    return any(
        e.get("job") == job_name
        and e.get("payload_tag") == payload_tag
        and e.get("reason") == reason
        and not e.get("recovered")
        for e in _COLLECTION_ERRORS
    )


# Whether gcloud must be run in anonymous mode.  Resolved once, on first
# use, under a lock — collectors run in a thread pool.
_GCLOUD_ANONYMOUS: Optional[bool] = None
_GCLOUD_ANONYMOUS_LOCK = threading.Lock()


def _gcloud_env() -> dict:
    """Environment for gcloud calls, enabling anonymous access if needed.

    The CI artifact buckets are public, but ``gcloud storage`` refuses
    client-side when no account is configured ("You do not currently have
    an active account selected") — it never even issues the request.
    Setting ``CLOUDSDK_AUTH_DISABLE_CREDENTIALS`` makes it read public
    objects anonymously, so an unauthenticated environment still gets a
    complete snapshot instead of an empty one.
    """
    global _GCLOUD_ANONYMOUS
    if _GCLOUD_ANONYMOUS is None:
        with _GCLOUD_ANONYMOUS_LOCK:
            if _GCLOUD_ANONYMOUS is None:
                anonymous = not _check_gcloud_credentials()
                if anonymous:
                    _log("  note: no gcloud credentials found — reading "
                         "public artifact buckets anonymously")
                _GCLOUD_ANONYMOUS = anonymous
    env = os.environ.copy()
    if _GCLOUD_ANONYMOUS:
        env["CLOUDSDK_AUTH_DISABLE_CREDENTIALS"] = "true"
    return env


def _run_gcloud(args: list[str], timeout: int = 120) -> Optional[str]:
    """Run a gcloud CLI command, returning stdout or None on error.

    Failures other than "no such object" are recorded in
    ``_COLLECTION_ERRORS`` so callers can distinguish an unreadable
    source from an empty one.
    """
    try:
        result = subprocess.run(
            args, capture_output=True, text=True, timeout=timeout,
            env=_gcloud_env(),
        )
        if result.returncode != 0:
            reason = _classify_gcloud_stderr(result.stderr)
            if reason != "no_match":
                _record_collection_error(reason, args, detail=result.stderr)
            return None
        return result.stdout
    except subprocess.TimeoutExpired:
        _record_collection_error(
            "timeout", args, detail=f"exceeded {timeout}s"
        )
        return None
    except FileNotFoundError:
        _record_collection_error("gcloud_missing", args)
        return None


def _run_gcloud_bytes(args: list[str], timeout: int = 120) -> Optional[bytes]:
    """Run a gcloud CLI command, returning raw stdout bytes or None.

    Records failures the same way as :func:`_run_gcloud`.
    """
    try:
        result = subprocess.run(
            args, capture_output=True, timeout=timeout, env=_gcloud_env()
        )
        if result.returncode != 0:
            stderr = (result.stderr or b"").decode("utf-8", errors="replace")
            reason = _classify_gcloud_stderr(stderr)
            if reason != "no_match":
                _record_collection_error(reason, args, detail=stderr)
            return None
        return result.stdout
    except subprocess.TimeoutExpired:
        _record_collection_error(
            "timeout", args, detail=f"exceeded {timeout}s"
        )
        return None
    except FileNotFoundError:
        _record_collection_error("gcloud_missing", args)
        return None


def _check_gcloud() -> bool:
    """Verify that gcloud CLI is available."""
    try:
        result = subprocess.run(
            ["gcloud", "--version"],
            capture_output=True, text=True, timeout=10,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def _check_gcloud_credentials() -> bool:
    """Report whether gcloud has an active credential.

    ``gcloud --version`` only proves the binary exists.  An installed but
    unauthenticated gcloud passes that check and then fails every read,
    which previously produced a snapshot full of silently empty JUnit
    data.  Public buckets can still be read anonymously, so a negative
    result here is a warning rather than a hard failure.
    """
    try:
        result = subprocess.run(
            ["gcloud", "auth", "list",
             "--filter=status:ACTIVE", "--format=value(account)"],
            capture_output=True, text=True, timeout=15,
        )
        return result.returncode == 0 and bool(result.stdout.strip())
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def _check_podman() -> bool:
    """Verify that podman is available and functional.

    Goes beyond --version: runs 'podman info' which exercises the runtime,
    storage, and namespace setup.  This catches cases where podman is
    installed but cannot operate (e.g. nested containers without
    appropriate privileges).  On failure, stdout/stderr from the probe are
    logged so the underlying runtime error (e.g. a namespace or storage
    driver failure under nested podman) is visible instead of a bare
    "not available" message.
    """
    try:
        result = subprocess.run(
            ["podman", "info"],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            _log(f"'podman info' exited {result.returncode}.")
            if result.stdout.strip():
                _log(f"stdout:\n{result.stdout.strip()}")
            if result.stderr.strip():
                _log(f"stderr:\n{result.stderr.strip()}")
        return result.returncode == 0
    except subprocess.TimeoutExpired as e:
        _log("'podman info' timed out after 30s.")
        if e.stdout:
            stdout = e.stdout if isinstance(e.stdout, str) else e.stdout.decode(errors="replace")
            if stdout.strip():
                _log(f"stdout:\n{stdout.strip()}")
        if e.stderr:
            stderr = e.stderr if isinstance(e.stderr, str) else e.stderr.decode(errors="replace")
            if stderr.strip():
                _log(f"stderr:\n{stderr.strip()}")
        return False
    except OSError as e:
        _log(f"'podman info' could not be run: {e}")
        return False


def _run_podman(
    args: list[str], timeout: int = 300
) -> Optional[subprocess.CompletedProcess]:
    """Run a podman CLI command, logging failures.

    Returns the CompletedProcess (check .returncode — a nonzero exit is
    already logged but not treated as failure here) or None if the
    command couldn't even be run.
    """
    try:
        result = subprocess.run(
            args, capture_output=True, text=True, timeout=timeout
        )
        if result.returncode != 0:
            _log(f"    podman command failed (exit {result.returncode}): "
                 f"{' '.join(args)}")
            stderr = result.stderr.strip()
            if stderr:
                _log(f"    stderr: {stderr}")
        return result
    except subprocess.TimeoutExpired as e:
        _log(f"    podman command timed out after {timeout}s: {' '.join(args)}")
        if e.stderr:
            stderr = e.stderr if isinstance(e.stderr, str) else e.stderr.decode(errors="replace")
            if stderr.strip():
                _log(f"    stderr: {stderr.strip()}")
        return None
    except OSError as e:
        _log(f"    podman command failed to start: {' '.join(args)}: {e}")
        return None


def _prow_url_to_gcs_bucket_path(prow_url: str) -> Optional[str]:
    """Extract the GCS bucket path from a Prow URL.

    Returns 'test-platform-results/logs/{job}/{build_id}' or None.
    """
    if not prow_url or not prow_url.startswith(PROW_VIEW_PREFIX):
        return None
    return prow_url[len(PROW_VIEW_PREFIX):]


def _extract_jobs(payload_data: dict, version: str = "") -> list[JobInfo]:
    """Extract job metadata from a payload.json response."""
    jobs = []
    for lifecycle, key in [("blocking", "blockingJobs"),
                           ("informing", "informingJobs")]:
        job_dict = payload_data.get("results", {}).get(key, {}) or {}
        for name, info in job_dict.items():
            url = info.get("url", "")
            gcs_path = _prow_url_to_gcs_bucket_path(url) or ""
            gcs_url = f"{GCSWEB_BASE}/{gcs_path}/" if gcs_path else ""
            rhcos = _determine_rhcos_version(name, version) if version else ""
            jobs.append(JobInfo(
                name=name,
                state=info.get("state", ""),
                lifecycle=lifecycle,
                url=url,
                retries=info.get("retries", 0),
                previous_attempt_urls=info.get("previousAttemptURLs", []) or [],
                is_aggregated=name.startswith("aggregated-"),
                gcs_bucket_path=gcs_path,
                gcs_url=gcs_url,
                rhcos_version=rhcos,
            ))
    return jobs


def _determine_rhcos_version(job_name: str, version: str) -> str:
    """Determine RHCOS version for a job based on its name and OCP version.

    Checks job name fragments in priority order (first match wins):
      1. rhcos9_10 -> heterogeneous (mixed RHCOS 9 and 10)
      2. rhcos10   -> RHCOS 10
      3. rhcos9    -> RHCOS 9 (explicit)
      4. no match  -> default by OCP major version at install time

    For upgrade jobs, the install-time OCP version determines the default,
    not the payload version.  Major upgrades in a 5.x payload install 4.x.
    """
    if "rhcos9_10" in job_name:
        return "rhcos9_10"
    if "rhcos10" in job_name:
        return "rhcos10"
    if "rhcos9" in job_name:
        return "rhcos9"

    install_version = version
    if "upgrade" in job_name and "major" in job_name:
        major = int(version.split(".")[0])
        if major >= 5:
            install_version = f"{major - 1}.{version.split('.')[1]}"

    major = int(install_version.split(".")[0])
    if major >= 5:
        return "rhcos10-default"
    return "rhcos9-default"


# ---------------------------------------------------------------------------
# JUnit XML parsing (embedded from parse_junit.py)
# ---------------------------------------------------------------------------

@dataclass
class _TestResult:
    """Parsed test result from JUnit XML."""

    name: str
    status: str  # passed, failed, error, skipped, flake
    suite_name: str = ""
    # The testcase's own lifecycle attribute, NOT the job's.  Absent means
    # the test gates the job; "informing" means it cannot.
    test_lifecycle: str = ""
    failure_message: str = ""
    failure_text: str = ""
    error_message: str = ""
    error_text: str = ""
    system_out: str = ""
    agg_passes: list = field(default_factory=list)
    agg_failures: list = field(default_factory=list)
    agg_skips: list = field(default_factory=list)


def _parse_system_out_yaml(text: str) -> dict:
    """Parse YAML-like system-out from aggregated JUnit XML."""
    result = {"passes": [], "failures": [], "skips": []}
    if not text:
        return result

    current_section = None
    current_entry: dict = {}

    for line in text.strip().splitlines():
        stripped = line.strip()
        if stripped in ("passes:", "failures:", "skips:"):
            if current_entry and current_section:
                result[current_section].append(current_entry)
                current_entry = {}
            current_section = stripped.rstrip(":")
            continue
        if current_section is None:
            continue
        if stripped.startswith("- "):
            if current_entry:
                result[current_section].append(current_entry)
            current_entry = {}
            kv = stripped[2:]
            if ":" in kv:
                key, val = kv.split(":", 1)
                current_entry[key.strip()] = val.strip().strip('"')
        elif ":" in stripped:
            key, val = stripped.split(":", 1)
            current_entry[key.strip()] = val.strip().strip('"')

    if current_entry and current_section:
        result[current_section].append(current_entry)
    return result


def _parse_junit_xml(
    source, source_name: str = "<data>"
) -> Optional[list[_TestResult]]:
    """Parse JUnit XML, returning a list of _TestResult."""
    try:
        tree = ET.parse(source)
    except (ET.ParseError, OSError):
        # Return None, not []: an unreadable or corrupt file is not the same
        # as a file that legitimately contains no failures.  Callers must be
        # able to tell those apart or corruption becomes a verified zero.
        return None

    root = tree.getroot()
    if root.tag == "testsuites":
        suites = root.findall("testsuite")
    elif root.tag == "testsuite":
        suites = [root]
    else:
        suites = root.findall(".//testsuite")
        if not suites:
            suites = [root]

    results = []
    for suite in suites:
        suite_name = suite.get("name", "")
        for tc in suite.findall("testcase"):
            name = tc.get("name", "")
            test_lifecycle = tc.get("lifecycle", "")
            failure_el = tc.find("failure")
            error_el = tc.find("error")
            skipped_el = tc.find("skipped")

            status = "passed"
            failure_message = failure_text = ""
            error_message = error_text = ""

            if error_el is not None:
                status = "error"
                error_message = error_el.get("message", "")
                error_text = error_el.text or ""
            elif failure_el is not None:
                status = "failed"
                failure_message = failure_el.get("message", "")
                failure_text = failure_el.text or ""
            elif skipped_el is not None:
                status = "skipped"

            sysout_el = tc.find("system-out")
            system_out = (sysout_el.text or "") if sysout_el is not None else ""

            agg_passes = []
            agg_failures = []
            agg_skips = []
            if system_out and re.search(
                r"^(?:passes|failures|skips):", system_out, re.MULTILINE
            ):
                parsed = _parse_system_out_yaml(system_out)
                agg_passes = parsed["passes"]
                agg_failures = parsed["failures"]
                agg_skips = parsed["skips"]

            results.append(_TestResult(
                name=name,
                status=status,
                suite_name=suite_name,
                test_lifecycle=test_lifecycle,
                failure_message=failure_message,
                failure_text=failure_text,
                error_message=error_message,
                error_text=error_text,
                system_out=system_out,
                agg_passes=agg_passes,
                agg_failures=agg_failures,
                agg_skips=agg_skips,
            ))
    return _mark_flakes(results)


def _mark_flakes(results: list[_TestResult]) -> list[_TestResult]:
    """Re-label failures as flakes when the same test also passed.

    A test that failed and then passed on retry is a flake.  Flakes do not
    fail jobs, so counting them as failures overstates what could have
    rejected a payload — and lets a flake drive regression onset.

    Grouped per (suite, name): the same name in two suites is two tests.
    """
    passed: set[tuple[str, str]] = {
        (r.suite_name, r.name) for r in results if r.status == "passed"
    }
    for r in results:
        if r.status in ("failed", "error") and (r.suite_name, r.name) in passed:
            r.status = "flake"
    return results


def _is_gating(entry: dict) -> bool:
    """True when this recorded result could actually fail its job.

    Excludes flakes (a later pass cleared them) and tests explicitly opted
    out via ``lifecycle="informing"`` — informing tests are run to
    stabilize them and are not expected to gate.
    """
    return (
        entry.get("status") in ("failed", "error")
        and entry.get("test_lifecycle") != "informing"
    )


def _test_results_to_json(results: list[_TestResult]) -> list[dict]:
    """Convert _TestResult list to JSON dicts (failures, errors and flakes).

    Flakes are included so consumers can see them, but each entry carries
    ``status`` and ``test_lifecycle`` so only genuinely gating results are
    counted as failures.
    """
    output = []
    for r in results:
        if r.status not in ("failed", "error", "flake"):
            continue
        d: dict = {
            "name": r.name,
            "status": r.status,
            "suite_name": r.suite_name,
            "test_lifecycle": r.test_lifecycle or "blocking",
        }
        if r.failure_message:
            d["failure_message"] = r.failure_message
        if r.failure_text:
            d["failure_text"] = r.failure_text
        if r.error_message:
            d["error_message"] = r.error_message
        if r.error_text:
            d["error_text"] = r.error_text
        if r.agg_passes or r.agg_failures or r.agg_skips:
            d["aggregated"] = {
                "passes": r.agg_passes,
                "failures": r.agg_failures,
                "skips": r.agg_skips,
            }
        output.append(d)
    return output


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Snapshot OpenShift payload data for offline analysis.",
        epilog=(
            "Examples:\n"
            "  python3 snapshot_payload.py 4.22.0-0.nightly-2026-02-25-152806\n"
            "  python3 snapshot_payload.py 4.18.0-0.ci-2026-01-15-114134 "
            "--output-dir .work/snapshot\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "payload_tag",
        help="Payload tag to snapshot (e.g., 4.22.0-0.nightly-2026-02-25-152806)",
    )
    parser.add_argument(
        "--output-dir", default="payload",
        help="Base output directory (default: payload)",
    )
    parser.add_argument(
        "--max-chain", type=int, default=20,
        help="Maximum backward chain depth (default: 20)",
    )
    parser.add_argument(
        "--workers", type=int, default=8,
        help="Parallel workers for GitHub API calls (default: 8)",
    )
    parser.add_argument(
        "--no-junit", action="store_true",
        help="Skip JUnit download, regression tracking",
    )
    parser.add_argument(
        "--fail-on-incomplete", action="store_true",
        help=("Exit non-zero if any data could not be collected. Use in "
              "automation so an incomplete snapshot is not analyzed as "
              "though it were complete."),
    )
    parser.add_argument(
        "--no-rpmdb", action="store_true",
        help="Skip RHCOS RPMDB extraction",
    )
    parser.add_argument(
        "--sippy", action="store_true",
        help=(
            "Force Sippy for all payload metadata (default: prefer release "
            "controller and automatically fall back for historical tags)"
        ),
    )

    args = parser.parse_args()

    try:
        tag = PayloadTag.parse(args.payload_tag)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(2)

    _log(f"Payload:  {tag.raw}")
    _log(f"Version:  {tag.version}")
    _log(f"Stream:   {tag.stream} ({tag.stream_name})")
    _log(f"Arch:     {tag.architecture}")
    _log("")

    if not _check_gh_auth():
        _log("Warning: 'gh' CLI is not authenticated. PR data will not be fetched.")
        _log("Run 'gh auth login' to enable PR diff/comment/job collection.\n")

    collect_junit = not args.no_junit
    if collect_junit and not _check_gcloud():
        _log("Warning: 'gcloud' CLI not found. JUnit data will not be fetched.")
        _log("Install gcloud SDK to enable JUnit download and regression tracking.\n")
        collect_junit = False
        # JUnit was requested and cannot be collected, so the snapshot is
        # incomplete by construction.  Record it: otherwise the completeness
        # gate sees an empty ledger and reports a complete snapshot.
        _record_collection_error(
            "gcloud_missing",
            ["gcloud", "storage"],
            detail=("gcloud CLI not available; JUnit, build logs and "
                    "regression tracking were skipped"),
            stage="preflight",
        )
    elif collect_junit and not _check_gcloud_credentials():
        _log("Note: 'gcloud' has no active credentials. CI artifact buckets")
        _log("are public, so they will be read anonymously. Run")
        _log("'gcloud auth login' if you need private buckets too.\n")

    collect_rpmdb = not args.no_rpmdb
    if collect_rpmdb and not _check_podman():
        _log("Warning: podman is not available ('podman info' failed).")
        _log("RHCOS RPMDB data will not be extracted.\n")
        collect_rpmdb = False

    if args.sippy:
        _log("Forcing Sippy APIs for all release payload data.\n")

    try:
        snapshotter = Snapshotter(
            tag=tag,
            output_dir=args.output_dir,
            max_chain=args.max_chain,
            workers=args.workers,
            collect_junit=collect_junit,
            use_sippy=args.sippy,
            collect_rpmdb=collect_rpmdb,
        )
        snapshotter.run()

        unrecovered = _unrecovered_errors()
        recovered = len(_COLLECTION_ERRORS) - len(unrecovered)
        if recovered:
            _log("")
            status = ("data is complete" if not unrecovered
                      else "see the warning below for what is still missing")
            _log(f"Note: {recovered} read failure(s) were recovered by a "
                 f"fallback; {status}. See 'collection_errors' "
                 f"(recovered: true) in summary.json.")
        if unrecovered:
            by_reason: dict[str, int] = {}
            for e in unrecovered:
                r = e.get("reason", "unknown")
                by_reason[r] = by_reason.get(r, 0) + 1
            _log("")
            _log("=" * 68)
            _log(f"WARNING: SNAPSHOT IS INCOMPLETE "
                 f"({len(unrecovered)} unrecovered collection error(s))")
            for reason, count in sorted(by_reason.items()):
                _log(f"  {reason}: {count}")
            affected = sorted({
                e["job"] for e in unrecovered if e.get("job")
            })
            if affected:
                _log(f"  affected jobs: {', '.join(affected)}")
            _log("")
            _log("Missing data is ABSENT, not empty. Do not interpret a job")
            _log("without test_failure_count as having zero test failures.")
            _log("Details: 'collection_errors' in summary.json")
            _log("=" * 68)
            if args.fail_on_incomplete:
                sys.exit(1)
    except urllib.error.HTTPError as e:
        print(f"Error: HTTP {e.code}: {e.reason}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"Error: Cannot connect to release controller: {e.reason}",
              file=sys.stderr)
        sys.exit(1)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
