# Debugging Plugin

Generic, evidence-backed debugging for software, systems, configuration, data,
and automation.

## Skill

### `evidence-chain`

The skill is automatically applicable whenever Claude is debugging, diagnosing,
troubleshooting, or root-causing. It does not require or provide a command. It
requires three artifacts before a conclusion is treated as proved:

1. A machine-readable evidence contract with exact local citations
2. A deterministically validated, hydrated Markdown report
3. A semantic review of the reasoning and independent verification

When those requirements cannot be met, the result remains inconclusive and the
missing evidence is reported explicitly.

## Installation

```bash
/plugin install debugging@ai-helpers
```
