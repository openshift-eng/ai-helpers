"""Tests for disruption_common.series — dashboard/alert parsing and series resolution."""
import datetime
import os
import sys

import pytest

# Run as a script (make test), the package parent is not on sys.path yet.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from disruption_common.series import (  # noqa: E402
    SeriesError,
    apply_master_nodes_filter,
    backend_name_warnings,
    disruption_peak,
    expand_backend_selectors,
    filter_disruption_data,
    grafana_params_from_inputs,
    master_nodes_filter_value,
    master_nodes_means_all,
    parse_backend,
    parse_grafana_url,
    resolve_series,
    resolve_window_start,
)

SAMPLE_ALERT = """\
Alert:  - warning
Description: P95 disruption has regressed over the past several days when compared to the 30 days prior to previous GA release for: openshift-api-http2-service-network-reused-connections azure micro ovn
Details:
   • alertname: DisruptionRegressionP95
   • architecture: amd64
   • backend: openshift-api-http2-service-network-reused-connections
   • category: disruption
   • compare_release: 4.22
   • delta: P95
   • feature_set: default
   • master_nodes_updated: Y
   • namespace: trt-monitoring
   • network: ovn
   • platform: azure
   • prometheus: trt-monitoring/trt
   • release: 5.0
   • releaseStatus: Development
   • severity: warning
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


def test_parse_backend_and_expand_selectors():
    assert parse_backend("cache-kube-api-reused-connections") == ("cache-kube-api", "reused")
    assert parse_backend("oauth-api") == ("oauth-api", None)
    assert expand_backend_selectors("kube-api") == {
        "kube-api-new-connections", "kube-api-reused-connections"}
    assert expand_backend_selectors(["kube-api-new-connections"]) == {"kube-api-new-connections"}


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


def test_parse_grafana_url_extracts_vars():
    url = (
        "https://grafana-loki.ci.openshift.org/d/gEdw_aLvk/"
        "disruption-for-5-0-os-agnostic"
        "?orgId=1&var-percentile=P50&var-platform=gcp"
        "&var-backend=host-to-host-new-connections"
        "&var-upgrade_type=micro&var-releases=5.0"
    )
    result = parse_grafana_url(url)
    assert result["platform"] == "gcp"
    assert result["backend"] == "host-to-host-new-connections"
    assert result["upgrade_type"] == "micro"
    assert result["releases"] == "5.0"
    assert result["percentile"] == "P50"
    assert result["_dashboard_name"] == "disruption-for-5-0-os-agnostic"
    assert "orgId" not in result


def test_parse_grafana_url_multi_value():
    url = (
        "https://grafana-loki.ci.openshift.org/d/abc/dash"
        "?var-platform=azure&var-platform=gcp"
        "&var-backend=host-to-host-new-connections"
        "&var-releases=5.0&var-ipmode=ipv6&var-ipmode=ipv4"
        "&var-os=rhcos10&var-os=rhcos9"
    )
    result = parse_grafana_url(url)
    assert result["platform"] == "azure,gcp"
    assert result["backend"] == "host-to-host-new-connections"
    assert result["ipmode"] == "ipv6,ipv4"
    assert result["os"] == "rhcos10,rhcos9"
    assert result["releases"] == "5.0"


def test_parse_grafana_url_all_variants():
    url = (
        "https://grafana-loki.ci.openshift.org/d/abc/dash"
        "?var-platform=aws&var-architectures=arm64"
        "&var-topologies=single&var-networks=sdn"
        "&var-upgrade_type=minor&var-releases=4.18"
        "&var-backend=kube-api-reused-connections"
    )
    result = parse_grafana_url(url)
    assert result["platform"] == "aws"
    assert result["architectures"] == "arm64"
    assert result["topologies"] == "single"
    assert result["networks"] == "sdn"
    assert result["upgrade_type"] == "minor"
    assert result["releases"] == "4.18"
    assert result["backend"] == "kube-api-reused-connections"


def test_parse_grafana_url_featureset_ipmode_os():
    url = (
        "https://grafana-loki.ci.openshift.org/d/abc/dash"
        "?var-platform=aws&var-backend=kube-api-new-connections"
        "&var-releases=5.0&var-featureset=techpreview"
        "&var-ipmode=ipv6&var-os=rhcos10"
    )
    result = parse_grafana_url(url)
    assert result["featureset"] == "techpreview"
    assert result["ipmode"] == "ipv6"
    assert result["os"] == "rhcos10"


def test_parse_grafana_url_feature_set_alias():
    url = (
        "https://grafana-loki.ci.openshift.org/d/abc/dash"
        "?var-feature_set=default&var-backend=kube-api-new-connections&var-releases=5.0"
    )
    result = parse_grafana_url(url)
    assert result["featureset"] == "default"
    assert "feature_set" not in result


def test_parse_backend_new_connections():
    base, conn = parse_backend("host-to-host-new-connections")
    assert base == "host-to-host"
    assert conn == "new"


def test_parse_backend_reused_connections():
    base, conn = parse_backend("kube-api-reused-connections")
    assert base == "kube-api"
    assert conn == "reused"


def test_parse_backend_no_suffix():
    base, conn = parse_backend("oauth-api")
    assert base == "oauth-api"
    assert conn is None


def test_parse_backend_cache_prefix():
    base, conn = parse_backend("cache-kube-api-new-connections")
    assert base == "cache-kube-api"
    assert conn == "new"


def test_resolve_window_start_lookback_is_calendar_days():
    now = datetime.datetime(2026, 10, 5, 15, 0, tzinfo=datetime.timezone.utc)
    assert resolve_window_start(None, 7, now=now) == datetime.datetime(
        2026, 9, 28, tzinfo=datetime.timezone.utc)
    # Explicit --since-hours wins over var-lookback.
    assert resolve_window_start(48, 7, now=now) == datetime.datetime(
        2026, 10, 3, 15, 0, tzinfo=datetime.timezone.utc)
    # No lookback and no --since-hours: 30 days rolling.
    assert resolve_window_start(None, None, now=now) == now - datetime.timedelta(hours=720)


def test_alert_without_link_uses_series_labels_and_three_day_lookback():
    params = grafana_params_from_inputs(alert_text=SAMPLE_ALERT + "   • os: rhcos10\n")
    assert params["_dashboard_name"] == "(alert)"
    assert params["lookback"] == "3"
    assert params["releases"] == "5.0"
    assert params["backend"] == "openshift-api-http2-service-network-reused-connections"
    assert params["platform"] == "azure"
    assert params["architectures"] == "amd64"
    assert params["topologies"] == "ha"
    assert params["networks"] == "ovn"
    assert params["upgrade_type"] == "micro"
    assert params["featureset"] == "default"
    assert params["os"] == "rhcos10"
    assert params["master_nodes_updated"] == "Y"
    assert params["percentile"] == "P95"
    assert params["compare_release"] == "4.22"
    assert "releaseStatus" not in params


def test_alert_link_wins_and_omitted_labels_are_overlaid():
    text = SAMPLE_ALERT + "link: " + ALERT_LINK + "\n   • os: rhcos10\n"
    params = grafana_params_from_inputs(alert_text=text)
    assert params["_dashboard_name"] == "disruption-for-5-0-os-agnostic"
    assert params["lookback"] == "7"
    assert params["percentile"] == "P95"
    assert params["featureset"] == "default"
    assert params["os"] == "rhcos10"
    assert params["compare_release"] == "4.22"
    assert params["master_nodes_updated"] == "Y"


def test_explicit_url_is_not_replaced_by_alert_link():
    params = grafana_params_from_inputs(
        grafana_url="https://grafana-loki.ci.openshift.org/d/abc/other?var-releases=5.0&var-backend=kube-api-new-connections&var-lookback=1",
        alert_text=SAMPLE_ALERT + "link: " + ALERT_LINK + "\n",
    )
    assert params["_dashboard_name"] == "other"
    assert params["lookback"] == "1"
    assert params["backend"] == "kube-api-new-connections"
    assert params["featureset"] == "default"
    assert params["platform"] == "azure"


def test_apply_master_nodes_filter_drops_other_runs_including_clean():
    rows = [
        {"prow_id": "Y1"},
        {"prow_id": "N1"},
        {"prow_id": "Y0"},
    ]
    data = {
        "Y1": [{"backend_name": "b", "disruption_seconds": 20, "master_nodes_updated": "Y"}],
        "N1": [{"backend_name": "b", "disruption_seconds": 90, "master_nodes_updated": "N"}],
        "Y0": [{"backend_name": "b", "disruption_seconds": 0, "master_nodes_updated": "Y"}],
    }
    kept = apply_master_nodes_filter(rows, data, "Y", True)
    assert [row["prow_id"] for row in kept] == ["Y1", "Y0"]
    assert apply_master_nodes_filter(rows, data, "Y", False) == []



@pytest.mark.parametrize("raw", ["Y,N", "N,Y", "y, n", "Y,N,Y"])
def test_master_nodes_y_and_n_together_means_all_without_warning(raw, capsys):
    assert master_nodes_means_all(raw)
    assert master_nodes_filter_value(raw) is None
    assert capsys.readouterr().err == ""


def test_master_nodes_single_value_filters_and_unknown_warns(capsys):
    assert master_nodes_filter_value("y") == "Y"
    assert master_nodes_filter_value("N,N") == "N"
    assert capsys.readouterr().err == ""
    assert not master_nodes_means_all("Y")
    assert master_nodes_filter_value("Y,X") is None
    assert "is not Y or N" in capsys.readouterr().err


def test_resolve_series_master_nodes_y_and_n_from_url(capsys):
    series = resolve_series(
        "https://grafana.example/d/x/dash?var-releases=5.1&var-backend=kube-api-new-connections"
        "&var-master_nodes_updated=Y&var-master_nodes_updated=N")
    assert series["master_nodes_updated"] is None
    assert "master_nodes_updated" not in capsys.readouterr().err


_SEEN = {"1": [{"backend_name": "host-to-host-new-connections"},
               {"backend_name": "kube-api-new-connections"},
               {"backend_name": "kube-api-reused-connections"}]}


def test_backend_name_warnings_flags_whitespace_and_suggests_the_seen_name():
    warnings = backend_name_warnings(["host-to-host-new-connec  tions", "kube-api-new-connections"], _SEEN)
    assert warnings == [
        "backend 'host-to-host-new-connec  tions' contains whitespace and is not in the disruption data "
        "for any scanned run; did you mean 'host-to-host-new-connections'? It is used exactly as given."]


def test_backend_name_warnings_flags_names_missing_from_the_data():
    warnings = backend_name_warnings(["kube-api-new-conections", "kube-api", "no-such-thing-at-all"], _SEEN)
    assert len(warnings) == 2
    assert "'kube-api-new-conections' is not in the disruption data" in warnings[0]
    assert "did you mean 'kube-api-new-connections'?" in warnings[0]
    # A bare base matches through its connection variants; nothing close means no suggestion.
    assert "no-such-thing-at-all" in warnings[1] and "did you mean" not in warnings[1]


def test_backend_name_warnings_without_data_checks_only_whitespace():
    assert backend_name_warnings(["kube-api-new-conections"], {}) == []
    warnings = backend_name_warnings(["kube-api new-connections"], {})
    assert len(warnings) == 1 and "contains whitespace" in warnings[0]
    assert "not in the disruption data" not in warnings[0]


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
