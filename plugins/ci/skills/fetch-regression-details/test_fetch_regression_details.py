import io
import json

import fetch_regression_details as frd


def _fetch(monkeypatch, labels_response):
    f = frd.RegressionFetcher(1)
    monkeypatch.setattr(f, "fetch_raw_data", lambda: {})
    monkeypatch.setattr(f, "parse_regression", lambda raw: {"test_details_url": "x"})
    monkeypatch.setattr(f, "fetch_test_details", lambda url: {})
    monkeypatch.setattr(f, "parse_analyses_metadata", lambda td: {})
    monkeypatch.setattr(f, "parse_failed_jobs_by_job", lambda td: {
        "a": {"label_summary": {"Infra": 2}}, "b": {"label_summary": {"Etcd": 1}}})
    monkeypatch.setattr(frd.urllib.request, "urlopen", labels_response)
    return f.fetch_and_parse()


def test_label_bugs_resolved(monkeypatch):
    body = json.dumps([{"id": "Infra", "bugs": ["OCPBUGS-1"]}]).encode()
    out = _fetch(monkeypatch, lambda url, timeout: io.BytesIO(body))
    assert out["label_bugs"] == {"Etcd": [], "Infra": ["OCPBUGS-1"]}


def test_label_bugs_error_on_timeout(monkeypatch):
    def boom(url, timeout):
        raise TimeoutError("timed out")
    out = _fetch(monkeypatch, boom)
    assert "label_bugs" not in out and out["label_bugs_error"] == "timed out"
