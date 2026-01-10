# k8s-bumpup Plugin

Automate Kubernetes version rebasing and dependency updates across Go repositories.

## Overview

The `k8s-bumpup` plugin provides commands to safely update Kubernetes dependencies in Go projects that use `k8s.io/*` libraries. It handles the complete workflow from analyzing breaking changes to updating dependencies, running tests, and creating commits.

## Features

- **Dependency Auditing**: Analyze breaking changes between Kubernetes versions
- **Automated Updates**: Update all k8s.io dependencies to target version
- **Conflict Detection**: Identify deprecated and removed APIs in your codebase
- **Test Validation**: Run builds and tests to verify updates
- **Multi-Repository Support**: Process multiple repositories in a single workflow
- **Changelog Generation**: Create detailed commit messages documenting changes

## Commands

### `/k8s-bumpup:batch-by-group`

**NEW** Rebase Kubernetes dependencies across a group of related repositories.

```
/k8s-bumpup:batch-by-group <group-name> [options]
```

**Example:**
```
/k8s-bumpup:batch-by-group corenet
```

Automatically fetches and uses the latest Kubernetes release. No version specification needed!

**What it does:**
1. Loads repository group configuration (network, storage, operators, etc.)
2. Clones fresh copies of all repos in the group
3. Runs audit analysis for each repository
4. Presents consolidated audit summary
5. Creates feature branches in each repo
6. Updates dependencies, builds, and tests each repo
7. Commits changes with detailed messages
8. Generates comprehensive group-wide summary
9. Offers to push branches and create PRs

**Available Groups:**
- `corenet` - Core networking components (multus-cni, ovn-kubernetes, cluster-network-operator)
- `storage` - Storage operators and CSI drivers
- `operators` - Core cluster operators
- `monitoring` - Monitoring and observability

**Output:**
- Cloned repositories: `.work/k8s-batch-by-group/${GROUP}/${TIMESTAMP}/repos/`
- Group summary: `.work/k8s-batch-by-group/${GROUP}/${TIMESTAMP}/rebase-summary.md`
- Individual audit reports and logs

---

### `/k8s-bumpup:rebase-repo`

Complete workflow to rebase Kubernetes dependencies across one or more repositories.

```
/k8s-bumpup:rebase-repo <target-version> <repository-path> [additional-repos...]
```

**Example:**
```
/k8s-bumpup:rebase-repo v1.29.0 ./my-operator ./my-controller
```

**What it does:**
1. Runs audit analysis for all repositories
2. Presents consolidated audit summary
3. Requests user confirmation
4. Creates feature branches
5. Updates dependencies
6. Runs builds and tests
7. Commits changes with detailed messages
8. Generates comprehensive summary report
9. Offers to push branches and create PRs

**Output:**
- Feature branches with commits
- Comprehensive summary: `.work/k8s-bumpup/${TIMESTAMP}/rebase-summary.md`
- Build/test logs for each repository
- Individual audit reports

## Typical Workflows

### Workflow 1: Group Rebase (Recommended for Related Repos)

Rebase multiple related repositories together:

```
/k8s-bumpup:batch-by-group corenet v0.34.2
```

This will:
1. Clone fresh copies of all corenet repos (multus-cni, ovn-kubernetes, sdn, cluster-network-operator)
2. Audit each repository for breaking changes
3. Show consolidated risk assessment
4. Request your confirmation
5. Rebase each repo sequentially
6. Generate group-wide summary with all results
7. Offer to push branches and create PRs

**Advantages:**
- Consistent versioning across related components
- Coordinated testing and deployment
- Single comprehensive summary
- Automatic PR cross-referencing
- Isolated workspace (doesn't modify existing clones)

### Workflow 2: Single Repository Update

Use the rebase-repo command for a single repository:

```
/k8s-bumpup:rebase-repo v1.29.0 ./my-repo
```

This will:
1. Audit the repository for breaking changes
2. Show audit summary and ask for confirmation
3. Update dependencies to target version
4. Build and test the project
5. Create a feature branch with committed changes
6. Generate summary report

### Workflow 3: Multiple Repositories

Use the all-in-one command for handling multiple related repositories:

```
/k8s-bumpup:rebase-repo v1.29.0 ./operator ./controller ./webhook
```

This will:
- Audit all repositories
- Show combined impact analysis
- Request confirmation
- Process each repository
- Create branches and commits
- Generate summary report

### Workflow 4: Incremental Major Version Update

When crossing multiple Kubernetes minor versions (e.g., v1.27 → v1.30), consider incremental updates:

```
/k8s-bumpup:rebase-repo v1.28.0 ./my-app
# Test thoroughly
/k8s-bumpup:rebase-repo v1.29.0 ./my-app
# Test thoroughly
/k8s-bumpup:rebase-repo v1.30.0 ./my-app
```

## Understanding Audit Reports

Audit reports include:

### Risk Levels

- **LOW**: Patch version updates, no breaking changes detected
- **MEDIUM**: Minor version update with deprecation warnings
- **HIGH**: API removals, significant breaking changes, or multi-version jump

### Common Breaking Changes

| Kubernetes Version | Common Breaking Changes |
|-------------------|-------------------------|
| v1.22 | Removed beta Ingress, RBAC, webhook APIs |
| v1.25 | Removed PodSecurityPolicy, beta CronJob |
| v1.26 | Removed beta HorizontalPodAutoscaler v2beta2 |
| v1.29 | Removed flowcontrol v1beta2, v1beta3 |

### Action Items

Audit reports categorize findings as:
- **Immediate Actions**: Must fix before update
- **Suggested Before Update**: Deprecations to address
- **Post-Update Validation**: Things to test after update

## Prerequisites

### Required Tools

- **Go** (1.20+): `go version`
- **Git**: `git --version`
- **jq** (for audit): `jq --version`
- **curl/wget** (for fetching changelogs)

### Optional Tools

- **gh CLI** (for creating PRs): `gh --version`

### Repository Requirements

- Valid Go module with `go.mod`
- Git repository
- Clean working directory (or user accepts proceeding with uncommitted changes)

## Configuration

The plugin uses these conventions:

### Working Directory

All artifacts are saved to `.work/k8s-bumpup/`:
```
.work/
└── k8s-bumpup/
    ├── audit/
    │   └── ${TIMESTAMP}/
    │       ├── audit-report.md
    │       ├── api-imports.txt
    │       └── breaking-changes.txt
    └── ${TIMESTAMP}/
        ├── logs/
        │   ├── repo1-build.log
        │   └── repo1-test.log
        ├── reports/
        │   └── repo1-audit.md
        └── rebase-summary.md
```

### Branch Naming

Feature branches are automatically named:
```
rebase/k8s-v${TARGET_VERSION}-${DATE}
```

Example: `rebase/k8s-v1.29.0-20250126`

### Commit Messages

Generated commit messages follow this format:
```
Rebase Kubernetes dependencies to v1.29.0

Updated modules:
- k8s.io/api: v1.28.0 → v1.29.0
- k8s.io/apimachinery: v1.28.0 → v1.29.0
- k8s.io/client-go: v1.28.0 → v1.29.0

Build: ✓ PASS
Tests: ✓ PASS (120 tests)
```

## Error Handling

### Build Failures

If build fails after update:
1. Review build log in `.work/k8s-bumpup/logs/`
2. Check audit report for known API changes
3. Fix compilation errors
4. Re-run build: `go build ./...`

### Test Failures

If tests fail:
1. Review test output
2. Identify if failures are k8s API-related
3. Update test code for new APIs
4. Re-run: `go test ./...`

### Network Issues

If changelog fetching fails:
- Check internet connectivity
- Verify GitHub API access
- Manually review changelogs at:
  `https://github.com/kubernetes/kubernetes/blob/master/CHANGELOG/CHANGELOG-1.XX.md`

## Troubleshooting

### "Version not found" error

```
Error: Target version v1.99.0 not found for k8s.io modules
```

**Solution**: Check available versions:
```bash
go list -m -versions k8s.io/api
```

### "Dependency conflict" error

```
Error: Conflicting versions of k8s.io/apimachinery
```

**Solution**: Ensure all k8s.io modules use same version:
```bash
go get k8s.io/api@v1.29.0 \
      k8s.io/apimachinery@v1.29.0 \
      k8s.io/client-go@v1.29.0
```

### Vendor directory out of sync

```
Error: vendor/ directory out of sync
```

**Solution**:
```bash
rm -rf vendor/
go mod vendor
```

## Best Practices

1. **Review audit reports**: Both workflow commands include audit analysis - review it before proceeding
2. **Test incrementally**: For multi-version jumps, update incrementally
3. **Keep vendor/ in sync**: If using vendoring, always run `go mod vendor`
4. **Use feature branches**: The plugin creates branches automatically
5. **Review before pushing**: Check commits before pushing to remote
6. **Run full test suite**: Don't rely on partial test results

## Examples

### Example 1: Group rebase for corenet components

```bash
# Rebase all corenet repos to v0.34.2
/k8s-bumpup:batch-by-group corenet v0.34.2

# Review the consolidated summary
cat .work/k8s-batch-by-group/corenet/*/rebase-summary.md

# Push all successful branches to your fork
# Note: Replace <fork-remote> with your actual fork remote name
cd .work/k8s-batch-by-group/corenet/*/repos/multus-cni && git push <fork-remote> rebase/k8s-v0.34.2-*
cd .work/k8s-batch-by-group/corenet/*/repos/ovn-kubernetes && git push <fork-remote> rebase/k8s-v0.34.2-*

# Create PRs with cross-references
cd .work/k8s-batch-by-group/corenet/*/repos/multus-cni && gh pr create --draft
cd .work/k8s-batch-by-group/corenet/*/repos/ovn-kubernetes && gh pr create --draft
```

### Example 2: Update single operator to latest Kubernetes

```bash
# First, check what version you're on
grep "k8s.io/api" go.mod

# Run the rebase workflow
/k8s-bumpup:rebase-repo v1.29.3 ./my-operator

# Review the summary report
cat .work/k8s-bumpup/*/rebase-summary.md

# Push the feature branch to your fork
# Note: Replace <fork-remote> with your actual fork remote name
git push <fork-remote> rebase/k8s-v1.29.3-*
```

### Example 3: Batch update multiple repositories

```bash
# Update three related repositories
/k8s-bumpup:rebase-repo v1.30.0 \
  ~/projects/my-operator \
  ~/projects/my-controller \
  ~/projects/my-webhook

# Review the summary
cat .work/k8s-bumpup/*/rebase-summary.md

# Push all branches to your fork
# Note: Replace <fork-remote> with your actual fork remote name
cd ~/projects/my-operator && git push <fork-remote> rebase/k8s-v1.30.0-*
cd ~/projects/my-controller && git push <fork-remote> rebase/k8s-v1.30.0-*
cd ~/projects/my-webhook && git push <fork-remote> rebase/k8s-v1.30.0-*
```

### Example 4: Incremental update across major versions

```bash
# Update from v1.26 → v1.30 incrementally
/k8s-bumpup:rebase-repo v1.27.0 ./my-app
# Test, fix issues, merge

/k8s-bumpup:rebase-repo v1.28.0 ./my-app
# Test, fix issues, merge

/k8s-bumpup:rebase-repo v1.29.0 ./my-app
# Test, fix issues, merge

/k8s-bumpup:rebase-repo v1.30.0 ./my-app
# Test, fix issues, merge
```

## Related Resources

- [Kubernetes Deprecation Policy](https://kubernetes.io/docs/reference/using-api/deprecation-policy/)
- [Kubernetes API Migration Guide](https://kubernetes.io/docs/reference/using-api/deprecation-guide/)
- [client-go Compatibility Matrix](https://github.com/kubernetes/client-go#compatibility-matrix)
- [Go Modules Documentation](https://go.dev/ref/mod)

## Contributing

This plugin is part of the [ai-helpers](https://github.com/openshift-eng/ai-helpers) repository.

To contribute:
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run `make lint` to validate
5. Submit a pull request

## Support

For issues and questions:
- GitHub Issues: https://github.com/openshift-eng/ai-helpers/issues
- Plugin Documentation: This README

## License

See the main [ai-helpers repository](https://github.com/openshift-eng/ai-helpers) for license information.
