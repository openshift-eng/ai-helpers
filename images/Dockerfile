FROM registry.ci.openshift.org/ocp/builder:rhel-9-golang-1.25-openshift-4.22 AS claude-latest
COPY images/repos/claude-code-latest.repo /etc/yum.repos.d/
COPY images/repos/RPM-GPG-KEY-claude-code /etc/pki/rpm-gpg/
RUN rm /etc/yum.repos.d/ubi.repo && \
    dnf install -y --disablerepo='*-ppc64le' --disablerepo='*-s390x' claude-code && \
    dnf clean all

FROM registry.ci.openshift.org/ocp/builder:rhel-9-golang-1.25-openshift-4.22

# Copy external rpm repos into the image, and tell the ART wrapper to append them
ENV ART_DNF_WRAPPER_POLICY=append
RUN rm /etc/yum.repos.d/ubi.repo
COPY images/repos/*.repo /etc/yum.repos.d/
COPY images/repos/RPM-GPG-KEY-* /etc/pki/rpm-gpg/

# Install all system packages in a single dnf transaction to avoid repeated
# metadata fetches (~800MB each). Disable foreign-arch repos to prevent
# cross-architecture dependency resolution failures in CI.
RUN dnf install -y \
    --disablerepo='*-ppc64le' --disablerepo='*-s390x' \
    --disablerepo='claude-code-latest' \
    python3.11 \
    python3.11-pip \
    python3.11-devel \
    gh \
    claude-code \
    pcp \
    pcp-devel \
    pcp-export-pcp2json \
    && dnf clean all \
    && alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1 \
    && alternatives --set python3 /usr/bin/python3.11

# Copy the latest Claude Code binary from the builder stage
COPY --from=claude-latest /usr/bin/claude /usr/local/bin/claude-latest

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

# In CI, OpenShift uses a random UID, but in the root group
RUN chmod -R g+rwx /home/claude && \
  chmod -R g+rwx /opt/ai-helpers && \
  chmod -R g+rwx /workspace

ENV CLAUDE_CONFIG_DIR="/home/claude/.claude"

# Set Claude Code as the default command
ENTRYPOINT ["claude"]

# Default to showing help
CMD ["--help"]
