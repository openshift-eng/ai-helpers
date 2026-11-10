"""Tests for disruption_common.known_issues — Jira query construction."""
import os
import sys

import pytest

# Run as a script (make test), the package parent is not on sys.path yet.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from disruption_common.known_issues import MAX_RESULTS, backend_family, build_queries  # noqa: E402


@pytest.mark.parametrize("backend, family", [
    ("openshift-api-http2-service-network-reused-connections", "openshift-api"),
    ("openshift-api-http2-internal-lb-new-connections", "openshift-api"),
    ("cache-kube-api-http1-localhost-new-connections", "kube-api"),
    ("kube-api-localhost-new-connections", "kube-api"),
    ("oauth-api-reused-connections", "oauth-api"),
    ("host-to-host-new-connections", "host-to-host"),
    ("ingress-to-oauth-server-new-connections", "ingress-to-oauth-server"),
    ("image-registry", "image-registry"),
])
def test_backend_family_strips_probe_variants(backend, family):
    assert backend_family(backend) == family


def _by_name(result):
    return {query["name"]: query["args"]["jql"] for query in result["queries"]}


def test_sibling_backends_share_one_family_query():
    result = build_queries(["openshift-api-http2-service-network-reused-connections",
                            "openshift-api-http2-internal-lb-new-connections"])

    assert result["families"] == ["openshift-api"]
    jql = _by_name(result)
    assert jql["backend-family"] == (
        'project in (TRT, OCPBUGS) AND labels = "disruption" AND (text ~ "openshift-api") '
        "AND (statusCategory != Done OR updated >= -90d) ORDER BY updated DESC")
    assert "statusCategory = Done AND updated < -90d" in jql["backend-family-history"]


def test_without_root_cause_inputs_only_family_queries_run():
    result = build_queries(["kube-api-new-connections"])

    assert [q["name"] for q in result["queries"]] == ["backend-family", "backend-family-history"]
    assert result["components"] == []


def test_root_cause_query_quotes_phrases_and_scopes_to_component_or_label():
    result = build_queries(["openshift-api-http2-service-network-reused-connections"],
                           components=["openshift-apiserver"], keywords=["watch cache", "imagestream"])

    names = [q["name"] for q in result["queries"]]
    assert names[:2] == ["root-cause", "component"]
    jql = _by_name(result)
    assert jql["root-cause"] == (
        'project in (TRT, OCPBUGS) AND (text ~ "\\"watch cache\\"" OR text ~ "imagestream") '
        'AND (component in ("openshift-apiserver") OR labels = "disruption") '
        "AND (statusCategory != Done OR updated >= -90d) ORDER BY updated DESC")
    assert jql["component"] == (
        'project in (TRT, OCPBUGS) AND component in ("openshift-apiserver") '
        'AND (labels = "disruption" OR summary ~ "disruption") '
        "AND (statusCategory != Done OR updated >= -90d) ORDER BY updated DESC")


def test_root_cause_query_without_component_is_not_restricted():
    jql = _by_name(build_queries(["kube-api-new-connections"], keywords=["conntrack"]))["root-cause"]

    assert jql == ('project in (TRT, OCPBUGS) AND (text ~ "conntrack") '
                   "AND (statusCategory != Done OR updated >= -90d) ORDER BY updated DESC")


def test_signal_presets_add_one_query_each():
    jql = _by_name(build_queries(["kube-api-new-connections"], signals=["etcd", "ovs"]))

    assert 'text ~ "\\"slow fdatasync\\""' in jql["signal-etcd"]
    assert 'text ~ "vswitchd"' in jql["signal-ovs"]


def test_unknown_signal_is_rejected():
    with pytest.raises(ValueError, match="unknown signal disk"):
        build_queries(["kube-api-new-connections"], signals=["disk"])


def test_quotes_inside_keywords_are_dropped():
    jql = _by_name(build_queries(["kube-api-new-connections"], keywords=['say "hi"']))["root-cause"]

    assert '(text ~ "\\"say hi\\"")' in jql


def test_recent_days_and_tool_args():
    query = build_queries(["kube-api-new-connections"], recent_days=30)["queries"][0]

    assert "updated >= -30d" in query["args"]["jql"]
    assert query["tool"] == "searchJiraIssuesUsingJql"
    assert query["args"]["cloudId"] == "redhat.atlassian.net"
    assert query["args"]["maxResults"] == MAX_RESULTS == 100
    assert "status" in query["args"]["fields"]
    assert "assignee" not in query["args"]["fields"]


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
