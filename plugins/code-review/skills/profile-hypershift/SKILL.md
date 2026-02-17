---
name: "HyperShift Project Profile"
description: "Project-specific review profile for the openshift/hypershift repository — delegates to the repo's own agents and skills"
---

# HyperShift Project Profile

This profile provides project-specific review guidance for the [openshift/hypershift](https://github.com/openshift/hypershift) repository. Instead of embedding domain knowledge, it points to the agents and skills already defined in the hypershift repo's `.claude/` directory.

## When to Use This Skill

Use this skill when `--profile hypershift` is specified.

## Agents

The hypershift repository maintains its own Claude agents at `.claude/agents/` that contain deep domain expertise (API, cloud providers, control plane, data plane, architecture). During review:

1. **If inside a local hypershift checkout**: Read the agent definitions from `.claude/agents/` in the repo root. Pick the agents relevant to the changed files based on each agent's own description, and launch them as sub-agents.
2. **If not in a hypershift checkout**: Fetch the agent definitions using `gh api repos/openshift/hypershift/contents/.claude/agents?ref=main` (or the GitHub contents API) and use them.
3. **Use all HyperShift SME agents** including (control-plane-sme, data-plane-sme, api-sme, cloud-provider-sme and hcp-architect-sme) to review branch changes or a given PR, questioning the approach and whether it solves the underlying problem.

The repo also has skills at `.claude/skills/` (code formatting, debugging, effective Go, git commit format, CLI conventions). Apply any that are relevant to the changed files.

## Build Commands

- `make test` — unit tests with race detection
- `make verify` — full verification suite (code generation, formatting, vetting, linting, tests)
- `make api` — **required if any files in `api/` were modified**; regenerates deepcopy, clients, informers, and listers

## API Type Changes

If any files in the `api/` directory were modified, verify that `make api` has been run and the generated files are included in the diff. Missing generated files are a blocking issue.
