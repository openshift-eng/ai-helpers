#!/usr/bin/env bash
set -euo pipefail

UPSTREAM="${UPSTREAM:-https://api.openshift.com/api/upgrades_info/graph}"
ARCH="${ARCH:-amd64}"

usage() {
  cat >&2 <<EOF
Usage: $(basename "$0") <version> [--channel <channel>] [--arch <arch>] [--to <target-version>]

Query Cincinnati for available upgrade paths from a given OCP version.

Examples:
  $(basename "$0") 4.16.3
  $(basename "$0") 4.16.3 --channel fast-4.17
  $(basename "$0") 4.16.3 --channel stable-4.17 --to 4.17.8
  $(basename "$0") 4.16.3 --arch arm64

Arguments:
  version              Source OCP version (e.g., 4.16.3)
  --channel <channel>  Graph channel (default: stable-<minor> derived from version)
  --arch <arch>        Cluster architecture (default: amd64)
  --to <target>        Filter results to show only a specific target version
EOF
  exit 1
}

die() { echo "Error: $*" >&2; exit 1; }
info() { echo "$*" >&2; }

[[ $# -lt 1 ]] && usage

VERSION="$1"
shift

CHANNEL=""
TARGET=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --channel) [[ $# -lt 2 ]] && die "--channel requires an argument"; CHANNEL="$2"; shift 2 ;;
    --arch) [[ $# -lt 2 ]] && die "--arch requires an argument"; ARCH="$2"; shift 2 ;;
    --to) [[ $# -lt 2 ]] && die "--to requires an argument"; TARGET="$2"; shift 2 ;;
    *) usage ;;
  esac
done

[[ "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || die "version must be like 4.16.3, got: $VERSION"

if [[ -z "$CHANNEL" ]]; then
  MINOR="${VERSION%.*}"
  CHANNEL="stable-${MINOR}"
fi

for cmd in curl jq; do
  command -v "$cmd" &>/dev/null || die "$cmd is required but not found"
done

OUTPUT=$(mktemp)
trap 'rm -f "$OUTPUT"' EXIT

info "Querying Cincinnati: channel=${CHANNEL} arch=${ARCH} from=${VERSION}"

if ! curl --silent --location --fail --header 'Accept:application/json' \
  "${UPSTREAM}?channel=${CHANNEL}&arch=${ARCH}" -o "$OUTPUT"; then
  die "Failed to fetch graph from ${UPSTREAM} (channel=${CHANNEL})"
fi

NODE_COUNT=$(jq '.nodes | length' "$OUTPUT")
EDGE_COUNT=$(jq '.edges | length' "$OUTPUT")
info "Graph: ${NODE_COUNT} nodes, ${EDGE_COUNT} edges"

SOURCE_EXISTS=$(jq -r --arg v "$VERSION" '[.nodes[] | select(.version == $v)] | length' "$OUTPUT")
if [[ "$SOURCE_EXISTS" -eq 0 ]]; then
  echo "Version ${VERSION} not found in channel ${CHANNEL}"
  echo ""
  echo "Available versions in ${CHANNEL}:"
  jq -r '[.nodes[].version] | sort_by(split(".") | map(tonumber))[]' "$OUTPUT" | tail -10
  exit 1
fi

if [[ -n "$TARGET" ]]; then
  RESULT=$(jq -r --arg src "$VERSION" --arg tgt "$TARGET" '
    (.nodes | to_entries | map({key: (.key | tostring), value: .value}) | from_entries) as $idx |
    [.edges[] |
      select($idx[(.[0] | tostring)].version == $src) |
      select($idx[(.[1] | tostring)].version == $tgt) |
      $idx[(.[1] | tostring)]
    ] | if length > 0 then
      .[0] | "REACHABLE: " + .version + "\t" + .payload + "\t" + (.metadata.url // "-")
    else
      "NOT REACHABLE: No direct upgrade path from " + $src + " to " + $tgt + " in channel " + "'"${CHANNEL}"'"
    end
  ' "$OUTPUT")
  echo "$RESULT"
else
  echo "Available upgrades from ${VERSION} in ${CHANNEL}:"
  echo ""
  jq -r --arg src "$VERSION" '
    (.nodes | to_entries | map({key: (.key | tostring), value: .value}) | from_entries) as $idx |
    [.edges[] |
      select($idx[(.[0] | tostring)].version == $src)[1] |
      tostring | $idx[.]
    ] | sort_by(.version | split(".") | map(tonumber))[] |
    .version + "\t" + .payload + "\t" + (.metadata.url // "-")
  ' "$OUTPUT"
fi

TOTAL=$(jq -r --arg src "$VERSION" '
  (.nodes | to_entries | map({key: (.key | tostring), value: .value}) | from_entries) as $idx |
  [.edges[] | select($idx[(.[0] | tostring)].version == $src)] | length
' "$OUTPUT")
info ""
info "Total: ${TOTAL} available upgrade(s) from ${VERSION}"
info "Graph visualizer: https://ctron.github.io/openshift-update-graph#${CHANNEL}"
