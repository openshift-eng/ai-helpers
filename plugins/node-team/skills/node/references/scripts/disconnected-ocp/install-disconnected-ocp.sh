#!/usr/bin/env bash
#
# ============================================================================
# install-disconnected-ocp.sh
#
# Fully automated, repeatable installer for a DISCONNECTED OpenShift cluster
# on GCP. Creates the VPC/subnets/firewall/bastion (if not already present),
# stands up a Quay mirror-registry on the bastion, mirrors the requested OCP
# release into it, generates install-config.yaml, and runs
# `openshift-install create cluster` — with automatic retry across zones if
# GCP returns ZONE_RESOURCE_POOL_EXHAUSTED.
#
# Run this from your Mac / Cloud Shell (needs `gcloud` configured with a
# project that has compute + dns + IAM permissions). It drives GCP directly
# for infra, and SSHes into the bastion (via IAP tunnel) to do the
# mirror + install work.
#
# USAGE:
#   ./install-disconnected-ocp.sh <ocp-version> [cluster-name]
#
# <ocp-version> can be:
#   - A full CI nightly pullspec tag, e.g. 5.1.0-0.nightly-2026-09-13-222843
#   - A minor version to auto-resolve the latest accepted nightly, e.g. 5.1
#   - A stable GA version from quay.io, e.g. 4.18.0
#
# EXAMPLES:
#   ./install-disconnected-ocp.sh 5.1                # latest 5.1 nightly
#   ./install-disconnected-ocp.sh 4.18.0             # stable GA release
#   ./install-disconnected-ocp.sh 5.1.0-0.nightly-2026-09-13-222843
#
# ONE-TIME PREREQS (per teammate — every person has different file paths):
#   - PULL_SECRET_PATH             : your registry pull secret (cloud.redhat.com)
#   - GCP_SA_KEY_PATH              : GCP service account JSON key for openshift-install
#   - SSH_PUBLIC_KEY_PATH          : SSH public key installed into cluster nodes
#   - MIRROR_REGISTRY_TARBALL_PATH : mirror-registry.tar.gz — Red Hat gates this
#                                    behind a login, so download it yourself once
#                                    from console.redhat.com/openshift/downloads
#                                    (search "mirror registry"); the script can't
#                                    fetch it automatically.
#
# HOW THESE PATHS ARE RESOLVED (first run per teammate):
#   1. If ./config.env exists next to this script, it is sourced automatically.
#   2. Otherwise, this script runs a one-time interactive wizard that asks
#      YOU for the 4 paths above, validates the files exist, and writes them
#      to ./config.env so you (and only you, on your machine) never have to
#      type them again. config.env is per-machine/per-user — do NOT commit
#      it to git (see config.env.example for the template instead).
#   3. You can always skip the wizard by exporting the env vars yourself
#      before running the script, or by pre-creating config.env manually
#      from config.env.example.
#
# The script is IDEMPOTENT: re-running it will skip steps whose resources
# already exist (VPC, bastion, mirror-registry) and just do a fresh
# mirror + install for the version you pass.
#
# NETWORK / INTERNET LIFECYCLE (important):
#   The bastion is given internet access (via Cloud NAT, scoped to whatever
#   subnet the bastion's NIC is actually on — discovered at runtime, never
#   hardcoded) ONLY for the duration of this run, so it can install tooling
#   and mirror the requested release. That NAT is deleted again automatically
#   before the script exits — on success, on failure, or on Ctrl-C — so the
#   environment always ends up with ZERO internet egress anywhere, including
#   the bastion. Cluster nodes never get internet access at any point. If you
#   need to mirror a new version later, just run the script again — it will
#   recreate the temporary NAT, do the work, and remove it again.
#
#   One nuance for the "prove this is disconnected" conversation: all 3
#   subnets have Private Google Access enabled. This is NOT internet access
#   — it only lets VMs with no external IP/NAT reach *.googleapis.com over
#   Google's internal backbone. It's required because openshift-install on
#   GCP stages the bootstrap node's ignition config in a GCS bucket rather
#   than handing it over directly, so the bootstrap node must be able to
#   fetch it from storage.googleapis.com even with zero general internet
#   egress. Nodes still cannot reach quay.io, registry.redhat.io, or any
#   non-Google destination at any point.
# ============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="${SCRIPT_DIR}/config.env"

# Load any previously-saved per-user config (paths to secrets/keys, and
# optionally PROJECT/REGION overrides). Safe no-op if it doesn't exist yet.
if [ -f "${CONFIG_FILE}" ]; then
  # shellcheck disable=SC1090
  source "${CONFIG_FILE}"
fi

# ---------------------------------------------------------------------------
# CONFIG — override any of these via config.env (see above) or env vars
# ---------------------------------------------------------------------------
PROJECT="${PROJECT:-openshift-qe}"
REGION="${REGION:-us-central1}"
# Zones tried in order until one has capacity for the machine type.
ZONES=(${ZONES:-us-central1-a us-central1-b us-central1-c us-central1-f})
# Defaults to your local username so two teammates running this with no
# CLUSTER_NAME override never collide on the same shared project.
CLUSTER_NAME="${2:-${CLUSTER_NAME:-$(whoami)-dc}}"
BASE_DOMAIN="${BASE_DOMAIN:-qe.gcp.devcluster.openshift.com}"
MACHINE_TYPE="${MACHINE_TYPE:-n2-standard-8}"
MASTER_REPLICAS="${MASTER_REPLICAS:-3}"
WORKER_REPLICAS="${WORKER_REPLICAS:-3}"

VPC_NAME="${CLUSTER_NAME}-vpc"
BASTION_SUBNET="${CLUSTER_NAME}-bastion-subnet"
MASTER_SUBNET="${CLUSTER_NAME}-master-subnet"
WORKER_SUBNET="${CLUSTER_NAME}-worker-subnet"
BASTION_NAME="${CLUSTER_NAME}-bastion"
ROUTER_NAME="${CLUSTER_NAME}-router"
NAT_NAME="${CLUSTER_NAME}-nat"

BASTION_SUBNET_CIDR="${BASTION_SUBNET_CIDR:-10.20.0.0/24}"
MASTER_SUBNET_CIDR="${MASTER_SUBNET_CIDR:-10.10.0.0/20}"
WORKER_SUBNET_CIDR="${WORKER_SUBNET_CIDR:-10.10.16.0/20}"
CLUSTER_CIDR="${CLUSTER_CIDR:-10.128.0.0/14}"
SERVICE_CIDR="${SERVICE_CIDR:-172.30.0.0/16}"

# NOTE: no hardcoded fallback paths here on purpose — every teammate keeps
# these files in a different place. ensure_secrets_configured() (called from
# main) fills these in from config.env or an interactive wizard.
PULL_SECRET_PATH="${PULL_SECRET_PATH:-}"
GCP_SA_KEY_PATH="${GCP_SA_KEY_PATH:-}"
SSH_PUBLIC_KEY_PATH="${SSH_PUBLIC_KEY_PATH:-}"
# mirror-registry.tar.gz has NO static/public download URL — Red Hat gates
# it behind a login at console.redhat.com/openshift/downloads. So unlike a
# normal tool dependency, this script cannot fetch it itself; you download
# it once yourself and point the script at the local file (same pattern as
# the pull secret / SSH key / GCP SA key above).
MIRROR_REGISTRY_TARBALL_PATH="${MIRROR_REGISTRY_TARBALL_PATH:-}"

MIRROR_INIT_USER="${MIRROR_INIT_USER:-init}"
# NOTE: this random default is only ever generated ONCE — the very first
# run that creates the mirror-registry — because ensure_secrets_configured()
# below persists whatever value is in effect here into config.env, and it
# is then sourced back on every later run. Without that, a re-run would
# generate a DIFFERENT random password than the one the registry was
# actually installed with, breaking `podman login` in Stage 3. The
# mirror-registry is reachable only from inside the VPC (no internet-facing
# exposure), but a random value is just as easy as a guessable one.
MIRROR_INIT_PASSWORD="${MIRROR_INIT_PASSWORD:-$(openssl rand -base64 18)}"

OCP_VERSION="${1:?Usage: $0 <ocp-version e.g. 5.1 | 4.18.0 | full-nightly-tag> [cluster-name]}"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
log()  { echo -e "\033[1;34m[install-disconnected-ocp]\033[0m $*"; }
warn() { echo -e "\033[1;33m[WARN]\033[0m $*"; }
die()  { echo -e "\033[1;31m[ERROR]\033[0m $*" >&2; exit 1; }

# find_bastion_zone/find_router/find_nat/bastion_internet_on/off/status,
# shared with bastion-internet.sh and clean-environment.sh.
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/lib-bastion-net.sh"

ssh_bastion() {
  # IMPORTANT: only the remote command's own stdout is returned here. gcloud
  # itself prints noise (SSH host-key notices, the "install NumPy for IAP
  # tunnel performance" banner, etc.) on ITS OWN stderr — that must never be
  # merged into stdout, because several callers do `var=$(ssh_bastion ...)`
  # to capture clean data (JSON, PEM certs, hostnames) for further parsing.
  # Any real remote-command output written to stderr (rare; most of our
  # remote commands already redirect 2>&1 into their own tee'd log files)
  # still gets filtered-and-shown live so real errors remain visible.
  gcloud compute ssh "${BASTION_NAME}" --zone="${BASTION_ZONE}" --project="${PROJECT}" \
    --tunnel-through-iap --command="$1" \
    2> >(grep -Ev "^Existing host|^Warning: Permanently added|^WARNING:$|NumPy|increase the performance|using-tcp-forwarding|^$" >&2)
}

scp_to_bastion() {
  gcloud compute scp "$1" "${BASTION_NAME}:$2" \
    --zone="${BASTION_ZONE}" --project="${PROJECT}" --tunnel-through-iap 2>&1 \
    | grep -v "^Existing host\|^Warning: Permanently added"
}

resource_exists() { eval "$1" >/dev/null 2>&1; }

# ---------------------------------------------------------------------------
# Stage 0 — Ensure secrets/keys are configured (config.env or wizard)
# ---------------------------------------------------------------------------
prompt_for_path() {
  # $1=variable name, $2=human description, $3=example path
  # $4=optional validator function name — called as `validator "$input"`;
  # a non-zero return re-prompts (validator is responsible for its own
  # warn() message explaining why). Use this to catch "right file exists,
  # wrong file" mistakes (e.g. pasting the pull-secret path when asked for
  # the mirror-registry tarball) instead of only checking the path exists.
  local varname="$1" desc="$2" example="$3" validator="${4:-}" input
  while true; do
    read -r -e -p "  Path to ${desc} [e.g. ${example}]: " input
    input="${input/#\~/$HOME}"
    if [ ! -f "${input}" ]; then
      warn "  File not found: ${input}. Try again (or Ctrl+C to abort)."
      continue
    fi
    if [ -n "${validator}" ] && ! "${validator}" "${input}"; then
      continue
    fi
    printf -v "${varname}" '%s' "${input}"
    break
  done
}

is_valid_mirror_registry_tarball() {
  if ! file "$1" 2>/dev/null | grep -qi "gzip compressed"; then
    warn "  '$1' doesn't look like a gzip archive (mirror-registry.tar.gz must be)."
    warn "  Did you paste the wrong file by mistake? Try again (or Ctrl+C to abort)."
    return 1
  fi
  return 0
}

ensure_secrets_configured() {
  # Self-heal: persist MIRROR_INIT_PASSWORD for configs written before this
  # was tracked, so it survives into next year even without a fresh wizard
  # run. Cheap no-op once it's already there.
  if [ -f "${CONFIG_FILE}" ] && ! grep -q '^MIRROR_INIT_PASSWORD=' "${CONFIG_FILE}"; then
    echo "MIRROR_INIT_PASSWORD=\"${MIRROR_INIT_PASSWORD}\"" >> "${CONFIG_FILE}"
  fi

  local need_wizard=0
  [ -n "${PULL_SECRET_PATH}" ] && [ -f "${PULL_SECRET_PATH}" ] || need_wizard=1
  [ -n "${GCP_SA_KEY_PATH}" ] && [ -f "${GCP_SA_KEY_PATH}" ] || need_wizard=1
  [ -n "${SSH_PUBLIC_KEY_PATH}" ] && [ -f "${SSH_PUBLIC_KEY_PATH}" ] || need_wizard=1
  [ -n "${MIRROR_REGISTRY_TARBALL_PATH}" ] && [ -f "${MIRROR_REGISTRY_TARBALL_PATH}" ] || need_wizard=1

  [ "${need_wizard}" = "0" ] && return 0

  if [ ! -t 0 ]; then
    die "Missing/invalid secret paths and not running interactively.
Set these env vars (or create ${CONFIG_FILE} from config.env.example) and re-run:
  PULL_SECRET_PATH, GCP_SA_KEY_PATH, SSH_PUBLIC_KEY_PATH, MIRROR_REGISTRY_TARBALL_PATH"
  fi

  log "First-time setup for this machine — let's locate your credentials once."
  log "(Saved afterwards to ${CONFIG_FILE} so you won't be asked again.)"

  if [ -z "${PULL_SECRET_PATH}" ] || [ ! -f "${PULL_SECRET_PATH}" ]; then
    prompt_for_path PULL_SECRET_PATH "OpenShift pull secret (from console.redhat.com/openshift/install/pull-secret)" "\$HOME/.openshift/pull-secret.json"
  fi
  if [ -z "${GCP_SA_KEY_PATH}" ] || [ ! -f "${GCP_SA_KEY_PATH}" ]; then
    prompt_for_path GCP_SA_KEY_PATH "GCP service account JSON key" "\$HOME/.gcp/osServiceAccount.json"
  fi
  if [ -z "${SSH_PUBLIC_KEY_PATH}" ] || [ ! -f "${SSH_PUBLIC_KEY_PATH}" ]; then
    prompt_for_path SSH_PUBLIC_KEY_PATH "SSH PUBLIC key for cluster node access" "\$HOME/.ssh/id_ed25519.pub"
  fi
  if [ -z "${MIRROR_REGISTRY_TARBALL_PATH}" ] || [ ! -f "${MIRROR_REGISTRY_TARBALL_PATH}" ]; then
    warn "mirror-registry.tar.gz has no public download URL — Red Hat requires you"
    warn "to log in and download it yourself from:"
    warn "  https://console.redhat.com/openshift/downloads (search 'mirror registry')"
    prompt_for_path MIRROR_REGISTRY_TARBALL_PATH "downloaded mirror-registry.tar.gz" "\$HOME/Downloads/mirror-registry.tar.gz" is_valid_mirror_registry_tarball
  fi

  cat > "${CONFIG_FILE}" <<EOF
# Auto-generated by install-disconnected-ocp.sh on $(date).
# Per-user, per-machine — DO NOT commit this file to git.
PULL_SECRET_PATH="${PULL_SECRET_PATH}"
GCP_SA_KEY_PATH="${GCP_SA_KEY_PATH}"
SSH_PUBLIC_KEY_PATH="${SSH_PUBLIC_KEY_PATH}"
MIRROR_REGISTRY_TARBALL_PATH="${MIRROR_REGISTRY_TARBALL_PATH}"
# Frozen at first-install time so re-runs in a later calendar year still
# match the password the mirror-registry was actually installed with.
MIRROR_INIT_PASSWORD="${MIRROR_INIT_PASSWORD}"
EOF
  log "Saved to ${CONFIG_FILE}. Edit that file directly if any path ever changes."
}

# ---------------------------------------------------------------------------
# Stage 1 — Network (VPC, subnets, firewall) — idempotent
# ---------------------------------------------------------------------------
stage_network() {
  log "Stage 1/6: Network"

  if resource_exists "gcloud compute networks describe ${VPC_NAME} --project=${PROJECT}"; then
    log "  VPC ${VPC_NAME} already exists, skipping."
  else
    log "  Creating VPC ${VPC_NAME}..."
    gcloud compute networks create "${VPC_NAME}" \
      --project="${PROJECT}" --subnet-mode=custom
  fi

  create_subnet() {
    local name="$1" cidr="$2"
    if resource_exists "gcloud compute networks subnets describe ${name} --region=${REGION} --project=${PROJECT}"; then
      log "  Subnet ${name} already exists, skipping."
    else
      # --enable-private-ip-google-access is REQUIRED, not optional, even
      # though there's no internet access anywhere in this environment.
      # openshift-install on GCP uploads the (large) bootstrap.ign to a GCS
      # bucket and gives the bootstrap node only a small pointer ignition
      # config that fetches it from storage.googleapis.com over HTTPS. That
      # is a Google Cloud API call, not general internet access — Private
      # Google Access lets VMs with no external IP and no NAT reach
      # *.googleapis.com over Google's internal backbone ONLY. It grants
      # nothing else: nodes still cannot reach quay.io, registry.redhat.io,
      # or any other internet destination. Without this, the bootstrap node
      # never finishes ignition and the install hangs for 20+ min before
      # timing out with a misleading "Kubernetes API timeout" error.
      log "  Creating subnet ${name} (${cidr}, Private Google Access enabled)..."
      gcloud compute networks subnets create "${name}" \
        --project="${PROJECT}" --network="${VPC_NAME}" --region="${REGION}" \
        --range="${cidr}" --enable-private-ip-google-access
    fi
  }
  create_subnet "${BASTION_SUBNET}" "${BASTION_SUBNET_CIDR}"
  create_subnet "${MASTER_SUBNET}" "${MASTER_SUBNET_CIDR}"
  create_subnet "${WORKER_SUBNET}" "${WORKER_SUBNET_CIDR}"

  # Self-heal subnets created by an older version of this script (before
  # Private Google Access was added above) — unconditional + idempotent, so
  # this is a no-op once it's already enabled.
  for subnet in "${BASTION_SUBNET}" "${MASTER_SUBNET}" "${WORKER_SUBNET}"; do
    gcloud compute networks subnets update "${subnet}" \
      --project="${PROJECT}" --region="${REGION}" \
      --enable-private-ip-google-access >/dev/null 2>&1 || true
  done

  # Allow all internal traffic within the VPC (masters <-> workers <-> bastion)
  if ! resource_exists "gcloud compute firewall-rules describe ${CLUSTER_NAME}-allow-internal --project=${PROJECT}"; then
    log "  Creating internal firewall rule..."
    gcloud compute firewall-rules create "${CLUSTER_NAME}-allow-internal" \
      --project="${PROJECT}" --network="${VPC_NAME}" --direction=INGRESS \
      --action=ALLOW --rules=all \
      --source-ranges="${BASTION_SUBNET_CIDR},${MASTER_SUBNET_CIDR},${WORKER_SUBNET_CIDR}"
  fi

  # Allow IAP range to SSH into the bastion only (nodes stay unreachable from
  # outside the VPC — this is what keeps the cluster disconnected).
  if ! resource_exists "gcloud compute firewall-rules describe ${CLUSTER_NAME}-allow-iap-ssh --project=${PROJECT}"; then
    log "  Creating IAP SSH firewall rule (bastion only)..."
    gcloud compute firewall-rules create "${CLUSTER_NAME}-allow-iap-ssh" \
      --project="${PROJECT}" --network="${VPC_NAME}" --direction=INGRESS \
      --action=ALLOW --rules=tcp:22 \
      --source-ranges=35.235.240.0/20 \
      --target-tags="${CLUSTER_NAME}-bastion"
  fi

  # NOTE: no Router/NAT created here anymore. Internet access is granted
  # ONLY transiently (see ensure_bastion_internet, called after the bastion
  # VM exists) and torn down completely (see teardown_bastion_internet,
  # registered as an EXIT trap in main) once mirroring is done — regardless
  # of success or failure. Nothing in this environment keeps internet
  # access at rest, including the bastion itself.
}

# ---------------------------------------------------------------------------
# Stage 2 — Bastion VM — idempotent (create only; provisioning is separate,
# see stage_bastion_provision, which runs AFTER ensure_bastion_internet so
# package installs/downloads on the bastion actually have connectivity).
# ---------------------------------------------------------------------------
BASTION_ZONE=""
stage_bastion_create() {
  log "Stage 2/6: Bastion (create VM if needed)"

  # Project-wide, VPC-anchored lookup (not just ZONES[0]) — if someone
  # reorders ZONES in config.env after a bastion was already created in a
  # different zone, checking only ZONES[0] here would miss it and create a
  # SECOND bastion, which then makes find_bastion_zone (used by
  # bastion-internet.sh and clean-environment.sh) die with "Multiple
  # instances found" the next time either of them runs.
  BASTION_ZONE="$(find_bastion_zone)" || die "Could not determine the bastion zone."

  if [ -n "${BASTION_ZONE}" ]; then
    log "  Bastion already exists in ${BASTION_ZONE}, skipping creation."
  else
    BASTION_ZONE="${ZONES[0]}"
    log "  Creating bastion VM in ${BASTION_ZONE}..."
    # NOTE: deliberately no --service-account/--scopes here. Attaching a
    # service account to a VM requires the *caller* to hold
    # iam.serviceAccountUser on that SA — an extra permission teammates may
    # not have, and using a human user account (e.g. via `gcloud config
    # get-value account`) is rejected outright by GCP (only real IAM service
    # accounts can be attached to an instance). It's also unnecessary: every
    # tool we run on the bastion (openshift-install, oc adm release mirror)
    # is handed credentials explicitly via the osServiceAccount.json /
    # pull-secret.json files we scp over — none of them rely on instance
    # metadata credentials. Omitting these flags makes the VM use no
    # attached service account at all, which is the safest default.
    gcloud compute instances create "${BASTION_NAME}" \
      --project="${PROJECT}" --zone="${BASTION_ZONE}" \
      --machine-type=e2-standard-4 \
      --network="${VPC_NAME}" --subnet="${BASTION_SUBNET}" \
      --no-address \
      --tags="${CLUSTER_NAME}-bastion" \
      --image-family=rhel-9 --image-project=rhel-cloud \
      --boot-disk-size=200GB \
      --no-service-account --no-scopes

    log "  Waiting for SSH to come up..."
    local ssh_ready=false
    for i in $(seq 1 20); do
      if ssh_bastion "echo ready" | grep -q ready; then
        ssh_ready=true
        break
      fi
      sleep 10
    done
    if [ "${ssh_ready}" != "true" ]; then
      die "Bastion ${BASTION_NAME} did not become SSH-reachable after $((20 * 10))s. Check the VM's serial console/boot status in the GCP console before retrying."
    fi
  fi
}

stage_bastion_provision() {
  log "  Installing base tooling on bastion (podman, oc, openshift-install deps)..."
  ssh_bastion "
    sudo dnf install -y podman jq python3 tar 2>&1 | tail -5
    mkdir -p ~/cluster-tools ~/.gcp ~/.ssh
  "

  scp_to_bastion "${GCP_SA_KEY_PATH}" "~/.gcp/osServiceAccount.json"
  scp_to_bastion "${PULL_SECRET_PATH}" "~/pull-secret.json"
  scp_to_bastion "${SSH_PUBLIC_KEY_PATH}" "~/.ssh/cluster_key.pub"

  # oc client
  ssh_bastion '
    if ! command -v oc >/dev/null 2>&1; then
      curl -sL https://mirror.openshift.com/pub/openshift-v4/clients/ocp/stable/openshift-client-linux.tar.gz \
        -o /tmp/oc.tar.gz \
      && sudo tar -xzf /tmp/oc.tar.gz -C /usr/local/bin oc kubectl \
      && rm -f /tmp/oc.tar.gz
    fi
  '
}

# ---------------------------------------------------------------------------
# Bastion internet lifecycle — EPHEMERAL, dynamically discovered.
#
# Nothing here is hardcoded to a resource name: we query GCP at runtime for
# (a) which subnet the bastion's NIC is ACTUALLY attached to (works whether
#     it's a fresh dedicated bastion-subnet or a legacy/manually-created
#     subnet the bastion happens to already live in), and
# (b) any router/NAT that already exists on this VPC+region, reusing and
#     re-scoping it rather than assuming our own naming.
#
# The actual find/grant/revoke logic lives in lib-bastion-net.sh (shared
# with bastion-internet.sh and clean-environment.sh). ensure_bastion_internet
# grants the bastion (and ONLY the bastion's subnet) outbound internet just
# long enough to install tooling and mirror the release.
# teardown_bastion_internet() is registered as an EXIT trap in main() so it
# always runs — on success, on failure, on Ctrl-C — leaving the final
# environment with ZERO internet egress anywhere, matching what a real
# disconnected customer environment looks like at rest.
# ---------------------------------------------------------------------------
ensure_bastion_internet() {
  log "Granting the bastion temporary internet access (for tooling + mirroring only)..."
  bastion_internet_on
}

teardown_bastion_internet() {
  local exit_code=$?
  set +e
  if [ "${NAT_MANAGED_BY_SCRIPT}" = "1" ]; then
    log "Tearing down Cloud NAT so nothing in this environment retains internet access..."
    bastion_internet_off
    log "  Done — bastion and all cluster nodes now have zero internet egress."
  fi
  exit "${exit_code}"
}

# ---------------------------------------------------------------------------
# Stage 3 — Mirror registry (Quay mirror-registry tool) — idempotent
# ---------------------------------------------------------------------------
stage_mirror_registry() {
  log "Stage 3/6: Mirror registry"

  local already_running
  already_running=$(ssh_bastion "podman ps --format '{{.Names}}' 2>/dev/null | grep -c quay-app || true")

  if [ "${already_running}" = "1" ]; then
    log "  Quay mirror-registry already running, skipping install."
  else
    log "  Installing mirror-registry tool from your local tarball (one-time)..."
    ssh_bastion 'mkdir -p ~/mirror-registry'
    local mirror_tool_state
    mirror_tool_state=$(ssh_bastion 'test -f ~/mirror-registry/mirror-registry && echo EXISTS || echo MISSING' | tail -1)
    if [ "${mirror_tool_state}" = "MISSING" ]; then
      scp_to_bastion "${MIRROR_REGISTRY_TARBALL_PATH}" "~/mirror-registry/mirror-registry.tar.gz"
      ssh_bastion 'cd ~/mirror-registry && tar -xzf mirror-registry.tar.gz'
    fi

    log "  Installing Quay mirror-registry (user: ${MIRROR_INIT_USER})..."
    ssh_bastion "
      cd ~/mirror-registry
      ./mirror-registry install \
        --quayHostname \$(hostname -f):8443 \
        --initUser '${MIRROR_INIT_USER}' \
        --initPassword '${MIRROR_INIT_PASSWORD}' \
        --quayRoot ~/quay-install -v 2>&1 | tee ~/mirror-install.log | tail -20
    "
  fi

  # Quay's self-signed cert is only trusted if we explicitly say so.
  # `podman login --tls-verify=false` below only bypasses it for that one
  # login — `oc adm release mirror`/`extract` (Go binaries using the system
  # cert pool + containers/image library) need the CA installed properly.
  # Done unconditionally (not just on fresh installs) so this stays
  # idempotent and self-healing on any existing bastion.
  log "  Trusting the mirror registry's CA on the bastion (system + containers)..."
  ssh_bastion "
    sudo cp ~/quay-install/quay-rootCA/rootCA.pem /etc/pki/ca-trust/source/anchors/mirror-registry-ca.pem
    sudo chmod 644 /etc/pki/ca-trust/source/anchors/mirror-registry-ca.pem
    sudo update-ca-trust extract
    sudo mkdir -p /etc/containers/certs.d/\$(hostname -f):8443
    sudo cp ~/quay-install/quay-rootCA/rootCA.pem /etc/containers/certs.d/\$(hostname -f):8443/ca.crt
    sudo chmod 755 /etc/containers/certs.d/\$(hostname -f):8443
    sudo chmod 644 /etc/containers/certs.d/\$(hostname -f):8443/ca.crt
  "

  log "  Verifying mirror-registry login..."
  # --password-stdin (piped via a here-string) instead of -p — keeps the
  # password out of the podman process's own argv, so it doesn't show up
  # in `ps` output on the bastion to anyone else who can see it.
  ssh_bastion "
    podman login --tls-verify=false -u '${MIRROR_INIT_USER}' --password-stdin \
      \$(hostname -f):8443 <<< '${MIRROR_INIT_PASSWORD}'
  "

  log "  Adding mirror registry creds to pull-secret.json..."
  ssh_bastion "
python3 - <<'PYEOF'
import json, base64, socket
path = '/home/' + __import__('getpass').getuser() + '/pull-secret.json'
with open(path) as f:
    ps = json.load(f)
hostname = socket.getfqdn()
cred = base64.b64encode(b'${MIRROR_INIT_USER}:${MIRROR_INIT_PASSWORD}').decode()
ps['auths'][hostname + ':8443'] = {'auth': cred}
with open(path, 'w') as f:
    json.dump(ps, f)
print('pull-secret updated for', hostname + ':8443')
PYEOF
  "
}

# ---------------------------------------------------------------------------
# Stage 4 — Resolve release image + mirror it
# ---------------------------------------------------------------------------
RELEASE_PULLSPEC=""
LOCAL_RELEASE_PULLSPEC=""
stage_mirror_release() {
  log "Stage 4/6: Resolve & mirror OCP release ${OCP_VERSION}"

  local hostname
  hostname=$(ssh_bastion "hostname -f" | tail -1)
  local local_registry="${hostname}:8443"
  local local_repo="ocp/release"

  # Resolve version -> full pullspec
  if [[ "${OCP_VERSION}" =~ ^[0-9]+\.[0-9]+\.[0-9]+ && ! "${OCP_VERSION}" =~ nightly ]]; then
    # Stable GA release from quay.io
    RELEASE_PULLSPEC="quay.io/openshift-release-dev/ocp-release:${OCP_VERSION}-x86_64"
    log "  Resolved stable release: ${RELEASE_PULLSPEC}"
  elif [[ "${OCP_VERSION}" =~ nightly ]]; then
    # Full nightly tag given directly. EVERY nightly build on
    # registry.ci.openshift.org — regardless of major/minor — is published
    # under the single repo path "ocp/release"; there is no per-major
    # "release-<N>" repo there (unlike the local on-prem mirror layout
    # below, which we choose to split by major purely for our own
    # organizational clarity).
    RELEASE_PULLSPEC="registry.ci.openshift.org/ocp/release:${OCP_VERSION}"
    # Confirm the tag actually exists on the release controller (catches
    # typos) before committing to a 30-60 min mirror against it. NOTE: the
    # per-tag `/release/<tag>` endpoint (unlike `/latest` used below) does
    # NOT return a "pullSpec" field — it's only usable here to confirm the
    # tag exists, which is why RELEASE_PULLSPEC is built directly above.
    local nightly_stream="${OCP_VERSION%%-*}"
    local nightly_suffix="${OCP_VERSION#*-}"
    nightly_stream="${nightly_stream}-${nightly_suffix%%-*}"
    curl -sf "https://amd64.ocp.releases.ci.openshift.org/api/v1/releasestream/${nightly_stream}/release/${OCP_VERSION}" \
      >/dev/null || die "Nightly tag ${OCP_VERSION} not found on the release controller (checked stream ${nightly_stream}). Double-check the tag, e.g. via https://amd64.ocp.releases.ci.openshift.org/#${nightly_stream}."
    log "  Using given nightly tag: ${RELEASE_PULLSPEC}"
  else
    # Minor version like "5.1" -> look up latest accepted nightly
    log "  Looking up latest accepted nightly for ${OCP_VERSION}..."
    local api="https://amd64.ocp.releases.ci.openshift.org/api/v1/releasestream/${OCP_VERSION}.0-0.nightly/latest"
    local resolved
    resolved=$(curl -sf "${api}" | python3 -c "import json,sys; print(json.load(sys.stdin)['pullSpec'])") \
      || die "Could not resolve latest nightly for ${OCP_VERSION}. Pass a full nightly tag instead."
    RELEASE_PULLSPEC="${resolved}"
    log "  Resolved: ${RELEASE_PULLSPEC}"
  fi

  local major
  major=$(echo "${OCP_VERSION}" | cut -d. -f1)
  LOCAL_RELEASE_PULLSPEC="${local_registry}/${local_repo}-${major}:$(basename "${RELEASE_PULLSPEC##*:}")"

  log "  Mirroring ${RELEASE_PULLSPEC} -> ${local_registry}/${local_repo}-${major} (this takes 30-60 min)..."
  # Fresh status file every run — otherwise a stale success/failure line
  # from a previous mirror attempt could be misread by the poller below
  # before this run's own line is appended.
  ssh_bastion "rm -f ~/mirror-latest.log"

  ssh_bastion "
    nohup bash -c '
      oc adm release mirror \
        --from=${RELEASE_PULLSPEC} \
        --to=${local_registry}/${local_repo}-${major} \
        --to-release-image=${LOCAL_RELEASE_PULLSPEC} \
        --registry-config=/home/\$(whoami)/pull-secret.json \
        --print-mirror-instructions=idms 2>&1 | tee ~/mirror-\$(date +%s).log
      echo MIRROR_EXIT_CODE: \${PIPESTATUS[0]} >> ~/mirror-latest.log
    ' > /dev/null 2>&1 &
    disown
    echo 'Mirror started in background.'
  "

  log "  Polling for completion (checking every 60s, this can take a while)..."
  # Bounded wait: without this, a bastion reboot/OOM-kill that takes down
  # the background mirror process WITHOUT it ever writing MIRROR_EXIT_CODE
  # would leave this loop polling forever. die() here still runs through
  # the EXIT trap (registered in main() before this stage), so the
  # temporary NAT still gets torn down instead of leaking internet access.
  local max_wait_seconds=$((3 * 60 * 60))  # 3h — mirroring is normally 30-60min
  local waited_seconds=0
  while true; do
    local status
    # A transient local IAP-tunnel/SSH hiccup here must NOT be fatal: the
    # background mirror keeps running on the bastion regardless, but under
    # `set -e` a failed assignment would kill this whole script — and the
    # EXIT trap would then tear down the bastion's temporary internet
    # access mid-mirror, forcing the user to redo this multi-hour stage.
    # Treat a failed poll the same as "still running" and just retry next
    # interval; the max_wait_seconds bound above still stops the loop if
    # the bastion genuinely never responds again.
    status=$(ssh_bastion "tail -1 ~/mirror-latest.log 2>/dev/null || echo RUNNING") \
      || { warn "  Poll SSH failed (transient IAP issue?) — retrying next interval."; status="RUNNING"; }
    if echo "${status}" | grep -q "MIRROR_EXIT_CODE: 0"; then
      log "  Mirror completed successfully."
      break
    elif echo "${status}" | grep -q "MIRROR_EXIT_CODE:"; then
      die "Mirror failed (${status}). Check ~/mirror-*.log on the bastion for full output."
    fi
    if [ "${waited_seconds}" -ge "${max_wait_seconds}" ]; then
      die "Mirror did not report completion within $((max_wait_seconds / 60)) minutes (no MIRROR_EXIT_CODE seen — bastion may have rebooted or the process was killed). Check ~/mirror-*.log on the bastion."
    fi
    sleep 60
    waited_seconds=$((waited_seconds + 60))
  done
}

# ---------------------------------------------------------------------------
# Stage 5 — Generate install-config.yaml
# ---------------------------------------------------------------------------
generate_install_config_for_zone() {
  local zone="$1"
  local hostname hex_suffix ca_cert pull_secret major

  hostname=$(ssh_bastion "hostname -f" | tail -1)
  ca_cert=$(ssh_bastion "cat ~/quay-install/quay-rootCA/rootCA.pem")
  pull_secret=$(ssh_bastion "cat ~/pull-secret.json")
  # Computed HERE (locally) rather than inside the heredoc below, because
  # that heredoc's terminator is quoted (<<'INSTALLCONFIGEOF') so nothing
  # inside it is expanded remotely — a remote $(...) would be written into
  # install-config.yaml as literal, invalid text.
  major=$(echo "${OCP_VERSION}" | cut -d. -f1)

  ssh_bastion "rm -rf ~/cluster && mkdir -p ~/cluster"

  # Build install-config.yaml directly on the bastion via python for safe
  # YAML/JSON string handling (avoids local shell-escaping headaches).
  ssh_bastion "cat > ~/cluster/install-config.yaml <<'INSTALLCONFIGEOF'
apiVersion: v1
metadata:
  name: ${CLUSTER_NAME}
additionalTrustBundlePolicy: Always
baseDomain: ${BASE_DOMAIN}
publish: Internal
platform:
  gcp:
    projectID: ${PROJECT}
    region: ${REGION}
    network: ${VPC_NAME}
    controlPlaneSubnet: ${MASTER_SUBNET}
    computeSubnet: ${WORKER_SUBNET}
controlPlane:
  name: master
  architecture: amd64
  hyperthreading: Enabled
  platform:
    gcp:
      onHostMaintenance: Terminate
      type: ${MACHINE_TYPE}
      zones:
      - ${zone}
  replicas: ${MASTER_REPLICAS}
compute:
  - name: worker
    architecture: amd64
    hyperthreading: Enabled
    platform:
      gcp:
        onHostMaintenance: Terminate
        type: ${MACHINE_TYPE}
        zones:
        - ${zone}
    replicas: ${WORKER_REPLICAS}
networking:
  clusterNetwork:
    - cidr: ${CLUSTER_CIDR}
      hostPrefix: 23
  machineNetwork:
    - cidr: ${MASTER_SUBNET_CIDR}
    - cidr: ${WORKER_SUBNET_CIDR}
  networkType: OVNKubernetes
  serviceNetwork:
    - ${SERVICE_CIDR}
imageDigestSources:
- mirrors:
  - ${hostname}:8443/ocp/release-${major}
  source: quay.io/openshift-release-dev/ocp-v4.0-art-dev
- mirrors:
  - ${hostname}:8443/ocp/release-${major}
  source: quay.io/openshift-release-dev/ocp-v5.0-art-dev
- mirrors:
  - ${hostname}:8443/ocp/release-${major}
  # registry.ci.openshift.org publishes every CI nightly under the single
  # repo path ocp/release (no per-major suffix). This mirror entry is
  # inert (never matched) for GA/stable installs, which pull from the
  # quay.io entries above instead.
  source: registry.ci.openshift.org/ocp/release
additionalTrustBundle: |
$(echo "${ca_cert}" | sed 's/^/  /')
pullSecret: |
  $(echo "${pull_secret}" | python3 -c "import json,sys; print(json.dumps(json.load(sys.stdin)))")
sshKey: |
  $(cat "${SSH_PUBLIC_KEY_PATH}")
INSTALLCONFIGEOF
"
  log "  install-config.yaml generated for zone ${zone}."
}

# ---------------------------------------------------------------------------
# Stage 6 — Extract installer + create cluster, with zone-capacity retry
# ---------------------------------------------------------------------------
cleanup_stale_gcp_resources() {
  log "  Cleaning up any stale GCP resources from a previous failed attempt..."
  local dns_zone
  dns_zone=$(gcloud dns managed-zones list --project="${PROJECT}" \
    --filter="dnsName=${CLUSTER_NAME}.${BASE_DOMAIN}." --format="value(name)" || true)
  if [ -n "${dns_zone}" ]; then
    for rs in api api-int; do
      gcloud dns record-sets delete "${rs}.${CLUSTER_NAME}.${BASE_DOMAIN}." \
        --zone="${dns_zone}" --type=A --project="${PROJECT}" --quiet 2>/dev/null || true
    done
    gcloud dns managed-zones delete "${dns_zone}" --project="${PROJECT}" --quiet 2>/dev/null || true
  fi

  # Anchored to the EXACT infraID this failed attempt was assigned (read
  # from metadata.json, which still exists on the bastion at this point —
  # see this function's caller, which checks for it right before its own
  # `destroy cluster` attempt), NOT a bare "${CLUSTER_NAME}-<5 chars>"
  # guess: that fallback is not actually safe on its own — e.g.
  # CLUSTER_NAME "team-dc" would also match a completely different cluster
  # named "team-dc-stage" in the same shared project (its "stage" segment
  # satisfies the same 5-char shape). Skip this sweep entirely rather than
  # risk deleting another cluster's load-balancer resources if the infraID
  # can't be read.
  local infra_id
  infra_id=$(ssh_bastion "cat /home/\$(whoami)/cluster/metadata.json 2>/dev/null" 2>/dev/null \
    | python3 -c "import json,sys; print(json.load(sys.stdin).get('infraID',''))" 2>/dev/null || true)
  if [ -z "${infra_id}" ]; then
    warn "  Could not read infraID from metadata.json — skipping the forwarding-rule/backend-service sweep to avoid risking another cluster's resources in this shared project. Check the GCP console manually for leftovers named '${CLUSTER_NAME}-<id>-*' if the next zone attempt also fails."
    return 0
  fi
  local infra_id_anchor="^${infra_id}-"

  # Regional resources (the internal api/api-int NLB, typically).
  for res in $(gcloud compute forwarding-rules list --project="${PROJECT}" --regions="${REGION}" \
      --filter="name~${infra_id_anchor}" --format="value(name)" || true); do
    gcloud compute forwarding-rules delete "${res}" --region="${REGION}" \
      --project="${PROJECT}" --quiet 2>/dev/null || true
  done
  for res in $(gcloud compute backend-services list --project="${PROJECT}" --regions="${REGION}" \
      --filter="name~${infra_id_anchor}" --format="value(name)" || true); do
    gcloud compute backend-services delete "${res}" --region="${REGION}" \
      --project="${PROJECT}" --quiet 2>/dev/null || true
  done

  # GLOBAL resources too — installer-created LBs aren't always regional
  # (e.g. this cluster's ingress could end up behind a global external LB
  # depending on install-config settings). Omitting this sweep would leave
  # global forwarding-rules/backend-services behind silently (the `|| true`
  # above only swallows errors from resources that WERE found; it doesn't
  # search the global scope at all).
  for res in $(gcloud compute forwarding-rules list --project="${PROJECT}" --global \
      --filter="name~${infra_id_anchor}" --format="value(name)" || true); do
    gcloud compute forwarding-rules delete "${res}" --global \
      --project="${PROJECT}" --quiet 2>/dev/null || true
  done
  for res in $(gcloud compute backend-services list --project="${PROJECT}" --global \
      --filter="name~${infra_id_anchor}" --format="value(name)" || true); do
    gcloud compute backend-services delete "${res}" --global \
      --project="${PROJECT}" --quiet 2>/dev/null || true
  done
}

stage_extract_installer() {
  log "  Extracting openshift-install binary matching the mirrored release..."
  ssh_bastion "
    cd ~/cluster-tools
    oc adm release extract \
      --registry-config=/home/\$(whoami)/pull-secret.json \
      --command=openshift-install \
      --to=. \
      ${LOCAL_RELEASE_PULLSPEC}
    ./openshift-install version
  "
}

stage_create_cluster() {
  log "Stage 6/6: Create cluster (with zone-capacity retry)"
  # If ~/cluster/metadata.json already exists, a PREVIOUS run's cluster may
  # still be live: the first zone-loop iteration below is about to `rm -rf
  # ~/cluster` (via generate_install_config_for_zone), which would destroy
  # our only handle for a proper `openshift-install destroy cluster` on
  # that old cluster, then try to create a NEW cluster with the same
  # CLUSTER_NAME/BASE_DOMAIN — colliding with the still-live private DNS
  # zone and load balancers, and orphaning the old cluster's resources.
  # (The zone-capacity retry loop further down already protects itself the
  # same way between zones; this guards the very first attempt.)
  if ssh_bastion "[ -f /home/\$(whoami)/cluster/metadata.json ]" 2>/dev/null; then
    die "~/cluster/metadata.json already exists on the bastion — a cluster from a previous run may still be live. Destroy it first (clean-environment.sh, or 'openshift-install destroy cluster --dir=~/cluster' on the bastion) before re-running."
  fi
  stage_extract_installer

  for zone in "${ZONES[@]}"; do
    log "  Attempting install in zone: ${zone}"
    generate_install_config_for_zone "${zone}"

    ssh_bastion "
      cd ~/cluster-tools
      # The installer's default image-signature policy expects to reach
      # quay.io/openshift-release-dev's signature store directly, which is
      # unreachable from this disconnected environment (only the mirror
      # registry is reachable). Without this, 'create cluster' fails
      # signature verification even though the mirrored release image
      # itself is valid.
      export OPENSHIFT_INSTALL_EXPERIMENTAL_DISABLE_IMAGE_POLICY=true
      ./openshift-install create cluster --dir=/home/\$(whoami)/cluster --log-level=info \
        2>&1 | tee ~/install.log
      echo INSTALL_EXIT_CODE: \${PIPESTATUS[0]} >> ~/install.log
    " || true

    local result
    result=$(ssh_bastion "tail -5 ~/install.log")

    if echo "${result}" | grep -q "INSTALL_EXIT_CODE: 0"; then
      log "  Cluster created successfully in zone ${zone}!"
      ssh_bastion "export KUBECONFIG=/home/\$(whoami)/cluster/auth/kubeconfig && oc get nodes && oc get clusterversion"
      return 0
    fi

    if echo "${result}" | grep -qi "ZONE_RESOURCE_POOL_EXHAUSTED"; then
      warn "  Zone ${zone} is out of capacity for ${MACHINE_TYPE}. Destroying the partial attempt and trying next zone..."
      # A ZONE_RESOURCE_POOL_EXHAUSTED failure can happen AFTER
      # openshift-install already created real resources for this attempt's
      # infraID (instances, instance groups, IAM service accounts, the
      # ignition GCS bucket, firewall rules — well beyond what
      # cleanup_stale_gcp_resources below sweeps). The next loop iteration's
      # generate_install_config_for_zone does `rm -rf ~/cluster`, which
      # deletes metadata.json — our only handle for a proper destroy — so
      # this MUST run first, while it still exists.
      if ssh_bastion "[ -f /home/\$(whoami)/cluster/metadata.json ]" 2>/dev/null; then
        ssh_bastion "
          cd ~/cluster-tools
          ./openshift-install destroy cluster --dir=/home/\$(whoami)/cluster --log-level=info 2>&1 | tail -30
        " || warn "  Partial-attempt 'destroy cluster' failed/incomplete — continuing with the stale-resource sweep as a best-effort cleanup."
      fi
      cleanup_stale_gcp_resources
      continue
    fi

    die "Install failed for a reason other than zone capacity. Check ~/install.log on the bastion:\n${result}"
  done

  die "All zones exhausted (${ZONES[*]}). Try different ZONES or a smaller MACHINE_TYPE."
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
main() {
  log "Installing disconnected OCP ${OCP_VERSION} as cluster '${CLUSTER_NAME}' in project ${PROJECT}"

  ensure_secrets_configured

  stage_network
  stage_bastion_create
  # Registered BEFORE calling ensure_bastion_internet (not after), so
  # teardown still runs even if that function itself fails partway through
  # (e.g. NAT gets created but a later command in it dies) or is
  # interrupted with Ctrl-C during its `sleep 15`. ensure_bastion_internet
  # sets NAT_NAME_ACTIVE/NAT_MANAGED_BY_SCRIPT as soon as it creates/updates
  # the NAT, so teardown_bastion_internet (a no-op until those are set)
  # correctly cleans up in every one of those cases too.
  trap teardown_bastion_internet EXIT
  ensure_bastion_internet
  stage_bastion_provision
  stage_mirror_registry
  stage_mirror_release
  stage_create_cluster

  log "Done! SSH to the bastion and run: export KUBECONFIG=~/cluster/auth/kubeconfig"
  log "Note: bastion's temporary internet access is being removed now (see next log lines)."
}

main "$@"
