# Node RPM Plugin

RPM package management for OpenShift Node team components.

Part of the [node-team plugin family](../node-team/).

## Installation

```bash
/plugin install node-rpm@ai-helpers
```

Requires the `node-team` plugin (installed automatically as a dependency). Its shared `version-map.md` and `components.md` are used to check that the target version matches the OCP release and the upstream repo.

## Command

### `/node-rpm:bump <package> <new-version> [--ocp-version <version>] [--scratch] [--vagrant]`

Bump a downstream RPM package to a new upstream version.

**Examples:**
```text
/node-rpm:bump cri-tools 1.36.0 --ocp-version 5.0
/node-rpm:bump cri-tools 1.36.0 --ocp-version 5.0 --vagrant
/node-rpm:bump cri-tools 1.36.0 --ocp-version 5.0 --scratch
```

**What it does:**

1. Checks the target version against the OCP release (node-team version map) and VPN connectivity
2. Validates prerequisites (locally or inside a Vagrant VM with `--vagrant`)
3. Clones the dist-git repo, lists the release branches that exist, and checks out the selected one
4. Updates the spec file with the new upstream version and commit hash, bumps the changelog, downloads sources
5. Shows the diff and waits for confirmation before anything leaves the machine
6. With `--scratch`: builds a scratch SRPM from the working tree (no source upload, commit or push). Otherwise: declares new sources, commits, then asks before pushing and again before the Brew build
7. Prints a summary with build URL and next steps

**Arguments:**
- `<package>`: Package name (required, e.g. "cri-tools")
- `<new-version>`: Target upstream version (required, e.g. "1.36.0")
- `--ocp-version <version>`: Target OCP version (prompted if omitted)
- `--scratch`: Run a scratch build from the working tree; nothing is uploaded, committed or pushed
- `--vagrant`: Run the workflow inside a Vagrant VM (auto-provisions if needed)

## Prerequisites

**Local execution (default):**
- `rhpkg` (Red Hat package tool)
- `spectool` / `rpmdev-bumpspec` (from `rpmdevtools`)
- `krb5-workstation` for Kerberos authentication (`kinit user@IPA.REDHAT.COM`)
- VPN access to Red Hat internal systems

**With `--vagrant`:**
- `vagrant` and libvirt (`virsh`)
- VPN access to Red Hat internal systems
- All other tools are installed automatically inside the VM

See the [rpm-workflow reference](references/rpm-workflow.md) for full environment setup. A [vendored Vagrantfile](references/Vagrantfile) is included for the `--vagrant` flag.
