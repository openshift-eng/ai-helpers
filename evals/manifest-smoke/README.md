# Manifest runner smoke eval

One small eval for testing the independent manifest runner in
[openshift/release#85160](https://github.com/openshift/release/pull/85160).
The root `evals.yaml` selects this eval when its inputs or the code-review
plugin change. Adding the manifest alone does not enable a CI job.

This reuses `code-review:classify-review-comment` with one local input and a
deterministic judge. It makes a real model call but needs no external issue,
cluster snapshot, or LLM judge. Existing eval configurations are unchanged.

## Cases

| Case | Description |
| --- | --- |
| case-001 | Classify an explicitly cosmetic trailing-whitespace comment as a style nitpick and write a valid JSON result. |

The manifest limits case parallelism to one and the outer orchestrator to
50 turns. The eval limits the case invocation to 120 seconds and a 1 USD
budget; this is not a total job budget and does not include the orchestrator.

A successful smoke run should produce the eval's report, result, logs and
run archive under `evals/<artifact_name>/` in Prow artifacts, with aggregate
JUnit and an HTML index at the artifact root. This checks the execution path,
not classification quality across a representative dataset.
