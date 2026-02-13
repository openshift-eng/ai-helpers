# Job Pattern Reference

When analyzing regressions, use these patterns to identify job types from job names and determine ownership.

## ROSA Classic

- **Match**: job name contains `rosa-sts-ovn`
- **Example**: `periodic-ci-openshift-release-master-nightly-4.22-e2e-rosa-sts-ovn`
- **Owner**: HCM OCP Release Enablement
- **Contact**: `#wg-hcm-ocp-release-enablement` on Slack
- **Notes**: ROSA (Red Hat OpenShift Service on AWS) classic managed platform jobs.

## RHCOS 10 (Tech Preview)

- **Match**: job name contains `rhcos10`
- **Example**: `periodic-ci-openshift-release-master-nightly-4.22-e2e-metal-ipi-ovn-ipv4-rhcos10-techpreview`
- **Notes**: RHCOS 10 is the next-generation Red Hat CoreOS based on RHEL 10. In release 4.22, these jobs are coming online as **TechPreview only** — the OS is not yet GA. These jobs currently produce a significant number of regressions. When analyzing a regression, always check whether the failing jobs are RHCOS 10 variants. Users may not immediately notice this from the job name alone. If a regression is isolated to `rhcos10` jobs and does not appear in standard RHCOS 9 jobs, highlight this prominently in the report — it likely indicates an RHCOS 10 / RHEL 10 specific issue rather than a general product regression.

## Insights Operator

- **Match**: job name contains `insights-operator`
- **Example**: `periodic-ci-openshift-insights-operator-release-4.22-periodics-e2e-aws-techpreview`
- **Owner**: Insights Operator team
- **Contact**: `#forum-observability-intelligence` on Slack (https://redhat.enterprise.slack.com/archives/CLABA9CHY)
- **Notes**: These jobs sit outside the normal OCP flows. We monitor them for regressions in component readiness, but failures here are best routed to the Insights team rather than treated as core OCP issues.
