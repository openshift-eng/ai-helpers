#!/usr/bin/env python3
"""Tests for hybrid release-controller/Sippy payload collection."""

import importlib.util
import json
import os
import urllib.error
import urllib.parse
from unittest.mock import Mock


_HERE = os.path.dirname(os.path.abspath(__file__))


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "payload_snapshot_sippy", os.path.join(_HERE, "payload_snapshot.py")
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ps = _load_module()

TARGET = "5.0.0-0.nightly-2026-07-26-222842"
CULLED = "5.0.0-0.nightly-2026-07-23-224236"
BASELINE = "5.0.0-0.nightly-2026-07-22-000000"


def _payload(state):
    return {
        "phase": "Rejected" if state != "Succeeded" else "Accepted",
        "results": {
            "blockingJobs": {
                "job-a": {"state": state, "url": ""},
            }
        },
    }


def test_sippy_release_endpoints_are_filtered(monkeypatch):
    urls = []

    def fake_fetch_json(url, timeout=30, max_retries=6):
        urls.append(url)
        if "/releases/tags" in url:
            return []
        if "/releases/job_runs" in url:
            return []
        if "/releases/pull_requests" in url:
            return [{"url": "https://github.com/openshift/origin/pull/1"}]
        if "/payloads/diff" in url:
            return [{"url": "https://github.com/openshift/origin/pull/2"}]
        raise AssertionError(f"unexpected URL: {url}")

    monkeypatch.setattr(ps, "fetch_json", fake_fetch_json)
    client = ps.SippyClient("5.0", architecture="arm64", stream="nightly")

    client._get_tags()
    client.fetch_job_runs(TARGET)
    prs = client.fetch_pull_requests(TARGET)
    diff = client.fetch_changelog(TARGET, from_tag=CULLED)

    assert len(prs) == 1
    assert diff[0]["url"].endswith("/pull/2")
    tag_query = urllib.parse.parse_qs(urllib.parse.urlparse(urls[0]).query)
    tag_filter = json.loads(tag_query["filter"][0])
    assert tag_query["release"] == ["5.0"]
    assert tag_query["sortField"] == ["release_time"]
    assert tag_filter["items"] == [
        {
            "columnField": "architecture",
            "operatorValue": "equals",
            "value": "arm64",
        },
        {
            "columnField": "stream",
            "operatorValue": "equals",
            "value": "nightly",
        },
    ]

    assert "/api/releases/job_runs" in urls[1]
    assert json.loads(
        urllib.parse.parse_qs(urllib.parse.urlparse(urls[1]).query)["filter"][0]
    )["items"][0]["value"] == TARGET
    assert "/api/releases/pull_requests" in urls[2]
    assert "/api/payloads/diff" in urls[3]
    diff_query = urllib.parse.parse_qs(urllib.parse.urlparse(urls[3]).query)
    assert diff_query == {
        "toPayload": [TARGET],
        "fromPayload": [CULLED],
    }


def test_sippy_tags_always_filter_nonstandard_stream(monkeypatch):
    urls = []

    def fake_fetch_json(url, timeout=30, max_retries=6):
        urls.append(url)
        return []

    monkeypatch.setattr(ps, "fetch_json", fake_fetch_json)
    client = ps.SippyClient("4.22", stream="okd-scos-nightly")

    client.fetch_tags()

    query = urllib.parse.parse_qs(urllib.parse.urlparse(urls[0]).query)
    tag_filter = json.loads(query["filter"][0])
    assert tag_filter["items"][1] == {
        "columnField": "stream",
        "operatorValue": "equals",
        "value": "okd-scos-nightly",
    }


def test_sippy_changelog_falls_back_to_per_payload_prs(monkeypatch):
    urls = []

    def fake_fetch_json(url, timeout=30, max_retries=6):
        urls.append(url)
        if "/payloads/diff" in url:
            raise urllib.error.URLError("diff unavailable")
        return [{"url": "https://github.com/openshift/origin/pull/3"}]

    monkeypatch.setattr(ps, "fetch_json", fake_fetch_json)
    client = ps.SippyClient("5.0")

    prs = client.fetch_changelog(TARGET, from_tag=CULLED)

    assert prs[0]["url"].endswith("/pull/3")
    assert "/api/payloads/diff" in urls[0]
    assert "/api/releases/pull_requests" in urls[1]


def test_sippy_chain_does_not_treat_unindexed_jobs_as_green():
    class FakeSippy:
        def fetch_tags(self):
            return [
                {"release_tag": TARGET},
                {"release_tag": BASELINE},
            ]

        def fetch_job_runs(self, tag_name):
            if tag_name == TARGET:
                return []
            return [{"kind": "Blocking", "state": "Succeeded"}]

        def find_tag(self, tag_name):
            return {
                "phase": "Rejected",
                "forced": False,
                "failed_job_names": [],
            }

    chain = ps.SippyPayloadChain(FakeSippy(), max_depth=10)

    assert chain.build(TARGET) == [TARGET, BASELINE]


def test_sippy_chain_accepts_confirmed_jobless_baseline():
    class FakeSippy:
        def fetch_job_runs(self, tag_name):
            return []

        def find_tag(self, tag_name):
            return {
                "phase": "Accepted",
                "forced": False,
                "failed_job_names": [],
            }

    chain = ps.SippyPayloadChain(FakeSippy())

    assert chain._all_blocking_passed(BASELINE) is True


def test_hybrid_chain_restores_culled_predecessor():
    class FakeReleaseController:
        def fetch_tags(self, stream_name):
            return [{"name": TARGET}, {"name": BASELINE}]

        def fetch_release(self, stream_name, tag_name):
            return _payload("Failed" if tag_name == TARGET else "Succeeded")

        def resolve_prow_state(self, prow_url):
            return None

    class FakeSippy:
        def fetch_tags(self):
            return [
                {"release_tag": TARGET},
                {"release_tag": CULLED},
                {"release_tag": BASELINE},
            ]

        def build_synthetic_payload(self, tag_name, tag):
            assert tag_name == CULLED
            payload = _payload("Failed")
            payload["_source"] = "sippy"
            return payload

    chain_builder = ps.HybridPayloadChain(
        FakeReleaseController(),
        FakeSippy(),
        "5.0.0-0.nightly",
        max_depth=10,
    )

    assert chain_builder.build(TARGET) == [TARGET, CULLED, BASELINE]
    assert chain_builder.sources == {
        TARGET: "release-controller",
        CULLED: "sippy",
        BASELINE: "release-controller",
    }


def test_hybrid_chain_can_start_from_culled_target():
    class FakeReleaseController:
        def fetch_tags(self, stream_name):
            return [{"name": BASELINE}]

        def fetch_release(self, stream_name, tag_name):
            assert tag_name == BASELINE
            return _payload("Succeeded")

        def resolve_prow_state(self, prow_url):
            return None

    class FakeSippy:
        def fetch_tags(self):
            return [
                {"release_tag": TARGET},
                {"release_tag": CULLED},
                {"release_tag": BASELINE},
            ]

        def build_synthetic_payload(self, tag_name, tag):
            assert tag_name in (TARGET, CULLED)
            payload = _payload("Failed")
            payload["_source"] = "sippy"
            return payload

    chain_builder = ps.HybridPayloadChain(
        FakeReleaseController(),
        FakeSippy(),
        "5.0.0-0.nightly",
        max_depth=10,
    )

    assert chain_builder.build(TARGET) == [TARGET, CULLED, BASELINE]
    assert chain_builder.sources[TARGET] == "sippy"
    assert chain_builder.sources[BASELINE] == "release-controller"


def test_payload_collection_falls_back_per_tag_and_diff(tmp_path, monkeypatch):
    class FakeReleaseController:
        def __init__(self):
            self.url = "https://release-controller.example"
            self.changelog_calls = []

        def fetch_release(self, stream_name, tag_name):
            return _payload("Failed" if tag_name == TARGET else "Succeeded")

        def fetch_tags(self, stream_name):
            return [{"name": TARGET}, {"name": BASELINE}]

        def release_url(self, stream_name, tag_name):
            return f"https://release-controller.example/{tag_name}"

        def fetch_changelog(self, stream_name, tag_name, from_tag):
            self.changelog_calls.append((tag_name, from_tag))
            return {"changeLogJson": {"updatedImages": []}}

    class FakeSippy:
        def __init__(self):
            self.payload_calls = []
            self.changelog_calls = []

        def fetch_tags(self):
            return [{"release_tag": tag} for tag in (TARGET, CULLED, BASELINE)]

        def build_synthetic_payload(self, tag_name, tag):
            self.payload_calls.append(tag_name)
            payload = _payload("Failed")
            payload["_release_url"] = f"https://sippy.example/{tag_name}"
            payload["_source"] = "sippy"
            return payload

        def build_synthetic_changelog(self, tag_name, from_tag=None):
            self.changelog_calls.append((tag_name, from_tag))
            return {
                "changeLogJson": {"updatedImages": []},
                "_source": "sippy",
            }

    profile = ps.PROFILES["ocp"]
    request = profile.resolve(TARGET, controller_url="https://release-controller.example")
    rc = FakeReleaseController()
    sippy = FakeSippy()
    monkeypatch.setattr(ps, "ReleaseController", lambda url: rc)
    monkeypatch.setattr(ps, "SippyClient", lambda *args: sippy)
    source = profile.build_source(request)
    chain = source.history(TARGET, 5)
    assert chain == [TARGET, CULLED, BASELINE]
    # History already queried the missing payload; check collection separately.
    sippy.payload_calls.clear()
    snapshotter = ps.Snapshotter(request.identity, source, snapshot_dir=str(tmp_path),
                                collect_junit=False)

    base_dir = tmp_path / "5.0" / "nightly"
    collectors = snapshotter._collect_payloads(
        str(base_dir), chain
    )

    assert collectors == []
    assert sippy.payload_calls == [CULLED]
    assert sippy.changelog_calls == [
        (TARGET, CULLED),
        (CULLED, BASELINE),
    ]
    assert rc.changelog_calls == []

    with open(base_dir / TARGET / "payload.json", encoding="utf-8") as handle:
        assert json.load(handle)["_source"] == "release-controller"
    with open(base_dir / CULLED / "payload.json", encoding="utf-8") as handle:
        assert json.load(handle)["_source"] == "sippy"
    with open(base_dir / TARGET / "changelog.json", encoding="utf-8") as handle:
        assert json.load(handle)["_source"] == "sippy"


def test_ocp_source_keeps_retained_diffs_on_controller():
    tag = ps.PayloadTag.parse(TARGET)
    rc = Mock(url="https://controller.example")
    rc.fetch_changelog.return_value = {"changeLogJson": {"updatedImages": []}}
    rc.fetch_tags.return_value = [{"name": TARGET}, {"name": BASELINE}]
    rc.fetch_release.side_effect = lambda stream, name: _payload(
        "Failed" if name == TARGET else "Succeeded"
    )
    sippy = Mock()
    sippy.fetch_tags.return_value = []
    source = ps.OcpPayloadSource(ps.ControllerSource(rc, tag),
                                 ps.SippySource(sippy, rc.url))
    assert source.history(TARGET, 5) == [TARGET, BASELINE]

    assert source.changelog(TARGET, BASELINE)["_source"] == "release-controller"
    rc.fetch_changelog.assert_called_once_with(tag.stream_name, TARGET, BASELINE)
    sippy.build_synthetic_changelog.assert_not_called()


def test_ocp_source_retains_controller_history_when_sippy_is_unavailable():
    tag = ps.PayloadTag.parse(TARGET)
    rc = Mock(url="https://controller.example")
    rc.fetch_tags.return_value = [{"name": TARGET}, {"name": BASELINE}]
    rc.fetch_release.side_effect = lambda stream, name: _payload(
        "Failed" if name == TARGET else "Succeeded"
    )
    sippy = Mock()
    sippy.fetch_tags.side_effect = urllib.error.URLError("unavailable")
    source = ps.OcpPayloadSource(ps.ControllerSource(rc, tag),
                                 ps.SippySource(sippy, rc.url))

    assert source.history(TARGET, 5) == [TARGET, BASELINE]
