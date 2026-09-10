#!/usr/bin/env python3
"""Tests for deterministic PR escape-evidence collection."""

import importlib.util
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location(
    "collect_pr_evidence", HERE / "collect_pr_evidence.py"
)
evidence = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(evidence)


def test_actor_classifies_chai_user_explicitly():
    assert evidence.actor({"login": "redhat-chai-bot", "type": "User"})["kind"] == "chai"
    assert evidence.actor({"login": "openshift-ci[bot]", "type": "Bot"})["kind"] == "automation"
    assert evidence.actor({"login": "maintainer", "type": "User"})["kind"] == "human"


def test_chatops_actions_are_cut_off_at_merge():
    comments = [
        {
            "created_at": "2026-01-01T01:00:00Z",
            "body": "/retest\n/override ci/prow/e2e-aws",
            "user": {"login": "redhat-chai-bot", "type": "User"},
        },
        {
            "created_at": "2026-01-03T01:00:00Z",
            "body": "/override ci/prow/unit",
            "user": {"login": "maintainer", "type": "User"},
        },
    ]

    actions = evidence.extract_chatops_actions(comments, "2026-01-02T00:00:00Z")

    assert [item["action"] for item in actions] == ["retest", "override"]
    assert actions[1]["arguments"] == "ci/prow/e2e-aws"
    assert actions[1]["actor"]["kind"] == "chai"


def test_status_history_counts_terminal_attempts_not_pending_updates():
    statuses = [
        {"context": "ci/prow/e2e", "state": "pending", "created_at": "2026-01-01T00:00:00Z"},
        {"context": "ci/prow/e2e", "state": "failure", "created_at": "2026-01-01T01:00:00Z", "target_url": "build/1"},
        {"context": "ci/prow/e2e", "state": "pending", "created_at": "2026-01-01T02:00:00Z"},
        {"context": "ci/prow/e2e", "state": "success", "created_at": "2026-01-01T03:00:00Z", "target_url": "build/2"},
    ]

    contexts = evidence.normalize_status_contexts(statuses, "2026-01-02T00:00:00Z")

    assert len(contexts) == 1
    assert [attempt["state"] for attempt in contexts[0]["terminal_attempts"]] == [
        "failure",
        "success",
    ]
    assert contexts[0]["retry_count"] == 1


def test_ci_report_rows_preserve_commit_required_flag_and_run_url():
    comments = [{
        "created_at": "2026-01-01T04:00:00Z",
        "user": {"login": "openshift-ci[bot]", "type": "Bot"},
        "body": (
            "ci/prow/e2e-aws | abcdef123 | "
            "[link](https://prow.ci.openshift.org/view/gs/bucket/build) | "
            "false | `/test e2e-aws`"
        ),
    }]

    failures = evidence.extract_ci_reported_failures(
        comments, "2026-01-02T00:00:00Z"
    )

    assert failures == [{
        "context": "ci/prow/e2e-aws",
        "commit_sha": "abcdef123",
        "prow_url": "https://prow.ci.openshift.org/view/gs/bucket/build",
        "required": False,
        "rerun_command": "/test e2e-aws",
        "reported_at": "2026-01-01T04:00:00Z",
        "report_actor": {
            "login": "openshift-ci[bot]",
            "type": "Bot",
            "kind": "automation",
        },
        "report_url": "",
    }]


def test_check_finishing_after_merge_is_still_in_progress_at_cutoff():
    pages = [{"check_runs": [{
        "name": "unit",
        "status": "completed",
        "conclusion": "success",
        "started_at": "2026-01-01T23:00:00Z",
        "completed_at": "2026-01-02T01:00:00Z",
    }]}]

    runs = evidence.normalize_check_runs(pages, "2026-01-02T00:00:00Z")

    assert runs[0]["status"] == "in_progress"
    assert runs[0]["conclusion"] is None
    assert runs[0]["completed_at"] is None


def test_collect_writes_self_contained_merge_time_bundle(tmp_path, monkeypatch):
    pr_meta = {
        "html_url": "https://github.com/openshift/example/pull/7",
        "title": "Break the example",
        "merged_at": "2026-01-02T00:00:00Z",
        "merge_commit_sha": "merge",
        "merged_by": {"login": "openshift-merge-bot[bot]", "type": "Bot"},
        "user": {"login": "author", "type": "User"},
        "base": {"ref": "release-4.22", "sha": "base"},
        "head": {"sha": "head"},
        "labels": [{"name": "verified"}],
    }

    def fake_gh(endpoint, paginate=False):
        if endpoint == "repos/openshift/example/pulls/7":
            return pr_meta, None
        if "/issues/7/comments" in endpoint:
            return [{
                "created_at": "2026-01-01T22:00:00Z",
                "body": "/override ci/prow/e2e",
                "user": {"login": "maintainer", "type": "User"},
            }], None
        if "/pulls/7/reviews" in endpoint:
            return [], None
        if "/statuses" in endpoint:
            return [{
                "context": "ci/prow/e2e",
                "state": "failure",
                "created_at": "2026-01-01T21:00:00Z",
                "target_url": "build/1",
            }], None
        if "/check-runs" in endpoint:
            return [], None
        if endpoint.startswith("repos/openshift/release/commits?"):
            return [{"sha": "release-ref"}], None
        if "contents/ci-operator/config/openshift/example" in endpoint:
            return [{
                "type": "file",
                "name": "openshift-example-release-4.22.yaml",
                "path": "ci-operator/config/openshift/example/openshift-example-release-4.22.yaml",
                "sha": "config-blob",
                "download_url": "https://example/config",
            }], None
        if "contents/ci-operator/jobs/openshift/example" in endpoint:
            return [{
                "type": "file",
                "name": "openshift-example-release-4.22-presubmits.yaml",
                "path": "ci-operator/jobs/openshift/example/openshift-example-release-4.22-presubmits.yaml",
                "sha": "jobs-blob",
                "download_url": "https://example/jobs",
            }], None
        if "contents/.github/workflows" in endpoint:
            return None, "not_found"
        if "contents/.ci-operator.yaml" in endpoint:
            return None, "not_found"
        raise AssertionError(endpoint)

    def fake_download(url, destination):
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(f"source: {url}\n", encoding="utf-8")

    monkeypatch.setattr(evidence, "run_gh_json", fake_gh)
    monkeypatch.setattr(evidence, "download_file", fake_download)

    destination = evidence.collect(
        "https://github.com/openshift/example/pull/7", tmp_path
    )
    bundle = json.loads(destination.read_text(encoding="utf-8"))

    assert bundle["data_complete"] is True
    assert bundle["pr"]["head_sha"] == "head"
    assert bundle["pr"]["merge_mechanism"] == "tide"
    assert bundle["chatops_actions"][0]["actor"]["kind"] == "human"
    assert bundle["status_contexts"][0]["terminal_attempts"][0]["state"] == "failure"
    release = bundle["ci_configuration"]["openshift_release"]
    assert release["ref"] == "release-ref"
    assert len(release["ci_operator_configs"]) == 1
    assert len(release["prow_presubmits"]) == 1
    for item in release["ci_operator_configs"] + release["prow_presubmits"]:
        assert (tmp_path / item["snapshot_path"]).exists()
