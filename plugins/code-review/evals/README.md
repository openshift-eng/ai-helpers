# Code Review Plugin Evals

Index of what each opaque `case-NNN` directory tests.

## classify-review-comment (`cases/classify-review-comment`)

Whether the review-comment classifier assigns the correct category to each
seeded PR comment.

| Case | Expected classification / focus |
|------|---------------------------------|
| case-001 | Nitpick — style |
| case-002 | Question — API design |
| case-003 | Required change — nil panic |
| case-004 | Required change — install failure |
| case-005 | Required change — test gap |
| case-006 | Suggestion — CI rebase |
| case-007 | Required change — process |
| case-008 | Suggestion — CI override |
| case-009 | Unclassified — approval |
| case-010 | Unclassified — process duplicate |
| case-011 | Required change — root cause |
| case-012 | Suggestion — architecture |
| case-013 | Required change — security |
| case-014 | CodeRabbit — logic bug |
