---
description: Run the RDS Analyzer full workflow from cluster-compare JSON to deviation reports (text/HTML/reporting), validate rules, and Jira-oriented follow-up — aligned with rds-analyzer docs/full-workflow.md
argument-hint: "[scenario]"
---

## Name

rds-analyzer:full-workflow

## Synopsis

```
/rds-analyzer:full-workflow [scenario]
```

## Description

Orchestrates the **complete RDS Analyzer workflow** from [openshift-kni/rds-analyzer](https://github.com/openshift-kni/rds-analyzer) ([docs/full-workflow.md](https://github.com/openshift-kni/rds-analyzer/blob/main/docs/full-workflow.md)):

1. **Prerequisites** — Must-gather (or cluster access) and kube-compare JSON as input.
2. **Cluster compare** — User must have the cluster-compare (kube-compare) plugin installed; official install and telco reference docs.
3. **Telco references** — RAN DU, Telco Core, Telco Hub documentation links for running comparisons.
4. **RDS Analyzer** — Run the single upstream `rds-analyzer` binary with the flags documented below (text/HTML, `--target`, `--output-mode reporting`, stdin, `--validate-rules-only`).
5. **Jira / LLM follow-up** — Reporting-mode output for telco team interaction; suggest Jira plugin commands when the user wants tickets.

This command does **not** replace installing cluster-compare or gathering must-gather; it guides execution and **runs** `rds-analyzer` when the user provides paths and a binary (PATH or `RDS_ANALYZER_BIN`).

## Upstream CLI — all commands and flags (openshift-kni/rds-analyzer)

The repository ships **one** Cobra root command: `rds-analyzer` (no subcommands). Standard Cobra additions apply:

| Invocation | Purpose |
|------------|---------|
| `rds-analyzer [flags]` | Default: read kube-compare JSON (from `-i` or stdin), load rules, write deviation report to stdout. |
| `rds-analyzer --help` | Short and long help (synopsis, flag list, embedded examples). Short: `-h`. |
| `rds-analyzer --version` | Print build version string. Short: `-v`. |

**Analysis flags** (from `internal/cli/root.go` and [README.md](https://github.com/openshift-kni/rds-analyzer/blob/main/README.md)):

| Flag | Short | Default | Description |
|------|-------|---------|-------------|
| `--input` | `-i` | *(unset → stdin)* | Path to kube-compare JSON. If omitted, JSON must be **piped on stdin**; if stdin is a TTY with no pipe, the tool errors (`no input provided; use -i flag or pipe JSON data`). |
| `--rules` | `-r` | `./rules.yaml` | Path to **one** rules YAML file. |
| `--output` | `-o` | `text` | Output format: `text` or `html` only. |
| `--output-mode` | `-m` | `simple` | Output mode: `simple` or `reporting` (LLM-oriented two-section layout). |
| `--target` | `-t` | *(empty)* | OCP version for rules evaluation (e.g. `4.19`, `4.21`). If unset, the engine uses the highest version defined in the rules file. |
| `--validate-rules-only` | *(none)* | `false` | Load rules YAML, validate all regexp / `value_regex` patterns, print success or error, **exit without reading JSON**. **Cannot be combined with `-i`.** |

**Upstream embedded examples** (from CLI `Long` help text):

```bash
# stdin + custom rules
cat results.json | rds-analyzer -r /path/to/custom-rules.yaml

# validate rules only (flag name is --validate-rules-only, not --validate-rules)
rds-analyzer -r ran-du-rules.yaml --validate-rules-only

# file input + HTML
rds-analyzer -i results.json -o html > report.html

# target OCP version (default rules path ./rules.yaml if -r omitted)
rds-analyzer -i results.json -t 4.19

# custom rules + input file
rds-analyzer -i results.json -r /path/to/rules.yaml

# reporting mode
rds-analyzer -i results.json -m reporting
```

**README / workflow doc examples** (same binary; paths illustrative):

```bash
rds-analyzer -i comparison-results.json -r example-ran-du-rules.yaml
rds-analyzer -i comparison-results.json -r example-ran-du-rules.yaml -o html > deviation-report.html
rds-analyzer -i comparison-results.json -o html -t 4.21 -r /path/to/rules.yaml > deviation-report.html
rds-analyzer -i comparison-results.json -r example-ran-du-rules.yaml -m reporting
```

**Container** (from upstream README; image `quay.io/rhsysdeseng/rds-analyzer`):

```bash
podman run --rm -v $(pwd):/data:Z quay.io/rhsysdeseng/rds-analyzer:latest \
  -i /data/results.json -r /data/rules.yaml
podman run --rm -v $(pwd):/data:Z quay.io/rhsysdeseng/rds-analyzer:latest \
  -i /data/results.json -r /data/rules.yaml -o html > report.html
cat results.json | podman run --rm -i -v $(pwd):/data:Z quay.io/rhsysdeseng/rds-analyzer:latest \
  -r /data/rules.yaml
```

## Implementation

1. **Load the skill** `plugins/rds-analyzer/skills/rds-analyzer-workflow/SKILL.md` for extra context and links.
2. **Interpret `scenario`** (optional `$1`):
   - `prerequisites` — Must-gather and environment checklist only.
   - `cluster-compare` — Install links and how to obtain JSON for RDS Analyzer.
   - `telco-refs` — Telco RAN DU / Core / Hub doc links for cluster compare.
   - `analyze-text` — Text report: `rds-analyzer -i … -r …` (defaults `-o text -m simple`).
   - `analyze-html` — HTML: `rds-analyzer -i … -r … -o html` (redirect stdout to a file).
   - `analyze-reporting` — LLM-oriented: `-m reporting` (still text stream unless combined with `-o html` as appropriate).
   - `analyze-versioned` — Include `-t <OCP>` and `-r` path as needed.
   - `validate-rules` — Run **`rds-analyzer -r <rules.yaml> --validate-rules-only`** (no `-i`, no stdin JSON).
   - `jira-followup` — How to use reporting output with Jira workflows (reference `/jira:*` commands in ai-helpers).
   - **Omitted or `all`** — Walk through sections 1–5 in order; ask for missing inputs before running commands.
3. **Execute** when the user supplies concrete paths:
   - Prefer `rds-analyzer` on PATH, or `RDS_ANALYZER_BIN`.
   - Optional wrapper: `plugins/rds-analyzer/scripts/run_rds_analyzer.sh` (`text`, `html`, `reporting`, `validate-rules` → passes **`--validate-rules-only`** to the binary).
4. **Rules file** — Upstream accepts **one** `-r` path per invocation. For combined hub + DU rules, merge YAML offline or run separate passes as the workflow requires.
5. **Never** combine `-i` (or stdin JSON) with `--validate-rules-only`.

## Return Value

- **Guidance**: Step-by-step narrative for the chosen scenario(s).
- **Commands**: Copy-pasteable `rds-analyzer` (or `podman run …`, or script) invocations with user-provided paths.
- **On failure**: Parse stderr; for regexp errors suggest `--validate-rules-only` or fixing rules YAML.

## Examples

1. **Full guided workflow**

   ```
   /rds-analyzer:full-workflow
   ```

2. **Validate rules only (upstream flag)**

   ```
   /rds-analyzer:full-workflow validate-rules
   ```

3. **HTML report scenario**

   ```
   /rds-analyzer:full-workflow analyze-html
   ```

4. **Reporting mode for LLM / Jira prep**

   ```
   /rds-analyzer:full-workflow analyze-reporting
   ```

5. **Show upstream help / version** (when the user asks how to run the tool)

   ```
   rds-analyzer --help
   rds-analyzer --version
   ```

## Arguments

- `$1` **scenario** (optional): One of `prerequisites`, `cluster-compare`, `telco-refs`, `analyze-text`, `analyze-html`, `analyze-reporting`, `analyze-versioned`, `validate-rules`, `jira-followup`, or `all`. If omitted, default to `all`. The scenario `validate-rules` maps to **`--validate-rules-only`** on the real binary.

## See Also

- Skill: `plugins/rds-analyzer/skills/rds-analyzer-workflow/SKILL.md`
- Upstream workflow: [docs/full-workflow.md](https://github.com/openshift-kni/rds-analyzer/blob/main/docs/full-workflow.md)
- Upstream usage index: [USAGE.md](https://github.com/openshift-kni/rds-analyzer/blob/main/USAGE.md)
- Script: `plugins/rds-analyzer/scripts/run_rds_analyzer.sh`
