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

Statically review an OpenShift Console dynamic plugin for compatibility with Content Security
Policy (CSP), using its source, build configuration, resource declarations and
available generated assets.

```text
/console:review-plugin-csp .
/console:review-plugin-csp ./my-plugin --policy-file ./csp-headers.txt
/console:review-plugin-csp ./my-plugin --console-ref release-4.22
```

All arguments are optional; the plugin path defaults to the current repository.
Without flags, the skill resolves the current upstream `main` HEAD of
`openshift/console`, records its commit SHA, derives the CSP baseline from that
revision, and inspects the plugin's ConsolePlugin CR for
`spec.contentSecurityPolicy` declarations when available. It does not silently
use a potentially stale local `main`. Users do not need to prepare a policy file
or provide cluster access to start a review.

`--console-ref` selects a particular Console Git revision instead of upstream
`main`. `--policy-file` accepts CSP directive values or captured response-header
lines and takes precedence when an effective deployed policy is supplied. To
capture headers, use browser DevTools Network on the authenticated Console HTML
document response; preserve all CSP headers and their enforcing/report-only
names. Saved HTML and an OAuth redirect response are not substitutes.

The default assessment is a **source-derived baseline plus declared additions**,
not a verified deployed policy: a manifest does not prove deployment or operator
propagation. With supplied effective headers, missing manifest sources are not
assumed to be allowed. Other cluster additions remain unknown without evidence.

The findings report relates each candidate to its directive and policy evidence,
gives file/asset locations, explains execution conditions, and suggests migration
steps. It uses three static assessment states: **Expected incompatibility**,
**Needs verification**, and **Permitted in reviewed context**. Code allowed by
the current policy can be assessed separately against explicit stricter-policy
assumptions. Static findings do not claim runtime confirmation.

The review does not require a cluster or a policy file. If no reliable policy
can be established, for example because the selected source revision is
unavailable, the skill reports that gap and gives conditional findings rather
than inventing a policy or silently substituting another revision. The skill
does not start Console, deploy the plugin, automate browser workflows or
collect/import browser violation reports; users do not need to generate them.
Its own findings report remains part of the review. Source and bundle inspection
cannot guarantee that every plugin workflow is compliant. Code changes,
dependency installation and production builds require an explicit request.

#### Prerequisites

- A local dynamic plugin repository.
- For the bundled scanner: Bash, ripgrep (`rg`) and standard Unix utilities; no Node.js or npm setup.
- Optional: the effective CSP header, Console origin and build-mode information.
- `gh` CLI or web access when fetching a Console revision for a baseline.

To try the skill from an ai-helpers checkout:

```bash
claude --plugin-dir ./plugins/console
```

Then invoke `/console:review-plugin-csp` with the plugin path and available policy
context. See [the skill](skills/review-plugin-csp/SKILL.md) for the review workflow.

#### Bundled candidate scanner

The skill ships [a Bash + ripgrep helper](skills/review-plugin-csp/scripts/scan-csp.sh)
for production `.js`, `.mjs` and `.cjs` files. No npm installation is needed.
It searches for evaluation references, Function constructors, string timers,
style/script creation, workers and connection calls. It does not execute bundle
code or load ripgrep configuration. Scanned files are unchanged; temporary
match files are cleaned up.

From an ai-helpers checkout, scan the plugin's actual production output directory:

```bash
bash plugins/console/skills/review-plugin-csp/scripts/scan-csp.sh /path/to/plugin/dist
```

Output is tab-separated: category, shell-escaped relative file, line, byte-column
and a short match, followed by counts, omitted results and errors. Defaults are
200 returned matches and 20 MiB per file; use `--max-findings` or `--max-file-bytes`
to adjust these limits. Source maps, `.git`/`node_modules` directories and symlinks
are excluded; hidden/gitignored JavaScript is included. Exit 0 means text
searching completed, not CSP compliance; exit 2 means an input/tool error or
incomplete search.

These are heuristic candidates, not a JavaScript analysis or confirmed
violations. Comments, strings and permitted operations can match; computed
access, aliases and unusual formatting may be missed. Claude must inspect
context, execution conditions and the assessed policy. For an installed plugin,
the skill locates the helper via `${CLAUDE_SKILL_DIR}`. Missing tools are reported,
not installed automatically.

Developer tests use Python's standard library (Python is not needed to run the
scanner):

```bash
python3 plugins/console/skills/review-plugin-csp/scripts/test_scan_csp.py
```

## License

See [LICENSE](../../LICENSE) for details.
