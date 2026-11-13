#!/usr/bin/env python3
"""Regression tests for review-comment author authorization."""

import contextlib
import io
import json
import sys
import unittest
from unittest.mock import patch

import check_authorized


class AuthorizationTests(unittest.TestCase):
    def run_main(self, login):
        stdout = io.StringIO()
        argv = ["check_authorized.py", "openshift", "release", login]
        with patch.object(sys, "argv", argv), contextlib.redirect_stdout(stdout):
            with self.assertRaises(SystemExit) as exit_context:
                check_authorized.main()
        return exit_context.exception.code, json.loads(stdout.getvalue())

    @patch("check_authorized.is_org_member", return_value=False)
    @patch(
        "check_authorized.get_authorized_users",
        side_effect=lambda _owner, _repo: set(check_authorized.APPROVED_BOTS),
    )
    def test_redhat_chai_bot_is_an_explicitly_approved_bot(self, owners, member):
        code, result = self.run_main("redhat-chai-bot")

        self.assertEqual(code, 0)
        self.assertEqual(
            result,
            {
                "authorized": True,
                "login": "redhat-chai-bot",
                "reason": "approved_bot",
            },
        )
        owners.assert_called_once_with("openshift", "release")
        member.assert_not_called()

    @patch("check_authorized.is_org_member", return_value=False)
    @patch("check_authorized.get_authorized_users", return_value=set())
    def test_unknown_account_remains_unauthorized(self, owners, member):
        code, result = self.run_main("unknown-reviewer")

        self.assertEqual(code, 1)
        self.assertEqual(result["reason"], "not_authorized")
        owners.assert_called_once_with("openshift", "release")
        member.assert_called_once_with("openshift", "unknown-reviewer")

    @patch("check_authorized.is_org_member")
    @patch("check_authorized.get_authorized_users")
    def test_unapproved_bot_is_rejected_without_external_lookups(self, owners, member):
        code, result = self.run_main("unapproved[bot]")

        self.assertEqual(code, 1)
        self.assertEqual(result["reason"], "ignored_bot")
        owners.assert_not_called()
        member.assert_not_called()

    @patch(
        "check_authorized.get_authorized_users",
        side_effect=check_authorized.OwnersLookupError("lookup failed"),
    )
    def test_owners_lookup_error_remains_fail_safe(self, owners):
        code, result = self.run_main("reviewer")

        self.assertEqual(code, 2)
        self.assertEqual(result["reason"], "owners_lookup_error: lookup failed")
        owners.assert_called_once_with("openshift", "release")

    @patch(
        "check_authorized.is_org_member",
        side_effect=check_authorized.OrgMembershipLookupError("lookup failed"),
    )
    @patch("check_authorized.get_authorized_users", return_value=set())
    def test_org_membership_lookup_error_remains_fail_safe(self, owners, member):
        code, result = self.run_main("reviewer")

        self.assertEqual(code, 2)
        self.assertEqual(result["reason"], "org_membership_error: lookup failed")
        owners.assert_called_once_with("openshift", "release")
        member.assert_called_once_with("openshift", "reviewer")


if __name__ == "__main__":
    unittest.main()
