# OpenShift Plugin

OpenShift development utilities and workflow helpers for Claude Code.

## Commands

### `/openshift:new-e2e-test`

Write and validate new OpenShift E2E tests using the Ginkgo framework.

### `/openshift:rebase`

Rebase an OpenShift fork of an upstream repository to a new upstream release.

This command automates the complex process of rebasing OpenShift forks following the UPSTREAM commit conventions.

### `/openshift:bump-deps`

Automates the process of bumping dependencies in OpenShift organization projects. It analyzes the dependency, determines
the appropriate version to bump to, updates the necessary files (go.mod, go.sum, package.json, etc.), runs tests,
and optionally creates Jira tickets and pull requests.

### `/openshift:analyze-pattern`

Analyze how OpenShift and Kubernetes repositories implement a design pattern and get custom recommendations.

This command searches GitHub for pattern implementations, analyzes common approaches, and provides context-aware guidance tailored to your repository type.

### `/openshift:create-cluster`

Extract OpenShift installer from release image and create an OCP cluster.

This command automates the process of extracting the installer from a release image and creating a new OpenShift cluster on various platforms (AWS, Azure, GCP, vSphere, OpenStack).

### `/openshift:destroy-cluster`

Destroy an OpenShift cluster created by the create-cluster command.

This command safely destroys a cluster and cleans up all cloud resources. Includes safety confirmations and optional backup of cluster information.

### `/openshift:ironic-status`

Check status of Ironic baremetal nodes in OpenShift cluster.

See the [commands/](commands/) directory for full documentation of each command.

## Installation

### From the Claude Code Plugin Marketplace

1. **Add the marketplace** (if not already added):
   ```bash
   /plugin marketplace add openshift-eng/ai-helpers
   ```

2. **Install the openshift plugin**:
   ```bash
   /plugin install openshift@ai-helpers
   ```

3. **Use the commands**:
   ```bash
   /openshift:bump-deps k8s.io/api
   ```

## Available Commands

### E2E Test Generation

#### `/openshift:new-e2e-test` - Generate E2E Tests

Generate end-to-end tests for OpenShift features.

See [commands/new-e2e-test.md](commands/new-e2e-test.md) for full documentation.

### Dependency Bumping

#### `/openshift:bump-deps` - Bump Dependencies

Automates dependency updates in OpenShift projects with comprehensive analysis, testing, and optional Jira ticket and PR creation.

**Basic Usage:**
```bash
# Bump to latest version
/openshift:bump-deps k8s.io/api

# Bump to specific version
/openshift:bump-deps golang.org/x/net v0.20.0

# Bump with Jira ticket
/openshift:bump-deps github.com/spf13/cobra --create-jira

# Bump with Jira ticket and PR
/openshift:bump-deps github.com/prometheus/client_golang --create-jira --create-pr
```

**Supported Dependency Types:**
- Go modules (go.mod)
- npm packages (package.json)
- Container images (Dockerfile)
- Python packages (requirements.txt, pyproject.toml)

**Key Features:**
- Automatic version discovery and compatibility checking
- Changelog and breaking change analysis
- Automated testing (unit, integration, e2e)
- Jira ticket creation with comprehensive details
- Pull request creation with proper formatting
- Handles direct and indirect dependencies
- Security vulnerability detection
- Batch updates for related dependencies

**Arguments:**
- `<dependency>` (required): Package identifier (e.g., `k8s.io/api`, `@types/node`)
- `[version]` (optional): Target version (defaults to latest stable)
- `--create-jira`: Create a Jira ticket for the update
- `--create-pr`: Create a pull request (implies --create-jira)
- `--jira-project <PROJECT>`: Specify Jira project (default: auto-detect)
- `--component <COMPONENT>`: Specify Jira component (default: auto-detect)
- `--skip-tests`: Skip running tests (creates draft PR)
- `--force`: Force update even if tests fail

**Examples:**

1. Simple bump to latest:
   ```bash
   /openshift:bump-deps k8s.io/client-go
   ```

2. Bump with custom Jira project:
   ```bash
   /openshift:bump-deps sigs.k8s.io/controller-runtime --create-jira --jira-project OCPBUGS
   ```

3. Bump container image:
   ```bash
   /openshift:bump-deps registry.access.redhat.com/ubi9/ubi-minimal
   ```

4. Batch update Kubernetes dependencies:
   ```bash
   /openshift:bump-deps "k8s.io/*"
   ```

See [commands/bump-deps.md](commands/bump-deps.md) for full documentation.

### Pattern Analysis

#### `/openshift:analyze-pattern` - Analyze Design Pattern Implementations

Analyze how OpenShift and Kubernetes repositories implement specific design patterns and get context-aware recommendations tailored to your repository.

**Basic Usage:**
```bash
# Analyze NetworkPolicy implementations
/openshift:analyze-pattern NetworkPolicy

# Analyze ValidatingWebhook across multiple orgs
/openshift:analyze-pattern ValidatingWebhook --orgs openshift,kubernetes,kubernetes-sigs

# Default: comprehensive analysis (50 repos)
/openshift:analyze-pattern NetworkPolicy

# Quick analysis with fewer repos (faster)
/openshift:analyze-pattern MutatingWebhook --repos 10

# Minimal analysis (fastest)
/openshift:analyze-pattern CustomResourceDefinition --repos 5

# Force refresh cached analysis
/openshift:analyze-pattern NetworkPolicy --refresh
```

**What It Does:**
- Searches GitHub for repositories implementing the pattern
- Clones and analyzes top repositories
- Detects common implementation approaches
- Identifies key features and configurations
- Finds repositories most similar to yours
- Generates context-aware recommendations

**Key Features:**
- Analyzes up to 50 repositories by default for comprehensive insights
- Statistical analysis ("X% of repos use approach Y") with high confidence
- Context detection (understands your project type)
- Similarity matching (finds repos like yours)
- Getting started steps tailored to your repo
- Caches results for fast subsequent runs

**Arguments:**
- `<pattern>` (required): Pattern name (e.g., NetworkPolicy, ValidatingWebhook)
- `--orgs <org1,org2>`: GitHub organizations to search (default: openshift,kubernetes)
- `--repos <N>`: Maximum repos to analyze (default: 50, range: 3-50)
- `--refresh`: Force refresh cached analysis

**Examples:**

1. Basic pattern analysis:
   ```bash
   /openshift:analyze-pattern NetworkPolicy
   ```
   Output:
   - 6/7 repos use ValidatingWebhooks
   - 7/7 repos use namespace label selectors
   - Follow cluster-network-operator (most similar to your operator project)
   - Step-by-step implementation guide

2. Analyze across multiple orgs:
   ```bash
   /openshift:analyze-pattern CustomResourceDefinition --orgs openshift,kubernetes,kubernetes-sigs
   ```

3. Quick analysis with fewer repos:
   ```bash
   /openshift:analyze-pattern MutatingWebhook --repos 5
   ```

**Prerequisites:**
- Python 3.6+ (check: `python3 --version`)
- Git installed (check: `git --version`)
- Network access to GitHub
- (Optional) `GITHUB_TOKEN` environment variable for higher API rate limits

**Output:**
- Repositories analyzed and ranked by quality
- Statistical insights on common patterns
- Context-aware recommendations for your repo
- References to best implementations
- Cached results in `.work/design-patterns/<pattern>/`

**Cache Management:**
```bash
# View cache size
du -sh .work/design-patterns/

# Clean up a specific pattern's cache
rm -rf .work/design-patterns/NetworkPolicy/

# Clean up all pattern analysis cache
rm -rf .work/design-patterns/

# Cache auto-expires after 7 days (forces re-analysis)
```

**Use Cases:**
- Learning how to implement a new pattern
- Understanding common approaches vs unique ones
- Getting started guidance tailored to your project
- Finding high-quality reference implementations
- Avoiding common implementation mistakes

**Tier 1 MVP Features:**
- GitHub repository search and ranking
- Pattern detection and statistical analysis
- Context detection (project type, existing patterns)
- Similarity matching with analyzed repos
- Getting started recommendations

See [commands/analyze-pattern.md](commands/analyze-pattern.md) for full documentation.

### Cluster Management

#### `/openshift:create-cluster` - Create OCP Clusters

Extract the OpenShift installer from a release image and create a new OpenShift Container Platform cluster. This command automates installer extraction and cluster creation for development and testing purposes.

**⚠️ Important**: This is a last-resort tool. For most workflows, use **Cluster Bot**, **Gangway**, or **Multi-PR Testing in CI** instead. Only use this when you need full control over cluster configuration or are testing installer changes.

**Basic Usage:**
```bash
# Interactive mode (prompts for all options)
/openshift:create-cluster

# With release image and platform
/openshift:create-cluster quay.io/openshift-release-dev/ocp-release:4.21.0-ec.2-x86_64 aws

# With CI build
/openshift:create-cluster registry.ci.openshift.org/ocp/release:4.21.0-0.ci-2025-10-27-031915 gcp
```

**Prerequisites:**
- OpenShift CLI (`oc`) installed
- Cloud provider credentials configured (AWS, Azure, GCP, etc.)
- Pull secret from [Red Hat Console](https://console.redhat.com/openshift/install/pull-secret)
- Domain/DNS configuration (e.g., Route53 hosted zone for AWS)

**Supported Platforms:**
- AWS (Amazon Web Services)
- Azure (Microsoft Azure)
- GCP (Google Cloud Platform)
- vSphere (VMware vSphere)
- OpenStack
- none (Bare metal / platform-agnostic)

**Key Features:**
- Automatic installer extraction from release images
- Version-specific installer caching
- Interactive configuration generation
- Post-installation verification
- Cluster credentials and access information

**Arguments:**
- `[release-image]` (optional): OpenShift release image (prompted if not provided)
- `[platform]` (optional): Target platform (prompted if not provided)

**Examples:**

1. Create cluster with production release on AWS:
   ```bash
   /openshift:create-cluster quay.io/openshift-release-dev/ocp-release:4.21.0-ec.2-x86_64 aws
   ```

2. Create cluster with CI build interactively:
   ```bash
   /openshift:create-cluster registry.ci.openshift.org/ocp/release:4.21.0-0.ci-2025-10-27-031915
   ```

3. Full interactive mode:
   ```bash
   /openshift:create-cluster
   ```

See [commands/create-cluster.md](commands/create-cluster.md) for full documentation.

#### `/openshift:destroy-cluster` - Destroy OCP Clusters

Safely destroy an OpenShift Container Platform cluster that was created using `/openshift:create-cluster`. This command handles cleanup of all cloud resources with built-in safety confirmations.

**⚠️ WARNING**: This operation is **irreversible** and permanently deletes all cluster resources and data.

**Basic Usage:**
```bash
# Interactive mode (searches for installation directories)
/openshift:destroy-cluster

# With specific installation directory
/openshift:destroy-cluster ./my-cluster-install-20251028-120000

# With full path
/openshift:destroy-cluster /path/to/cluster-install-dir
```

**Safety Features:**
- Requires explicit "yes" confirmation before destruction
- Displays cluster information before proceeding
- Optional backup of cluster credentials and metadata
- Validates installation directory and metadata
- Provides manual cleanup instructions if automated cleanup fails

**What Gets Deleted:**
- All cluster VMs and compute resources
- Load balancers and networking resources
- Storage volumes and persistent data
- DNS records (if managed by installer)
- All cluster configuration

**Arguments:**
- `[install-dir]` (optional): Path to cluster installation directory (prompted if not provided)

**Examples:**

1. Destroy cluster interactively:
   ```bash
   /openshift:destroy-cluster
   ```

2. Destroy specific cluster:
   ```bash
   /openshift:destroy-cluster ./test-cluster-install-20251028-120000
   ```

See [commands/destroy-cluster.md](commands/destroy-cluster.md) for full documentation.

## Development

### Adding New Commands

To add a new command to this plugin:

1. Create a new markdown file in `commands/`:
   ```bash
   touch plugins/openshift/commands/your-command.md
   ```

2. Follow the structure from existing commands (see `commands/bump-deps.md` for reference)

3. Include these sections:
   - Name
   - Synopsis
   - Description
   - Implementation
   - Return Value
   - Examples
   - Arguments
   - Error Handling
   - Notes

4. Test your command:
   ```bash
   /openshift:your-command
   ```

### Plugin Structure

```
plugins/openshift/
├── .claude-plugin/
│   └── marketplace.json          # Plugin metadata
├── commands/
│   ├── bump-deps.md              # Dependency bumping command
│   ├── new-e2e-test.md           # E2E test generation
│   └── ...                        # Additional commands
└── README.md                      # This file
```

## Related Plugins

- **utils** - General utilities including `process-renovate-pr` for processing Renovate PRs
- **jira** - Jira automation and issue management
- **git** - Git workflow automation
- **ci** - OpenShift CI integration

## Contributing

Contributions are welcome! When adding new OpenShift-related commands:

1. Ensure the command is specific to OpenShift development workflows
2. Follow the existing command structure and documentation format
3. Include comprehensive examples and error handling
4. Test with real OpenShift projects
5. Update this README with new command documentation

## License

See [LICENSE](../../LICENSE) for details.
