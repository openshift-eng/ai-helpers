---
name: image-repo-mapping
description: Map a container image name (from a Jira ticket summary, pscomponent label, or Downstream Component Name field) to the GitHub repository that should be cloned for CVE impact analysis
---

# Image to Repository Mapping

Translates a container image name into the GitHub repository URL to clone for analysis. Image names appear in the ticket summary, `pscomponent:` labels, and the `Downstream Component Name` custom field.

## When to Use This Skill

Use this skill when:
- An image name has been extracted from a Jira ticket (summary, label, or custom field)
- The user passes `--repo=<image-name>` using a short image name rather than a full GitHub URL
- Phase 0.7 needs to determine which repository to clone

---

## Resolution Order

Apply these in order and stop at the first match:

1. **Full GitHub URL supplied** (`--repo=https://github.com/...`) → use directly, skip this skill.
2. **Exact image name match** — look the image name up in the table below.
3. **Prefix match** — strip version suffixes (e.g. `-1-0`, `-1-12-4`, `-rhel9`, `-rhel8`) and re-match.
4. **Keyword match** — check the per-section keyword rules at the bottom of each group.
5. **NOT FOUND → Exit immediately** with the error message below. Do not guess. Do not proceed with analysis.

> **Tip:** Strip `pkg:oci/` prefix before matching (e.g. `pkg:oci/ose-ansible-operator` → `ose-ansible-operator`).

### Not-Found Exit

If no match is found after all steps above, **stop immediately** and output:

```
❌ Repository mapping not found for image: <image_name>

The image "<image_name>" is not in the known mapping table and could not
be resolved automatically.

To proceed, re-run with an explicit repository URL:

  --repo=https://github.com/org/repo

Or add the mapping to:
  plugins/compliance/skills/image-repo-mapping/SKILL.md

Do NOT continue analysis without a confirmed source repository.
```

Do NOT fall back to guessing, fuzzy matching, or prompting the user inline. Exit the command at this point.

---

## Two Repository Patterns

Components fall into one of two patterns. The resolution output is different for each.

### Pattern A — Direct repo

Clone the mapped repo directly at the mapped branch. Used by: Operator SDK, Ansible Operator, must-gather, Secrets Store CSI.

```
image → repo URL + branch
```

### Pattern B — Release repo with git submodules

Some components use a dedicated `-release` repo that aggregates all component repos as git submodules. The release repo branch pins each submodule to the exact commit/tag used for that release. Used by: cert-manager, ZTWIM, ESO.

**Resolution steps for Pattern B:**
1. Clone the **release repo** at the mapped release branch
2. Read `.gitmodules` from that branch to find the submodule entry matching the target image
3. Extract the submodule `url` and `branch`/`tag` from `.gitmodules`
4. Clone the **component repo** at that pinned ref for analysis

```bash
# Step 1: Clone release repo at correct branch
git clone --depth=1 -b "${RELEASE_BRANCH}" "${RELEASE_REPO_URL}" /tmp/release-repo

# Step 2: Read .gitmodules
cat /tmp/release-repo/.gitmodules

# Step 3: Extract the relevant submodule url + branch/tag
# Step 4: Clone component repo at pinned ref
git clone --depth=50 -b "${COMPONENT_BRANCH}" "${COMPONENT_URL}" "${REPO_DIR}"
# or for a tag:
git clone --depth=1 --branch "${COMPONENT_TAG}" "${COMPONENT_URL}" "${REPO_DIR}"
```

**Jira branch → release branch naming for Pattern B:**

| Jira `BRANCH` value | Release branch |
|---|---|
| `cert-manager-X-Y` | `release-X.Y` in `cert-manager-operator-release` |
| `external-secrets-X-Y` | `release-X.Y` in `external-secrets-operator-release` |
| `ztwim-1.0` | **`release-1.0.0`** in `zero-trust-workload-identity-manager-release` _(one-time exception — team confirmed this was a branching mistake; future releases use `release-X.Y`)_ |
| `ztwim-X.Y` (any other) | `release-X.Y` in `zero-trust-workload-identity-manager-release` |

> **Note:** Jira branch values use hyphens for separators (e.g. `external-secrets-1-0`) while release branches use dots (e.g. `release-1.0`). Strip the component prefix and convert the remaining hyphen-separated version to dot notation.

---

## Image → Repository Map

> Every image name here has appeared in real ticket summaries or labels. This table is intentionally scoped to the components this command has been validated against — extend it as new components come up (see the not-found exit message above).

### cert-manager / jetstack — Pattern B (release repo + submodules)

**Release repo:** `https://github.com/openshift/cert-manager-operator-release`
**Submodules:** `cert-manager-operator`, `cert-manager`, `cert-manager-istio-csr`
**Branch mapping:** Jira `cert-manager-X-Y` → `release-X.Y` in the release repo

Clone the release repo at the correct branch, read `.gitmodules` to find the submodule URL and pinned ref for the target image, then clone that component at the pinned ref.

| Image Name / Prefix | Submodule in `.gitmodules` |
|---|---|
| `cert-manager/cert-manager-operator-rhel9`, `cert-manager/cert-manager-operator-bundle`, `cert-manager-operator-*` | `cert-manager-operator` |
| `cert-manager/cert-manager-istio-csr-rhel9` | `cert-manager-istio-csr` |
| `cert-manager/jetstack-cert-manager-*`, `jetstack-cert-manager-*`, `redhat-user-workloads/jetstack-cert-manager-*` | `cert-manager` |

#### cert-manager-operator (operator + bundle only)

| Image Name / Prefix | GitHub Repository |
|---|---|
| `cert-manager-operator-container` | `https://github.com/openshift/cert-manager-operator` |
| `cert-manager-operator-rhel9` | `https://github.com/openshift/cert-manager-operator` |
| `cert-manager/cert-manager-operator-rhel9` | `https://github.com/openshift/cert-manager-operator` |
| `cert-manager/cert-manager-operator-bundle` | `https://github.com/openshift/cert-manager-operator` |

#### cert-manager-istio-csr

| Image Name / Prefix | GitHub Repository |
|---|---|
| `cert-manager/cert-manager-istio-csr-rhel9` | `https://github.com/openshift/cert-manager-istio-csr` |

#### jetstack-cert-manager

| Image Name / Prefix | GitHub Repository |
|---|---|
| `cert-manager/jetstack-cert-manager-rhel9` | `https://github.com/openshift/jetstack-cert-manager` |
| `cert-manager/jetstack-cert-manager-acmesolver-rhel9` | `https://github.com/openshift/jetstack-cert-manager` |
| `jetstack-cert-manager-rhel9` | `https://github.com/openshift/jetstack-cert-manager` |
| `jetstack-cert-manager-container` | `https://github.com/openshift/jetstack-cert-manager` |
| `jetstack-cert-manager-acmesolver-rhel9` | `https://github.com/openshift/jetstack-cert-manager` |
| `jetstack-cert-manager-acmesolver-container` | `https://github.com/openshift/jetstack-cert-manager` |
| `redhat-user-workloads/jetstack-cert-manager-*` | `https://github.com/openshift/jetstack-cert-manager` |

**Namespace prefix match:** `cert-manager` → requires full image name lookup above (multiple repos in this namespace).
**Keyword match:** `cert-manager-operator` / `cert-manager-operator-bundle` → `cert-manager-operator`; `cert-manager-istio-csr` → `cert-manager-istio-csr`; `jetstack-cert-manager` → `jetstack-cert-manager`.

---

### Operator SDK / Helm Operator (non-ansible images)

| Image Name / Prefix | GitHub Repository |
|---|---|
| `operator-sdk` | `https://github.com/openshift/ocp-release-operator-sdk` |
| `openshift4/ose-operator-sdk-rhel8` | `https://github.com/openshift/ocp-release-operator-sdk` |
| `openshift4/ose-operator-sdk-rhel9` | `https://github.com/openshift/ocp-release-operator-sdk` |
| `openshift-enterprise-operator-sdk-container` | `https://github.com/openshift/ocp-release-operator-sdk` |
| `openshift4/ose-helm-operator` | `https://github.com/openshift/ocp-release-operator-sdk` |
| `openshift4/ose-helm-rhel9-operator` | `https://github.com/openshift/ocp-release-operator-sdk` |
| `openshift-enterprise-helm-operator-container` | `https://github.com/openshift/ocp-release-operator-sdk` |
| `pkg:oci/ose-operator-sdk-rhel8` | `https://github.com/openshift/ocp-release-operator-sdk` |
| `pkg:oci/ose-operator-sdk-rhel9` | `https://github.com/openshift/ocp-release-operator-sdk` |
| `pkg:oci/ose-helm-operator` | `https://github.com/openshift/ocp-release-operator-sdk` |
| `pkg:oci/openshift-enterprise-helm-operator` | `https://github.com/openshift/ocp-release-operator-sdk` |

---

### Ansible Operator

| Image Name / Prefix | GitHub Repository |
|---|---|
| `ansible-operator-plugins` | `https://github.com/openshift/ansible-operator-plugins` |
| `openshift4/ose-ansible-operator` | `https://github.com/openshift/ansible-operator-plugins` |
| `openshift4/ose-ansible-rhel9-operator` | `https://github.com/openshift/ansible-operator-plugins` |
| `openshift-enterprise-ansible-operator-container` | `https://github.com/openshift/ansible-operator-plugins` |
| `pkg:oci/ose-ansible-operator` | `https://github.com/openshift/ansible-operator-plugins` |
| `pkg:oci/ose-ansible-rhel9-operator` | `https://github.com/openshift/ansible-operator-plugins` |

**Keyword match:** any image containing `ansible-operator` → `https://github.com/openshift/ansible-operator-plugins`

---

### External Secrets Operator — Pattern B (release repo + submodules)

**Release repo:** `https://github.com/openshift/external-secrets-operator-release`
**Submodules:** `external-secrets-operator`, `external-secrets`, `bitwarden-sdk-server`
**Branch mapping:** Jira `external-secrets-X-Y` → `release-X.Y` in the release repo

Clone the release repo at the correct branch, read `.gitmodules` to find the submodule URL and pinned ref for the target image, then clone that component at the pinned ref.

| Image Name / Prefix | Submodule in `.gitmodules` |
|---|---|
| `external-secrets-operator/external-secrets-operator-rhel9`, `external-secrets-operator/external-secrets-operator-bundle`, `redhat-user-workloads/external-secrets-operator-*` | `external-secrets-operator` |
| `external-secrets-operator/external-secrets-rhel9`, `redhat-user-workloads/external-secrets-1-0` | `external-secrets` |
| `external-secrets-operator/bitwarden-sdk-server-rhel9`, `redhat-user-workloads/bitwarden-sdk-server-*` | `bitwarden-sdk-server` |

**Keyword match:** `external-secrets-operator` / `external-secrets-operator-bundle` → submodule `external-secrets-operator`; `bitwarden-sdk-server` → submodule `bitwarden-sdk-server`; `external-secrets-rhel9` / `external-secrets-1-0` → submodule `external-secrets`.

---

### Zero Trust / SPIFFE / SPIRE — Pattern B (release repo + submodules)

**Release repo:** `https://github.com/openshift/zero-trust-workload-identity-manager-release`
**Submodules:** `zero-trust-workload-identity-manager` (spire-operator), `spiffe-spire`, `spiffe-spire-controller-manager`, `spiffe-spiffe-csi`
**Branch mapping:** Jira `ztwim-X.Y` → `release-X.Y` in the release repo

Clone the release repo at the correct branch (`--recurse-submodules` is NOT needed — read `.gitmodules` manually and clone only the relevant submodule), then clone that component at the pinned ref.

| Image Name / Prefix | Submodule in `.gitmodules` |
|---|---|
| `zero-trust-workload-identity-manager/zero-trust-workload-identity-manager-rhel9`, `*-operator-bundle` | `zero-trust-workload-identity-manager` |
| `zero-trust-workload-identity-manager/spiffe-spire-agent-rhel9`, `*spiffe-spire-server*`, `*spire-oidc*`, `redhat-user-workloads/spiffe-spire-*` | `spiffe-spire` |
| `zero-trust-workload-identity-manager/spiffe-spire-controller-manager-rhel9` | `spiffe-spire-controller-manager` |
| `zero-trust-workload-identity-manager/spiffe-csi-driver-rhel9`, `redhat-user-workloads/spiffe-csi-driver-*` | `spiffe-spiffe-csi` |
| `zero-trust-workload-identity-manager/spiffe-helper-rhel9` | `spiffe-spiffe-helper` |

The `zero-trust-workload-identity-manager` namespace spans **four** repositories — match on the full image name, not just the namespace prefix.

#### spire-operator (operator + bundle only)

| Image Name / Prefix | GitHub Repository |
|---|---|
| `zero-trust-workload-identity-manager/zero-trust-workload-identity-manager-rhel9` | `https://github.com/openshift/spire-operator` |
| `zero-trust-workload-identity-manager/zero-trust-workload-identity-manager-operator-bundle` | `https://github.com/openshift/spire-operator` |

#### spiffe-spire (agent, server, OIDC discovery provider)

| Image Name / Prefix | GitHub Repository |
|---|---|
| `zero-trust-workload-identity-manager/spiffe-spire-agent-rhel9` | `https://github.com/openshift/spiffe-spire` |
| `zero-trust-workload-identity-manager/spiffe-spire-server-rhel9` | `https://github.com/openshift/spiffe-spire` |
| `zero-trust-workload-identity-manager/spiffe-spire-oidc-discovery-provider-rhel9` | `https://github.com/openshift/spiffe-spire` |
| `redhat-user-workloads/spiffe-spire-agent-*` | `https://github.com/openshift/spiffe-spire` |
| `redhat-user-workloads/spiffe-spire-server-*` | `https://github.com/openshift/spiffe-spire` |
| `redhat-user-workloads/spiffe-spire-oidc-discovery-provider-*` | `https://github.com/openshift/spiffe-spire` |

#### spiffe-spire-controller-manager

| Image Name / Prefix | GitHub Repository |
|---|---|
| `zero-trust-workload-identity-manager/spiffe-spire-controller-manager-rhel9` | `https://github.com/openshift/spiffe-spire-controller-manager` |

#### spiffe-spiffe-csi (CSI driver)

| Image Name / Prefix | GitHub Repository |
|---|---|
| `zero-trust-workload-identity-manager/spiffe-csi-driver-rhel9` | `https://github.com/openshift/spiffe-spiffe-csi` |
| `redhat-user-workloads/spiffe-csi-driver-*` | `https://github.com/openshift/spiffe-spiffe-csi` |

#### spiffe-spiffe-helper

| Image Name / Prefix | GitHub Repository |
|---|---|
| `zero-trust-workload-identity-manager/spiffe-helper-rhel9` | `https://github.com/openshift/spiffe-spiffe-helper` |

**Namespace prefix match:** `zero-trust-workload-identity-manager` → requires full image name lookup above (multiple repos in this namespace).
**Keyword match:** `spire-agent` / `spire-server` / `spire-oidc` → `https://github.com/openshift/spiffe-spire`; `spire-controller-manager` → `https://github.com/openshift/spiffe-spire-controller-manager`; `spiffe-csi-driver` → `https://github.com/openshift/spiffe-spiffe-csi`; `spiffe-helper` → `https://github.com/openshift/spiffe-spiffe-helper`; `zero-trust-workload-identity-manager` (manager/bundle) → `https://github.com/openshift/spire-operator`.

---

### must-gather

| Image Name / Prefix | GitHub Repository |
|---|---|
| `openshift4/ose-must-gather-rhel9` | `https://github.com/openshift/must-gather` |
| `openshift4/ose-support-log-gather-rhel9-operator` | `https://github.com/openshift/must-gather-operator` |

---

### Secrets Store CSI

The namespace spans **two** repositories. The mustgather image is built from the operator repo.

#### secrets-store-csi-driver-operator (operator, bundle, mustgather)

| Image Name / Prefix | GitHub Repository |
|---|---|
| `openshift4/ose-secrets-store-csi-driver-rhel9-operator` | `https://github.com/openshift/secrets-store-csi-driver-operator` |
| `openshift4/ose-secrets-store-csi-driver-operator-bundle` | `https://github.com/openshift/secrets-store-csi-driver-operator` |
| `ose-secrets-store-csi-driver-operator-container` | `https://github.com/openshift/secrets-store-csi-driver-operator` |
| `openshift4/ose-secrets-store-csi-mustgather-rhel9` | `https://github.com/openshift/secrets-store-csi-driver-operator` |
| `ose-secrets-store-csi-mustgather-container` | `https://github.com/openshift/secrets-store-csi-driver-operator` |

#### secrets-store-csi-driver (driver only)

| Image Name / Prefix | GitHub Repository |
|---|---|
| `openshift4/ose-secrets-store-csi-driver-rhel9` | `https://github.com/openshift/secrets-store-csi-driver` |
| `ose-secrets-store-csi-driver-container` | `https://github.com/openshift/secrets-store-csi-driver` |

**Keyword match:** `secrets-store-csi-mustgather` / `secrets-store-csi-driver-operator` / `secrets-store-csi-driver-operator-bundle` → `secrets-store-csi-driver-operator`; `secrets-store-csi-driver-rhel9` (driver image, not operator) → `secrets-store-csi-driver`.

---

## Return Value

**Success:**
```json
{
  "skill": "image-repo-mapping",
  "status": "success",
  "resolved_repos": [
    {
      "image_name": "openshift4/ose-ansible-rhel9-operator",
      "repo_url": "https://github.com/openshift/ansible-operator-plugins",
      "clone_path": ".work/compliance/analyze-cve/repos/ansible-operator-plugins",
      "confidence": "exact_match",
      "match_method": "exact"
    }
  ],
  "unresolved": [],
  "resolution_method": "summary_image_name"
}
```

**Not found (exit):**
```json
{
  "skill": "image-repo-mapping",
  "status": "not_found",
  "image_name": "<image_name>",
  "error": "No repository mapping found. Re-run with --repo=https://github.com/org/repo or add the mapping to image-repo-mapping/SKILL.md."
}
```

`confidence`: `exact_match`, `prefix_match`, `keyword_match`, `user_provided`

---

## Integration with Parent Command

Called from **Phase 0.7** of `/compliance:analyze-cve` (see `commands/analyze-cve.md`).

**Input:** image name extracted by `jira-cve-extraction` skill (from summary, `pscomponent:` label, or `Downstream Component Name` field), or the short name passed via `--repo=<name>`
**Output:** `(image_name, repo_url, clone_path)` tuple passed to Phase 0.7 for cloning
