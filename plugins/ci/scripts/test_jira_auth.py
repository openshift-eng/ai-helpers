import base64
import contextlib
import io
import json
import os
import sys
import unittest
import urllib.error
import urllib.parse
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import jira_auth

CLOUD = "11111111-2222-3333-4444-555555555555"
SA_ENV = {"JIRA_CLIENT_ID": "cid", "JIRA_CLIENT_SECRET": "s3cret", "JIRA_CLOUD_ID": CLOUD}
PAT_ENV = {"JIRA_USERNAME": "u@example.com", "JIRA_API_TOKEN": "pat"}


class Resp:
    def __init__(self, body, status=200):
        self._body = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.status = status

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class ResolveTests(unittest.TestCase):
    def test_api_token_mode(self):
        auth = jira_auth.resolve(env=PAT_ENV)
        self.assertEqual(auth.mode, jira_auth.MODE_API_TOKEN)
        self.assertEqual(auth.url("/rest/api/3/myself"), "https://redhat.atlassian.net/rest/api/3/myself")
        expected = base64.b64encode(b"u@example.com:pat").decode()
        self.assertEqual(auth.authorization(), "Basic " + expected)

    def test_service_account_mode_uses_gateway(self):
        auth = jira_auth.resolve(env=SA_ENV)
        self.assertEqual(auth.mode, jira_auth.MODE_SERVICE_ACCOUNT)
        self.assertEqual(auth.url("rest/api/3/myself"),
                         "https://api.atlassian.com/ex/jira/%s/rest/api/3/myself" % CLOUD)

    def test_service_account_wins_over_api_token_env(self):
        auth = jira_auth.resolve(env=dict(PAT_ENV, **SA_ENV))
        self.assertEqual(auth.mode, jira_auth.MODE_SERVICE_ACCOUNT)

    def test_incomplete_service_account_does_not_fall_back(self):
        env = dict(PAT_ENV, JIRA_CLIENT_ID="cid")
        with self.assertRaises(jira_auth.JiraAuthError) as cm:
            jira_auth.resolve(env=env)
        self.assertIn("JIRA_CLIENT_SECRET", str(cm.exception))
        self.assertIn("JIRA_CLOUD_ID", str(cm.exception))

    def test_cloud_id_must_be_uuid(self):
        with self.assertRaises(jira_auth.JiraAuthError):
            jira_auth.resolve(env=dict(SA_ENV, JIRA_CLOUD_ID="redhat"))

    def test_cloud_id_alone_keeps_api_token_mode(self):
        auth = jira_auth.resolve(env=dict(PAT_ENV, JIRA_CLOUD_ID=CLOUD))
        self.assertEqual(auth.mode, jira_auth.MODE_API_TOKEN)

    def test_explicit_username_and_token_force_api_token(self):
        auth = jira_auth.resolve(username="x", token="y", env=SA_ENV)
        self.assertEqual(auth.mode, jira_auth.MODE_API_TOKEN)
        auth = jira_auth.resolve(token="y", env=dict(SA_ENV, JIRA_USERNAME="u"))
        self.assertEqual(auth.mode, jira_auth.MODE_API_TOKEN)

    def test_missing_credentials(self):
        with self.assertRaises(jira_auth.JiraAuthError) as cm:
            jira_auth.resolve(env={"JIRA_USERNAME": "u"})
        self.assertIn("JIRA_API_TOKEN", str(cm.exception))


class TokenTests(unittest.TestCase):
    def test_token_request_and_bearer_header(self):
        seen = []

        def urlopen(req, timeout=None):
            seen.append(req)
            return Resp({"access_token": "tok", "expires_in": 3600})

        auth = jira_auth.resolve(env=SA_ENV)
        with mock.patch("urllib.request.urlopen", side_effect=urlopen):
            self.assertEqual(auth.authorization(), "Bearer tok")
            self.assertEqual(auth.authorization(), "Bearer tok")
        self.assertEqual(len(seen), 1, "a valid token must be reused")
        req = seen[0]
        self.assertEqual(req.full_url, "https://auth.atlassian.com/oauth/token")
        self.assertEqual(req.get_method(), "POST")
        self.assertEqual(urllib.parse.parse_qs(req.data.decode()), {
            "grant_type": ["client_credentials"], "client_id": ["cid"], "client_secret": ["s3cret"]})

    def test_expired_token_is_renewed(self):
        tokens = iter([{"access_token": "one", "expires_in": 30}, {"access_token": "two", "expires_in": 3600}])
        auth = jira_auth.resolve(env=SA_ENV)
        with mock.patch("urllib.request.urlopen", side_effect=lambda *a, **k: Resp(next(tokens))):
            self.assertEqual(auth.authorization(), "Bearer one")
            self.assertEqual(auth.authorization(), "Bearer two")

    def test_rejected_credentials_do_not_leak_secret(self):
        def urlopen(req, timeout=None):
            raise urllib.error.HTTPError(req.full_url, 401, "Unauthorized", {}, io.BytesIO(b"s3cret"))

        auth = jira_auth.resolve(env=SA_ENV)
        with mock.patch("urllib.request.urlopen", side_effect=urlopen):
            with self.assertRaises(jira_auth.JiraAuthError) as cm:
                auth.authorization()
        self.assertIn("401", str(cm.exception))
        self.assertNotIn("s3cret", str(cm.exception))

    def test_rejected_credentials_report_oauth_error_code(self):
        def urlopen(req, timeout=None):
            body = io.BytesIO(b'{"error": "invalid_client", "error_description": "s3cret"}')
            raise urllib.error.HTTPError(req.full_url, 400, "Bad Request", {}, body)

        auth = jira_auth.resolve(env=SA_ENV)
        with mock.patch("urllib.request.urlopen", side_effect=urlopen):
            with self.assertRaises(jira_auth.JiraAuthError) as cm:
                auth.authorization()
        self.assertIn("invalid_client", str(cm.exception))
        self.assertNotIn("s3cret", str(cm.exception))

    def test_response_without_access_token(self):
        auth = jira_auth.resolve(env=SA_ENV)
        with mock.patch("urllib.request.urlopen", return_value=Resp({"error": "nope"})):
            with self.assertRaises(jira_auth.JiraAuthError):
                auth.authorization()


class CliTests(unittest.TestCase):
    def run_main(self, argv, env, urlopen):
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.dict(os.environ, env, clear=True), \
             mock.patch("urllib.request.urlopen", side_effect=urlopen), \
             contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = jira_auth.main(argv)
        return rc, out.getvalue(), err.getvalue()

    def test_check_reports_account_without_token(self):
        def urlopen(req, timeout=None):
            if req.full_url == jira_auth.OAUTH_TOKEN_URL:
                return Resp({"access_token": "tok", "expires_in": 3600})
            self.assertEqual(req.get_header("Authorization"), "Bearer tok")
            return Resp({"accountId": "abc", "displayName": "Bot"})

        rc, out, _ = self.run_main(["check"], SA_ENV, urlopen)
        self.assertEqual(rc, 0)
        self.assertEqual(json.loads(out)["account_id"], "abc")
        self.assertEqual(json.loads(out)["mode"], "service-account")
        self.assertNotIn("tok", out)

    def test_request_rejects_non_rest_path(self):
        rc, _, err = self.run_main(["request", "GET", "/secure/admin"], PAT_ENV,
                                   lambda *a, **k: self.fail("no request expected"))
        self.assertEqual(rc, 2)
        self.assertIn("/rest/", err)

    def test_request_http_error_is_nonzero(self):
        def urlopen(req, timeout=None):
            raise urllib.error.HTTPError(req.full_url, 403, "Forbidden", {}, io.BytesIO(b'{"e":1}'))

        rc, _, err = self.run_main(["request", "GET", "/rest/api/3/myself"], PAT_ENV, urlopen)
        self.assertEqual(rc, 1)
        self.assertIn("403", err)

    def test_missing_credentials_is_nonzero(self):
        rc, _, err = self.run_main(["check"], {}, lambda *a, **k: self.fail("no request expected"))
        self.assertEqual(rc, 1)
        self.assertIn("JIRA_USERNAME", err)


if __name__ == "__main__":
    unittest.main()
