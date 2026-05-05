# RDS Analyzer plugin

AI-helpers workflows for **RDS Analyzer**: evaluate kube-compare JSON against YAML rules and produce text, HTML, or **reporting** mode output for LLMs and Jira follow-up.

This plugin mirrors the upstream [full-workflow.md](https://github.com/openshift-kni/rds-analyzer/blob/main/docs/full-workflow.md) document (from [openshift-kni/rds-analyzer](https://github.com/openshift-kni/rds-analyzer)).

## Commands

### `/rds-analyzer:full-workflow`

Runs or explains the end-to-end workflow: prerequisites (must-gather), cluster-compare installation and JSON output, telco reference documentation, all upstream `rds-analyzer` flags and examples (including `--validate-rules-only`, `--help`, `--version`), and Jira-oriented next steps.

Optional argument: a **scenario** name (see command file). Omit to cover the full workflow.

## Installation

```bash
/plugin marketplace add openshift-eng/ai-helpers
/plugin install rds-analyzer@ai-helpers
```

## Helper script

`scripts/run_rds_analyzer.sh` wraps common `rds-analyzer` flag combinations. Set `RDS_ANALYZER_BIN` if the binary is not on `PATH`.

```bash
chmod +x plugins/rds-analyzer/scripts/run_rds_analyzer.sh
export RDS_ANALYZER_BIN=/path/to/rds-analyzer
./plugins/rds-analyzer/scripts/run_rds_analyzer.sh text -- -i comparison.json -r rules.yaml
```

## Requirements

- Built or installed `rds-analyzer` CLI (see upstream Makefile / releases).
- Kube-compare JSON from cluster compare (not produced by this plugin).
- Rules YAML (one `-r` path per run); see upstream `examples/` in the rds-analyzer repository.
