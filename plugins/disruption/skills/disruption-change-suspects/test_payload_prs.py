"""Tests for payload_prs.py — PRs between two payloads from the release controller changelog."""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import payload_prs as pp  # noqa: E402

FROM = "5.0.0-0.nightly-2026-11-07-182718"
TO = "5.0.0-0.nightly-2026-11-09-184859"
RESPONSE = {"changeLogJson": {"updatedImages": [
    {"name": "ironic-agent", "path": "https://github.com/openshift/ironic-agent-image/tree/5c81",
     "fullChangeLog": "https://github.com/openshift/ironic-agent-image/compare/601c...5c81",
     "commits": [{"subject": "Bump urllib3", "pullID": 326,
                  "pullURL": "https://github.com/openshift/ironic-agent-image/pull/326",
                  "issues": {"OCPBUGS-2": "u", "OCPBUGS-1": "u"}}]},
    {"name": "cluster-kube-apiserver-operator", "path": "https://github.com/openshift/cluster-kube-apiserver-operator/tree/ab",
     "fullChangeLog": "https://github.com/openshift/cluster-kube-apiserver-operator/compare/a...b", "commits": []},
]}}


def test_changelog_url_covers_a_range_in_one_stream_and_picks_the_arch():
    url = pp.changelog_url(FROM, TO)
    assert url == ("https://amd64.ocp.releases.ci.openshift.org/api/v1/releasestream/5.0.0-0.nightly/release/"
                   "%s?from=%s" % (TO, FROM))
    arm = pp.changelog_url("5.0.0-0.nightly-arm64-2026-11-07-182718", "5.0.0-0.nightly-arm64-2026-11-09-184859")
    assert arm.startswith("https://arm64.ocp.releases.ci.openshift.org/")


def test_changelog_url_rejects_mixed_streams_order_and_bad_tags():
    with pytest.raises(pp.ChangelogError, match="different streams"):
        pp.changelog_url(FROM, "5.0.0-0.ci-2026-11-09-184859")
    with pytest.raises(pp.ChangelogError, match="older payload first"):
        pp.changelog_url(TO, FROM)
    with pytest.raises(pp.ChangelogError, match="not a payload tag"):
        pp.changelog_url("4.20.3", TO)
    with pytest.raises(pp.ChangelogError, match="unknown architecture"):
        pp.changelog_url(FROM, TO, arch="sparc")


def test_components_lists_prs_and_filters_by_image_or_repo():
    comps = pp.components(RESPONSE)
    assert [c["component"] for c in comps] == ["cluster-kube-apiserver-operator", "ironic-agent"]
    ironic = comps[1]
    assert ironic["repo"] == "openshift/ironic-agent-image"
    assert ironic["prs"] == [{"title": "Bump urllib3", "url": "https://github.com/openshift/ironic-agent-image/pull/326",
                              "number": 326, "issues": ["OCPBUGS-1", "OCPBUGS-2"]}]
    assert [c["component"] for c in pp.components(RESPONSE, ["ironic-agent-image"])] == ["ironic-agent"]
    assert pp.components({}) == []


def test_load_changelog_caches_the_response(tmp_path):
    calls = []

    def fetch(url):
        calls.append(url)
        return RESPONSE

    first, _ = pp.load_changelog(FROM, TO, cache_dir=str(tmp_path), fetch=fetch)
    second, _ = pp.load_changelog(FROM, TO, cache_dir=str(tmp_path), fetch=fetch)
    assert first == second == RESPONSE
    assert len(calls) == 1


def test_main_prints_prs_and_reports_errors(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(pp, "fetch_json", lambda url, timeout=pp.FETCH_TIMEOUT: RESPONSE)
    assert pp.main([FROM, TO, "--cache-dir", ""]) == 0
    out = capsys.readouterr().out
    assert "PRs from %s to %s: 1 in 2 component(s)" % (FROM, TO) in out
    assert "(image changed, no PRs listed)" in out
    assert "[OCPBUGS-1, OCPBUGS-2]" in out
    assert pp.main([FROM, TO, "--cache-dir", "", "--format", "json", "--component", "ironic-agent"]) == 0
    assert [c["component"] for c in json.loads(capsys.readouterr().out)["components"]] == ["ironic-agent"]

    def boom(url, timeout=None):
        raise pp.ChangelogError("HTTP 404 from the release controller for %s" % url)

    monkeypatch.setattr(pp, "fetch_json", boom)
    assert pp.main([FROM, TO, "--cache-dir", ""]) == 1
    assert "HTTP 404" in capsys.readouterr().err


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
