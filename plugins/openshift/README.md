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

### `/openshift:create-cluster`

Extract OpenShift installer from release image and create an OCP cluster.

This command automates the process of extracting the installer from a release image and creating a new OpenShift cluster on various platforms (AWS, Azure, GCP, vSphere, OpenStack).

### `/openshift:destroy-cluster`

Destroy an OpenShift cluster created by the create-cluster command.

This command safely destroys a cluster and cleans up all cloud resources. Includes safety confirmations and optional backup of cluster information.

### `/openshift:ironic-status`

Check status of Ironic baremetal nodes in OpenShift cluster.

### Node Kernel Diagnostics

Kernel-level networking diagnostics for OpenShift/OVN-Kubernetes nodes:

- `/openshift:node-kernel-conntrack` - Connection tracking inspection
- `/openshift:node-kernel-iptables` - IPv4/IPv6 packet filter rules
- `/openshift:node-kernel-nft` - nftables packet filtering
- `/openshift:node-kernel-ip` - IP routing and network interfaces

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
│   └── plugin.json                    # Plugin metadata
├── commands/
│   ├── bump-deps.md                   # Dependency bumping command
│   ├── new-e2e-test.md                # E2E test generation
│   ├── node-kernel-conntrack.md       # Kernel: Connection tracking
│   ├── node-kernel-ip.md              # Kernel: IP routing and interfaces
│   ├── node-kernel-iptables.md        # Kernel: iptables rules
│   ├── node-kernel-nft.md             # Kernel: nftables rules
│   └── ...                             # Additional commands
├── skills/
│   ├── generating-ovn-topology/       # OVN topology visualization
│   └── openshift-node-kernel/         # Node kernel diagnostics helpers
│       └── kernel-helper.sh           # Helper for kernel networking commands
└── README.md                           # This file
```

## Node Kernel Diagnostics

Kernel-level networking diagnostics and troubleshooting tools for OpenShift/OVN-Kubernetes nodes. These commands provide direct access to kernel networking subsystems including conntrack, iptables, nftables, and IP routing configuration.

### Available Commands

#### `/openshift:node-kernel-conntrack`

Interact with the connection tracking system of a Kubernetes node to discover currently tracked connections.

**Usage:**
```bash
/openshift:node-kernel-conntrack <node> <image> [--command <cmd>] [--filter <params>]
```

**Example:**
```bash
/openshift:node-kernel-conntrack worker-2 registry.redhat.io/rhel9/support-tools --command -L
```

#### `/openshift:node-kernel-iptables`

Inspect IPv4 and IPv6 packet filter rules in the Linux kernel.

**Usage:**
```bash
/openshift:node-kernel-iptables <node> <image> --command <cmd> [--table <table>] [--filter <params>]
```

**Example:**
```bash
/openshift:node-kernel-iptables worker-2 registry.redhat.io/rhel9/support-tools --command -L --table nat --filter "-nv4"
```

#### `/openshift:node-kernel-nft`

Inspect nftables packet filtering and classification rules.

**Usage:**
```bash
/openshift:node-kernel-nft <node> <image> --command <cmd> [--family <family>]
```

**Example:**
```bash
/openshift:node-kernel-nft worker-2 registry.redhat.io/rhel9/support-tools --command "list tables" --family inet
```

#### `/openshift:node-kernel-ip`

Inspect routing, network devices, and interfaces configuration.

**Usage:**
```bash
/openshift:node-kernel-ip <node> <image> --command <cmd> [--options <opts>] [--filter <params>]
```

**Example:**
```bash
/openshift:node-kernel-ip worker-2 registry.redhat.io/rhel9/support-tools --command "route show" --options "-4"
```

### Common Use Cases

- Debug connection tracking and NAT issues
- Analyze iptables/nftables rules for traffic flow problems
- Troubleshoot routing and interface configuration
- Investigate OVN-Kubernetes networking at the kernel level

See individual command documentation in [commands/](commands/) for detailed usage.

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
