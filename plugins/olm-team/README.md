# OLM Team Plugin

Development utilities and onboarding tools for the OLM (Operator Lifecycle Manager) team.

## Overview

This plugin provides tools to help OLM team members quickly set up their development environment and understand the OLM ecosystem. It automates the process of forking, cloning, and configuring all necessary OLM repositories with proper remote configurations.

## Prerequisites

- Claude Code installed
- GitHub CLI (`gh`) installed and authenticated
- Git installed and configured
- SSH keys configured with GitHub (or HTTPS credentials)

## Commands

### `/olm-team:configure-agent` - Configure k8s-ocp-olm-expert Agent

Creates or updates the configuration file for the k8s-ocp-olm-expert agent with paths to local OLM repositories.

**Usage:**
```bash
/olm-team:configure-agent
```

**What it does:**
- Searches for OLM repositories in common locations
- Detects which repositories you have cloned locally
- Recommends running `/olm-team:dev-setup` if repositories are missing
- Helps you create a configuration file at `~/.config/claude-code/olm-agent-config.json`
- Validates all configured paths
- Enables the k8s-ocp-olm-expert agent to provide code-aware responses

**When to use:**
- **After `/olm-team:dev-setup`**: Automatically configures the agent with cloned repository paths
- **With existing repositories**: If you already have OLM repositories cloned, this command finds them
- **To update paths**: If you move repositories or clone additional ones

**Interactive process:**
1. Scans common directories for OLM repositories
2. Shows which repositories were found and which are missing
3. If < 80% of repositories found, recommends running `/olm-team:dev-setup`
4. Prompts for any missing repository paths
5. Validates all paths and creates configuration file
6. Displays summary and next steps

**Configuration file created:**
`~/.config/claude-code/olm-agent-config.json` with paths to:
- openshift-docs
- operator-lifecycle-manager, operator-registry, api (OLM v0 upstream)
- operator-framework-olm, operator-marketplace (OLM v0 downstream)
- operator-controller (OLM v1 upstream)
- operator-framework-operator-controller, cluster-olm-operator (OLM v1 downstream)

See [commands/configure-agent.md](commands/configure-agent.md) for full documentation.

---

### `/olm-team:dev-setup` - Development Environment Setup

Automates the complete onboarding process for new OLM team members by setting up all development repositories.

**Usage:**
```bash
/olm-team:dev-setup                          # Prompts for target directory
/olm-team:dev-setup ~/go/src/github.com/     # Uses specified directory
```

**What it does:**
- Explains the OLM repository ecosystem (upstream vs downstream, v0 vs v1)
- Forks all OLM repositories to your GitHub account (if not already forked)
- Clones repositories locally with "origin" pointing to your fork
- Adds "upstream" remote pointing to the original repository
- Provides educational context about each repository's purpose
- Generates a comprehensive summary with next steps

**Repositories configured:**

**OLM v0 (Traditional Architecture)**
- Upstream:
  - `operator-framework/operator-registry` - Catalog and bundle management
  - `operator-framework/operator-lifecycle-manager` - Core OLM v0 runtime
  - `operator-framework/api` - API definitions and CRD schemas
- Downstream:
  - `openshift/operator-framework-olm` - OpenShift distribution of OLM v0
  - `operator-framework/operator-marketplace` - OperatorHub integration

**OLM v1 (Next-Generation Architecture)**
- Upstream:
  - `operator-framework/operator-controller` - Core OLM v1 runtime
- Downstream:
  - `openshift/operator-framework-operator-controller` - OpenShift distribution of OLM v1
  - `openshift/cluster-olm-operator` - OLM cluster operator for OpenShift

**Arguments:**
- `target-directory` (optional): Base directory for cloning repositories
  - Common choices: `~/go/src/github.com/`, `~/src/`, `~/code/olm/`
  - If not provided, you'll be prompted to choose

**Directory structure created:**
```
<target-directory>/
  <github-username>/
    operator-registry/
      .git/
        config (origin → your fork, upstream → operator-framework)
    operator-lifecycle-manager/
    api/
    operator-framework-olm/
    operator-marketplace/
    operator-controller/
    operator-framework-operator-controller/
    cluster-olm-operator/
```

See [commands/dev-setup.md](commands/dev-setup.md) for full documentation.

---

## Understanding the OLM Ecosystem

### Upstream vs Downstream

**Upstream (operator-framework)**:
- Community-driven development
- Latest features and improvements
- Base for all downstream distributions

**Downstream (openshift)**:
- OpenShift-specific customizations
- Enterprise features and security patches
- What ships in Red Hat OpenShift products

### OLM v0 vs OLM v1

**OLM v0 (Traditional)**:
- Current production architecture in OpenShift
- Uses CSV, Subscription, InstallPlan resources
- Mature and battle-tested

**OLM v1 (Next-Generation)**:
- Simplified architecture
- Better dependency resolution
- Uses ClusterExtension and Catalog resources
- Active development, future of OLM

## Example Workflow

### Initial Setup
```bash
# Set up your entire development environment
/olm-team:dev-setup ~/go/src/github.com/

# The command will:
# 1. Fork all 8 OLM repositories to your GitHub account
# 2. Clone them to ~/go/src/github.com/<your-username>/
# 3. Configure origin (fork) and upstream (original) remotes
# 4. Explain each repository's purpose
```

### After Setup - Typical Development Workflow
```bash
# Navigate to a repository
cd ~/go/src/github.com/<your-username>/operator-lifecycle-manager

# Create a feature branch
git checkout -b feature/my-feature

# Make changes and commit
git add .
git commit -m "Add new feature"

# Push to your fork
git push origin feature/my-feature

# Create pull request (from your fork to upstream)
gh pr create --web

# Keep your fork in sync with upstream
git fetch upstream
git checkout main  # or master, depending on the repo's default branch
git merge upstream/HEAD
git push origin HEAD
```

## Development Resources

After running `/olm-team:dev-setup`, you'll have access to:

1. **Source Code**: All OLM repositories cloned and ready for development
2. **Repository Context**: Understanding of each repository's role
3. **Remote Configuration**: Proper setup for contributing (fork + upstream)
4. **Next Steps Guide**: Commands and workflows for getting started

## k8s-ocp-olm-expert Agent

This plugin includes the **k8s-ocp-olm-expert agent**, an elite software engineering agent with deep expertise in Kubernetes, OpenShift, and OLM.

### What it does

The agent automatically engages when you:
- Debug Kubernetes resources (pods, deployments, etc.)
- Work with OpenShift-specific features
- Develop or troubleshoot operators using OLM
- Review manifests, CRDs, or operator bundles
- Ask questions about k8s/OCP/OLM concepts

### Features

- **Documentation Integration**: Searches local openshift-docs and provides file references with line numbers
- **Code-Aware Responses**: References upstream/downstream OLM v0 and v1 source code
- **Documentation Gap Identification**: Identifies what's documented and what's missing
- **Production-Ready Advice**: Security-minded, version-aware recommendations

### Configuration Required

The agent requires configuration to know where your local repositories are located.

**Quick setup:**
```bash
# Option 1: New team member (clones all repos + configures agent)
/olm-team:dev-setup

# Option 2: Have repos already (just configures agent)
/olm-team:configure-agent
```

### Usage Example

```
User: Where is catalogd CA configuration documented in openshift-docs?

Agent: [k8s-ocp-olm-expert automatically engages]

## Documentation Found

**CA Certificate Configuration for Image Registries:**
- **File:** `modules/images-configuration-cas.adoc` (line 8): "Configuring additional trust stores for image registry access"
...

## Documentation Gaps

**What's missing:**
- No specific documentation for catalogd CA certificate configuration
...
```

See [skills/k8s-ocp-olm-expert/README.md](skills/k8s-ocp-olm-expert/README.md) for detailed agent documentation.

---

## Additional Resources

- **OLM Documentation**: https://olm.operatorframework.io/
- **OpenShift OLM Docs**: https://docs.openshift.com/container-platform/latest/operators/
- **Contributing Guides**: Check `CONTRIBUTING.md` in each repository
- **OLM Slack**: Join the #olm channel in Kubernetes Slack
- **Agent Skill Documentation**: [skills/k8s-ocp-olm-expert/SKILL.md](skills/k8s-ocp-olm-expert/SKILL.md)

## Troubleshooting

### GitHub CLI Not Authenticated
```bash
gh auth login
# Follow the prompts to authenticate
```

### SSH Key Issues
```bash
# Test SSH connection
ssh -T git@github.com

# If fails, set up SSH keys
ssh-keygen -t ed25519 -C "your-email@example.com"
# Add key to GitHub: https://github.com/settings/keys
```

### Directory Permission Issues
Choose a directory where you have write permissions, typically:
- Your home directory: `~/`
- Your user-specific directories: `~/go/`, `~/src/`, `~/code/`

Avoid system directories like `/usr/`, `/opt/` which require elevated permissions.

### Fork Already Exists
If you've already forked a repository, the command will detect this and skip the fork step, proceeding directly to cloning.

### Repository Already Cloned
If a repository is already cloned in the target directory, the command will ask if you want to skip it or re-clone.

## Contributing

To add new commands to this plugin:

1. Create a new `.md` file in `plugins/olm-team/commands/`
2. Follow the command definition format (see existing commands)
3. Update this README with the new command documentation
4. Run `make lint` to validate the plugin structure

## Support

For issues or feature requests, please file an issue at:
https://github.com/openshift-eng/ai-helpers/issues
