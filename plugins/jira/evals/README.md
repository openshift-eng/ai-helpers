# Jira Plugin Evals

Index of what each opaque `case-NNN` directory tests.

## ready-to-solve (`cases/ready-to-solve`)

Whether `jira:ready-to-solve` correctly judges issue readiness (and, in fix
mode, augments the issue).

| Case | Description |
|------|-------------|
| case-001 | Missing standard sections |
| case-002 | Detailed bug, no acceptance criteria |
| case-003 | Has standard sections but ambiguous |
| case-004 | Fix mode |

## pre-refinement (`cases/pre-refinement`)

Whether `jira:pre-refinement` (dry-run) picks the right outcome for a TRT card,
applies the stricter review to assistant-drafted cards, and proposes concise
cards that keep every fact, criterion, link and boundary.

| Case | Description |
|------|-------------|
| case-001 | Well-refined Story: no change |
| case-002 | Wordy generated Story (label and creator): condense to five criteria |
| case-003 | Narrative Bug with a log dump and a raw URL: restructure, keep evidence |
| case-004 | Spike without exit criteria: gap comment only |
| case-005 | Epic: unsupported type |
| case-006 | Re-filed card: duplicate of a closed card, not of a related one |
| case-007 | Follow-up card: related, not a duplicate |
| case-008 | Borderline generated Story (creator only): stricter bar forces a proposal |
| case-009 | Already pre-refined: skipped |
