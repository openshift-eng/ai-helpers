# Test Pattern Reference

When analyzing regressions, use these patterns to identify test types and understand their failure modes.

## Monitor Tests

- **Match**: test name contains `[Monitor:<name>]`
- **Example**: `[Monitor:kubelet-container-restarts][sig-architecture] platform pods in ns/openshift-machine-config-operator should not exit an excessive amount of times`
- **What they are**: A framework in origin that monitors the cluster during e2e testing, then generates junit results after testing completes. They scan for abnormal behavior during test runs by analyzing intervals, pod logs, and system journal logs.
- **When they fail**: Indicates something unexpected happened on the cluster during testing (excessive restarts, disruption, unexpected log messages). The failure may not be caused by the test itself but by a product issue that the monitor detected.
- **Triage guidance**: These are product bugs, not test bugs. The monitor is reporting real cluster behavior. Triage as `product` unless the monitor logic itself is clearly wrong.

## Excessive Watch Request Tests

- **Match**: test name contains `should not create excessive watch requests`
- **What they are**: Tests that enforce upper limits on watch requests by operators. The limits are fixed values in origin, and the test fails if an operator exceeds its threshold significantly. The goal is to catch exponential growth in watch requests.
- **When they fail**: Usually indicates natural, gradual growth in watches by an operator. The limits need updating if the increase is modest and explainable. Values below 100 are normal.
- **Current thresholds**: Based on P99 values over the past month, with the limit set to double that amount.
- **How to fix**: There is a Claude Code command in the origin repo that automates updating the limits: https://github.com/openshift/origin/blob/main/.claude/commands/update-all-operator-watch-request-limits.md
- **Triage guidance**: If the increase is small and gradual, triage as `test` (limit update needed). If the increase is large or sudden, triage as `product` (investigate why the operator's watch count spiked).
