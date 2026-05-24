FROM registry.ci.openshift.org/ocp/builder:rhel-9-golang-1.25-openshift-4.22

# Install Python 3.11 (required for agent-eval-harness and modern type syntax)
RUN dnf install -y \
    python3.11 \
    python3.11-pip \
    python3.11-devel \
    && dnf clean all \
    && alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1 \
    && alternatives --set python3 /usr/bin/python3.11

# Install common Python tools
RUN python3 -m pip install --no-cache-dir \
    pytest \
    requests \
    pyyaml

# Install GitHub CLI
RUN dnf install -y 'dnf-command(config-manager)' \
    && dnf config-manager --add-repo https://cli.github.com/packages/rpm/gh-cli.repo \
    && dnf install -y gh \
    && dnf clean all

# Install PCP tools
RUN dnf install -y \
    pcp \
    pcp-export-pcp2json \
    && dnf clean all

# Create claude user with root group for OpenShift compatibility
RUN useradd -m -u 1000 -g 0 -s /bin/bash claude

# Copy ai-helpers repository to /opt/ai-helpers
COPY . /opt/ai-helpers
RUN chown -R claude:root /opt/ai-helpers

# Create Claude configuration directory and copy settings
#   Note: We pre-configure known_marketplaces.json because extraKnownMarketplaces doesn't seem to work in non-interactive mode.
RUN mkdir -p /home/claude/.claude/plugins
COPY images/claude-settings.json /home/claude/.claude/settings.json
COPY images/known_marketplaces.json /home/claude/.claude/plugins/known_marketplaces.json
RUN chown -R claude:root /home/claude

# Create workspace directory
RUN mkdir -p /workspace && chown -R claude:root /workspace
WORKDIR /workspace

# Switch to claude user
USER claude

# Install Claude Code CLI with GPG signature and SHA-256 verification.
# See: https://code.claude.com/docs/en/setup#binary-integrity-and-code-signing
ARG CLAUDE_CODE_VERSION=2.1.150
RUN set -eux; \
    REPO="https://downloads.claude.ai/claude-code-releases"; \
    KEYURL="https://downloads.claude.ai/keys/claude-code.asc"; \
    EXPECTED_FPR="31DDDE24DDFAB679F42D7BD2BAA929FF1A7ECACE"; \
    \
    curl -fsSL "$KEYURL" | gpg --import; \
    FPR=$(gpg --fingerprint --with-colons security@anthropic.com \
          | awk -F: '/^fpr:/{print $10; exit}'); \
    [ "$FPR" = "$EXPECTED_FPR" ]; \
    \
    curl -fsSL -o manifest.json     "$REPO/$CLAUDE_CODE_VERSION/manifest.json"; \
    curl -fsSL -o manifest.json.sig "$REPO/$CLAUDE_CODE_VERSION/manifest.json.sig"; \
    gpg --verify manifest.json.sig manifest.json; \
    \
    ARCH=$(uname -m); \
    case "$ARCH" in \
      x86_64)  PLATFORM="linux-x64" ;; \
      aarch64) PLATFORM="linux-arm64" ;; \
      *)       echo "Unsupported architecture: $ARCH" >&2; exit 1 ;; \
    esac; \
    EXPECTED_SHA=$(python3 -c "import json; print(json.load(open('manifest.json'))['platforms']['$PLATFORM']['checksum'])"); \
    \
    curl -fsSL -o claude "$REPO/$CLAUDE_CODE_VERSION/$PLATFORM/claude"; \
    ACTUAL_SHA=$(sha256sum claude | cut -d' ' -f1); \
    [ "$ACTUAL_SHA" = "$EXPECTED_SHA" ]; \
    \
    chmod +x claude; \
    mkdir -p /home/claude/.local/bin; \
    mv claude /home/claude/.local/bin/claude; \
    rm -f manifest.json manifest.json.sig

# In CI, OpenShift uses a random UID, but in the root group
RUN chmod -R g+rwx /home/claude && \
  chmod -R g+rwx /opt/ai-helpers && \
  chmod -R g+rwx /workspace

# Ensure ~/.local/bin is in PATH for the entrypoint
ENV PATH="/home/claude/.local/bin:${PATH}"
ENV CLAUDE_CONFIG_DIR="/home/claude/.claude"

# Set Claude Code as the default command
ENTRYPOINT ["claude"]

# Default to showing help
CMD ["--help"]
