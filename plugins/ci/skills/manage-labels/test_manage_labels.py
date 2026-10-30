import manage_labels
from manage_labels import build_update_payload, parse_jira_keys, validate_label

def test_valid_label_no_errors():
    assert validate_label({"label_title": "Infra Failure", "explanation": "x"}) == []

def test_missing_title():
    errs = validate_label({"explanation": "x"})
    assert any("label_title" in e for e in errs)

def test_id_too_long():
    errs = validate_label({"id": "a" * 81, "label_title": "t"})
    assert any("80" in e for e in errs)

def test_bad_hide_context():
    errs = validate_label({"label_title": "t", "hide_display_contexts": ["bogus"]})
    assert any("hide_display_contexts" in e for e in errs)

def test_valid_hide_contexts():
    assert validate_label({"label_title": "t",
                           "hide_display_contexts": ["spyglass", "metrics", "jaq-options"]}) == []

def test_valid_jira_keys():
    assert validate_label({"label_title": "t", "bugs": ["OCPBUGS-12345", "TRT-2896"]}) == []

def test_invalid_jira_key():
    errs = validate_label({"label_title": "t", "bugs": ["ocpbugs-12345"]})
    assert any("Jira issue key" in e for e in errs)

def test_parse_jira_keys_trims_and_deduplicates():
    assert parse_jira_keys(" OCPBUGS-12345,TRT-2896,OCPBUGS-12345 ") == [
        "OCPBUGS-12345", "TRT-2896"]

def test_parse_jira_keys_empty_clears():
    assert parse_jira_keys("") == []


EXISTING = {"id": "ClusterDNSFlake", "label_title": "Cluster DNS Flake",
            "explanation": "old text", "hide_display_contexts": ["spyglass"],
            "bugs": ["OCPBUGS-12345"]}


def test_update_overrides_title():
    out = build_update_payload(EXISTING, title="New Title")
    assert out["label_title"] == "New Title"
    assert out["id"] == "ClusterDNSFlake"


def test_update_preserves_explanation_when_not_passed():
    out = build_update_payload(EXISTING)
    assert out["explanation"] == "old text"


def test_update_empty_string_clears_explanation():
    out = build_update_payload(EXISTING, explanation="")
    assert out["explanation"] == ""


def test_update_hide_contexts_preserved_and_overridden():
    assert build_update_payload(EXISTING)["hide_display_contexts"] == ["spyglass"]
    out = build_update_payload(EXISTING, hide_display_contexts=["metrics"])
    assert out["hide_display_contexts"] == ["metrics"]

def test_update_bugs_preserved_and_overridden():
    assert build_update_payload(EXISTING)["bugs"] == ["OCPBUGS-12345"]
    assert build_update_payload(EXISTING, bugs=["TRT-2896"])["bugs"] == ["TRT-2896"]
    assert build_update_payload(EXISTING, bugs=[])["bugs"] == []

def test_update_sends_complete_arrays_for_legacy_label():
    out = build_update_payload({"id": "Legacy", "label_title": "Legacy"})
    assert out["bugs"] == []
    assert out["hide_display_contexts"] == []


def test_resolve_token_arg_wins_over_env():
    assert manage_labels.resolve_token("argtok", {"SIPPY_TOKEN": "envtok"}) == "argtok"

def test_resolve_token_falls_back_to_env():
    assert manage_labels.resolve_token(None, {"SIPPY_TOKEN": "envtok"}) == "envtok"

def test_resolve_token_none_when_unset():
    assert manage_labels.resolve_token(None, {}) is None
