import io
import json
import socket
import urllib.error
import urllib.request

import pytest

import diagnose_job_run
from diagnose_job_run import (classify_response, format_jira_issues,
                              jira_issue_url, normalize_label_entry, parse_prow_url)


class FakeResponse:
    def __init__(self, status, body, read_error=None):
        self.status = status
        self._body = json.dumps(body).encode("utf-8") if not isinstance(body, str) else body.encode("utf-8")
        self._read_error = read_error

    def getcode(self):
        return self.status

    def read(self):
        if self._read_error:
            raise self._read_error
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def queue_authenticated_responses(monkeypatch, *responses):
    calls = []
    pending = list(responses)

    def fake_open(req, timeout=None):
        calls.append((req, timeout))
        response = pending.pop(0)
        if isinstance(response, BaseException):
            raise response
        return response

    monkeypatch.setattr(diagnose_job_run.HTTP_OPENER, "open", fake_open)
    return calls


def batch_response(status="complete", items=None):
    terminal = status in diagnose_job_run.TERMINAL_STATES
    return {
        "batch_id": "batch-1",
        "status": status,
        "requested": 1,
        "enqueued": 1,
        "deduped": 0,
        "completed": 1 if status == "complete" else 0,
        "failed": 1 if status in ("failed", "cancelled") else 0,
        "running": 0,
        "pending": 0 if terminal else 1,
        "items": items if items is not None else [
            {"item_key": "1856789012345678848", "state": "completed"},
        ],
    }


PROW_URL = (
    "https://prow.ci.openshift.org/view/gs/test-platform-results-public/logs/"
    "some-job/1856789012345678848"
)


def mock_catalogs(monkeypatch):
    def fake_get_json(url):
        if url.endswith("/labels"):
            return [{"id": "InfraFailure", "label_title": "Infrastructure failure"}]
        if url.endswith("/symptoms"):
            return []
        raise AssertionError("unexpected catalog URL %s" % url)

    monkeypatch.setattr(diagnose_job_run, "get_json", fake_get_json)

def test_parse_standard_prow_url():
    url = ("https://prow.ci.openshift.org/view/gs/test-platform-results-public/logs/"
           "periodic-ci-openshift-release-master-ci-4.20-e2e-aws-ovn/1856789012345678848")
    bucket, path, build_id = parse_prow_url(url)
    assert bucket == "test-platform-results-public"
    assert path == ("logs/periodic-ci-openshift-release-master-ci-4.20-e2e-aws-ovn/"
                    "1856789012345678848")
    assert build_id == "1856789012345678848"

def test_parse_pr_job_url():
    url = ("https://prow.ci.openshift.org/view/gs/test-platform-results-public/pr-logs/pull/"
           "openshift_origin/29000/pull-ci-openshift-origin-master-e2e/1856789012345678848/")
    bucket, path, build_id = parse_prow_url(url)
    assert bucket == "test-platform-results-public"
    assert build_id == "1856789012345678848"
    assert path.startswith("pr-logs/pull/") and path.endswith(build_id)

def test_url_bucket_is_preserved():
    url = ("https://prow.ci.openshift.org/view/gs/test-platform-results/logs/"
           "periodic-ci-openshift-release-master-ci-4.20-e2e-aws-ovn/1856789012345678848")
    bucket, path, build_id = parse_prow_url(url)
    assert bucket == "test-platform-results"
    assert path == ("logs/periodic-ci-openshift-release-master-ci-4.20-e2e-aws-ovn/"
                    "1856789012345678848")
    assert build_id == "1856789012345678848"


def test_archive_bucket_is_preserved():
    url = ("https://prow.ci.openshift.org/view/gs/prow-artifact-archive/logs/"
           "periodic-ci-openshift-release-master-ci-4.20-e2e-aws-ovn/1856789012345678848")
    bucket, path, build_id = parse_prow_url(url)
    assert bucket == "prow-artifact-archive"
    assert path == ("logs/periodic-ci-openshift-release-master-ci-4.20-e2e-aws-ovn/"
                    "1856789012345678848")
    assert build_id == "1856789012345678848"


def test_rejects_non_prow_url():
    with pytest.raises(ValueError):
        parse_prow_url("https://example.com/foo")

def test_parse_url_with_query_string_and_fragment():
    url = ("https://prow.ci.openshift.org/view/gs/test-platform-results-public/logs/"
           "some-job/1856789012345678848?tab=x#top")
    bucket, path, build_id = parse_prow_url(url)
    assert bucket == "test-platform-results-public"
    assert build_id == "1856789012345678848"
    assert path == "logs/some-job/1856789012345678848"

def test_classify_response_login_page():
    _, err = classify_response("<html><body>Please Log in to continue</body></html>")
    assert err and "oc-auth" in err

def test_classify_response_other_html():
    _, err = classify_response("<html>504 Gateway Time-out</html>")
    assert err and "HTML error page" in err

def test_classify_response_non_json_plaintext():
    _, err = classify_response("service unavailable")
    assert err and "non-JSON" in err

def test_classify_response_valid_json():
    parsed, err = classify_response('{"batch_id": "batch-1"}')
    assert err is None
    assert parsed["batch_id"] == "batch-1"


@pytest.mark.parametrize(
    "body, expected_detail",
    [
        ({"message": "x" * 600}, "x" * 500),
        ({"error": "unexpected success"}, '{"error": "unexpected success"}'),
    ],
)
def test_unexpected_success_status_preserves_safe_api_detail(
    monkeypatch, body, expected_detail
):
    queue_authenticated_responses(monkeypatch, FakeResponse(200, body))

    with pytest.raises(diagnose_job_run.ClientError) as caught:
        diagnose_job_run.request_json(
            "POST",
            diagnose_job_run.REEVALUATE_URL,
            "secret",
            202,
            {"dry_run": True},
        )

    assert str(caught.value) == "expected HTTP 202, got HTTP 200: %s" % expected_detail


WRAPPED_ENTRY = {
    "symptom_label_v1": {
        "symptom": {"id": "KubeletVersionSkew1355", "summary": "kubelet version skew 1.35.5",
                    "matcher_type": "string",
                    "file_pattern": "artifacts/*e2e*/gather-extra/artifacts/nodes.json",
                    "match_string": "\"kubeletVersion\": \"v1.35.3\"",
                    "label_ids": ["KubeletVersion1353"]},
        "label": {"id": "KubeletVersion1353", "label_title": "kubeletVersion 1.35.3",
                  "explanation": ""},
        "file_match": "artifacts/e2e-metal/gather-extra/artifacts/nodes.json",
        "text_match": "  \"kubeletVersion\": \"v1.35.3\",",
    }
}

def test_normalize_wrapped_symptom_label_v1():
    m = normalize_label_entry(WRAPPED_ENTRY)
    assert m["label_id"] == "KubeletVersion1353"
    assert m["symptom_id"] == "KubeletVersionSkew1355"
    assert m["label"]["label_title"] == "kubeletVersion 1.35.3"
    assert m["symptom"]["matcher_type"] == "string"
    assert m["file_match"].endswith("nodes.json")
    assert "v1.35.3" in m["text_match"]
    assert m["raw"] is WRAPPED_ENTRY

def test_normalize_flat_fallback():
    m = normalize_label_entry({"label_id": "InfraFailure", "symptom_id": "AWSAuth"})
    assert m["label_id"] == "InfraFailure"
    assert m["symptom_id"] == "AWSAuth"

def test_normalize_flat_fallback_id_key():
    assert normalize_label_entry({"id": "InfraFailure"})["label_id"] == "InfraFailure"

def test_jira_issue_url():
    assert jira_issue_url("OCPBUGS-12345") == (
        "https://redhat.atlassian.net/browse/OCPBUGS-12345")

def test_format_jira_issues():
    assert format_jira_issues(["OCPBUGS-12345", "TRT-2896"]) == (
        "OCPBUGS-12345 (https://redhat.atlassian.net/browse/OCPBUGS-12345), "
        "TRT-2896 (https://redhat.atlassian.net/browse/TRT-2896)")

def test_normalize_garbage_returns_empty_match():
    m = normalize_label_entry("not-a-dict")
    assert m["label_id"] is None and m["symptom_id"] is None


def test_resolve_token_arg_wins_over_env():
    assert diagnose_job_run.resolve_token("argtok", {"SIPPY_TOKEN": "envtok"}) == "argtok"

def test_resolve_token_falls_back_to_env():
    assert diagnose_job_run.resolve_token(None, {"SIPPY_TOKEN": "envtok"}) == "envtok"

def test_resolve_token_none_when_unset():
    assert diagnose_job_run.resolve_token(None, {}) is None


def test_deep_mode_submits_202_polls_all_states_and_reads_item_result(monkeypatch, capsys):
    mock_catalogs(monkeypatch)
    result = {
        "prow_job_build_id": "1856789012345678848",
        "status": "success",
        "symptoms_evaluated": 5,
        "symptoms_matched": ["KnownFailure"],
        "labels_applied": ["InfraFailure"],
    }
    complete = batch_response(items=[{
        "item_key": "1856789012345678848",
        "state": "completed",
        "result": result,
    }])
    calls = queue_authenticated_responses(
        monkeypatch,
        FakeResponse(202, {
            "batch_id": "batch-1",
            "requested": 1,
            "links": {"status": "/api/jobs/runs/reevaluate/batch-1"},
        }),
        FakeResponse(200, batch_response(status="pending")),
        FakeResponse(200, batch_response(status="processing")),
        FakeResponse(200, batch_response(status="running")),
        FakeResponse(200, complete),
    )
    sleeps = []
    monkeypatch.setattr(diagnose_job_run.time, "sleep", sleeps.append)

    assert diagnose_job_run.main([
        PROW_URL, "--deep", "--token", "secret", "--format", "json",
    ]) == 0
    captured = capsys.readouterr()
    report = json.loads(captured.out)
    assert report["reevaluate_results"] == [result]
    assert report["matches"] == [{
        "label_id": "InfraFailure",
        "label": {"id": "InfraFailure", "label_title": "Infrastructure failure"},
    }]
    assert [call[0].get_method() for call in calls] == ["POST", "GET", "GET", "GET", "GET"]
    assert json.loads(calls[0][0].data) == {
        "prow_job_build_ids": ["1856789012345678848"],
        "dry_run": True,
    }
    assert all(call[1] == diagnose_job_run.REQUEST_TIMEOUT_SECONDS for call in calls)
    assert sleeps == [diagnose_job_run.POLL_INTERVAL_SECONDS] * 3
    assert "batch-1" in captured.err
    assert diagnose_job_run.REEVALUATE_URL + "/batch-1" in captured.err
    assert "secret" not in captured.out + captured.err


@pytest.mark.parametrize("output_format", ["json", "summary"])
@pytest.mark.parametrize(
    "unsafe_status,unsafe_marker",
    [
        ("https://unsafe-cross-origin.invalid/status", "unsafe-cross-origin"),
        ("https://sippy-auth.dptools.openshift.org:unsafe-port/status", "unsafe-port"),
        ("https://[unsafe-bracket.invalid/status", "unsafe-bracket"),
        (
            "https://unsafe-user:unsafe-password@"
            "sippy-auth.dptools.openshift.org/status",
            "unsafe-user",
        ),
    ],
)
def test_deep_mode_invalid_status_link_retains_safe_batch_id_without_get(
    monkeypatch, capsys, output_format, unsafe_status, unsafe_marker
):
    mock_catalogs(monkeypatch)
    calls = queue_authenticated_responses(monkeypatch, FakeResponse(202, {
        "batch_id": "batch-1",
        "requested": 1,
        "links": {"status": unsafe_status},
    }))

    assert diagnose_job_run.main([
        PROW_URL, "--deep", "--token", "cli-secret-token", "--format", output_format,
    ]) == 1
    captured = capsys.readouterr()
    expected_error = (
        "deep reevaluation batch batch-1 was accepted, but its status link "
        "failed validation"
    )
    assert captured.err == "Error: %s\n" % expected_error
    assert "Submitted deep reevaluation" not in captured.out + captured.err
    assert unsafe_status not in captured.out + captured.err
    assert unsafe_marker not in captured.out + captured.err
    assert "unsafe-password" not in captured.out + captured.err
    assert "cli-secret-token" not in captured.out + captured.err
    if output_format == "json":
        assert json.loads(captured.out) == {
            "batch_id": "batch-1",
            "error": expected_error,
        }
    else:
        assert captured.out == ""
        assert "batch-1" in captured.err
    assert [call[0].get_method() for call in calls] == ["POST"]
    assert len(calls) == 1


@pytest.mark.parametrize("terminal,item_state", [
    ("failed", "discarded"),
    ("cancelled", "cancelled"),
])
@pytest.mark.parametrize("output_format", ["json", "summary"])
def test_deep_mode_terminal_failure_preserves_item_diagnostics(
    monkeypatch, capsys, terminal, item_state, output_format
):
    mock_catalogs(monkeypatch)
    result = {
        "prow_job_build_id": "1856789012345678848",
        "status": "eval_error",
        "error": "artifact scan failed",
        "symptoms_evaluated": 3,
    }
    terminal_response = batch_response(status=terminal, items=[{
        "item_key": "1856789012345678848",
        "state": item_state,
        "result": result,
    }])
    calls = queue_authenticated_responses(
        monkeypatch,
        FakeResponse(202, {
            "batch_id": "batch-1",
            "requested": 1,
            "links": {"status": diagnose_job_run.REEVALUATE_URL + "/batch-1"},
        }),
        FakeResponse(200, terminal_response),
    )

    assert diagnose_job_run.main([
        PROW_URL, "--deep", "--token", "secret", "--format", output_format,
    ]) == 1
    captured = capsys.readouterr()
    assert "batch ended in %s" % terminal in captured.err
    assert "secret" not in captured.out + captured.err
    if output_format == "json":
        failure = json.loads(captured.out)
        assert failure == {
            "batch": terminal_response,
            "batch_id": "batch-1",
            "error": "deep reevaluation batch ended in %s" % terminal,
            "status_url": diagnose_job_run.REEVALUATE_URL + "/batch-1",
        }
        assert "batch-1" in captured.err
    else:
        assert "Deep reevaluation batch batch-1: %s" % terminal in captured.out
        assert "Run 1856789012345678848: %s" % item_state in captured.out
        assert '"status": "eval_error"' in captured.out
        assert '"error": "artifact scan failed"' in captured.out
    assert len(calls) == 2


@pytest.mark.parametrize(
    "failure_kind,expected_error",
    [
        ("network", "connection error: connection lost"),
        ("timeout", "request timed out connecting to the API"),
        ("auth", "HTTP 401 (token missing/expired; use the oc-auth skill): expired"),
        ("malformed", "server returned a non-JSON response body"),
        ("invalid_status", "batch status response is missing integer requested"),
        ("http", "HTTP 500: database unavailable"),
    ],
)
@pytest.mark.parametrize("output_format", ["json", "summary"])
def test_post_submission_poll_failure_retains_recovery_context(
    monkeypatch, capsys, failure_kind, expected_error, output_format
):
    mock_catalogs(monkeypatch)
    status_url = diagnose_job_run.REEVALUATE_URL + "/batch-recover"
    if failure_kind == "network":
        failure = urllib.error.URLError("connection lost")
    elif failure_kind == "timeout":
        failure = socket.timeout("connect timed out")
    elif failure_kind == "auth":
        failure = urllib.error.HTTPError(
            status_url, 401, "Unauthorized", {},
            io.BytesIO(b'{"message":"expired"}'),
        )
    elif failure_kind == "malformed":
        failure = FakeResponse(200, "not json")
    elif failure_kind == "invalid_status":
        failure = FakeResponse(200, {
            "batch_id": "batch-recover", "status": "complete",
        })
    else:
        failure = urllib.error.HTTPError(
            status_url, 500, "Internal Server Error", {},
            io.BytesIO(b'{"message":"database unavailable"}'),
        )
    calls = queue_authenticated_responses(
        monkeypatch,
        FakeResponse(202, {
            "batch_id": "batch-recover",
            "requested": 1,
            "links": {"status": status_url},
        }),
        failure,
    )

    assert diagnose_job_run.main([
        PROW_URL, "--deep", "--token", "secret", "--format", output_format,
    ]) == 1
    captured = capsys.readouterr()
    assert expected_error in captured.err
    assert "batch-recover" in captured.out + captured.err
    assert status_url in captured.out + captured.err
    assert "secret" not in captured.out + captured.err
    if output_format == "json":
        assert json.loads(captured.out) == {
            "batch_id": "batch-recover",
            "error": expected_error,
            "status_url": status_url,
        }
    else:
        assert "Submitted deep reevaluation" in captured.out
    assert len(calls) == 2


def test_deep_mode_unknown_status_is_rejected_before_sleep(monkeypatch, capsys):
    mock_catalogs(monkeypatch)
    calls = queue_authenticated_responses(
        monkeypatch,
        FakeResponse(202, {
            "batch_id": "batch-1",
            "requested": 1,
            "links": {"status": diagnose_job_run.REEVALUATE_URL + "/batch-1"},
        }),
        FakeResponse(200, batch_response(status="mystery")),
    )
    sleeps = []
    monkeypatch.setattr(diagnose_job_run.time, "sleep", sleeps.append)

    assert diagnose_job_run.main([PROW_URL, "--deep", "--token", "secret"]) == 1
    assert "unknown status 'mystery'" in capsys.readouterr().err
    assert len(calls) == 2
    assert sleeps == []


def test_deep_redirect_handler_rejects_cross_origin_and_preserves_same_origin_auth():
    handler = diagnose_job_run.SafeRedirectHandler()
    original = urllib.request.Request(
        diagnose_job_run.REEVALUATE_URL,
        headers={"Authorization": "Bearer secret"},
    )

    same = handler.redirect_request(
        original, None, 302, "Found", {}, diagnose_job_run.REEVALUATE_URL + "/batch-1"
    )
    assert same.get_header("Authorization") == "Bearer secret"
    with pytest.raises(diagnose_job_run.ClientError, match="cross-origin API redirect"):
        handler.redirect_request(
            original, None, 302, "Found", {}, "https://other.invalid/batch-1"
        )
