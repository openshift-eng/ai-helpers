import io
import json
import socket
import urllib.error
import urllib.request

import pytest

import reevaluate_job_runs as client


class FakeResponse:
    def __init__(self, status, body=None, read_error=None):
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


def queue_responses(monkeypatch, *responses):
    calls = []
    pending = list(responses)

    def fake_open(req, timeout=None):
        calls.append((req, timeout))
        response = pending.pop(0)
        if isinstance(response, BaseException):
            raise response
        return response

    monkeypatch.setattr(client.HTTP_OPENER, "open", fake_open)
    monkeypatch.setattr(client.time, "sleep", lambda seconds: None)
    return calls


def batch_response(batch_id="batch-1", status="complete", items=None):
    return {
        "batch_id": batch_id,
        "status": status,
        "requested": 2,
        "enqueued": 2,
        "deduped": 0,
        "completed": 2 if status == "complete" else 0,
        "failed": 2 if status == "failed" else 0,
        "running": 0,
        "pending": 0 if status in client.TERMINAL_STATES else 2,
        "items": items if items is not None else [
            {"item_key": "1", "state": "completed"},
            {"item_key": "2", "state": "completed"},
        ],
    }


@pytest.mark.parametrize(
    "value, expected",
    [
        ("1856789012345678848", "1856789012345678848"),
        ("https://prow.ci.openshift.org/view/gs/b/logs/job/123456/", "123456"),
        ("https://prow.ci.openshift.org/view/gs/b/logs/job/123456?tab=x", "123456"),
        ("https://prow.ci.openshift.org/view/gs/b/logs/job/123456#fragment", "123456"),
    ],
)
def test_extract_build_id(value, expected):
    assert client.extract_build_id(value) == expected


def test_invalid_input_raises():
    with pytest.raises(ValueError, match="numeric build ID"):
        client.extract_build_id("not-a-build-id")


def test_resolve_token_precedence():
    assert client.resolve_token("argtok", {"SIPPY_TOKEN": "envtok"}) == "argtok"
    assert client.resolve_token(None, {"SIPPY_TOKEN": "envtok"}) == "envtok"
    assert client.resolve_token(None, {}) is None


def test_non_dry_run_submits_one_deduplicated_batch_and_polls_complete(monkeypatch, capsys):
    result = {
        "prow_job_build_id": "1",
        "status": "success",
        "symptoms_evaluated": 42,
        "symptoms_matched": ["KnownFailure"],
        "labels_applied": ["InfraFailure"],
        "links": {"job_run": "https://prow.example/1"},
    }
    pending = batch_response(status="running")
    pending.update(completed=0, running=1, pending=1)
    complete = batch_response(items=[
        {"item_key": "1", "state": "completed", "result": result},
        {"item_key": "2", "state": "completed"},
    ])
    calls = queue_responses(
        monkeypatch,
        FakeResponse(202, {
            "batch_id": "batch-1",
            "requested": 2,
            "links": {"status": "/api/jobs/runs/reevaluate/batch-1"},
        }),
        FakeResponse(200, pending),
        FakeResponse(200, complete),
    )

    assert client.main(["2", "1", "2", "--token", "secret"]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output == complete
    assert output["items"][0]["result"] == result
    assert [call[0].get_method() for call in calls] == ["POST", "GET", "GET"]
    assert all(call[1] == client.REQUEST_TIMEOUT_SECONDS for call in calls)
    assert json.loads(calls[0][0].data) == {
        "prow_job_build_ids": ["1", "2"],
        "dry_run": False,
    }


def test_dry_run_submits_202_and_polls_detailed_results(monkeypatch, capsys):
    result = {
        "prow_job_build_id": "1",
        "status": "success",
        "symptoms_evaluated": 5,
        "symptoms_matched": ["KnownFailure"],
        "labels_applied": ["InfraFailure"],
    }
    running = batch_response(status="running", items=[
        {"item_key": "1", "state": "running"},
    ])
    running.update(requested=1, enqueued=1, running=1, pending=0)
    response = batch_response(items=[
        {"item_key": "1", "state": "completed", "result": result},
    ])
    response.update(requested=1, enqueued=1, completed=1)
    calls = queue_responses(
        monkeypatch,
        FakeResponse(202, {
            "batch_id": "batch-1",
            "requested": 1,
            "links": {"status": client.URL + "/batch-1"},
        }),
        FakeResponse(200, running),
        FakeResponse(200, response),
    )

    assert client.main(["1", "--dry-run", "--token", "secret"]) == 0
    assert json.loads(capsys.readouterr().out) == response
    assert [call[0].get_method() for call in calls] == ["POST", "GET", "GET"]
    assert json.loads(calls[0][0].data)["dry_run"] is True


@pytest.mark.parametrize("terminal", ["failed", "cancelled"])
@pytest.mark.parametrize("dry_run", [False, True])
def test_failed_and_cancelled_batches_are_terminal_errors(monkeypatch, capsys, terminal, dry_run):
    queue_responses(
        monkeypatch,
        FakeResponse(202, {
            "batch_id": "batch-1",
            "requested": 2,
            "links": {"status": client.URL + "/batch-1"},
        }),
        FakeResponse(200, batch_response(status=terminal)),
    )

    args = ["1", "2", "--token", "secret"]
    if dry_run:
        args.append("--dry-run")
    assert client.main(args) == 1
    assert json.loads(capsys.readouterr().out)["status"] == terminal


def test_summary_preserves_detailed_item_result(monkeypatch, capsys):
    result = {"status": "rewrite_error", "error": "backend failed", "labels_applied": ["a", "b"]}
    response = batch_response(items=[
        {"item_key": "1", "state": "completed", "result": result},
        {"item_key": "2", "state": "completed"},
    ])
    queue_responses(
        monkeypatch,
        FakeResponse(202, {
            "batch_id": "batch-1",
            "requested": 2,
            "links": {"status": client.URL + "/batch-1"},
        }),
        FakeResponse(200, response),
    )

    assert client.main(["1", "2", "--token", "secret", "--format", "summary"]) == 0
    output = capsys.readouterr().out
    assert "Requested: 2, enqueued: 2, deduped: 0" in output
    assert "Run 1: completed" in output
    assert '"error": "backend failed"' in output
    assert '"labels_applied": [' in output


def test_dry_run_summary_preserves_detailed_item_result(monkeypatch, capsys):
    result = {
        "prow_job_build_id": "1",
        "status": "success",
        "symptoms_evaluated": 5,
        "symptoms_matched": ["KnownFailure"],
        "labels_applied": ["InfraFailure"],
    }
    response = batch_response(items=[
        {"item_key": "1", "state": "completed", "result": result},
    ])
    response.update(requested=1, enqueued=1, completed=1)
    queue_responses(
        monkeypatch,
        FakeResponse(202, {
            "batch_id": "batch-1",
            "requested": 1,
            "links": {"status": client.URL + "/batch-1"},
        }),
        FakeResponse(200, response),
    )

    assert client.main(["1", "--dry-run", "--token", "secret", "--format", "summary"]) == 0
    output = capsys.readouterr().out
    assert "Reevaluation (DRY RUN) — batch batch-1: complete" in output
    assert "Run 1: completed" in output
    assert '"symptoms_evaluated": 5' in output
    assert '"labels_applied": [' in output


def test_more_than_10000_unique_ids_is_rejected_before_network(monkeypatch, capsys):
    calls = queue_responses(monkeypatch)
    ids = [str(value) for value in range(client.API_MAX_IDS + 1)]

    assert client.main(ids + ["--token", "secret"]) == 1
    assert "maximum 10000 unique job run IDs" in capsys.readouterr().err
    assert calls == []


def test_10000_ids_are_submitted_in_one_request(monkeypatch, capsys):
    ids = [str(value) for value in range(client.API_MAX_IDS)]
    terminal = batch_response()
    terminal.update(requested=client.API_MAX_IDS, enqueued=client.API_MAX_IDS,
                    completed=client.API_MAX_IDS, items=[])
    calls = queue_responses(
        monkeypatch,
        FakeResponse(202, {
            "batch_id": "batch-1",
            "requested": client.API_MAX_IDS,
            "links": {"status": client.URL + "/batch-1"},
        }),
        FakeResponse(200, terminal),
    )

    assert client.main(ids + ["--token", "secret"]) == 0
    capsys.readouterr()
    assert len(calls) == 2
    assert len(json.loads(calls[0][0].data)["prow_job_build_ids"]) == client.API_MAX_IDS


@pytest.mark.parametrize(
    "response, message",
    [
        (FakeResponse(202, "not json"), "malformed JSON"),
        (FakeResponse(202, {}), "missing batch_id"),
        (FakeResponse(202, {"batch_id": "x", "requested": 1, "links": {}}), "links.status"),
    ],
)
def test_malformed_api_responses_are_controlled(monkeypatch, capsys, response, message):
    queue_responses(monkeypatch, response)

    assert client.main(["1", "--token", "secret"]) == 1
    assert message in capsys.readouterr().err


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
    queue_responses(monkeypatch, FakeResponse(200, body))

    with pytest.raises(client.ClientError) as caught:
        client.request_json("POST", client.URL, "secret", 202, {"dry_run": True})

    assert str(caught.value) == "expected HTTP 202, got HTTP 200: %s" % expected_detail


def test_malformed_status_response_is_controlled(monkeypatch, capsys):
    queue_responses(
        monkeypatch,
        FakeResponse(202, {
            "batch_id": "batch-1", "requested": 1,
            "links": {"status": client.URL + "/batch-1"},
        }),
        FakeResponse(200, {"batch_id": "batch-1", "status": "complete"}),
    )

    assert client.main(["1", "--token", "secret"]) == 1
    assert "missing integer requested" in capsys.readouterr().err


@pytest.mark.parametrize("status", sorted(client.NONTERMINAL_STATES))
def test_every_nonterminal_status_continues_polling(monkeypatch, capsys, status):
    intermediate = batch_response(status=status)
    terminal = batch_response(status="complete")
    calls = queue_responses(
        monkeypatch,
        FakeResponse(202, {
            "batch_id": "batch-1", "requested": 2,
            "links": {"status": client.URL + "/batch-1"},
        }),
        FakeResponse(200, intermediate),
        FakeResponse(200, terminal),
    )

    assert client.main(["1", "2", "--token", "secret"]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "complete"
    assert [call[0].get_method() for call in calls] == ["POST", "GET", "GET"]


def test_unknown_batch_status_is_controlled_before_sleep(monkeypatch, capsys):
    calls = queue_responses(
        monkeypatch,
        FakeResponse(202, {
            "batch_id": "batch-1", "requested": 2,
            "links": {"status": client.URL + "/batch-1"},
        }),
        FakeResponse(200, batch_response(status="mystery")),
    )
    sleeps = []
    monkeypatch.setattr(client.time, "sleep", sleeps.append)

    assert client.main(["1", "2", "--token", "secret"]) == 1
    assert "unknown status 'mystery'" in capsys.readouterr().err
    assert [call[0].get_method() for call in calls] == ["POST", "GET"]
    assert sleeps == []


def test_http_api_error_is_controlled(monkeypatch, capsys):
    error = urllib.error.HTTPError(
        client.URL, 500, "Internal Server Error", {},
        io.BytesIO(b'{"message":"database unavailable"}'),
    )
    queue_responses(monkeypatch, error)

    assert client.main(["1", "--token", "secret"]) == 1
    assert "HTTP 500: database unavailable" in capsys.readouterr().err


@pytest.mark.parametrize(
    "failure, expected",
    [
        (socket.timeout("connect timed out"), "timed out connecting"),
        (urllib.error.URLError(socket.timeout("connect timed out")), "timed out connecting"),
        (FakeResponse(202, read_error=socket.timeout("read timed out")), "timed out while reading"),
    ],
)
def test_socket_and_read_timeouts_are_controlled(monkeypatch, capsys, failure, expected):
    queue_responses(monkeypatch, failure)

    assert client.main(["1", "--token", "secret"]) == 1
    assert expected in capsys.readouterr().err


def test_sso_login_page_is_controlled_auth_error(monkeypatch, capsys):
    queue_responses(monkeypatch, FakeResponse(202, "<html>Log in to your account</html>"))

    assert client.main(["1", "--token", "secret"]) == 1
    assert "token is missing/expired" in capsys.readouterr().err


def test_cross_origin_status_link_is_rejected_without_get(monkeypatch, capsys):
    calls = queue_responses(monkeypatch, FakeResponse(202, {
        "batch_id": "batch-1",
        "requested": 1,
        "links": {"status": "https://attacker.invalid/status/batch-1"},
    }))

    assert client.main(["1", "--token", "secret"]) == 1
    assert "cross-origin status URL" in capsys.readouterr().err
    assert len(calls) == 1


def test_invalid_port_in_status_link_is_a_controlled_error(monkeypatch, capsys):
    calls = queue_responses(monkeypatch, FakeResponse(202, {
        "batch_id": "batch-1",
        "requested": 1,
        "links": {"status": "https://sippy-auth.dptools.openshift.org:bad/status"},
    }))

    assert client.main(["1", "--token", "secret"]) == 1
    error = capsys.readouterr().err
    assert "invalid links.status URL" in error
    assert "Port could not be cast" in error
    assert len(calls) == 1


def test_redirect_handler_rejects_cross_origin_but_keeps_same_origin_auth():
    handler = client.SafeRedirectHandler()
    original = urllib.request.Request(client.URL, headers={"Authorization": "Bearer secret"})

    same = handler.redirect_request(
        original, None, 302, "Found", {}, client.URL + "/batch-1"
    )

    assert same.get_header("Authorization") == "Bearer secret"
    with pytest.raises(client.ClientError, match="cross-origin API redirect"):
        handler.redirect_request(
            original, None, 302, "Found", {}, "https://other.invalid/batch-1"
        )


def test_missing_token_and_invalid_poll_interval_are_validation_errors(capsys):
    assert client.main(["1"]) == 1
    assert "no token" in capsys.readouterr().err
    assert client.main(["1", "--token", "secret", "--poll-interval", "0"]) == 1
    assert "finite and greater than zero" in capsys.readouterr().err


@pytest.mark.parametrize("value", ["nan", "inf", "-inf"])
def test_nonfinite_poll_interval_is_rejected_before_network(monkeypatch, capsys, value):
    calls = queue_responses(monkeypatch)

    assert client.main(["1", "--token", "secret", "--poll-interval=" + value]) == 1
    assert "finite and greater than zero" in capsys.readouterr().err
    assert calls == []
