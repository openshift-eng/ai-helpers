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

## License

See [LICENSE](../../LICENSE) for details.
