import importlib.util
from pathlib import Path


def _load(name, filename):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).resolve().parent / filename)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


rb = _load("render_bug", "render-bug.py")


def _cand(**over):
    c = {"namespace": "openshift-marketplace", "deployment": "marketplace-operator",
         "direction": "raise", "job_runs": 100, "p50_start_mb": 40.0, "p90_start_mb": 45.4,
         "current_mb": 5.0, "request_mb_min": 5.0, "request_mb_max": 5.0,
         "recommended_mb": 49.9, "recommended_mi": 48, "drift_pct": 898.0, "var": False}
    c.update(over)
    return c


def test_fixed_fields_and_key():
    bug = rb.render_bug(_cand(), "5.1", 30)
    assert bug["project"] == "OCPBUGS" and bug["issuetype"] == "Bug"
    assert bug["key"] == "5.1/openshift-marketplace/marketplace-operator"
    assert bug["labels"] == ["issue-for-agent", "ocp-memory-requests", "ai-generated-jira"]
    assert bug["versions"] == [{"name": "5.1"}]
    assert bug["target_version"] == "openshift-5.1"
    assert bug["security"] == {"name": "Red Hat Employee"}


def test_raise_summary_warning_and_sections():
    bug = rb.render_bug(_cand(), "5.1", 30)
    assert "5 -> 49.9 MB (+898%)" in bug["summary"]
    d = bug["description"]
    assert "memory-drift-key: 5.1/openshift-marketplace/marketplace-operator" in d
    assert "49.9 MB (48Mi)" in d
    assert "WARNING" in d                      # raise -> SNO/HyperShift warning
    assert "openshift` GitHub org" in d        # PR rules carried over
    assert "What was found (step 5)" in d


def test_lower_has_no_increase_warning():
    bug = rb.render_bug(_cand(direction="lower", current_mb=256.0, recommended_mb=42.4,
                              recommended_mi=48, drift_pct=-83.4, p90_start_mb=38.5), "5.1", 30)
    assert "256 -> 42.4 MB (-83.4%)" in bug["summary"]
    assert "WARNING" not in bug["description"]


def test_set_direction():
    bug = rb.render_bug(_cand(direction="set", current_mb=0, drift_pct=None,
                              recommended_mb=176.7, recommended_mi=176, p90_start_mb=160.6), "5.1", 30)
    assert bug["summary"].startswith("Set memory request")
    assert "not set (no request configured)" in bug["description"]
    assert "WARNING" in bug["description"]      # set is an increase too


def test_var_note():
    bug = rb.render_bug(_cand(var=True, request_mb_min=50.0, request_mb_max=100.0), "5.1", 30)
    assert "differs across variants" in bug["description"]
