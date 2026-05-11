---
name: RDS Analyzer workflow skill
description: End-to-end workflow from cluster data to deviation reports and optional Jira follow-up
---
# RDS Analyzer workflow skill

Use this skill when guiding users through the end-to-end workflow from cluster data to deviation reports and optional Jira follow-up. It mirrors [rds-analyzer `docs/full-workflow.md`](https://github.com/openshift-kni/rds-analyzer/blob/main/docs/full-workflow.md) and matches the **current** [openshift-kni/rds-analyzer](https://github.com/openshift-kni/rds-analyzer) CLI (`internal/cli/root.go`, [README.md](https://github.com/openshift-kni/rds-analyzer/blob/main/README.md)).

## Prerequisites (workflow context)

1. **Must-gather** (or live cluster access via kubeconfig) — see Red Hat docs for `oc adm must-gather`.
2. **cluster-compare (kube-compare) plugin** — produces the JSON input RDS Analyzer consumes. Install per OCP docs and upstream [kube-compare](https://github.com/openshift/kube-compare).
3. **Telco reference** — pick RAN DU, Telco Core, or Telco Hub; run comparison per product docs so output is **JSON** (e.g. `--output json` where applicable).

## Upstream `rds-analyzer` CLI (single command)

The repo exposes **one** executable with **no subcommands**: `rds-analyzer [flags]`. Cobra also provides **`--help` / `-h`** and **`--version` / `-v`**.

| Flag | Short | Default | Purpose |
|------|-------|---------|---------|
| `--input` | `-i` | stdin if not set | Path to kube-compare JSON. Without `-i`, data must be piped to stdin; interactive stdin with no pipe fails fast. |
| `--rules` | `-r` | `./rules.yaml` | Path to **one** rules YAML file. |
| `--output` | `-o` | `text` | `text` or `html` only. |
| `--output-mode` | `-m` | `simple` | `simple` or `reporting`. |
| `--target` | `-t` | *(empty)* | OCP version for rules (e.g. `4.19`). If empty, highest version in rules is used. |
| `--validate-rules-only` | — | `false` | Validate regexp patterns in rules; **no JSON input**; **do not use with `-i`.** |

### Examples (from upstream README / CLI help)

```bash
cat results.json | rds-analyzer -r /path/to/custom-rules.yaml
rds-analyzer -r ran-du-rules.yaml --validate-rules-only
rds-analyzer -i results.json -o html > report.html
rds-analyzer -i results.json -t 4.19
rds-analyzer -i results.json -r /path/to/rules.yaml
rds-analyzer -i results.json -m reporting
rds-analyzer --help
rds-analyzer --version
```

### Container (README)

```bash
podman run --rm -v $(pwd):/data:Z quay.io/rhsysdeseng/rds-analyzer:latest \
  -i /data/results.json -r /data/rules.yaml
```

## Workflow scenarios (map to user requests)

### A. Text report (terminal)

```bash
rds-analyzer -i comparison-results.json -r example-ran-du-rules.yaml
```

Equivalent defaults: `-o text -m simple`.

### B. HTML report

```bash
rds-analyzer -i comparison-results.json -r example-ran-du-rules.yaml -o html > deviation-report.html
```

### C. Specific OCP version + rules path

```bash
rds-analyzer -i comparison-results.json -o html -t 4.21 -r /path/to/rules.yaml > deviation-report.html
```

### D. Reporting mode (LLM / Jira prep)

```bash
rds-analyzer -i comparison-results.json -r example-ran-du-rules.yaml -m reporting
```

### E. Stdin

```bash
cat comparison-results.json | rds-analyzer -r rules.yaml
```

### F. Validate rules only

```bash
rds-analyzer -r ran-du-rules.yaml --validate-rules-only
```

## Helper script (optional)

From the ai-helpers repo, after `chmod +x`:

`plugins/rds-analyzer/scripts/run_rds_analyzer.sh`

- `text` → `-o text -m simple`
- `html` → `-o html -m simple`
- `reporting` → `-o text -m reporting`
- `validate-rules` → **`--validate-rules-only`** (matches upstream flag name)

Example:

```bash
export RDS_ANALYZER_BIN=/path/to/rds-analyzer
./plugins/rds-analyzer/scripts/run_rds_analyzer.sh text -- -i results.json -r rules.yaml
./plugins/rds-analyzer/scripts/run_rds_analyzer.sh validate-rules -- -r rules.yaml
```

## Reference documentation links (cluster compare / telco)

- [Telco RAN DU — cluster compare](https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/scalability_and_performance/telco-ran-du-ref-design-specs#using-cluster-compare-telco-ran_ran-ref-design-crs)
- [Telco Core](https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/scalability_and_performance/telco-core-ref-design-specs#using-cluster-compare-telco_core_telco-core)
- [Telco Hub](https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/scalability_and_performance/telco-hub-ref-design-specs#telco-hub-rds-container_telco-hub)
- [Install cluster-compare plugin](https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/scalability_and_performance/comparing-cluster-configurations#installing-cluster-compare-plugin)

## After the report: Jiras

Use deviation output to open or track issues. In ai-helpers, the **jira** plugin can assist with creating or structuring issues from structured text; combine **reporting** mode output with `/jira:create` or related commands when appropriate.

## Example rules path in rds-analyzer repo

`examples/example-ran-du-rules.yaml` (relative to a clone of [openshift-kni/rds-analyzer](https://github.com/openshift-kni/rds-analyzer)).

## Rules engine reminders

- Worst impact wins: Impacting > NeedsReview > NotImpacting > NotADeviation.
- Regex in rules is validated at startup; invalid patterns fail before JSON is read (unless `--validate-rules-only` alone).
