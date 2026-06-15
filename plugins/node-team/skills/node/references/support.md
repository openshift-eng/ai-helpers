# Red Hat Support: Knowledge Base & Cases

## Authentication

Both APIs use OAuth Bearer tokens. Get the offline token from keychain, exchange for access token:

- Keychain key: `RH_API_OFFLINE_TOKEN` (macOS: `security find-generic-password -a "$USER" -s "RH_API_OFFLINE_TOKEN" -w`, Linux: `secret-tool lookup service redhat key RH_API_OFFLINE_TOKEN`)
- Token exchange: `POST https://sso.redhat.com/auth/realms/redhat-external/protocol/openid-connect/token` with `grant_type=refresh_token`, `client_id=rhsm-api`, `refresh_token=$OFFLINE_TOKEN` → extract `access_token` from response

Always get a fresh token before each session.

## Knowledge Base

Endpoint: `GET https://access.redhat.com/hydra/rest/search/kcs`

Key params: `q` (search terms, `+` joins), `rows`, `start` (pagination offset), `fq` (filter), `fl` (field list), `sort`.

Useful `fq` filters: `documentKind:Solution`, `id:7087003` (fetch by ID), `boostProduct:openshift`.

Solution-specific field names (Solr): `solution_resolution`, `solution_rootcause`, `solution_environment`, `solution_diagnosticsteps`, `issue`, `caseCount`.

URL parsing: `https://access.redhat.com/solutions/7087003` → extract `7087003`, fetch with `fq=id:7087003`.

## Support Cases

Endpoint: `https://api.access.redhat.com/support/v1/cases/{caseNumber}`

Comments: `GET .../comments`, Attachments: `GET .../attachments`, Search: `POST .../filter` with JSON body (`maxResults`, `offset`, `keyword`, `status`, `product`, `startDate`, `endDate`).

Statuses: `Waiting on Red Hat`, `Waiting on Customer`, `Closed`. Severities: `1 (Urgent)` = production down, `2 (High)`, `3 (Normal)`, `4 (Low)`.

URL parsing: `https://access.redhat.com/support/cases/#/case/04378910` → extract `04378910`.

When Jira bugs have SFDC case links (`customfield_12313441` or `customfield_10979`), look up each referenced case number.
