# payload-agent

Bundle of plugins for payload agents: CI analysis, must-gather diagnostics, and sosreport analysis.

## What's included

### Plugins

- `ci` — OpenShift CI / Prow job analysis
- `must-gather` — Must-gather data analysis and reporting
- `sosreport` — Sosreport archive diagnostics and troubleshooting

## Installation

Add the marketplace (one-time):

```sh
claude plugin marketplace add openshift-eng/ai-helpers
```

Install the bundle:

```sh
claude plugin install payload-agent@ai-helpers
```
