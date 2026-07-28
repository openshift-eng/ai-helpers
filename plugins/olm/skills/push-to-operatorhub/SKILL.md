---
name: push-to-operatorhub
description: Guide and automate publishing a Hive operator release to both Kubernetes and Red Hat OpenShift OperatorHub repositories, following the Hive SOP. Validates prerequisites, runs bundle generation, and monitors resulting PRs.
---

# Push to OperatorHub

Walks through the end-to-end process of publishing a Hive operator release to OperatorHub, following the [Hive SOP](https://github.com/openshift/hive-sops/blob/master/sop/PushToOperatorHub.md). The skill validates prerequisites, guides setup of anything missing, runs the bundle generation script, and monitors the resulting PRs.

For background on how bundles, channels, and catalogs work, refer to the [OperatorHub Workflow primer](https://github.com/openshift/hive-sops/blob/master/sop/OperatorHubWorkFlow.md).

## Arguments

- `$1` (optional): The hive commit SHA to publish. Defaults to current `HEAD` of `master`.
- `--dry-run`: Pass through `--dry-run` to `bundle-gen.sh` to skip image build and PR creation.
- `--hold`: Pass through `--hold` to create PRs with `/hold` to prevent automatic merge.
- `--github-user <user>`: Override the GitHub username for PR creation.

## Workflow

Execute the following phases in order. Stop and report to the user at any phase that fails.

---

### Phase 1: Validate Prerequisites

Check each prerequisite and report a summary table showing pass/fail status. Any failure here blocks subsequent phases.

#### Step 1.1 — Check required tools

```bash
# All three checks in one pass
for tool in gh yq docker podman buildah; do
  if command -v "$tool" &>/dev/null; then
    echo "OK: $tool found ($(command -v "$tool"))"
  else
    echo "MISSING: $tool"
  fi
done
```

- `gh` CLI is required. Verify it is authenticated: `gh auth status`.
- `yq` must be v4 (developed against v4.47.1 — see `YQ_VERSION` in the hive `Makefile`; any recent v4 release should work). Verify: `yq --version` should show `v4.x`.
- At least one of `docker`, `podman`, or `buildah` is required for image builds.

#### Step 1.2 — Check GitHub token

```bash
TOKEN="${GITHUB_TOKEN:-$GH_TOKEN}"
if [ -n "$TOKEN" ]; then
  echo "OK: GitHub token is set (via ${GITHUB_TOKEN:+GITHUB_TOKEN}${GH_TOKEN:+GH_TOKEN})"
else
  echo "MISSING: Neither GITHUB_TOKEN nor GH_TOKEN is set"
fi
```

> **MANUAL STEP**: If neither `GITHUB_TOKEN` nor `GH_TOKEN` is set, the user must create or renew a [GitHub personal access token](https://github.com/settings/tokens) with full repo permissions and export it:
> ```bash
> export GITHUB_TOKEN="<token>"
> ```
> Alternatively, authenticate via `gh auth login` — the `gh` CLI and `bundle-gen.sh` will pick up the token automatically.

#### Step 1.3 — Check GitHub username

```bash
GH_USER="${GITHUB_USER:-$(gh api user --jq .login 2>/dev/null)}"
if [ -z "$GH_USER" ]; then
  echo "WARN: Could not determine GitHub username — set GITHUB_USER or pass --github-user"
else
  echo "GitHub user will be: $GH_USER"
  echo "Verify this matches your GitHub username. If not, pass --github-user to the skill."
fi
```

#### Step 1.4 — Check Quay.io access (bot account)

The `openshift-hive` Quay organization has a bot account with write permissions to push images. This skill uses that bot account exclusively.

**Step 1.4a — Check bot token is available**

```bash
if [ -n "$QUAY_BOT_TOKEN" ]; then
  echo "OK: QUAY_BOT_TOKEN is set"
else
  echo "MISSING: QUAY_BOT_TOKEN environment variable"
  echo "Obtain the bot robot token from your team's secrets manager and export it:"
  echo '  export QUAY_BOT_TOKEN="<token>"'
fi
```

> If `QUAY_BOT_TOKEN` is not set, the user must retrieve it from the team's secrets manager and export it. Do **not** hardcode the token anywhere.

**Step 1.4b — Login to Quay.io with the bot account**

```bash
if command -v podman &>/dev/null; then
  echo "$QUAY_BOT_TOKEN" | podman login -u="openshift-hive+hive_bot" --password-stdin quay.io && \
    echo "OK: Logged into quay.io as bot" || \
    echo "FAIL: Bot login failed — check QUAY_BOT_TOKEN"
elif command -v docker &>/dev/null; then
  echo "$QUAY_BOT_TOKEN" | docker login -u="openshift-hive+hive_bot" --password-stdin quay.io && \
    echo "OK: Logged into quay.io as bot" || \
    echo "FAIL: Bot login failed — check QUAY_BOT_TOKEN"
elif command -v buildah &>/dev/null; then
  echo "$QUAY_BOT_TOKEN" | buildah login -u="openshift-hive+hive_bot" --password-stdin quay.io && \
    echo "OK: Logged into quay.io as bot" || \
    echo "FAIL: Bot login failed — check QUAY_BOT_TOKEN"
else
  echo "FAIL: No container runtime (docker/podman/buildah) available"
fi
```

**Step 1.4c — Verify registry read access**

```bash
# Read-access check — confirms credentials can reach the repo (push access is verified at build time)
if command -v skopeo &>/dev/null; then
  skopeo inspect --no-tags docker://quay.io/openshift-hive/hive:latest &>/dev/null && \
    echo "OK: Bot can read quay.io/openshift-hive/hive (push access verified at build time)" || \
    echo "WARN: Cannot read quay.io/openshift-hive/hive — verify bot credentials"
else
  echo "INFO: skopeo not installed, skipping read-access check (credentials verified at build time)"
fi
```

#### Step 1.5 — Check forks exist

```bash
gh api repos/${GH_USER}/community-operators-prod --jq '.full_name' 2>/dev/null && \
  echo "OK: OpenShift Operators fork exists" || \
  echo "MISSING: Fork of redhat-openshift-ecosystem/community-operators-prod"

gh api repos/${GH_USER}/community-operators --jq '.full_name' 2>/dev/null && \
  echo "OK: K8s Operators fork exists" || \
  echo "MISSING: Fork of k8s-operatorhub/community-operators"
```

> **MANUAL STEP** if forks are missing: The user must fork these repos via the GitHub UI or:
> ```bash
> gh repo fork redhat-openshift-ecosystem/community-operators-prod --clone=false
> gh repo fork k8s-operatorhub/community-operators --clone=false
> ```

#### Step 1.6 — Check hive repo clone

Ask the user for the path to their local hive clone and store it as `HIVE_REPO`:

```bash
read -rp "Path to local hive repo clone: " HIVE_REPO
HIVE_REPO="${HIVE_REPO:-$HOME/go/src/github.com/openshift/hive}"

if [ -d "$HIVE_REPO" ] && [ -f "$HIVE_REPO/hack/bundle-gen.sh" ]; then
  echo "OK: Hive repo found at $HIVE_REPO"
else
  echo "MISSING: Hive repo clone with hack/bundle-gen.sh at $HIVE_REPO"
  echo "Clone it with: gh repo clone openshift/hive \"$HIVE_REPO\""
fi
```

#### Step 1.7 — Check CI registry credentials

> **MANUAL STEP**: The user must verify they have logged into the CI registry per [OpenShift CI docs](https://docs.ci.openshift.org/docs/how-tos/use-registries-in-build-farm/#how-do-i-log-in-to-pull-images-that-require-authentication). This is required for pulling base images during the operator image build.

Ask the user to confirm: "Have you logged into the OpenShift CI registry (`registry.ci.openshift.org`)?"

#### Step 1.8 — Report prerequisite summary

Present a table summarizing all checks:

| Prerequisite | Status | Action Required |
|---|---|---|
| `gh` CLI | OK / MISSING | Install and `gh auth login` |
| `yq` v4 | OK / MISSING | Install yq v4 |
| Container tool | OK / MISSING | Install docker, podman, or buildah |
| `GITHUB_TOKEN` / `GH_TOKEN` | OK / MISSING | **Manual**: Create token or `gh auth login` |
| GitHub username | OK / MISMATCH | Use `--github-user` |
| `QUAY_BOT_TOKEN` | OK / MISSING | **Manual**: Retrieve from secrets manager |
| Quay.io bot login | OK / FAIL | Re-run step 1.4b |
| OpenShift fork | OK / MISSING | Fork or `gh repo fork` |
| K8s fork | OK / MISSING | Fork or `gh repo fork` |
| Hive clone | OK / MISSING | `gh repo clone openshift/hive` |
| CI registry | **Manual check** | **Manual**: Login per CI docs |

If any checks failed, stop here and tell the user what needs to be fixed before proceeding.

---

### Phase 2: Identify the Target Commit

#### Step 2.1 — Determine the commit to publish

If the user provided a commit SHA via `$1`, use that. Otherwise, identify `HEAD` of `master`:

```bash
cd "$HIVE_REPO"
REMOTE=$(git remote -v | grep 'openshift/hive.*fetch' | awk '{print $1}' | head -1)
REMOTE="${REMOTE:-origin}"
git fetch "$REMOTE" master
git log --oneline -1 "$REMOTE/master"
```

Present the commit to the user and ask for confirmation: "Publish commit `<sha>` (`<subject>`)?"

> **Important**: The commit must be on the `master` branch — `bundle-gen.sh` always uses the `1.2` version prefix regardless of the local branch. A full checkout of `master` is not required; the script produces the same output from any local branch. If the user has pushed to prod and unfroze before publishing but more commits have since merged to `master`, they should specify the SHA of the prod commit via `--commit`.

#### Step 2.2 — Verify scripts are current

Ensure `hack/bundle-gen.sh` and `hack/version2.sh` are up to date with `master`:

```bash
cd "$HIVE_REPO"
git diff "$REMOTE/master" -- hack/bundle-gen.sh hack/version2.sh
```

If there are differences, check for uncommitted local changes first and confirm with the user before overwriting:

```bash
if ! git diff --quiet -- hack/bundle-gen.sh hack/version2.sh; then
  echo "WARNING: You have local changes to these scripts."
  echo "Review them before overwriting:"
  git diff -- hack/bundle-gen.sh hack/version2.sh
  read -rp "Overwrite local changes with $REMOTE/master versions? [y/N] " CONFIRM
  [ "$CONFIRM" = "y" ] || exit 1
fi
git checkout "$REMOTE/master" -- hack/bundle-gen.sh hack/version2.sh
```

#### Step 2.3 — Preview the version name

Run a dry-run first to verify the generated version and channel look correct:

```bash
cd "$HIVE_REPO"
GITHUB_TOKEN="$GITHUB_TOKEN" ./hack/bundle-gen.sh --dry-run --commit "$COMMIT_SHA"
```

Present the version name and channels to the user for confirmation before proceeding.

Run `./hack/bundle-gen.sh --help` for the full list of available flags.

---

### Phase 3: Build and Publish

#### Step 3.1 — Run bundle-gen.sh

Construct and execute the command:

```bash
cd "$HIVE_REPO"
GITHUB_TOKEN="$GITHUB_TOKEN" ./hack/bundle-gen.sh \
  --github-user "$GH_USER" \
  --commit "$COMMIT_SHA" \
  ${DRY_RUN:+--dry-run} \
  ${HOLD:+--hold}
```

Initialize `DRY_RUN` and `HOLD` from the skill's `--dry-run` and `--hold` arguments respectively before running this command.

This will:
1. Clone the hive repo and both OperatorHub repos to temp directories
2. Calculate a version name based on the branch and commit (format: `1.2.<commitcount>-<shaprefix7>`)
3. Build and push the operator image to [quay.io/openshift-hive/hive](https://quay.io/repository/openshift-hive/hive?tab=tags)
4. Generate OLM bundle manifests
5. Create commits with the bundle in both OperatorHub clones
6. Create PRs for both commits

#### Step 3.2 — Capture PR URLs

Extract the two PR URLs from the script output. Present them to the user:

```text
Created PRs:
- OpenShift OperatorHub: https://github.com/redhat-openshift-ecosystem/community-operators-prod/pull/XXXX
- K8s OperatorHub: https://github.com/k8s-operatorhub/community-operators/pull/XXXX
```

---

### Phase 4: Verify PRs

#### Step 4.1 — Inspect PR contents

For each PR, fetch and display a summary:

```bash
gh pr view <PR_NUMBER> --repo redhat-openshift-ecosystem/community-operators-prod
gh pr view <PR_NUMBER> --repo k8s-operatorhub/community-operators
```

Check that:
- The bundle directory name matches the expected version
- The CSV filename matches the version
- The `replaces` field in the CSV points to the previous version
- For the OpenShift PR: `release-config.yaml` is present with correct channel (`alpha` for master) and `replaces` value

#### Step 4.2 — Report PR status

Present a summary of both PRs and what to watch for.

---

### Phase 5: Post-Merge Monitoring

> **MANUAL STEP**: The user must monitor both PRs through to merge. After merge, the following must be verified.

#### Step 5.1 — Monitor OpenShift OperatorHub PR pipeline

After the OpenShift PR merges, `rh-operator-bundle-bot` runs the `operator-release-pipeline` job:
- **Success**: The label `operator-release-pipeline/passed` is applied.
- **Failure**: The label `operator-release-pipeline/failed` is applied, and a "Pipeline Summary" comment provides the failing task, log link, and restart option.

Check pipeline status:
```bash
gh pr view <PR_NUMBER> --repo redhat-openshift-ecosystem/community-operators-prod --json labels --jq '.labels[].name' | grep -i pipeline
```

If the pipeline failed, check the PR comments for the "Pipeline Summary":
```bash
gh api repos/redhat-openshift-ecosystem/community-operators-prod/issues/<PR_NUMBER>/comments --jq '.[].body' | grep -A 20 "Pipeline Summary"
```

To diagnose failures: scroll to the bottom of the pipeline logs and locate the failing task. See [this example of a failed pipeline run](https://github.com/redhat-openshift-ecosystem/community-operators-prod/pull/6616#issuecomment-2956287126) for reference.

#### Step 5.2 — Monitor K8s OperatorHub PR

The K8s OperatorHub PR typically merges via automated CI checks. Monitor for merge:
```bash
gh pr view <PR_NUMBER> --repo k8s-operatorhub/community-operators --json state --jq '.state'
```

#### Step 5.3 — Escalation

If bundles look correct but PRs are not merging, contact [#forum-community-operators](https://redhat.enterprise.slack.com/archives/C01UYB5E414) on Slack.

---

## Manual Steps Summary

The following steps require human intervention and cannot be fully automated:

| Step | What | Why |
|---|---|---|
| 1.2 | Create/renew GitHub token | Requires browser-based auth and permission selection |
| 1.4 | Set `QUAY_BOT_TOKEN` from team secrets manager | Bot token cannot be retrieved programmatically |
| 1.7 | Login to OpenShift CI registry | Requires interactive SSO authentication |
| 5.1 | Monitor OpenShift pipeline post-merge | Pipeline is triggered by external bot; failures need human triage |
| 5.2 | Monitor K8s PR merge | Merge depends on external CI; may need manual intervention |
| 5.3 | Escalate to Slack if stuck | Requires human communication with the community operators team |

## Error Handling

- **`bundle-gen.sh` fails during image push**: Verify `QUAY_BOT_TOKEN` is correct. Re-authenticate: `echo "$QUAY_BOT_TOKEN" | podman login -u="openshift-hive+hive_bot" --password-stdin quay.io`.
- **`bundle-gen.sh` fails during PR creation**: Verify `GITHUB_TOKEN` has correct permissions and forks exist. Check `--github-user` matches your GitHub username.
- **Pipeline fails post-merge**: Check the "Pipeline Summary" comment on the PR. Common issues include image SHA mismatches or catalog template conflicts. See the [manual catalog update procedure](https://github.com/openshift/hive-sops/blob/master/sop/OperatorHubWorkFlow.md#manually-updating-the-catalogs) if `release-config.yaml` was not included or failed.
- **Version conflict**: If the `replaces` field points to a version that doesn't exist in the catalog, the bundle will fail validation. Verify the previous version exists in the OperatorHub repo.

## References

- [Hive SOP: Push to OperatorHub](https://github.com/openshift/hive-sops/blob/master/sop/PushToOperatorHub.md)
- [Hive SOP: OperatorHub Workflow](https://github.com/openshift/hive-sops/blob/master/sop/OperatorHubWorkFlow.md)
- [Hive SOP: Branches and Versions](https://github.com/openshift/hive-sops/blob/master/sop/BranchesAndVersions.md)
- [Hive bundle-gen.sh](https://github.com/openshift/hive/blob/master/hack/bundle-gen.sh)
- [OpenShift Operators repo](https://github.com/redhat-openshift-ecosystem/community-operators-prod)
- [K8s Operators repo](https://github.com/k8s-operatorhub/community-operators)
- [Red Hat Operator Pipelines docs](https://redhat-openshift-ecosystem.github.io/operator-pipelines/)
