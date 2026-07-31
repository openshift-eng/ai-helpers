# Output Files

Generate all outputs from `analysis-state.yaml`. Do not independently
recalculate causes while formatting.

## Payload results YAML

Load `ci:payload-results-yaml` and follow its current schema exactly. Include:

- metadata and the snapshot's phase;
- every failed blocking job, including jobs with no candidate;
- every scored PR or causal CI-configuration candidate;
- confidence, itemized rationale, all revert gates, and `revert_eligible`;
- existing actions;
- RHCOS suspects when present.

The job root cause and candidate decisions must match working state. An
unresolved failure remains unresolved in every output.

Validate the YAML with the bundled validator before continuing.

## Autodl JSON

Load `ci:payload-autodl-json` and generate the flat ingestion file. Produce one
row for every `(failed blocking job, candidate)` pair and the required
no-candidate row for a failed job without a candidate. All row values are
strings.

## HTML report

Create a self-contained dark-mode report with embedded CSS and working links.
Put decisions before detail. Include:

1. **Executive Summary**
   - phase, architecture, stream;
   - blocking pass/fail counts;
   - new versus persistent signatures;
   - chain length, last accepted payload, and hours since baseline;
   - concise root causes and immediate actions.
2. **Recommended Reverts**
   - only `revert_eligible: true` candidates;
   - PR, component, confidence, causal chain, and gate evidence;
   - otherwise an explicit **No Recommended Reverts** verdict.
3. **Force-Accept Decision**
   - recommendation and exact reasoning.
4. **Blocking Jobs Summary**
   - every blocking job, status, RHCOS variant, streak, history, and originating
     signature payload.
5. **Failed Job Details**
   - Prow and artifact links;
   - minimal signatures and ordered chains;
   - short source excerpts;
   - competing explanations and missing evidence;
   - candidate score breakdowns.
6. **CI and RHCOS Changes**
   - causal CI changes and RHCOS suspects, clearly distinguished from ordinary
     payload PRs.
7. **Informing and Flake Tests**
   - individual tests only, with the caveat that they do not independently
     reject a payload unless the test itself damages cluster health.
8. **Adversarial Review**
   - review outcome and corrections, or why review was not required.

Use collapsible details for gory evidence. Keep the executive summary and
actions visible without expanding anything.

## Cross-output consistency

Before review, verify:

- exact filenames under `OUTPUT_DIR`;
- every file is non-empty;
- phase, failure count, per-job root cause, candidate score, eligibility, and
  action agree across HTML, YAML, and JSON;
- infrastructure causes retain `failure_type: infra` even when a test detected
  the failure;
- the HTML never recommends a candidate whose YAML says
  `revert_eligible: false`.
