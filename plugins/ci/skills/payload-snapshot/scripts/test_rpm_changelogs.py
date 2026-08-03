#!/usr/bin/env python3
"""Tests for RPM changelog extraction (packages changed vs. baseline).

Run with: pytest test_rpm_changelogs.py
"""

import importlib.util
import os

import pytest


_HERE = os.path.dirname(os.path.abspath(__file__))


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "payload_snapshot_rpm_changelogs", os.path.join(_HERE, "payload_snapshot.py")
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ps = _load_module()


def _snapshotter(**kwargs):
    tag = ps.PayloadTag.parse("5.0.0-0.nightly-2026-08-03-000000")
    return ps.Snapshotter(tag, **kwargs)


def _fake_result(returncode=0, stdout="", stderr=""):
    return type("R", (), {
        "returncode": returncode, "stdout": stdout, "stderr": stderr,
    })()


# ---------------------------------------------------------------------------
# _trim_changelog_to_new_entries — version-string heuristic
# ---------------------------------------------------------------------------

CHANGELOG = """\
* Fri Aug 01 2026 Some Body <a@b.com> - 5.14.0-687.33.1.el9_8
- newest entry

* Wed Jul 30 2026 Some Body <a@b.com> - 5.14.0-687.32.1.el9_8
- boundary entry (old version)

* Mon Jul 20 2026 Some Body <a@b.com> - 5.14.0-687.30.1.el9_8
- older entry
"""


def test_trim_finds_boundary_and_keeps_only_newer_entries():
    trimmed, found = ps._trim_changelog_to_new_entries(
        CHANGELOG, "5.14.0-687.32.1.el9_8"
    )
    assert found is True
    assert "newest entry" in trimmed
    assert "boundary entry" not in trimmed
    assert "older entry" not in trimmed


def test_trim_strips_epoch_prefix_before_matching():
    trimmed, found = ps._trim_changelog_to_new_entries(
        CHANGELOG, "2:5.14.0-687.32.1.el9_8"
    )
    assert found is True
    assert "newest entry" in trimmed


def test_trim_falls_back_to_full_changelog_when_no_match():
    trimmed, found = ps._trim_changelog_to_new_entries(CHANGELOG, "9.9.9-nomatch")
    assert found is False
    assert trimmed.strip() == CHANGELOG.strip()


def test_trim_does_not_false_positive_on_substring_version():
    """A short old version must not match inside a longer newer one.

    Regression test: old="1.2" used to match anywhere inside "1.20.3-1"
    (a plain substring test), silently discarding the real newest entry
    while reporting boundary_found=True.
    """
    changelog = (
        "* Mon Aug 03 2026 Someone <a@b.com> - 1.20.3-1\n"
        "- newest fix\n\n"
        "* Mon Jan 01 2026 Someone <a@b.com> - 1.2-1\n"
        "- old baseline\n"
    )
    trimmed, found = ps._trim_changelog_to_new_entries(changelog, "1.2")
    assert found is False
    assert "newest fix" in trimmed
    assert "old baseline" in trimmed


# ---------------------------------------------------------------------------
# _diff_changelog_against_baseline — exact rpmdb-vs-rpmdb diff
# ---------------------------------------------------------------------------

def test_diff_against_baseline_returns_only_new_entries():
    baseline = (
        "* Wed Jul 30 2026 Some Body <a@b.com> - 1.1-1\n"
        "- boundary entry\n\n"
        "* Mon Jul 20 2026 Some Body <a@b.com> - 1.0-1\n"
        "- older entry\n"
    )
    target = (
        "* Fri Aug 01 2026 Some Body <a@b.com> - 1.2-1\n"
        "- newest entry\n\n"
    ) + baseline
    diff = ps._diff_changelog_against_baseline(target, baseline)
    assert diff is not None
    assert "newest entry" in diff
    assert "boundary entry" not in diff
    assert "older entry" not in diff


def test_diff_against_baseline_returns_none_when_not_a_clean_suffix():
    """Baseline entries must appear verbatim as target's oldest suffix.

    If they don't (diverged history, or the package wasn't in the
    baseline), the caller must fall back rather than trust a bogus diff.
    """
    baseline = "* Wed Jul 30 2026 Some Body <a@b.com> - 1.1-1\n- boundary entry\n"
    target = "* Fri Aug 01 2026 Some Body <a@b.com> - 1.2-1\n- newest entry\n"
    assert ps._diff_changelog_against_baseline(target, baseline) is None


def test_diff_against_baseline_returns_none_for_empty_baseline():
    assert ps._diff_changelog_against_baseline("anything", "") is None


# ---------------------------------------------------------------------------
# _read_changelog_cache_header — round-trips the header _extract_one_changelog writes
# ---------------------------------------------------------------------------

def test_cache_header_round_trips(tmp_path):
    path = tmp_path / "pkg.txt"
    ps._write_text(
        str(path),
        "# pkg: 1.0-1 -> 1.1-1\n# boundary_found: True\n# trim_method: rpmdb_diff\n\nbody",
    )
    header = ps._read_changelog_cache_header(str(path))
    assert header == {
        "old": "1.0-1", "new": "1.1-1",
        "boundary_found": True, "trim_method": "rpmdb_diff",
    }


def test_cache_header_returns_none_for_malformed_file(tmp_path):
    path = tmp_path / "pkg.txt"
    ps._write_text(str(path), "not a changelog header\n")
    assert ps._read_changelog_cache_header(str(path)) is None


def test_cache_header_returns_none_for_missing_file(tmp_path):
    assert ps._read_changelog_cache_header(str(tmp_path / "missing.txt")) is None


# ---------------------------------------------------------------------------
# Snapshotter._extract_one_changelog
# ---------------------------------------------------------------------------

def test_extract_prefers_exact_rpmdb_diff_over_baseline(tmp_path, monkeypatch):
    target_dir = str(tmp_path / "target")
    baseline_dir = str(tmp_path / "baseline")
    baseline_text = "* Wed Jul 30 2026 A <a@b.com> - 1.1-1\n- boundary\n"
    target_text = (
        "* Fri Aug 01 2026 A <a@b.com> - 1.2-1\n- newest\n\n"
    ) + baseline_text

    def fake_run(args, **kwargs):
        dbpath = args[args.index("--dbpath") + 1]
        if dbpath == target_dir:
            return _fake_result(stdout=target_text)
        return _fake_result(stdout=baseline_text)

    monkeypatch.setattr(ps.subprocess, "run", fake_run)
    snap = _snapshotter()
    entry = snap._extract_one_changelog(
        "target-tag", "rhel-coreos-10", target_dir, "openshift-clients",
        "1.1-1", "1.2-1", baseline_variant_dir=baseline_dir,
    )
    assert entry["trim_method"] == "rpmdb_diff"
    assert entry["boundary_found"] is True
    with open(os.path.join(target_dir, "changelogs", "openshift-clients.txt")) as f:
        content = f.read()
    assert "newest" in content
    assert "- boundary\n" not in content


def test_extract_falls_back_to_version_match_when_baseline_diverged(tmp_path, monkeypatch):
    target_dir = str(tmp_path / "target")
    baseline_dir = str(tmp_path / "baseline")
    target_text = (
        "* Fri Aug 01 2026 A <a@b.com> - 1.2-1\n- newest\n\n"
        "* Wed Jul 30 2026 A <a@b.com> - 1.1-1\n- boundary\n"
    )
    # Baseline changelog doesn't match target's suffix at all (diverged/unrelated).
    baseline_text = "* Thu Jan 01 2026 A <a@b.com> - 0.1-1\n- unrelated\n"

    def fake_run(args, **kwargs):
        dbpath = args[args.index("--dbpath") + 1]
        if dbpath == target_dir:
            return _fake_result(stdout=target_text)
        return _fake_result(stdout=baseline_text)

    monkeypatch.setattr(ps.subprocess, "run", fake_run)
    snap = _snapshotter()
    entry = snap._extract_one_changelog(
        "target-tag", "rhel-coreos-10", target_dir, "openshift-clients",
        "1.1-1", "1.2-1", baseline_variant_dir=baseline_dir,
    )
    assert entry["trim_method"] == "version_match"
    assert entry["boundary_found"] is True


def test_extract_falls_back_to_full_dump_with_no_baseline(tmp_path, monkeypatch):
    target_dir = str(tmp_path / "target")
    target_text = "* Fri Aug 01 2026 A <a@b.com> - 1.2-1\n- newest\n"

    monkeypatch.setattr(
        ps.subprocess, "run",
        lambda args, **kwargs: _fake_result(stdout=target_text),
    )
    snap = _snapshotter()
    entry = snap._extract_one_changelog(
        "target-tag", "rhel-coreos-10", target_dir, "openshift-clients",
        "9.9.9-nomatch", "1.2-1", baseline_variant_dir=None,
    )
    assert entry["trim_method"] == "full_dump"
    assert entry["boundary_found"] is False


def test_extract_rejects_path_traversal_package_names(tmp_path, monkeypatch):
    called = []
    monkeypatch.setattr(
        ps.subprocess, "run",
        lambda *a, **k: called.append(1) or _fake_result(),
    )
    snap = _snapshotter()
    entry = snap._extract_one_changelog(
        "target-tag", "rhel-coreos-10", str(tmp_path),
        "../../etc/passwd", "1.0", "1.1",
    )
    assert entry is None
    assert not called, "must not shell out for a suspicious package name"
    assert not (tmp_path / "changelogs").exists()


def test_extract_revalidates_stale_cache(tmp_path, monkeypatch):
    target_dir = str(tmp_path / "target")
    changelog_dir = os.path.join(target_dir, "changelogs")
    cache_path = os.path.join(changelog_dir, "pkg.txt")
    ps._write_text(
        cache_path,
        "# pkg: 1.0-1 -> 1.1-1\n# boundary_found: True\n# trim_method: version_match\n\nold cached body",
    )

    fresh_text = "* Fri Aug 01 2026 A <a@b.com> - 1.3-1\n- fresh\n"
    monkeypatch.setattr(
        ps.subprocess, "run",
        lambda args, **kwargs: _fake_result(stdout=fresh_text),
    )
    snap = _snapshotter()
    # old/new differ from what's cached (1.0-1 -> 1.1-1) - must re-extract.
    entry = snap._extract_one_changelog(
        "target-tag", "rhel-coreos-10", target_dir, "pkg", "1.1-1", "1.3-1",
    )
    assert entry["old"] == "1.1-1" and entry["new"] == "1.3-1"
    with open(cache_path) as f:
        assert "fresh" in f.read()


def test_extract_reuses_matching_cache_without_shelling_out(tmp_path, monkeypatch):
    target_dir = str(tmp_path / "target")
    cache_path = os.path.join(target_dir, "changelogs", "pkg.txt")
    ps._write_text(
        cache_path,
        "# pkg: 1.0-1 -> 1.1-1\n# boundary_found: True\n# trim_method: rpmdb_diff\n\ncached body",
    )

    def fail_run(*a, **k):
        raise AssertionError("must not shell out on a valid cache hit")

    monkeypatch.setattr(ps.subprocess, "run", fail_run)
    snap = _snapshotter()
    entry = snap._extract_one_changelog(
        "target-tag", "rhel-coreos-10", target_dir, "pkg", "1.0-1", "1.1-1",
    )
    assert entry == {
        "variant": "rhel-coreos-10", "package": "pkg",
        "old": "1.0-1", "new": "1.1-1",
        "changelog": "target-tag/rpmdb/rhel-coreos-10/changelogs/pkg.txt",
        "boundary_found": True, "trim_method": "rpmdb_diff",
    }


# ---------------------------------------------------------------------------
# Snapshotter._collect_rpm_changelogs — cumulative fold across chain hops
# ---------------------------------------------------------------------------

def _write_changelog(base_dir, tag, changed_by_variant):
    streams = [
        {"name": variant, "tag": variant, "rpmDiff": {"changed": changed}}
        for variant, changed in changed_by_variant.items()
    ]
    ps._write_json(
        os.path.join(base_dir, tag, "changelog.json"),
        {"nodeImageStreams": streams},
    )


def test_fold_reconstructs_cumulative_diff_across_hops(tmp_path, monkeypatch):
    base_dir = str(tmp_path)
    chain = ["p0", "p1", "p2"]  # p0=target, p2=baseline
    _write_changelog(base_dir, "p0", {
        "rhel-coreos-10": {"openshift-clients": {"old": "1.1-1", "new": "1.2-1"}},
    })
    _write_changelog(base_dir, "p1", {
        "rhel-coreos-10": {
            "kernel": {"old": "5.0-1", "new": "5.0-2"},
            "openshift-clients": {"old": "1.0-1", "new": "1.1-1"},
        },
    })
    rpmdb_data = {"p0": [{"tag": "rhel-coreos-10", "name": "x", "pullspec": "y"}]}

    captured = []
    monkeypatch.setattr(
        ps.Snapshotter, "_extract_one_changelog",
        lambda self, target_tag, variant, variant_dir, pkg, old, new,
               baseline_variant_dir=None: captured.append(
            (variant, pkg, old, new)
        ) or None,
    )
    snap = _snapshotter()
    snap._collect_rpm_changelogs(base_dir, chain, rpmdb_data)

    # openshift-clients changed in both hops: cumulative old=1.0 (first seen),
    # new=1.2 (last seen) - not just the most recent hop's 1.1->1.2.
    assert ("rhel-coreos-10", "openshift-clients", "1.0-1", "1.2-1") in captured
    assert ("rhel-coreos-10", "kernel", "5.0-1", "5.0-2") in captured


def test_fold_skips_packages_that_revert_to_no_net_change(tmp_path, monkeypatch):
    """A package bumped then reverted across hops nets to old == new and
    must not be queued for extraction (or reported as "changed" at all)."""
    base_dir = str(tmp_path)
    chain = ["p0", "p1", "p2"]  # p0=target, p2=baseline
    _write_changelog(base_dir, "p1", {  # p1 vs p2 (baseline): bump
        "rhel-coreos-10": {"kernel": {"old": "5.0-1", "new": "5.0-2"}},
    })
    _write_changelog(base_dir, "p0", {  # p0 vs p1 (target): revert back
        "rhel-coreos-10": {"kernel": {"old": "5.0-2", "new": "5.0-1"}},
    })
    rpmdb_data = {"p0": [{"tag": "rhel-coreos-10", "name": "x", "pullspec": "y"}]}

    captured = []
    monkeypatch.setattr(
        ps.Snapshotter, "_extract_one_changelog",
        lambda self, *a, **k: captured.append(a) or None,
    )
    snap = _snapshotter()
    result = snap._collect_rpm_changelogs(base_dir, chain, rpmdb_data)
    assert captured == []
    assert result == []


def test_fold_aborts_on_unreadable_hop_changelog(tmp_path, monkeypatch):
    """An unreadable hop must not be silently treated as 'no changes' -
    that could misattribute a later hop's old version as the baseline."""
    base_dir = str(tmp_path)
    chain = ["p0", "p1", "p2"]
    _write_changelog(base_dir, "p0", {
        "rhel-coreos-10": {"openshift-clients": {"old": "1.1-1", "new": "1.2-1"}},
    })
    # p1's changelog.json is corrupt/unreadable.
    os.makedirs(os.path.join(base_dir, "p1"), exist_ok=True)
    with open(os.path.join(base_dir, "p1", "changelog.json"), "w") as f:
        f.write("{not valid json")

    rpmdb_data = {"p0": [{"tag": "rhel-coreos-10", "name": "x", "pullspec": "y"}]}
    called = []
    monkeypatch.setattr(
        ps.Snapshotter, "_extract_one_changelog",
        lambda self, *a, **k: called.append(a) or None,
    )
    snap = _snapshotter()
    result = snap._collect_rpm_changelogs(base_dir, chain, rpmdb_data)
    assert result == []
    assert called == []


@pytest.mark.parametrize("kwargs", [
    {"use_sippy": True},
    {"collect_rpmdb": False},
    {"collect_rpm_changelogs": False},
])
def test_fold_gates_are_respected(tmp_path, kwargs):
    base_dir = str(tmp_path)
    chain = ["p0", "p1"]
    _write_changelog(base_dir, "p0", {
        "rhel-coreos-10": {"kernel": {"old": "1.0", "new": "1.1"}},
    })
    rpmdb_data = {"p0": [{"tag": "rhel-coreos-10", "name": "x", "pullspec": "y"}]}
    snap = _snapshotter(**kwargs)
    assert snap._collect_rpm_changelogs(base_dir, chain, rpmdb_data) == []


def test_fold_requires_a_baseline_and_target_rpmdb():
    snap = _snapshotter()
    assert snap._collect_rpm_changelogs("base", ["only-one-tag"], {}) == []
    assert snap._collect_rpm_changelogs("base", ["t", "b"], {}) == []
