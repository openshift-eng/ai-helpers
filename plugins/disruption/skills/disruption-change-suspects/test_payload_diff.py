"""Tests for payload_diff.py — releaseinfo parsing, changed repos, gh compare, and fallbacks."""
import io
import json
import os
import sys
import tempfile
from contextlib import redirect_stdout
from unittest.mock import MagicMock, patch

import pytest

from payload_diff import (
    PayloadError,
    changed_repos,
    component_commits,
    gh_compare,
    main,
    parse_repo,
    payload_version,
    resolve_payload,
    select_component,
    summarize_compare,
)


def _tag(name, commit, repo):
    return {
        "name": name,
        "annotations": {
            "io.openshift.build.commit.id": commit,
            "io.openshift.build.commit.ref": "master",
            "io.openshift.build.source-location": "https://github.com/%s" % repo,
        },
        "from": {"kind": "DockerImage", "name": "quay-proxy.ci.openshift.org/openshift/ci@sha256:00"},
    }


def _releaseinfo(version, tags):
    """Shape of gather-extra releaseinfo.json / `oc adm release info -o json`."""
    return {
        "image": "registry.build04.ci.openshift.org/ci-op-x/release@sha256:19be",
        "metadata": {"kind": "cincinnati-metadata-v0", "version": version, "previous": []},
        "references": {"kind": "ImageStream", "metadata": {"name": version},
                       "spec": {"tags": tags}},
    }


BEFORE = _releaseinfo("5.1.0-0.nightly-2026-11-09-143447", [
    _tag("cluster-authentication-operator", "5a17788ddb9921882df2941dee4a40862e4c8127",
         "openshift/cluster-authentication-operator"),
    _tag("cluster-kube-apiserver-operator", "5105250647f33a232b1bf2982372f7cc66580deb",
         "openshift/cluster-kube-apiserver-operator"),
    _tag("hyperkube", "aaaa", "openshift/kubernetes"),
    _tag("kube-proxy", "aaaa", "openshift/kubernetes"),
    _tag("cli", "cccc", "openshift/oc"),
    {"name": "no-annotations"},
])

AFTER = _releaseinfo("5.1.0-0.ci-2026-11-09-232923", [
    _tag("cluster-authentication-operator", "7e14ab4dd3050d59d211f4ae06851275f591463b",
         "openshift/cluster-authentication-operator"),
    _tag("cluster-kube-apiserver-operator", "d6f7208656ab177260839635e130664203d4700d",
         "openshift/cluster-kube-apiserver-operator"),
    _tag("hyperkube", "bbbb", "openshift/kubernetes"),
    _tag("kube-proxy", "bbbb", "openshift/kubernetes"),
    _tag("cli", "cccc", "openshift/oc"),
    _tag("new-thing", "dddd", "openshift/new-thing.git"),
])

COMPARE_RESPONSE = {
    "status": "ahead", "ahead_by": 2, "behind_by": 0, "total_commits": 2,
    "commits": [
        {"sha": "f62a5c754e0000", "commit": {"committer": {"date": "2026-11-09T13:15:51Z"},
                                             "message": "Merge pull request #1034 from x/token-review-service\n\nbody"}},
        {"sha": "7e14ab4dd30000", "commit": {"committer": {"date": "2026-11-09T15:46:53Z"},
                                             "message": "Merge pull request #1057 from y/update-library-go"}},
    ],
    "files": [
        {"filename": "bindata/oauth-apiserver/authenticator-kubeconfig.yaml", "status": "modified",
         "additions": 2, "deletions": 2},
        {"filename": "vendor/github.com/openshift/library-go/x.go", "status": "modified",
         "additions": 10, "deletions": 1},
    ],
}


def _write(tmp, rel, data):
    path = os.path.join(tmp, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f)
    return path


def test_parse_repo():
    assert parse_repo("https://github.com/openshift/cluster-authentication-operator") == (
        "openshift", "cluster-authentication-operator")
    assert parse_repo("https://github.com/openshift/new-thing.git") == ("openshift", "new-thing")
    assert parse_repo("https://github.com/example/component.v2") == ("example", "component.v2")
    assert parse_repo("https://github.com/example/component.v2.git") == ("example", "component.v2")
    assert parse_repo("https://github.com/example/..") is None
    assert parse_repo("https://gitlab.example.com/x/y") is None
    assert parse_repo("") is None


def test_component_commits_and_version():
    commits = component_commits(BEFORE)
    assert commits["cluster-authentication-operator"] == {
        "commit": "5a17788ddb9921882df2941dee4a40862e4c8127",
        "source": "https://github.com/openshift/cluster-authentication-operator",
        "repo": "openshift/cluster-authentication-operator",
    }
    assert "no-annotations" not in commits
    assert payload_version(BEFORE) == "5.1.0-0.nightly-2026-11-09-143447"
    assert payload_version({"references": {"metadata": {"name": "x"}}}) == "x"


def test_changed_repos_groups_tags_and_skips_unchanged():
    changed = changed_repos(component_commits(BEFORE), component_commits(AFTER))
    assert [(c["repo"], c["tags"]) for c in changed] == [
        ("openshift/cluster-authentication-operator", ["cluster-authentication-operator"]),
        ("openshift/cluster-kube-apiserver-operator", ["cluster-kube-apiserver-operator"]),
        ("openshift/kubernetes", ["hyperkube", "kube-proxy"]),
        ("openshift/new-thing", ["new-thing"]),
    ]
    assert changed[0]["compare_url"] == (
        "https://github.com/openshift/cluster-authentication-operator/compare/"
        "5a17788ddb9921882df2941dee4a40862e4c8127...7e14ab4dd3050d59d211f4ae06851275f591463b")
    assert changed[3]["before"] is None
    assert changed[3]["compare_url"] is None


def test_select_component_by_tag_or_repo():
    before, after = component_commits(BEFORE), component_commits(AFTER)
    assert select_component("cluster-authentication-operator", before, after)[0] == "cluster-authentication-operator"
    assert select_component("kubernetes", before, after)[0] == "hyperkube"
    assert select_component("openshift/oc", before, after)[0] == "cli"
    with pytest.raises(PayloadError):
        select_component("nope", before, after)
    # A repo whose tags moved differently needs an exact tag.
    after["kube-proxy"] = dict(after["kube-proxy"], commit="aaaa")
    with pytest.raises(PayloadError, match="hyperkube, kube-proxy"):
        select_component("kubernetes", before, after)
    assert select_component("kube-proxy", before, after)[2]["commit"] == "aaaa"


def test_summarize_compare_hides_vendor():
    summary = summarize_compare(COMPARE_RESPONSE)
    assert summary["commits"][0] == {"sha": "f62a5c754e", "date": "2026-11-09T13:15:51Z",
                                     "title": "Merge pull request #1034 from x/token-review-service"}
    assert [f["filename"] for f in summary["files"]] == ["bindata/oauth-apiserver/authenticator-kubeconfig.yaml"]
    assert summary["vendor_files_hidden"] == 1
    assert len(summarize_compare(COMPARE_RESPONSE, include_vendor=True)["files"]) == 2
    assert summary["files_truncated"] is False
    full = dict(COMPARE_RESPONSE, files=[{"filename": "vendor/x%d.go" % i} for i in range(300)])
    assert summarize_compare(full)["files_truncated"] is True


def test_resolve_payload_file_and_build_dir():
    with tempfile.TemporaryDirectory() as tmp:
        path = _write(tmp, "111/gather/releaseinfo.json", BEFORE)
        assert resolve_payload(path, tmp)[0] == path
        label, info = resolve_payload(os.path.join(tmp, "111"), tmp)
        assert label == "111"
        assert payload_version(info) == "5.1.0-0.nightly-2026-11-09-143447"
        os.makedirs(os.path.join(tmp, "222"))
        with pytest.raises(PayloadError, match="--gather"):
            resolve_payload(os.path.join(tmp, "222"), tmp)
    with pytest.raises(PayloadError, match="not a file"):
        resolve_payload("garbage", "/tmp")


def test_resolve_payload_run_ref_downloads_anonymously():
    prowjob = {"spec": {"pod_spec": {"containers": [{"args": ["--target=e2e-gcp-ovn-upgrade"]}]}}}
    calls = []

    def run(cmd, **kwargs):
        calls.append((cmd, kwargs))
        dest = cmd[4]
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "w") as f:
            json.dump(prowjob if dest.endswith("prowjob.json") else AFTER, f)
        result = MagicMock()
        result.returncode = 0
        result.stdout = result.stderr = ""
        return result

    with tempfile.TemporaryDirectory() as tmp:
        with patch("subprocess.run", side_effect=run):
            label, info = resolve_payload("periodic-ci-x-e2e-gcp-ovn-upgrade:2119937168964063232", tmp)
        assert os.path.isfile(os.path.join(tmp, "2119937168964063232", "gather", "releaseinfo.json"))
    assert label == "2119937168964063232"
    assert payload_version(info) == "5.1.0-0.ci-2026-11-09-232923"
    assert calls[1][0][3] == ("gs://test-platform-results-public/logs/periodic-ci-x-e2e-gcp-ovn-upgrade/"
                              "2119937168964063232/artifacts/e2e-gcp-ovn-upgrade/gather-extra/artifacts/"
                              "releaseinfo.json")
    assert all(kw["env"]["CLOUDSDK_AUTH_DISABLE_CREDENTIALS"] == "true" for _cmd, kw in calls)


def test_resolve_payload_pullspec_without_oc_prints_command():
    with patch("payload_diff.shutil.which", return_value=None):
        with pytest.raises(PayloadError) as exc:
            resolve_payload("registry.ci.openshift.org/ocp/release-5:5.0.0-0.nightly-2026-11-09-184859", "/tmp")
    assert ("oc adm release info -o json -- "
            "registry.ci.openshift.org/ocp/release-5:5.0.0-0.nightly-2026-11-09-184859") in str(exc.value)


def test_resolve_payload_pullspec_with_oc():
    result = MagicMock()
    result.returncode = 0
    result.stdout = json.dumps(BEFORE)
    result.stderr = ""
    with patch("payload_diff.shutil.which", return_value="/usr/bin/oc"), \
            patch("payload_diff.subprocess.run", return_value=result) as run:
        label, info = resolve_payload("quay.io/openshift-release-dev/ocp-release:5.0.1-x86_64", "/tmp")
    assert run.call_args[0][0] == ["oc", "adm", "release", "info", "-o", "json", "--",
                                   "quay.io/openshift-release-dev/ocp-release:5.0.1-x86_64"]
    assert payload_version(info) == "5.1.0-0.nightly-2026-11-09-143447"


def test_resolve_payload_rejects_an_option_like_ref():
    with pytest.raises(PayloadError, match="is not a file"):
        resolve_payload("--kubeconfig=/tmp/a:b", "/tmp")


def test_gh_compare_rejects_non_sha_commits():
    with patch("payload_diff.subprocess.run") as run:
        data, error = gh_compare("openshift/origin", "abc1234", "../../user?x=")
    assert data is None and "not hex SHAs" in error
    run.assert_not_called()
    assert parse_repo("https://github.com/open?shift/origin") is None


def _run_main(args):
    out = io.StringIO()
    with redirect_stdout(out):
        code = main(args)
    return code, out.getvalue()


def test_main_lists_changed_repos():
    with tempfile.TemporaryDirectory() as tmp:
        before = _write(tmp, "before.json", BEFORE)
        after = _write(tmp, "after.json", AFTER)
        code, text = _run_main([before, after])
    assert code == 0
    assert "before: %s (5.1.0-0.nightly-2026-11-09-143447)" % before in text
    assert "4 repos changed:" in text
    assert "openshift/kubernetes aaaa...bbbb (hyperkube, kube-proxy)" in text
    assert "openshift/new-thing absent...dddd (new-thing)" in text


def test_main_component_with_gh():
    result = MagicMock()
    result.returncode = 0
    result.stdout = json.dumps(COMPARE_RESPONSE)
    with tempfile.TemporaryDirectory() as tmp:
        before = _write(tmp, "before.json", BEFORE)
        after = _write(tmp, "after.json", AFTER)
        with patch("payload_diff.shutil.which", return_value="/usr/bin/gh"), \
                patch("payload_diff.subprocess.run", return_value=result) as run:
            code, text = _run_main([before, after, "--component", "cluster-authentication-operator"])
    assert code == 0
    assert run.call_args[0][0] == [
        "gh", "api", "repos/openshift/cluster-authentication-operator/compare/"
        "5a17788ddb9921882df2941dee4a40862e4c8127...7e14ab4dd3050d59d211f4ae06851275f591463b"]
    assert "2 commits (status ahead, ahead 2, behind 0)" in text
    assert "f62a5c754e 2026-11-09T13:15:51Z Merge pull request #1034" in text
    assert "files (1, 1 vendor/ hidden):" in text
    assert "modified bindata/oauth-apiserver/authenticator-kubeconfig.yaml +2/-2" in text


def test_main_component_gh_failure_prints_command_and_url():
    result = MagicMock()
    result.returncode = 1
    result.stdout = ""
    result.stderr = "HTTP 403: API rate limit exceeded"
    with tempfile.TemporaryDirectory() as tmp:
        before = _write(tmp, "before.json", BEFORE)
        after = _write(tmp, "after.json", AFTER)
        with patch("payload_diff.shutil.which", return_value="/usr/bin/gh"), \
                patch("payload_diff.subprocess.run", return_value=result):
            code, text = _run_main([before, after, "--component", "cluster-kube-apiserver-operator"])
        with patch("payload_diff.shutil.which", return_value=None):
            code2, text2 = _run_main([before, after, "--component", "cluster-kube-apiserver-operator",
                                      "--format", "json"])
    assert code == 0
    assert "gh compare unavailable (exited 1: HTTP 403: API rate limit exceeded). Run:" in text
    assert ("    gh api repos/openshift/cluster-kube-apiserver-operator/compare/"
            "5105250647f33a232b1bf2982372f7cc66580deb...d6f7208656ab177260839635e130664203d4700d") in text
    assert "or open https://github.com/openshift/cluster-kube-apiserver-operator/compare/" in text
    data = json.loads(text2)
    assert code2 == 0
    assert data["component"]["compare_error"] == "gh not found"
    assert data["component"]["command"][:2] == ["gh", "api"]


def test_main_component_unchanged_and_errors():
    with tempfile.TemporaryDirectory() as tmp:
        before = _write(tmp, "before.json", BEFORE)
        after = _write(tmp, "after.json", AFTER)
        empty = _write(tmp, "empty.json", {"references": {"spec": {"tags": []}}})
        code, text = _run_main([before, after, "--component", "cli"])
        assert code == 0
        assert "unchanged between the two payloads" in text
        assert _run_main([before, empty])[0] == 1
        assert _run_main([before, after, "--component", "nope"])[0] == 1
        assert _run_main([before, os.path.join(tmp, "missing")])[0] == 1


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
