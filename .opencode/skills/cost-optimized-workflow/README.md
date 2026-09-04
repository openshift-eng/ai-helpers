# Cost-Optimized OpenCode Workflow

This skill provides a provider-neutral workflow for reducing OpenCode context and model costs while preserving quality.

## Install Globally

From a clone of this repository:

```bash
mkdir -p ~/.config/opencode/skills
cp -R .opencode/skills/cost-optimized-workflow ~/.config/opencode/skills/
```

Restart OpenCode after installation.

## Configure Locally

Each user should choose model IDs from their own installation with:

```bash
opencode models
```

Configure their own provider credentials, model assignments, permissions, and RTK integration. Do not copy personal absolute paths, API keys, or project-specific assumptions.

## Scope

The skill covers:

- Cost-aware model selection
- Cheap-agent delegation and concise handoffs
- Prompt context and caching hygiene
- RTK output filtering
- Deterministic verification

It does not provide a universal hard model router. OpenCode normally uses a capable primary coordinator that delegates suitable work to configured subagents.
