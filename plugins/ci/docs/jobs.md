# Job Pattern Reference

When analyzing regressions, use these patterns to identify job types from job names and determine ownership.

## ROSA Classic

- **Match**: job name contains `rosa-sts-ovn`
- **Example**: `periodic-ci-openshift-release-master-nightly-4.22-e2e-rosa-sts-ovn`
- **Owner**: HCM OCP Release Enablement
- **Contact**: `#wg-hcm-ocp-release-enablement` on Slack
- **Notes**: ROSA (Red Hat OpenShift Service on AWS) classic managed platform jobs.

## Insights Operator

- **Match**: job name contains `insights-operator`
- **Example**: `periodic-ci-openshift-insights-operator-release-4.22-periodics-e2e-aws-techpreview`
- **Owner**: Insights Operator team
- **Contact**: `#forum-observability-intelligence` on Slack (https://redhat.enterprise.slack.com/archives/CLABA9CHY)
- **Notes**: These jobs sit outside the normal OCP flows. We monitor them for regressions in component readiness, but failures here are best routed to the Insights team rather than treated as core OCP issues.
