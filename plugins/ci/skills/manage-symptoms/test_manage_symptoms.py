from manage_symptoms import (validate_symptom, build_update_payload,
                             parse_label_ids, check_labels_exist)

def test_valid_string_symptom():
    assert validate_symptom({"summary": "AWS auth failure", "matcher_type": "string",
                             "file_pattern": "build-log.txt", "match_string": "AuthFailure",
                             "label_ids": ["InfraFailure"]}) == []

def test_missing_summary():
    errs = validate_symptom({"matcher_type": "string", "file_pattern": "f", "match_string": "x"})
    assert any("summary" in e for e in errs)

def test_bad_matcher_type():
    errs = validate_symptom({"summary": "s", "matcher_type": "glob", "file_pattern": "f"})
    assert any("matcher_type" in e for e in errs)

def test_non_cel_requires_file_pattern():
    errs = validate_symptom({"summary": "s", "matcher_type": "none"})
    assert any("file_pattern" in e for e in errs)

def test_cel_requires_match_string_but_not_file_pattern():
    assert validate_symptom({"summary": "s", "matcher_type": "cel",
                             "match_string": "'A' in labels"}) == []
    errs = validate_symptom({"summary": "s", "matcher_type": "cel"})
    assert any("match_string" in e for e in errs)

def test_string_and_regex_require_match_string():
    errs = validate_symptom({"summary": "s", "matcher_type": "regex", "file_pattern": "f"})
    assert any("match_string" in e for e in errs)

def test_none_matcher_needs_no_match_string():
    assert validate_symptom({"summary": "s", "matcher_type": "none", "file_pattern": "f"}) == []

def test_summary_too_long():
    errs = validate_symptom({"summary": "a" * 201, "matcher_type": "none", "file_pattern": "f"})
    assert any("200" in e for e in errs)


EXISTING = {"id": "AWSAuthFailure", "summary": "AWS could not validate credentials",
            "matcher_type": "string", "file_pattern": "build-log.txt",
            "match_string": "api error AuthFailure", "label_ids": ["InfraFailure"]}


def test_update_overrides_match_string():
    out = build_update_payload(EXISTING, match_string="new pattern")
    assert out["match_string"] == "new pattern"
    assert out["id"] == "AWSAuthFailure"
    assert out["summary"] == "AWS could not validate credentials"


def test_update_preserves_fields_when_not_passed():
    out = build_update_payload(EXISTING)
    assert out == EXISTING


def test_update_empty_string_clears_match_string():
    out = build_update_payload(EXISTING, match_string="")
    assert out["match_string"] == ""


def test_update_label_ids_preserved_and_overridden():
    assert build_update_payload(EXISTING)["label_ids"] == ["InfraFailure"]
    out = build_update_payload(EXISTING, label_ids=["ClusterDNSFlake"])
    assert out["label_ids"] == ["ClusterDNSFlake"]


def test_update_empty_list_clears_label_ids():
    assert build_update_payload(EXISTING, label_ids=[])["label_ids"] == []


def test_parse_label_ids():
    assert parse_label_ids(None) is None
    assert parse_label_ids("") == []
    assert parse_label_ids("A, B,,C ") == ["A", "B", "C"]


def test_check_labels_exist_handles_bad_api_response(monkeypatch):
    import manage_symptoms
    for bad in (None, {"error": "x"}, "oops", [1, 2], ["str"]):
        monkeypatch.setattr(manage_symptoms, "get_json", lambda url, _b=bad: _b)
        errs = check_labels_exist(["InfraFailure"])
        assert errs and "could not verify label IDs" in errs[0]


def test_check_labels_exist_valid_response(monkeypatch):
    import manage_symptoms
    monkeypatch.setattr(manage_symptoms, "get_json",
                        lambda url: [{"id": "InfraFailure"}])
    assert check_labels_exist(["InfraFailure"]) == []
    assert check_labels_exist(["Nope"])
