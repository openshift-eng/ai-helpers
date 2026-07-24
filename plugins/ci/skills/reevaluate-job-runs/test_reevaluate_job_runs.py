import pytest
from reevaluate_job_runs import extract_build_id, chunk

def test_plain_numeric_id():
    assert extract_build_id("1856789012345678848") == "1856789012345678848"

def test_prow_url():
    url = ("https://prow.ci.openshift.org/view/gs/test-platform-results/logs/"
           "periodic-ci-openshift-release-master-ci-4.20-e2e-aws-ovn/1856789012345678848")
    assert extract_build_id(url) == "1856789012345678848"

def test_prow_url_trailing_slash():
    assert extract_build_id("https://prow.ci.openshift.org/view/gs/b/logs/job/123456/") == "123456"

def test_invalid_input_raises():
    with pytest.raises(ValueError):
        extract_build_id("not-a-build-id")

def test_chunk_splits_evenly():
    assert chunk([1, 2, 3, 4], 2) == [[1, 2], [3, 4]]

def test_chunk_last_partial():
    assert chunk([1, 2, 3], 2) == [[1, 2], [3]]

def test_chunk_smaller_than_size():
    assert chunk([1], 10) == [[1]]
