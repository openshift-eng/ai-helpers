# Red Hat Support: Knowledge Base & Cases

## Authentication

Both APIs use OAuth Bearer tokens. Get the offline token from keychain, exchange for access token:

- Keychain key: `RH_API_OFFLINE_TOKEN` (macOS: `security find-generic-password -a "$USER" -s "RH_API_OFFLINE_TOKEN" -w`, Linux: `secret-tool lookup service redhat key RH_API_OFFLINE_TOKEN`)
- Token exchange: `POST https://sso.redhat.com/auth/realms/redhat-external/protocol/openid-connect/token` with `grant_type=refresh_token`, `client_id=rhsm-api`, `refresh_token=$OFFLINE_TOKEN`, then extract `access_token` from response

Always get a fresh token before each session. Exchange the token and call the
API in the same Bash invocation (variables do not persist between Bash tool
calls), and keep both tokens off the command line:

```bash
OFFLINE_TOKEN="${RH_API_OFFLINE_TOKEN:-$(security find-generic-password -a "$USER" -s "RH_API_OFFLINE_TOKEN" -w 2>/dev/null || secret-tool lookup service redhat key RH_API_OFFLINE_TOKEN 2>/dev/null)}"
[ -n "$OFFLINE_TOKEN" ] || { echo "ERROR: RH_API_OFFLINE_TOKEN not found (env, Keychain, secret-tool)" >&2; exit 1; }
ACCESS_TOKEN=$(printf 'data = "grant_type=refresh_token&client_id=rhsm-api&refresh_token=%s"\n' "$OFFLINE_TOKEN" \
  | curl -s -K - "https://sso.redhat.com/auth/realms/redhat-external/protocol/openid-connect/token" \
  | jq -r '.access_token // empty')
[ -n "$ACCESS_TOKEN" ] || { echo "ERROR: token exchange failed" >&2; exit 1; }
rh_curl() { printf 'header = "Authorization: Bearer %s"\n' "$ACCESS_TOKEN" | curl -s -K - "$@"; }
```

## Customer Data Handling

Support cases, their comments and attachments are customer data. Rules:

- Only open a case when the user names it or a Jira issue they are working on
  links to it. No bulk case searches without an explicit request.
- Do not download attachments (must-gathers, sosreports) to the local machine.
  Use SupportShell for that (see `shared/team-info.md`).
- Do not copy customer names, hostnames, IPs or log excerpts into public
  places (GitHub, upstream issues, public Jira comments). Summarize instead.
- Do not write case content to files under `.work/`.

## Knowledge Base

Endpoint: `GET https://access.redhat.com/hydra/rest/search/kcs`

Key params: `q` (search terms, `+` joins), `rows`, `start` (pagination offset), `fq` (filter), `fl` (field list), `sort`.

Useful `fq` filters: `documentKind:Solution`, `id:7087003` (fetch by ID), `boostProduct:openshift`.

Solution-specific field names (Solr): `solution_resolution`, `solution_rootcause`, `solution_environment`, `solution_diagnosticsteps`, `issue`, `caseCount`.

URL parsing: `https://access.redhat.com/solutions/7087003`: extract `7087003`, fetch with `fq=id:7087003`.

## Support Cases

Endpoint: `https://api.access.redhat.com/support/v1/cases/{caseNumber}`

Comments: `GET .../comments`, Attachments: `GET .../attachments`, Search: `POST .../filter` with JSON body (`maxResults`, `offset`, `keyword`, `status`, `product`, `startDate`, `endDate`).

Statuses: `Waiting on Red Hat`, `Waiting on Customer`, `Closed`. Severities: `1 (Urgent)` = production down, `2 (High)`, `3 (Normal)`, `4 (Low)`.

URL parsing: `https://access.redhat.com/support/cases/#/case/04378910`: extract `04378910`.

When Jira bugs have SFDC case links (`customfield_10979`, "SFDC Cases Links" in [jira.md](jira.md)), look up each referenced case number.
