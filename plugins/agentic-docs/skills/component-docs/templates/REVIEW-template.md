# Review instructions

<!-- REVIEW.md is the single source of truth for code review tools (Claude Code Review, CodeRabbit).
     .coderabbit.yaml is a structured sidecar that points CodeRabbit at this file and translates
     skip/path rules into native format. Keep them in sync — one is the translation of the other.

     Writing conventions:
     - Tool-agnostic severity: "must fix before merge" / "worth fixing, not blocking" / "suggestion only"
     - Glob patterns for skips (e.g., `**/clientset/**`) rather than prose
     - Path rules as markdown subsections with glob headers
     - Imperative phrasing: "Flag X as must-fix" rather than "X is considered important"
     - Target 60-80 lines, soft cap 100 — length dilutes signal

     Don'ts:
     - Don't copy CLAUDE.md content into REVIEW.md — different purposes
     - Don't include vague dev-guide guidance — only diff-enforceable rules
     - Don't duplicate CI — suppress those categories, don't re-enforce
     - Don't use tool-specific severity markers — natural language only
-->

## Must fix before merge

<!-- Phase 9.5 — Fill based on repo type detected in Phase 5:

     OPERATORS: Flag as must-fix: incorrect reconciliation logic, unscoped queries
     crossing tenant boundaries, resource leaks, upgrade/downgrade safety violations,
     breaking changes to GA openshift.io APIs, unmitigated security vulnerabilities,
     Available=False or Degraded=True during normal upgrade, premature version bump
     in ClusterOperator status. Style and naming are minor at most.

     LIBRARIES: Flag as must-fix: API convention violations (bool fields, annotation-based
     APIs, missing validation markers, pointer misuse in CRDs), breaking changes to
     stable APIs, functions added to openshift/api.

     CLIs: Flag as must-fix: breaking changes to CLI behavior, security vulnerabilities,
     incorrect error codes or output format changes.

     Source: openshift/enhancements dev-guide/api-conventions.md, dev-guide/breaking-changes.md,
     CONVENTIONS.md, dev-guide/operators.md, guidelines/supportability.md
-->

## Minor issue volume

<!-- Phase 9.5 — Default: "Report at most five minor issues. Overflow: 'plus N similar items'
     in the summary. If all minor, lead with 'No blocking issues.'"
     Adjust count based on repo complexity if needed. -->

## Do not report

<!-- Phase 9.5 — Fill from Phase 5 CI enforcement discovery + generated code inventory.

     Always include these categories:
     - CI-enforced: lint, gofmt, govet, type-check (discovered from `grep Makefile`)
     - Generated: `zz_generated*`, `**/clientset/**`, `**/informers/**`, `**/listers/**`
     - Vendored: `vendor/**`
     - Lockfiles: `go.sum`, `go.mod` (review dep bumps separately)

     Repo-specific additions from Phase 5:
     - Generated dashboards/assets if present (e.g., `assets/**`)
     - Bindata files if present (e.g., `**/bindata.go`)
     - Protobuf generated files (e.g., `generated.pb.go`, `generated.proto`)
     - Payload manifests if present (e.g., `payload-manifests/**`)

     Use glob patterns, not prose descriptions.
-->

## Always check

<!-- Phase 9.5 — Fill from repo-type platform rules + Phase 5 discoveries.

     OPERATORS (all apply):
     - Feature gates: alpha behind TechPreviewNoUpgrade (guidelines/supportability.md)
     - API fields: no bool fields, no CRD pointers unless zero vs unset; config APIs
       default in controller (dev-guide/api-conventions.md)
     - HA: 2 replicas + hard anti-affinity on hostname (CONVENTIONS.md)
     - "OpenShift" never "Openshift" (CONVENTIONS.md)
     - Breaking GA API changes -> must-fix (dev-guide/breaking-changes.md)
     - No PII in logs (email, tokens, request bodies)
     - Resource requests required, limits forbidden (CONVENTIONS.md)
     - Never tolerate node.kubernetes.io/unschedulable (CONVENTIONS.md)
     - Status conditions: reason+message for happy AND sad states (clusteroperator.md)
     - Leader election: 137/107/26s defaults (CONVENTIONS.md)
     - Metrics: HTTPS + TLS client certs (CONVENTIONS.md)

     LIBRARIES:
     - API conventions: no bool fields, no functions in openshift/api, no annotation APIs
     - Validation markers match godoc constraints
     - Object references use resource-specific types

     CLIs:
     - "OpenShift" never "Openshift"
     - CLI elements default to API tier 1

     Cite the dev-guide source for each rule (parenthetical at end of line).
-->

## Verification bar

<!-- Phase 9.5 — Default: "Every comment must cite file:line evidence from the diff
     or linked source. If you cannot point to a specific line, do not post the comment.
     Read surrounding context (at minimum the enclosing function) before flagging — the
     answer may be ten lines below the diff hunk."

     This prevents hallucinated or context-free comments. Adjust wording to match
     repo conventions if needed, but always require concrete evidence. -->

## Re-review

<!-- Phase 9.5 — Default: "On re-review of an updated PR, only comment on lines that
     changed since the last review. Do not re-raise resolved issues or introduce new
     nits on unchanged code. Converge toward approval."

     This prevents review ping-pong where the reviewer raises new issues on
     unchanged code each round. Adjust wording if the repo has a different
     re-review policy. -->

## Path-specific rules

<!-- Phase 9.5 — Fill from Phase 5 framework split + naming conventions.

     Use glob headers for each path. Example:

     ### `pkg/controller/**`
     Verify apply method matches existing controllers. Do not mix SSA
     and strategic merge within the same controller package.

     ### `test/**`
     Jira component annotation required. Always produce JUnit result.
     Narrow scope; exclude must-gather namespaces (dev-guide/test-conventions.md).

     ### `vendor/**`
     Do not review — vendored code is upstream's responsibility.
     Review go.mod changes for dependency bumps separately.

     Add subsections based on Phase 5 discoveries — only for paths where
     the repo has specific conventions that differ from the repo-wide rules.
-->
