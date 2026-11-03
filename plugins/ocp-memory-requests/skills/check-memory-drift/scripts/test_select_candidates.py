import importlib.util
from decimal import Decimal
from pathlib import Path


def _load(name, filename):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).resolve().parent / filename)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


sc = _load("select_candidates", "select-candidates.py")


def _row(dep, ns, runs, p90, req, req_min=None, req_max=None, p50=0):
    return {"Deployment": dep, "Namespace": ns, "job_runs": runs,
            "p90_start_mb": p90, "p50_start_mb": p50, "request_mb": req,
            "request_mb_min": req if req_min is None else req_min,
            "request_mb_max": req if req_max is None else req_max}


def test_round1_half_away_from_zero():
    assert sc.round1("42.35") == Decimal("42.4")
    assert sc.round1(45.4 * 1.10) == Decimal("49.9")
    assert sc.round1("-83.4375") == Decimal("-83.4")


def test_mb_to_mi_roundup():
    assert sc.mb_to_mi_roundup(49.9) == 48    # 47.6 -> next 16
    assert sc.mb_to_mi_roundup(132.0) == 128  # 125.9 -> next 16
    assert sc.mb_to_mi_roundup(176.7) == 176  # 168.5 -> next 16


def test_raise_candidate_and_recommendation():
    [c] = sc.select_candidates([_row("marketplace-operator", "openshift-marketplace", 100, 45.4, 5)],
                               threshold_pct=30, min_runs=100)
    assert c["direction"] == "raise"
    assert c["recommended_mb"] == 49.9
    assert c["recommended_mi"] == 48
    assert c["drift_pct"] == 898.0
    assert c["var"] is False


def test_lower_candidate():
    [c] = sc.select_candidates([_row("image-registry", "openshift-image-registry", 100, 38.5, 256)],
                               threshold_pct=30, min_runs=100)
    assert c["direction"] == "lower"
    assert c["recommended_mb"] == 42.4
    assert c["drift_pct"] == -83.4


def test_threshold_is_strictly_greater():
    rows = [_row("dep-at", "openshift-dep-at", 100, 130.0, 110),      # drift exactly 30.0
            _row("dep-above", "openshift-dep-above", 100, 120.0, 100)]  # drift 32.0
    deps = {c["deployment"] for c in sc.select_candidates(rows, 30, 100)}
    assert deps == {"dep-above"}


def test_min_runs_floor():
    assert sc.select_candidates([_row("x", "openshift-x", 50, 500, 5)], 30, 100) == []


def test_zero_request_becomes_set():
    [c] = sc.select_candidates([_row("etcd-operator", "openshift-etcd-operator", 100, 160.6, 0)], 30, 100)
    assert c["direction"] == "set"
    assert c["drift_pct"] is None
    assert c["recommended_mi"] == 176


def test_var_flag():
    [c] = sc.select_candidates([_row("kas", "openshift-kas", 100, 212.3, 100, req_min=50, req_max=100)], 30, 100)
    assert c["var"] is True


def test_ordering_set_first_then_by_abs_drift():
    rows = [_row("small", "openshift-small", 100, 150, 100),   # +65%
            _row("zero", "openshift-zero", 100, 160.6, 0),     # set
            _row("big", "openshift-big", 100, 1000, 100)]      # +1000%
    order = [c["deployment"] for c in sc.select_candidates(rows, 30, 100)]
    assert order == ["zero", "big", "small"]


def test_string_inputs_coerced_and_empty():
    [c] = sc.select_candidates([_row("d", "openshift-d", "100", "45.4", "5")], 30, 100)
    assert c["direction"] == "raise"
    assert sc.select_candidates([], 30, 100) == []
