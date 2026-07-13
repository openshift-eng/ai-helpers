Read the patterns doc (find k8s-rebase-patterns.md in the plugin
directory). Step 2 already verified autofix patterns (deprecated
APIs, CRD validation, feature gates, e2e infra). Do NOT re-check
those — focus on CI-specific gaps that only matter at ship time:

1. Does any e2e test or CI config reference a hardcoded k8s
   version, KIND image tag, or container image that needs updating?
   Check ALL workflow files for KIND binary version consistency:
   `grep -rn 'kind.sigs.k8s.io/dl/v\|KIND_VERSION=v' .github/ --include="*.yml" --include="*.yaml" 2>/dev/null`
2. Are there test skips that should be added or removed for this
   k8s version?
3. Are there patterns in the doc that the agent should have fixed
   manually (e.g., KubeVirt test, hybrid-overlay timing) but
   didn't? Check the branch diff for these fixes.
4. Would the KIND image tag actually exist? (Check if
   kindest/node:<version> is published)

Flag gaps that would cause CI failures. List each item checked
and your finding.

Rules: you are read-only — do not edit files. Cite file:line
for any issues.
