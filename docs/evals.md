# Evals

This project uses [agent-eval-harness](https://github.com/opendatahub-io/agent-eval-harness) to evaluate Claude Code skills against ground-truth test cases. See the harness README for framework details — this doc covers ai-helpers-specific concerns.

## Directory layout

Each plugin keeps its evals alongside its skill code:

```
plugins/
  hello-world/
    evals/
      eval.yaml              # eval config
      cases/
        case-001-default/
          input.yaml          # skill arguments
          annotations.yaml    # expected outcomes (ground truth)
        case-002-named/
          ...
  ci/
    evals/
      eval-install-analysis.yaml
      eval-payload-agent.yaml
      cases/
        install-analysis/
          case-install-001-.../
        payload-agent/
          case-001-.../
      shims/                  # CLI shims for sandboxed execution
        gcloud
        curl
        gh
```

## Adding a new eval

Start from `plugins/hello-world/evals/eval.yaml` — it's the minimal working example.

### Config structure

```yaml
name: my-eval
description: What this eval tests
skill: plugin-name:skill-name

execution:
  mode: case
  arguments: "{field1} {field2?}"   # {field?} = optional
  timeout: 60
  max_budget_usd: 0.50
  env:
    MY_VAR: $MY_VAR               # resolved from caller's env at runtime

runner:
  type: claude-code
  plugin_dirs:
    - plugins/my-plugin

models:
  judge: claude-opus-4-6          # fixed — most capable model for judging

permissions:
  allow: ["Skill", "Bash", "Read"]
  deny: []

dataset:
  path: plugins/my-plugin/evals/cases
  schema: |
    Describe the case directory structure here.

outputs:
  - path: "output"                # named subdir, NOT "."
    schema: |
      Describe expected output files here.

traces:
  stdout: true

judges:
  - name: my_check
    description: Inline Python check
    check: |
      transcript = outputs.get("conversation", "")
      # return (bool, explanation)

  - name: my_llm_judge
    description: LLM judge
    prompt: |
      Evaluate the output...
      {{ outputs }}
      {{ annotations }}

thresholds:
  my_check:
    min_pass_rate: 1.0
  my_llm_judge:
    min_mean: 4.0
```

### Test cases

Each case is a directory containing:

- **`input.yaml`**: Fields matching the `execution.arguments` template. Empty strings are treated as missing for required fields.
- **`annotations.yaml`**: Ground-truth expected outcomes. These are passed to judges as `{{ annotations }}` or `annotations` in inline checks.

### Judges

Two types:

- **Inline checks** (`check:`): Python snippets that return `(bool, explanation)`. Access `outputs` dict with keys like `conversation`, `files`, `modified_files`. Access `annotations` dict directly.
- **LLM judges** (`prompt:`): Jinja2 templates with `{{ outputs }}` and `{{ annotations }}`. Score on a 1-5 scale. Uses `models.judge` (currently `claude-opus-4-6`).

## Running evals locally

```bash
claude --plugin-dir path/to/agent-eval-harness \
  --model claude-sonnet-4-6 \
  --allowedTools "Bash Read Write Edit Grep Glob Agent Skill" \
  -p "/agent-eval-harness:eval-run --config plugins/hello-world/evals/eval.yaml --run-id my-run-001"
```

Results land in `eval/runs/{run-id}/` with per-case results and a `summary.yaml`.

## Running evals on OpenShift

The deployment manifest lives in the [manifest repo](https://github.com/not-stbenjam/manifest). It runs all eval suites sequentially, uploads results to a local MLflow server, and generates an HTML summary report.

### Payload archive data

Eval cases for the payload and install-analysis skills need archived CI artifacts. These are stored as OCI images on [quay.io/stbenjam/payload-data](https://quay.io/stbenjam/payload-data) and mounted as image volumes in the deployment. Each image is tagged with the payload version (e.g., `4.22.0-0.nightly-2026-03-20-053450`).

### Shims

The `plugins/ci/evals/shims/` directory contains CLI shims (`gcloud`, `curl`, `gh`) that intercept external API calls and serve from local archives when `EVAL_ARCHIVES_DIR` is set. The deployment prepends this directory to `PATH`. This makes evals reproducible and avoids external dependencies during scoring.

### MLflow

The deployment starts a local MLflow server in a Python venv. After evals complete, the harness's `eval-mlflow` command uploads results. The MLflow data is tar'd into artifacts for later inspection.

## Gotchas

**Environment variable syntax**: The harness resolves `$VAR` from the caller's environment, not `${VAR}`. The resolution code does `v[1:]` on values starting with `$`, so `${MY_VAR}` resolves to looking up `{MY_VAR}` (with braces), which fails silently.

**Outputs key in inline checks**: The conversation transcript is `outputs.get("conversation", "")`, not `"transcript"`.

**Optional arguments**: Use `{field?}` for optional fields. An empty string in `input.yaml` is treated as missing for required fields, causing a `ValueError`.

**Output path**: `outputs[0].path` cannot be `"."` — the harness requires a named subdirectory.

**Judge model**: Hardcoded to `claude-opus-4-6` in all configs. The judge should always be the most capable model available, independent of which model the skill under test uses. The skill model is controlled via `--model` on the CLI or `EVAL_MODEL` env var.
