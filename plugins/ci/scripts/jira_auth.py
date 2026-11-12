#!/usr/bin/env python3
"""
Shared Jira authentication for the ci plugin scripts.

Two modes, selected from the environment:

  Service account (OAuth 2.0 client credentials), when JIRA_CLIENT_ID or
  JIRA_CLIENT_SECRET is set. Requires JIRA_CLIENT_ID, JIRA_CLIENT_SECRET and
  JIRA_CLOUD_ID. Requests go to https://api.atlassian.com/ex/jira/<cloud-id>
  with a Bearer token obtained from https://auth.atlassian.com/oauth/token.
  A misconfigured or rejected credential is an error; there is no fallback to
  the API token.

  API token (Basic auth), otherwise. Requires JIRA_USERNAME and JIRA_API_TOKEN.
  Requests go to https://redhat.atlassian.net.

Usage as a command:
    python3 jira_auth.py check
    python3 jira_auth.py request GET '/rest/api/3/search/jql?jql=project=OCPBUGS&maxResults=1'
    python3 jira_auth.py request POST /rest/api/3/issue --data-file issue.json

The command never prints credentials or access tokens.
"""

import argparse
import base64
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

JIRA_SITE_URL = "https://redhat.atlassian.net"
OAUTH_TOKEN_URL = "https://auth.atlassian.com/oauth/token"
OAUTH_GATEWAY_URL = "https://api.atlassian.com/ex/jira"
TIMEOUT = 30
EXPIRY_MARGIN = 60

MODE_SERVICE_ACCOUNT = "service-account"
MODE_API_TOKEN = "api-token"


class JiraAuthError(Exception):
    """Jira credentials are missing, incomplete, or were rejected."""


class JiraAuth:
    """Resolved Jira credentials: where to send requests and how to sign them."""

    def __init__(self, mode, base_url, username=None, token=None,
                 client_id=None, client_secret=None):
        self.mode = mode
        self.base_url = base_url
        self._username = username
        self._token = token
        self._client_id = client_id
        self._client_secret = client_secret
        self._access_token = None
        self._expires_at = 0.0

    def url(self, path):
        """Absolute URL for a REST path such as /rest/api/3/myself."""
        return self.base_url + "/" + path.lstrip("/")

    def authorization(self):
        """Value for the Authorization header, obtaining or renewing the token when needed."""
        if self.mode == MODE_API_TOKEN:
            credentials = base64.b64encode(
                ("%s:%s" % (self._username, self._token)).encode("utf-8")).decode("ascii")
            return "Basic " + credentials
        if not self._access_token or time.time() >= self._expires_at - EXPIRY_MARGIN:
            self._access_token, expires_in = _fetch_access_token(self._client_id, self._client_secret)
            self._expires_at = time.time() + expires_in
        return "Bearer " + self._access_token


def _oauth_error_code(http_error):
    try:
        code = json.loads(http_error.read().decode("utf-8")).get("error")
    except (AttributeError, OSError, ValueError):
        return ""
    return " (%s)" % code if isinstance(code, str) and re.fullmatch(r"[a-z_]{1,40}", code) else ""


def _fetch_access_token(client_id, client_secret):
    body = urllib.parse.urlencode({
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret,
    }).encode("utf-8")
    req = urllib.request.Request(OAUTH_TOKEN_URL, data=body, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    req.add_header("Accept", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        # The response body can echo request parameters, so only the status and error code are reported.
        raise JiraAuthError("Jira service-account token request failed: HTTP %d%s" % (e.code, _oauth_error_code(e)))
    except urllib.error.URLError as e:
        raise JiraAuthError("Jira service-account token request failed: %s" % e.reason)
    except ValueError:
        raise JiraAuthError("Jira service-account token response was not valid JSON")
    token = data.get("access_token") if isinstance(data, dict) else None
    if not token:
        raise JiraAuthError("Jira service-account token response had no access_token")
    try:
        expires_in = float(data.get("expires_in") or 0)
    except (TypeError, ValueError):
        expires_in = 0.0
    return token, expires_in


def service_account_requested(env=None):
    """True when the environment opts into service-account authentication."""
    env = os.environ if env is None else env
    return bool(env.get("JIRA_CLIENT_ID") or env.get("JIRA_CLIENT_SECRET"))


def resolve(username=None, token=None, env=None):
    """Select credentials. An explicit username or token always means API-token auth."""
    env = os.environ if env is None else env
    if not (username or token) and service_account_requested(env):
        missing = [k for k in ("JIRA_CLIENT_ID", "JIRA_CLIENT_SECRET", "JIRA_CLOUD_ID") if not env.get(k)]
        if missing:
            raise JiraAuthError(
                "Jira service-account authentication needs JIRA_CLIENT_ID, JIRA_CLIENT_SECRET and "
                "JIRA_CLOUD_ID; missing: %s" % ", ".join(missing))
        try:
            cloud_id = str(uuid.UUID(env["JIRA_CLOUD_ID"].strip()))
        except ValueError:
            raise JiraAuthError("JIRA_CLOUD_ID must be a UUID")
        return JiraAuth(MODE_SERVICE_ACCOUNT, "%s/%s" % (OAUTH_GATEWAY_URL, cloud_id),
                        client_id=env["JIRA_CLIENT_ID"].strip(),
                        client_secret=env["JIRA_CLIENT_SECRET"].strip())
    username = username or env.get("JIRA_USERNAME", "")
    token = token or env.get("JIRA_API_TOKEN", "")
    missing = [k for k, v in (("JIRA_USERNAME", username), ("JIRA_API_TOKEN", token)) if not v]
    if missing:
        raise JiraAuthError(
            "Jira credentials are not set; missing: %s. Set JIRA_USERNAME and JIRA_API_TOKEN "
            "(https://id.atlassian.com/manage-profile/security/api-tokens), or JIRA_CLIENT_ID, "
            "JIRA_CLIENT_SECRET and JIRA_CLOUD_ID for a service account." % ", ".join(missing))
    return JiraAuth(MODE_API_TOKEN, JIRA_SITE_URL, username=username, token=token)


def _request(auth, method, path, data=None):
    req = urllib.request.Request(auth.url(path), data=data, method=method)
    req.add_header("Authorization", auth.authorization())
    req.add_header("Accept", "application/json")
    if data is not None:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return resp.status, resp.read().decode("utf-8", errors="replace")


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Authenticated Jira REST requests using the credentials in the environment")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check", help="Verify the credentials authenticate and report the account")
    r = sub.add_parser("request", help="Send one REST request and print the response body")
    r.add_argument("method", choices=["GET", "POST", "PUT", "DELETE"])
    r.add_argument("path", help="REST path starting with /rest/, including any query string")
    r.add_argument("--data-file", help="File holding the JSON request body")
    args = parser.parse_args(argv)

    try:
        auth = resolve()
        if args.cmd == "check":
            _, body = _request(auth, "GET", "/rest/api/3/myself")
            me = json.loads(body)
            print(json.dumps({
                "mode": auth.mode,
                "base_url": auth.base_url,
                "account_id": me.get("accountId"),
                "display_name": me.get("displayName"),
            }, indent=2))
            return 0
        if not args.path.startswith("/rest/"):
            print("Error: path must start with /rest/", file=sys.stderr)
            return 2
        data = None
        if args.data_file:
            with open(args.data_file, "rb") as f:
                data = f.read()
        _, body = _request(auth, args.method, args.path, data)
        if body:
            print(body)
        return 0
    except JiraAuthError as e:
        print("Error: %s" % e, file=sys.stderr)
        return 1
    except urllib.error.HTTPError as e:
        print("Error: HTTP %d: %s" % (e.code, e.read().decode("utf-8", errors="replace")), file=sys.stderr)
        return 1
    except urllib.error.URLError as e:
        print("Error: %s" % e.reason, file=sys.stderr)
        return 1
    except (OSError, ValueError) as e:
        print("Error: %s" % e, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
