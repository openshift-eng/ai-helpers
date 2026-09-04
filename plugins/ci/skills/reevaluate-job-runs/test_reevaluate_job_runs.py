import io
import json
import socket
import urllib.error

import pytest

import reevaluate_job_runs
from reevaluate_job_runs import (
    APIError,
    MalformedResponseError,
    extract_build_id,
    poll_batch,
    submit_batch,
)


BATCH_ID = "6e2c31fa-298d-4b9e-89bc-bc94f58c1082"
STATUS_URL = reevaluate_job_runs.URL + "/" + BATCH_ID


def test_plain_numeric_id():
    assert extract_build_id("1856789012345678848") == "1856789012345678848"


def test_prow_url():
    url = (
        "https://prow.ci.openshift.org/view/gs/test-platform-results/logs/"
        "periodic-ci-openshift-release-master-ci-4.20-e2e-aws-ovn/1856789012345678848"
    )
    assert extract_build_id(url) == "1856789012345678848"


def test_prow_url_trailing_slash():
    assert extract_build_id("https://prow.ci.openshift.org/view/gs/b/logs/job/123456/") == "123456"


def test_url_with_query_string_and_fragment():
    assert (
        extract_build_id("https://prow.ci.openshift.org/view/gs/b/logs/job/123456?tab=x#fragment")
        == "123456"
    )


def test_invalid_input_raises():
    with pytest.raises(ValueError):
        extract_build_id("not-a-build-id")


def test_resolve_token_arg_wins_over_env():
    assert reevaluate_job_runs.resolve_token("argtok", {"SIPPY_TOKEN": "envtok"}) == "argtok"


def test_resolve_token_falls_back_to_env():
    assert reevaluate_job_runs.resolve_token(None, {"SIPPY_TOKEN": "envtok"}) == "envtok"


def test_resolve_token_none_when_unset():
    assert reevaluate_job_runs.resolve_token(None, {}) is None


class FakeResponse:
    def __init__(self, body, status=200):
        self._body = body.encode("utf-8")
        self.status = status

    def read(self):
        return self._body

    def getcode(self):
        return self.status

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def _patch_open_url(monkeypatch, responses):
    """Make the HTTP opener return or raise each entry in responses."""
    calls = []

    def fake_open_url(req, timeout=None):
        calls.append((req, timeout))
        response = responses[len(calls) - 1]
        if isinstance(response, Exception):
            raise response
        if isinstance(response, FakeResponse):
            return response
        status, body = response
        if not isinstance(body, str):
            body = json.dumps(body)
        return FakeResponse(body, status)

    monkeypatch.setattr(reevaluate_job_runs, "_open_url", fake_open_url)
    return calls


def _submission(include_link=True):
    response = {"batch_id": BATCH_ID, "requested": 2}
    if include_link:
        response["links"] = {"status": STATUS_URL}
    return response


def _status(status="complete", **overrides):
    response = {
        "batch_id": BATCH_ID,
        "status": status,
        "requested": 2,
        "enqueued": 2,
        "deduped": 0,
        "completed": 2 if status == "complete" else 0,
        "failed": 2 if status == "failed" else 0,
        "running": 0,
        "pending": 0,
        "items": [
            {"item_key": "1", "state": "completed"},
            {"item_key": "2", "state": "completed"},
        ],
    }
    response.update(overrides)
    return response


def _http_error(code, body='{"message":"server problem"}'):
    return urllib.error.HTTPError(
        STATUS_URL,
        code,
        "error",
        {},
        io.BytesIO(body.encode("utf-8")),
    )


def test_submit_batch_sends_one_202_request_with_all_ids_and_dry_run(monkeypatch):
    calls = _patch_open_url(monkeypatch, [(202, _submission())])

    response, status_url = submit_batch(["1", "2"], "tok", True)

    assert response == _submission()
    assert status_url == STATUS_URL
    assert len(calls) == 1
    req, timeout = calls[0]
    assert req.get_method() == "POST"
    assert req.full_url == reevaluate_job_runs.URL
    assert json.loads(req.data) == {"prow_job_build_ids": ["1", "2"], "dry_run": True}
    assert req.headers["Authorization"] == "Bearer tok"
    assert timeout == reevaluate_job_runs.REQUEST_TIMEOUT_SECONDS


def test_submit_batch_uses_documented_status_url_when_link_is_absent(monkeypatch):
    calls = _patch_open_url(monkeypatch, [(202, _submission(include_link=False))])

    _, status_url = submit_batch(["1", "2"], "tok", False)

    assert status_url == STATUS_URL
    assert len(calls) == 1


def test_submit_batch_requires_202(monkeypatch):
    _patch_open_url(monkeypatch, [(200, _submission())])

    with pytest.raises(APIError, match="expected HTTP 202, got HTTP 200"):
        submit_batch(["1", "2"], "tok", False)


@pytest.mark.parametrize(
    "response,error",
    [
        ({"requested": 2}, "batch_id"),
        ({"batch_id": BATCH_ID, "requested": "2"}, "requested"),
        ({"batch_id": BATCH_ID, "requested": 1}, "does not match"),
        (
            {
                "batch_id": BATCH_ID,
                "requested": 2,
                "links": {"status": "https://example.invalid/steal-token"},
            },
            "does not match the documented endpoint",
        ),
    ],
)
def test_submit_batch_rejects_malformed_response(monkeypatch, response, error):
    _patch_open_url(monkeypatch, [(202, response)])

    with pytest.raises(MalformedResponseError, match=error):
        submit_batch(["1", "2"], "tok", False)


def test_submit_batch_reports_http_error_without_retry(monkeypatch):
    calls = _patch_open_url(monkeypatch, [_http_error(500)])

    with pytest.raises(APIError, match="HTTP 500: server problem"):
        submit_batch(["1", "2"], "tok", False)
    assert len(calls) == 1


def test_submit_batch_detects_sso_login_page(monkeypatch):
    _patch_open_url(monkeypatch, [(202, "<html><body>Log in to your account</body></html>")])

    with pytest.raises(APIError, match="token is missing/expired"):
        submit_batch(["1", "2"], "tok", False)


def test_submit_batch_converts_timeout_to_controlled_api_error(monkeypatch):
    _patch_open_url(monkeypatch, [TimeoutError("submission timed out")])

    with pytest.raises(APIError, match="request timeout: submission timed out") as caught:
        submit_batch(["1", "2"], "tok", False)

    assert caught.value.retryable is True


def test_cross_origin_redirect_strips_authorization_header():
    handler = reevaluate_job_runs.SameOriginAuthRedirectHandler()
    request = urllib.request.Request(
        STATUS_URL,
        headers={"Authorization": "Bearer secret", "Accept": "application/json"},
    )

    redirected = handler.redirect_request(
        request,
        None,
        302,
        "Found",
        {},
        "https://attacker.invalid/collect",
    )

    assert redirected.get_header("Authorization") is None
    assert redirected.get_header("Accept") == "application/json"


def test_same_origin_redirect_preserves_authorization_header():
    handler = reevaluate_job_runs.SameOriginAuthRedirectHandler()
    request = urllib.request.Request(
        reevaluate_job_runs.URL,
        headers={"Authorization": "Bearer tok"},
    )

    redirected = handler.redirect_request(
        request,
        None,
        307,
        "Temporary Redirect",
        {},
        reevaluate_job_runs.URL + "/same-origin",
    )

    assert redirected.get_header("Authorization") == "Bearer tok"


def test_poll_batch_follows_nonterminal_states_until_complete(monkeypatch):
    responses = [
        (200, _status("pending", completed=0, pending=2)),
        (200, _status("processing", completed=0, pending=2)),
        (200, _status("running", completed=0, running=1, pending=1)),
        (200, _status("complete")),
    ]
    calls = _patch_open_url(monkeypatch, responses)
    sleeps = []

    response = poll_batch(STATUS_URL, BATCH_ID, "tok", poll_interval=0.01, sleeper=sleeps.append)

    assert response["status"] == "complete"
    assert len(calls) == 4
    assert all(call[0].get_method() == "GET" for call in calls)
    assert sleeps == [0.01, 0.01, 0.01]


@pytest.mark.parametrize("terminal", ["failed", "cancelled"])
def test_poll_batch_returns_terminal_failure_and_cancelled(monkeypatch, terminal):
    calls = _patch_open_url(monkeypatch, [(200, _status(terminal))])

    response = poll_batch(STATUS_URL, BATCH_ID, "tok", sleeper=lambda _: None)

    assert response["status"] == terminal
    assert len(calls) == 1


def test_poll_batch_retries_transient_http_error(monkeypatch):
    calls = _patch_open_url(monkeypatch, [_http_error(503), (200, _status())])
    sleeps = []

    response = poll_batch(STATUS_URL, BATCH_ID, "tok", poll_interval=0.01, sleeper=sleeps.append)

    assert response["status"] == "complete"
    assert len(calls) == 2
    assert sleeps == [0.01]


class ReadTimeoutResponse(FakeResponse):
    def __init__(self):
        super().__init__("", 200)

    def read(self):
        raise socket.timeout("response read timed out")


def test_poll_batch_retries_response_read_timeout(monkeypatch):
    calls = _patch_open_url(monkeypatch, [ReadTimeoutResponse(), (200, _status())])
    sleeps = []

    response = poll_batch(
        STATUS_URL,
        BATCH_ID,
        "tok",
        poll_interval=0.01,
        sleeper=sleeps.append,
    )

    assert response["status"] == "complete"
    assert len(calls) == 2
    assert sleeps == [0.01]


def test_poll_batch_stops_after_consecutive_timeout_errors(monkeypatch):
    errors = [TimeoutError("timed out")] * reevaluate_job_runs.MAX_CONSECUTIVE_POLL_ERRORS
    calls = _patch_open_url(monkeypatch, errors)
    sleeps = []

    with pytest.raises(APIError, match="lost connection to batch status after 5 attempts"):
        poll_batch(
            STATUS_URL,
            BATCH_ID,
            "tok",
            poll_interval=0.01,
            sleeper=sleeps.append,
        )

    assert len(calls) == reevaluate_job_runs.MAX_CONSECUTIVE_POLL_ERRORS
    assert sleeps == [0.01] * (reevaluate_job_runs.MAX_CONSECUTIVE_POLL_ERRORS - 1)


def test_poll_batch_does_not_retry_auth_error(monkeypatch):
    calls = _patch_open_url(monkeypatch, [_http_error(401)])

    with pytest.raises(APIError, match="token missing/expired"):
        poll_batch(STATUS_URL, BATCH_ID, "tok", sleeper=lambda _: None)
    assert len(calls) == 1


@pytest.mark.parametrize(
    "response,error",
    [
        (_status("mystery"), "unknown status"),
        (_status(batch_id="different"), "batch_id does not match"),
        (_status(items=None), "items list"),
        (_status(completed="2"), "completed count"),
        (_status(items=[{"item_key": "1"}]), "invalid item"),
    ],
)
def test_poll_batch_rejects_malformed_status_response(monkeypatch, response, error):
    _patch_open_url(monkeypatch, [(200, response)])

    with pytest.raises(MalformedResponseError, match=error):
        poll_batch(STATUS_URL, BATCH_ID, "tok", sleeper=lambda _: None)


def test_main_deduplicates_inputs_and_preserves_dry_run_json(monkeypatch, capsys):
    submitted = {}

    def fake_submit(ids, token, dry_run):
        submitted.update(ids=ids, token=token, dry_run=dry_run)
        return _submission(), STATUS_URL

    monkeypatch.setattr(reevaluate_job_runs, "submit_batch", fake_submit)
    monkeypatch.setattr(reevaluate_job_runs, "poll_batch", lambda *args: _status())

    rc = reevaluate_job_runs.main(
        ["2", "https://prow.ci.openshift.org/view/gs/b/logs/job/1", "2", "--token", "tok", "--dry-run"]
    )

    assert rc == 0
    assert submitted == {"ids": ["1", "2"], "token": "tok", "dry_run": True}
    output = json.loads(capsys.readouterr().out)
    assert output == {"submission": _submission(), "status": _status()}


def test_main_submission_api_error_emits_structured_json(monkeypatch, capsys):
    def fail_submission(*args):
        raise APIError("HTTP 503: unavailable", retryable=True)

    monkeypatch.setattr(reevaluate_job_runs, "submit_batch", fail_submission)

    rc = reevaluate_job_runs.main(["1", "2", "--token", "tok", "--format", "json"])

    captured = capsys.readouterr()
    output = json.loads(captured.out)
    assert rc == 1
    assert "Error: HTTP 503: unavailable" in captured.err
    assert output["submission"] is None
    assert output["status"] is None
    assert output["failed_batches"] == [
        {
            "batch": 1,
            "ids": ["1", "2"],
            "stage": "submission",
            "error": "HTTP 503: unavailable",
        }
    ]


def test_main_poll_api_error_emits_structured_json_with_batch_id(monkeypatch, capsys):
    monkeypatch.setattr(
        reevaluate_job_runs,
        "submit_batch",
        lambda *args: (_submission(), STATUS_URL),
    )

    def fail_poll(*args):
        raise APIError("lost connection to batch status after 5 attempts")

    monkeypatch.setattr(reevaluate_job_runs, "poll_batch", fail_poll)

    rc = reevaluate_job_runs.main(["1", "2", "--token", "tok", "--format", "json"])

    captured = capsys.readouterr()
    output = json.loads(captured.out)
    assert rc == 1
    assert "Error: lost connection" in captured.err
    assert output["submission"] == _submission()
    assert output["status"] is None
    assert output["failed_batches"] == [
        {
            "batch": 1,
            "ids": ["1", "2"],
            "stage": "polling",
            "error": "lost connection to batch status after 5 attempts",
            "batch_id": BATCH_ID,
        }
    ]


@pytest.mark.parametrize(
    "final_status,failed_count,expected_rc",
    [
        ("complete", 0, 0),
        ("complete", 1, 1),
        ("failed", 2, 1),
        ("cancelled", 0, 1),
    ],
)
def test_main_exit_code_for_terminal_outcome(
    monkeypatch, capsys, final_status, failed_count, expected_rc
):
    monkeypatch.setattr(
        reevaluate_job_runs,
        "submit_batch",
        lambda *args: (_submission(), STATUS_URL),
    )
    monkeypatch.setattr(
        reevaluate_job_runs,
        "poll_batch",
        lambda *args: _status(final_status, failed=failed_count),
    )

    rc = reevaluate_job_runs.main(["1", "2", "--token", "tok", "--format", "summary"])

    assert rc == expected_rc
    assert "batch %s: %s" % (BATCH_ID, final_status) in capsys.readouterr().out


def test_main_rejects_more_than_api_limit_before_submission(monkeypatch, capsys):
    submit = pytest.fail
    monkeypatch.setattr(reevaluate_job_runs, "submit_batch", submit)
    ids = [str(index) for index in range(reevaluate_job_runs.API_MAX_IDS + 1)]

    rc = reevaluate_job_runs.main(ids + ["--token", "tok"])

    assert rc == 1
    assert "at most 10000 unique job runs" in capsys.readouterr().err
