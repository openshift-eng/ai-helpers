from fetch_regression_details import build_label_bugs, collect_label_ids, format_summary

JOBS = {
    "job-a": {"pass_sequence": "F", "failed_runs": [], "label_summary": {"InfraFailure": 2}},
    "job-b": {"pass_sequence": "F", "failed_runs": [], "label_summary": {"EtcdSlow": 1, "InfraFailure": 1}},
    "job-c": {"pass_sequence": "F", "failed_runs": []},
}

def test_collect_label_ids_dedupes_and_sorts():
    assert collect_label_ids(JOBS) == ["EtcdSlow", "InfraFailure"]

def test_collect_label_ids_empty():
    assert collect_label_ids({}) == []

def test_build_label_bugs_maps_known_and_unknown():
    labels = [{"id": "InfraFailure", "bugs": ["OCPBUGS-1", "TRT-2"]}, {"id": "Other"}]
    assert build_label_bugs(["EtcdSlow", "InfraFailure"], labels) == {
        "EtcdSlow": [], "InfraFailure": ["OCPBUGS-1", "TRT-2"]}

def _regression(**extra):
    base = {"regression_id": 1, "test_name": "t", "release": "5.0", "base_release": "4.22",
            "component": "c", "capability": "", "opened": "", "closed": None, "status": "open",
            "last_failure": None, "max_failures": 0, "variants": [], "triages": [],
            "test_details_url": "", "api_url": ""}
    base.update(extra)
    return base

def test_summary_shows_label_bugs():
    out = format_summary(_regression(label_bugs={"InfraFailure": ["OCPBUGS-1"], "EtcdSlow": []}))
    assert "InfraFailure: OCPBUGS-1" in out
    assert "EtcdSlow: (none linked)" in out

def test_summary_shows_label_bugs_error():
    assert "Label Bugs: Error fetching - boom" in format_summary(_regression(label_bugs={}, label_bugs_error="boom"))
