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

# Install Claude Code CLI via official RPM repository
RUN printf '%s\n' \
    '[claude-code]' \
    'name=Claude Code' \
    'baseurl=https://downloads.claude.ai/claude-code/rpm/stable' \
    'enabled=1' \
    'gpgcheck=1' \
    'gpgkey=https://downloads.claude.ai/keys/claude-code.asc' \
    > /etc/yum.repos.d/claude-code.repo && \
    dnf install -y claude-code && dnf clean all

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

# In CI, OpenShift uses a random UID, but in the root group
RUN chmod -R g+rwx /home/claude && \
  chmod -R g+rwx /opt/ai-helpers && \
  chmod -R g+rwx /workspace

ENV CLAUDE_CONFIG_DIR="/home/claude/.claude"

# Set Claude Code as the default command
ENTRYPOINT ["claude"]

# Default to showing help
CMD ["--help"]
