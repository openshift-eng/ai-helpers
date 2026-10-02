# Console Plugin

OpenShift Console dynamic plugin development utilities.

## Skills

### `upgrade-console-sdk`

Upgrade an OpenShift Console dynamic plugin to a newer Console SDK version.

```text
/console:upgrade-console-sdk <current-target-version> <new-target-version>
```

Analyzes the plugin's current dependencies, fetches breaking changes and release notes across the version range, presents a detailed upgrade plan, and executes the migration with user approval. Handles SDK packages, shared modules (React, PatternFly, etc.), TypeScript/webpack config, and code migrations.

#### Prerequisites

- Node.js
- `gh` CLI (authenticated)
- Internet access

### `review-plugin-csp`

Review an OpenShift Console dynamic plugin for compatibility with Content Security
Policy (CSP), using its source, build configuration, resource declarations and
available generated assets.

```text
/console:review-plugin-csp .
/console:review-plugin-csp ./my-plugin --policy-file ./csp-headers.txt
/console:review-plugin-csp ./my-plugin --console-ref release-4.22
```

`--policy-file` accepts CSP directive values or response-header lines from the
Console HTML document. `--console-ref` uses an identified Console Git revision to
derive a baseline when the deployed policy is unavailable. Without either, the
skill can describe conditional requirements and ask for the missing context.

The report relates each finding to its directive and policy evidence, gives
file/asset locations, explains execution conditions, and suggests a migration
with targeted verification. It distinguishes observed browser violations from
expected incompatibilities and unresolved questions. Code allowed by the current
policy can be reviewed separately against explicit stricter-policy assumptions.

The review does not require a cluster. When neither `--policy-file` nor
`--console-ref` is provided, the skill describes conditional requirements (e.g.,
"this path requires dynamic evaluation to be permitted") rather than inventing a
policy. Runtime validation, when available and requested, supplies stronger
evidence for the exercised workflows; a source-only review is not a guarantee
that every plugin workflow is compliant. Builds, dependency changes and
deployments are performed only within the requested scope.

#### Prerequisites

- A local dynamic plugin repository.
- Optional: the effective CSP header, Console origin and build-mode information.
- `gh` CLI or web access when fetching a Console revision for a baseline.

To try the skill from an ai-helpers checkout:

```bash
claude --plugin-dir ./plugins/console
```

Then invoke `/console:review-plugin-csp` with the plugin path and available policy
context. See [the skill](skills/review-plugin-csp/SKILL.md) for the review workflow.

## License

See [LICENSE](../../LICENSE) for details.
