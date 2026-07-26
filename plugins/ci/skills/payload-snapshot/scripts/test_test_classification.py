#!/usr/bin/env python3
"""Tests for classifying test results as gating, flaking, or informing.

Only one of the three can fail a job and therefore reject a payload:

    flake     -> failed, then passed on retry        -> does NOT gate
    informing -> lifecycle="informing" (stabilizing) -> does NOT gate
    failure   -> failed everywhere, no lifecycle     -> GATES

Counting the other two as failures overstates what could have rejected a
payload, and lets a non-cause drive regression onset.

Run with: pytest test_test_classification.py
"""

import importlib.util
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "payload_snapshot", os.path.join(_HERE, "payload_snapshot.py")
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ps = _load_module()


def _xml(cases: str) -> str:
    return f'<testsuite name="suite" tests="1">{cases}</testsuite>'


def _case(name, *, failed=False, lifecycle=None, skipped=False):
    attrs = f'name="{name}"'
    if lifecycle:
        attrs += f' lifecycle="{lifecycle}"'
    body = ""
    if failed:
        body = "<failure>boom</failure>"
    elif skipped:
        body = "<skipped/>"
    return f"<testcase {attrs}>{body}</testcase>"


def _parse(tmp_path, xml):
    path = tmp_path / "junit.xml"
    path.write_text(xml)
    return ps._parse_junit_xml(str(path))


def _json(tmp_path, xml):
    return ps._test_results_to_json(_parse(tmp_path, xml))


# --------------------------------------------------------------------------
# Flakes
# --------------------------------------------------------------------------

def test_fail_then_pass_is_a_flake(tmp_path):
    entries = _json(tmp_path, _xml(
        _case("t", failed=True) + _case("t")
    ))
    assert [e["status"] for e in entries] == ["flake"]
    assert not ps._is_gating(entries[0])


def test_fail_only_is_a_failure(tmp_path):
    entries = _json(tmp_path, _xml(_case("t", failed=True)))
    assert [e["status"] for e in entries] == ["failed"]
    assert ps._is_gating(entries[0])


def test_multiple_failures_with_one_pass_is_still_a_flake(tmp_path):
    """A flake is one success among any number of failures."""
    entries = _json(tmp_path, _xml(
        _case("t", failed=True) * 3 + _case("t")
    ))
    assert {e["status"] for e in entries} == {"flake"}
    assert not any(ps._is_gating(e) for e in entries)


def test_pass_in_a_different_suite_does_not_clear_a_failure(tmp_path):
    """Same name in two suites is two different tests."""
    xml = (
        '<testsuites>'
        f'<testsuite name="a">{_case("t", failed=True)}</testsuite>'
        f'<testsuite name="b">{_case("t")}</testsuite>'
        '</testsuites>'
    )
    entries = _json(tmp_path, xml)
    assert [e["status"] for e in entries] == ["failed"]
    assert ps._is_gating(entries[0])


def test_skipped_does_not_clear_a_failure(tmp_path):
    entries = _json(tmp_path, _xml(
        _case("t", failed=True) + _case("t", skipped=True)
    ))
    assert [e["status"] for e in entries] == ["failed"]


# --------------------------------------------------------------------------
# Informing
# --------------------------------------------------------------------------

def test_informing_failure_does_not_gate(tmp_path):
    entries = _json(tmp_path, _xml(
        _case("udn", failed=True, lifecycle="informing")
    ))
    assert entries[0]["test_lifecycle"] == "informing"
    assert entries[0]["status"] == "failed"
    assert not ps._is_gating(entries[0])


def test_absent_lifecycle_gates(tmp_path):
    """No lifecycle attribute means the test gates the job."""
    entries = _json(tmp_path, _xml(_case("t", failed=True)))
    assert entries[0]["test_lifecycle"] == "blocking"
    assert ps._is_gating(entries[0])


def test_explicit_blocking_lifecycle_gates(tmp_path):
    entries = _json(tmp_path, _xml(
        _case("t", failed=True, lifecycle="blocking")
    ))
    assert ps._is_gating(entries[0])


def test_informing_flake_is_neither(tmp_path):
    entries = _json(tmp_path, _xml(
        _case("t", failed=True, lifecycle="informing") + _case("t")
    ))
    assert entries[0]["status"] == "flake"
    assert not ps._is_gating(entries[0])


# --------------------------------------------------------------------------
# Counting
# --------------------------------------------------------------------------

def test_only_gating_results_are_counted_as_failures(tmp_path):
    """The mixed case: one real failure among flakes and informing noise."""
    entries = _json(tmp_path, _xml(
        _case("real", failed=True)
        + _case("flaky", failed=True) + _case("flaky")
        + _case("udn1", failed=True, lifecycle="informing")
        + _case("udn2", failed=True, lifecycle="informing")
    ))
    gating = [e for e in entries if ps._is_gating(e)]
    assert [e["name"] for e in gating] == ["real"]
    # One flake entry: the failing attempt, relabelled. The passing attempt
    # is not a result worth recording.
    assert sum(1 for e in entries if e["status"] == "flake") == 1
    assert sum(
        1 for e in entries
        if e["status"] == "failed" and e["test_lifecycle"] == "informing"
    ) == 2


def test_flakes_are_still_recorded_for_visibility(tmp_path):
    """Not gating is not the same as not worth reporting."""
    entries = _json(tmp_path, _xml(
        _case("flaky", failed=True) + _case("flaky")
    ))
    assert entries, "flakes must remain visible in results.json"


def test_passing_tests_are_not_recorded(tmp_path):
    assert _json(tmp_path, _xml(_case("t"))) == []


# --------------------------------------------------------------------------
# Against real aggregated JUnit shapes
# --------------------------------------------------------------------------

REAL_SHAPE = _xml(
    # A real gating invariant, as emitted with no lifecycle attribute.
    _case(
        '[Monitor:legacy-cvo-invariants][bz-config-operator] '
        'clusteroperator/config-operator must go Progressing=True',
        failed=True,
    )
    # A UDN test being stabilized, opted out of gating.
    + _case(
        '[Feature:NetworkSegmentation][ovn-kubernetes-ote][sig-network] '
        'Network Segmentation UserDefinedNetwork CRD Controller',
        failed=True, lifecycle="informing",
    )
)


def test_real_aggregated_shape_splits_correctly(tmp_path):
    entries = _json(tmp_path, REAL_SHAPE)
    gating = [e for e in entries if ps._is_gating(e)]
    assert len(gating) == 1
    assert "config-operator" in gating[0]["name"]
    informing = [e for e in entries if e["test_lifecycle"] == "informing"]
    assert len(informing) == 1
    assert "NetworkSegmentation" in informing[0]["name"]


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
