Find CRD YAMLs anywhere in the repo (not just helm/*/crds/):
  find . -name '*.yaml' -not -path '*/vendor/*' -exec grep -l 'kind: CustomResourceDefinition' {} \;

If CRDs are found:

1. Count files where `format: int32` immediately precedes
   `maximum: 4294967295` (these need format: int64).
2. Count CRDs that lost metadata.name pattern validation
   compared to the base branch. Detect the base branch with
   `git merge-base HEAD main 2>/dev/null || git merge-base HEAD master`,
   then use `git show <base>:path` to check the original.

Report both counts.

If no CRDs found in the repo, report 0 for both.

Rules: report specific counts, not "looks good." You are
read-only — do not edit files. Cite file:line for any issues.
