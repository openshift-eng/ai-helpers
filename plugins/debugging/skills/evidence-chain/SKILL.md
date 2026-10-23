---
name: evidence-chain
description: Use whenever debugging, diagnosing, troubleshooting, root-causing, or investigating unexpected behavior in software, systems, configuration, data, or automation. Proves conclusions with a validated and hydrated evidence chain.
---

# Evidence Chain

Make a debugging conclusion independently checkable. This skill applies to any
debugging workflow, including investigations started through another command or
domain-specific skill; it is not limited to failed jobs or causal questions
that begin with "why."

## Required outcome

A debugging result is complete only when all of these exist:

1. A machine-readable evidence contract containing the investigation scope,
   hypotheses, reasoning links, exact artifact citations, and conclusion.
2. A successful deterministic validation and a hydrated Markdown report with
   the cited source lines embedded.
3. A semantic proof review that checks the links, alternatives, and independent
   verification rather than trusting the contract's shape.

If decisive evidence is unavailable or review finds an unsupported link, report
the investigation as `inconclusive`. Never promote a plausible hypothesis to a
fact merely because the contract validates.

## Workflow

### 1. Frame the investigation

Write one answerable question and an explicit scope before collecting evidence.
Record relevant versions, time windows, environments, inputs, and boundaries.
Do not silently expand the user's requested scope or make external changes just
to obtain stronger proof.

Choose an evidence root approved for task output. In a repository, prefer
`.work/debugging/<short-investigation-name>/`. Keep the contract, hydrated
report, and copied text artifacts together so another investigator can inspect
them without relying on transient terminal output.

### 2. Investigate and preserve evidence

Use the tools and specialized skills appropriate to the domain. Test competing
hypotheses when practical. For every load-bearing claim, preserve the relevant
log, source, diff, command output, configuration, trace, metric, test result, or
data excerpt as a UTF-8 text artifact inside the evidence root.

Prefer primary artifacts and minimal excerpts that include enough context to
identify the operation, subject, and outcome. Record counterevidence and failed
hypotheses; do not select only observations that favor the final explanation.
Do not copy secrets or sensitive data into the evidence bundle. Use a sanitized
artifact and state the resulting limitation when redaction affects verification.

### 3. Write the contract

Read [the evidence contract](references/evidence-contract.md) and write
`evidence.json` in the evidence root. Each reasoning link needs at least one
exact, 1-indexed inclusive line range in a local artifact and a note explaining
what that excerpt proves.

Use one causal or inferential step per link. A source that merely repeats the
symptom does not prove its cause. Stop at the deepest supported claim and put
the remaining gap in `limitations` rather than inventing the next link.

### 4. Validate and hydrate

Run:

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/validate_evidence.py" \
  /path/to/evidence.json \
  --root /path/to/evidence-root \
  --render /path/to/evidence.md
```

The validator rejects malformed contracts, unsupported proof types, missing or
escaping artifacts, invalid line ranges, unknown chain references, and
supported conclusions without verification. Fix every reported error and rerun
it. Do not hand-edit the hydrated report; it must remain reproducible from the
JSON contract and local artifacts.

### 5. Review the proof

Read [the proof review](references/proof-review.md). Give a separate review pass
only the framed question and scope, contract, hydrated report, and necessary
domain context. Use a fresh reviewer when delegation is available; otherwise
perform the same adversarial pass explicitly after validation.

Repair rejected or weak links, collect better evidence when within scope, then
validate and review again. Deterministic validation proves that citations exist
and were copied accurately. Only the review can judge whether they demonstrate
the claimed mechanism.

### 6. Report

State:

- the conclusion and `supported` or `inconclusive` status;
- the contract and hydrated report paths;
- how the conclusion was independently verified;
- alternatives ruled out and material counterevidence; and
- limitations or missing evidence.

Do not state a more specific or more confident conclusion than the validated
and reviewed chain supports.
