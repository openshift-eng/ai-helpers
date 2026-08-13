# OpenShift Developer Plugin Evals

Index of what each opaque `case-NNN` directory tests.

## address-reviews (`cases/address-reviews`)

Whether the address-reviews flow deduplicates bot replies, categorizes review
comments correctly, prioritizes, and formats replies.

| Case | Description |
|------|-------------|
| case-001 | Duplicate bot reply |
| case-002 | Duplicate — extreme |
| case-003 | Categorize — question |
| case-004 | Categorize — question (variant 2) |
| case-005 | Categorize — change request |
| case-006 | Categorize — dead code |
| case-007 | Categorize — suggestion |
| case-008 | Categorize — action instruction |
| case-009 | Prioritize — mixed |
| case-010 | Filter — CodeRabbit comment kept |
| case-011 | Reply format |
| case-012 | CI push override |
| case-013 | Response — question, no change |
| case-014 | Response — imperative change |

## solve (`cases/solve`)

End-to-end jira-solve pipeline against a snapshot branch with a known-good PR.

| Case | JIRA | Description |
|------|------|-------------|
| case-001 | OCPBUGS-34662 | HyperShift jira-solve pipeline (known-good PR #7538) |
