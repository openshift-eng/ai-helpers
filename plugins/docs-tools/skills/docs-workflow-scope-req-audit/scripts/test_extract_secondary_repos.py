"""Tests for extract_secondary_repos.py."""

from unittest.mock import patch

import pytest
from extract_secondary_repos import (
    _clean_url,
    _derive_suggested_scope,
    _extract_pr_refs,
    _extract_repo_url,
    extract_secondary_repos,
)


class TestExtractRepoUrl:
    def test_github_pr(self):
        url = "https://github.com/kagenti/kagenti-operator/pull/262"
        assert _extract_repo_url(url) == "https://github.com/kagenti/kagenti-operator"

    def test_github_plain(self):
        url = "https://github.com/kagenti/kagenti-operator"
        assert _extract_repo_url(url) == "https://github.com/kagenti/kagenti-operator"

    def test_github_with_path(self):
        url = "https://github.com/kagenti/kagenti/tree/main/charts"
        assert _extract_repo_url(url) == "https://github.com/kagenti/kagenti"

    def test_gitlab_mr(self):
        url = "https://gitlab.example.com/org/repo/-/merge_requests/42"
        assert _extract_repo_url(url) == "https://gitlab.example.com/org/repo"

    def test_non_repo_url(self):
        assert _extract_repo_url("https://docs.example.com/page") is None


class TestCleanUrl:
    def test_trailing_punctuation(self):
        assert _clean_url("https://github.com/org/repo.") == "https://github.com/org/repo"

    def test_brackets(self):
        assert _clean_url("[https://github.com/org/repo]") == "https://github.com/org/repo"

    def test_parens(self):
        assert _clean_url("(https://github.com/org/repo)") == "https://github.com/org/repo"


class TestExtractPrRefs:
    def test_pr_url_match(self):
        text = "See https://github.com/org/repo/pull/42 for details"
        refs = _extract_pr_refs(text, "https://github.com/org/repo")
        assert refs == ["#42"]

    def test_hash_ref(self):
        text = "Implementation in PR #262, PR #317"
        refs = _extract_pr_refs(text, "https://github.com/org/repo")
        assert refs == ["#262", "#317"]

    def test_no_refs(self):
        text = "No PR references here"
        refs = _extract_pr_refs(text, "https://github.com/org/repo")
        assert refs == []


class TestDeriveSuggestedScope:
    def test_typical_paths(self):
        paths = [
            "pkg/controller/mlflow_reconciler.go",
            "pkg/controller/types.go",
            "pkg/mutator/webhook.go",
        ]
        result = _derive_suggested_scope(paths)
        assert "pkg/controller/" in result
        assert "pkg/mutator/" in result

    def test_empty(self):
        assert _derive_suggested_scope([]) is None

    def test_none(self):
        assert _derive_suggested_scope(None) is None

    def test_root_files(self):
        result = _derive_suggested_scope(["Makefile"])
        assert result == ["Makefile/"]


class TestExtractSecondaryRepos:
    @pytest.fixture()
    def base_evidence(self):
        return {
            "ticket": "TEST-1",
            "repo_path": "/path/to/primary",
            "requirements": [
                {
                    "id": "REQ-001",
                    "status": "grounded",
                    "recommended_action": None,
                },
                {
                    "id": "REQ-002",
                    "status": "absent",
                    "recommended_action": (
                        "Implementation exists in kagenti/kagenti-operator repo"
                        " (PR #262, PR #317). Add --source-code-repo"
                        " https://github.com/kagenti/kagenti-operator"
                        " for full evidence."
                    ),
                },
                {
                    "id": "REQ-003",
                    "status": "absent",
                    "recommended_action": (
                        "Python SDK may be in"
                        " https://github.com/kagenti/kagenti"
                        " (charts/kagenti-deps/). PR #1170, PR #1379."
                    ),
                },
                {
                    "id": "REQ-004",
                    "status": "partial",
                    "recommended_action": (
                        "Partial implementation, rest in"
                        " https://github.com/kagenti/kagenti-operator"
                        " PR #245."
                    ),
                },
            ],
        }

    def test_extracts_repos_grouped(self, base_evidence):
        repos = extract_secondary_repos(base_evidence)
        assert len(repos) == 2
        operator = next(r for r in repos if "kagenti-operator" in r["url"])
        assert set(operator["requirements"]) == {"REQ-002", "REQ-004"}
        assert operator["priority"] == "secondary"
        assert operator["source"] == "gap_classification"

    def test_pr_refs_collected(self, base_evidence):
        repos = extract_secondary_repos(base_evidence)
        operator = next(r for r in repos if "kagenti-operator" in r["url"])
        assert "#262" in operator["pr_refs"]
        assert "#317" in operator["pr_refs"]
        assert "#245" in operator["pr_refs"]

    def test_sorted_by_requirement_count(self, base_evidence):
        repos = extract_secondary_repos(base_evidence)
        assert "kagenti-operator" in repos[0]["url"]
        assert len(repos[0]["requirements"]) >= len(repos[1]["requirements"])

    def test_excludes_primary_repo(self, base_evidence):
        repos = extract_secondary_repos(
            base_evidence,
            primary_repo_url="https://github.com/kagenti/kagenti-operator",
        )
        assert len(repos) == 1
        assert "kagenti" in repos[0]["url"]
        assert "operator" not in repos[0]["url"]

    def test_max_repos_limit(self, base_evidence):
        repos = extract_secondary_repos(base_evidence, max_repos=1)
        assert len(repos) == 1

    def test_grounded_requirements_ignored(self, base_evidence):
        base_evidence["requirements"] = [
            {
                "id": "REQ-001",
                "status": "grounded",
                "recommended_action": ("Found at https://github.com/org/repo"),
            },
        ]
        repos = extract_secondary_repos(base_evidence)
        assert repos == []

    def test_no_action_text(self, base_evidence):
        base_evidence["requirements"] = [
            {
                "id": "REQ-001",
                "status": "absent",
                "recommended_action": None,
            },
        ]
        repos = extract_secondary_repos(base_evidence)
        assert repos == []

    def test_empty_requirements(self):
        repos = extract_secondary_repos({"requirements": []})
        assert repos == []

    def test_fetch_pr_paths_integration(self, base_evidence):
        mock_result = type(
            "R",
            (),
            {
                "returncode": 0,
                "stdout": "pkg/controller/reconciler.go\npkg/mutator/webhook.go\n",
            },
        )()
        with patch("extract_secondary_repos.subprocess.run", return_value=mock_result):
            repos = extract_secondary_repos(base_evidence, fetch_pr_paths=True)
        operator = next(r for r in repos if "kagenti-operator" in r["url"])
        assert operator["suggested_scope"] is not None
        assert "pkg/controller/" in operator["suggested_scope"]
