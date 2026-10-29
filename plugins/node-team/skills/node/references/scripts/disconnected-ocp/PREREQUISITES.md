# Prerequisites — `install-disconnected-ocp.sh`

Before running this script for the first time, make sure you have the following.
The script's interactive wizard will ask for the 4 file paths below once and
save them to `config.env` — you won't be asked again after that.

---

## 1. Local machine (wherever you run the script from)

- **`gcloud` CLI**, installed and authenticated:
  ```bash
  gcloud auth login
  gcloud config set project openshift-qe   # or your target project
  ```
- **`python3`** (used to safely embed the pull-secret JSON into `install-config.yaml`)
- **`bash`** (macOS's default `/bin/bash` is fine)
- **`ssh-keygen`**, if you don't already have an SSH keypair

## 2. GCP IAM permissions

You need enough IAM on the target project to create/delete:
- Compute Engine resources (VPC, subnets, firewall rules, instances, routers, Cloud NAT)
- Cloud DNS managed zones / record-sets
- IAM service accounts (openshift-install creates several per cluster)
- Cloud Storage buckets (image registry bucket)
- `roles/iap.tunnelResourceAccessor` (to SSH into the bastion — no public IP is ever used)

On a shared team project this is usually already covered by whatever role your
GCP admin grants. For a brand-new project, see Red Hat's official
[minimum required GCP permissions for OpenShift](https://docs.redhat.com/en/documentation/openshift_container_platform/latest/html/installing_on_gcp/installing-gcp-account).

## 3. Four credential files

| # | What | Where to get it |
|---|---|---|
| 1 | GCP service account JSON key | A GCP SA with the IAM permissions above; download its key as JSON |
| 2 | SSH public key (`.pub` file) | Your own `~/.ssh/id_ed25519.pub` (`ssh-keygen -t ed25519` if you don't have one) |
| 3 | `mirror-registry.tar.gz` | https://console.redhat.com/openshift/downloads → search "mirror registry" (gated behind login, ~1.3GB — **must be downloaded manually**, the script cannot fetch it for you) |
| 4 | Pull secret | See section 4 below — **the exact contents depend on which OCP version you're installing** |

## 4. Pull secret — depends on stable vs. nightly

This is the one prerequisite that differs depending on what you're installing.
`OCP_VERSION` (the argument you pass to the script) determines the source
registry `oc adm release mirror` pulls from:

| You're installing | Source registry | Pull secret needed |
|---|---|---|
| **Stable/GA**, e.g. `./install-disconnected-ocp.sh 4.18.0` | `quay.io/openshift-release-dev/ocp-release` | The plain pull secret from console.redhat.com — nothing extra |
| **Nightly**, e.g. `./install-disconnected-ocp.sh 5.1` or a full tag like `5.1.0-0.nightly-2026-09-13-222843` | `registry.ci.openshift.org/ocp/release` | The plain pull secret **PLUS** a `registry.ci.openshift.org` auth entry merged in |

### Stable/GA builds — just this:
1. Go to https://console.redhat.com/openshift/install/pull-secret
2. Log in, click **Download pull secret** (or copy it directly)
3. Save it locally, e.g. `~/.openshift/pull-secret.json`
4. Point the wizard at that file when asked

### Nightly builds — extra step required:
The plain console.redhat.com pull secret does **not** include credentials for
`registry.ci.openshift.org` (that's Red Hat's internal CI registry, not a
public one — this only works for Red Hat associates/QE with CI cluster
access, not external customers). Without this, Stage 4 (mirroring) will fail
with a 401/403 pulling the source release image.

1. Log into the internal CI cluster (check with your team for the current
   cluster URL/SSO if you don't already have access), then run:
   ```bash
   oc registry login
   ```
   This fetches your CI registry token and merges a `registry.ci.openshift.org`
   entry into `~/.docker/config.json` automatically.
2. Merge that `registry.ci.openshift.org` auth entry into the same
   `pull-secret.json` file from the stable-build steps above (or ask a
   teammate who already has one working to share just that one auth block —
   it's per-user/per-token, so copying someone else's may or may not work
   depending on token scope/expiry; getting your own via `oc registry login`
   is the reliable path).
3. Point the wizard at this merged file.

> Tip: if you're not sure whether your pull secret already has this entry,
> check for a `"registry.ci.openshift.org"` key in the JSON before running
> the script — it'll save you a failed Stage 4 run.

## 5. GCP project-level setup (usually already true for a shared project)

- Compute Engine, Cloud DNS, IAM, and Cloud Resource Manager APIs enabled
- Sufficient quota for `n2-standard-8` × 6 nodes + `e2-standard-4` bastion in
  at least one of the zones the script tries (`us-central1-a/b/c/f` by
  default — configurable via `ZONES` in `config.env`)
- **No pre-existing DNS zone needed** for `BASE_DOMAIN` — since installs use
  `publish: Internal`, `openshift-install` creates its own private managed
  zone per cluster; nothing needs to be pre-provisioned.

## 6. What you do NOT need

- `install-config.yaml` — fully generated by the script on the bastion, every run
- `oc` / `openshift-install` installed locally — everything runs on the
  bastion over an IAP SSH tunnel
- Manual VPC/subnet/bastion/mirror-registry setup — idempotent, the script
  handles all of it
- Manual Cloud NAT management — ephemeral, created and torn down automatically
