#!/usr/bin/env bash
#
# ============================================================================
# lib-bastion-net.sh
#
# Shared helpers for finding the disconnected-OCP bastion (and its VPC's
# Cloud Router/NAT), and for granting/revoking the bastion's temporary
# internet access. Sourced by bastion-internet.sh, clean-environment.sh, and
# install-disconnected-ocp.sh, so a fix to this logic only has to land once.
#
# This file is NOT meant to be executed directly — it only defines
# functions/globals for the caller to use after sourcing it.
#
# Callers must already have these defined before sourcing:
#   PROJECT, REGION, VPC_NAME, BASTION_NAME   — required by find_bastion_zone/find_router
#   ROUTER_NAME, NAT_NAME                     — additionally required by
#                                                bastion_internet_on/off/status
#   log(), warn(), die()
# ============================================================================

find_bastion_zone() {
  # Restricted to instances actually on OUR VPC (anchored, not substring) —
  # GCE instance names only need to be unique per ZONE, not per project, so
  # a same-named instance for a completely different environment could
  # otherwise be found in another zone. If more than one still matches,
  # refuse to guess which one is "ours" rather than silently picking the
  # first (via `head -1`).
  local zones count
  zones=$(gcloud compute instances list --project="${PROJECT}" \
    --filter="name=${BASTION_NAME} AND networkInterfaces.network~/${VPC_NAME}\$" \
    --format="value(zone.basename())")
  count=$(echo "${zones}" | grep -c . || true)
  if [ "${count}" -gt 1 ]; then
    die "Multiple '${BASTION_NAME}' instances found on ${VPC_NAME} across zones (${zones//$'\n'/, }) — this should never happen; investigate manually before continuing."
  fi
  echo "${zones}"
}

find_router() {
  # Anchored to the END of the network's resource URL — requires the FULL
  # VPC name, not a substring — so e.g. VPC_NAME "team-dc-vpc" can never
  # also match a router that actually belongs to "other-team-dc-vpc" in the
  # same shared project.
  gcloud compute routers list --project="${PROJECT}" \
    --filter="region:( ${REGION} ) AND network~/${VPC_NAME}\$" --format="value(name)" | head -1
}

find_nat() {
  local router="$1"
  [ -n "${router}" ] || return 0
  # Filtered to OUR NAT_NAME specifically — a router can carry other NATs
  # for unrelated purposes; grabbing the first NAT found on the router
  # could return (and then mutate/delete) someone else's NAT.
  gcloud compute routers nats list --router="${router}" --region="${REGION}" \
    --project="${PROJECT}" --filter="name=${NAT_NAME}" --format="value(name)" | head -1
}

# Grants BASTION_NAME temporary internet access via Cloud NAT, scoped ONLY
# to the subnet the bastion's NIC is actually attached to (discovered at
# runtime, never assumed). Requires BASTION_ZONE to already be set by the
# caller (e.g. via find_bastion_zone).
#
# On return, sets — in the CALLER's shell, intentionally not `local` —
# ROUTER_NAME_ACTIVE, NAT_NAME_ACTIVE, and NAT_MANAGED_BY_SCRIPT=1 (set
# whether the NAT was freshly created OR just re-scoped, since either way
# THIS invocation is now the one responsible for tearing it down again via
# bastion_internet_off).
ROUTER_NAME_ACTIVE=""
NAT_NAME_ACTIVE=""
NAT_MANAGED_BY_SCRIPT=0
bastion_internet_on() {
  local bastion_subnet
  bastion_subnet=$(gcloud compute instances describe "${BASTION_NAME}" \
    --zone="${BASTION_ZONE}" --project="${PROJECT}" \
    --format="value(networkInterfaces[0].subnetwork)" | sed 's#.*/##')
  [ -n "${bastion_subnet}" ] || die "Could not determine which subnet the bastion is actually attached to."
  log "Bastion NIC is attached to subnet: ${bastion_subnet} (discovered, not assumed)"

  ROUTER_NAME_ACTIVE="$(find_router)"
  if [ -z "${ROUTER_NAME_ACTIVE}" ]; then
    ROUTER_NAME_ACTIVE="${ROUTER_NAME}"
    log "No existing router for this VPC/region — creating ${ROUTER_NAME_ACTIVE}..."
    gcloud compute routers create "${ROUTER_NAME_ACTIVE}" \
      --project="${PROJECT}" --network="${VPC_NAME}" --region="${REGION}"
  else
    log "Found existing router: ${ROUTER_NAME_ACTIVE}"
  fi

  NAT_NAME_ACTIVE="$(find_nat "${ROUTER_NAME_ACTIVE}")"
  if [ -z "${NAT_NAME_ACTIVE}" ]; then
    NAT_NAME_ACTIVE="${NAT_NAME}"
    log "No existing ${NAT_NAME} — creating it, scoped ONLY to ${bastion_subnet}..."
    gcloud compute routers nats create "${NAT_NAME_ACTIVE}" --project="${PROJECT}" \
      --router="${ROUTER_NAME_ACTIVE}" --region="${REGION}" \
      --nat-custom-subnet-ip-ranges="${bastion_subnet}" \
      --auto-allocate-nat-external-ips
  else
    log "Found existing NAT ${NAT_NAME_ACTIVE} — re-scoping to ${bastion_subnet} only (never ALL_SUBNETWORKS)..."
    gcloud compute routers nats update "${NAT_NAME_ACTIVE}" --router="${ROUTER_NAME_ACTIVE}" \
      --region="${REGION}" --project="${PROJECT}" \
      --nat-custom-subnet-ip-ranges="${bastion_subnet}"
  fi
  NAT_MANAGED_BY_SCRIPT=1

  log "Waiting briefly for NAT to become active..."
  sleep 15
  log "Bastion now has internet access. Cluster nodes still do NOT."
}

# Revokes internet access, and removes the router too if it now serves no
# other purpose. Safe to call even if nothing was ever granted (finds
# nothing, does nothing, returns 0). Never calls exit/die itself, so it is
# safe to call from an EXIT trap.
bastion_internet_off() {
  local router
  router="$(find_router)"
  if [ -z "${router}" ]; then
    log "No router found — environment already has zero internet access anywhere."
    return 0
  fi

  local nat
  nat="$(find_nat "${router}")"
  if [ -n "${nat}" ]; then
    log "Deleting NAT ${nat}..."
    gcloud compute routers nats delete "${nat}" --router="${router}" \
      --region="${REGION}" --project="${PROJECT}" --quiet 2>/dev/null || true
  else
    log "No NAT named ${NAT_NAME} present on router ${router}."
  fi

  local remaining
  remaining=$(gcloud compute routers describe "${router}" --region="${REGION}" \
    --project="${PROJECT}" --format="value(nats,bgpPeers,interfaces)" 2>/dev/null || true)
  if [ -z "${remaining// /}" ]; then
    log "Router ${router} now has no other purpose — deleting it too..."
    gcloud compute routers delete "${router}" --region="${REGION}" \
      --project="${PROJECT}" --quiet 2>/dev/null || true
  else
    log "Router ${router} left in place (still serving something else)."
  fi

  # Deliberately scoped to what we actually verified: we only ever look for
  # (and remove) a NAT named ${NAT_NAME}. A DIFFERENT NAT covering some
  # other subnet in ${VPC_NAME} — one we never touched — could still exist,
  # so we don't claim the whole environment is disconnected here.
  log "Removed NAT ${NAT_NAME} (if it existed). Bastion no longer has internet access via it."
}

# Read-only: reports whether the bastion currently has internet access,
# without changing anything.
bastion_internet_status() {
  local router
  router="$(find_router)"
  if [ -z "${router}" ]; then
    log "No router/NAT present anywhere in ${VPC_NAME} — bastion has NO internet access."
    return 0
  fi
  local nat
  nat="$(find_nat "${router}")"
  if [ -z "${nat}" ]; then
    log "Router ${router} exists but no NAT named ${NAT_NAME} is attached — bastion has NO internet access."
    return 0
  fi

  log "Router: ${router}"
  log "NAT: ${nat}"
  gcloud compute routers nats describe "${nat}" --router="${router}" \
    --region="${REGION}" --project="${PROJECT}" \
    --format="table(sourceSubnetworkIpRangesToNat,natIpAllocateOption)"

  # A NAT named ${NAT_NAME} existing isn't proof the BASTION has internet —
  # it could be scoped to a different subnet (e.g. "on" was never re-run
  # after a change). Confirm the bastion's actual subnet is in the NAT's
  # configured ranges before claiming access.
  local nat_scope
  nat_scope=$(gcloud compute routers nats describe "${nat}" --router="${router}" \
    --region="${REGION}" --project="${PROJECT}" \
    --format="value(sourceSubnetworkIpRangesToNat)" 2>/dev/null)
  # NOT `|| true` here — find_bastion_zone's own die() (ambiguous multi-zone
  # match) only kills the subshell $(...) runs in; `|| true` would silently
  # swallow that exit and misreport "bastion not found" instead of the real
  # "investigate manually" condition. Propagate it.
  local bastion_zone
  bastion_zone="$(find_bastion_zone)" || die "Could not determine the bastion zone."
  if [ -z "${bastion_zone}" ]; then
    warn "Bastion ${BASTION_NAME} not found — cannot confirm the NAT actually covers it."
  elif [[ "${nat_scope}" == ALL_SUBNETWORKS_* ]]; then
    # Cloud NAT has TWO all-subnet modes: ALL_SUBNETWORKS_ALL_IP_RANGES and
    # ALL_SUBNETWORKS_ALL_PRIMARY_IP_RANGES. Checking only the first one
    # would make the primary-ranges mode fall through to the
    # subnetworks[].name check below (which is empty in this mode),
    # producing a false "NO internet access" reading.
    log "Bastion currently HAS internet access (NAT is scoped to ALL_SUBNETWORKS — broader than 'on' normally sets; consider re-running 'on' to narrow it back to just the bastion)."
  else
    local nat_subnets bastion_subnet
    nat_subnets=$(gcloud compute routers nats describe "${nat}" --router="${router}" \
      --region="${REGION}" --project="${PROJECT}" \
      --format="value(subnetworks[].name)" 2>/dev/null | tr ';' '\n' | sed 's#.*/##')
    bastion_subnet=$(gcloud compute instances describe "${BASTION_NAME}" \
      --zone="${bastion_zone}" --project="${PROJECT}" \
      --format="value(networkInterfaces[0].subnetwork)" | sed 's#.*/##')
    if echo "${nat_subnets}" | grep -qx "${bastion_subnet}"; then
      log "Bastion currently HAS internet access (NAT covers its subnet: ${bastion_subnet})."
    else
      log "NAT ${nat} exists but does NOT cover the bastion's subnet (${bastion_subnet}) — bastion has NO internet access. Run 'on' to fix."
    fi
  fi
}
