# CI Plugin Evals

Index of what each opaque `case-NNN` directory tests.

## bulk-triage-regressions (`cases/bulk-triage-regressions`)

Phase 3 mechanism-verification of `ci:bulk-triage-regressions` against real
mis-diagnosed duty-run regressions.

| Case | JIRA | Description |
|------|------|-------------|
| case-001 | OCPBUGS-100316 | VAP denial mechanism |
| case-002 | OCPBUGS-99918 | GID mapping producer |
| case-003 | OCPBUGS-94106 | etcd vs router victim |
| case-004 | OCPBUGS-100392 | security-penetration interference |
| case-005 | OCPBUGS-99220 | CBO flap / duplicate-avoidance trap |

## detect-permafail (`cases/detect-permafail`)

Whether `ci:detect-permafail` correctly distinguishes permafails from
below-threshold and infra-driven failures.

| Case | Description |
|------|-------------|
| case-001 | Test below permafail threshold |
| case-002 | Genuine test permafail |
| case-003 | Mixed set containing a test permafail |
| case-004 | Mixed set with diverse infra failures |
| case-005 | Mixed set with infra-driven permafail |
| case-006 | Informing tests correctly ignored |

## payload-analysis (`cases/payload-analysis`)

Root-cause and revert-recommendation quality for `ci:payload-analysis` across
accepted/rejected payload snapshots.

| Case | Description |
|------|-------------|
| case-001 | 4.22 nightly — CI-config and product regression |
| case-002 | 5.0 nightly — all-new failures |
| case-003 | 5.0 CI — CNO NetworkPolicy revert |
| case-004 | 4.22 — two reverts |
| case-005 | 4.22 CI — CCO revert |
| case-006 | 4.22 CI — HyperShift revert |
| case-007 | 4.22 — OLM revert |
| case-008 | 5.0 nightly — CMO monitoring revert |
| case-009 | 5.0 CI — HyperShift builder false positive |
| case-010 | 4.18 — rejected, multiple failures |
| case-011 | 5.0 CI — infra-only, no candidates |
| case-012 | 4.20 — rejected streak |
| case-013 | 4.20 — accepted with failures |
| case-014 | 5.0 nightly — step-registry infra change |

## prow-job-analysis (`cases/prow-job-analysis`)

Failure root-cause analysis for `ci:prow-job-analysis`. (Numbering is
non-contiguous; retired cases leave gaps.)

| Case | Description |
|------|-------------|
| case-002 | Extension binary panic — pending spec |
| case-003 | Missing oc-mirror extension binary |
| case-004 | Aggregated router metrics regression |
| case-005 | HyperShift snapshot-controller CRD race |
| case-006 | vSphere TechPreview MCO render mismatch |
| case-007 | Upgrade — node-lifecycle NotReady |
| case-008 | Upgrade — kube-apiserver non-graceful shutdown |
| case-010 | Insights external gateway 500 |
| case-011 | EgressIP SNAT regression |
| case-012 | Build-farm disk-pressure eviction |
| case-013 | ROSA NAT gateway quota |
