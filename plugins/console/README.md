# Console Plugin

OpenShift Console dynamic plugin development utilities.

## Skills

### `upgrade-sdk`

Upgrade an OpenShift Console dynamic plugin to a newer Console SDK version.

```text
/console:upgrade-sdk <current-target-version> <new-target-version>
```

Analyzes the plugin's current dependencies, fetches breaking changes and release notes across the version range, presents a detailed upgrade plan, and executes the migration with user approval. Handles SDK packages, shared modules (React, PatternFly, etc.), TypeScript/webpack config, and code migrations.

#### Prerequisites

- Node.js
- `gh` CLI (authenticated)
- Internet access

### `jira-bug-create`

Create an OCPBUGS Jira bug for OpenShift Console with the fields expected by the team's Definition of Ready, so the report is detailed enough for others (including automation) to pick up and work the issue.

```text
/console:jira-bug-create [--dry-run] [bug description]
```

Runs a seven-step wizard: bug description (with duplicate search), reproduction details, environment and configuration, severity and priority, affected and target versions, required artifacts, then review and create. Component is fixed to Management Console; use `--dry-run` to assemble the report without creating the issue.

#### Prerequisites

- Jira MCP access to project OCPBUGS (create and search issues)
- Internet access

## License

See [LICENSE](../../LICENSE) for details.
