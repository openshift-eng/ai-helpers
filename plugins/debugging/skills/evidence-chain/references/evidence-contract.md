# Generic Debugging Evidence Contract

Use this contract for any debugging investigation. It records both the evidence
locations a program can validate and the inferential links a reviewer must
judge.

## Document

Write `evidence.json` inside the evidence root:

```json
{
  "schema_version": "1.0",
  "investigation": {
    "question": "Why does the API return stale data after an update?",
    "scope": "service version 2.4.1, single-node development environment, request 7f31",
    "status": "supported"
  },
  "chains": [
    {
      "id": "cache-invalidation",
      "hypothesis": "The update path leaves the read cache populated.",
      "status": "supported",
      "links": [
        {
          "question": "What serves the stale response?",
          "answer": "The read path returns the pre-update value from the cache.",
          "proof": [
            {
              "type": "trace",
              "artifact": "artifacts/request-trace.txt",
              "artifact_url": "https://example.invalid/traces/7f31",
              "lines": [18, 23],
              "note": "The trace identifies a cache hit for request 7f31 and the old object revision."
            }
          ]
        },
        {
          "question": "Why is the old value still cached after the update?",
          "answer": "The successful update path writes the database but does not invalidate this cache key.",
          "proof": [
            {
              "type": "code",
              "artifact": "artifacts/update-path.txt",
              "lines": [41, 58],
              "note": "The executed success branch returns after the database write and contains no invalidation call."
            },
            {
              "type": "log",
              "artifact": "artifacts/service.log",
              "lines": [203, 209],
              "note": "The correlated request completes the database update without the invalidation event emitted by other update paths."
            }
          ]
        }
      ]
    }
  ],
  "conclusion": {
    "answer": "The API returns stale data because the executed update path omits cache invalidation.",
    "chain_ids": ["cache-invalidation"],
    "verification": [
      {
        "method": "counterfactual",
        "claim": "Invalidating the same key after the update makes the next read return the new revision.",
        "proof": [
          {
            "type": "test",
            "artifact": "artifacts/counterfactual-test.txt",
            "lines": [9, 16],
            "note": "The controlled run differs only by cache invalidation and observes the updated revision."
          }
        ]
      }
    ],
    "limitations": []
  }
}
```

## Fields

- `schema_version` must be `1.0`.
- `investigation.question` is the exact question being answered.
- `investigation.scope` identifies the bounded system, input, environment, and
  time or version context where relevant.
- `investigation.status` is `supported` or `inconclusive`.
- `chains` contains the investigated hypotheses. A supported result requires at
  least one chain; an inconclusive result may use an empty array when no usable
  evidence exists. Chain status is `supported`, `ruled_out`, or `inconclusive`;
  retain meaningful alternatives instead of deleting them after the primary
  hypothesis succeeds.
- `links` records one reasoning step at a time as a question, answer, and one or
  more proofs.
- `conclusion.chain_ids` names the chains used to reach the conclusion. It may
  be empty only for an inconclusive result.
- `conclusion.verification` contains a discriminating confirmation. Supported
  results require at least one verification using `reproduction`,
  `counterfactual`, `fix-validation`, `cross-source`, or `other`.
- `conclusion.limitations` is an array of honest evidence gaps. It may be empty
  for a supported result and must be non-empty for an inconclusive one.

## Proof fields

- `type` is one of `log`, `code`, `command`, `configuration`, `metric`, `trace`,
  `test`, `data`, or `other`.
- `artifact` is a local path relative to the evidence root. It must resolve
  inside that root and name a UTF-8 text file.
- `lines` is a two-element, 1-indexed inclusive range in that exact artifact.
  Keep an excerpt at 200 lines or fewer.
- `note` explains how the excerpt supports the answer or verification claim. It
  must not introduce another unsupported claim.
- `artifact_url` is optional. When present it must be a durable `http` or
  `https` source for the local artifact.

## Invariants

- Every reasoning link has proof, including links in ruled-out or inconclusive
  chains. For an inconclusive chain, include only the links proved so far and
  record the unproved next step as a limitation.
- An evidence-free investigation still produces and hydrates a contract with
  empty `chains`, empty `chain_ids`, and an explicit limitation, but it cannot
  be `supported`.
- A `supported` investigation has at least one supported chain and at least one
  independent verification.
- `chain_ids` are unique and refer to existing chains.
- Validation establishes structure, path safety, and citation accuracy. It
  cannot establish causality, source trustworthiness, completeness, or the
  semantic truth of a note; the proof review covers those properties.
