"""JQL for finding Jira cards that may already track a disruption pattern.

The Atlassian MCP tool runs the queries; this module only writes them, so every
investigation searches the same way and the queries are testable.

Backend names are collapsed to a family here (openshift-api-http2-service-network-
reused-connections -> openshift-api) because a bug is often filed against a
sibling probe of the same API. Run discovery must not do this: it scores exact
backend names.
"""
import re

CLOUD_ID = "redhat.atlassian.net"
PROJECTS = "project in (TRT, OCPBUGS)"
# No assignee: it carries avatar URLs and pushes a 100-row page past the MCP output limit.
FIELDS = ["summary", "status", "resolution", "labels", "components", "updated"]
# The MCP tool accepts 50-100. Read every page: relevance is not the sort order.
MAX_RESULTS = 100
DEFAULT_RECENT_DAYS = 90

_CONNECTION_SUFFIX = re.compile(r"-(new|reused)-connections$")
# Probe variants of one API: transport, then the path the poller takes.
_PROBE_SUFFIX = re.compile(r"(-http[12])?(-(localhost|internal-lb|service-network|external-lb))?$")

# Preset keywords for mechanisms the parser reports in concurrent_events.
SIGNAL_KEYWORDS = {
    "ovs": ["vswitchd", "OVS stall", "ovs-vswitchd"],
    "cpu": ["ExtremelyHighIndividualControlPlaneCPU", "CPU exhaustion", "high CPU"],
    "etcd": ["etcd leader", "took too long", "slow fdatasync", "etcd pressure"],
}


def backend_family(backend):
    """Collapse a backend name to the API it probes.

    cache-kube-api-http1-localhost-new-connections -> kube-api
    openshift-api-http2-service-network-reused-connections -> openshift-api
    host-to-host-new-connections -> host-to-host
    """
    name = backend.strip()
    if name.startswith("cache-"):
        name = name[len("cache-"):]
    name = _CONNECTION_SUFFIX.sub("", name)
    return _PROBE_SUFFIX.sub("", name, count=1) or name


def _unique(items):
    """Non-empty items in their first-seen order, without repeats."""
    seen = []
    for item in items:
        if item and item not in seen:
            seen.append(item)
    return seen


def _quote(value):
    """A JQL string literal for value, with backslashes and quotes escaped."""
    return '"%s"' % value.replace("\\", "\\\\").replace('"', '\\"')


def _phrase(value):
    """A text term that must match as a phrase, not as any of its words.

    Quotes cannot nest inside a Jira phrase, so they are dropped.
    """
    value = value.replace('"', "")
    return _quote('"%s"' % value) if " " in value else _quote(value)


def _any(field, values, phrase=False):
    """A JQL clause matching any of values in field, as phrases or plain terms."""
    term = _phrase if phrase else _quote
    return "(%s)" % " OR ".join("%s ~ %s" % (field, term(v)) for v in values)


def _components(components):
    """A JQL clause matching any of the given Jira components."""
    return "component in (%s)" % ", ".join(_quote(c) for c in components)


def _query(name, purpose, jql):
    """One named Jira search, in the shape the agent passes to searchJiraIssuesUsingJql."""
    return {
        "name": name,
        "purpose": purpose,
        "tool": "searchJiraIssuesUsingJql",
        "args": {"cloudId": CLOUD_ID, "jql": jql, "maxResults": MAX_RESULTS, "fields": FIELDS},
    }


def build_queries(backends, components=(), keywords=(), signals=(), recent_days=DEFAULT_RECENT_DAYS):
    """Return the queries to run, most specific first.

    backends: exact backend names from the analysis.
    components: OCPBUGS components the evidence points at (for example the
        apiserver whose audit log shows the stall). Never guessed from a name.
    keywords: root-cause terms (resource names, error strings, mechanisms).
    signals: preset keys from SIGNAL_KEYWORDS.

    Open cards and cards that reached Done within recent_days are searched
    together, so a bug that was just fixed is not missed. Older closed cards get
    their own query so they are classified by their evidence, apart from recent cards.
    """
    unknown = [s for s in signals if s not in SIGNAL_KEYWORDS]
    if unknown:
        raise ValueError("unknown signal %s (choose from %s)"
                         % (", ".join(unknown), ", ".join(sorted(SIGNAL_KEYWORDS))))
    families = _unique(backend_family(b) for b in backends)
    all_components = _unique(c.strip() for c in components)
    keywords = _unique(k.strip() for k in keywords)
    current = "(statusCategory != Done OR updated >= -%dd)" % recent_days
    labelled = 'labels = "disruption"'

    queries = []
    if keywords:
        scope = "(%s OR %s)" % (_components(all_components), labelled) if all_components else None
        clauses = [PROJECTS, _any("text", keywords, phrase=True)] + ([scope] if scope else []) + [current]
        queries.append(_query(
            "root-cause",
            "Cards about the mechanism, whatever backend they were filed against",
            " AND ".join(clauses) + " ORDER BY updated DESC"))
    if all_components:
        queries.append(_query(
            "component",
            "Disruption cards on the components the evidence points at",
            "%s AND %s AND (%s OR summary ~ \"disruption\") AND %s ORDER BY updated DESC"
            % (PROJECTS, _components(all_components), labelled, current)))
    if families:
        family_text = _any("text", families)
        queries.append(_query(
            "backend-family",
            "Disruption cards naming any probe of these APIs (%s)" % ", ".join(families),
            "%s AND %s AND %s AND %s ORDER BY updated DESC" % (PROJECTS, labelled, family_text, current)))
        queries.append(_query(
            "backend-family-history",
            "Older closed investigations, to classify by their evidence",
            "%s AND %s AND %s AND statusCategory = Done AND updated < -%dd ORDER BY updated DESC"
            % (PROJECTS, labelled, family_text, recent_days)))
    for signal in _unique(signals):
        queries.append(_query(
            "signal-" + signal,
            "Cards about %s, filed without a disruption label" % signal,
            "%s AND %s AND %s ORDER BY updated DESC"
            % (PROJECTS, _any("text", SIGNAL_KEYWORDS[signal], phrase=True), current)))
    return {"families": families, "components": all_components, "keywords": keywords,
            "queries": queries}
