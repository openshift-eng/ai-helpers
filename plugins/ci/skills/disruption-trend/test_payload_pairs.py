"""Tests for payload_pairs.py — payload pairs from prowjob.json, fetching, and caching."""
import http.client
import json
import os
import sys
import urllib.error
from io import BytesIO
from unittest.mock import patch

import pytest

import disruption_series  # noqa: F401  (puts disruption_common on sys.path)
import payload_pairs as pp
from disruption_common import state

REGISTRY = "registry.ci.openshift.org/ocp/release-5:"
UPGRADE = {
    "metadata": {"annotations": {"release.openshift.io/from-tag": "5.1.0-0.nightly-2026-11-08-173648",
                                 "release.openshift.io/tag": "5.1.0-0.nightly-2026-11-09-143447"}},
    "spec": {"pod_spec": {"containers": [{"env": [
        {"name": "RELEASE_IMAGE_LATEST", "value": REGISTRY + "5.1.0-0.nightly-2026-11-09-143447"},
        {"name": "RELEASE_IMAGE_INITIAL", "value": REGISTRY + "5.1.0-0.nightly-2026-11-08-173648"},
    ]}]}},
}


def test_payloads_from_prowjob_reads_env_values():
    assert pp.payloads_from_prowjob(UPGRADE) == {"initial": "5.1.0-0.nightly-2026-11-08-173648",
                                                 "target": "5.1.0-0.nightly-2026-11-09-143447"}


def test_payloads_from_prowjob_falls_back_to_annotations_and_tolerates_missing_fields():
    annotated = {"metadata": {"annotations": {"release.openshift.io/tag": "5.1.0-0.ci-2026-11-09-172923"}},
                 "spec": {"pod_spec": {"containers": [{"env": [{"name": "OTHER", "value": "x"}]}]}}}
    assert pp.payloads_from_prowjob(annotated) == {"initial": "", "target": "5.1.0-0.ci-2026-11-09-172923"}
    assert pp.payloads_from_prowjob({}) == {"initial": "", "target": ""}
    assert pp.payloads_from_prowjob({"spec": {"pod_spec": {"containers": [None, {"env": [None]}]}}}) == {
        "initial": "", "target": ""}


def test_payload_from_pullspec():
    assert pp.payload_from_pullspec("registry.ci.openshift.org/ocp/release-5:5.1.0-0.nightly-x") == "5.1.0-0.nightly-x"
    assert pp.payload_from_pullspec("quay.io/openshift-release-dev/ocp-release@sha256:abc") == (
        "quay.io/openshift-release-dev/ocp-release@sha256:abc")
    assert pp.payload_from_pullspec("registry:5000/ns/release") == "registry:5000/ns/release"
    ci = "quay-proxy.ci.openshift.org/openshift/ci:rc_payload__5.1.0-0.ci-2026-11-09-172923"
    assert pp.payload_from_pullspec(ci) == "5.1.0-0.ci-2026-11-09-172923"
    assert pp.payload_from_pullspec(None) == ""


def test_payload_time_and_minor():
    assert pp.payload_time("5.1.0-0.ci-2026-11-09-172923") == "2026-11-09-172923"
    assert pp.payload_time("5.1.0-0.nightly-2026-11-09-143447") < pp.payload_time("5.1.0-0.ci-2026-11-09-172923")
    assert pp.payload_time("4.20.3") == ""
    assert pp.payload_minor("5.0.0-0.nightly-2026-11-01-000000") == "5.0"
    assert pp.payload_minor("sha256:abc") == ""
    assert pp.is_upgrade({"initial": "a", "target": "b"}) and not pp.is_upgrade({"initial": "a", "target": "a"})
    assert not pp.is_upgrade({"initial": "", "target": "b"})


def test_prowjob_url_uses_the_public_bucket():
    assert pp.prowjob_url("job", "123") == (
        "https://storage.googleapis.com/test-platform-results-public/logs/job/123/prowjob.json")


def test_fetch_prowjob_wraps_errors():
    error = urllib.error.HTTPError("u", 404, "missing", {}, BytesIO(b""))
    with patch("urllib.request.urlopen", side_effect=error):
        with pytest.raises(pp.PayloadError, match="HTTP 404"):
            pp.fetch_prowjob("job", "1")
    with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("refused")):
        with pytest.raises(pp.PayloadError, match="failed to connect"):
            pp.fetch_prowjob("job", "1")

    class Response:
        def __enter__(self):
            return BytesIO(b"not json")

        def __exit__(self, *args):
            return False

    with patch("urllib.request.urlopen", return_value=Response()):
        with pytest.raises(pp.PayloadError, match="failed to read"):
            pp.fetch_prowjob("job", "1")
    with patch("urllib.request.urlopen", side_effect=http.client.IncompleteRead(b"par")):
        with pytest.raises(pp.PayloadError, match="failed to read"):
            pp.fetch_prowjob("job", "1")
    with patch("urllib.request.urlopen", side_effect=TimeoutError()):
        with pytest.raises(pp.PayloadError, match="TimeoutError$"):
            pp.fetch_prowjob("job", "1")


def test_fetch_payloads_caches_results_and_retries_failures_later(tmp_path, capsys):
    cache = tmp_path / "cache" / "prowjob-payloads.json"
    calls = []

    def fetch(job, build_id):
        calls.append(build_id)
        if build_id == "3":
            raise pp.PayloadError("HTTP 503 for x")
        return UPGRADE if build_id == "1" else {}

    runs = [{"prow_id": "1", "job": "j"}, {"prow_id": "2", "job": "j"}, {"prow_id": "3", "job": "j"},
            {"prow_id": "1", "job": "j"}, {"prow_id": "4", "job": ""}]
    payloads, failed = pp.fetch_payloads(runs, cache_path=str(cache), fetch=fetch, write=state.write_json_atomic)
    assert sorted(calls) == ["1", "2", "3"]
    assert payloads["1"]["target"] == "5.1.0-0.nightly-2026-11-09-143447"
    assert payloads["2"] == {"initial": "", "target": ""}
    assert failed == ["3"]
    assert "could not fetch prowjob.json for 1 of 3 run(s); first error: HTTP 503" in capsys.readouterr().err
    assert set(json.loads(cache.read_text())) == {"1", "2"}

    calls.clear()
    payloads, failed = pp.fetch_payloads(runs, cache_path=str(cache), fetch=fetch, write=state.write_json_atomic)
    assert calls == ["3"]
    assert payloads["1"]["initial"] == "5.1.0-0.nightly-2026-11-08-173648"
    assert not [p for p in os.listdir(cache.parent) if p.endswith(".tmp")]


def test_fetch_payloads_cache_write_failure_is_a_warning(tmp_path, capsys):
    def failing_write(path, data):
        raise PermissionError("read-only")

    payloads, failed = pp.fetch_payloads([{"prow_id": "1", "job": "j"}], cache_path=str(tmp_path / "c.json"),
                                         fetch=lambda job, pid: UPGRADE, write=failing_write)
    assert payloads["1"]["target"] and failed == []
    assert "could not write payload cache" in capsys.readouterr().err


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
