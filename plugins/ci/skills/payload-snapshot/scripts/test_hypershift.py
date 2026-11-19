"""Behavioral regressions for profile selection and snapshot output."""

import importlib.util
import json
from pathlib import Path
from urllib.parse import unquote, urlsplit
from unittest.mock import Mock

import pytest

spec = importlib.util.spec_from_file_location(
    "payload_snapshot", Path(__file__).with_name("payload_snapshot.py")
)
ps = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ps)

TAG = "0.1.87-0036-gd2d9578c4.nightly-2026-11-06-105750"
OLDER = "0.1.87-0033-g1b72ba5ab.nightly-2026-11-05-195108"
BASE = "https://hcp.releases.ci.openshift.org"
OCP_TAG = "5.1.0-0.nightly-2026-11-06-105750"
OCP_OLDER = "5.1.0-0.nightly-2026-11-05-195108"


@pytest.mark.parametrize("arguments,tag,older,controller,stream,arch,version", [
    ([], OCP_TAG, OCP_OLDER, "https://amd64.ocp.releases.ci.openshift.org",
     "5.1.0-0.nightly", "amd64", "5.1"),
    (["--profile", "hypershift"], TAG, OLDER, BASE, "hypershift", "multi", "0.1.87"),
    (["--profile", "hypershift", "--release-controller-url", "https://mirror.example/"],
     TAG, OLDER, "https://mirror.example", "hypershift", "multi", "0.1.87"),
    (["--profile", "hypershift", "--stream", "hypershift.v2"],
     TAG, OLDER, BASE, "hypershift.v2", "multi", "0.1.87"),
    (["--profile", "hypershift", "--architecture", "arm64"],
     TAG, OLDER, BASE, "hypershift", "arm64", "0.1.87"),
])
def test_cli_writes_snapshot_using_profile_defaults_and_overrides(
    monkeypatch, tmp_path, arguments, tag, older, controller, stream, arch, version,
):
    def fetch(url, **kwargs):
        parsed = urlsplit(url)
        path = unquote(parsed.path)
        if parsed.netloc == "sippy.dptools.openshift.org" and tag == OCP_TAG:
            assert path == "/api/releases/tags"
            return []
        if parsed.scheme + "://" + parsed.netloc != controller:
            # OCP discovery probes other architecture controllers.
            assert tag == OCP_TAG and path.endswith("/tags")
            return {"tags": []}
        if path.endswith("/tags"):
            return {"tags": [{"name": tag}, {"name": older}]} if f"/{stream}/" in path else {"tags": []}
        assert path.startswith(f"/api/v1/releasestream/{stream}/release/")
        current = path.rsplit("/", 1)[1]
        assert current in (tag, older)
        if parsed.query:
            assert parsed.query == "from=" + older
            return {"changeLogJson": {"updatedImages": []}}
        return {
            "phase": "Rejected" if current == tag else "Accepted",
            "results": {"blockingJobs": {
                "release-5.1-e2e": {"state": "Failed" if current == tag else "Succeeded", "url": ""},
                "release-4.20-e2e": {"state": "Succeeded", "url": ""},
                "unversioned-e2e": {"state": "Succeeded", "url": ""},
            }},
        }

    def unexpected(*args, **kwargs):
        raise AssertionError("metadata collection should not invoke artifact tools")

    monkeypatch.setattr(ps, "fetch_json", fetch)
    monkeypatch.setattr(ps, "_check_gh_auth", lambda: True)
    monkeypatch.setattr(ps, "_check_podman", unexpected)
    monkeypatch.setattr(ps, "_check_rpm", unexpected)
    monkeypatch.setattr(ps, "_check_gcloud", unexpected)
    options = ["--no-rpmdb"] if tag == OCP_TAG else []
    monkeypatch.setattr(ps.sys, "argv", [
        "payload_snapshot.py", tag, *arguments, *options, "--no-junit",
        "--output-dir", str(tmp_path), "--max-chain", "3",
    ])
    ps.main()

    base = next(tmp_path.glob("*/*/summary.json")).parent
    summary = json.loads((base / "summary.json").read_text())
    assert {key: summary[key] for key in (
        "payload_tag", "version", "stream_name", "architecture", "release_controller_url",
    )} == dict(payload_tag=tag, version=version, stream_name=stream,
              architecture=arch, release_controller_url=controller)
    assert summary["phase"] == "Rejected"
    assert summary["chain_length"] == 2
    assert summary["baseline_tag"] == older
    assert summary["blocking_jobs"]["failed"] == 1
    assert summary["blocking_jobs"]["failed_jobs"][0]["name"] == "release-5.1-e2e"
    payload = json.loads((base / tag / "payload.json").read_text())
    assert payload["_release_url"] == f"{controller}/releasestream/{stream}/release/{tag}"
    assert json.loads((base / tag / "changelog.json").read_text())["_source"] == "release-controller"
    # HCP jobs exercise multiple OCP versions; the component version must not
    # be used to classify their operating system.
    if tag == TAG:
        labels = {path.parent.name: json.loads(path.read_text()).get("rhcos_version", "")
                  for path in (base / tag).glob("jobs/blocking/*/job.json")}
        assert labels == {"release-5.1-e2e": "rhcos10-default",
                          "release-4.20-e2e": "rhcos9-default", "unversioned-e2e": ""}


@pytest.mark.parametrize("tag,arch,controller", [
    ("4.22.0-0.nightly-arm64-2026-11-06-105750", "arm64", "arm64.ocp.releases.ci.openshift.org"),
    ("4.22.0-0.okd-scos-nightly-2026-11-06-105750", "amd64", "amd64.origin.releases.ci.openshift.org"),
])
def test_ocp_profile_preserves_architecture_and_okd_routing(tag, arch, controller):
    request = ps.PROFILES["ocp"].resolve(tag)
    assert request.identity.architecture == arch
    assert request.controller_url == "https://" + controller


@pytest.mark.parametrize("arguments", [
    [TAG], ["--profile", "hypershift", OCP_TAG],
    ["--profile", "hypershift", TAG, "--sippy"],
])
def test_cli_rejects_incompatible_profile_before_collection(monkeypatch, arguments):
    monkeypatch.setattr(ps.sys, "argv", ["payload_snapshot.py", *arguments])
    monkeypatch.setattr(ps, "_check_gh_auth", Mock(side_effect=AssertionError("collection started")))
    with pytest.raises(SystemExit) as error:
        ps.main()
    assert error.value.code == 2


def test_core_persists_injected_enrichment_and_reuses_cached_payloads(monkeypatch, tmp_path):
    def unexpected(*args, **kwargs):
        raise AssertionError("core attempted to fetch cached payload details")

    monkeypatch.setattr(ps, "fetch_json", unexpected)
    identity = ps.PayloadTag("opaque-target", "component", "custom", "multi", "custom", "")
    source = Mock(spec=ps.PayloadSource)
    source.streams.return_value = [{"stream_name": "custom"}]
    source.history.return_value = ["opaque-target", "opaque-baseline"]
    source.payload.return_value = {"phase": "Accepted", "_source": "fixture", "results": {
        "blockingJobs": {"e2e": {"state": "Succeeded", "url": ""}},
    }}
    source.changelog.side_effect = lambda tag, previous: {"compared": [tag, previous]}
    stage = Mock(spec=ps.SnapshotStage)
    stage.collect.return_value = {"rpmdb_data": {"opaque-target": [{"tag": "rhcos"}]}}
    base = tmp_path / "stream"
    snapshot = ps.Snapshotter(identity, source, snapshot_dir=str(base),
                              collect_junit=False, collectors=[stage])
    snapshot.run()
    summary = json.loads((base / "summary.json").read_text())
    assert summary["rhcos_rpms"][0]["rpmdb"] == "opaque-target/rpmdb/rhcos/rpmdb.sqlite"
    assert json.loads((base / "opaque-target/changelog.json").read_text())["compared"] == [
        "opaque-target", "opaque-baseline",
    ]
    source.payload.side_effect = unexpected
    snapshot.run()
    assert json.loads((base / "summary.json").read_text()) == summary


@pytest.mark.parametrize("override", [
    {"controller_url": "http://amd64.ocp.releases.ci.openshift.org:8080"},
    {"stream": "another-stream"},
    {"payload_tag": "5.1.0-0.nightly-arm64-2026-11-06-105750",
     "controller_url": "https://amd64.ocp.releases.ci.openshift.org"},
])
def test_snapshots_from_different_controllers_and_streams_coexist_and_reuse_evidence(
    monkeypatch, tmp_path, override,
):
    profile = ps.PROFILES["ocp"]
    first = profile.resolve(OCP_TAG)
    second = profile.resolve(**{"payload_tag": OCP_TAG, **override})
    sources = []

    def build_source(request):
        source = Mock(spec=ps.PayloadSource)
        source.streams.return_value = []
        source.history.return_value = [request.identity.raw]
        source.payload.return_value = {
            "phase": "Accepted" if request == first else "Rejected",
            "_release_controller_url": request.controller_url,
            "results": {"blockingJobs": {"e2e": {
                "state": "Succeeded" if request == first else "Failed", "url": "",
            }}},
        }
        sources.append(source)
        return source

    monkeypatch.setattr(profile, "build_source", build_source)
    options = dict(output_dir=str(tmp_path), collect_junit=False, collect_rpmdb=False)
    profile.build_snapshotter(first, **options).run()
    profile.build_snapshotter(second, **options).run()
    summaries = {json.loads(path.read_text())["phase"]: path
                 for path in tmp_path.glob("*/*/summary.json")}
    assert set(summaries) == {"Accepted", "Rejected"}
    for request, phase, state in ((first, "Accepted", "Succeeded"),
                                  (second, "Rejected", "Failed")):
        base = summaries[phase].parent
        summary = json.loads(summaries[phase].read_text())
        assert summary["payload_tag"] == request.identity.raw
        assert summary["release_controller_url"] == request.controller_url
        assert summary["stream_name"] == request.identity.stream_name
        assert summary["architecture"] == request.identity.architecture
        job = summary["payloads"][0]["jobs"]["blocking"][0]
        assert json.loads((base / job["job_json"]).read_text())["state"] == state

    before = {path: path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()}
    sources[0].payload.side_effect = AssertionError("cached payload was fetched again")
    monkeypatch.setattr(profile, "build_source", lambda request: sources[0])
    profile.build_snapshotter(first, **options).run()

    assert {path: path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()} == before
