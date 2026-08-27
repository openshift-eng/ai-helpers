# Payload Analysis Evidence Contract

Use this contract after the per-job investigations finish and before candidate
scoring. It makes each root-cause claim independently checkable instead of
leaving citations embedded only in prose.

## Document

Write `payload-evidence-<sanitized-tag>.json` in the analysis output directory:

```json
{
  "payload_tag": "4.22.0-0.nightly-2026-02-25-152806",
  "jobs": [
    {
      "job_name": "periodic-ci-...-e2e-aws-ovn",
      "causal_chain": [
        {
          "question": "Why did this job fail?",
          "answer": "The test timed out because ovnkube-controller repeatedly failed to reconcile the gateway.",
          "proof": [
            {
              "type": "log",
              "artifact": "payload-evidence/e2e-aws-ovn/ovnkube-controller.log",
              "artifact_url": "https://gcsweb-ci.example/artifacts/ovnkube-controller.log",
              "lines": [412, 417],
              "note": "These retries cover the failing operation and end with the timeout reported by the test."
            }
          ]
        },
        {
          "question": "Why did gateway reconciliation fail?",
          "answer": "The controller rejected the selected gateway mode as unsupported.",
          "proof": [
            {
              "type": "log",
              "artifact": "payload-evidence/e2e-aws-ovn/ovnkube-controller.log",
              "artifact_url": "https://gcsweb-ci.example/artifacts/ovnkube-controller.log",
              "lines": [389, 396],
              "note": "The controller emits the unsupported-mode error from the reconcile path immediately before retrying."
            },
            {
              "type": "code",
              "artifact": "payload-evidence/e2e-aws-ovn/pr-2037-controller.diff",
              "artifact_url": "https://github.com/openshift/cno/pull/2037/files",
              "lines": [73, 91],
              "note": "The candidate changes the branch that validates the same gateway-mode value."
            }
          ]
        }
      ]
    }
  ]
}
```

## Rules

- Start every chain with exactly `Why did this job fail?`.
- Use one causal layer per link. The next question must ask why the previous
  answer occurred; do not jump directly from a test symptom to a candidate PR.
- Every link needs at least one proof. Stop with an explicit unknown when the
  next layer cannot be proved.
- `artifact` is a path relative to the analysis output directory. Copy each
  cited log or diff under `payload-evidence/<job-slug>/`; do not cite transient
  paths outside the output directory.
- `lines` is a 1-indexed inclusive range in that exact local artifact.
- `artifact_url` is the durable upstream URL when one exists.
- `note` explains how the excerpt proves the answer. It must not introduce a
  separate unsupported claim.

## Validate and hydrate

Run:

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/validate_evidence.py" \
  "$OUTPUT_DIR/payload-evidence-$SANITIZED_TAG.json" \
  --root "$OUTPUT_DIR" \
  --summary "$SNAPSHOT_DIR/summary.json" \
  --render "$OUTPUT_DIR/payload-evidence-$SANITIZED_TAG.md"
```

The command fails for missing artifacts, escaping paths, malformed or
out-of-range line references, empty answers, missing failed jobs, or unsupported causal links. The
rendered Markdown contains the exact line-numbered excerpts and is the evidence
document supplied to scoring, report generation, and completeness review.
