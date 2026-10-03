---
description: Install, inspect, or tear down a fully disconnected OpenShift cluster on GCP for node-layer testing
argument-hint: "<ocp-version> [cluster-name] | --destroy [cluster-name] | --bastion-internet <on|off|status>"
---

## Name
node-team:disconnected-install

## Synopsis
```text
/node-team:disconnected-install <ocp-version> [cluster-name]
/node-team:disconnected-install --destroy [cluster-name]
/node-team:disconnected-install --bastion-internet <on|off|status> [cluster-name]
```

## Description

Builds (or tears down) a fully disconnected OpenShift cluster on GCP,
end to end, from a completely clean project: VPC + subnets + firewall
rules, a bastion host, a Quay mirror-registry on that bastion, mirrors the
requested OCP release into it, and runs `openshift-install` — with zero
internet egress anywhere in the environment once it finishes (success,
failure, or interruption).

This is useful for node-layer testing that specifically requires a
disconnected/air-gapped environment — e.g. validating CRI-O/podman image
pull behavior, mirror-registry interactions, or MachineConfig rollout when
nodes cannot reach the public internet. Every stage is idempotent: re-run
freely, it skips whatever already exists.

Everything here wraps three existing, hand-tested shell scripts bundled at
[scripts/disconnected-ocp/](../skills/node/references/scripts/disconnected-ocp/)
rather than reimplementing this logic inline — see that directory's
[PREREQUISITES.md](../skills/node/references/scripts/disconnected-ocp/PREREQUISITES.md)
for full setup details before your first run.

## Implementation

### 0. Locate the bundled scripts

Resolve relative to this plugin's own install location first — reliable
regardless of where/how the plugin was installed — and only fall back to a
broad `find` if that path is somehow missing:
```bash
SCRIPTS_DIR="${CLAUDE_PLUGIN_ROOT}/skills/node/references/scripts/disconnected-ocp"
if [ ! -f "${SCRIPTS_DIR}/install-disconnected-ocp.sh" ]; then
  SCRIPTS_DIR="$(find ~/.claude ~/.config -type d -path '*node-team/skills/node/references/scripts/disconnected-ocp' 2>/dev/null | head -1)"
fi
ls "${SCRIPTS_DIR}/install-disconnected-ocp.sh" || echo "Bundled scripts not found — check plugin installation"
```

### 1. Parse arguments and dispatch

- **No flags, just `<ocp-version> [cluster-name]`**: run the install path
  (step 2).
- **`--destroy [cluster-name]`**: run the teardown path (step 3).
- **`--bastion-internet <on|off|status>`**: run the bastion-internet toggle
  (step 4).

If `<ocp-version>` is missing for the install path, stop and show the
Synopsis instead of guessing.

### 2. Install path

First-time run on a machine: the script's own interactive wizard will ask
for 4 credential paths (pull secret, GCP service account key, SSH public
key, and a manually-downloaded `mirror-registry.tar.gz` — see
PREREQUISITES.md for why that one can't be automated) and save them to
`config.env` next to the script so it never asks again. Before running,
remind the user of this if it looks like a first-time run (no `config.env`
present next to the script).

Note: whether `<ocp-version>` is a stable/GA tag (e.g. `4.18.0`) or a
nightly tag (e.g. `5.1` or a full `5.1.0-0.nightly-...` string) changes
which pull-secret entries are required — see the "Pull secret — depends on
stable vs. nightly" section of PREREQUISITES.md.

#### 2a. Pre-flight checks (before the ~1-1.5h run starts)

If `config.env` already exists next to the script, source the values it
would use (`PROJECT`, `REGION`, `CLUSTER_NAME` if a custom one wasn't
passed, and `PULL_SECRET_PATH`) to check for problems that the underlying
script would otherwise only discover 30-45 minutes in, after mirroring is
already well underway:

- **Nightly CI-registry credential check**: if `<ocp-version>` looks like a
  nightly tag, verify the pull secret at `PULL_SECRET_PATH` already has a
  `registry.ci.openshift.org` entry:
  ```bash
  python3 -c "import json,sys; d=json.load(open(sys.argv[1])); sys.exit(0 if 'registry.ci.openshift.org' in d.get('auths',{}) else 1)" "${PULL_SECRET_PATH}"
  ```
  If missing, stop and tell the user now (with a link to the "Pull secret
  — depends on stable vs. nightly" section of PREREQUISITES.md) instead of
  letting the run fail deep into Stage 4/5.
- **Confirm the billable target before proceeding**: this creates real,
  billed GCP resources (VPC, bastion VM, mirror-registry storage, and a
  full OCP cluster's worth of compute) for up to ~1.5 hours. Show the user
  the resolved `PROJECT`, `REGION`, and `CLUSTER_NAME` (from `config.env`
  if present, otherwise the script's defaults: `openshift-qe`,
  `us-central1`, `$(whoami)-dc`) and get explicit confirmation before
  running the script, especially if `PROJECT` isn't one the user has
  mentioned in this conversation.

```bash
cd "${SCRIPTS_DIR}"
./install-disconnected-ocp.sh <ocp-version> [cluster-name]
```

This runs unattended through 6 stages (network, bastion, mirror registry,
mirror release, install-config generation, cluster creation) and can take
roughly 1-1.5 hours end to end on a clean project (mirroring is the
long pole, 30-60 min; bootstrap is another ~30 min). Stream its output to
the user rather than waiting silently — each stage prints clear progress.

On success, print the final `oc get nodes` / `oc get clusterversion` output
already shown by the script, plus:
```text
SSH to the bastion to interact with the cluster:
  gcloud compute ssh <cluster-name>-bastion --zone=<zone> --project=<project> --tunnel-through-iap
  export KUBECONFIG=~/cluster/auth/kubeconfig
```

#### 2b. If it fails: diagnose before just reporting the error

The script's own stderr/stdout already surfaces which stage failed, but
before relaying that to the user, pull the actual remote log for that
stage from the bastion (if it got far enough to exist) and look for the
real root cause rather than just forwarding a generic "command failed":

```bash
gcloud compute ssh <cluster-name>-bastion --zone=<zone> --project=<project> --tunnel-through-iap \
  --command="tail -80 ~/install.log ~/mirror-release.log ~/mirror-install.log 2>/dev/null"
```

Grep the output for common, recognizable failure signatures before
presenting a diagnosis — e.g. `x509`/`certificate` (CA trust issue, see
Stage 3's CA-install step), `unauthorized`/`401` (pull-secret or
`registry.ci.openshift.org` credential issue), `context deadline
exceeded`/`i/o timeout` (a stale/still-active Cloud NAT restriction, or a
transient IAP tunnel drop — safe to just retry), or `no space left on
device` (bastion disk full from mirrored image layers). Summarize the
likely cause and the concrete next step (e.g. "re-run the same command —
this stage is idempotent" vs. "fix the pull secret and re-run") rather
than just pasting the raw log back at the user.

### 3. Destroy path

```bash
cd "${SCRIPTS_DIR}"
./clean-environment.sh [cluster-name]
```

This is destructive and irreversible (full teardown: cluster, bastion,
NAT/router, firewall rules, subnets, VPC, and the local `config.env`). The
script itself prompts for typed confirmation of the cluster name before
deleting anything — do not bypass or auto-answer that prompt. Let the user
type it themselves, or explicitly confirm with the user first if this
command is being run non-interactively.

### 4. Bastion-internet toggle

For one-off tasks that need the bastion to temporarily reach the public
internet again after a cluster is already installed (e.g. pulling a new
test image to mirror in) — nothing else in the environment ever gets
internet access via this, only the bastion, and only until you turn it
back off:

```bash
cd "${SCRIPTS_DIR}"
./bastion-internet.sh <on|off|status> [cluster-name]
```

`[cluster-name]` is only needed if the cluster was installed with a custom
name — it is **not** persisted to `config.env` by the install script, so it
must be repeated here to target the right bastion/VPC. Omitting it targets
the default `$(whoami)-dc` cluster.

Remind the user to run `off` again once they're done, even though
`install-disconnected-ocp.sh` itself always tears this down automatically
on its own exit path — this toggle is a separate, manual on/off switch for
ad-hoc use between installer runs.

## Return Value

- Install path: cluster access instructions (bastion SSH command +
  `KUBECONFIG` path) on success, or the failing stage's error output
- Destroy path: confirmation that all resources were removed
- Bastion-internet path: current NAT/internet status for the bastion

## Examples

1. **Install a stable GA release**:
   ```text
   /node-team:disconnected-install 4.18.0
   ```

2. **Install a nightly build with a custom cluster name**:
   ```text
   /node-team:disconnected-install 5.1.0-0.nightly-2026-09-13-222843 my-test-cluster
   ```

3. **Tear everything down**:
   ```text
   /node-team:disconnected-install --destroy my-test-cluster
   ```

4. **Temporarily give the bastion internet to pull a new test image**:
   ```text
   /node-team:disconnected-install --bastion-internet on
   # ... podman pull / tag / push on the bastion ...
   /node-team:disconnected-install --bastion-internet off
   ```

## Arguments

- `<ocp-version>`: Required for the install path. A stable GA version
  (`4.18.0`), a minor version to auto-resolve the latest accepted nightly
  (`5.1`), or a full nightly pullspec tag (`5.1.0-0.nightly-YYYY-MM-DD-HHMMSS`).
- `[cluster-name]`: Optional for install/destroy. Defaults to
  `$(whoami)-dc` so teammates sharing a GCP project don't collide.
- `--destroy [cluster-name]`: Tear down everything for that cluster name.
- `--bastion-internet <on|off|status> [cluster-name]`: Toggle or check the
  bastion's temporary internet access independent of a full install/destroy
  run. Pass `[cluster-name]` if the cluster wasn't installed with the
  default `$(whoami)-dc` name.

## Notes

- Requires `gcloud` CLI authenticated locally, plus IAM permissions
  covering Compute Engine, Cloud DNS, IAM service accounts, Cloud Storage,
  and `roles/iap.tunnelResourceAccessor` — see PREREQUISITES.md.
- The environment always ends up with zero internet egress anywhere at
  rest — the bastion only ever gets temporary internet during setup/mirror
  stages (via a scoped, ephemeral Cloud NAT), never the cluster nodes.
- One deliberate exception: subnets have Private Google Access enabled,
  required because `openshift-install` on GCP stages the bootstrap node's
  ignition config in a GCS bucket. This is a narrow allowlist for
  `*.googleapis.com` only — not general internet access, and nodes still
  cannot reach quay.io, registry.redhat.io, or any other destination.
