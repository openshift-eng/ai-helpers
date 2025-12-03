# adapted from image/Dockerfile, with pnpm specific sections

FROM registry.access.redhat.com/ubi9/nodejs-22

# dnf requires superuser instead of uid 1001 coming from base image
USER 0

# Install Python 3 and development tools
RUN dnf install -y \
    python3 \
    python3-pip \
    python3-devel \
    && dnf clean all

# Install common Python tools
RUN pip3 install --no-cache-dir \
    pytest \
    requests \
    pyyaml

# Create claude user with 1002 uid
RUN useradd -m -u 1002 -s /bin/bash claude

# Copy ai-helpers repository to /opt/ai-helpers
COPY . /opt/ai-helpers
RUN chown -R claude:claude /opt/ai-helpers

# Create Claude configuration directory and copy settings
RUN mkdir -p /home/claude/.claude/plugins
COPY images/claude-settings.json /home/claude/.claude/settings.json
COPY images/known_marketplaces.json /home/claude/.claude/plugins/known_marketplaces.json
RUN chown -R claude:claude /home/claude/.claude
# RUN chown -R claude:claude /opt/app-root/

# Create workspace directory
RUN mkdir -p /workspace && chown -R claude:claude /workspace
WORKDIR /workspace

# Switch to claude user
USER claude

ENV HOME=/home/claude

# get pnpm
ENV PNPM_HOME=/home/claude/.local/share/pnpm
ENV PATH="$PNPM_HOME:$PATH"

RUN curl -fsSL https://get.pnpm.io/install.sh | bash -

# Install Claude Code CLI globally
RUN /home/claude/.local/share/pnpm/pnpm install -g @anthropic-ai/claude-code

ENTRYPOINT ["/home/claude/.local/share/pnpm/claude"]
