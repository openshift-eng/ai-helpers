#!/usr/bin/env python3
"""Tests for filter_optional_checks.py"""

import unittest

from filter_optional_checks import (
    annotate_checks,
    check_is_optional,
    filter_checks,
    gcs_path_from_link,
    is_optional_prowjob,
    is_tide,
    prowjob_json_urls,
)

PROW_LINK = (
    "https://prow.ci.openshift.org/view/gs/test-platform-results/"
    "pr-logs/pull/openshift_sippy/3816/pull-ci-openshift-sippy-main-lint/123"
)
OPTIONAL_LINK = (
    "https://prow.ci.openshift.org/view/gs/test-platform-results/"
    "pr-logs/pull/openshift_sippy/3816/pull-ci-openshift-sippy-main-agentic-staging/456"
)

CHECKS = [
    {"name": "ci/prow/lint", "state": "FAILURE", "bucket": "fail", "link": PROW_LINK},
    {"name": "ci/prow/agentic-staging", "state": "FAILURE", "bucket": "fail", "link": OPTIONAL_LINK},
    {"name": "ci/prow/verify", "state": "SUCCESS", "bucket": "pass", "link": PROW_LINK},
    {"name": "tide", "state": "FAILURE", "bucket": "fail", "link": ""},
    {"name": "CodeRabbit", "state": "FAILURE", "bucket": "fail", "link": "https://coderabbit.example"},
]


def fake_fetch(url: str):
    if "agentic-staging" in url:
        return {"metadata": {"labels": {"prow.k8s.io/is-optional": "true"}}, "spec": {}}
    if "pull-ci-openshift-sippy-main-lint" in url:
        return {"spec": {}}
    return None


class FilterOptionalChecksTest(unittest.TestCase):
    def test_gcs_path_from_prow_link(self):
        self.assertEqual(
            gcs_path_from_link(PROW_LINK),
            "test-platform-results/pr-logs/pull/openshift_sippy/3816/"
            "pull-ci-openshift-sippy-main-lint/123",
        )

    def test_gcs_path_from_gcsweb_link(self):
        link = (
            "https://gcsweb-ci.apps.ci.l2s4.p1.openshiftapps.com/gcs/"
            "test-platform-results/pr-logs/pull/foo/1/job/99/"
        )
        self.assertEqual(
            gcs_path_from_link(link),
            "test-platform-results/pr-logs/pull/foo/1/job/99",
        )

    def test_gcs_path_rejects_non_prow(self):
        self.assertIsNone(gcs_path_from_link("https://coderabbit.example"))
        self.assertIsNone(gcs_path_from_link(""))

    def test_prowjob_json_urls(self):
        urls = prowjob_json_urls(PROW_LINK)
        self.assertEqual(len(urls), 2)
        self.assertTrue(urls[0].endswith("/prowjob.json"))
        self.assertIn("gcsweb-ci", urls[0])
        self.assertIn("storage.googleapis.com", urls[1])

    def test_is_optional_prowjob(self):
        self.assertTrue(is_optional_prowjob({"spec": {"optional": True}}))
        self.assertTrue(is_optional_prowjob(
            {"metadata": {"labels": {"prow.k8s.io/is-optional": "true"}}, "spec": {}}
        ))
        self.assertFalse(is_optional_prowjob({"spec": {"optional": False}}))
        self.assertFalse(is_optional_prowjob(
            {"metadata": {"labels": {"prow.k8s.io/is-optional": "false"}}, "spec": {}}
        ))
        self.assertFalse(is_optional_prowjob({"spec": {}}))
        self.assertFalse(is_optional_prowjob({}))

    def test_check_is_optional(self):
        self.assertTrue(check_is_optional(OPTIONAL_LINK, fetch=fake_fetch))
        self.assertFalse(check_is_optional(PROW_LINK, fetch=fake_fetch))
        self.assertIsNone(check_is_optional("https://coderabbit.example", fetch=fake_fetch))

    def test_optional_only_failures_are_not_actionable(self):
        checks = [
            {
                "name": "ci/prow/agentic-staging",
                "state": "FAILURE",
                "bucket": "fail",
                "link": OPTIONAL_LINK,
            }
        ]
        self.assertEqual(filter_checks(checks, fetch=fake_fetch), [])

    def test_keeps_required_drops_optional_and_tide(self):
        result = filter_checks(CHECKS, fetch=fake_fetch)
        names = [c["name"] for c in result]
        self.assertEqual(names, ["ci/prow/lint", "CodeRabbit"])

    def test_unknown_prowjob_is_kept(self):
        unknown = (
            "https://prow.ci.openshift.org/view/gs/test-platform-results/"
            "pr-logs/pull/foo/1/job/1"
        )
        checks = [
            {"name": "ci/prow/job", "state": "FAILURE", "bucket": "fail", "link": unknown}
        ]
        result = filter_checks(checks, fetch=fake_fetch)
        self.assertEqual([c["name"] for c in result], ["ci/prow/job"])

    def test_annotate_keeps_optional_and_marks_them(self):
        result = annotate_checks(CHECKS, fetch=fake_fetch)
        by_name = {c["name"]: c for c in result}
        self.assertEqual(set(by_name), {"ci/prow/lint", "ci/prow/agentic-staging", "CodeRabbit"})
        self.assertTrue(by_name["ci/prow/agentic-staging"]["optional"])
        self.assertFalse(by_name["ci/prow/lint"]["optional"])
        self.assertNotIn("optional", by_name["CodeRabbit"])

    def test_is_tide(self):
        self.assertTrue(is_tide("tide"))
        self.assertTrue(is_tide("ci/prow/tide"))
        self.assertFalse(is_tide("ci/prow/lint"))


if __name__ == "__main__":
    unittest.main()
