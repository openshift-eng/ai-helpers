FROM registry.ci.openshift.org/ocp/builder:rhel-9-golang-1.25-openshift-4.22 AS claude-latest
ENV ART_DNF_WRAPPER_POLICY=append
COPY images/repos/claude-code-latest.repo /etc/yum.repos.d/
COPY images/repos/RPM-GPG-KEY-claude-code /etc/pki/rpm-gpg/
RUN rm -f /etc/yum.repos.d/ubi.repo && \
    dnf install -y --disablerepo='*-ppc64le' --disablerepo='*-s390x' --disablerepo='claude-code' --enablerepo='claude-code-latest' claude-code && \
    dnf clean all

FROM registry.ci.openshift.org/ocp/builder:rhel-9-golang-1.25-openshift-4.22

# Copy external rpm repos into the image, and tell the ART wrapper to append them
ENV ART_DNF_WRAPPER_POLICY=append
RUN rm -f /etc/yum.repos.d/ubi.repo
COPY images/repos/*.repo /etc/yum.repos.d/
COPY images/repos/RPM-GPG-KEY-* /etc/pki/rpm-gpg/

# Install all system packages in a single dnf transaction to avoid repeated
# metadata fetches (~800MB each). Disable foreign-arch repos to prevent
# cross-architecture dependency resolution failures in CI.
RUN dnf install -y \
    --disablerepo='*-ppc64le' --disablerepo='*-s390x' \
    python3.11 \
    python3.11-pip \
    python3.11-devel \
    gh \
    google-cloud-cli \
    claude-code \
    pcp \
    pcp-devel \
    pcp-export-pcp2json \
    && dnf clean all \
    && alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1 \
    && alternatives --set python3 /usr/bin/python3.11

# The "latest" channel binary lets users try newer features not yet in stable,
# or compare behavior between versions, without disrupting the default entrypoint.
COPY --from=claude-latest /usr/bin/claude /usr/local/bin/claude-latest

# Install the complete Codex CLI package, including its code-mode host and sandbox tools.
ARG CODEX_VERSION=0.149.0
ARG CODEX_SHA256_AMD64=1c08ba262820b78d49ea7a93f326b6b430b72e5fe46830e433edef12e5123244
ARG CODEX_SHA256_ARM64=dac03e4db966e94f7083b9eb9f95d8b40da9d568fd2fdbb6885b0ea7d5b0d97f
RUN case "$(uname -m)" in \
      x86_64) CODEX_ARCH=x86_64; CODEX_SHA256="${CODEX_SHA256_AMD64}" ;; \
      aarch64) CODEX_ARCH=aarch64; CODEX_SHA256="${CODEX_SHA256_ARM64}" ;; \
      *) echo "Unsupported architecture: $(uname -m)" >&2; exit 1 ;; \
    esac \
    && curl -fsSL "https://github.com/openai/codex/releases/download/rust-v${CODEX_VERSION}/codex-package-${CODEX_ARCH}-unknown-linux-musl.tar.gz" \
    -o /tmp/codex.tar.gz \
    && echo "${CODEX_SHA256}  /tmp/codex.tar.gz" | sha256sum -c - \
    && mkdir -p /opt/codex \
    && tar -xzf /tmp/codex.tar.gz -C /opt/codex \
    && rm /tmp/codex.tar.gz
COPY images/codex-wrapper.sh /usr/local/bin/codex
RUN chmod 0755 /usr/local/bin/codex
ENV PATH="/usr/local/bin:/opt/codex/bin:/opt/codex/codex-path:${PATH}"

# Install Python tools and PCP bindings
RUN python3 -m pip install --no-cache-dir \
    agentic-ci \
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

# Configure Codex from the same local marketplace and default plugin set as Claude Code.
ENV CODEX_HOME="/home/claude/.codex"
RUN mkdir -p "${CODEX_HOME}" \
    && codex plugin marketplace add /opt/ai-helpers \
    && codex plugin add hello-world@ai-helpers \
    && codex plugin add jira@ai-helpers \
    && codex plugin add ci@ai-helpers \
    && chown -R claude:root "${CODEX_HOME}"

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
