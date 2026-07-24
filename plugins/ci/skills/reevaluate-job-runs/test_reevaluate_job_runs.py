import json

import pytest
import reevaluate_job_runs
from reevaluate_job_runs import extract_build_id, chunk, send_batch

def test_plain_numeric_id():
    assert extract_build_id("1856789012345678848") == "1856789012345678848"

def test_prow_url():
    url = ("https://prow.ci.openshift.org/view/gs/test-platform-results/logs/"
           "periodic-ci-openshift-release-master-ci-4.20-e2e-aws-ovn/1856789012345678848")
    assert extract_build_id(url) == "1856789012345678848"

def test_prow_url_trailing_slash():
    assert extract_build_id("https://prow.ci.openshift.org/view/gs/b/logs/job/123456/") == "123456"

def test_invalid_input_raises():
    with pytest.raises(ValueError):
        extract_build_id("not-a-build-id")

def test_chunk_splits_evenly():
    assert chunk([1, 2, 3, 4], 2) == [[1, 2], [3, 4]]

def test_chunk_last_partial():
    assert chunk([1, 2, 3], 2) == [[1, 2], [3]]

def test_chunk_smaller_than_size():
    assert chunk([1], 10) == [[1]]

def test_url_with_query_string():
    assert extract_build_id(
        "https://prow.ci.openshift.org/view/gs/b/logs/job/123456?tab=x") == "123456"

def test_url_with_fragment():
    assert extract_build_id(
        "https://prow.ci.openshift.org/view/gs/b/logs/job/123456#fragment") == "123456"


class FakeResponse:
    def __init__(self, body):
        self._body = body.encode("utf-8")

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def _patch_urlopen(monkeypatch, bodies):
    """urlopen returns successive bodies from the list."""
    calls = []

    def fake_urlopen(req, timeout=None):
        calls.append(req)
        return FakeResponse(bodies[len(calls) - 1])

    monkeypatch.setattr(reevaluate_job_runs.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(reevaluate_job_runs.time, "sleep", lambda s: None)
    return calls


def test_send_batch_json_success(monkeypatch):
    body = json.dumps({"results": [{"prow_job_build_id": "1", "status": "success"}]})
    calls = _patch_urlopen(monkeypatch, [body])
    results, err, auth_failed = send_batch(["1"], "tok", True)
    assert err is None
    assert auth_failed is False
    assert results == [{"prow_job_build_id": "1", "status": "success"}]
    assert len(calls) == 1


def test_send_batch_sso_login_page_no_retries(monkeypatch):
    calls = _patch_urlopen(monkeypatch, ["<html><body>Log in to your account</body></html>"] * 3)
    results, err, auth_failed = send_batch(["1"], "tok", True)
    assert results is None
    assert auth_failed is True
    assert "token" in err
    assert len(calls) == 1  # no retries on auth failure


def test_send_batch_504_html_then_success(monkeypatch):
    ok = json.dumps({"results": [{"prow_job_build_id": "1", "status": "success"}]})
    calls = _patch_urlopen(monkeypatch, ["<html>504 Gateway Time-out</html>", ok])
    results, err, auth_failed = send_batch(["1"], "tok", True)
    assert err is None
    assert auth_failed is False
    assert len(results) == 1
    assert len(calls) == 2


def test_send_batch_plaintext_body_is_retryable(monkeypatch):
    calls = _patch_urlopen(monkeypatch, ["not json at all"] * 3)
    results, err, auth_failed = send_batch(["1"], "tok", True)
    assert results is None
    assert auth_failed is False
    assert "non-JSON" in err
    assert len(calls) == 3  # retried up to the limit


def test_resolve_token_arg_wins_over_env():
    assert reevaluate_job_runs.resolve_token("argtok", {"SIPPY_TOKEN": "envtok"}) == "argtok"

def test_resolve_token_falls_back_to_env():
    assert reevaluate_job_runs.resolve_token(None, {"SIPPY_TOKEN": "envtok"}) == "envtok"

def test_resolve_token_none_when_unset():
    assert reevaluate_job_runs.resolve_token(None, {}) is None
