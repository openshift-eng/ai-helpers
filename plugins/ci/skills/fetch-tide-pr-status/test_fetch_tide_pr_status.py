import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(__file__))

from fetch_tide_pr_status import build_job_entry, build_pr_result, classify_jobs, match_tide_queries


# -- Fixtures --

def _pr_meta(repo="openshift/test-repo", branch="main", labels=None,
             mergeable=True, draft=False):
    return {
        "number": 1,
        "title": "Test PR",
        "user": {"login": "dev"},
        "html_url": f"https://github.com/{repo}/pull/1",
        "state": "open",
        "draft": draft,
        "mergeable": mergeable,
        "base": {
            "ref": branch,
            "repo": {"full_name": repo},
        },
        "labels": [{"name": l} for l in (labels or [])],
    }


def _status_data(statuses):
    return {"statuses": statuses}


def _status(context, state="success", description="", url=""):
    return {
        "context": context,
        "state": state,
        "description": description,
        "target_url": url,
    }


def _tide_queries(repo="openshift/test-repo", labels=None, missing_labels=None,
                  included_branches=None):
    q = {"repos": [repo]}
    if labels:
        q["labels"] = labels
    if missing_labels:
        q["missingLabels"] = missing_labels
    if included_branches:
        q["includedBranches"] = included_branches
    return [q]


def _presubmit_configs(branch="main", jobs=None):
    """Build a presubmit_configs dict keyed by branch."""
    if jobs is None:
        jobs = {}
    return {branch: jobs}


# -- Tests: build_job_entry --

def test_build_job_entry_success():
    e = build_job_entry("ci/prow/e2e", "success", "Build succeeded.", "")
    assert e == {"name": "ci/prow/e2e", "state": "success"}


def test_build_job_entry_failure_includes_url():
    e = build_job_entry("ci/prow/e2e", "failure", "Build failed.",
                        "https://prow.ci/view/123")
    assert e["state"] == "failure"
    assert e["url"] == "https://prow.ci/view/123"


def test_build_job_entry_pending_normalised_to_running():
    e = build_job_entry("ci/prow/e2e", "pending", "Running tests.", "")
    assert e["state"] == "running"


def test_build_job_entry_pending_pipeline():
    e = build_job_entry("ci/prow/e2e", "pending",
                        "Waiting for pipeline to start.", "")
    assert e["state"] == "awaiting_pipeline"


# -- Tests: required jobs correctly extracted from statuses --

def test_required_jobs_extracted():
    statuses = _status_data([
        _status("ci/prow/e2e-aws", "success"),
        _status("ci/prow/e2e-gcp", "failure"),
        _status("ci/prow/optional-lint", "success"),
    ])
    config = _presubmit_configs(jobs={
        "ci/prow/e2e-aws": {"always_run": True, "optional": False},
        "ci/prow/e2e-gcp": {"always_run": True, "optional": False},
        "ci/prow/optional-lint": {"always_run": True, "optional": True},
    })
    queries = _tide_queries()
    result = build_pr_result(1, _pr_meta(), statuses, queries, config)
    names = [j["name"] for j in result["required_jobs"]]
    assert "ci/prow/e2e-aws" in names
    assert "ci/prow/e2e-gcp" in names
    assert "ci/prow/optional-lint" not in names


# -- Tests: missing required contexts detected --

def test_missing_required_contexts_detected():
    """Required contexts in config that have NO entry in reported statuses."""
    statuses = _status_data([
        _status("ci/prow/e2e-aws", "success"),
    ])
    config = _presubmit_configs(jobs={
        "ci/prow/e2e-aws": {"always_run": True, "optional": False},
        "ci/prow/e2e-gcp": {"always_run": True, "optional": False},
        "ci/prow/images": {"always_run": True, "optional": False},
    })
    queries = _tide_queries()
    result = build_pr_result(1, _pr_meta(), statuses, queries, config)
    names = {j["name"] for j in result["required_jobs"]}
    assert "ci/prow/e2e-gcp" in names
    assert "ci/prow/images" in names


def test_not_reported_state_appears():
    """Missing required contexts have state 'not_reported'."""
    statuses = _status_data([
        _status("ci/prow/e2e-aws", "success"),
    ])
    config = _presubmit_configs(jobs={
        "ci/prow/e2e-aws": {"always_run": True, "optional": False},
        "ci/prow/e2e-gcp": {"always_run": True, "optional": False},
    })
    queries = _tide_queries()
    result = build_pr_result(1, _pr_meta(), statuses, queries, config)
    missing = [j for j in result["required_jobs"] if j["name"] == "ci/prow/e2e-gcp"]
    assert len(missing) == 1
    assert missing[0]["state"] == "not_reported"


def test_optional_missing_contexts_not_included():
    """Optional contexts missing from statuses should NOT appear."""
    statuses = _status_data([])
    config = _presubmit_configs(jobs={
        "ci/prow/optional-lint": {"always_run": False, "optional": True},
        "ci/prow/e2e-aws": {"always_run": True, "optional": False},
    })
    queries = _tide_queries()
    result = build_pr_result(1, _pr_meta(), statuses, queries, config)
    names = {j["name"] for j in result["required_jobs"]}
    assert "ci/prow/optional-lint" not in names
    assert "ci/prow/e2e-aws" in names


# -- Tests: blockers include both failed AND missing required jobs --

def test_blockers_include_failed_jobs():
    statuses = _status_data([
        _status("ci/prow/e2e-aws", "failure"),
    ])
    config = _presubmit_configs(jobs={
        "ci/prow/e2e-aws": {"always_run": True, "optional": False},
    })
    queries = _tide_queries()
    result = build_pr_result(1, _pr_meta(), statuses, queries, config)
    assert any("ci/prow/e2e-aws" in b and "failure" in b for b in result["blockers"])


def test_blockers_include_missing_required_jobs():
    statuses = _status_data([])
    config = _presubmit_configs(jobs={
        "ci/prow/e2e-aws": {"always_run": True, "optional": False},
    })
    queries = _tide_queries()
    result = build_pr_result(1, _pr_meta(), statuses, queries, config)
    assert any("ci/prow/e2e-aws" in b and "not_reported" in b for b in result["blockers"])


def test_blockers_include_both_failed_and_missing():
    statuses = _status_data([
        _status("ci/prow/e2e-aws", "failure"),
    ])
    config = _presubmit_configs(jobs={
        "ci/prow/e2e-aws": {"always_run": True, "optional": False},
        "ci/prow/e2e-gcp": {"always_run": True, "optional": False},
    })
    queries = _tide_queries()
    result = build_pr_result(1, _pr_meta(), statuses, queries, config)
    blocker_text = " ".join(result["blockers"])
    assert "ci/prow/e2e-aws" in blocker_text
    assert "ci/prow/e2e-gcp" in blocker_text


# -- Tests: label matching --

def test_labels_required_present():
    queries = _tide_queries(labels=["approved", "lgtm"])
    result = build_pr_result(
        1, _pr_meta(labels=["approved", "lgtm"]),
        _status_data([]), queries, _presubmit_configs(jobs={}),
    )
    assert result["labels"]["met"] is True
    assert sorted(result["labels"]["required"]["have"]) == ["approved", "lgtm"]
    assert result["labels"]["required"]["missing"] == []


def test_labels_required_missing():
    queries = _tide_queries(labels=["approved", "lgtm"])
    result = build_pr_result(
        1, _pr_meta(labels=["approved"]),
        _status_data([]), queries, _presubmit_configs(jobs={}),
    )
    assert result["labels"]["met"] is False
    assert "lgtm" in result["labels"]["required"]["missing"]
    assert any("lgtm" in b for b in result["blockers"])


def test_labels_forbidden_absent():
    queries = _tide_queries(missing_labels=["do-not-merge/hold"])
    result = build_pr_result(
        1, _pr_meta(labels=[]),
        _status_data([]), queries, _presubmit_configs(jobs={}),
    )
    assert result["labels"]["met"] is True
    assert result["labels"]["forbidden"]["clear"] == ["do-not-merge/hold"]
    assert result["labels"]["forbidden"]["have"] == []


def test_labels_forbidden_present():
    queries = _tide_queries(missing_labels=["do-not-merge/hold"])
    result = build_pr_result(
        1, _pr_meta(labels=["do-not-merge/hold"]),
        _status_data([]), queries, _presubmit_configs(jobs={}),
    )
    assert result["labels"]["met"] is False
    assert "do-not-merge/hold" in result["labels"]["forbidden"]["have"]
    assert any("do-not-merge/hold" in b for b in result["blockers"])


# -- Tests: output shape --

def test_output_uses_tide_verdict_key():
    statuses = _status_data([
        _status("tide", "success", "Merging."),
    ])
    queries = _tide_queries()
    result = build_pr_result(1, _pr_meta(), statuses, queries,
                             _presubmit_configs(jobs={}))
    assert "tide_verdict" in result
    assert result["tide_verdict"] == "Merging."
    assert "tide" not in result


def test_output_has_no_mergeable_key():
    queries = _tide_queries()
    result = build_pr_result(1, _pr_meta(), _status_data([]), queries,
                             _presubmit_configs(jobs={}))
    assert "mergeable" not in result


# -- Tests: not_in_config (stale/removed) jobs --

def test_not_in_config_jobs_detected():
    """Jobs in statuses but NOT in config appear in required_jobs with state not_in_config."""
    statuses = _status_data([
        _status("ci/prow/e2e-aws", "success"),
        _status("ci/prow/removed-job", "success"),
    ])
    config = _presubmit_configs(jobs={
        "ci/prow/e2e-aws": {"always_run": True, "optional": False},
    })
    queries = _tide_queries()
    result = build_pr_result(1, _pr_meta(), statuses, queries, config)
    nic = [j for j in result["required_jobs"] if j["state"] == "not_in_config"]
    nic_names = {j["name"] for j in nic}
    assert "ci/prow/removed-job" in nic_names
    assert "ci/prow/e2e-aws" not in nic_names
    assert "extra_jobs" not in result


def test_not_in_config_jobs_not_blockers():
    """not_in_config jobs should NOT appear in blockers even if originally failed."""
    statuses = _status_data([
        _status("ci/prow/e2e-aws", "success"),
        _status("ci/prow/removed-job", "failure"),
    ])
    config = _presubmit_configs(jobs={
        "ci/prow/e2e-aws": {"always_run": True, "optional": False},
    })
    queries = _tide_queries()
    result = build_pr_result(1, _pr_meta(), statuses, queries, config)
    assert not any("ci/prow/removed-job" in b for b in result["blockers"])


def test_no_not_in_config_when_all_match():
    """When all reported jobs are in the config, no not_in_config entries exist."""
    statuses = _status_data([
        _status("ci/prow/e2e-aws", "success"),
        _status("ci/prow/unit", "success"),
    ])
    config = _presubmit_configs(jobs={
        "ci/prow/e2e-aws": {"always_run": True, "optional": False},
        "ci/prow/unit": {"always_run": True, "optional": False},
    })
    queries = _tide_queries()
    result = build_pr_result(1, _pr_meta(), statuses, queries, config)
    nic = [j for j in result["required_jobs"] if j["state"] == "not_in_config"]
    assert nic == []
    assert "extra_jobs" not in result


# -- Tests: classify_jobs (pure function, both directions) --

def _job(name, state="success"):
    return {"name": name, "state": state}


_CLASSIFY_CONFIG = {
    "ci/prow/e2e": {"always_run": True, "optional": False},
    "ci/prow/unit": {"always_run": True, "optional": False},
    "ci/prow/lint": {"always_run": True, "optional": True},
    "ci/prow/images": {"always_run": True, "optional": False},
}


def test_classify_required_extracted():
    jobs = [_job("ci/prow/e2e"), _job("ci/prow/unit"), _job("ci/prow/lint")]
    result = classify_jobs(jobs, _CLASSIFY_CONFIG)
    required_names = {j["name"] for j in result["required_jobs"]
                      if j.get("state") != "not_reported"}
    assert "ci/prow/e2e" in required_names
    assert "ci/prow/unit" in required_names
    assert "ci/prow/lint" not in required_names  # optional


def test_classify_missing_required():
    """Config has required contexts not in statuses → not_reported."""
    jobs = [_job("ci/prow/e2e")]
    result = classify_jobs(jobs, _CLASSIFY_CONFIG)
    not_reported = [j for j in result["required_jobs"]
                    if j["state"] == "not_reported"]
    nr_names = {j["name"] for j in not_reported}
    assert "ci/prow/unit" in nr_names
    assert "ci/prow/images" in nr_names
    assert "ci/prow/lint" not in nr_names  # optional


def test_classify_not_in_config_detected():
    """Statuses have jobs not in config → not_in_config in required_jobs."""
    jobs = [_job("ci/prow/e2e"), _job("ci/old-job")]
    result = classify_jobs(jobs, _CLASSIFY_CONFIG)
    nic = [j for j in result["required_jobs"] if j["state"] == "not_in_config"]
    nic_names = {j["name"] for j in nic}
    assert "ci/old-job" in nic_names
    assert "ci/prow/e2e" not in nic_names
    assert "extra_jobs" not in result


def test_classify_all_present_no_extras():
    """When all reported match config, no not_reported and no not_in_config."""
    jobs = [_job("ci/prow/e2e"), _job("ci/prow/unit"),
            _job("ci/prow/lint"), _job("ci/prow/images")]
    result = classify_jobs(jobs, _CLASSIFY_CONFIG)
    not_reported = [j for j in result["required_jobs"]
                    if j.get("state") == "not_reported"]
    assert not_reported == []
    nic = [j for j in result["required_jobs"]
           if j.get("state") == "not_in_config"]
    assert nic == []
    assert "extra_jobs" not in result


def test_classify_empty_statuses():
    """No statuses → all required are not_reported, no not_in_config."""
    result = classify_jobs([], _CLASSIFY_CONFIG)
    nr_names = {j["name"] for j in result["required_jobs"]}
    assert "ci/prow/e2e" in nr_names
    assert "ci/prow/unit" in nr_names
    assert "ci/prow/images" in nr_names
    assert "ci/prow/lint" not in nr_names
    nic = [j for j in result["required_jobs"]
           if j.get("state") == "not_in_config"]
    assert nic == []
    assert "extra_jobs" not in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
