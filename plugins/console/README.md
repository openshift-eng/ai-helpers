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

## Commands

### `ci-triage`

Triage failing CI on an OpenShift Console PR, it helps you specially to classify each failure as PR-related or unrelated.

```text
/console:ci-triage [PR-number]
```

Fetches Prow job logs, extracts specific error messages, cross-references them against the PR's changed files, and produces an actionable triage table. Helps Console contributors quickly understand what they need to fix versus what they can `/retest`.

#### Prerequisites

- `gh` CLI (authenticated)
- Internet access

## License

See [LICENSE](../../LICENSE) for details.
