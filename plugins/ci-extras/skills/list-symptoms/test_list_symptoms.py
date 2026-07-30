from list_symptoms import filter_labels, filter_symptoms, item_url

SYMPTOMS = [
    {"id": "AWSAuthFailure", "summary": "AWS could not validate credentials",
     "matcher_type": "string", "file_pattern": "build-log.txt",
     "match_string": "api error AuthFailure", "label_ids": ["InfraFailure"]},
    {"id": "DNSFlake", "summary": "Cluster DNS lookup flake",
     "matcher_type": "regex", "file_pattern": "**/pods/*.log",
     "match_string": "dns lookup .* timed out", "label_ids": ["ClusterDNSFlake"]},
]

def test_filter_by_search_matches_summary_case_insensitive():
    assert [s["id"] for s in filter_symptoms(SYMPTOMS, search="aws could")] == ["AWSAuthFailure"]

def test_filter_by_search_matches_match_string_and_id():
    assert [s["id"] for s in filter_symptoms(SYMPTOMS, search="dns lookup")] == ["DNSFlake"]
    assert [s["id"] for s in filter_symptoms(SYMPTOMS, search="dnsflake")] == ["DNSFlake"]

def test_filter_by_label():
    assert [s["id"] for s in filter_symptoms(SYMPTOMS, label="InfraFailure")] == ["AWSAuthFailure"]

def test_filter_by_matcher_type():
    assert [s["id"] for s in filter_symptoms(SYMPTOMS, matcher_type="regex")] == ["DNSFlake"]

def test_no_filters_returns_all():
    assert filter_symptoms(SYMPTOMS) == SYMPTOMS

LABELS = [
    {"id": "InfraFailure", "label_title": "Infrastructure Failure",
     "explanation": "Cloud provider or infra problem"},
    {"id": "ClusterDNSFlake", "label_title": "Cluster DNS Flake",
     "explanation": "DNS lookups intermittently time out"},
]

def test_filter_labels_matches_title():
    assert [label["id"] for label in filter_labels(LABELS, search="dns flake")] == ["ClusterDNSFlake"]

def test_filter_labels_matches_id():
    assert [label["id"] for label in filter_labels(LABELS, search="infrafailure")] == ["InfraFailure"]

def test_filter_labels_case_insensitive_explanation():
    assert [label["id"] for label in filter_labels(LABELS, search="CLOUD PROVIDER")] == ["InfraFailure"]

def test_filter_labels_no_search_returns_all():
    assert filter_labels(LABELS) == LABELS

def test_item_url_encodes_reserved_characters():
    assert item_url("symptoms", "a/b c") == (
        "https://sippy.dptools.openshift.org/api/jobs/symptoms/a%2Fb%20c")

def test_item_url_plain_id_unchanged():
    assert item_url("labels", "InfraFailure") == (
        "https://sippy.dptools.openshift.org/api/jobs/labels/InfraFailure")
