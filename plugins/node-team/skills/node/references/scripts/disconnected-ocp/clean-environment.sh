#!/usr/bin/env bash
#
# ============================================================================
# clean-environment.sh
#
# FULLY AND IRREVERSIBLY deletes everything install-disconnected-ocp.sh
# creates for a given CLUSTER_NAME: the OCP cluster (via proper `destroy
# cluster` if reachable, plus a sweep for stale leftovers), the bastion VM
# (and with it the mirror-registry/Quay data), Cloud NAT/Router, firewall
# rules, subnets, and the VPC itself. Also removes your local config.env so
# the next run of install-disconnected-ocp.sh behaves like a brand new
# team member running it for the very first time.
#
# USE THIS WHEN: you want to reset a project back to a clean slate to test
# the "first-time user" experience, or to tear down a demo/test environment
# you no longer need.
#
# USAGE:
#   ./clean-environment.sh [cluster-name]
#
# You will be asked to type the cluster name to confirm before ANYTHING is
# deleted. There is no undo.
# ============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="${SCRIPT_DIR}/config.env"
[ -f "${CONFIG_FILE}" ] && source "${CONFIG_FILE}"

PROJECT="${PROJECT:-openshift-qe}"
REGION="${REGION:-us-central1}"
BASE_DOMAIN="${BASE_DOMAIN:-qe.gcp.devcluster.openshift.com}"
CLUSTER_NAME="${1:-${CLUSTER_NAME:-$(whoami)-dc}}"
# Always DERIVED from the selected CLUSTER_NAME — deliberately NOT
# overridable via config.env/env vars. If VPC_NAME/BASTION_NAME could be
# sourced independently of CLUSTER_NAME, a stale/edited config.env could
# pair the cluster name the user just confirmed with a DIFFERENT VPC/bastion
# and delete the wrong environment. install-disconnected-ocp.sh derives
# these identically (unconditionally from CLUSTER_NAME) for the same reason.
VPC_NAME="${CLUSTER_NAME}-vpc"
BASTION_NAME="${CLUSTER_NAME}-bastion"

# NOTE: the exact infraID-based anchor used to scope the load-balancer
# sweep below (CLUSTER_NAME_ANCHOR) is resolved later, from the bastion's
# own cluster metadata, once we know whether the bastion is even reachable.
# See the "Resolve infraID" step after the destroy-cluster attempt below —
# a bare "${CLUSTER_NAME}-[a-z0-9]{5}" guess is NOT safe on its own: e.g.
# CLUSTER_NAME "team-dc" would also match a totally different cluster named
# "team-dc-stage" in the same shared project (its "stage" segment satisfies
# the same 5-char shape), even with a trailing "-" added to the pattern.

log()  { echo -e "\033[1;34m[clean-environment]\033[0m $*"; }
warn() { echo -e "\033[1;33m[WARN]\033[0m $*"; }
die()  { echo -e "\033[1;31m[ERROR]\033[0m $*" >&2; exit 1; }

# Only find_bastion_zone() from the shared lib is used here (this script
# never grants/revokes internet access itself — that's bastion-internet.sh
# and install-disconnected-ocp.sh's job), so ROUTER_NAME/NAT_NAME are not
# set before sourcing; the lib's other functions simply aren't called.
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/lib-bastion-net.sh"

# Set to 1 whenever a deletion step below fails in a way that could leave
# real resources behind, so we know not to delete config.env at the end
# (losing the ability to target a retry) and can report an honest result
# instead of claiming a full teardown that didn't actually happen.
TEARDOWN_FAILED=0

# GCP resource deletion is not always immediately consistent — e.g. deleting
# a subnet can report success while the network still briefly considers it
# "in use", or a network delete can fail with "not ready" for a few seconds
# after its last subnet/address was removed. Retry a few times with backoff
# instead of failing the whole script on these transient errors.
retry_delete() {
  local desc="$1"; shift
  local max_attempts=6 attempt=1 delay=10
  local out
  while [ "${attempt}" -le "${max_attempts}" ]; do
    if out=$("$@" 2>&1); then
      return 0
    fi
    if echo "${out}" | grep -qi "was not found\|notFound"; then
      return 0  # already gone — treat as success
    fi
    warn "  Attempt ${attempt}/${max_attempts} to delete ${desc} failed (likely transient GCP consistency lag):"
    echo "${out}" | tail -3
    if [ "${attempt}" -lt "${max_attempts}" ]; then
      warn "  Retrying in ${delay}s..."
      sleep "${delay}"
    fi
    attempt=$((attempt + 1))
  done
  warn "  Giving up on deleting ${desc} after ${max_attempts} attempts — please check/delete it manually."
  return 1
}

# Best-effort delete used by the stale-resource sweeps below (DNS zone,
# forwarding rules, backend services, health checks, addresses). Unlike
# retry_delete (used for subnets/VPC, where transient "still in use" errors
# are expected and worth retrying), a single attempt is enough here — but
# unlike a bare `|| true`, a REAL failure still gets logged and flips
# TEARDOWN_FAILED, instead of unconditionally printing "Deleted" and
# reporting a clean teardown that didn't actually happen.
try_delete() {
  local desc="$1"; shift
  local out
  if out=$("$@" 2>&1); then
    log "  Deleted ${desc}"
    return 0
  fi
  if echo "${out}" | grep -qi "was not found\|notFound"; then
    return 0  # already gone — not a failure
  fi
  warn "  Failed to delete ${desc}: $(echo "${out}" | tail -1)"
  TEARDOWN_FAILED=1
  return 1
}

# Runs a `gcloud ... list` and stores its output into the global
# LIST_RESULT (newline-separated names) for the caller's `for x in
# ${LIST_RESULT}` loop. On failure, sets TEARDOWN_FAILED=1 and leaves
# LIST_RESULT empty, so a transient listing error (rate limit, brief API
# hiccup) can't silently look identical to "nothing to delete" here — it
# gets flagged instead of letting the sweep quietly do nothing.
#
# IMPORTANT: must be called as a bare statement (never via `$(run_list
# ...)`) — that would fork a subshell, and TEARDOWN_FAILED/LIST_RESULT set
# inside it would then be lost the moment that subshell exits.
run_list() {
  local desc="$1"; shift
  LIST_RESULT=""
  local out
  if ! out=$("$@" 2>&1); then
    warn "  Failed to list ${desc} — skipping this sweep: $(echo "${out}" | tail -1)"
    TEARDOWN_FAILED=1
    return 0
  fi
  LIST_RESULT="${out}"
}

echo ""
warn "This will PERMANENTLY DELETE everything for cluster '${CLUSTER_NAME}' in project '${PROJECT}':"
echo "    - The OCP cluster itself (masters/workers/load balancers/DNS)"
echo "    - The bastion VM (${BASTION_NAME}) and its mirror-registry data"
echo "    - Cloud NAT + Router"
echo "    - Firewall rules on ${VPC_NAME}"
echo "    - All subnets on ${VPC_NAME}"
echo "    - The VPC ${VPC_NAME} itself"
echo "    - Your local ${CONFIG_FILE}"
echo ""
read -r -p "Type the cluster name (${CLUSTER_NAME}) to confirm: " confirm
[ "${confirm}" = "${CLUSTER_NAME}" ] || die "Confirmation did not match. Aborting — nothing was deleted."

# ---------------------------------------------------------------------------
# 1. Try a proper `openshift-install destroy cluster` first (cleanest).
#    find_bastion_zone() (VPC-anchored, refuses to guess on an ambiguous
#    multi-zone match — this feeds directly into what gets destroyed) comes
#    from the shared lib-bastion-net.sh sourced above.
# ---------------------------------------------------------------------------
# NOT `|| true` here — find_bastion_zone's own die() (ambiguous multi-zone
# match, or a `gcloud ... list` failure) only kills the subshell $(...)
# runs in; `|| true` would silently swallow that exit and let the script
# continue with an empty BASTION_ZONE, skipping the clean 'destroy cluster'
# and bastion delete while still sweeping/deleting other resources and
# eventually the VPC — defeating the "refuse to guess" check entirely.
BASTION_ZONE="$(find_bastion_zone)" || die "Could not determine the bastion zone — aborting before any deletion."

if [ -n "${BASTION_ZONE}" ]; then
  log "Bastion found in ${BASTION_ZONE}. Attempting a clean 'openshift-install destroy cluster'..."
  # `exit \${PIPESTATUS[0]}` on the remote side propagates the *installer's*
  # exit code (not `tail`'s) back through SSH; PIPESTATUS is captured again
  # locally after the local `| grep` filter for the same reason — otherwise
  # `||` below would only ever observe grep's exit status, and this step's
  # actual success/failure would never be checked at all.
  DESTROY_STATUS=0
  if ! gcloud compute ssh "${BASTION_NAME}" --zone="${BASTION_ZONE}" --project="${PROJECT}" \
    --tunnel-through-iap --command="
      if [ -f /home/\$(whoami)/cluster/metadata.json ] && [ -f /home/\$(whoami)/cluster-tools/openshift-install ]; then
        cd ~/cluster-tools
        ./openshift-install destroy cluster --dir=/home/\$(whoami)/cluster --log-level=info 2>&1 | tail -30
        exit \${PIPESTATUS[0]}
      else
        echo 'No cluster metadata.json / openshift-install binary found — skipping clean destroy.'
      fi
    " 2>&1 | grep -v "^Existing host\|^Warning: Permanently added"; then
    DESTROY_STATUS="${PIPESTATUS[0]}"
  fi
  if [ "${DESTROY_STATUS}" -ne 0 ]; then
    warn "Clean 'destroy cluster' failed (exit ${DESTROY_STATUS}) — continuing with the manual sweep below to remove what it couldn't, but config.env will be kept in case a retry is needed."
    TEARDOWN_FAILED=1
  fi
else
  log "No bastion found — skipping clean 'destroy cluster' step (nothing to SSH into)."
fi

# ---------------------------------------------------------------------------
# 1b. Resolve this cluster's EXACT infraID from the bastion's own
#     ~/cluster/metadata.json, so the load-balancer sweep in step 2 can
#     anchor to it precisely instead of guessing. metadata.json survives
#     `destroy cluster` above (that command never removes the file itself),
#     so it's still readable here even when the destroy attempt succeeded.
#
#     A bare "${CLUSTER_NAME}-[a-z0-9]{5}" pattern is NOT safe here on its
#     own: e.g. CLUSTER_NAME "team-dc" would also match a totally different
#     cluster named "team-dc-stage" in the same shared project — its
#     "stage" segment satisfies the same 5-char shape, and adding a
#     trailing "-" doesn't fix it either ("team-dc-stage-" still matches).
#     Only an exact infraID, read from this specific attempt's own
#     metadata, can safely scope which load-balancer resources get deleted.
# ---------------------------------------------------------------------------
INFRA_ID="${INFRA_ID:-}"  # optional manual override, e.g. if the bastion is already gone
if [ -z "${INFRA_ID}" ] && [ -n "${BASTION_ZONE}" ]; then
  log "Reading exact infraID from bastion's ~/cluster/metadata.json..."
  INFRA_ID="$(gcloud compute ssh "${BASTION_NAME}" --zone="${BASTION_ZONE}" --project="${PROJECT}" \
      --tunnel-through-iap --command="cat /home/\$(whoami)/cluster/metadata.json" 2>/dev/null \
    | grep -v "^Existing host\|^Warning: Permanently added" \
    | python3 -c "import json,sys; print(json.load(sys.stdin).get('infraID',''))" 2>/dev/null || true)"
  if [ -n "${INFRA_ID}" ]; then
    log "  Resolved infraID: ${INFRA_ID}"
  else
    warn "  Could not read infraID from ~/cluster/metadata.json (it may not exist — e.g. a failed run that never reached 'create cluster')."
  fi
fi

CLUSTER_NAME_ANCHOR=""
if [ -n "${INFRA_ID}" ]; then
  CLUSTER_NAME_ANCHOR="^${INFRA_ID}-"
else
  warn "No exact infraID available — SKIPPING the forwarding-rule/backend-service/health-check/reserved-address sweep below to avoid any risk of deleting a DIFFERENT cluster's load-balancer resources in this shared project. If you know the infraID from a previous run (check its logs or the GCP console), re-run as: INFRA_ID=<cluster>-<id> ./clean-environment.sh ${CLUSTER_NAME}. Otherwise check the GCP console manually for leftovers named '${CLUSTER_NAME}-<id>-*'."
  TEARDOWN_FAILED=1
fi

# ---------------------------------------------------------------------------
# 2. Sweep any stale cluster-created resources (DNS, LB, health checks).
#    The DNS zone is matched on the cluster's exact domain (not a
#    substring), and the load-balancer resources on the exact infraID
#    resolved above — never a bare substring/guess — so this never touches
#    a similarly-prefixed but DIFFERENT cluster in the same shared project.
#    Still catches every past attempt's random cluster-ID suffix (djnbc,
#    q26nq, xpzpw...) as long as its infraID could be resolved above.
# ---------------------------------------------------------------------------
CLUSTER_DOMAIN="${CLUSTER_NAME}.${BASE_DOMAIN}"

log "Sweeping stale DNS zone for ${CLUSTER_DOMAIN}..."
run_list "DNS zones" gcloud dns managed-zones list --project="${PROJECT}" \
    --filter="dnsName=${CLUSTER_DOMAIN}." --format="value(name)"
for zone in ${LIST_RESULT}; do
  while read -r rec_name rec_type; do
    [ -n "${rec_name}" ] || continue
    gcloud dns record-sets delete "${rec_name}" --zone="${zone}" --type="${rec_type}" \
      --project="${PROJECT}" --quiet 2>/dev/null || true
  done < <(gcloud dns record-sets list --zone="${zone}" --project="${PROJECT}" \
      --format="value(name,type)" 2>/dev/null | grep -Ev "^\S+\s+(NS|SOA)$")
  try_delete "DNS zone: ${zone}" gcloud dns managed-zones delete "${zone}" --project="${PROJECT}" --quiet || true
done

if [ -n "${INFRA_ID}" ]; then
  log "Sweeping stale forwarding rules / backend services / health checks for infraID ${INFRA_ID}..."
  run_list "forwarding rules (regional)" gcloud compute forwarding-rules list --project="${PROJECT}" \
      --regions="${REGION}" --filter="name~${CLUSTER_NAME_ANCHOR}" --format="value(name)"
  for fr in ${LIST_RESULT}; do
    try_delete "forwarding rule: ${fr}" gcloud compute forwarding-rules delete "${fr}" \
      --region="${REGION}" --project="${PROJECT}" --quiet || true
  done
  run_list "backend services (regional)" gcloud compute backend-services list --project="${PROJECT}" \
      --regions="${REGION}" --filter="name~${CLUSTER_NAME_ANCHOR}" --format="value(name)"
  for bs in ${LIST_RESULT}; do
    try_delete "backend service: ${bs}" gcloud compute backend-services delete "${bs}" \
      --region="${REGION}" --project="${PROJECT}" --quiet || true
  done
  run_list "health checks (regional)" gcloud compute health-checks list --project="${PROJECT}" \
      --regions="${REGION}" --filter="name~${CLUSTER_NAME_ANCHOR}" --format="value(name)"
  for hc in ${LIST_RESULT}; do
    try_delete "health check: ${hc}" gcloud compute health-checks delete "${hc}" \
      --region="${REGION}" --project="${PROJECT}" --quiet || true
  done

  # GLOBAL variants too — install-config settings can put the cluster's LB
  # resources at global scope instead of regional. The regional-only sweep
  # above silently misses these (its `|| true` only swallows delete errors
  # for resources it actually FOUND; it never even looks at global scope).
  run_list "forwarding rules (global)" gcloud compute forwarding-rules list --project="${PROJECT}" \
      --global --filter="name~${CLUSTER_NAME_ANCHOR}" --format="value(name)"
  for fr in ${LIST_RESULT}; do
    try_delete "forwarding rule: ${fr}" gcloud compute forwarding-rules delete "${fr}" \
      --global --project="${PROJECT}" --quiet || true
  done
  run_list "backend services (global)" gcloud compute backend-services list --project="${PROJECT}" \
      --global --filter="name~${CLUSTER_NAME_ANCHOR}" --format="value(name)"
  for bs in ${LIST_RESULT}; do
    try_delete "backend service: ${bs}" gcloud compute backend-services delete "${bs}" \
      --global --project="${PROJECT}" --quiet || true
  done
  run_list "health checks (global)" gcloud compute health-checks list --project="${PROJECT}" \
      --global --filter="name~${CLUSTER_NAME_ANCHOR}" --format="value(name)"
  for hc in ${LIST_RESULT}; do
    try_delete "health check: ${hc}" gcloud compute health-checks delete "${hc}" \
      --global --project="${PROJECT}" --quiet || true
  done

  log "Sweeping stale reserved internal addresses (e.g. ${INFRA_ID}-api-internal)..."
  run_list "reserved addresses" gcloud compute addresses list --project="${PROJECT}" \
      --filter="name~${CLUSTER_NAME_ANCHOR}" --format="value(name)"
  for addr in ${LIST_RESULT}; do
    try_delete "reserved address: ${addr}" gcloud compute addresses delete "${addr}" \
      --region="${REGION}" --project="${PROJECT}" --quiet || true
  done
fi

# ---------------------------------------------------------------------------
# 3. Delete the bastion VM.
# ---------------------------------------------------------------------------
if [ -n "${BASTION_ZONE}" ]; then
  log "Deleting bastion VM ${BASTION_NAME}..."
  gcloud compute instances delete "${BASTION_NAME}" --zone="${BASTION_ZONE}" \
    --project="${PROJECT}" --quiet
else
  log "No bastion VM to delete."
fi

# ---------------------------------------------------------------------------
# 4. Delete any Cloud NAT + Router on this VPC.
#    `network~/${VPC_NAME}$` anchors the match to the END of the network's
#    resource URL, requiring the FULL VPC name (not a bare substring), so a
#    VPC named "${VPC_NAME}2" can never match here — same anchoring applied
#    to the firewall and subnet sweeps below.
# ---------------------------------------------------------------------------
log "Deleting Cloud NAT + Router on ${VPC_NAME}..."
for router in $(gcloud compute routers list --project="${PROJECT}" \
    --filter="network~/${VPC_NAME}\$" --format="value(name)" 2>/dev/null); do
  for nat in $(gcloud compute routers nats list --router="${router}" --region="${REGION}" \
      --project="${PROJECT}" --format="value(name)" 2>/dev/null); do
    gcloud compute routers nats delete "${nat}" --router="${router}" --region="${REGION}" \
      --project="${PROJECT}" --quiet 2>/dev/null || true
    log "  Deleted NAT: ${nat}"
  done
  gcloud compute routers delete "${router}" --region="${REGION}" \
    --project="${PROJECT}" --quiet 2>/dev/null || true
  log "  Deleted router: ${router}"
done

# ---------------------------------------------------------------------------
# 5. Delete firewall rules on this VPC.
# ---------------------------------------------------------------------------
log "Deleting firewall rules on ${VPC_NAME}..."
for fw in $(gcloud compute firewall-rules list --project="${PROJECT}" \
    --filter="network~/${VPC_NAME}\$" --format="value(name)" 2>/dev/null); do
  gcloud compute firewall-rules delete "${fw}" --project="${PROJECT}" --quiet 2>/dev/null || true
  log "  Deleted firewall rule: ${fw}"
done

# ---------------------------------------------------------------------------
# 6. Delete subnets on this VPC.
# ---------------------------------------------------------------------------
log "Deleting subnets on ${VPC_NAME}..."
for subnet in $(gcloud compute networks subnets list --project="${PROJECT}" \
    --filter="network~/${VPC_NAME}\$" --format="value(name)" 2>/dev/null); do
  if retry_delete "subnet ${subnet}" gcloud compute networks subnets delete "${subnet}" \
      --region="${REGION}" --project="${PROJECT}" --quiet; then
    log "  Deleted subnet: ${subnet}"
  else
    TEARDOWN_FAILED=1
  fi
done

# ---------------------------------------------------------------------------
# 7. Delete the VPC itself. Retried with backoff — GCP can briefly report
#    the network as "not ready" right after its last subnet is removed.
# ---------------------------------------------------------------------------
if gcloud compute networks describe "${VPC_NAME}" --project="${PROJECT}" >/dev/null 2>&1; then
  log "Deleting VPC ${VPC_NAME}..."
  if retry_delete "VPC ${VPC_NAME}" gcloud compute networks delete "${VPC_NAME}" --project="${PROJECT}" --quiet; then
    log "  Deleted VPC: ${VPC_NAME}"
  else
    TEARDOWN_FAILED=1
  fi
else
  log "VPC ${VPC_NAME} already gone."
fi

# ---------------------------------------------------------------------------
# 8. Remove local per-user config — but ONLY if nothing above reported a
#    real failure. If a resource might still be lingering (destroy cluster
#    failed, or a subnet/VPC delete gave up after retries), keep config.env
#    so a re-run of this script (or bastion-internet.sh) can still target
#    the right VPC/bastion names instead of falling back to the wizard.
# ---------------------------------------------------------------------------
if [ "${TEARDOWN_FAILED}" -eq 0 ]; then
  if [ -f "${CONFIG_FILE}" ]; then
    rm -f "${CONFIG_FILE}"
    log "Removed local ${CONFIG_FILE} — next run of install-disconnected-ocp.sh will show the first-time wizard."
  fi
else
  warn "Keeping local ${CONFIG_FILE} because one or more deletions above failed/gave up — see [WARN] lines above."
fi

echo ""
if [ "${TEARDOWN_FAILED}" -eq 0 ]; then
  log "Environment for cluster '${CLUSTER_NAME}' in project '${PROJECT}' has been fully torn down."
  log "You can now run ./install-disconnected-ocp.sh <version>"
else
  warn "Teardown for cluster '${CLUSTER_NAME}' in project '${PROJECT}' completed WITH FAILURES — some resources may still exist."
  warn "Re-run ./clean-environment.sh ${CLUSTER_NAME} to retry, or check the GCP console for leftovers."
  exit 1
fi
