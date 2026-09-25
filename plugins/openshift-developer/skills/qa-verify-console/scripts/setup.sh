#!/usr/bin/env bash
# setup.sh — Phase 0 + 1 for qa-verify-console
#
# Validates inputs, logs into the cluster, clones openshift/console,
# fetches both branches, installs Chrome system libraries, installs
# Puppeteer, and creates evidence directories.
#
# Usage:
#   PR_NUMBER=17199 OC_LOGIN_CMD="oc login ..." bash setup.sh
#   # or:
#   OC_LOGIN_CMD="oc login ..." bash setup.sh 17199
#
# Outputs:
#   /workspace/evidence/metadata.json  — PR metadata
#   /workspace/console/               — cloned repo on base-branch
#   Prints LD_LIBRARY_PATH and CHROME_BIN to stdout for sourcing

set -euo pipefail

# ---------------------------------------------------------------------------
# Logging helpers
# ---------------------------------------------------------------------------
log()  { echo "[setup] $(date '+%H:%M:%S') $*"; }
warn() { echo "[setup] $(date '+%H:%M:%S') WARNING: $*" >&2; }
die()  { echo "[setup] $(date '+%H:%M:%S') ERROR: $*" >&2; exit 1; }

# ---------------------------------------------------------------------------
# Phase 0 — Validate Inputs
# ---------------------------------------------------------------------------
log "=== Phase 0: Validate Inputs ==="

# PR number: accept as $1 or $PR_NUMBER env var
PR_NUMBER="${1:-${PR_NUMBER:-}}"
if [[ -z "$PR_NUMBER" ]]; then
  die "Usage: PR_NUMBER=<number> OC_LOGIN_CMD=\"oc login ...\" bash setup.sh [PR_NUMBER]"
fi

if ! [[ "$PR_NUMBER" =~ ^[0-9]+$ ]]; then
  die "PR_NUMBER must be a positive integer, got: $PR_NUMBER"
fi

log "PR number: $PR_NUMBER"

# OC login command
if [[ -z "${OC_LOGIN_CMD:-}" ]]; then
  die "OC_LOGIN_CMD environment variable is required (e.g. 'oc login --token=... --server=...')"
fi

# --- Cluster login ---
log "Logging into cluster..."
eval "$OC_LOGIN_CMD"

CLUSTER_USER=$(oc whoami) || die "oc whoami failed — cluster login did not succeed"
CLUSTER_SERVER=$(oc whoami --show-server) || die "Cannot determine cluster server URL"
log "Logged in as: $CLUSTER_USER"
log "Cluster:      $CLUSTER_SERVER"

# --- PR metadata ---
log "Fetching PR #${PR_NUMBER} metadata..."
PR_JSON=$(gh pr view "$PR_NUMBER" --repo openshift/console \
  --json headRefName,baseRefName,title,author,number,url 2>&1) \
  || die "gh pr view failed — PR #${PR_NUMBER} not found or GH auth issue: $PR_JSON"

HEAD_REF=$(echo "$PR_JSON" | jq -r '.headRefName')
BASE_REF=$(echo "$PR_JSON" | jq -r '.baseRefName')
PR_TITLE=$(echo "$PR_JSON" | jq -r '.title')
PR_AUTHOR=$(echo "$PR_JSON" | jq -r '.author.login')
PR_URL=$(echo "$PR_JSON" | jq -r '.url')

log "PR title:  $PR_TITLE"
log "Author:    $PR_AUTHOR"
log "Head ref:  $HEAD_REF"
log "Base ref:  $BASE_REF"

# ---------------------------------------------------------------------------
# Phase 1 — Setup Environment
# ---------------------------------------------------------------------------
log "=== Phase 1: Setup Environment ==="

# --- Evidence directories ---
log "Creating evidence directories..."
mkdir -p /workspace/evidence/{baseline,candidate,flicker}

# Save metadata
cat > /workspace/evidence/metadata.json <<METADATA_EOF
{
  "pr_number": ${PR_NUMBER},
  "title": $(echo "$PR_TITLE" | jq -Rs .),
  "author": $(echo "$PR_AUTHOR" | jq -Rs .),
  "head_ref": $(echo "$HEAD_REF" | jq -Rs .),
  "base_ref": $(echo "$BASE_REF" | jq -Rs .),
  "url": $(echo "$PR_URL" | jq -Rs .),
  "cluster_user": $(echo "$CLUSTER_USER" | jq -Rs .),
  "cluster_server": $(echo "$CLUSTER_SERVER" | jq -Rs .),
  "setup_timestamp": "$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
}
METADATA_EOF
log "Metadata saved to /workspace/evidence/metadata.json"

# --- Clone console ---
if [[ -d /workspace/console/.git ]]; then
  log "Console repo already cloned at /workspace/console — reusing"
  cd /workspace/console
  git fetch origin
else
  log "Cloning openshift/console (full clone)..."
  git clone https://github.com/openshift/console.git /workspace/console
  cd /workspace/console
fi

# --- Fetch branches ---
log "Fetching PR branch (pull/${PR_NUMBER}/head)..."
git fetch origin "pull/${PR_NUMBER}/head:pr-branch" \
  || die "Failed to fetch PR branch — PR #${PR_NUMBER} may not exist"

log "Fetching base branch (${BASE_REF})..."
git fetch origin "${BASE_REF}:base-branch" \
  || die "Failed to fetch base branch '${BASE_REF}'"

# Check out base branch first (baseline capture happens before candidate)
log "Checking out base-branch for baseline capture..."
git checkout base-branch

log "Repo ready: base-branch checked out, pr-branch available"

# --- Chrome system libraries ---
# The workspace pod runs as non-root. Chrome needs ~15 system libraries
# that aren't installed. We download their RPMs and extract .so files
# to a local directory, then set LD_LIBRARY_PATH.
log "Installing Chrome system libraries via RPM extraction..."
CHROME_LIBS_DIR="/workspace/chrome-libs"
mkdir -p "$CHROME_LIBS_DIR"

ORIGINAL_DIR=$(pwd)
cd "$CHROME_LIBS_DIR"

# List of required library packages for Chrome
CHROME_LIB_PACKAGES=(
  nss
  nspr
  nss-util
  atk
  at-spi2-atk
  at-spi2-core
  libXcomposite
  libXdamage
  libXfixes
  libXrandr
  mesa-libgbm
  libxkbcommon
  alsa-lib
  cups-libs
  nss-softokn-freebl
)

# Download RPMs — continue even if some fail (Chrome may still work)
log "Downloading ${#CHROME_LIB_PACKAGES[@]} library RPMs..."
if command -v dnf &>/dev/null; then
  dnf download --destdir=. "${CHROME_LIB_PACKAGES[@]}" 2>&1 || warn "Some RPM downloads failed — Chrome may still work"
elif command -v yumdownloader &>/dev/null; then
  yumdownloader --destdir=. "${CHROME_LIB_PACKAGES[@]}" 2>&1 || warn "Some RPM downloads failed — Chrome may still work"
else
  warn "Neither dnf nor yumdownloader found — skipping Chrome library installation"
  warn "Chrome may fail to launch if system libraries are missing"
fi

# Extract all downloaded RPMs
RPM_COUNT=$(find . -maxdepth 1 -name '*.rpm' | wc -l)
if [[ "$RPM_COUNT" -gt 0 ]]; then
  log "Extracting $RPM_COUNT RPMs..."
  for rpm in *.rpm; do
    rpm2cpio "$rpm" | cpio -idmv 2>/dev/null || warn "Failed to extract $rpm"
  done
  log "Chrome libraries extracted to $CHROME_LIBS_DIR"
else
  warn "No RPMs downloaded — Chrome library installation skipped"
fi

cd "$ORIGINAL_DIR"

# Set LD_LIBRARY_PATH for Chrome
export LD_LIBRARY_PATH="${CHROME_LIBS_DIR}/usr/lib64:${LD_LIBRARY_PATH:-}"
log "LD_LIBRARY_PATH set: ${CHROME_LIBS_DIR}/usr/lib64"

# --- Install Puppeteer ---
log "Installing Puppeteer in frontend directory..."
cd /workspace/console/frontend

# Install puppeteer (adds Chrome download)
npm install puppeteer 2>&1 | tail -5
log "Puppeteer npm package installed"

# Install Chrome browser explicitly
log "Installing Chrome browser via Puppeteer..."
npx puppeteer browsers install chrome 2>&1 | tail -5

# Find the installed Chrome binary
# Puppeteer stores browsers under the cache directory
CHROME_BIN=""
for candidate in \
  "$HOME/.cache/puppeteer/chrome/"*/chrome-linux64/chrome \
  "$HOME/.cache/puppeteer/chrome/"*/chrome-linux/chrome \
  /workspace/console/frontend/node_modules/puppeteer/.local-chromium/*/chrome-linux64/chrome \
  /workspace/console/frontend/node_modules/puppeteer/.local-chromium/*/chrome-linux/chrome; do
  if [[ -x "$candidate" ]]; then
    CHROME_BIN="$candidate"
    break
  fi
done

if [[ -z "$CHROME_BIN" ]]; then
  # Try npx puppeteer to find it
  CHROME_BIN=$(node -e "
    try {
      const puppeteer = require('puppeteer');
      console.log(puppeteer.executablePath());
    } catch(e) {
      console.error(e.message);
      process.exit(1);
    }
  " 2>/dev/null) || true
fi

if [[ -n "$CHROME_BIN" && -x "$CHROME_BIN" ]]; then
  log "Chrome binary found: $CHROME_BIN"
else
  warn "Chrome binary not found — capture-screenshots.js will attempt auto-detection"
  CHROME_BIN=""
fi

cd "$ORIGINAL_DIR"

# ---------------------------------------------------------------------------
# Output environment for sourcing
# ---------------------------------------------------------------------------
log "=== Setup Complete ==="
log ""
log "Environment variables to export:"
log "  export LD_LIBRARY_PATH=\"${CHROME_LIBS_DIR}/usr/lib64:\${LD_LIBRARY_PATH:-}\""
if [[ -n "$CHROME_BIN" ]]; then
  log "  export CHROME_BIN=\"${CHROME_BIN}\""
fi
log ""
log "Next steps:"
log "  1. cd /workspace/console"
log "  2. ./build.sh                           # Build baseline (base branch)"
log "  3. export BRIDGE_USER_AUTH=\"disabled\""
log "  4. source ./contrib/oc-environment.sh    # Sets BRIDGE_K8S_AUTH_BEARER_TOKEN"
log "  5. ./bin/bridge -branding openshift &    # Start bridge"
log "  6. node scripts/capture-screenshots.js   # Capture baseline screenshots"

# Write env vars to a sourceable file so subsequent scripts can pick them up
cat > /workspace/evidence/setup-env.sh <<ENV_EOF
# Source this file to set up the environment for capture
export LD_LIBRARY_PATH="${CHROME_LIBS_DIR}/usr/lib64:\${LD_LIBRARY_PATH:-}"
export PR_NUMBER="${PR_NUMBER}"
export HEAD_REF="${HEAD_REF}"
export BASE_REF="${BASE_REF}"
ENV_EOF

if [[ -n "$CHROME_BIN" ]]; then
  echo "export CHROME_BIN=\"${CHROME_BIN}\"" >> /workspace/evidence/setup-env.sh
fi

log "Environment file written to /workspace/evidence/setup-env.sh"
log "Run: source /workspace/evidence/setup-env.sh"
