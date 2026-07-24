from manage_labels import validate_label

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
