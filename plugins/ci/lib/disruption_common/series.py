"""Resolve a disruption series from a Grafana URL, alert text, or explicit fields.

A series is one release, a set of exact backend names, Sippy job-variant
filters, and an optional run-level master_nodes_updated filter. Every
disruption skill that queries Sippy resolves its input through this module so
the dashboard and alert label mapping lives in one place.
"""
import re
import sys
import urllib.parse
from datetime import datetime, timedelta, timezone

DEFAULT_SINCE_HOURS = 720
# DisruptionRegression* compares the last 3 days to the previous GA.
ALERT_LOOKBACK_DAYS = "3"
_CONNECTION_SUFFIXES = ("-new-connections", "-reused-connections")

GRAFANA_TO_VARIANT = {
    "platform": "Platform",
    "architectures": "Architecture",
    "topologies": "Topology",
    "networks": "Network",
    "upgrade_type": "Upgrade",
    "featureset": "FeatureSet",
    "ipmode": "NetworkStack",
    "os": "OS",
}

# Chart thresholds and regression context. Not Sippy job filters.
GRAFANA_DISPLAY_ONLY = {
    "percentile", "lookback", "min_disruption_regression",
    "min_disruption_job_list", "min_relevance", "orgId",
    "compare_release", "releaseStatus", "release_status",
}

# Run-level series labels. Same job can be Y on one run and N on the next.
RUN_LEVEL_FILTERS = {"master_nodes_updated"}

# Alert label -> grafana param. The annotation link omits feature_set and os.
ALERT_LABEL_TO_GRAFANA = {
    "platform": "platform",
    "backend": "backend",
    "upgrade_type": "upgrade_type",
    "master_nodes_updated": "master_nodes_updated",
    "architecture": "architectures",
    "topology": "topologies",
    "network": "networks",
    "release": "releases",
    "delta": "percentile",
    "feature_set": "featureset",
    "os": "os",
    "compare_release": "compare_release",
}

# CLI override name -> grafana param.
OVERRIDE_TO_GRAFANA = {
    "platform": "platform",
    "upgrade_type": "upgrade_type",
    "architecture": "architectures",
    "topology": "topologies",
    "network": "networks",
}

_LABEL_LINE = re.compile(
    r"^(?:[\s\-*•·]+)?([A-Za-z][A-Za-z0-9_]*)\s*:\s*(.+?)\s*$"
)


class SeriesError(ValueError):
    """The input does not name a usable series (missing release or backend)."""


def parse_grafana_url(url):
    """Extract var-* parameters from a Grafana dashboard URL.

    Multi-value params (e.g. var-platform=azure&var-platform=gcp) are stored
    as comma-joined strings so downstream code stays simple.
    """
    parsed = urllib.parse.urlparse(url)
    params = urllib.parse.parse_qs(parsed.query)
    result = {}
    for key, values in params.items():
        if key.startswith("var-"):
            name = key[4:]
            result[name] = ",".join(values) if len(values) > 1 else values[0]

    dashboard_name = ""
    path_parts = parsed.path.rstrip("/").split("/")
    if len(path_parts) >= 2:
        dashboard_name = path_parts[-1]

    result["_dashboard_name"] = dashboard_name
    return _normalize_grafana_keys(result)


def _normalize_grafana_keys(result):
    """Collapse alert-style names onto the dashboard var names."""
    alias = result.pop("feature_set", None)
    if alias and not result.get("featureset"):
        result["featureset"] = alias
    return result


def parse_alert_labels(text):
    """Pull `key: value` labels and an optional `link:` annotation out of alert text."""
    labels = {}
    link = None
    for line in (text or "").splitlines():
        match = _LABEL_LINE.match(line)
        if not match:
            continue
        key, value = match.group(1), match.group(2).strip()
        if not value:
            continue
        if key.lower() == "link" and value.startswith("http"):
            link = value
            continue
        labels[key] = value
    return labels, link


def _overlay_alert_labels(params, labels):
    """Fill grafana params the link left empty. A value already on the link wins."""
    for alert_key, gkey in ALERT_LABEL_TO_GRAFANA.items():
        value = (labels.get(alert_key) or "").strip()
        if not value:
            continue
        existing = params.get(gkey)
        if existing is None or str(existing).strip() == "":
            params[gkey] = value
    return params


def grafana_params_from_inputs(grafana_url=None, alert_text=None):
    """Build the shared filter set from a dashboard URL, alert text, or both.

    An explicit URL is the base. Otherwise a `link:` annotation in the alert is
    the base. Alert labels fill keys that base omitted (`feature_set`, `os`,
    and any other series label the link does not set). With neither URL nor
    link, the window is the 3-day regression lookback.
    """
    labels, link = parse_alert_labels(alert_text) if alert_text else ({}, None)
    if grafana_url:
        params = parse_grafana_url(grafana_url)
    elif link:
        params = parse_grafana_url(link)
    elif alert_text:
        params = {"_dashboard_name": "(alert)", "lookback": ALERT_LOOKBACK_DAYS}
    else:
        return {}
    if labels:
        _overlay_alert_labels(params, labels)
    return params


def parse_backend(backend_value):
    """Parse backend name into base name and connection type.

    Examples:
        host-to-host-new-connections -> (host-to-host, new)
        cache-kube-api-reused-connections -> (cache-kube-api, reused)
        oauth-api -> (oauth-api, None)
    """
    for suffix, conn in (("-new-connections", "new"), ("-reused-connections", "reused")):
        if backend_value.endswith(suffix):
            return backend_value[: -len(suffix)], conn
    return backend_value, None


def split_backends(value):
    """Split a comma-joined backend list into exact selector strings."""
    if not value:
        return []
    return [part.strip() for part in str(value).split(",") if part.strip()]


def expand_backend_selectors(selectors):
    """Return the exact backend names a selector or list of selectors scores.

    A name that already ends in -new-connections or -reused-connections matches
    only itself. A bare base name matches only those two connection variants.
    Derived probes (localhost, http1/http2, service-network, internal-lb) and
    cache-* backends match only when their exact name was requested.
    """
    if isinstance(selectors, str):
        selectors = [selectors]
    names = set()
    for selector in selectors or []:
        if not selector:
            continue
        if selector.endswith(_CONNECTION_SUFFIXES):
            names.add(selector)
        else:
            for suffix in _CONNECTION_SUFFIXES:
                names.add(selector + suffix)
    return names


def selector_bases(selectors):
    """Base names implied by selectors, for disruption test-failure names.

    Failed tests record `disruption/kube-api`, not the full connection backend.
    """
    if isinstance(selectors, str):
        selectors = [selectors]
    bases = set()
    for selector in selectors or []:
        if not selector:
            continue
        base, _conn = parse_backend(selector)
        bases.add(base)
    return bases


def is_all_sentinel(value):
    """True when a Grafana value means 'all', not a Sippy variant.

    `All` and `$__all` match zero Sippy rows (there is no FeatureSet:All).
    A list that includes either sentinel is also unfiltered.
    """
    parts = [part.strip() for part in str(value).split(",") if part.strip()]
    if not parts:
        return False
    return any(part == "$__all" or part.lower() == "all" for part in parts)


def concrete_variant_values(raw):
    """Return concrete variant values, or None when the field should not be filtered."""
    if raw is None or str(raw).strip() == "":
        return None
    if is_all_sentinel(raw):
        return None
    parts = [part.strip() for part in str(raw).split(",") if part.strip()]
    return parts or None


def resolve_window_start(since_hours, lookback_days, now=None):
    """Choose the start of the Sippy `timestamp >` window.

    An explicit since_hours is a rolling hour count and wins over the
    dashboard. Otherwise lookback_days=N is N calendar days: UTC midnight of
    `now` minus N days, so lookback 7 on 2026-10-05 includes 2026-09-28.
    With neither, the window is the last DEFAULT_SINCE_HOURS hours.
    """
    now = now or datetime.now(timezone.utc)
    if since_hours is not None:
        return now - timedelta(hours=float(since_hours))
    if lookback_days is not None and str(lookback_days).strip() != "":
        try:
            days = int(float(lookback_days))
        except (TypeError, ValueError):
            days = None
        if days is not None and days >= 0:
            midnight = now.astimezone(timezone.utc).replace(
                hour=0, minute=0, second=0, microsecond=0)
            return midnight - timedelta(days=days)
    return now - timedelta(hours=DEFAULT_SINCE_HOURS)


def master_nodes_filter_value(raw):
    """Return Y or N when runs should be filtered, else None.

    All / $__all / empty means the series is not limited to one value.
    """
    if raw is None or str(raw).strip() == "":
        return None
    if is_all_sentinel(raw):
        print("Warning: master_nodes_updated=%s is an All sentinel, not applied as a run filter" % (
            raw), file=sys.stderr)
        return None
    value = str(raw).strip().upper()
    if value in ("Y", "N"):
        return value
    print("Warning: master_nodes_updated '%s' is not Y or N; not applied as a run filter" % (
        raw), file=sys.stderr)
    return None


def dashboard_lookback_days(grafana_params):
    """The dashboard or alert lookback in whole days, or None when absent or not a number."""
    lookback = grafana_params.get("lookback")
    if lookback is None or str(lookback).strip() == "":
        return None
    try:
        return int(float(lookback))
    except (TypeError, ValueError):
        print("Warning: var-lookback '%s' is not a number of days; ignoring it" % lookback,
              file=sys.stderr)
        return None


def resolve_series(grafana_url=None, alert_text=None, release=None, backend=None, **overrides):
    """Resolve the inputs into a series description.

    `overrides` takes platform, upgrade_type, architecture, topology, and
    network; a set value wins over the URL or alert. Returns a dict with
    release, selectors (exact backend names), variants (Sippy filters),
    master_nodes_updated (Y, N, or None), lookback_days, percentile,
    compare_release, dashboard, and grafana_params. Raises SeriesError when
    release or backend is missing, or when more than one release is named.
    """
    grafana_params = grafana_params_from_inputs(grafana_url, alert_text)

    release = release or grafana_params.get("releases")
    backend = backend or grafana_params.get("backend")
    if not release:
        raise SeriesError("a release is required (--release, a Grafana URL with var-releases, "
                          "or alert text with a release label)")
    if "," in release:
        raise SeriesError("multiple releases not supported (got '%s'). Use a single release." % release)
    selectors = split_backends(backend)
    if not selectors:
        raise SeriesError("a backend is required (--backend, a Grafana URL with var-backend, "
                          "or alert text with a backend label)")

    cli_values = {OVERRIDE_TO_GRAFANA[key]: value
                  for key, value in overrides.items() if key in OVERRIDE_TO_GRAFANA and value}
    unknown = set(overrides) - set(OVERRIDE_TO_GRAFANA)
    if unknown:
        raise TypeError("unknown series override(s): %s" % ", ".join(sorted(unknown)))

    variants = {}
    for gkey, variant_key in GRAFANA_TO_VARIANT.items():
        raw = cli_values.get(gkey) or grafana_params.get(gkey)
        if raw and is_all_sentinel(raw):
            print("Warning: Grafana parameter '%s=%s' is an All sentinel, not applied as a Sippy filter" % (
                gkey, raw), file=sys.stderr)
            continue
        values = concrete_variant_values(raw)
        if values:
            variants[variant_key] = ",".join(values)

    known_keys = (
        set(GRAFANA_TO_VARIANT) | GRAFANA_DISPLAY_ONLY | RUN_LEVEL_FILTERS
        | {"releases", "backend", "_dashboard_name"}
    )
    for gkey in grafana_params:
        if gkey not in known_keys:
            print("Warning: Grafana parameter '%s' not mapped to a Sippy filter, ignoring" % gkey,
                  file=sys.stderr)

    return {
        "release": release,
        "selectors": selectors,
        "variants": variants,
        "master_nodes_updated": master_nodes_filter_value(grafana_params.get("master_nodes_updated")),
        "lookback_days": dashboard_lookback_days(grafana_params),
        "percentile": grafana_params.get("percentile"),
        "compare_release": grafana_params.get("compare_release"),
        "dashboard": grafana_params.get("_dashboard_name") or "(manual query)",
        "grafana_params": grafana_params,
    }


def filter_disruption_data(disruption_data, selectors):
    """Keep only entries whose backend_name is an exact selected name."""
    allowed = expand_backend_selectors(selectors)
    filtered = {}
    for pid, entries in (disruption_data or {}).items():
        kept = [entry for entry in entries if entry.get("backend_name") in allowed]
        if kept:
            filtered[pid] = kept
    return filtered


def disruption_peak(disruption_entries, selectors):
    """Return (seconds, backend_name) for the highest exact selected match.

    seconds is None when there is no disruption data for the run. It is 0,
    with backend_name None, when data exists but no selected backend matches.
    """
    allowed = expand_backend_selectors(selectors)
    if not disruption_entries:
        return None, None
    best_secs = None
    best_name = None
    for entry in disruption_entries:
        if entry.get("backend_name") not in allowed:
            continue
        secs = entry.get("disruption_seconds", 0)
        if best_secs is None or secs > best_secs:
            best_secs = secs
            best_name = entry.get("backend_name")
    if best_secs is None:
        return 0, None
    return best_secs, best_name


def disruption_api_has_master_field(disruption_data):
    """True when any returned row included master_nodes_updated."""
    for entries in (disruption_data or {}).values():
        for entry in entries or []:
            if "master_nodes_updated" in entry:
                return True
    return False


def apply_master_nodes_filter(rows, disruption_data, wanted, field_present):
    """Keep runs whose selected-backend rows match wanted (Y or N).

    wanted is None when no filter applies. When a filter is set and the API
    response did not include the field, return no rows rather than the
    unfiltered set. A run with no selected-backend row cannot be classified
    and is dropped.
    """
    if wanted is None:
        return rows
    if not field_present:
        print(
            "Warning: master_nodes_updated=%s was requested, but the disruption API "
            "response did not include that field. Those runs were not kept." % wanted,
            file=sys.stderr,
        )
        return []
    kept = []
    for row in rows:
        pid = str(row.get("prow_id", ""))
        matched = False
        for entry in disruption_data.get(pid) or []:
            value = entry.get("master_nodes_updated")
            if value is None:
                continue
            if str(value).strip().upper() == wanted:
                matched = True
                break
        if matched:
            kept.append(row)
    print("Kept %d of %d runs with master_nodes_updated=%s." % (
        len(kept), len(rows), wanted), file=sys.stderr)
    return kept
