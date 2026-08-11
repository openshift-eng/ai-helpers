#!/bin/bash
# Gate companion: feature-gates — k8s client-go feature gate wiring check.
# Discovers gates already wired in source (wiring-first, not full vendor scan),
# then verifies vendor symbol presence and all 3 layer completeness.
# Repos with zero wiring SKIP immediately — no false-FAIL from unwired vendor gates.
# Usage: bash feature-gates.sh <repo-path>

source "$(dirname "$0")/../../scripts/gate-script-lib.sh"
init_gate "$@"

details=()

# PRIMARY_GOMOD discovery: sub-module repos (e.g. ovn-org/ovn-kubernetes) keep
# go.mod and vendor/ under a subdirectory (go-controller/), not the repo root.
# Find the go.mod that depends on k8s.io/client-go; scope all searches there.
PRIMARY_GOMOD_DIR="."
if ! grep -q 'k8s.io/client-go' "$REPO/go.mod" 2>/dev/null; then
  found_mod=""
  while IFS= read -r gomod; do
    if grep -q 'k8s.io/client-go' "$gomod" 2>/dev/null; then
      found_mod="$gomod"
      break
    fi
  done < <(find . -maxdepth 3 -name 'go.mod' \
    -not -path '*/vendor/*' -not -path '*/.claude/*' 2>/dev/null | LC_ALL=C sort)
  [[ -n "$found_mod" ]] && PRIMARY_GOMOD_DIR=$(dirname "${found_mod}")
fi

# Locate known_features.go early — needed for Layer 3 raw-key filtering below.
known_features=$(find "$PRIMARY_GOMOD_DIR" \
  -path '*/vendor/k8s.io/*/features/known_features.go' \
  -not -path '*/.claude/*' 2>/dev/null | head -1)

# WIRING-FIRST GATE DISCOVERY: union of 3 layers.
# Use --exclude-dir instead of post-hoc grep -v to correctly exclude vendor/
# paths (grep -h suppresses filenames so grep -v '/vendor/' would filter gate
# text, not file paths — a silent bug when -h is combined with -r).
# Only gates with existing wiring are checked — vendor gates with no source refs
# were intentionally not wired by the autofix.

# Layer 1: KUBE_FEATURE_ in shell scripts and Makefiles
wired_l1=$(grep -rohE 'KUBE_FEATURE_[A-Za-z0-9_]+' "$PRIMARY_GOMOD_DIR/" \
  --include='*.sh' --include='Makefile*' \
  --exclude-dir=vendor --exclude-dir='.claude' 2>/dev/null \
  | sed 's/KUBE_FEATURE_//' | LC_ALL=C sort -u || true)

# Layer 2: KUBE_FEATURE_ in Go source (os.Setenv, t.Setenv, string literals)
wired_l2=$(grep -rohE 'KUBE_FEATURE_[A-Za-z0-9_]+' "$PRIMARY_GOMOD_DIR/" \
  --include='*.go' \
  --exclude-dir=vendor --exclude-dir='.claude' 2>/dev/null \
  | sed 's/KUBE_FEATURE_//' | LC_ALL=C sort -u || true)

# Layer 3: gate names from SetFromMap calls.
# Handles both constant form string(features.Gate) and raw string keys "Gate": bool.
# Raw string keys are filtered against known_features.go to avoid false positives
# from non-gate map keys that happen to start with an uppercase letter.
sfm_files=$(grep -rlE 'SetFromMap' "$PRIMARY_GOMOD_DIR/" \
  --include='*.go' \
  --exclude-dir=vendor --exclude-dir='.claude' 2>/dev/null || true)
wired_l3=""
if [[ -n "$sfm_files" ]]; then
  # Constant form: string(features.WatchListClient) → WatchListClient
  from_const=$(while IFS= read -r f; do
    [[ -z "$f" ]] && continue
    grep -Eo 'string\(features\.[A-Za-z0-9]+\)' "$f" 2>/dev/null \
      | grep -oE '[A-Z][A-Za-z0-9]+' || true
  done <<< "$sfm_files")
  # Raw string key form: "WatchListClient": false → WatchListClient
  # Filter against known_features.go so non-gate uppercase map keys are excluded.
  from_raw=""
  if [[ -n "$known_features" ]]; then
    from_raw=$(while IFS= read -r f; do
      [[ -z "$f" ]] && continue
      grep -Eo '"[A-Z][A-Za-z0-9]+"' "$f" 2>/dev/null | tr -d '"' || true
    done <<< "$sfm_files" \
    | while IFS= read -r name; do
        grep -q "\"${name}\"" "$known_features" 2>/dev/null && echo "$name" || true
      done)
  fi
  wired_l3=$(printf '%s\n%s\n' "$from_const" "$from_raw" \
    | grep -v '^$' | LC_ALL=C sort -u || true)
fi

all_wired=$(printf '%s\n%s\n%s\n' "$wired_l1" "$wired_l2" "$wired_l3" \
  | grep -v '^$' | LC_ALL=C sort -u || true)

if [[ -z "$all_wired" ]]; then
  finish_evidence "SKIP: no feature gate wiring in repo" \
    "SKIP: no KUBE_FEATURE_ refs or SetFromMap gate names found outside vendor"
fi

details+=("WIRED_GATES: $(tr '\n' ' ' <<< "$all_wired" | sed 's/ $//')")

# Locate hack/test-go.sh (layer 1 canonical location)
test_go_sh=$(find "$PRIMARY_GOMOD_DIR" -name 'test-go.sh' \
  -path '*/hack/*' -not -path '*/vendor/*' -not -path '*/.claude/*' \
  2>/dev/null | head -1)

# Locate layer 2 files (os.Setenv/t.Setenv with KUBE_FEATURE_)
setenv_files=$(grep -rln 'os\.Setenv.*KUBE_FEATURE\|t\.Setenv.*KUBE_FEATURE' \
  "$PRIMARY_GOMOD_DIR/" --include='*_test.go' 2>/dev/null \
  | grep -v '/vendor/' | grep -v '/.claude/' || true)

# Per-gate checks
while IFS= read -r gate; do
  # Vendor symbol presence — gate must exist in vendored known_features.go
  if [[ -n "$known_features" ]]; then
    if ! grep -q "\"${gate}\"" "$known_features" 2>/dev/null; then
      if [[ -n "$BASE" ]] && ! git grep -q "\"${gate}\"" "$BASE" -- 'vendor/k8s.io/' 2>/dev/null; then
        details+=("VENDOR_MISSING_PREEXISTING: $gate absent from current and base vendor — pre-existing, not a regression")
      else
        details+=("VENDOR_MISSING: $gate not in vendor/k8s.io/*/features/known_features.go")
        inc NEW_ISSUES
      fi
    fi
  else
    details+=("VENDOR_UNKNOWN: known_features.go absent — cannot verify $gate symbol")
  fi

  # Layer 1: KUBE_FEATURE_<gate> in hack/test-go.sh
  if [[ -n "$test_go_sh" ]]; then
    if ! grep -q "KUBE_FEATURE_${gate}" "$test_go_sh" 2>/dev/null; then
      details+=("LAYER1_MISSING: KUBE_FEATURE_${gate} absent from ${test_go_sh#"$PRIMARY_GOMOD_DIR/"}")
      inc NEW_ISSUES
    fi
  else
    details+=("LAYER1_SKIP: no hack/test-go.sh — layer 1 not checked for $gate")
  fi

  # Layer 2: KUBE_FEATURE_<gate> in each os.Setenv/t.Setenv file.
  # INFO only — a test file that sets one gate for a focused test legitimately
  # omits all others; subagent inspects intent before treating absences as fixes.
  while IFS= read -r f; do
    [[ -z "$f" ]] && continue
    if ! grep -q "KUBE_FEATURE_${gate}" "$f" 2>/dev/null; then
      details+=("LAYER2_MISSING: KUBE_FEATURE_${gate} absent from ${f#"$PRIMARY_GOMOD_DIR/"}")
    fi
  done <<< "$setenv_files"

  # Layer 3: gate name in each SetFromMap file
  while IFS= read -r f; do
    [[ -z "$f" ]] && continue
    if ! grep -qE "\"${gate}\"|features\.${gate}" "$f" 2>/dev/null; then
      details+=("LAYER3_MISSING: $gate absent from SetFromMap in ${f#"$PRIMARY_GOMOD_DIR/"}")
      inc NEW_ISSUES
    fi
  done <<< "$sfm_files"

done <<< "$all_wired"

# Layer 4: Ginkgo suite files with RegisterFailHandler but no SetFromMap.
# k8s 1.35+ pkg/features.init() overrides DefaultMutableFeatureGate and can
# defeat env-var-based gate disables. SetFromMap in suite setup is belt-and-suspenders.
# Emitted as INFO only — subagent picks which suites to fix based on known-good.
_suite_missing=()
  while IFS= read -r _sf; do
    grep -q 'RegisterFailHandler' "$_sf" 2>/dev/null || continue
    grep -q 'SetFromMap' "$_sf" 2>/dev/null && continue
    _suite_missing+=("${_sf#"$PRIMARY_GOMOD_DIR/"}")
  done < <(find "$PRIMARY_GOMOD_DIR" -name '*_suite_test.go' \
    -not -path '*/vendor/*' -not -path '*/.claude/*' 2>/dev/null)
  if [[ ${#_suite_missing[@]} -gt 0 ]]; then
    details+=("SUITE_NO_SETFROMMAP (${#_suite_missing[@]} files): ${_suite_missing[*]}")
  fi

# Sudo/export check: new KUBE_FEATURE_*=false export in rebase-touched scripts
# with bare sudo (env not preserved) would silently drop the gate variable.
if [[ -n "$BASE" ]]; then
  while IFS= read -r script; do
    [[ -z "$script" ]] && continue
    git diff "$BASE"..HEAD -- "$script" 2>/dev/null \
      | grep -q '^\+.*export KUBE_FEATURE_.*=false' || continue
    if grep -q 'sudo ' "$script" 2>/dev/null && \
       ! grep -qE 'sudo -E|sudo --preserve-env' "$script" 2>/dev/null; then
      details+=("SUDO_FAIL: $script exports KUBE_FEATURE_*=false but has bare sudo (env dropped)")
      inc NEW_ISSUES
    fi
  done < <(git diff --name-only "$BASE"..HEAD -- '*.sh' 'Makefile*' 2>/dev/null)
fi

details+=("NEW_ISSUES=$NEW_ISSUES")
finish_evidence "$NEW_ISSUES feature gate coverage gap(s)" "${details[@]}"
