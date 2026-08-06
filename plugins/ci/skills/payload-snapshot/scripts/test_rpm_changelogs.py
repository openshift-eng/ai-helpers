#!/usr/bin/env python3
"""Tests for the RPM changelog diffs between payloads in the chain.

Run with: pytest test_rpm_changelogs.py
"""

import importlib.util
import os
import sys

import pytest


_HERE = os.path.dirname(os.path.abspath(__file__))


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "payload_snapshot_rpm_changelogs",
        os.path.join(_HERE, "payload_snapshot.py"),
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ps = _load_module()


# ---------------------------------------------------------------------------
# Fake rpm CLI
# ---------------------------------------------------------------------------

def _result(returncode=0, stdout="", stderr=""):
    return type("R", (), {
        "returncode": returncode, "stdout": stdout, "stderr": stderr,
    })()


def _fake_rpm(dbs):
    """A subprocess.run stand-in answering rpm queries from memory.

    `dbs` maps a dbpath to {package: (version, changelog)}.  An unknown
    dbpath answers the way rpm does for one it cannot open.
    """
    def run(cmd, **kwargs):
        assert cmd[0] == "rpm", cmd
        db = dbs.get(cmd[cmd.index("--dbpath") + 1])
        if db is None:
            return _result(1, "", "error: cannot open Packages database")
        if "-qa" in cmd:
            return _result(0, "".join(
                f"{pkg}\t{version}\n" for pkg, (version, _) in sorted(db.items())
            ))
        names = cmd[cmd.index("--qf") + 2:]
        missing = [n for n in names if n not in db]
        return _result(
            1 if missing else 0,
            "".join(f"===PKG {n}\n{db[n][1]}\n" for n in names if n in db),
            "".join(f"package {n} is not installed\n" for n in missing),
        )
    return run


ENTRY_NEW = (
    "* Fri Aug 01 2026 Some Body <a@b.com> - 1.2-1\n"
    "- the new thing\n"
)
ENTRY_MID = (
    "* Wed Jul 30 2026 Some Body <a@b.com> - 1.1-1\n"
    "- the middle thing\n"
)
ENTRY_OLD = (
    "* Mon Jul 20 2026 Some Body <a@b.com> - 1.0-1\n"
    "- the old thing\n"
)


# ---------------------------------------------------------------------------
# _split_changelog_entries / _new_changelog_entries
# ---------------------------------------------------------------------------

def test_split_separates_entries_on_their_header_line():
    entries = ps._split_changelog_entries(
        f"{ENTRY_NEW}\n{ENTRY_MID}\n{ENTRY_OLD}"
    )
    assert len(entries) == 3
    assert entries[0].startswith("* Fri Aug 01 2026")
    assert "the new thing" in entries[0]
    # A body line that merely mentions '*' does not start a new entry.
    assert len(ps._split_changelog_entries(
        "* Fri Aug 01 2026 A <a@b.com> - 1.2-1\n- fixed a * glob\n"
    )) == 1


def test_new_entries_keeps_only_what_the_old_version_lacked():
    new = f"{ENTRY_NEW}\n{ENTRY_MID}\n{ENTRY_OLD}"
    old = f"{ENTRY_MID}\n{ENTRY_OLD}"
    diff = ps._new_changelog_entries(new, old)
    assert "the new thing" in diff
    assert "the middle thing" not in diff
    assert "the old thing" not in diff


def test_new_entries_tolerates_entries_trimmed_off_the_bottom():
    """rpm trims stale changelog entries at build time, so the newer build
    can be missing the oldest entries the older build still carries.

    Regression test: requiring a common *suffix* found no overlap at all
    for e.g. glibc 2.34-274 (159 entries) vs. 2.34-275 (158 entries) and
    dumped the entire changelog instead of the one entry that was added.
    """
    new = f"{ENTRY_NEW}\n{ENTRY_MID}"
    old = f"{ENTRY_MID}\n{ENTRY_OLD}"
    diff = ps._new_changelog_entries(new, old)
    assert "the new thing" in diff
    assert "the middle thing" not in diff


def test_new_entries_is_empty_when_nothing_was_added():
    changelog = f"{ENTRY_NEW}\n{ENTRY_MID}"
    assert ps._new_changelog_entries(changelog, changelog) == ""


def test_new_entries_returns_everything_when_the_old_side_is_empty():
    diff = ps._new_changelog_entries(f"{ENTRY_NEW}\n{ENTRY_MID}", "")
    assert "the new thing" in diff
    assert "the middle thing" in diff


def test_new_entries_returns_everything_when_histories_share_nothing():
    """A rewritten (or unrelated) history degrades to the full changelog.

    Deliberate: showing more history is noise, guessing a cut point that
    is not there would drop real entries.
    """
    diff = ps._new_changelog_entries(
        f"{ENTRY_NEW}\n{ENTRY_MID}",
        "* Thu Jan 01 2026 Other <o@b.com> - 0.1-1\n- unrelated\n",
    )
    assert "the new thing" in diff
    assert "the middle thing" in diff


def test_new_entries_is_empty_for_a_downgrade():
    """The target having *fewer* entries is not a diff to report."""
    assert ps._new_changelog_entries(
        f"{ENTRY_MID}\n{ENTRY_OLD}", f"{ENTRY_NEW}\n{ENTRY_MID}\n{ENTRY_OLD}"
    ) == ""


# ---------------------------------------------------------------------------
# _rpm_versions / _rpm_changelogs
# ---------------------------------------------------------------------------

def test_rpm_versions_reads_every_package(monkeypatch):
    monkeypatch.setattr(ps.subprocess, "run", _fake_rpm({
        "/db": {"kernel": ("5.14.0-1", ""), "bash": ("5.2-3", "")},
    }))
    assert ps._rpm_versions("/db") == {
        "kernel": "5.14.0-1", "bash": "5.2-3",
    }


def test_rpm_versions_collapses_packages_installed_several_times(monkeypatch):
    monkeypatch.setattr(ps.subprocess, "run", lambda cmd, **kw: _result(
        0, "kernel\t5.14.0-2\nkernel\t5.14.0-1\ngarbage-without-a-version\n"
    ))
    assert ps._rpm_versions("/db") == {"kernel": "5.14.0-1, 5.14.0-2"}


def test_rpm_queries_decode_leniently(monkeypatch):
    """Changelog author names are not always valid UTF-8, and a decode
    error must not escape as a ValueError that sinks the whole snapshot."""
    seen = {}
    monkeypatch.setattr(ps.subprocess, "run", lambda cmd, **kw: (
        seen.update(kw) or _result(0, "")
    ))
    ps._rpm_versions("/db")
    assert seen["errors"] == "replace"


def test_rpm_versions_is_empty_when_the_rpmdb_cannot_be_read(monkeypatch):
    monkeypatch.setattr(ps.subprocess, "run", _fake_rpm({}))
    assert ps._rpm_versions("/missing") == {}


def test_rpm_changelogs_splits_the_response_per_package(monkeypatch):
    monkeypatch.setattr(ps.subprocess, "run", _fake_rpm({
        "/db": {"kernel": ("1", ENTRY_NEW), "bash": ("1", ENTRY_OLD)},
    }))
    changelogs = ps._rpm_changelogs("/db", ["kernel", "bash"])
    assert set(changelogs) == {"kernel", "bash"}
    assert "the new thing" in changelogs["kernel"]
    assert "the old thing" in changelogs["bash"]


def test_rpm_changelogs_keeps_what_it_got_when_a_package_is_missing(monkeypatch):
    """rpm exits nonzero for the package it cannot find — the rest is still
    a valid answer and must not be thrown away."""
    monkeypatch.setattr(ps.subprocess, "run", _fake_rpm({
        "/db": {"kernel": ("1", ENTRY_NEW)},
    }))
    assert set(ps._rpm_changelogs("/db", ["kernel", "gone"])) == {"kernel"}


def test_rpm_changelogs_joins_several_records_for_one_package(monkeypatch):
    monkeypatch.setattr(ps.subprocess, "run", lambda cmd, **kw: _result(
        0, f"===PKG kernel\n{ENTRY_NEW}\n===PKG kernel\n{ENTRY_OLD}\n"
    ))
    changelog = ps._rpm_changelogs("/db", ["kernel"])["kernel"]
    assert "the new thing" in changelog and "the old thing" in changelog


def test_rpm_changelogs_does_not_run_rpm_for_an_empty_package_set(monkeypatch):
    def fail(*a, **kw):
        raise AssertionError("must not shell out with nothing to query")

    monkeypatch.setattr(ps.subprocess, "run", fail)
    assert ps._rpm_changelogs("/db", []) == {}


# ---------------------------------------------------------------------------
# RpmChangelogDiffer
# ---------------------------------------------------------------------------

VARIANT = "rhel-coreos-10"
TARGET = "5.0.0-0.nightly-2026-08-03-000000"
MIDDLE = "5.0.0-0.nightly-2026-08-02-000000"
BASELINE = "5.0.0-0.nightly-2026-08-01-000000"


def _dbpath(base_dir, tag, variant=VARIANT):
    return os.path.join(base_dir, tag, "rpmdb", variant)


def _extracted(base_dir, *tags, variant=VARIANT):
    """Create the rpmdb.sqlite files the differ looks for."""
    for tag in tags:
        ps._write_text(
            os.path.join(_dbpath(base_dir, tag, variant), "rpmdb.sqlite"), ""
        )


def _differ(base_dir, older=(MIDDLE, BASELINE), variants=(VARIANT,)):
    return ps.RpmChangelogDiffer(
        base_dir, TARGET, list(older), list(variants), workers=1
    )


def test_diff_reports_changed_new_and_removed_packages(tmp_path, monkeypatch):
    base_dir = str(tmp_path)
    _extracted(base_dir, TARGET, BASELINE)
    monkeypatch.setattr(ps.subprocess, "run", _fake_rpm({
        _dbpath(base_dir, TARGET): {
            "kernel": ("5.14.0-2", f"{ENTRY_NEW}\n{ENTRY_MID}\n{ENTRY_OLD}"),
            "brand-new": ("1.0-1", f"{ENTRY_NEW}\n{ENTRY_OLD}"),
            "untouched": ("3.0-1", ENTRY_OLD),
        },
        _dbpath(base_dir, BASELINE): {
            "kernel": ("5.14.0-1", f"{ENTRY_MID}\n{ENTRY_OLD}"),
            "untouched": ("3.0-1", ENTRY_OLD),
            "dropped": ("2.0-1", ENTRY_OLD),
        },
    }))

    entries = _differ(base_dir, older=[BASELINE]).collect()

    assert entries == [{
        "variant": VARIANT,
        "compared_tag": BASELINE,
        "is_baseline": True,
        "changed": 1,
        "added": 1,
        "removed": 1,
        "changelogs": f"{TARGET}/rpm-changelogs/{VARIANT}/{BASELINE}.md",
        # The baseline diff is inline, so summary.json answers "what
        # changed since the baseline?" without opening the report.
        "diff": {
            "changed": [{
                "package": "kernel",
                "old": "5.14.0-1",
                "new": "5.14.0-2",
                "changelog": ENTRY_NEW.strip(),
            }],
            "added": [{"package": "brand-new", "version": "1.0-1"}],
            "removed": [{"package": "dropped", "version": "2.0-1"}],
        },
    }]

    with open(os.path.join(base_dir, entries[0]["changelogs"])) as f:
        report = f.read()
    assert "### kernel: 5.14.0-1 -> 5.14.0-2" in report
    # Changed package: only what the new version added.
    assert "the new thing" in report
    assert "the middle thing" not in report
    # New package: the whole changelog.
    assert "### brand-new: 1.0-1" in report
    assert report.count("the old thing") == 1  # brand-new's, not untouched's
    # Removed package: recorded, but no changelog.
    assert f"- dropped: 2.0-1 (in {BASELINE}" in report
    assert "untouched" not in report


def test_diff_notes_a_rebuild_that_added_no_changelog_entry(tmp_path, monkeypatch):
    base_dir = str(tmp_path)
    _extracted(base_dir, TARGET, BASELINE)
    monkeypatch.setattr(ps.subprocess, "run", _fake_rpm({
        _dbpath(base_dir, TARGET): {"kernel": ("5.14.0-2", ENTRY_OLD)},
        _dbpath(base_dir, BASELINE): {"kernel": ("5.14.0-1", ENTRY_OLD)},
    }))
    entries = _differ(base_dir, older=[BASELINE]).collect()
    assert entries[0]["changed"] == 1
    with open(os.path.join(base_dir, entries[0]["changelogs"])) as f:
        assert "rebuilt without adding a changelog entry" in f.read()


def test_diff_writes_one_report_per_older_payload(tmp_path, monkeypatch):
    """Each older payload is compared against the target on its own — the
    chain is not folded hop by hop."""
    base_dir = str(tmp_path)
    _extracted(base_dir, TARGET, MIDDLE, BASELINE)
    monkeypatch.setattr(ps.subprocess, "run", _fake_rpm({
        _dbpath(base_dir, TARGET): {
            "kernel": ("5.14.0-3", f"{ENTRY_NEW}\n{ENTRY_MID}\n{ENTRY_OLD}"),
        },
        _dbpath(base_dir, MIDDLE): {
            "kernel": ("5.14.0-2", f"{ENTRY_MID}\n{ENTRY_OLD}"),
        },
        _dbpath(base_dir, BASELINE): {
            "kernel": ("5.14.0-1", ENTRY_OLD),
        },
    }))

    entries = _differ(base_dir).collect()

    assert [(e["compared_tag"], e["is_baseline"]) for e in entries] == [
        (MIDDLE, False), (BASELINE, True),
    ]
    # Only the oldest comparison inlines its diff — the intermediate hops
    # are a subset of it and would grow summary.json by the whole chain.
    assert "diff" not in entries[0]
    assert entries[1]["diff"]["changed"][0]["package"] == "kernel"
    with open(os.path.join(base_dir, entries[0]["changelogs"])) as f:
        vs_middle = f.read()
    with open(os.path.join(base_dir, entries[1]["changelogs"])) as f:
        vs_baseline = f.read()
    assert "the middle thing" not in vs_middle
    assert "the middle thing" in vs_baseline


def test_diff_ignores_older_payloads_without_this_variant(tmp_path, monkeypatch):
    """A variant that only exists in the newer payload (a RHEL major bump
    adds one) has nothing to diff against, so it is left alone rather than
    reported as hundreds of new packages."""
    base_dir = str(tmp_path)
    _extracted(base_dir, TARGET, BASELINE)
    _extracted(base_dir, TARGET, variant="rhel-coreos-11")
    monkeypatch.setattr(ps.subprocess, "run", _fake_rpm({
        _dbpath(base_dir, TARGET): {"kernel": ("2", ENTRY_NEW)},
        _dbpath(base_dir, TARGET, "rhel-coreos-11"): {
            "kernel": ("2", ENTRY_NEW),
        },
        _dbpath(base_dir, BASELINE): {"kernel": ("1", ENTRY_OLD)},
    }))

    entries = _differ(
        base_dir, older=[BASELINE], variants=[VARIANT, "rhel-coreos-11"]
    ).collect()

    assert [e["variant"] for e in entries] == [VARIANT]
    assert not os.path.exists(
        os.path.join(base_dir, TARGET, "rpm-changelogs", "rhel-coreos-11")
    )


def test_diff_skips_a_variant_whose_target_rpmdb_is_unreadable(tmp_path, monkeypatch):
    base_dir = str(tmp_path)
    _extracted(base_dir, TARGET, BASELINE)
    monkeypatch.setattr(ps.subprocess, "run", _fake_rpm({
        _dbpath(base_dir, BASELINE): {"kernel": ("1", ENTRY_OLD)},
    }))
    assert _differ(base_dir, older=[BASELINE]).collect() == []


def test_diff_skips_an_older_payload_whose_rpmdb_is_unreadable(tmp_path, monkeypatch):
    base_dir = str(tmp_path)
    _extracted(base_dir, TARGET, MIDDLE, BASELINE)
    monkeypatch.setattr(ps.subprocess, "run", _fake_rpm({
        _dbpath(base_dir, TARGET): {"kernel": ("2", ENTRY_NEW)},
        _dbpath(base_dir, BASELINE): {"kernel": ("1", ENTRY_OLD)},
    }))
    entries = _differ(base_dir).collect()
    assert [e["compared_tag"] for e in entries] == [BASELINE]


def test_diff_promotes_the_oldest_readable_comparison_to_baseline(
    tmp_path, monkeypatch
):
    """When the chain baseline's rpmdb cannot be read, the next-oldest
    readable comparison takes over is_baseline/diff — flagged so a
    consumer can tell the diff does not reach the actual chain start."""
    base_dir = str(tmp_path)
    _extracted(base_dir, TARGET, MIDDLE, BASELINE)
    monkeypatch.setattr(ps.subprocess, "run", _fake_rpm({
        _dbpath(base_dir, TARGET): {"kernel": ("3", ENTRY_NEW)},
        _dbpath(base_dir, MIDDLE): {"kernel": ("2", ENTRY_OLD)},
    }))
    entries = _differ(base_dir).collect()
    assert [e["compared_tag"] for e in entries] == [MIDDLE]
    assert entries[0]["is_baseline"] is True
    assert "diff" in entries[0]
    assert entries[0]["baseline_rpmdb_missing"] is True


def test_diff_keeps_going_when_one_variant_fails(tmp_path, monkeypatch):
    """The diffs are derived, best-effort data collected before summary.json
    is written — one broken variant must not abort the whole snapshot."""
    base_dir = str(tmp_path)
    _extracted(base_dir, TARGET, BASELINE)
    _extracted(base_dir, TARGET, BASELINE, variant="rhel-coreos")
    monkeypatch.setattr(ps.subprocess, "run", _fake_rpm({
        _dbpath(base_dir, TARGET): {"kernel": ("2", ENTRY_NEW)},
        _dbpath(base_dir, BASELINE): {"kernel": ("1", ENTRY_OLD)},
        _dbpath(base_dir, TARGET, "rhel-coreos"): {"kernel": ("2", ENTRY_NEW)},
        _dbpath(base_dir, BASELINE, "rhel-coreos"): {"kernel": ("1", ENTRY_OLD)},
    }))
    differ = _differ(base_dir, older=[BASELINE],
                     variants=["rhel-coreos", VARIANT])
    real_diff_variant = differ._diff_variant
    differ._diff_variant = lambda variant: (
        (_ for _ in ()).throw(RuntimeError("boom"))
        if variant == "rhel-coreos" else real_diff_variant(variant)
    )

    entries = differ.collect()

    assert [e["variant"] for e in entries] == [VARIANT]


# ---------------------------------------------------------------------------
# Cross-links from the per-payload data to the reports
# ---------------------------------------------------------------------------

def _changelog_entry(variant, compared_tag):
    return {
        "variant": variant, "compared_tag": compared_tag,
        "is_baseline": compared_tag == BASELINE,
        "changed": 1, "added": 0, "removed": 0,
        "changelogs":
            f"{TARGET}/rpm-changelogs/{variant}/{compared_tag}.md",
    }


def test_target_raw_jsons_point_at_the_predecessor_report(tmp_path):
    """payload.json and changelog.json show the release controller's RPM
    diff without changelog text, so they must say where the text is."""
    base_dir = str(tmp_path)
    for name in ("payload.json", "changelog.json"):
        ps._write_json(os.path.join(base_dir, TARGET, name),
                       {"nodeImageStreams": [], "_source": "rc"})

    _snapshotter()._link_rpm_changelogs(
        base_dir, [TARGET, MIDDLE, BASELINE],
        [_changelog_entry(VARIANT, MIDDLE), _changelog_entry(VARIANT, BASELINE)],
    )

    for name in ("payload.json", "changelog.json"):
        data = ps._read_json(os.path.join(base_dir, TARGET, name))
        assert data["_source"] == "rc", "must not clobber the payload data"
        # Only the pairing these files describe: target vs. predecessor,
        # by a path relative to the payload directory they live in.
        assert data["_rpm_changelogs"] == [{
            "variant": VARIANT,
            "compared_tag": MIDDLE,
            "changelogs": f"rpm-changelogs/{VARIANT}/{MIDDLE}.md",
        }]


def test_raw_jsons_are_left_alone_without_a_matching_report(tmp_path):
    base_dir = str(tmp_path)
    path = os.path.join(base_dir, TARGET, "payload.json")
    ps._write_json(path, {"_source": "rc"})
    snap = _snapshotter()

    snap._link_rpm_changelogs(base_dir, [TARGET], [])          # no chain
    snap._link_rpm_changelogs(base_dir, [TARGET, MIDDLE], [])  # no reports
    snap._link_rpm_changelogs(  # reports, but not for the predecessor
        base_dir, [TARGET, MIDDLE, BASELINE],
        [_changelog_entry(VARIANT, BASELINE)],
    )

    assert ps._read_json(path) == {"_source": "rc"}


def test_payload_entries_point_at_their_report(tmp_path):
    base_dir = str(tmp_path)
    generator = ps.SummaryGenerator(
        base_dir, [TARGET, BASELINE], TARGET,
        ps.PayloadTag.parse(TARGET),
        rpm_changelogs=[_changelog_entry(VARIANT, BASELINE)],
    )

    by_tag = {e["tag"]: e for e in generator._build_payload_entries()}

    assert by_tag[BASELINE]["rpm_changelogs"] == [{
        "variant": VARIANT,
        "changelogs": f"{TARGET}/rpm-changelogs/{VARIANT}/{BASELINE}.md",
    }]
    # The target is what every report is anchored on, so it has none.
    assert "rpm_changelogs" not in by_tag[TARGET]


# ---------------------------------------------------------------------------
# Snapshotter wiring
# ---------------------------------------------------------------------------

def _snapshotter(**kwargs):
    return ps.Snapshotter(
        ps.PayloadTag.parse("5.0.0-0.nightly-2026-08-03-000000"), **kwargs
    )


RPMDB_DATA = {TARGET: [{"tag": VARIANT, "name": "n", "pullspec": "p"}]}


@pytest.mark.parametrize("kwargs,chain,rpmdb_data", [
    ({"collect_rpm_changelogs": False}, [TARGET, BASELINE], RPMDB_DATA),
    ({}, [TARGET], RPMDB_DATA),          # no baseline to diff against
    ({}, [TARGET, BASELINE], {}),        # rpmdb extraction was skipped
])
def test_collect_is_skipped_without_anything_to_diff(kwargs, chain, rpmdb_data,
                                                     monkeypatch):
    def fail(*a, **kw):
        raise AssertionError("must not shell out to rpm")

    monkeypatch.setattr(ps.subprocess, "run", fail)
    snap = _snapshotter(**kwargs)
    assert snap._collect_rpm_changelogs("base", chain, rpmdb_data) == []


def test_collect_diffs_the_target_against_the_rest_of_the_chain(tmp_path,
                                                                monkeypatch):
    base_dir = str(tmp_path)
    _extracted(base_dir, TARGET, MIDDLE, BASELINE)
    monkeypatch.setattr(ps.subprocess, "run", _fake_rpm({
        _dbpath(base_dir, tag): {"kernel": (version, ENTRY_NEW)}
        for tag, version in [(TARGET, "3"), (MIDDLE, "2"), (BASELINE, "1")]
    }))
    entries = _snapshotter()._collect_rpm_changelogs(
        base_dir, [TARGET, MIDDLE, BASELINE], RPMDB_DATA
    )
    assert [e["compared_tag"] for e in entries] == [MIDDLE, BASELINE]


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
