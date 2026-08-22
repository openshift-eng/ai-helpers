# Golang Plugin Evals

Evaluations for the golang plugin's three skills. Each eval targets the
**failure-prone behaviors** where models actually diverge — not the trivial
parts any model gets right.

## What each eval tests

### `eval-fix-cve.yaml` — 6 cases, 8 judges

Tests the hard parts of CVE patching, not version number comparison:

| Case | Tests |
|------|-------|
| replace-directive-syntax | Exact `// CVE-...\nreplace A => B v...` format |
| multi-module-detection | Find affected go.mod files, exclude vendor/ |
| command-ordering | `go mod vendor` BEFORE `make update` (the skill's #1 footgun) |
| path-c-hard-stop | Stop and ask for fork URL, don't barrel ahead |
| module-not-affected | Negative case — module not in go.mod, make no changes |
| commit-message-format | `fix(deps): <action>` prefix, ticket on own line |

### `eval-go-lint.yaml` — 5 cases, 5 judges

Tests the discovery cascade and constraints, not "can it run golangci-lint":

| Case | Tests |
|------|-------|
| discovery-claudemd | CLAUDE.md says `make verify-lint` — use it, not `golangci-lint run` |
| discovery-makefile | No CLAUDE.md, Makefile has `lint:` — use `make lint` |
| discovery-fallback | Neither exists — fall back to `golangci-lint run ./...` |
| read-only-constraint | Found issues → report them, do NOT edit files |
| not-installed-handling | Not available → link to docs, do NOT auto-install |

### `eval-go-lint-fix.yaml` — 4 cases, 6 judges

Tests the constraints models actually violate:

| Case | Tests |
|------|-------|
| generated-file-skip | `// Code generated` header → never modify |
| real-fix-not-nolint | Fixable errcheck → handle error, don't `//nolint` |
| existing-constant-reuse | `DefaultTimeout = 30` exists → use it, don't create duplicate |
| direct-invocation-not-make | Has Makefile lint target → still use `golangci-lint --fix` directly, carry flags |

## Running

Evals run via the `agent-eval-harness` plugin (`/plugin install agent-eval-harness@opendatahub-skills`).

```bash
# Run a single eval (from repo root)
/agent-eval-harness:eval-run plugins/golang/evals/eval-fix-cve.yaml

# Run with a specific model
/agent-eval-harness:eval-run plugins/golang/evals/eval-go-lint.yaml --model claude-sonnet-4-20250514

# Run all three
/agent-eval-harness:eval-run plugins/golang/evals/eval-fix-cve.yaml
/agent-eval-harness:eval-run plugins/golang/evals/eval-go-lint.yaml
/agent-eval-harness:eval-run plugins/golang/evals/eval-go-lint-fix.yaml
```

Results land in `eval/runs/<eval-name>/<run-id>/report.html`.

## Thresholds

Constraint judges (generated-file-skip, read-only, hard-stop, command-ordering)
require **100% pass rate** — these are behaviors that must never fail.

Reasoning judges (replace-directive-syntax, discovery-command, constant-reuse)
require **85%** — minor format variations are acceptable.

LLM quality judges require **mean >= 3.5** on a 1-5 scale.

## Adding cases

Each case targets a specific failure mode. Before adding:
1. Identify a behavior the skill prescribes that models get wrong
2. Write the case to test that behavior specifically
3. Write judges that catch the failure deterministically (not LLM)

```text
cases/<skill-name>/case-NNN-failure-description/
├── input.yaml         # scenario setup
└── annotations.yaml   # expected behavior + notes on what models get wrong
```
