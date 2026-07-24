import pytest
from diagnose_job_run import parse_prow_url, normalize_label_entry, classify_response

def test_parse_standard_prow_url():
    url = ("https://prow.ci.openshift.org/view/gs/test-platform-results/logs/"
           "periodic-ci-openshift-release-master-ci-4.20-e2e-aws-ovn/1856789012345678848")
    bucket, path, build_id = parse_prow_url(url)
    assert bucket == "test-platform-results"
    assert path == ("logs/periodic-ci-openshift-release-master-ci-4.20-e2e-aws-ovn/"
                    "1856789012345678848")
    assert build_id == "1856789012345678848"

def test_parse_pr_job_url():
    url = ("https://prow.ci.openshift.org/view/gs/test-platform-results/pr-logs/pull/"
           "openshift_origin/29000/pull-ci-openshift-origin-master-e2e/1856789012345678848/")
    bucket, path, build_id = parse_prow_url(url)
    assert bucket == "test-platform-results"
    assert build_id == "1856789012345678848"
    assert path.startswith("pr-logs/pull/") and path.endswith(build_id)

def test_rejects_non_prow_url():
    with pytest.raises(ValueError):
        parse_prow_url("https://example.com/foo")

def test_parse_url_with_query_string_and_fragment():
    url = ("https://prow.ci.openshift.org/view/gs/test-platform-results/logs/"
           "some-job/1856789012345678848?tab=x#top")
    bucket, path, build_id = parse_prow_url(url)
    assert bucket == "test-platform-results"
    assert build_id == "1856789012345678848"
    assert path == "logs/some-job/1856789012345678848"

def test_classify_response_login_page():
    _, err = classify_response("<html><body>Please Log in to continue</body></html>")
    assert err and "oc-auth" in err

def test_classify_response_other_html():
    _, err = classify_response("<html>504 Gateway Time-out</html>")
    assert err and "HTML error page" in err

def test_classify_response_non_json_plaintext():
    _, err = classify_response("service unavailable")
    assert err and "non-JSON" in err

def test_classify_response_valid_json():
    parsed, err = classify_response('{"results": [{"status": "success"}]}')
    assert err is None
    assert parsed["results"][0]["status"] == "success"

WRAPPED_ENTRY = {
    "symptom_label_v1": {
        "symptom": {"id": "KubeletVersionSkew1355", "summary": "kubelet version skew 1.35.5",
                    "matcher_type": "string",
                    "file_pattern": "artifacts/*e2e*/gather-extra/artifacts/nodes.json",
                    "match_string": "\"kubeletVersion\": \"v1.35.3\"",
                    "label_ids": ["KubeletVersion1353"]},
        "label": {"id": "KubeletVersion1353", "label_title": "kubeletVersion 1.35.3",
                  "explanation": ""},
        "file_match": "artifacts/e2e-metal/gather-extra/artifacts/nodes.json",
        "text_match": "  \"kubeletVersion\": \"v1.35.3\",",
    }
}

def test_normalize_wrapped_symptom_label_v1():
    m = normalize_label_entry(WRAPPED_ENTRY)
    assert m["label_id"] == "KubeletVersion1353"
    assert m["symptom_id"] == "KubeletVersionSkew1355"
    assert m["label"]["label_title"] == "kubeletVersion 1.35.3"
    assert m["symptom"]["matcher_type"] == "string"
    assert m["file_match"].endswith("nodes.json")
    assert "v1.35.3" in m["text_match"]
    assert m["raw"] is WRAPPED_ENTRY

def test_normalize_flat_fallback():
    m = normalize_label_entry({"label_id": "InfraFailure", "symptom_id": "AWSAuth"})
    assert m["label_id"] == "InfraFailure"
    assert m["symptom_id"] == "AWSAuth"

def test_normalize_flat_fallback_id_key():
    assert normalize_label_entry({"id": "InfraFailure"})["label_id"] == "InfraFailure"

def test_normalize_garbage_returns_empty_match():
    m = normalize_label_entry("not-a-dict")
    assert m["label_id"] is None and m["symptom_id"] is None
