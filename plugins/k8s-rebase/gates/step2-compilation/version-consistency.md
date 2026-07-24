Count go.mod files where k8s.io/* dependency versions are
inconsistent (e.g., k8s.io/api at v0.36 but k8s.io/client-go
at v0.35). For each module with a vendor/ directory, verify
vendor is in sync with go.mod (check vendor/modules.txt).
Report inconsistency count.

Rules: report specific counts, not "looks good." You are
read-only — do not edit files. Cite file:line for any issues.
