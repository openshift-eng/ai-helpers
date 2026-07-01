# Node RPM Plugin

RPM package management for OpenShift Node team components. Part of the [node-team](../node-team/) plugin family.

## Installation

```bash
/plugin install node-rpm@ai-helpers
```

Requires the `node-team` plugin (installed automatically as a dependency).

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

1. Checks VPN connectivity to Red Hat internal systems
2. Validates prerequisites (locally or inside a Vagrant VM with `--vagrant`)
3. Clones the dist-git repo and checks out the correct release branch
4. Updates the spec file with the new upstream version and commit hash
5. Downloads sources, declares new sources, bumps the changelog
6. Commits, pushes, and kicks off a Brew build (or scratch build with `--scratch`)
7. Prints a summary with build URL and next steps

**Arguments:**
- `<package>`: Package name (required, e.g. "cri-tools")
- `<new-version>`: Target upstream version (required, e.g. "1.36.0")
- `--ocp-version <version>`: Target OCP version (prompted if omitted)
- `--scratch`: Run a scratch build instead of a full build
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
