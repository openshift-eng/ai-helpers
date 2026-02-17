---
description: Analyze OpenShift installation failures in Prow CI jobs
argument-hint: <prowjob-url>
---

## Name
ci:analyze-prow-job-install-failure

## Synopsis
```
/ci:analyze-prow-job-install-failure <prowjob-url>
```

## Description

The `ci:analyze-prow-job-install-failure` command analyzes OpenShift installation failures in Prow CI jobs by downloading and examining installer logs, log bundles, and sosreports (for metal jobs). This command is specifically designed to debug failures in the **"install should succeed: overall"** test, which indicates that the installation process failed at some stage.

**Important**: All "install should succeed" tests have a specific suffix indicating the failure stage (configuration, infrastructure, cluster bootstrap, cluster creation, cluster operator stability, or other). The JUnit XML contains both the specific failure reason test (which fails) and the overall test (which also fails when any stage fails). This command analyzes the specific failure stage to provide targeted diagnostics.

The command accepts:
- Prow job URL (required): URL to the failed CI job from prow.ci.openshift.org

It downloads relevant artifacts from Google Cloud Storage, analyzes them, and generates a comprehensive report with findings and recommended next steps.

### Recognized Failure Modes

The command identifies the failure mode from `junit_install.xml` and tailors its analysis:

- **"install should succeed: configuration"** - Extremely rare failure where install-config.yaml validation failed. Focus on installer log only.
- **"install should succeed: infrastructure"** - Failed to create cloud resources. Usually due to cloud quota, rate limiting, or outages. Log bundle may not exist.
- **"install should succeed: cluster bootstrap"** - Bootstrap node failed to start temporary control plane. Check bootkube logs in the bundle.
- **"install should succeed: cluster creation"** - One or more operators unable to deploy. Check operator logs in gather-must-gather.
- **"install should succeed: cluster operator stability"** - Operators never stabilized (stuck progressing/degraded). Check operator status and logs.
- **"install should succeed: other"** - Unknown failure requiring comprehensive analysis of all available logs.

## Implementation

The command performs the following steps by invoking the "Prow Job Analyze Install Failure" skill:

1. **Parse Job URL**: Extract build ID and job details from the Prow URL

2. **Download prowjob.json**: Identify the ci-operator target

3. **Download JUnit XML**: Identify the specific failure mode (configuration, infrastructure, cluster bootstrap, etc.)

4. **Download Installer Logs**: Get `.openshift_install*.log` files that contain the installation timeline

5. **Download Log Bundle**: Get `log-bundle-*.tar` containing:
   - Bootstrap node journals (bootkube, kubelet, crio, etc.)
   - Serial console logs from all nodes
   - Cluster API resources (etcd, kube-apiserver logs)
   - Failed systemd units list

6. **Invoke Metal Skill** (metal jobs only): Use the specialized `ci:prow-job-analyze-metal-install-failure` skill to analyze:
   - Dev-scripts setup logs (installation framework)
   - libvirt console logs (VM/node boot sequence)
   - sosreport (hypervisor diagnostics)
   - squid logs (proxy logs for disconnected environments)

7. **Analyze Logs**: Extract key failure indicators based on failure mode:
   - **configuration**: install-config.yaml validation errors
   - **infrastructure**: Cloud quota/rate limit/API errors
   - **cluster bootstrap**: bootkube/etcd/API server failures
   - **cluster creation**: Operator deployment failures
   - **cluster operator stability**: Operators stuck in unstable state
   - **other**: Comprehensive analysis of all logs

8. **Generate Report**: Create comprehensive analysis with:
   - Failure mode and summary
   - Timeline of events
   - Key error messages with context
   - Failure mode-specific recommended steps
   - Artifact locations

The skill handles all the implementation details including URL parsing, artifact downloading, archive extraction, log analysis, and report generation.

## Return Value
- **Success**: Comprehensive analysis report saved to `.work/prow-job-analyze-install-failure/{build_id}/analysis/report.txt`
- **Error**: Error message explaining the issue (invalid URL, gcloud not installed, artifacts not found, etc.)

**Important for Claude**:
1. Parse the Prow job URL to extract the build ID and job name
2. Invoke the "ci:prow-job-analyze-install-failure" skill with the job details
3. The skill will download all relevant artifacts and analyze them
4. For metal jobs, the skill automatically invokes the specialized metal install failure skill
5. Present the analysis report to the user with clear findings
6. Provide actionable next steps based on the failure mode
7. Highlight critical errors and their context

## Examples

1. **Analyze an AWS installation failure**:
   ```
   /ci:analyze-prow-job-install-failure https://prow.ci.openshift.org/view/gs/test-platform-results/logs/periodic-ci-openshift-release-master-ci-4.21-e2e-aws-ovn-techpreview/1983307151598161920
   ```
   Expected output:
   - Downloads installer logs and log bundle
   - Identifies failure mode from junit_install.xml
   - Analyzes bootstrap and installation logs
   - Reports: "Bootstrap failed due to etcd cluster formation timeout"
   - Provides etcd logs and recommendations

2. **Analyze a metal installation failure**:
   ```
   /ci:analyze-prow-job-install-failure https://prow.ci.openshift.org/view/gs/test-platform-results/logs/periodic-ci-openshift-release-master-nightly-4.21-e2e-metal-ipi-ovn-ipv6/1983304069657137152
   ```
   Expected output:
   - Invokes specialized metal install failure skill
   - Downloads dev-scripts logs, libvirt console logs, sosreport
   - Analyzes dev-scripts setup and VM console logs
   - Reports: "Bootstrap VM failed to boot - Ignition config fetch failed"
   - Provides console logs and dev-scripts analysis

3. **Analyze an infrastructure failure**:
   ```
   /ci:analyze-prow-job-install-failure https://prow.ci.openshift.org/view/gs/test-platform-results/pr-logs/pull/openshift/installer/12345/pull-ci-openshift-installer-master-e2e-aws/7890
   ```
   Expected output:
   - Identifies "install should succeed: infrastructure" failure
   - Focuses on installer log (no log bundle expected)
   - Reports: "Cloud quota exceeded for instance type m5.xlarge"
   - Recommends checking quota limits

4. **Analyze an operator stability failure**:
   ```
   /ci:analyze-prow-job-install-failure https://prow.ci.openshift.org/view/gs/test-platform-results/logs/periodic-ci-openshift-release-master-ci-4.21-e2e-gcp/1234567890123456789
   ```
   Expected output:
   - Identifies "install should succeed: cluster operator stability" failure
   - Checks gather-must-gather for operator logs
   - Reports: "kube-apiserver operator stuck progressing"
   - Provides operator logs and status conditions

## Notes

- **Failure Modes**: The installer has multiple failure modes detected from junit_install.xml. Each mode requires different analysis approaches.
- **Log Bundle**: Contains detailed node-level diagnostics including journals, serial consoles, and cluster API resources
- **Metal Jobs**: Identified by "metal" in the job name. These jobs automatically invoke the specialized `ci:prow-job-analyze-metal-install-failure` skill.
- **Metal Artifacts**: Metal jobs analyze dev-scripts logs, libvirt console logs, sosreport, and squid logs
- **Artifacts Location**: All downloaded artifacts are cached in `.work/prow-job-analyze-install-failure/{build_id}/` for faster re-analysis
- **gcloud Requirement**: Requires gcloud CLI to be installed to access GCS buckets
- **Public Access**: The test-platform-results bucket is publicly accessible - no authentication needed

## Arguments
- **$1** (prowjob-url): The Prow job URL from prow.ci.openshift.org (required)
