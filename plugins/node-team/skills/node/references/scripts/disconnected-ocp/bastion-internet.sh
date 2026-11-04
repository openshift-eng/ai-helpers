#!/usr/bin/env bash
#
# ============================================================================
# bastion-internet.sh
#
# Temporarily grant or revoke internet access to the bastion in a
# disconnected OCP environment created by install-disconnected-ocp.sh.
#
# install-disconnected-ocp.sh already removes internet access from
# everything (bastion included) when it finishes a run. Use THIS script
# whenever you need the bastion to reach the public internet again for a
# one-off task — e.g. pulling a new test image to mirror in:
#
#   ./bastion-internet.sh on
#   # on the bastion:
#   #   podman pull <public-image>
#   #   podman tag  <public-image> $(hostname -f):8443/test/<name>:<tag>
#   #   podman push --tls-verify=false --remove-signatures --format v2s2 \
#   #     $(hostname -f):8443/test/<name>:<tag>
#   ./bastion-internet.sh off
#
# Like install-disconnected-ocp.sh, NOTHING here is hardcoded: it discovers
# the bastion's actual subnet, and any existing router/NAT, at runtime. The
# actual find/grant/revoke/status logic lives in lib-bastion-net.sh, shared
# with install-disconnected-ocp.sh and clean-environment.sh.
#
# USAGE:
#   ./bastion-internet.sh on     [cluster-name]   # grant bastion internet (idempotent)
#   ./bastion-internet.sh off    [cluster-name]   # revoke it again (idempotent)
#   ./bastion-internet.sh status [cluster-name]   # show current state
#
# Reads the same config.env as install-disconnected-ocp.sh (if present) so
# it targets the same PROJECT/REGION/CLUSTER_NAME without re-typing anything.
# [cluster-name] only needs to be passed if you installed with a custom
# cluster name (install-disconnected-ocp.sh's own [cluster-name] argument) —
# it is NOT persisted to config.env, so it must be repeated here too.
# ============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="${SCRIPT_DIR}/config.env"
if [ -f "${CONFIG_FILE}" ]; then
  # shellcheck disable=SC1090
  source "${CONFIG_FILE}"
fi

PROJECT="${PROJECT:-openshift-qe}"
REGION="${REGION:-us-central1}"
# $2, not $1 — $1 is the on/off/status action below. Needed so this script
# can target a cluster installed with a custom [cluster-name], since that
# name is never persisted to config.env (see install-disconnected-ocp.sh).
CLUSTER_NAME="${2:-${CLUSTER_NAME:-$(whoami)-dc}}"
# Always DERIVED from the selected CLUSTER_NAME — deliberately NOT
# overridable via config.env/env vars (same reasoning as
# clean-environment.sh and install-disconnected-ocp.sh). Otherwise a
# [cluster-name] argument would change CLUSTER_NAME but leave a stale
# config.env's BASTION_NAME/VPC_NAME/etc. pointed at a DIFFERENT
# environment, and `on`/`off` would silently act on the wrong bastion.
BASTION_NAME="${CLUSTER_NAME}-bastion"
VPC_NAME="${CLUSTER_NAME}-vpc"
ROUTER_NAME="${CLUSTER_NAME}-router"
NAT_NAME="${CLUSTER_NAME}-nat"

log()  { echo -e "\033[1;34m[bastion-internet]\033[0m $*"; }
warn() { echo -e "\033[1;33m[WARN]\033[0m $*"; }
die()  { echo -e "\033[1;31m[ERROR]\033[0m $*" >&2; exit 1; }

# shellcheck disable=SC1091
source "${SCRIPT_DIR}/lib-bastion-net.sh"

action="${1:-status}"

case "${action}" in
  on)
    # NOT `|| true` here — find_bastion_zone's own die() (ambiguous
    # multi-zone match) only kills the subshell $(...) runs in; `|| true`
    # would silently swallow that exit and misreport "bastion not found"
    # instead of the real "investigate manually" condition. Propagate it.
    BASTION_ZONE="$(find_bastion_zone)" || die "Could not determine the bastion zone."
    [ -n "${BASTION_ZONE}" ] || die "Bastion ${BASTION_NAME} not found in project ${PROJECT}."
    bastion_internet_on
    warn "Remember to run: $0 off   — once you're done pulling/mirroring."
    ;;

  off)
    bastion_internet_off
    ;;

  status)
    bastion_internet_status
    ;;

  *)
    die "Usage: $0 {on|off|status} [cluster-name]"
    ;;
esac
