#!/usr/bin/env python3
"""Regression tests for the snapshot completeness contract.

The contract under test: data the snapshot could not read must never be
published as an authoritative zero.  Each test below corresponds to a way
that guarantee was previously broken.

Run with: pytest test_collection_completeness.py
"""

import importlib.util
import json
import os
import sys
import threading

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "payload_snapshot", os.path.join(_HERE, "payload_snapshot.py")
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ps = _load_module()


@pytest.fixture(autouse=True)
def clean_ledger():
    """Each test starts with an empty global error ledger."""
    ps._COLLECTION_ERRORS.clear()
    ps._GCLOUD_ANONYMOUS = True  # never probe real credentials in tests
    yield
    ps._COLLECTION_ERRORS.clear()


def _job(name="job-a", bucket="bucket/path"):
    return ps.JobInfo(
        name=name, state="Failed", lifecycle="blocking", url="",
        retries=0, previous_attempt_urls=[], is_aggregated=False,
        gcs_bucket_path=bucket,
    )


def _collector(tmp_path, job=None, tag="4.99.0-0.ci-2026-01-01-000000"):
    return ps.JUnitCollector(str(tmp_path / "junit"), job or _job(), tag)


VALID_JUNIT = (
    '<testsuite name="s" tests="1" failures="1">'
    '<testcase name="t"><failure>boom</failure></testcase>'
    "</testsuite>"
)


# --------------------------------------------------------------------------
# Error classification
# --------------------------------------------------------------------------

@pytest.mark.parametrize("stderr,expected", [
    ("ERROR: One or more URLs matched no objects.", "no_match"),
    ("ERROR: 403 does not have storage.objects.list access", "auth"),
    ("ERROR: Anonymous caller does not have access", "auth"),
    ("ERROR: something unexpected", "command_failed"),
])
def test_stderr_classification(stderr, expected):
    assert ps._classify_gcloud_stderr(stderr) == expected


def test_no_match_is_not_recorded_as_error(monkeypatch):
    """A missing object is absence, not failure — probes must stay quiet."""
    monkeypatch.setattr(ps.subprocess, "run", lambda *a, **k: type(
        "R", (), {"returncode": 1, "stdout": "",
                  "stderr": "ERROR: matched no objects"})())
    assert ps._run_gcloud(["gcloud", "storage", "ls", "x"]) is None
    assert ps._COLLECTION_ERRORS == []


def test_auth_failure_is_recorded(monkeypatch):
    monkeypatch.setattr(ps.subprocess, "run", lambda *a, **k: type(
        "R", (), {"returncode": 1, "stdout": "",
                  "stderr": "ERROR: 403 forbidden"})())
    assert ps._run_gcloud(["gcloud", "storage", "ls", "x"]) is None
    assert [e["reason"] for e in ps._COLLECTION_ERRORS] == ["auth"]


def test_detail_is_sanitized():
    """Persisted diagnostics must not carry control characters."""
    ps._record_collection_error(
        "auth", ["gcloud"], detail="bad\x1b[31mred\x00\nthing"
    )
    detail = ps._COLLECTION_ERRORS[0]["detail"]
    assert "\x1b" not in detail and "\x00" not in detail
    assert "\n" not in detail


# --------------------------------------------------------------------------
# Recovery bookkeeping
# --------------------------------------------------------------------------

def test_recovery_is_scoped_to_its_own_operation():
    """A recovered fallback must not clear another operation's error."""
    with ps._error_scope() as mine:
        ps._record_collection_error("timeout", ["gcloud"], job="mine")
        # A concurrent collector records its own, unrelated failure.
        ps._record_collection_error("auth", ["gcloud"], job="theirs")

    # Only the entry captured for *this* operation is recovered.
    ps._mark_errors_recovered([e for e in mine if e.get("job") == "mine"])

    by_job = {e["job"]: e for e in ps._COLLECTION_ERRORS}
    assert by_job["mine"].get("recovered") is True
    assert by_job["theirs"].get("recovered") is None
    assert len(ps._unrecovered_errors()) == 1


def test_concurrent_collectors_do_not_recover_each_others_errors():
    """Threads racing on the shared ledger must stay isolated."""
    started = threading.Barrier(2)

    def worker(tag):
        with ps._error_scope() as own:
            ps._record_collection_error("timeout", ["gcloud"], job=tag)
            started.wait(timeout=5)  # force interleaving
            if tag == "recovers":
                ps._mark_errors_recovered(own)

    threads = [threading.Thread(target=worker, args=(t,))
               for t in ("recovers", "keeps")]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)

    by_job = {e["job"]: e for e in ps._COLLECTION_ERRORS}
    assert by_job["recovers"].get("recovered") is True
    assert by_job["keeps"].get("recovered") is None


def test_data_complete_ignores_recovered_errors():
    with ps._error_scope() as own:
        ps._record_collection_error("timeout", ["gcloud"])
    ps._mark_errors_recovered(own)
    assert ps._unrecovered_errors() == []


# --------------------------------------------------------------------------
# Parsing
# --------------------------------------------------------------------------

def test_malformed_xml_returns_none_not_empty(tmp_path):
    """Corrupt XML must be distinguishable from "no failures"."""
    bad = tmp_path / "junit_bad.xml"
    bad.write_text('<testsuite><testcase name="t"><failure>trunc')
    assert ps._parse_junit_xml(str(bad)) is None


def test_valid_xml_with_no_failures_returns_empty_list(tmp_path):
    good = tmp_path / "junit_ok.xml"
    good.write_text('<testsuite name="s" tests="1"><testcase name="t"/>'
                    "</testsuite>")
    results = ps._parse_junit_xml(str(good))
    assert results is not None
    assert ps._test_results_to_json(results) == []


# --------------------------------------------------------------------------
# Publishing decisions
# --------------------------------------------------------------------------

def _stub_discovery(monkeypatch, files):
    monkeypatch.setattr(
        ps.JUnitCollector, "_list_junit_files", lambda self: list(files)
    )


def test_unreadable_junit_leaves_results_absent(tmp_path, monkeypatch):
    """Read failure => results.json absent (unknown), never []."""
    _stub_discovery(monkeypatch, ["gs://b/junit_operator.xml"])
    monkeypatch.setattr(ps, "_run_gcloud_bytes", lambda *a, **k: (
        ps._record_collection_error("auth", ["gcloud"]) or None))

    c = _collector(tmp_path)
    assert c.collect() is False
    assert not os.path.exists(c.output_path)
    assert any(e["reason"] == "junit_unavailable"
               for e in ps._COLLECTION_ERRORS)


def test_no_junit_discovered_is_unknown_not_zero(tmp_path, monkeypatch):
    """A failed job with no JUnit at all is unknown, not verified clean."""
    _stub_discovery(monkeypatch, [])

    c = _collector(tmp_path)
    assert c.collect() is False
    assert not os.path.exists(c.output_path)
    assert any(e["reason"] == "junit_missing"
               for e in ps._COLLECTION_ERRORS)


def test_partial_read_is_published_but_flagged(tmp_path, monkeypatch):
    """Half the files read => real results, explicitly marked partial."""
    _stub_discovery(monkeypatch, ["gs://b/junit_a.xml", "gs://b/junit_b.xml"])

    def fake_cat(args, **kwargs):
        if args[-1].endswith("junit_a.xml"):
            return VALID_JUNIT.encode()
        ps._record_collection_error("auth", ["gcloud"])
        return None

    monkeypatch.setattr(ps, "_run_gcloud_bytes", fake_cat)

    c = _collector(tmp_path)
    assert c.collect() is True
    assert json.load(open(c.output_path))  # real failures published
    assert any(e["reason"] == "junit_partial"
               for e in ps._COLLECTION_ERRORS)


def test_unparseable_download_counts_as_unread(tmp_path, monkeypatch):
    """Corrupt XML must not be published as zero failures."""
    _stub_discovery(monkeypatch, ["gs://b/junit_bad.xml"])
    monkeypatch.setattr(
        ps, "_run_gcloud_bytes", lambda *a, **k: b"<testsuite><trunc"
    )

    c = _collector(tmp_path)
    assert c.collect() is False
    assert not os.path.exists(c.output_path)
    reasons = {e["reason"] for e in ps._COLLECTION_ERRORS}
    assert "junit_unparseable" in reasons
    assert "junit_unavailable" in reasons


def test_complete_read_publishes_authoritative_results(tmp_path, monkeypatch):
    _stub_discovery(monkeypatch, ["gs://b/junit_a.xml"])
    monkeypatch.setattr(
        ps, "_run_gcloud_bytes", lambda *a, **k: VALID_JUNIT.encode()
    )

    c = _collector(tmp_path)
    assert c.collect() is True
    assert len(json.load(open(c.output_path))) == 1
    assert ps._unrecovered_errors() == []


# --------------------------------------------------------------------------
# Payload scoping and resume
# --------------------------------------------------------------------------

def test_junit_state_is_scoped_by_payload():
    """The same job name recurs per payload; state must not leak across."""
    ps._record_collection_error(
        "junit_unavailable", ["gcloud"], job="job-a", payload_tag="old"
    )
    assert ps._job_junit_state("job-a", "old", "junit_unavailable") is True
    assert ps._job_junit_state("job-a", "target", "junit_unavailable") is False


def test_suspect_junit_is_discarded_on_rerun(tmp_path):
    """A rerun must re-collect output a previous run called incomplete."""
    base = tmp_path / "5.0" / "ci"
    junit_dir = base / "tag-1" / "jobs" / "blocking" / "job-a" / "junit"
    junit_dir.mkdir(parents=True)
    (junit_dir / "results.json").write_text("[]")
    (base / ps.COLLECTION_STATE_FILE).write_text(json.dumps([
        {"reason": "junit_partial", "job": "job-a", "payload_tag": "tag-1"}
    ]))

    assert ps._invalidate_suspect_junit(str(base)) == 1
    assert not junit_dir.exists()


def test_recovered_state_is_not_invalidated_on_rerun(tmp_path):
    base = tmp_path / "5.0" / "ci"
    junit_dir = base / "tag-1" / "jobs" / "blocking" / "job-a" / "junit"
    junit_dir.mkdir(parents=True)
    (junit_dir / "results.json").write_text("[]")
    (base / ps.COLLECTION_STATE_FILE).write_text(json.dumps([
        {"reason": "junit_partial", "job": "job-a", "payload_tag": "tag-1",
         "recovered": True}
    ]))

    assert ps._invalidate_suspect_junit(str(base)) == 0
    assert junit_dir.exists()


def test_unsafe_ledger_entries_never_delete_outside_base(tmp_path):
    """The ledger is data from disk; it must not aim rmtree at a parent."""
    base = tmp_path / "snap" / "5.0" / "ci"
    base.mkdir(parents=True)
    victim = tmp_path / "victim"
    victim.mkdir()
    (victim / "keep.txt").write_text("do not delete me")

    (base / ps.COLLECTION_STATE_FILE).write_text(json.dumps([
        {"reason": "junit_partial", "job": "../../../../victim",
         "payload_tag": ".."},
        {"reason": "junit_partial", "job": "a/b", "payload_tag": "tag"},
    ]))

    assert ps._invalidate_suspect_junit(str(base)) == 0
    assert (victim / "keep.txt").exists()


def test_carry_forward_keeps_unresolved_junit_errors(tmp_path):
    """--no-junit must not launder a stale partial snapshot into complete."""
    base = tmp_path / "5.0" / "ci"
    base.mkdir(parents=True)
    (base / ps.COLLECTION_STATE_FILE).write_text(json.dumps([
        {"reason": "junit_partial", "job": "job-a", "payload_tag": "tag-1"},
        {"reason": "auth", "job": "job-a", "payload_tag": "tag-1"},
        {"reason": "junit_partial", "job": "job-b", "payload_tag": "tag-1",
         "recovered": True},
    ]))

    assert ps._carry_forward_junit_errors(str(base)) == 1
    carried = ps._unrecovered_errors()
    assert [e["reason"] for e in carried] == ["junit_partial"]
    assert carried[0]["carried_forward"] is True


@pytest.mark.parametrize("raw,forbidden", [
    ("ERROR: account someone@example.com lacks access", "someone@example.com"),
    ("ERROR: GET https://x/o?X-Goog-Signature=abc123", "X-Goog-Signature"),
])
def test_detail_redacts_identifiers(raw, forbidden):
    ps._record_collection_error("auth", ["gcloud"], detail=raw)
    assert forbidden not in ps._COLLECTION_ERRORS[0]["detail"]


def test_collection_state_round_trips(tmp_path):
    base = tmp_path / "snap"
    base.mkdir()
    ps._record_collection_error("auth", ["gcloud"], job="job-a")
    ps._write_collection_state(str(base))

    persisted = json.load(open(base / ps.COLLECTION_STATE_FILE))
    assert persisted[0]["reason"] == "auth"

    # A clean run clears the stale ledger.
    ps._COLLECTION_ERRORS.clear()
    ps._write_collection_state(str(base))
    assert not (base / ps.COLLECTION_STATE_FILE).exists()


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
