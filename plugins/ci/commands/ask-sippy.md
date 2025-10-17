---
description: Ask the Sippy AI agent questions about OpenShift CI payloads, jobs, and test results
argument-hint: [question]
---

## Name
ask-sippy

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

## Prerequisites

**Required Environment Variable:**
- `ASK_SIPPY_API_TOKEN`: Authentication token for Sippy API access

If the token is not set, the command will fail with an authentication error.

## Implementation

The command performs the following steps:

1. **Validate Environment**: Checks that `ASK_SIPPY_API_TOKEN` is set
2. **Notify User**: Informs the user that the query is being processed (may take time)
3. **API Request**: Sends a POST request to the Sippy API with:
   - The user's question
   - Empty chat history (each query is independent)
   - `show_thinking: false` for concise responses
   - `persona: default` for general AI assistant behavior
4. **Return JSON**: Returns the full JSON response for Claude to parse

Implementation logic:
```bash
if [ -z "$ASK_SIPPY_API_TOKEN" ]; then
  echo "Error: ASK_SIPPY_API_TOKEN environment variable is not set"
  echo "Please set your Sippy API token before using this command"
  exit 1
fi

if [ -z "$1" ]; then
  echo "Error: Please provide a question to ask Sippy"
  echo "Usage: /ask-sippy [question]"
  exit 1
fi

echo "Querying Sippy AI agent... (this may take a moment)"
echo ""

curl -s -X POST "https://sippy-auth.dptools.openshift.org/api/chat" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ASK_SIPPY_API_TOKEN" \
  -d "{
    \"message\": \"$1\",
    \"chat_history\": [],
    \"show_thinking\": false,
    \"persona\": \"default\"
  }"
```

## Return Value
- **Success**: JSON response from Sippy API with the following structure:
  - `response`: Markdown-formatted answer from the agent (this is what should be displayed to the user)
  - `error`: null if successful
- **Error**: JSON with `error` field populated if the request fails

**Important for Claude**:
1. **Before invoking this command**, inform the user that querying Sippy may take 10-60 seconds for complex queries
2. Extract the `response` field from the JSON and render it as markdown to the user
3. If there's an `error` field, display that instead

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
