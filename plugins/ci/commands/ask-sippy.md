---
description: Ask the Sippy AI agent questions about OpenShift CI payloads, jobs, and test results
argument-hint: "[question]"
---

## Name
ci:ask-sippy

## Synopsis
```
/ask-sippy [question]
```

## Description

The `ask-sippy` command allows you to query the Sippy AI agent, which has deep knowledge about OpenShift CI infrastructure, including:
- CI payload status and rejection reasons
- Job failures and patterns
- Test results and trends
- Release quality metrics
- Historical CI data analysis

The command sends your question to the Sippy API and returns the agent's
response. Note that complex queries may take some time to process as the
agent analyzes CI data. Please inform the user of this.

## Security

**IMPORTANT SECURITY REQUIREMENTS:**

Claude is granted LIMITED and SPECIFIC access to the DPCR cluster token for the following AUTHORIZED operations ONLY:
- **READ operations**: Querying the Sippy API for CI data analysis

Claude is EXPLICITLY PROHIBITED from:
- Modifying cluster resources (deployments, pods, services, etc.)
- Deleting or altering any data
- Accessing secrets, configmaps, or sensitive data beyond Sippy API responses
- Making any cluster modifications
- Using the token for any purpose other than the specific operations listed above

**Token Usage:**
The DPCR cluster token is used solely for authentication with the Sippy API. This token grants the same permissions as the authenticated user and must be handled with appropriate care. The `curl_with_token.sh` wrapper handles all authentication automatically.

## Implementation

1. **Validate Arguments**: Checks that a question was provided
2. **Notify User**: Informs the user that the query is being processed (may take time)
3. **API Request**: Sends a POST request to the Sippy API using the `oc-auth` skill's curl wrapper:
   ```bash
   # Use curl_with_token.sh from oc-auth skill - it automatically adds the OAuth token
   # DPCR cluster API: https://api.cr.j7t7.p1.openshiftapps.com:6443
   curl_with_token.sh https://api.cr.j7t7.p1.openshiftapps.com:6443 -s -X POST "https://sippy-auth.dptools.openshift.org/api/chat" \
     -H "Content-Type: application/json" \
     -d @- <<'EOF'
{
  "message": "$1",
  "chat_history": [],
  "show_thinking": false,
  "persona": "default"
}
EOF
   ```
4. **Return JSON**: Returns the full JSON response for Claude to parse

## Return Value
- **Success**: JSON response from Sippy API with the following structure:
  - `response`: Markdown-formatted answer from the agent (this is what should be displayed to the user)
  - `visualizations`: Optional field containing Plotly JSON for interactive charts and graphs
  - `error`: null if successful
- **Error**: JSON with `error` field populated if the request fails

**Important for Claude**:
1. **REQUIRED**: Before executing this command, you MUST ensure the `ci:oc-auth` skill is loaded by invoking it with the Skill tool. The curl_with_token.sh script depends on this skill being active.
2. You must locate and verify curl_with_token.sh before running it, you (Claude Code) have a bug that tries to use the script from the wrong directory!
3. **Before invoking this command**, inform the user that querying Sippy may take 10-60 seconds for complex queries
4. Extract the `response` field from the JSON and render it as markdown to the user
5. If the response includes a `visualizations` field, it contains Plotly JSON. Render the visualization(s) in an interactive, user-friendly way by creating an HTML file with the Plotly chart(s) embedded. Open it in the user's browser for them.
6. If there's an `error` field, display that instead

## Examples

1. **Query about payload rejection**:
   ```
   /ask-sippy Why was the last 4.21 payload rejected?
   ```
   Response will include analysis of the latest 4.21 payload rejection with specific job failures and reasons.

2. **Ask about job failures**:
   ```
   /ask-sippy What are the most common test failures in the e2e-aws job this week?
   ```
   Response will analyze recent test failure patterns in the specified job.

3. **Investigate CI trends**:
   ```
   /ask-sippy How is the overall CI health for 4.20 compared to last week?
   ```
   Response will provide comparative analysis of CI metrics.

4. **Specific test inquiry**:
   ```
   /ask-sippy Why is the test "sig-network Feature:SCTP should create a Pod with SCTP HostPort" failing?
   ```
   Response will analyze failure patterns and potential causes for the specific test.

## Notes

- **Response Time**: Complex queries analyzing large datasets may take 30-60 seconds
- **Chat History**: Each query is independent; no conversation context is maintained between calls
- **Response Format**: The API returns JSON with a `response` field containing markdown-formatted text
- **Markdown Rendering**: Claude will automatically render the markdown response nicely with proper formatting
- **Visualizations**: When available, the `visualizations` field contains Plotly JSON for interactive charts and graphs. Claude should render these as HTML files for the user to view
- **Error Handling**: If the API returns an error, it will be displayed in the `error` field of the JSON response

## Data Sources Available

Sippy can query and analyze:
- **Release Payloads**: Status, rejections, promotions for all 4.x versions
- **CI Jobs**: Failure rates, patterns, infrastructure issues (aws, gcp, azure, metal, vsphere, etc.)
- **Test Results**: Pass/fail rates, flakes, regressions, execution times
- **Historical Analysis**: Week-over-week and release-to-release comparisons
- **Infrastructure Metrics**: Provisioning issues, platform problems, resource patterns

## Arguments
- **$1** (question): The question to ask the Sippy AI agent. Should be a clear, specific question about OpenShift CI infrastructure, payloads, jobs, or test results.
