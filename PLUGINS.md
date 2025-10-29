# Available Plugins

This document lists all available Claude Code plugins and their commands in the ai-helpers repository.

- [Agendas](#agendas-plugin)
- [Ci](#ci-plugin)
- [Doc](#doc-plugin)
- [Git](#git-plugin)
- [Hello World](#hello-world-plugin)
- [Jira](#jira-plugin)
- [Microshift Prow Job](#microshift-prow-job-plugin)
- [Must Gather](#must-gather-plugin)
- [Openshift](#openshift-plugin)
- [Prow Job](#prow-job-plugin)
- [Session](#session-plugin)
- [Utils](#utils-plugin)
- [Yaml](#yaml-plugin)

### Agendas Plugin

A plugin to create various meeting agendas

**Commands:**
- **`/agendas:outcome-refinement`** - Analyze the list of JIRA outcome issues to prepare an outcome refinement meeting agenda.

See [plugins/agendas/README.md](plugins/agendas/README.md) for detailed documentation.

### Ci Plugin

Miscellaenous tools for working with OpenShift CI

**Commands:**
- **`/ci:ask-sippy` `[question]`** - Ask the Sippy AI agent questions about OpenShift CI payloads, jobs, and test results
- **`/ci:query-job-status` `<execution-id>`** - Query the status of a gangway job execution by ID
- **`/ci:trigger-periodic` `<job-name> [ENV_VAR=value ...]`** - Trigger a periodic gangway job with optional environment variable overrides
- **`/ci:trigger-postsubmit` `<job-name> <org> <repo> <base-ref> <base-sha> [ENV_VAR=value ...]`** - Trigger a postsubmit gangway job with repository refs
- **`/ci:trigger-presubmit` `<job-name> <org> <repo> <base-ref> <base-sha> <pr-number> <pr-sha> [ENV_VAR=value ...]`** - Trigger a presubmit gangway job (typically use GitHub Prow commands instead)

See [plugins/ci/README.md](plugins/ci/README.md) for detailed documentation.

### Doc Plugin

A plugin for engineering documentation and notes

**Commands:**
- **`/doc:note` `[task description]`** - Generate professional engineering notes and append them to a log file

See [plugins/doc/README.md](plugins/doc/README.md) for detailed documentation.

### Git Plugin

Git workflow automation and utilities

**Commands:**
- **`/git:cherry-pick-by-patch` `<commit_hash>`** - Cherry-pick git commit into current branch by "patch" command
- **`/git:commit-suggest` `[N]`** - Generate Conventional Commits style commit messages or summarize existing commits
- **`/git:debt-scan`** - Analyze technical debt indicators in the repository
- **`/git:summary`** - Show current branch, git status, and recent commits for quick context

See [plugins/git/README.md](plugins/git/README.md) for detailed documentation.

### Hello World Plugin

A hello world plugin

**Commands:**
- **`/hello-world:echo` `[name]`** - Hello world plugin implementation

See [plugins/hello-world/README.md](plugins/hello-world/README.md) for detailed documentation.

### Jira Plugin

A plugin to automate tasks with Jira

**Commands:**
- **`/jira:create` `<type> [project-key] <summary> [--component <name>] [--version <version>] [--parent <key>]`** - Create Jira issues (story, epic, feature, task, bug) with proper formatting
- **`/jira:generate-test-plan` `[JIRA issue key] [GitHub PR URLs]`** - Generate test steps for a JIRA issue
- **`/jira:grooming` `[project-filter] [time-period] [--component component-name] [--label label-name]`** - Analyze new bugs and cards added over a time period and generate grooming meeting agenda
- **`/jira:solve`** - Analyze a JIRA issue and create a pull request to solve it.
- **`/jira:status-rollup` `issue-id [--start-date YYYY-MM-DD] [--end-date YYYY-MM-DD]`** - Generate a status rollup comment for any JIRA issue based on all child issues and a given date range

See [plugins/jira/README.md](plugins/jira/README.md) for detailed documentation.

### Microshift Prow Job Plugin

Analyze MicroShift Prow CI jobs

**Commands:**
- **`/microshift-prow-job:analyze-job` `<job-url>`** - Analyze a MicroShift Prow CI job execution
- **`/microshift-prow-job:analyze-test-scenario` `<job-url> <scenario-name>`** - Analyze MicroShift Test Scenario results

See [plugins/microshift-prow-job/README.md](plugins/microshift-prow-job/README.md) for detailed documentation.

### Must Gather Plugin

A plugin to analyze and report on must-gather data

**Commands:**
- **`/must-gather:analyze` `[must-gather-path] [component]`** - Quick analysis of must-gather data - runs all analysis scripts and provides comprehensive cluster diagnostics

See [plugins/must-gather/README.md](plugins/must-gather/README.md) for detailed documentation.

### Openshift Plugin

OpenShift development utilities and helpers

**Commands:**
- **`/openshift:bump-deps` `<dependency> [version] [--create-jira] [--create-pr]`** - Bump dependencies in OpenShift projects with automated analysis and PR creation
- **`/openshift:create-cluster` `"[release-image] [platform] [options]"`** - Extract OpenShift installer from release image and create an OCP cluster
- **`/openshift:destroy-cluster` `"[install-dir]"`** - Destroy an OpenShift cluster created by create-cluster command
- **`/openshift:new-e2e-test` `[test-specification]`** - Write and validate new OpenShift E2E tests using Ginkgo framework
- **`/openshift:rebase` `<tag>`** - Rebase OpenShift fork of an upstream repository to a new upstream release.

See [plugins/openshift/README.md](plugins/openshift/README.md) for detailed documentation.

### Prow Job Plugin

A plugin to analyze and inspect Prow CI job results

**Commands:**
- **`/prow-job:analyze-resource` `prowjob-url resource-name`** - Analyze Kubernetes resource lifecycle in Prow job artifacts
- **`/prow-job:analyze-test-failure` `prowjob-url test-name`** - Analyzes test errors from console logs and Prow CI job artifacts
- **`/prow-job:extract-must-gather` `prowjob-url`** - Extract and decompress must-gather archives from Prow job artifacts

See [plugins/prow-job/README.md](plugins/prow-job/README.md) for detailed documentation.

### Session Plugin

A plugin to save and resume conversation sessions across long time intervals

**Commands:**
- **`/session:save-session` `[optional-description]`** - Save current conversation session to markdown file for future continuation

See [plugins/session/README.md](plugins/session/README.md) for detailed documentation.

### Utils Plugin

A generic utilities plugin serving as a catch-all for various helper commands and agents

**Commands:**
- **`/utils:address-reviews` `[PR number (optional - uses current branch if omitted)]`** - Fetch and address all PR review comments
- **`/utils:generate-test-plan` `[GitHub PR URLs]`** - Generate test steps for one or more related PRs
- **`/utils:placeholder`** - Placeholder command for the utils plugin
- **`/utils:process-renovate-pr` `<PR_NUMBER|open> [JIRA_PROJECT] [COMPONENT]`** - Process Renovate dependency PR(s) to meet repository contribution standards

See [plugins/utils/README.md](plugins/utils/README.md) for detailed documentation.

### Yaml Plugin

Generate comprehensive YAML documentation from Go struct definitions with sensible default values

**Commands:**
- **`/yaml:docs` `[file:StructName] [output.md]`** - Generate comprehensive YAML documentation from Go struct definitions with sensible default values

See [plugins/yaml/README.md](plugins/yaml/README.md) for detailed documentation.
