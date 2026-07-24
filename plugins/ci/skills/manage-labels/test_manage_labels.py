from manage_labels import validate_label, build_update_payload

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


EXISTING = {"id": "ClusterDNSFlake", "label_title": "Cluster DNS Flake",
            "explanation": "old text", "hide_display_contexts": ["spyglass"]}


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
