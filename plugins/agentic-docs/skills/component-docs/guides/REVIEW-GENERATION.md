# REVIEW.md + .coderabbit.yaml Generation

You MUST generate both files. REVIEW.md is the single source of truth for code review tools (Claude Code Review, CodeRabbit). .coderabbit.yaml translates skip/path rules into CodeRabbit's native format. Target: 60-80 lines (soft cap 100).

## Step 1 — Clone enhancements repo

```bash
[ ! -d "/tmp/openshift-enhancements" ] && git clone --depth 1 https://github.com/openshift/enhancements.git /tmp/openshift-enhancements
```

## Step 2 — Read applicable dev-guide files

Based on repo type detected in Phase 4:

| Repo Type | Files to Read |
|-----------|---------------|
| **Operator** | `dev-guide/api-conventions.md`, `dev-guide/breaking-changes.md`, `dev-guide/operators.md`, `CONVENTIONS.md`, `guidelines/supportability.md`, `dev-guide/cluster-version-operator/dev/clusteroperator.md` |
| **Library** | `dev-guide/api-conventions.md`, `CONVENTIONS.md`, `dev-guide/breaking-changes.md` |
| **CLI** | `CONVENTIONS.md`, `dev-guide/breaking-changes.md` |

Extract ONLY diff-enforceable rules — rules that can be checked by looking at a code diff. Discard vague guidance ("should consider...") and retain imperative rules ("Flag X as must-fix", "Never allow Y").

## Step 3 — Chai-bot verification (optional)

Use the Chai Bot access path selected in `SKILL.md`. If hosted or external access is available, check whether any extracted rule has been superseded or changed by newer authoritative guidance. For external access, use the available Chai Bot `ask_persona` MCP capability; hosts may normalize the server name differently. If Chai Bot is unavailable, skip — include all extracted rules (err on side of inclusion).

```
"I'm generating REVIEW.md for {component} (github.com/openshift/{component}).
I extracted these enforceable review rules from openshift/enhancements dev-guide.
Are these still current? Have any been superseded, relaxed, or tightened?

1. [Rule 1 from Step 2]
2. [Rule 2 from Step 2]
...
(list top 5-8 most critical rules for the detected repo type)

For each rule: confirm current, superseded (by what), or unknown."
```

Discard rules chai-bot confirms are superseded. Keep confirmed + unverified (err on side of inclusion). DISCARD any claims about repo internals — chai-bot fabricates these.

## Step 4 — Collect skip patterns

From Phase 4 discoveries:
- Generated code (zz_generated*, clientset, informers, listers, bindata, protobuf, payload-manifests)
- Vendored dependencies (vendor/**)
- CI-enforced checks
- Generated dependency checksums (`go.sum`): do not report individual checksum-line
  changes, but investigate unexplained churn
- Generated dashboards/assets if present

`go.mod` is a dependency manifest, not a lockfile. Keep it reviewable and check
semantic changes such as added, removed, or upgraded dependencies, `replace` /
`exclude` directives, and Go/toolchain directives.

## Step 5 — Extract path-specific rules

From Phase 4 discoveries:
- Framework split table (which controllers use which apply method)
- Anti-patterns per package/directory
- Naming conventions per area
- Test conventions (Jira annotations, JUnit output, scoping)

## Step 6 — Calibrate severity

| Repo Type | Must-Fix Categories |
|-----------|-------------------|
| **Operator** | Incorrect reconciliation logic, unscoped queries crossing tenant boundaries, resource leaks, upgrade/downgrade safety violations, breaking changes to GA openshift.io APIs, security vulnerabilities, `Available=False` or `Degraded=True` during normal upgrade, premature version bump in ClusterOperator status, tolerating `node.kubernetes.io/unschedulable` |
| **Library** | API convention violations (bool fields, annotation-based APIs, missing validation markers, pointer misuse in CRDs), breaking changes to stable APIs, functions added to openshift/api |
| **CLI** | Breaking changes to CLI behavior, security vulnerabilities, incorrect error codes |

Style and naming issues are minor at most for all repo types.

## Step 7 — Generate REVIEW.md

- [ ] Use `templates/REVIEW-template.md` for structure
- [ ] Fill each section from Steps 2-6, stripping template comments from output
- [ ] Use tool-agnostic severity language ("must fix before merge" / "worth fixing, not blocking" / "suggestion only")
- [ ] Use glob patterns for skip rules, not prose descriptions
- [ ] Cite the dev-guide source for each "Always check" rule (parenthetical at end of line)
- [ ] Include "Verification bar" section — require file:line citations for every comment
- [ ] Include "Re-review" section — suppress new nits on unchanged code during re-reviews
- [ ] Validate line count: target 60-80 lines, soft cap 100
- [ ] **Do NOT** copy CLAUDE.md/AGENTS.md content — different purposes

## Step 8 — Generate/merge .coderabbit.yaml

- [ ] Use `templates/coderabbit-template.yaml` for structure — always set `inheritance: true`
- [ ] Only add repo-specific exclusions to `path_filters` — org config already excludes vendor, zz_generated, node_modules
- [ ] Translate "Path-specific rules" subsections to `path_instructions` entries
- [ ] Set `knowledge_base.filePatterns` to `["REVIEW.md", "AGENTS.md"]` — **NEVER add CLAUDE.md**
- [ ] `tone_instructions` is optional — only add if the repo has a distinct review culture
- [ ] If `.coderabbit.yaml` already exists, merge: preserve existing settings, add/update `knowledge_base`, `path_filters`, and `path_instructions`
- [ ] Validate YAML syntax: `python3 -c "import yaml; yaml.safe_load(open('.coderabbit.yaml'))"`
