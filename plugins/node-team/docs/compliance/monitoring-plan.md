# Node Team AI Assistant - Monitoring Plan

Control ID: Mon-01

## 1. Runtime Integrity

### Headless/CronJob Execution
- Verify that `.work/node-cve/triage-YYYY-MM-DD/` artifacts exist and are
  non-empty after each scheduled run
- CronJob failure (non-zero exit) surfaces via standard OpenShift job
  monitoring and alerts
- Monitor pod logs for errors (failed Jira API calls, clone timeouts,
  Slack delivery failures)

### Monitoring for Behavioral Drift
- Track classification distribution over time. A sudden shift (e.g., all
  CVEs classified as "Uncertain" when they were previously mixed) may
  indicate a problem with repo connectivity or prompt drift.
- Monitor for unexpected tool invocations. The agent should only use
  `jira` CLI for Jira queries and comments, `git` for cloning, `curl`
  for Jira/Slack API calls, and `gh` for GitHub operations. Any other
  tool usage is anomalous.

### Overprivilege Audit
- Quarterly review of API token scopes to confirm least privilege:
  - `JIRA_API_TOKEN`: verify the token owner has only the necessary
    project permissions (OCPBUGS read + comment, OCPNODE read)
  - `SLACK_API_TOKEN`: verify bot is only added to #team-node
- Confirm no access creep (no new repos, APIs, or data sources added
  without updating the capabilities inventory)

## 2. Feedback and Quality Sampling

### Feedback Loop
- Users can report incorrect classifications or unhelpful output via
  GitHub issues at https://github.com/openshift-eng/ai-helpers/issues
  (tag with `plugin/node-cve`)
- Review flagged issues within one sprint cycle

### Accuracy Spot-Checks
- Monthly: randomly sample 3-5 Jira comments posted by `node-cve:triage`
  and verify the classification matches a manual assessment
- Track false positive rate (code flagged as reachable but is not) and
  false negative rate (reachable code missed)
- Target: false positive rate below 20%, false negative rate below 10%

### Skill Invocation Audit
- Review Claude Code session logs (JSONL transcripts) to verify the agent
  used read-only tools (git clone, curl GET, jira list) for analysis and
  only used write tools (curl POST for Jira comment, Slack message) when
  `--notify-*` flags were provided
- Flag any invocation of write tools without the corresponding opt-in flag

## 3. Core Performance Tracking

| Metric | How to Measure | Alert Threshold | Status |
|--------|----------------|-----------------|--------|
| Triage duration | CronJob pod runtime | > 2x rolling 30-day average | Planned |
| Token usage | Claude Code session metrics | > 2x rolling average per run | Planned |
| CVE count per run | `cves.json` total_cves field | Drops to 0 unexpectedly | Planned |
| Classification confidence | % of "Low" confidence results | > 30% low confidence | Planned |
| Jira comment failures | Return value `jira_comments_failed` | > 0 | Planned |
| Slack delivery failures | Slack API response status | Non-200 response | Planned |

Dashboards and alerting will be wired up as part of CronJob deployment.
Manual review against these thresholds applies until automated monitoring
is in place.

## 4. Behavioral Monitoring and Anomaly Detection

| Anomaly | Detection | Response | Status |
|---------|-----------|----------|--------|
| Infinite loop | Pod runtime exceeds 1 hour | Kill pod, investigate | Planned |
| Permission probing | Agent attempts to access files or APIs outside approved scope | Review session logs, update prompts | Manual |
| Resource spike | Token consumption > 3x baseline | Throttle, investigate prompt complexity | Planned |
| All-Uncertain results | Every CVE classified as Uncertain | Check repo clone connectivity, verify branch patterns | Manual |
| Zero CVEs found | Query returns no results when CVEs are known to exist | Verify JQL query, check component names | Manual |

## 5. Prompt and Skill Refinement

- Use negative examples from accuracy spot-checks to update analysis
  prompts in skill files
- Focus refinements on narrowing the agent's authority to the most
  restrictive necessary path
- Version all prompt changes via semver bumps to the node-cve plugin
- Track prompt changes in git history for auditability

## Review Cadence

| Activity | Frequency |
|----------|-----------|
| CronJob health check | Daily (automated) |
| Accuracy spot-check | Monthly |
| API token scope audit | Quarterly |
| Full monitoring plan review | Semi-annually |
