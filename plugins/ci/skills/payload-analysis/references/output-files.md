# Output Files

Generate every output from `analysis-state.yaml`. Do not recalculate causes or
scores while formatting.

## Create the payload results YAML

1. Load `ci:payload-results-yaml`.
2. Follow its current schema exactly.
3. Include:
   - metadata and the snapshot's phase;
   - every failed blocking job, including jobs with no candidate;
   - every scored PR or causal CI-configuration candidate;
   - confidence, rationale, revert gates, and `revert_eligible`;
   - existing actions;
   - RHCOS suspects when present.
4. Preserve unresolved causes as unresolved.
5. Run the bundled validator and fix every error.

## Create the autodl JSON

1. Load `ci:payload-autodl-json`.
2. Generate one row for every `(failed blocking job, candidate)` pair.
3. Generate the required no-candidate row for each job without a candidate.
4. Encode every row value as a string.

## Create the HTML report

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

## Validate all outputs

Verify:

- exact filenames under `OUTPUT_DIR`;
- every file is non-empty;
- phase, failure count, per-job root cause, candidate score, eligibility, and
  action agree across HTML, YAML, and JSON;
- infrastructure causes retain `failure_type: infra` even when a test detected
  the failure;
- the HTML never recommends a candidate whose YAML says
  `revert_eligible: false`.

Complete this step only when the YAML validator passes and all three outputs
agree on every cause and action.
