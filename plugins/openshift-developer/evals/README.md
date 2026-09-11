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

## address-ci-failures (`cases/address-ci-failures`)

Whether the address-ci-failures skill correctly classifies CI failures and
decides fix vs report per TRT-2831 guardrails.

| Case | Description |
|------|-------------|
| case-001 | Pre-existing npm audit CVE on unchanged deps (TRT-2831 canonical) |
| case-002 | PR-caused unit test failure in modified file |
| case-003 | Infrastructure failure (pod_pending) |
| case-004 | Optional job — do not fix without slam-dunk PR-caused evidence |

## solve (`cases/solve`)

Direct end-to-end evaluation of the jira-solve orchestrator against the
immutable commit immediately before a known-good PR. The eval initializes the
case workspace as the target repository and lets jira-solve select its own
skill chain.

| Case | JIRA | Description |
|------|------|-------------|
| case-001 | OCPBUGS-34662 | HyperShift jira-solve pipeline (known-good PR #7538) |
| case-002 | OCPBUGS-120802 | Preserve webhook certificates on transient API errors (PR #9507) |
| case-003 | OCPBUGS-119976 | Include unavailable components in KAS load-balancer status (PR #9502) |
| case-004 | OCPBUGS-100141 | Propagate proxy configuration to AWS cloud-controller-manager (PR #9156) |
| case-005 | OCPBUGS-85182 | Remove obsolete MutatingAdmissionPolicy runtime configuration (PR #9350) |
