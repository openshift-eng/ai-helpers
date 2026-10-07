# Manifest runner smoke evals

Two small evals test the independent manifest runner in
[openshift/release#85160](https://github.com/openshift/release/pull/85160).
The root `evals.yaml` selects both when the manifest or code-review plugin
changes, and selects each when its own fixture changes. Adding the manifest
alone does not enable a CI job.

Both reuse `code-review:classify-review-comment` with one local input and a
deterministic judge. Each makes a real model call but needs no external issue,
cluster snapshot, or LLM judge. Existing eval configurations are unchanged.

## Cases

| Case | Description | Expected severity / topic |
| --- | --- | --- |
| case-001 | Cosmetic trailing whitespace | `nitpick` / `style` |

The [secondary eval](../manifest-smoke-secondary/README.md) has its own
`case-001` describing a blocking nil-pointer bug, expected to produce
`required_change` / `logic_bug`.

Both configurations deliberately share the basename `eval-smoke.yaml`, harness
name `manifest-smoke`, case ID `case-001`, and output filename
`classification.json`. Their distinct inputs and expected labels let us verify
that artifacts belong to the correct eval, even when filenames collide.
Both evals should pass; the second input describes a bug, not a failing test.

Each manifest entry limits case parallelism to one and the outer orchestrator
to 50 turns. Each eval limits the case invocation to 120 seconds and a 1 USD
budget; these are not total job limits and exclude the orchestrators.

A successful smoke run should produce two distinct `evals/<artifact_name>/`
directories in Prow artifacts, each containing its own report, summary, result,
logs and `eval-run.tar`. The artifact root should contain a two-eval HTML index,
aggregate JUnit with two passing testcases, and metrics retaining both runs.
Check the uploaded archives' inputs and classifications as well as directory
names. This checks execution and artifact isolation, not classification quality
across a representative dataset or behavior after an eval fails.
