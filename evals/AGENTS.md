# Plugin Evals

Behavioral evals for ai-helpers plugins using [promptfoo](https://github.com/promptfoo/promptfoo) with the `anthropic:claude-agent-sdk` provider.

## Architecture Decisions

### Provider: `anthropic:claude-agent-sdk` with Vertex AI
- The SDK provider spawns the Claude Code CLI as a subprocess, giving full agent behavior (tools, skills, plugins)
- Vertex AI auth via `CLAUDE_CODE_USE_VERTEX=true` — no Anthropic API key needed, uses GCP credentials
- `ANTHROPIC_VERTEX_PROJECT_ID` tells Claude Code which GCP project to bill

### Co-located eval configs
- Eval configs live inside each plugin: `plugins/<name>/evals/*.yaml`
- Not in a central `evals/` directory — keeps tests next to the code they test
- The root `evals/` only holds the smoke test config and this file
- Adding evals for a new plugin: create `plugins/<name>/evals/<test>.yaml`

### Assertions
- **`skill-used` / `not-skill-used`**: verifies the agent invokes the correct skill and doesn't route to adjacent ones. Requires the SDK provider (not available with `exec:` providers). Skill names are namespaced: `plugin-name:skill-name`
- **`icontains`**: deterministic string match on agent output — cheap, no LLM judge
- **`llm-rubric`**: LLM-judged quality check — used for fuzzy assertions where exact output varies
- **`cost` / `latency`**: regression guards — fail if a test exceeds thresholds
- **No `output_format`**: we don't use `output_format: json_schema` because it bypasses the Skill tool invocation, which breaks `skill-used` assertions. The agent returns natural text with embedded JSON instead
- See [promptfoo assertion docs](https://www.promptfoo.dev/docs/configuration/expected-outputs/) for the full list of available assertion types

### Test fixtures
- Issue descriptions for jira evals live in `plugins/jira/evals/fixtures/*.md`
- Referenced via `file://fixtures/<name>.md` in yaml vars
- Plain markdown, not JSON — promptfoo loads them as string variables

### Test metadata and tiering

Every test case carries per-test metadata that describes its cost profile. Metadata must be on each test case directly — `defaultTest.metadata` is not used because `--filter-metadata` runs before defaultTest merging.

Use YAML anchors (`&meta-fast`) and aliases (`*meta-fast`) to avoid repetition:

```yaml
tests:
  - description: "first test"
    metadata: &meta-fast          # anchor: defines the block
      token-usage: medium
      judge-size: none
      tier: fast
    ...

  - description: "second test"
    metadata: *meta-fast          # alias: reuses the block
    ...
```

#### Metadata fields

```yaml
metadata:
  token-usage: small | medium | large    # agent execution cost
  judge-size: none | sonnet | opus       # grading model for llm-rubric assertions
  tier: fast | medium | heavy            # computed from token-usage and judge-size
```

**`token-usage`** — how expensive the agent execution is, derived from the `type: cost` and `type: latency` assertion thresholds on each test:

| token-usage | cost threshold | latency threshold | typical test                         |
|-------------|----------------|-------------------|--------------------------------------|
| small       | $0.50          | 30s               | simple command, minimal tool calls   |
| medium      | $0.50          | 60s               | single skill invocation with tool use|
| large       | $0.60-1.20     | 120-180s          | multi-tool workflow, script execution|

The `cost` assertion checks the agent execution cost only (not judge cost).

**`judge-size`** — which model grades `llm-rubric` assertions:
- `none`: no LLM judge — only deterministic assertions (`icontains`, `skill-used`, `cost`, `latency`)
- `sonnet`: graded by `vertex:claude-sonnet-4-6` — cheaper, good for straightforward pass/fail
- `opus`: graded by `vertex:claude-opus-4-6` — more capable, for nuanced quality judgments

The judge model is configured in `defaultTest.options.provider` per eval file.

**`tier`** — computed from the other two, determines when the test runs:

| token-usage | judge-size | tier   |
|-------------|------------|--------|
| small       | none       | fast   |
| medium      | none       | fast   |
| large       | none       | medium |
| small       | sonnet     | fast   |
| medium      | sonnet     | medium |
| large       | sonnet     | heavy  |
| small       | opus       | medium |
| medium      | opus       | medium |
| large       | opus       | heavy  |

Rule: tier is the highest cost contributor across both dimensions. A `none` judge pulls the tier down (no grading cost), while `opus` judge or `large` agent cost pushes it up.

#### Current test inventory

| Test                         | token-usage | judge-size | tier   | count |
|------------------------------|-------------|------------|--------|-------|
| hello-world/echo             | small       | none       | fast   | 3     |
| classify golden tests        | medium      | none       | fast   | 13    |
| classify ambiguous/routing   | medium      | opus       | medium | 2     |
| jira/ready-to-solve          | large       | opus       | heavy  | 3     |
| jira/solve                   | large       | opus       | heavy  | 4     |
| **Total**                    |             |            |        | **25**|

#### Running by tier

```bash
# Fast only — 16 tests, deterministic
make eval-plugins EVAL_TIER=fast

# Medium only — 2 tests, opus judge but cheap agent
make eval-plugins EVAL_TIER=medium

# Heavy only — 8 tests, expensive agent + opus judge
make eval-plugins EVAL_TIER=heavy

# All tiers (default)
make eval-plugins

# Combine with plugin filter
make eval-plugins EVAL_PLUGIN=code-review EVAL_TIER=fast
```

#### Budget planning

Measured cost per full run (25 tests, opus agent, Vertex AI): **~$6**

| Plugin              | Tests | Tier        | Actual cost | Per-test avg |
|---------------------|-------|-------------|-------------|--------------|
| hello-world         | 3     | fast        | $0.56       | $0.19        |
| code-review         | 15    | fast/medium | $2.70       | $0.18        |
| jira/ready-to-solve | 3     | heavy       | $1.62       | $0.54        |
| jira/solve          | 5     | heavy       | $0.73       | $0.15        |
| **Total**           | **26**|             | **$5.61**   | **$0.22**    |

By tier:

| Tier   | Tests | Actual cost |
|--------|-------|-------------|
| fast   | 16    | ~$3.26      |
| medium | 2     | ~$0.33      |
| heavy  | 8     | ~$2.02      |

Agent execution is the dominant cost (~99%). Judge calls are negligible even with opus.

When setting `cost` thresholds per test, use ~2x the observed per-test max:
- `small`: observed ~$0.20, threshold $0.50
- `medium`: observed ~$0.21, threshold $0.50
- `large`: observed $0.27-0.62, threshold $0.60-1.20

### Cost and latency thresholds
Per-test thresholds in `defaultTest.assert` catch regressions without flaking:

| Plugin              | Latency | Cost  | token-usage |
|---------------------|---------|-------|-------------|
| hello-world         | 30s     | $0.50 | small       |
| code-review         | 60s     | $0.50 | medium      |
| jira/ready-to-solve | 3min    | $1.20 | large       |
| jira/solve          | 2min    | $0.60 | large       |

### Per-plugin budgets
Budgets are defined centrally in `evals/budget.yaml` with `allowed` (admin-set cap) and `current` (sum of cost thresholds across all tests) per plugin:

| Plugin              | Allowed | Current (sum of thresholds) |
|---------------------|---------|----------------------------|
| hello-world         | $1.50   | $1.50                      |
| code-review         | $8.00   | $7.50                      |
| jira                | $7.00   | $6.00                      |
| **Total**           | **$16.50** | **$15.00**              |

`evals/budget.yaml` is the single source of truth for the eval cost model. It contains:
- **`orderings`**: defines `small < medium < large`, `none < sonnet < opus`, `fast < medium < heavy`
- **`token-usage`**: maps each size to its `max-cost` and `max-latency` thresholds
- **`tiers`**: maps each tier to its `max-token-usage` and `max-judge-size` bounds
- **`budgets`**: per-plugin `allowed` (admin cap) and `current` (sum of thresholds)
- **Linter validation rules**: documented as comments — how to validate metadata consistency, threshold bounds, and budget compliance

## File Structure

```text
plugins/
  hello-world/evals/
    echo.yaml                                     # 3 command output tests
  code-review/evals/
    classify-review-comment.yaml                  # 15 skill classification tests
  jira/evals/
    ready-to-solve.yaml                           # 3 readiness validation tests
    solve.yaml                                    # 4 phase-level analysis tests
    fixtures/                                     # test issue descriptions (.md)
evals/
  AGENTS.md                                       # this file
  budget.yaml                                     # shared cost definitions + per-plugin budgets
  promptfooconfig.yaml                            # smoke test
package.json                                      # pins promptfoo + claude-agent-sdk versions
.github/workflows/eval-plugins.yml                # CI: evals on PRs with changed plugins
```

## Running Evals

### Prerequisites
- `claude` CLI installed and authenticated
- Node.js 22+
- `gcloud auth application-default login` (for Vertex AI)
- `ANTHROPIC_VERTEX_PROJECT_ID` set

### Commands

```bash
# Run all plugin evals (parallel)
ANTHROPIC_VERTEX_PROJECT_ID=<project> make eval-plugins

# Single plugin
make eval-plugins EVAL_PLUGIN=hello-world

# Filter by test description
make eval-plugins EVAL_PLUGIN=code-review EVAL_FILTER=nitpick

# Filter by tier
make eval-plugins EVAL_TIER=fast

# Combine plugin and tier
make eval-plugins EVAL_PLUGIN=code-review EVAL_TIER=fast

# Multiple runs with pass rate threshold
make eval-plugins EVAL_REPEAT=3 EVAL_PASS_RATE_THRESHOLD=80

# JUnit XML output (for CI)
EVAL_OUTPUT_DIR=./eval-results make eval-plugins

# View results in browser
npx promptfoo view
```

### Makefile parallelism
`make eval-plugins` discovers all `plugins/*/evals/*.yaml` files and runs them in parallel via `$(MAKE) -j`. Each yaml file becomes a sub-make target (with `/` replaced by `__` to work around Make's pattern rule limitation). All eval files run simultaneously — total wall-clock time equals the slowest plugin, not the sum.

`EVAL_PLUGIN=<name>` narrows the `find` to a single plugin directory. `EVAL_FILTER=<pattern>` passes `--filter-pattern` to promptfoo, which matches against test `description:` fields within each yaml. `EVAL_TIER=<tier>` passes `--filter-metadata tier=<tier>` to run only tests at that tier level.

## CI Workflow

`.github/workflows/eval-plugins.yml` runs on every PR:

1. **detect-changed-plugins**: diffs `plugins/` against the base branch, finds plugins with `evals/` directories
2. **behavioral-evals**: matrix job — one per changed plugin, runs `make eval-plugins EVAL_PLUGIN=<name>`
3. Results rendered as GitHub Check via `dorny/test-reporter` and uploaded as JUnit XML artifacts

The workflow requires `ANTHROPIC_VERTEX_PROJECT_ID` and `GOOGLE_APPLICATION_CREDENTIALS` as GitHub secrets.

## Adding Evals for a New Plugin

1. Create `plugins/<name>/evals/<test-name>.yaml`
2. Use an existing eval as a template (e.g., `plugins/hello-world/evals/echo.yaml`)
3. Set the provider to load your plugin: `plugins: [{type: local, path: ../}]`
4. Add `skill-used` in `defaultTest.assert` if testing a skill
5. Add `cost` and `latency` thresholds in `defaultTest.assert` based on observed values (run once, then set 2-3x)
6. Add per-test `metadata` with `token-usage`, `judge-size`, and `tier` — use YAML anchors to DRY
7. For test data, create `plugins/<name>/evals/fixtures/` and reference via `file://fixtures/<name>.md`
8. Run locally: `make eval-plugins EVAL_PLUGIN=<name>`
