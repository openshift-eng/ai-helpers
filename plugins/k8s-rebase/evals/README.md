# k8s-rebase Plugin Evals

Index of what each opaque `case-NNN` directory tests.

## Running evals

**On a laptop: run one case at a time.** Each case spawns a full Claude
session (up to 200 turns) plus `go mod vendor`. All 16 cases
sequentially can take 24h+ and exhaust RAM on heavy cases.

### Single-case runs (recommended for development)

> **Note:** `claude plugin eval --case <name>` does **not** work with
> this eval — the `--case` filter is only supported for prompt-file
> dataset mode, not the cli runner dataset mode used here. Use the
> runner script directly instead.

```bash
# From the ai-helpers repo root:
cd /path/to/ai-helpers

# case-012: ovn-kubernetes-mcp @ 1.35.3 (light, ~30min)
AI_HELPERS_DIR=$PWD \
EVAL_REPO_DIR=$PWD/plugins/k8s-rebase/evals/.repos/ovn-kubernetes_ovn-kubernetes-mcp \
plugins/k8s-rebase/evals/scripts/run-rebase.sh \
  https://github.com/ovn-kubernetes/ovn-kubernetes-mcp \
  36ac87c1aec7bc8f62e47ecbe161a1c972945773 \
  1.35.3 \
  claude-sonnet-4-6 \
  https://github.com/ovn-kubernetes/ovn-kubernetes-mcp \
  47c72f75684f435efe28ea3c20e1589430cd603c
```

Output lands in `$(pwd)/output/`. The repo is cached under `EVAL_REPO_DIR`
and reused on subsequent runs. Both are gitignored via `.gitignore`.

SHA arguments come from the case's `input.yaml`.

### Full-suite runs

`claude plugin eval plugins/k8s-rebase` runs all 16 cases sequentially.
Intended for CI or a dedicated workstation with ≥ 32GB RAM (24h timeout).

**Case weight order** (lightest → heaviest, by vendor tree size and API
surface):

- **Fastest:** cases with ovn-kubernetes-mcp, multus-cni, ingress-node-firewall
  (002, 003, 004, 008, 012, 013, 014) — small repos, narrow API surface
- **Medium:** cloud-network-config-controller (005, 009, 015)
- **Medium-heavy:** cluster-network-operator (006, 010, 016)
- **Slowest:** ovn-org/ovn-kubernetes (001, 007, 011) — sub-module layout,
  ~350MB vendor tree, expect 1–3h per run

## pattern-retention (`cases/pattern-retention`)

Smoke check only — not a substitute for `make court`, and does not test
generalization to novel breakage. All 16 cases reuse repos the skill's
autofix patterns were tuned against.

16 cases covering a full repo×version matrix. Source data in
`test/config-1.3{4,5,6}.yaml`.

| Case | Repo | Version | Weight |
|------|------|---------|--------|
| case-001 | ovn-org/ovn-kubernetes | 1.36.2 | Heavy — sub-module layout |
| case-002 | ovn-kubernetes/ovn-kubernetes-mcp | 1.36.2 | Light — minimal API surface |
| case-003 | openshift/multus-cni | 1.36.2 | Light — narrow API surface |
| case-004 | openshift/ingress-node-firewall | 1.36.2 | Light — narrow API surface |
| case-005 | openshift/cloud-network-config-controller | 1.36.2 | Medium |
| case-006 | openshift/cluster-network-operator | 1.36.2 | Medium-heavy — heavy openshift/api usage |
| case-007 | ovn-org/ovn-kubernetes | 1.34.1 | Heavy — sub-module layout |
| case-008 | openshift/multus-cni | 1.34.1 | Light — narrow API surface |
| case-009 | openshift/cloud-network-config-controller | 1.34.1 | Medium |
| case-010 | openshift/cluster-network-operator | 1.34.1 | Medium-heavy |
| case-011 | ovn-org/ovn-kubernetes | 1.35.3 | Heavy — sub-module layout |
| case-012 | ovn-kubernetes/ovn-kubernetes-mcp | 1.35.3 | Light — minimal API surface |
| case-013 | openshift/multus-cni | 1.35.3 | Light — narrow API surface |
| case-014 | openshift/ingress-node-firewall | 1.35.3 | Light — AI-produced known-good |
| case-015 | openshift/cloud-network-config-controller | 1.35.3 | Medium |
| case-016 | openshift/cluster-network-operator | 1.35.3 | Medium-heavy |

Note: 1.34 has no ovn-kubernetes-mcp or ingress-node-firewall cases —
those repos were not rebased to 1.34 (mcp didn't exist, infw had no
complete rebase).
