"""Tests for disruption_common.series — dashboard/alert parsing and series resolution."""
import datetime

import pytest

from disruption_common.series import (
    SeriesError,
    apply_master_nodes_filter,
    disruption_peak,
    expand_backend_selectors,
    filter_disruption_data,
    grafana_params_from_inputs,
    parse_backend,
    parse_grafana_url,
    resolve_series,
    resolve_window_start,
)

SAMPLE_ALERT = """\
Alert:  - warning
Details:
   • alertname: DisruptionRegressionP95
   • architecture: amd64
   • backend: openshift-api-http2-service-network-reused-connections
   • compare_release: 4.22
   • delta: P95
   • feature_set: default
   • master_nodes_updated: Y
   • network: ovn
   • platform: azure
   • release: 5.0
   • topology: ha
   • upgrade_type: micro
"""

ALERT_LINK = (
    "https://grafana-loki.ci.openshift.org/d/gEdw_aLvk/disruption-for-5-0-os-agnostic"
    "?orgId=1&var-percentile=P95&var-platform=azure"
    "&var-backend=openshift-api-http2-service-network-reused-connections"
    "&var-upgrade_type=micro&var-master_nodes_updated=Y"
    "&var-architectures=amd64&var-topologies=ha&var-networks=ovn"
    "&var-releases=5.0&var-lookback=7"
)


def test_parse_grafana_url_multi_value_and_alias():
    url = (
        "https://grafana-loki.ci.openshift.org/d/abc/dash"
        "?var-platform=azure&var-platform=gcp&var-feature_set=default"
        "&var-backend=kube-api-new-connections&var-releases=5.0"
    )
    result = parse_grafana_url(url)
    assert result["platform"] == "azure,gcp"
    assert result["featureset"] == "default"
    assert "feature_set" not in result
    assert result["_dashboard_name"] == "dash"


def test_alert_without_link_uses_three_day_lookback():
    params = grafana_params_from_inputs(alert_text=SAMPLE_ALERT)
    assert params["lookback"] == "3"
    assert params["platform"] == "azure"
    assert params["featureset"] == "default"


def test_alert_link_wins_and_omitted_labels_are_overlaid():
    params = grafana_params_from_inputs(alert_text=SAMPLE_ALERT + "   • os: rhcos10\nlink: " + ALERT_LINK)
    assert params["lookback"] == "7"
    assert params["os"] == "rhcos10"
    assert params["featureset"] == "default"


def test_parse_backend_and_expand_selectors():
    assert parse_backend("cache-kube-api-reused-connections") == ("cache-kube-api", "reused")
    assert parse_backend("oauth-api") == ("oauth-api", None)
    assert expand_backend_selectors("kube-api") == {
        "kube-api-new-connections", "kube-api-reused-connections"}
    assert expand_backend_selectors(["kube-api-new-connections"]) == {"kube-api-new-connections"}


def test_resolve_window_start_lookback_is_calendar_days():
    now = datetime.datetime(2026, 10, 5, 15, 30, tzinfo=datetime.timezone.utc)
    start = resolve_window_start(None, "7", now=now)
    assert start == datetime.datetime(2026, 9, 28, tzinfo=datetime.timezone.utc)
    assert resolve_window_start(24, "7", now=now) == now - datetime.timedelta(hours=24)


def test_resolve_series_from_alert():
    series = resolve_series(alert_text=SAMPLE_ALERT)
    assert series["release"] == "5.0"
    assert series["selectors"] == ["openshift-api-http2-service-network-reused-connections"]
    assert series["variants"] == {
        "Platform": "azure", "Architecture": "amd64", "Topology": "ha",
        "Network": "ovn", "Upgrade": "micro", "FeatureSet": "default",
    }
    assert series["master_nodes_updated"] == "Y"
    assert series["lookback_days"] == 3
    assert series["percentile"] == "P95"
    assert series["compare_release"] == "4.22"


def test_resolve_series_overrides_win_and_all_is_not_a_filter():
    url = (
        "https://grafana-loki.ci.openshift.org/d/abc/dash"
        "?var-platform=gcp&var-featureset=All&var-backend=kube-api-new-connections"
        "&var-backend=oauth-api-new-connections&var-releases=5.0"
    )
    series = resolve_series(grafana_url=url, platform="aws")
    assert series["variants"] == {"Platform": "aws"}
    assert series["selectors"] == ["kube-api-new-connections", "oauth-api-new-connections"]
    assert series["lookback_days"] is None


def test_resolve_series_explicit_fields():
    series = resolve_series(release="4.22", backend="kube-api-new-connections",
                            platform="gcp", upgrade_type="minor")
    assert series["variants"] == {"Platform": "gcp", "Upgrade": "minor"}
    assert series["dashboard"] == "(manual query)"


@pytest.mark.parametrize("kwargs, message", [
    ({"backend": "kube-api-new-connections"}, "release is required"),
    ({"release": "5.0"}, "backend is required"),
    ({"release": "5.0,4.22", "backend": "kube-api"}, "multiple releases"),
])
def test_resolve_series_errors(kwargs, message):
    with pytest.raises(SeriesError, match=message):
        resolve_series(**kwargs)


def test_resolve_series_rejects_unknown_override():
    with pytest.raises(TypeError):
        resolve_series(release="5.0", backend="kube-api", region="us-east-1")


def test_disruption_peak_uses_exact_names_only():
    entries = [
        {"backend_name": "kube-api-http2-localhost-new-connections", "disruption_seconds": 90},
        {"backend_name": "cache-kube-api-new-connections", "disruption_seconds": 80},
        {"backend_name": "kube-api-new-connections", "disruption_seconds": 4},
    ]
    assert disruption_peak(entries, ["kube-api-new-connections"]) == (4, "kube-api-new-connections")
    assert disruption_peak(entries, ["oauth-api-new-connections"]) == (0, None)
    assert disruption_peak([], ["kube-api-new-connections"]) == (None, None)
    assert filter_disruption_data({"1": entries}, ["kube-api-new-connections"]) == {"1": entries[2:]}


def test_apply_master_nodes_filter():
    rows = [{"prow_id": "1"}, {"prow_id": "2"}]
    data = {
        "1": [{"backend_name": "kube-api-new-connections", "master_nodes_updated": "Y"}],
        "2": [{"backend_name": "kube-api-new-connections", "master_nodes_updated": "N"}],
    }
    assert apply_master_nodes_filter(rows, data, "Y", True) == [{"prow_id": "1"}]
    assert apply_master_nodes_filter(rows, data, "Y", False) == []
    assert apply_master_nodes_filter(rows, data, None, False) == rows
