"""Tests for extract_discovered_repos.py — sort ranking, discovery merge."""

import json

import pytest
from extract_discovered_repos import (
    _extract_prs_from_discovery,
    _rebuild_repo_groups,
    _serialize_repo_groups,
    extract_repos_from_graph,
    merge_discovery_prs,
)


def _minimal_graph(git_links=None, auto_prs=None, ticket="TEST-1"):
    """Build a minimal JIRA graph structure."""
    return {
        "ticket": ticket,
        "git_links": git_links or [],
        "auto_discovered_urls": {"pull_requests": auto_prs or []},
        "children": {"issues": []},
        "issue_links": {"links": []},
    }


class TestSortRanking:
    def test_prefers_repos_with_prs(self):
        """Repo with fewer refs but more PRs should rank first."""
        graph = _minimal_graph()
        config_issue = {
            "git_links": ["https://github.com/org/config-repo"],
            "auto_discovered_urls": {},
        }
        graph["children"]["issues"] = [
            {"key": "T-2", **config_issue},
            {"key": "T-3", **config_issue},
            {"key": "T-4", **config_issue},
            {"key": "T-5", **config_issue},
            {"key": "T-6", **config_issue},
            {
                "key": "T-7",
                "git_links": [
                    "https://github.com/org/impl-repo/pull/10",
                    "https://github.com/org/impl-repo/pull/20",
                    "https://github.com/org/impl-repo/pull/30",
                ],
                "auto_discovered_urls": {},
            },
            {
                "key": "T-8",
                "git_links": ["https://github.com/org/impl-repo"],
                "auto_discovered_urls": {},
            },
        ]

        result = extract_repos_from_graph(graph)
        assert result["repos"][0]["repo_url"] == "https://github.com/org/impl-repo"
        assert result["repos"][0]["reference_count"] == 2
        assert len(result["repos"][0]["pr_urls"]) == 3
        assert result["repos"][1]["repo_url"] == "https://github.com/org/config-repo"
        assert result["repos"][1]["reference_count"] == 5

    def test_tiebreaker_by_reference_count(self):
        """Equal PR count: higher reference count wins."""
        graph = _minimal_graph()
        graph["children"]["issues"] = [
            {
                "key": "T-2",
                "git_links": ["https://github.com/org/repo-a/pull/1"],
                "auto_discovered_urls": {},
            },
            {
                "key": "T-3",
                "git_links": [
                    "https://github.com/org/repo-b/pull/2",
                    "https://github.com/org/repo-b",
                ],
                "auto_discovered_urls": {},
            },
            {
                "key": "T-4",
                "git_links": ["https://github.com/org/repo-b"],
                "auto_discovered_urls": {},
            },
        ]

        result = extract_repos_from_graph(graph)
        assert result["repos"][0]["repo_url"] == "https://github.com/org/repo-b"


class TestDiscoveryMerge:
    @pytest.fixture()
    def discovery_file(self, tmp_path):
        """Write a discovery.json and return the path."""

        def _write(data):
            path = tmp_path / "discovery.json"
            path.write_text(json.dumps(data))
            return str(path)

        return _write

    def test_adds_new_repos(self, discovery_file):
        """PRs in discovery.json for repos not in graph should appear."""
        graph = _minimal_graph()
        result = extract_repos_from_graph(graph)
        assert result["total_repos"] == 0

        discovery_path = discovery_file(
            {
                "sources_consulted": {
                    "pull_requests": [
                        {"url": "https://github.com/org/new-repo/pull/42"},
                    ],
                },
                "requirements": [],
            }
        )

        repo_groups = _rebuild_repo_groups(result)
        merge_discovery_prs(repo_groups, discovery_path)
        merged = _serialize_repo_groups(repo_groups)

        assert merged["total_repos"] == 1
        assert merged["repos"][0]["repo_url"] == "https://github.com/org/new-repo"
        assert "https://github.com/org/new-repo/pull/42" in merged["repos"][0]["pr_urls"]

    def test_augments_existing_repos(self, discovery_file):
        """Same repo in graph and discovery: PR lists merge, deduped."""
        graph = _minimal_graph(
            auto_prs=["https://github.com/org/repo/pull/1"],
        )
        result = extract_repos_from_graph(graph)
        assert len(result["repos"][0]["pr_urls"]) == 1

        discovery_path = discovery_file(
            {
                "sources_consulted": {
                    "pull_requests": [
                        {"url": "https://github.com/org/repo/pull/1"},
                        {"url": "https://github.com/org/repo/pull/2"},
                    ],
                },
                "requirements": [],
            }
        )

        repo_groups = _rebuild_repo_groups(result)
        merge_discovery_prs(repo_groups, discovery_path)
        merged = _serialize_repo_groups(repo_groups)

        assert merged["total_repos"] == 1
        assert len(merged["repos"][0]["pr_urls"]) == 2

    def test_missing_file_is_noop(self):
        """Nonexistent discovery file should not raise or change groups."""
        repo_groups = {}
        merge_discovery_prs(repo_groups, "/nonexistent/discovery.json")
        assert repo_groups == {}

    def test_deduplicates(self, discovery_file):
        """Same PR in graph and discovery appears once."""
        pr_url = "https://github.com/org/repo/pull/42"
        graph = _minimal_graph(auto_prs=[pr_url])
        result = extract_repos_from_graph(graph)

        discovery_path = discovery_file(
            {
                "sources_consulted": {
                    "pull_requests": [{"url": pr_url}],
                },
                "requirements": [],
            }
        )

        repo_groups = _rebuild_repo_groups(result)
        merge_discovery_prs(repo_groups, discovery_path)
        merged = _serialize_repo_groups(repo_groups)

        assert len(merged["repos"][0]["pr_urls"]) == 1

    def test_reads_per_requirement_sources(self, discovery_file):
        """PRs in per-requirement sources (type=pr) are extracted."""
        discovery_path = discovery_file(
            {
                "sources_consulted": {"pull_requests": []},
                "requirements": [
                    {
                        "id": "REQ-001",
                        "sources": [
                            {"type": "pr", "url": "https://github.com/org/repo/pull/99"},
                            {"type": "jira", "url": "https://jira.example.com/PROJ-1"},
                        ],
                    },
                ],
            }
        )

        urls = _extract_prs_from_discovery(discovery_path)
        assert "https://github.com/org/repo/pull/99" in urls
        assert len(urls) == 1


class TestEndToEnd:
    def test_implementation_repo_wins_after_merge(self, tmp_path):
        """Motivating scenario: graph empty, discovery has PRs for two repos.

        impl-repo has 2 PRs (implementation), config-repo has 5 references
        but only 1 PR. After merge+sort, impl-repo should be repos[0].
        """
        graph = _minimal_graph()
        result = extract_repos_from_graph(graph)
        assert result["total_repos"] == 0

        discovery_path = tmp_path / "discovery.json"
        discovery_path.write_text(
            json.dumps(
                {
                    "sources_consulted": {
                        "pull_requests": [
                            {"url": "https://github.com/org/impl-repo/pull/10"},
                            {"url": "https://github.com/org/impl-repo/pull/20"},
                            {"url": "https://github.com/org/config-repo/pull/1"},
                        ],
                    },
                    "requirements": [],
                }
            )
        )

        repo_groups = _rebuild_repo_groups(result)
        merge_discovery_prs(repo_groups, str(discovery_path))
        merged = _serialize_repo_groups(repo_groups)

        assert merged["total_repos"] == 2
        assert merged["repos"][0]["repo_url"] == "https://github.com/org/impl-repo"
        assert len(merged["repos"][0]["pr_urls"]) == 2
        assert merged["repos"][1]["repo_url"] == "https://github.com/org/config-repo"
        assert len(merged["repos"][1]["pr_urls"]) == 1
