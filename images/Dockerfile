FROM registry.ci.openshift.org/ocp/builder:rhel-9-golang-1.24-openshift-4.21

# Install Node.js and NPM from yum repositories
RUN dnf install -y nodejs npm \
    && dnf clean all

# Install Python 3 and development tools
RUN dnf install -y \
    python3 \
    python3-pip \
    python3-devel \
    && dnf clean all

# Install Claude Code CLI globally
RUN npm install -g @anthropic-ai/claude-code

# Install common Python tools
RUN pip3 install --no-cache-dir \
    pytest \
    requests \
    pyyaml

# Create claude user
RUN useradd -m -u 1000 -s /bin/bash claude

# Copy ai-helpers repository to /opt/ai-helpers
COPY . /opt/ai-helpers
RUN chown -R claude:claude /opt/ai-helpers

# Create Claude configuration directory and copy settings
#   Note: We pre-configure known_marketplaces.json because extraKnownMarketplaces doesn't seem to work in non-interactive mode.
RUN mkdir -p /home/claude/.claude/plugins
COPY images/claude-settings.json /home/claude/.claude/settings.json
COPY images/known_marketplaces.json /home/claude/.claude/plugins/known_marketplaces.json
RUN chown -R claude:claude /home/claude/.claude

# Create workspace directory
RUN mkdir -p /workspace && chown -R claude:claude /workspace
WORKDIR /workspace

# Switch to claude user
USER claude

# Set Claude Code as the default command
ENTRYPOINT ["claude"]

# Default to showing help
CMD ["--help"]
