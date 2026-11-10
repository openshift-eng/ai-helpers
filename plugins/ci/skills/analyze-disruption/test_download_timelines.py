"""Tests for download_timelines.py — input parsing, target extraction, payloads, gather-extra, output formatting."""
import io
import json
import os
import subprocess
import sys
import tempfile
from contextlib import redirect_stdout
from unittest.mock import patch, MagicMock

import pytest

from download_timelines import (
    download_file,
    exit_code,
    extract_payloads,
    extract_target,
    gcloud_env,
    list_timeline_files,
    main,
    parse_runs,
    payload_tag,
    payloads_from_clusterversion,
    print_text,
    process_run,
    sanitize_process_output,
)


def test_parse_runs_single():
    runs = parse_runs("periodic-ci-openshift-release-main-ci-5.0-e2e-gcp-ovn-upgrade:2084701838124257280")
    assert runs == [("periodic-ci-openshift-release-main-ci-5.0-e2e-gcp-ovn-upgrade", "2084701838124257280")]


def test_parse_runs_multiple():
    runs = parse_runs(
        "job-a:111,job-b:222, job-c:333"
    )
    assert runs == [("job-a", "111"), ("job-b", "222"), ("job-c", "333")]


def test_parse_runs_trailing_comma():
    runs = parse_runs("job-a:111,")
    assert runs == [("job-a", "111")]


def test_extract_target_valid():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump({
            "spec": {
                "pod_spec": {
                    "containers": [{
                        "args": [
                            "--image-import-pull-secret=/etc/pull-secret/.dockerconfigjson",
                            "--target=e2e-gcp-ovn-upgrade",
                            "--variant=ci-5.0",
                        ]
                    }]
                }
            }
        }, f)
        f.flush()
        assert extract_target(f.name) == "e2e-gcp-ovn-upgrade"
    os.unlink(f.name)


def test_extract_target_no_target():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump({"spec": {"pod_spec": {"containers": [{"args": ["--foo=bar"]}]}}}, f)
        f.flush()
        assert extract_target(f.name) is None
    os.unlink(f.name)


def test_extract_target_missing_file():
    assert extract_target("/nonexistent/path.json") is None


def test_extract_target_invalid_json():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        f.write("not json")
        f.flush()
        assert extract_target(f.name) is None
    os.unlink(f.name)


def test_list_timeline_files_success():
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = (
        "gs://test-platform-results-public/logs/job/123/artifacts/target/openshift-e2e-test/artifacts/junit/e2e-timelines_spyglass_20260804-000654.json\n"
        "gs://test-platform-results-public/logs/job/123/artifacts/target/openshift-e2e-test/artifacts/junit/e2e-timelines_spyglass_20260804-012513.json\n"
    )
    mock_result.stderr = ""
    with patch("download_timelines.subprocess.run", return_value=mock_result) as run:
        files, error = list_timeline_files("job", "123")
    assert error is None
    assert len(files) == 2
    assert files[0].endswith("000654.json")
    assert files[1].endswith("012513.json")
    assert run.call_args.kwargs["env"]["CLOUDSDK_AUTH_DISABLE_CREDENTIALS"] == "true"


def test_list_timeline_files_failure_keeps_stderr():
    mock_result = MagicMock()
    mock_result.returncode = 1
    mock_result.stdout = ""
    mock_result.stderr = (
        "ERROR: There was a problem refreshing your current auth tokens: "
        "Reauthentication failed. cannot prompt during non-interactive execution.\n"
    )
    with patch("download_timelines.subprocess.run", return_value=mock_result):
        files, error = list_timeline_files("job", "123")
    assert files == []
    assert error is not None
    assert "Reauthentication failed" in error
    assert "cannot prompt during non-interactive execution" in error


def test_list_timeline_files_no_matches_is_not_a_command_failure():
    mock_result = MagicMock()
    mock_result.returncode = 1
    mock_result.stdout = ""
    mock_result.stderr = "ERROR: (gcloud.storage.ls) One or more URLs matched no objects.\n"
    with patch("download_timelines.subprocess.run", return_value=mock_result):
        files, error = list_timeline_files("job", "123")
    assert files == []
    assert error is None


def test_process_run_full_success():
    prowjob_data = {
        "spec": {
            "pod_spec": {
                "containers": [{
                    "args": ["--target=e2e-gcp-ovn-upgrade"]
                }]
            }
        }
    }

    def mock_subprocess_run(cmd, **kwargs):
        result = MagicMock()
        if "cp" in cmd:
            if "prowjob.json" in cmd[3]:
                dest = cmd[4]
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                with open(dest, "w") as f:
                    json.dump(prowjob_data, f)
            else:
                dest = cmd[4]
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                with open(dest, "w") as f:
                    f.write("{}")
            result.returncode = 0
        elif "ls" in cmd:
            result.returncode = 0
            result.stdout = "gs://bucket/path/e2e-timelines_spyglass_20260804-000654.json\n"
        return result

    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("download_timelines.subprocess.run", side_effect=mock_subprocess_run):
            r = process_run("my-job", "999", tmpdir)

    assert r["build_id"] == "999"
    assert r["job"] == "my-job"
    assert r["target"] == "e2e-gcp-ovn-upgrade"
    assert r["error"] is None
    assert len(r["timeline_files"]) == 1
    assert r["timeline_files"][0].endswith("e2e-timelines_spyglass_20260804-000654.json")


def test_process_run_prowjob_download_fails():
    mock_result = MagicMock()
    mock_result.returncode = 1
    mock_result.stdout = ""
    mock_result.stderr = (
        "Reauthentication failed. cannot prompt during non-interactive execution. "
        "token ya29.super-secret-token"
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("download_timelines.subprocess.run", return_value=mock_result):
            r = process_run("my-job", "999", tmpdir)

    assert r["error"].startswith("failed to download prowjob.json:")
    assert "Reauthentication failed" in r["error"]
    assert "ya29." not in r["error"]
    assert "[redacted]" in r["error"]
    assert r["timeline_files"] == []


def test_process_run_listing_failure_is_not_an_empty_list():
    prowjob_data = {"spec": {"pod_spec": {"containers": [{"args": ["--target=e2e"]}]}}}

    def mock_subprocess_run(cmd, **kwargs):
        result = MagicMock()
        result.stdout = ""
        result.stderr = ""
        if "cp" in cmd:
            dest = cmd[4]
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            with open(dest, "w") as f:
                json.dump(prowjob_data, f)
            result.returncode = 0
        else:
            result.returncode = 1
            result.stderr = "ERROR: HTTPSConnectionPool: network is unreachable"
        return result

    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("download_timelines.subprocess.run", side_effect=mock_subprocess_run):
            r = process_run("my-job", "999", tmpdir)
        assert os.path.isfile(os.path.join(tmpdir, "999", "logs", "prowjob.json"))

    assert r["target"] == "e2e"
    assert r["timeline_files"] == []
    assert r["error"].startswith("failed to list timeline files:")
    assert "network is unreachable" in r["error"]


def test_process_run_keeps_successful_timeline_when_another_fails():
    prowjob_data = {"spec": {"pod_spec": {"containers": [{"args": ["--target=e2e"]}]}}}

    def mock_subprocess_run(cmd, **kwargs):
        result = MagicMock()
        result.stdout = ""
        result.stderr = ""
        result.returncode = 0
        if "cp" in cmd and "prowjob.json" in cmd[3]:
            dest = cmd[4]
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            with open(dest, "w") as f:
                json.dump(prowjob_data, f)
        elif "ls" in cmd:
            result.stdout = (
                "gs://bucket/e2e-timelines_spyglass_ok.json\n"
                "gs://bucket/e2e-timelines_spyglass_bad.json\n"
            )
        elif "cp" in cmd and cmd[3].endswith("bad.json"):
            result.returncode = 1
            result.stderr = "ERROR: timed out reading the object"
        else:
            dest = cmd[4]
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            with open(dest, "w") as f:
                f.write("{}")
        return result

    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("download_timelines.subprocess.run", side_effect=mock_subprocess_run):
            r = process_run("my-job", "999", tmpdir)

    assert len(r["timeline_files"]) == 1
    assert r["timeline_files"][0].endswith("e2e-timelines_spyglass_ok.json")
    assert "1 of 2 timeline file downloads failed" in r["error"]
    assert "timed out reading the object" in r["error"]


def test_download_file_timeout_and_launch_errors():
    with patch("download_timelines.subprocess.run",
               side_effect=subprocess.TimeoutExpired(cmd=["gcloud"], timeout=120)):
        ok, error = download_file("gs://bucket/prowjob.json", "/tmp/prowjob.json")
    assert ok is False
    assert error == "timed out after 120s"

    with patch("download_timelines.subprocess.run",
               side_effect=OSError(2, "No such file or directory")):
        ok, error = download_file("gs://bucket/prowjob.json", "/tmp/prowjob.json")
    assert ok is False
    assert error == "failed to start gcloud: No such file or directory"


def test_gcloud_env_does_not_change_process_environment():
    before = os.environ.get("CLOUDSDK_AUTH_DISABLE_CREDENTIALS")
    env = gcloud_env()
    assert env["CLOUDSDK_AUTH_DISABLE_CREDENTIALS"] == "true"
    assert os.environ.get("CLOUDSDK_AUTH_DISABLE_CREDENTIALS") == before
    assert env is not os.environ


def test_sanitize_process_output_redacts_tokens():
    text = sanitize_process_output(
        "Reauthentication failed.\naccess_token=ya29.secret-value bearer ya29.other\n"
    )
    assert "Reauthentication failed." in text
    assert "ya29." not in text
    assert "secret-value" not in text


def test_sanitize_process_output_redacts_authorization_headers():
    text = sanitize_process_output(
        "Authorization: Bearer ya29.secret extra context\n"
        "Proxy-Authorization: Basic abcdef== more context\n"
        "access_token=ya29.other-token\n"
    )
    assert "ya29." not in text
    assert "secret" not in text
    assert "abcdef" not in text
    assert "extra context" not in text
    assert "more context" not in text
    assert "other-token" not in text


def test_exit_code_total_partial_and_success():
    assert exit_code([{"error": None, "timeline_files": ["a.json"]}]) == 0
    assert exit_code([
        {"error": None, "timeline_files": ["a.json"]},
        {"error": "failed to download prowjob.json: timed out after 120s", "timeline_files": []},
    ]) == 2
    assert exit_code([
        {"error": "1 of 2 timeline file downloads failed: bad.json: exited 1",
         "timeline_files": ["ok.json"]},
    ]) == 2
    assert exit_code([
        {"error": "failed to download prowjob.json: exited 1", "timeline_files": []},
        {"error": "no timeline files found", "timeline_files": []},
    ]) == 1


def test_main_exit_status(tmp_path=None):
    runs = {
        "1": {"build_id": "1", "job": "job-a", "target": "e2e", "timeline_files": [],
              "error": "failed to download prowjob.json: timed out after 120s"},
        "2": {"build_id": "2", "job": "job-b", "target": "e2e", "timeline_files": ["/tmp/a.json"],
              "error": None},
    }

    def fake_process(job, build_id, output_dir, gather=False):
        return runs[build_id]

    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("download_timelines.check_gcloud"), \
                patch("download_timelines.process_run", side_effect=fake_process):
            try:
                main(["--runs", "job-a:1", "--output-dir", tmpdir, "--format", "json"])
                assert False, "total failure should exit 1"
            except SystemExit as exc:
                assert exc.code == 1
            try:
                main(["--runs", "job-a:1,job-b:2", "--output-dir", tmpdir, "--format", "text"])
                assert False, "partial success should exit 2"
            except SystemExit as exc:
                assert exc.code == 2
            runs["1"] = {"build_id": "1", "job": "job-a", "target": "e2e",
                         "timeline_files": ["/tmp/b.json"], "error": None}
            main(["--runs", "job-a:1", "--output-dir", tmpdir, "--format", "text"])



# ---------------------------------------------------------------------------
# Payloads and gather-extra
# ---------------------------------------------------------------------------

UPGRADE_PROWJOB = {
    "metadata": {"annotations": {
        "release.openshift.io/from-tag": "5.0.0-0.nightly-2026-11-09-184859",
        "release.openshift.io/tag": "5.1.0-0.nightly-2026-11-10-075706",
    }},
    "spec": {"pod_spec": {"containers": [{
        "args": ["--target=e2e-gcp-ovn-rt-upgrade"],
        "env": [
            {"name": "RELEASE_IMAGE_LATEST",
             "value": "registry.ci.openshift.org/ocp/release-5:5.1.0-0.nightly-2026-11-10-075706"},
            {"name": "RELEASE_IMAGE_INITIAL",
             "value": "registry.ci.openshift.org/ocp/release-5:5.0.0-0.nightly-2026-11-09-184859"},
        ],
    }]}},
}

CLUSTERVERSION = {"kind": "List", "items": [{"status": {"history": [
    {"state": "Completed", "version": "5.1.0-0.ci-2026-11-09-112923",
     "image": "registry.build04.ci.openshift.org/ci-op-x/release@sha256:d7e1"},
    {"state": "Completed", "version": "5.1.0-0.ci-2026-11-08-232923",
     "image": "registry.build04.ci.openshift.org/ci-op-x/release@sha256:3030"},
]}}]}


def _write_json(data):
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
    json.dump(data, f)
    f.close()
    return f.name


def test_extract_payloads_from_env():
    path = _write_json(UPGRADE_PROWJOB)
    try:
        payloads = extract_payloads(path)
    finally:
        os.unlink(path)
    assert payloads == {
        "initial": "registry.ci.openshift.org/ocp/release-5:5.0.0-0.nightly-2026-11-09-184859",
        "target": "registry.ci.openshift.org/ocp/release-5:5.1.0-0.nightly-2026-11-10-075706",
        "source": "prowjob-env",
    }


def test_extract_payloads_from_annotations_and_missing():
    data = {"metadata": UPGRADE_PROWJOB["metadata"],
            "spec": {"pod_spec": {"containers": [{"args": ["--target=e2e"]}]}}}
    path = _write_json(data)
    try:
        payloads = extract_payloads(path)
    finally:
        os.unlink(path)
    assert payloads == {"initial": "5.0.0-0.nightly-2026-11-09-184859",
                        "target": "5.1.0-0.nightly-2026-11-10-075706",
                        "source": "prowjob-annotations"}

    path = _write_json({"spec": {"pod_spec": {"containers": [{"args": ["--target=e2e-gcp-runc-upgrade"]}]}}})
    try:
        assert extract_payloads(path) == {"initial": None, "target": None, "source": None}
    finally:
        os.unlink(path)
    assert extract_payloads("/nonexistent/prowjob.json")["target"] is None


def test_payloads_from_clusterversion():
    path = _write_json(CLUSTERVERSION)
    try:
        payloads = payloads_from_clusterversion(path)
    finally:
        os.unlink(path)
    assert payloads["initial"] == "5.1.0-0.ci-2026-11-08-232923"
    assert payloads["target"] == "5.1.0-0.ci-2026-11-09-112923"
    assert payloads["source"] == "clusterversion-history"
    assert payloads["target_image"].endswith("sha256:d7e1")
    assert payloads["target_state"] == "Completed"

    path = _write_json({"kind": "List", "items": [{"status": {}}]})
    try:
        assert payloads_from_clusterversion(path)["target"] is None
    finally:
        os.unlink(path)


def test_payload_tag():
    assert payload_tag("registry.ci.openshift.org/ocp/release-5:5.1.0-0.nightly-2026-11-09-143447") == \
        "5.1.0-0.nightly-2026-11-09-143447"
    assert payload_tag("registry.build04.ci.openshift.org:443/ci-op-x/release@sha256:abc") == \
        "registry.build04.ci.openshift.org:443/ci-op-x/release@sha256:abc"
    assert payload_tag("5.1.0-0.nightly-2026-11-09-143447") == "5.1.0-0.nightly-2026-11-09-143447"
    assert payload_tag(None) is None


def _gcs_mock(prowjob, files, calls):
    """subprocess.run stand-in: prowjob.json, one timeline, and gather-extra files by name."""
    def run(cmd, **kwargs):
        calls.append(cmd)
        result = MagicMock()
        result.stdout = ""
        result.stderr = ""
        result.returncode = 0
        if "ls" in cmd:
            result.stdout = "gs://bucket/e2e-timelines_spyglass_1.json\n"
            return result
        src, dest = cmd[3], cmd[4]
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        name = os.path.basename(src)
        if name == "prowjob.json":
            content = prowjob
        elif name in files:
            content = files[name]
        elif name.startswith("e2e-timelines"):
            content = {}
        else:
            result.returncode = 1
            result.stderr = "ERROR: One or more URLs matched no objects."
            return result
        with open(dest, "w") as f:
            json.dump(content, f)
        return result
    return run


def test_process_run_payloads_from_env_skip_clusterversion():
    calls = []
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("download_timelines.subprocess.run", side_effect=_gcs_mock(UPGRADE_PROWJOB, {}, calls)):
            r = process_run("my-job", "999", tmpdir)
    assert r["error"] is None
    assert r["payload_source"] == "prowjob-env"
    assert r["initial_payload"].endswith("5.0.0-0.nightly-2026-11-09-184859")
    assert not any("clusterversion.json" in " ".join(c) for c in calls)
    assert "gather_files" not in r


def test_process_run_falls_back_to_clusterversion():
    prowjob = {"spec": {"pod_spec": {"containers": [{"args": ["--target=e2e-gcp-runc-upgrade"]}]}}}
    calls = []
    with tempfile.TemporaryDirectory() as tmpdir:
        mock = _gcs_mock(prowjob, {"clusterversion.json": CLUSTERVERSION}, calls)
        with patch("download_timelines.subprocess.run", side_effect=mock):
            r = process_run("my-job", "999", tmpdir)
        assert os.path.isfile(os.path.join(tmpdir, "999", "gather", "clusterversion.json"))
    cv_calls = [c for c in calls if c[3].endswith("clusterversion.json")]
    assert cv_calls[0][3] == ("gs://test-platform-results-public/logs/my-job/999/artifacts/"
                              "e2e-gcp-runc-upgrade/gather-extra/artifacts/clusterversion.json")
    assert r["error"] is None
    assert r["initial_payload"] == "5.1.0-0.ci-2026-11-08-232923"
    assert r["target_payload"] == "5.1.0-0.ci-2026-11-09-112923"
    assert r["payload_source"] == "clusterversion-history"
    assert "payload_warning" not in r


def test_process_run_payload_warning_does_not_set_error():
    prowjob = {"spec": {"pod_spec": {"containers": [{"args": ["--target=e2e"]}]}}}
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("download_timelines.subprocess.run", side_effect=_gcs_mock(prowjob, {}, [])):
            r = process_run("my-job", "999", tmpdir)
    assert r["error"] is None
    assert r["target_payload"] is None
    assert "clusterversion.json" in r["payload_warning"]
    assert exit_code([r]) == 0


def test_process_run_gather_downloads_gather_extra():
    calls = []
    files = {"events.json": {"items": []}, "configmaps.json": {"items": []},
             "releaseinfo.json": {"references": {}}}
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("download_timelines.subprocess.run", side_effect=_gcs_mock(UPGRADE_PROWJOB, files, calls)):
            r = process_run("my-job", "999", tmpdir, gather=True)
        gather_dir = os.path.join(tmpdir, "999", "gather")
        assert sorted(os.listdir(gather_dir)) == ["configmaps.json", "events.json", "releaseinfo.json"]
    assert [os.path.basename(p) for p in r["gather_files"]] == [
        "events.json", "configmaps.json", "releaseinfo.json"]
    assert r["gather_error"].startswith("clusterversion.json:")
    assert r["error"] is None
    assert all(c[0] == "gcloud" for c in calls)


def test_print_text_shows_payloads_and_warnings():
    out = io.StringIO()
    with redirect_stdout(out):
        print_text([
            {"build_id": "1", "target": "e2e", "timeline_files": ["/a.json"], "error": None,
             "initial_payload": "registry.ci.openshift.org/ocp/release-5:5.0.0-a",
             "target_payload": "registry.ci.openshift.org/ocp/release-5:5.1.0-b",
             "payload_source": "prowjob-env"},
            {"build_id": "2", "target": "e2e", "timeline_files": ["/b.json"], "error": None,
             "initial_payload": None, "target_payload": None, "payload_source": None,
             "payload_warning": "no history", "gather_files": ["/g/events.json"],
             "gather_error": "releaseinfo.json: exited 1"},
        ])
    text = out.getvalue()
    assert "  payloads: 5.0.0-a -> 5.1.0-b (from prowjob-env)" in text
    assert "  payloads: unknown (no history)" in text
    assert "  /g/events.json" in text
    assert "  WARNING: gather-extra: releaseinfo.json: exited 1" in text


def test_main_passes_gather_flag():
    seen = []

    def fake_process(job, build_id, output_dir, gather=False):
        seen.append(gather)
        return {"build_id": build_id, "job": job, "target": "e2e", "timeline_files": ["/a.json"],
                "error": None}

    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("download_timelines.check_gcloud"), \
                patch("download_timelines.process_run", side_effect=fake_process), \
                redirect_stdout(io.StringIO()):
            main(["--runs", "job-a:1", "--output-dir", tmpdir, "--gather"])
            main(["--runs", "job-a:1", "--output-dir", tmpdir])
    assert seen == [True, False]


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
