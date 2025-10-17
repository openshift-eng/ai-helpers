# CI Plugin

A plugin for working with OpenShift CI infrastructure, providing
commands to analyze CI data, investigate failures, and understand
release quality.

## Commands

### ask-sippy

Query the Sippy Chat AI agent for CI/CD data analysis.  Sippy Chat has a
[web interface](https://sippy-auth.dptools.openshift.org/sippy-ng/chat)
available as well.

**Note:** Each query is independent with no conversation history
maintained between calls. Use the web interface for longer sessions
requiring more context.

Thinking steps are not currently streamed, so it may take some time to
appear to get a result, 10-60 seconds in most cases.

**Usage:**
```bash
/ask-sippy [question]
```

**What it does:**
- Analyzes OpenShift release payloads and rejection reasons
- Investigates CI job failures and patterns
- Examines test failures, flakes, and regressions
- Provides CI health trends and comparisons
- Delivers release quality metrics

**Prerequisites:**

You need to set a token for Sippy's authenticated instance. You can
obtain the OAuth token by visiting
[api.ci](https://console-openshift-console.apps.cr.j7t7.p1.openshiftapps.com/k8s/cluster/projects)
and logging in with SSO, and displaying your API token (sha256~<something>).

```bash
export ASK_SIPPY_API_TOKEN='your-token-here'
```

**Examples:**

1. **Payload investigation:**
   ```bash
   /ask-sippy Why was the latest 4.21 payload rejected?
   ```

2. **Test failure analysis:**
   ```bash
   /ask-sippy What are the most common test failures in e2e-aws this week?
   ```

3. **CI health check:**
   ```bash
   /ask-sippy How is the overall CI health for 4.20 compared to last week?
   ```

4. **Specific test inquiry:**
   ```bash
   /ask-sippy Why is the test "sig-network Feature:SCTP should create a Pod with SCTP HostPort" failing?
   ```

## Configuration

### Environment Variables

- `ASK_SIPPY_API_TOKEN`: Required for Sippy queries.
