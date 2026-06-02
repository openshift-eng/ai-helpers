FROM registry.ci.openshift.org/ocp/builder:rhel-9-golang-1.25-openshift-4.22

# Install all system packages in a single dnf transaction to avoid repeated
# metadata fetches (~800MB each). Disable foreign-arch repos to prevent
# cross-architecture dependency resolution failures in CI.
RUN dnf install -y \
    --disablerepo='*-ppc64le' --disablerepo='*-s390x' --disablerepo='*-aarch64' \
    'dnf-command(config-manager)' \
    && dnf config-manager --add-repo https://cli.github.com/packages/rpm/gh-cli.repo \
    --disablerepo='*-ppc64le' --disablerepo='*-s390x' --disablerepo='*-aarch64' \
    && dnf install -y \
    --disablerepo='*-ppc64le' --disablerepo='*-s390x' --disablerepo='*-aarch64' \
    python3.11 \
    python3.11-pip \
    python3.11-devel \
    gh \
    pcp \
    pcp-devel \
    pcp-export-pcp2json \
    && dnf clean all \
    && alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1 \
    && alternatives --set python3 /usr/bin/python3.11

# Install Python tools and PCP bindings
RUN python3 -m pip install --no-cache-dir \
    pytest \
    requests \
    pyyaml \
    && python3 -m pip install --no-cache-dir --use-pep517 pcp

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

# Install Claude Code CLI using the official installation script
RUN curl -fsSL https://claude.ai/install.sh | bash

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
