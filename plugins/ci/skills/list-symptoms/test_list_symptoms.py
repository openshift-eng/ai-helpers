from list_symptoms import filter_symptoms

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
