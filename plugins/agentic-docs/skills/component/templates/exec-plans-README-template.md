# Execution Plans

> **Exec-Plans Guidance**: See [Tier 1 Exec-Plans Guide](https://github.com/openshift/enhancements/tree/master/ai-docs/workflows/exec-plans/) for:
> - What are exec-plans?
> - When to create them
> - How to use them
> - Completion workflow
> - Template

## Component-Specific Exec-Plans

Active exec-plans for this component are tracked in `active/`:

```text
exec-plans/
└── active/              # Create feature-specific exec-plans here
```

## Usage

```bash
# Get template from Tier 1
curl -O https://raw.githubusercontent.com/openshift/enhancements/master/ai-docs/workflows/exec-plans/template.md

# Create exec-plan
mv template.md active/feature-name.md

# Fill in and track during implementation
```

See [Tier 1 Exec-Plans Guide](https://github.com/openshift/enhancements/tree/master/ai-docs/workflows/exec-plans/README.md) for complete documentation.
