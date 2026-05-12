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
- **`llm-rubric`**: LLM-judged quality check — used for fuzzy assertions where exact output varies. The judge model is `vertex:claude-opus-4-6` configured in `defaultTest.options.provider`
- **`cost` / `latency`**: regression guards — fail if a test exceeds thresholds
- **No `output_format`**: we don't use `output_format: json_schema` because it bypasses the Skill tool invocation, which breaks `skill-used` assertions. The agent returns natural text with embedded JSON instead
- See [promptfoo assertion docs](https://www.promptfoo.dev/docs/configuration/expected-outputs/) for the full list of available assertion types

### Test fixtures
- Issue descriptions for jira evals live in `plugins/jira/evals/fixtures/*.md`
- Referenced via `file://fixtures/<name>.md` in yaml vars
- Plain markdown, not JSON — promptfoo loads them as string variables

### Cost and latency thresholds
Per-test thresholds in `defaultTest.assert` catch regressions without flaking:

| Plugin | Latency | Cost |
|--------|---------|------|
| hello-world | 30s | $0.50 |
| code-review | 60s | $0.50 |
| jira/ready-to-solve | 3min | $2.00 |
| jira/solve | 2min | $1.00 |

### LLM judge
The grading model (`defaultTest.options.provider`) is `vertex:claude-opus-4-6` — same model as the agent target. This is only invoked for `llm-rubric` assertions. Tests using only `icontains`, `skill-used`, `cost`, or `latency` don't call the judge.

## File Structure

```
plugins/
  hello-world/evals/echo.yaml                    # 3 command output tests
  code-review/evals/classify-review-comment.yaml  # 15 skill classification tests
  jira/evals/
    ready-to-solve.yaml                           # 3 readiness validation tests
    solve.yaml                                    # 5 phase-level analysis tests
    fixtures/                                     # test issue descriptions (.md)
evals/
  AGENTS.md                                       # this file
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

# Multiple runs with pass rate threshold
make eval-plugins EVAL_REPEAT=3 EVAL_PASS_RATE_THRESHOLD=80

# JUnit XML output (for CI)
EVAL_OUTPUT_DIR=./eval-results make eval-plugins

# View results in browser
npx promptfoo view
```

### Makefile parallelism
`make eval-plugins` discovers all `plugins/*/evals/*.yaml` files and runs them in parallel via `$(MAKE) -j`. Each yaml file becomes a sub-make target (with `/` replaced by `__` to work around Make's pattern rule limitation). All eval files run simultaneously — total wall-clock time equals the slowest plugin, not the sum.

`EVAL_PLUGIN=<name>` narrows the `find` to a single plugin directory. `EVAL_FILTER=<pattern>` passes `--filter-pattern` to promptfoo, which matches against test `description:` fields within each yaml.

## CI Workflow

`.github/workflows/eval-plugins.yml` runs on every PR:

1. **detect-changed-plugins**: diffs `plugins/` against the base branch, finds plugins with `evals/` directories
2. **behavioral-evals**: matrix job — one per changed plugin, runs `make eval-plugins EVAL_PLUGIN=<name>`
3. Results uploaded as JUnit XML artifacts via `EVAL_OUTPUT_DIR`

The workflow requires `ANTHROPIC_VERTEX_PROJECT_ID` as a GitHub secret and GCP auth (Workload Identity Federation or service account key).

## Adding Evals for a New Plugin

1. Create `plugins/<name>/evals/<test-name>.yaml`
2. Use an existing eval as a template (e.g., `plugins/hello-world/evals/echo.yaml`)
3. Set the provider to load your plugin: `plugins: [{type: local, path: ../}]`
4. Add `skill-used` in `defaultTest.assert` if testing a skill
5. Add `cost` and `latency` thresholds based on observed values (run once, then set 2-3x)
6. For test data, create `plugins/<name>/evals/fixtures/` and reference via `file://fixtures/<name>.md`
7. Run locally: `make eval-plugins EVAL_PLUGIN=<name>`
