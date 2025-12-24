# Available Plugins

This document lists all available Claude Code plugins and their commands in the ai-helpers repository.

- [Agendas](#agendas-plugin)
- [Bigquery](#bigquery-plugin)
- [Ci](#ci-plugin)
- [Compliance](#compliance-plugin)
- [Component Health](#component-health-plugin)
- [Container Image](#container-image-plugin)
- [Doc](#doc-plugin)
- [Etcd](#etcd-plugin)
- [Git](#git-plugin)
- [Gwapi](#gwapi-plugin)
- [Hcp](#hcp-plugin)
- [Hello World](#hello-world-plugin)
- [Jira](#jira-plugin)
- [Lvms](#lvms-plugin)
- [Must Gather](#must-gather-plugin)
- [Node](#node-plugin)
- [Node Tuning](#node-tuning-plugin)
- [Olm](#olm-plugin)
- [Openshift](#openshift-plugin)
- [Origin](#origin-plugin)
- [Prow Job](#prow-job-plugin)
- [Session](#session-plugin)
- [Sosreport](#sosreport-plugin)
- [Test Coverage](#test-coverage-plugin)
- [Utils](#utils-plugin)
- [Workspaces](#workspaces-plugin)
- [Yaml](#yaml-plugin)

### Agendas Plugin

A plugin to create various meeting agendas

**Commands:**
- **`/agendas:outcome-refinement`** - Analyze the list of JIRA outcome issues to prepare an outcome refinement meeting agenda.

See [plugins/agendas/README.md](plugins/agendas/README.md) for detailed documentation.

### Bigquery Plugin

BigQuery cost analysis and optimization utilities

**Commands:**
- **`/bigquery:analyze-usage` `<project-id> <timeframe>`** - Analyze BigQuery usage and costs for a project

See [plugins/bigquery/README.md](plugins/bigquery/README.md) for detailed documentation.

### Ci Plugin

Miscellaneous tools for working with OpenShift CI

**Commands:**
- **`/ci:add-debug-wait` `<workflow-or-job-name> [timeout]`** - Add a wait step to a CI workflow for debugging test failures
- **`/ci:ask-sippy` `[question]`** - Ask the Sippy AI agent questions about OpenShift CI payloads, jobs, and test results
- **`/ci:list-unstable-tests` `<version> <keywords> [sippy-url]`** - List unstable tests with pass rate below 95%
- **`/ci:query-job-status` `<execution-id>`** - Query the status of a gangway job execution by ID
- **`/ci:query-test-result` `<version> <keywords> [sippy-url]`** - Query test results from Sippy by version and test keywords
- **`/ci:trigger-periodic` `<job-name> [ENV_VAR=value ...]`** - Trigger a periodic gangway job with optional environment variable overrides
- **`/ci:trigger-postsubmit` `<job-name> <org> <repo> <base-ref> <base-sha> [ENV_VAR=value ...]`** - Trigger a postsubmit gangway job with repository refs
- **`/ci:trigger-presubmit` `<job-name> <org> <repo> <base-ref> <base-sha> <pr-number> <pr-sha> [ENV_VAR=value ...]`** - Trigger a presubmit gangway job (typically use GitHub Prow commands instead)

See [plugins/ci/README.md](plugins/ci/README.md) for detailed documentation.

### Compliance Plugin

Security compliance and vulnerability analysis tools for Go projects

**Commands:**
- **`/compliance:analyze-cve` `<CVE-ID>`** - Analyze Go codebase for CVE vulnerabilities and suggest fixes

See [plugins/compliance/README.md](plugins/compliance/README.md) for detailed documentation.

### Component Health Plugin

Analyze component health using regression and jira data

**Commands:**
- **`/component-health:analyze` `<release> [--components comp1 comp2 ...] [--project JIRAPROJECT]`** - Analyze and grade component health based on regression and JIRA bug metrics
- **`/component-health:list-components` `<release>`** - List all components tracked in Sippy for a release
- **`/component-health:list-jiras` `<project> [--component comp1 comp2 ...] [--status status1 status2 ...] [--include-closed] [--limit N]`** - Query and list raw JIRA bug data for a specific project
- **`/component-health:list-regressions` `<release> [--components comp1 comp2 ...] [--start YYYY-MM-DD] [--end YYYY-MM-DD]`** - Fetch and list raw regression data for OpenShift releases
- **`/component-health:summarize-jiras` `--project <project> [--component comp1 comp2 ...] [--status status1 status2 ...] [--include-closed] [--limit N]`** - Query and summarize JIRA bugs for a specific project with counts by component
- **`/component-health:summarize-regressions` `<release> [--components comp1 comp2 ...] [--start YYYY-MM-DD] [--end YYYY-MM-DD]`** - Query and summarize regression data for OpenShift releases with counts and metrics

See [plugins/component-health/README.md](plugins/component-health/README.md) for detailed documentation.

### Container Image Plugin

Container image inspection and analysis using skopeo and podman

**Commands:**
- **`/container-image:compare` `<image1> <image2>`** - Compare two container images to identify differences
- **`/container-image:inspect` `<image>`** - Inspect and provide detailed breakdown of a container image
- **`/container-image:tags` `<repository>`** - List and analyze available tags for a container image repository

See [plugins/container-image/README.md](plugins/container-image/README.md) for detailed documentation.

### Doc Plugin

A plugin for engineering documentation and notes

**Commands:**
- **`/doc:note` `[task description]`** - Generate professional engineering notes and append them to a log file

See [plugins/doc/README.md](plugins/doc/README.md) for detailed documentation.

### Etcd Plugin

Etcd cluster health monitoring and performance analysis utilities

**Commands:**
- **`/etcd:analyze-performance` `[--duration <minutes>]`** - Analyze etcd performance metrics, latency, and identify bottlenecks
- **`/etcd:health-check` `[--verbose]`** - Check etcd cluster health, member status, and identify issues

See [plugins/etcd/README.md](plugins/etcd/README.md) for detailed documentation.

### Git Plugin

Git workflow automation and utilities

**Commands:**
- **`/git:backport` `<commit> <branch1> [branch2...] [--new-branch]`** - Backport commits to multiple branches
- **`/git:bisect` `[good-commit] [bad-commit]`** - Interactive git bisect assistant with pattern detection and automation
- **`/git:branch-cleanup` `[--dry-run] [--merged-only] [--remote]`** - Clean up old and defunct branches that are no longer needed
- **`/git:cherry-pick-by-patch` `<commit_hash>`** - Cherry-pick git commit into current branch by "patch" command
- **`/git:commit-suggest` `[N]`** - Generate Conventional Commits style commit messages or summarize existing commits
- **`/git:debt-scan`** - Analyze technical debt indicators in the repository
- **`/git:fix-cherrypick-robot-pr` `<pr-url> [error-messages]`** - Fix a cherrypick-robot PR that needs manual intervention
- **`/git:suggest-reviewers` `[base-branch]`** - Suggest appropriate reviewers for a PR based on git blame and OWNERS files
- **`/git:summary`** - Show current branch, git status, and recent commits for quick context

See [plugins/git/README.md](plugins/git/README.md) for detailed documentation.

### Gwapi Plugin

Gateway API management for Kubernetes/OpenShift clusters

**Commands:**
- **`/gwapi:check` `[namespace]`** - Check Gateway API resources status in the cluster
- **`/gwapi:delete` `[namespace]`** - Delete Gateway API resources from a Kubernetes/OpenShift cluster
- **`/gwapi:install` `[namespace]`** - Install Gateway API resources to a Kubernetes/OpenShift cluster

See [plugins/gwapi/README.md](plugins/gwapi/README.md) for detailed documentation.

### Hcp Plugin

Generate HyperShift cluster creation commands via hcp CLI from natural language descriptions

**Commands:**
- **`/hcp:cluster-health-check` `<cluster-name> [--verbose] [--output-format json|text]`** - Perform comprehensive health check on HCP cluster and report issues
- **`/hcp:generate` `<provider> <cluster-description>`** - Generate ready-to-execute hypershift cluster creation commands from natural language descriptions

See [plugins/hcp/README.md](plugins/hcp/README.md) for detailed documentation.

### Hello World Plugin

A hello world plugin

**Commands:**
- **`/hello-world:echo` `[name]`** - Hello world plugin implementation

See [plugins/hello-world/README.md](plugins/hello-world/README.md) for detailed documentation.

### Jira Plugin

A plugin to automate tasks with Jira

**Commands:**
- **`/jira:backlog` `[project-key] [--assignee username] [--days-inactive N]`** - Find suitable JIRA tickets from the backlog to work on based on priority and activity
- **`/jira:categorize-activity-type` `<issue-key> [--auto-apply]`** - Categorize JIRA tickets into activity types using AI
- **`/jira:create-release-note` `<issue-key>`** - Generate bug fix release notes from Jira tickets and linked GitHub PRs
- **`/jira:create` `<type> [project-key] <summary> [--component <name>] [--version <version>] [--parent <key>]`** - Create Jira issues (story, epic, feature, task, bug, feature-request) with proper formatting
- **`/jira:generate-feature-doc` `<feature-key>`** - Generate comprehensive feature documentation from Jira feature and all related issues and PRs
- **`/jira:generate-test-plan` `[JIRA issue key] [GitHub PR URLs]`** - Generate test steps for a JIRA issue
- **`/jira:grooming` `[project-filter] [time-period] [--component component-name] [--label label-name] [--type issue-type] [--status status] [--story-points]`** - Analyze new bugs and cards added over a time period and generate grooming meeting agenda
- **`/jira:solve`** - Analyze a JIRA issue and create a pull request to solve it.
- **`/jira:status-rollup` `issue-id [--start-date YYYY-MM-DD] [--end-date YYYY-MM-DD]`** - Generate a status rollup comment for any JIRA issue based on all child issues and a given date range
- **`/jira:validate-blockers` `[target-version] [component-filter] [--bug issue-key]`** - Validate proposed release blockers using Red Hat OpenShift release blocker criteria

See [plugins/jira/README.md](plugins/jira/README.md) for detailed documentation.

### Lvms Plugin

LVMS (Logical Volume Manager Storage) plugin for troubleshooting and debugging storage issues

**Commands:**
- **`/lvms:analyze` `[must-gather-path|--live] [--component storage|operator|volumes]`** - Comprehensive LVMS troubleshooting - analyzes LVMCluster, volume groups, PVCs, and storage issues on live clusters or must-gather

See [plugins/lvms/README.md](plugins/lvms/README.md) for detailed documentation.

### Must Gather Plugin

A plugin to analyze and report on must-gather data

**Commands:**
- **`/must-gather:analyze` `[must-gather-path] [component]`** - Quick analysis of must-gather data - runs all analysis scripts and provides comprehensive cluster diagnostics
- **`/must-gather:ovn-dbs` `[must-gather-path]`** - Analyze OVN databases from a must-gather using ovsdb-tool
- **`/must-gather:windows` `[must-gather-path] [--component COMPONENT]`** - Analyze Windows node logs and issues in must-gather data

See [plugins/must-gather/README.md](plugins/must-gather/README.md) for detailed documentation.

### Node Plugin

Kubernetes and OpenShift node health monitoring and diagnostics

**Commands:**
- **`/node:cluster-node-health-check` `[--node <node-name>] [--verbose] [--output-format json|text]`** - Perform comprehensive health check on cluster nodes and report kubelet, CRI-O, and node-level issues

See [plugins/node/README.md](plugins/node/README.md) for detailed documentation.

### Node Tuning Plugin

Automatically create and apply tuned profile

**Commands:**
- **`/node-tuning:analyze-node-tuning` `[--sosreport PATH] [--format json|markdown] [--max-irq-samples N]`** - Analyze kernel/sysctl tuning from a live node or sosreport snapshot and propose NTO recommendations
- **`/node-tuning:generate-tuned-profile` `[profile-name] [--summary ...] [--sysctl ...] [options]`** - Generate a Tuned (tuned.openshift.io/v1) profile manifest for the Node Tuning Operator

See [plugins/node-tuning/README.md](plugins/node-tuning/README.md) for detailed documentation.

### Olm Plugin

OLM (Operator Lifecycle Manager) plugin for operator management and debugging

**Commands:**
- **`/olm:approve` `<operator-name> [namespace] [--all]`** - Approve pending InstallPlans for operator installations and upgrades
- **`/olm:catalog` `<list|add|remove|refresh|status> [arguments]`** - Manage catalog sources for discovering and installing operators
- **`/olm:debug` `<issue-description> <must-gather-path> [olm-version]`** - Debug OLM issues using must-gather logs and source code analysis
- **`/olm:diagnose` `[operator-name] [namespace] [--fix] [--cluster]`** - Diagnose and optionally fix common OLM and operator issues
- **`/olm:install` `<operator-name> [namespace] [channel] [source] [--approval=Automatic|Manual]`** - Install a day-2 operator using Operator Lifecycle Manager
- **`/olm:list` `[namespace] [--all-namespaces]`** - List installed operators in the cluster
- **`/olm:opm` `<action> [arguments...]`** - Execute opm (Operator Package Manager) commands for building and managing operator catalogs
- **`/olm:search` `[query] [--catalog <catalog-name>]`** - Search for available operators in catalog sources
- **`/olm:status` `<operator-name> [namespace]`** - Get detailed status and health information for an operator
- **`/olm:uninstall` `<operator-name> [namespace] [--remove-crds] [--remove-namespace]`** - Uninstall a day-2 operator and optionally remove its resources
- **`/olm:upgrade` `<operator-name> [namespace] [--channel=<channel>] [--approve]`** - Update an operator to the latest version or switch channels

See [plugins/olm/README.md](plugins/olm/README.md) for detailed documentation.

### Openshift Plugin

OpenShift development utilities and helpers

**Commands:**
- **`/openshift:add-enhancement` `[area] <name> <description> <jira>`** - Create a new OpenShift Enhancement Proposal
- **`/openshift:bootstrap-om`** - Bootstrap OpenShift Manager (OM) integration for OpenShift operators with automated resource discovery
- **`/openshift:bump-deps` `<dependency> [version] [--create-jira] [--create-pr]`** - Bump dependencies in OpenShift projects with automated analysis and PR creation
- **`/openshift:cluster-health-check` `[--verbose] [--output-format]`** - Perform comprehensive health check on OpenShift cluster and report issues
- **`/openshift:crd-review` `[repository-path]`** - Review Kubernetes CRDs against Kubernetes and OpenShift API conventions
- **`/openshift:create-cluster` `[release-image] [platform] [options]`** - Extract OpenShift installer from release image and create an OCP cluster
- **`/openshift:destroy-cluster` `[install-dir]`** - Destroy an OpenShift cluster created by create-cluster command
- **`/openshift:expand-test-case` `[test-idea-or-file-or-commands] [format]`** - Expand basic test ideas or existing oc commands into comprehensive test scenarios with edge cases in oc CLI or Ginkgo format
- **`/openshift:ironic-status`** - Check status of Ironic baremetal nodes in OpenShift cluster
- **`/openshift:new-e2e-test` `[test-specification]`** - Write and validate new OpenShift E2E tests using Ginkgo framework
- **`/openshift:rebase` `<tag>`** - Rebase OpenShift fork of an upstream repository to a new upstream release.
- **`/openshift:review-test-cases` `[file-path-or-test-code-or-commands]`** - Review test cases for completeness, quality, and best practices - accepts file path or direct oc commands/test code
- **`/openshift:visualize-ovn-topology`** - Generate and visualize OVN-Kubernetes network topology diagram

See [plugins/openshift/README.md](plugins/openshift/README.md) for detailed documentation.

### Origin Plugin

Helpers for openshift/origin development.

**Commands:**
- **`/origin:two-node-origin-pr-helper` `[--url PR_URL] [<pr>] [--depth quick|full]`** - Expert review tool for PRs that add or modify Two Node (Fencing or Arbiter) tests under test/extended/two_node/ in openshift/origin.

See [plugins/origin/README.md](plugins/origin/README.md) for detailed documentation.

### Prow Job Plugin

A plugin to analyze and inspect Prow CI job results

**Commands:**
- **`/prow-job:analyze-install-failure` `<prowjob-url>`** - Analyze OpenShift installation failures in Prow CI jobs
- **`/prow-job:analyze-resource` `prowjob-url resource-name`** - Analyze Kubernetes resource lifecycle in Prow job artifacts
- **`/prow-job:analyze-test-failure` `prowjob-url test-name`** - Analyzes test errors from console logs and Prow CI job artifacts
- **`/prow-job:extract-must-gather` `prowjob-url`** - Extract and decompress must-gather archives from Prow job artifacts

See [plugins/prow-job/README.md](plugins/prow-job/README.md) for detailed documentation.

### Session Plugin

A plugin to save and resume conversation sessions across long time intervals

**Commands:**
- **`/session:save-session` `[optional-description]`** - Save current conversation session to markdown file for future continuation

See [plugins/session/README.md](plugins/session/README.md) for detailed documentation.

### Sosreport Plugin

Analyze sosreport archives for system diagnostics and troubleshooting

**Commands:**
- **`/sosreport:analyze` `<path-to-sosreport> [--only <areas>] [--skip <areas>]`** - Analyze sosreport archive for system diagnostics and issues
- **`/sosreport:ovs-db` `[sosreport-path] [--db] [--flows-only] [--query <json>]`** - Analyze OVS data from sosreport (text files or database)

See [plugins/sosreport/README.md](plugins/sosreport/README.md) for detailed documentation.

### Test Coverage Plugin

Analyze code coverage and identify untested paths

**Commands:**
- **`/test-coverage:analyze` `<path-or-url> [--output <path>] [--priority <level>] [--test-structure-only]`** - Analyze test code structure without running tests to identify coverage gaps
- **`/test-coverage:gaps` `<test-file-or-url> [--output <path>]`** - Identify E2E test scenario gaps in OpenShift/Kubernetes tests (component-agnostic)

See [plugins/test-coverage/README.md](plugins/test-coverage/README.md) for detailed documentation.

### Utils Plugin

A generic utilities plugin serving as a catch-all for various helper commands and agents

**Commands:**
- **`/utils:address-reviews` `[PR number (optional - uses current branch if omitted)]`** - Fetch and address all PR review comments
- **`/utils:auto-approve-konflux-prs` `<target-repository>`** - Automate approving Konflux bot PRs for the given repository by adding /lgtm and /approve
- **`/utils:generate-test-plan` `[GitHub PR URLs]`** - Generate test steps for one or more related PRs
- **`/utils:gh-attention` `[--repo <org/repo>]`** - List PRs and issues requiring your attention
- **`/utils:placeholder`** - Placeholder command for the utils plugin
- **`/utils:process-renovate-pr` `<PR_NUMBER|open> [JIRA_PROJECT] [COMPONENT]`** - Process Renovate dependency PR(s) to meet repository contribution standards
- **`/utils:review-ai-helpers-overlap` `[--idea TEXT] [--pr NUMBER] [--verbose]`** - Review potential overlaps with existing ai-helpers (Claude Code Plugins, Commands, Skills, Sub-agents, or Hooks) and open PRs

See [plugins/utils/README.md](plugins/utils/README.md) for detailed documentation.

### Workspaces Plugin

Manage isolated git worktree workspaces for multi-repo development

**Commands:**
- **`/workspaces:create` `<short-description> <repo1|url> [repo2...]`** - Create a workspace with git worktrees for multi-repository development
- **`/workspaces:delete` `<workspace-name>`** - Delete a workspace and its git worktrees

See [plugins/workspaces/README.md](plugins/workspaces/README.md) for detailed documentation.

### Yaml Plugin

Generate comprehensive YAML documentation from Go struct definitions with sensible default values

**Commands:**
- **`/yaml:docs` `[file:StructName] [output.md]`** - Generate comprehensive YAML documentation from Go struct definitions with sensible default values

See [plugins/yaml/README.md](plugins/yaml/README.md) for detailed documentation.
