import json
import urllib.request

import pytest

import diagnose_job_run
from diagnose_job_run import (classify_response, format_jira_issues,
                              jira_issue_url, normalize_label_entry, parse_prow_url)


class FakeResponse:
    def __init__(self, status, body):
        self.status = status
        self._body = json.dumps(body).encode("utf-8") if not isinstance(body, str) else body.encode("utf-8")

    def getcode(self):
        return self.status

    def read(self):
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
        return pending.pop(0)

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
        "failed": 1 if status == "failed" else 0,
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
    report = json.loads(capsys.readouterr().out)
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


def test_deep_mode_rejects_cross_origin_status_without_get(monkeypatch, capsys):
    mock_catalogs(monkeypatch)
    calls = queue_authenticated_responses(monkeypatch, FakeResponse(202, {
        "batch_id": "batch-1",
        "requested": 1,
        "links": {"status": "https://attacker.invalid/status"},
    }))

    assert diagnose_job_run.main([PROW_URL, "--deep", "--token", "secret"]) == 1
    assert "cross-origin status URL" in capsys.readouterr().err
    assert len(calls) == 1


@pytest.mark.parametrize("terminal", ["failed", "cancelled"])
def test_deep_mode_terminal_failure_is_controlled(monkeypatch, capsys, terminal):
    mock_catalogs(monkeypatch)
    calls = queue_authenticated_responses(
        monkeypatch,
        FakeResponse(202, {
            "batch_id": "batch-1",
            "requested": 1,
            "links": {"status": diagnose_job_run.REEVALUATE_URL + "/batch-1"},
        }),
        FakeResponse(200, batch_response(status=terminal)),
    )

    assert diagnose_job_run.main([PROW_URL, "--deep", "--token", "secret"]) == 1
    assert "batch ended in %s" % terminal in capsys.readouterr().err
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
