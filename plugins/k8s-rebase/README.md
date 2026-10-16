# k8s-rebase

Automate Kubernetes minor-version rebases for Go projects: align dependencies
across modules, regenerate code, update version references, and fix build,
lint, and test breakage. A state machine above the agent owns progress:
scripts do repeatable work, the agent repairs, and 32 verification gates
decide when a step may advance. The [workflow design](docs/design.md)
explains how that structure resists reward hacking; its patterns apply to
other long-running agent workflows.

## Install

Claude Code:

```text
/plugin marketplace add openshift-eng/ai-helpers
/plugin install k8s-rebase@ai-helpers
```

Codex:

```bash
codex plugin marketplace add openshift-eng/ai-helpers
codex plugin add k8s-rebase@ai-helpers
```

See the [marketplace guide](../../site/docs/getting-started.md) for updates
and branch previews, and [runtime compatibility](docs/compatibility.md)
for host requirements and qualification status.

## Run

Start the agent session at the root of a clean target checkout, normally on
its default branch, with `go.mod` or `go-controller/go.mod`. Hooks use the
session cwd; changing a shell command's working directory is not sufficient.

```text
Claude Code: /k8s-rebase:k8s-rebase 1.36.2
Codex:       $k8s-rebase:k8s-rebase 1.36.2
```

Accepts `1.Y` or `1.Y.Z`; `1.Y` means `1.Y.0`. The no-op check compares
Kubernetes minors, so this workflow does not perform patch-only upgrades.

The skill creates a rebase branch with separate commits for each kind of
change, then prints a `gh pr create` command; it never pushes.

| Step | Work |
| --- | --- |
| 1 | Script bumps `k8s.io/*` in each module, runs codegen, and updates version references |
| 2 | Agent fixes build and vet errors |
| 3 | Autofix applies known patterns; the agent repairs what remains |
| 4 | Lint, tests, and an independent review of the fixes |
| 5 | Full-branch review, PR command, and cleanup |

Steps 1–4 each end at verification gates. After bounded repairs, Steps 2–4
can advance with unresolved checks; those findings remain in the PR body,
so finishing is not an all-checks-passed claim.

### Optional tooling updates

Add `--bump-tools` before the version to include non-Kubernetes updates in
separate commits, for projects that expect rebase PRs to keep tooling
current. Where present, the script syncs `GINKGO_VERSION` from
go.mod and updates `NODE_VERSION`, `NPM_VERSION`, and `NVM_VERSION`.
Step 4d updates non-k8s direct Go dependencies individually, preserving
Kubernetes pins and skipping replacements and commit-pinned dependencies.
Omit the flag for the core rebase scope.

### Resume

Use one mutating session per checkout and separate clones for concurrent
rebases; worktrees share Git hooks. Resume on the same branch with the same
version and tools flag. Preserve `.rebase-tmp/`: the skill resumes from
`state.json` and retained reports. The tools flag is not stored in that file.
If state is missing or conflicts with the request, preserve the artifacts
and resolve recovery before restarting.

## Prerequisites

- Bash with associative arrays, GNU command-line tools, Git, Make, Go,
  curl, Perl with `JSON::PP`, Python 3, `jq`, and `envsubst`.
- `podman` (preferred) or `docker` for toolchain/lint containers. The rebase
  auto-containerizes if local Go is too old. Network access is needed for
  dependencies, release metadata, and images; `gh` is used for GitHub lookups.
- Claude Code uses the `claude` CLI for independent reviews. Codex requires
  fresh-context native reviewers in Steps 4–5 and stops if unavailable.
- In Codex, review and trust the installed hooks through `/hooks` before
  starting; changed definitions need renewed trust. See the
  [hook documentation](https://learn.chatgpt.com/docs/hooks#review-and-trust-hooks).

## Development and coverage

The configs cover six repositories across Kubernetes 1.34.1, 1.35.3, and
1.36.2, with 16 reference cases; two 1.34 combinations are absent. Six
additional pinned [1.37.1 exploration baselines](test/config-1.37.yaml)
cover the next rebase. Read the [1.37 / OpenShift 5.1 notes](docs/k8s-1.37.md)
for downstream readiness and testing instructions. See the
[coverage table](evals/README.md#coverage) for exact cases and references.

| Read | Purpose |
| --- | --- |
| [Workflow design](docs/design.md) | Reusable patterns: state machine, reward-hacking countermeasures, evidence, review |
| [Skill entry point](skills/k8s-rebase/SKILL.md) | Executable instructions, step routing, and recovery |
| [Breakage patterns](docs/k8s-rebase-patterns.md) | Reusable migration knowledge and extension guidance |
| [Testing and evals](evals/README.md) | Offline checks, mutation tests, court, and scoring limits |

For local installation, register a clean **ai-helpers checkout** as the
marketplace root. Installers may copy scratch data and nested test clones
from a development checkout. Reinstall the package and start a new session
after edits. Follow the repository's [contribution rules](../../CONTRIBUTING.md)
for review checks and versioning.
