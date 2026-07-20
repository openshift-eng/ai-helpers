---
description: Bump a downstream RPM package to a new upstream version
argument-hint: "<package> <new-version> [--ocp-version <version>] [--scratch] [--vagrant]"
---

## Name
node-rpm:bump

## Synopsis
```text
/node-rpm:bump <package> <new-version> [--ocp-version <version>] [--scratch] [--vagrant]
```

## Description

Guides the user through bumping a downstream RPM package to a new upstream version in Red Hat's dist-git. Handles spec file updates, source downloads, changelog bumps, and Brew builds.

The workflow follows the established pattern for Node team RPM packages (cri-tools as the primary template). Each phase presents its changes to the user for review before proceeding.

When `--vagrant` is passed, the entire workflow runs inside a Fedora Vagrant VM that is automatically provisioned with all required tools. This is the recommended approach when rhpkg and related tools are not installed locally.

## Implementation

### Phase 0: Setup and Argument Parsing

1. **Parse required arguments:**
   - `<package>` (required): The package name, e.g. `cri-tools`. Must exist in the Packages table in [`../references/rpm-workflow.md`](../references/rpm-workflow.md). If not found, list supported packages and stop.
   - `<new-version>` (required): The target upstream version, e.g. `1.36.0`

2. **Parse optional arguments:**
   - `--ocp-version <version>`: Target OCP version. If omitted, prompt the user to specify one.
   - `--scratch`: Run a scratch build instead of a full build.
   - `--vagrant`: Run the workflow inside a Vagrant VM.

3. **Check VPN connectivity:**
   ```bash
   curl -s --connect-timeout 5 http://download.devel.redhat.com > /dev/null 2>&1 || echo "UNREACHABLE"
   ```
   If unreachable, warn the user to connect to the Red Hat VPN and stop.

4. **Validate prerequisites:**

   **Without `--vagrant` (local execution):**
   ```bash
   which rhpkg 2>/dev/null || echo "MISSING: rhpkg"
   which spectool 2>/dev/null || echo "MISSING: spectool"
   which rpmdev-bumpspec 2>/dev/null || echo "MISSING: rpmdev-bumpspec"
   klist -s 2>/dev/null || echo "MISSING: valid Kerberos ticket (run kinit)"
   ```
   If any tool is missing, print installation instructions and stop.

   **With `--vagrant`:**
   - Verify `vagrant` is installed locally.
   - Verify libvirt is available (`virsh --version`).
   - Create the work directory: `mkdir -p .work/node-rpm`
   - If `.work/node-rpm/Vagrantfile` does not exist, copy it from the vendored reference:
     ```bash
     cp "${CLAUDE_PLUGIN_ROOT}/references/Vagrantfile" .work/node-rpm/Vagrantfile
     ```
   - Check if the VM is already running:
     ```bash
     cd .work/node-rpm && vagrant status --machine-readable | grep ",state," | grep -q "running"
     ```
     If not running, provision and start it:
     ```bash
     cd .work/node-rpm && vagrant up
     ```
   - Verify VPN connectivity from inside the VM (NAT may not inherit host routes with split-tunnel VPN):
     ```bash
     cd .work/node-rpm && vagrant ssh -c "curl -s --connect-timeout 5 http://download.devel.redhat.com > /dev/null 2>&1" || echo "VM cannot reach Red Hat network"
     ```
     If unreachable, warn about potential split-tunnel or DNS issues and stop.
   - Validate prerequisites inside the VM:
     ```bash
     cd .work/node-rpm && vagrant ssh -c "which rhpkg && which spectool && which rpmdev-bumpspec"
     ```
   - Check Kerberos ticket inside the VM:
     ```bash
     cd .work/node-rpm && vagrant ssh -c "klist -s 2>/dev/null" || echo "MISSING: valid Kerberos ticket"
     ```
     If no valid ticket, tell the user to authenticate interactively:
     ```bash
     cd .work/node-rpm && vagrant ssh
     # inside the VM:
     kinit <user>@IPA.REDHAT.COM
     exit
     ```
     Then re-run the command. `kinit` requires interactive password input that does not work through `vagrant ssh -c`.
   - Check git user config inside the VM:
     ```bash
     cd .work/node-rpm && vagrant ssh -c "git config user.name && git config user.email" 2>/dev/null
     ```
     If not set, tell the user to configure them interactively:
     ```bash
     cd .work/node-rpm && vagrant ssh
     # inside the VM:
     git config --global user.name "Your Name"
     git config --global user.email "you@redhat.com"
     exit
     ```

5. **Resolve the dist-git branch:**
   - Look up the package in [`../references/rpm-workflow.md`](../references/rpm-workflow.md) for the branch pattern and RHEL version cutoff. The branch comes from `--ocp-version` plus the Dist-git Branch Pattern column (e.g. `rhaos-<version>-rhel-{8,9,10}`).
   - For cri-tools: branches follow `rhaos-<version>-rhel-{8,9,10}`. Most OCP versions have two RHEL branches (e.g. RHEL 9 + RHEL 10 for OCP 5.0). Check which branches exist for the target version and repeat Phases 1-3 for each branch.

---

### Execution Mode

All shell commands in Phases 1-3 run differently depending on `--vagrant`:

- **Local (default):** Commands run directly in the shell.
- **Vagrant:** Commands are prefixed with `cd .work/node-rpm && vagrant ssh -c "cd <package> && ..."`. Each `vagrant ssh -c` invocation opens a fresh session in `/home/vagrant`, so every command after the initial clone must include the `cd <package>` prefix. The dist-git clone and build happen inside the VM. Output is captured and shown to the user as normal.
- **Exception:** `git ls-remote` against public GitHub repos (Phase 2 step 1) always runs locally, since it does not require Red Hat internal access.

---

### Phase 1: Clone and Checkout

1. **Create work directory** (local mode only; Vagrant mode already created this in Phase 0):
   ```bash
   mkdir -p .work/node-rpm
   ```

2. **Clone the dist-git repo:**
   ```bash
   cd .work/node-rpm
   ```
   Check if `<package>` already exists (from a prior interrupted run). In vagrant mode, check inside the VM: `cd .work/node-rpm && vagrant ssh -c "test -d <package>"`. In local mode, check `.work/node-rpm/<package>`. If it exists, offer to reuse it (`cd <package> && git fetch && git checkout <branch> && git reset --hard origin/<branch>`) or remove it (`rm -rf <package>`) before proceeding.
   ```bash
   rhpkg clone <package>
   cd <package>
   git checkout <branch>
   ```
   With `--vagrant`, this runs inside the VM. The clone lives in the VM's filesystem.

3. **Read the current spec file** and extract:
   - Current `Version:` value
   - Current `Release:` value
   - Current `%global commit0` value (the upstream commit hash)

4. **Display current state** to the user:
   - Package name, current version, current commit hash, branch name

---

### Phase 2: Update Spec File

1. **Get the upstream commit for the new version:**
   Look up the upstream org and repo from the Packages table in [`../references/rpm-workflow.md`](../references/rpm-workflow.md) (e.g. `kubernetes-sigs` / `cri-tools`).
   ```bash
   git ls-remote https://github.com/<upstream-org>/<upstream-repo> "v<new-version>" "v<new-version>^{}" | tail -1 | cut -f1
   ```
   The `^{}` suffix dereferences annotated tags to the underlying commit SHA. For lightweight tags, only the first pattern matches. `tail -1` picks the dereferenced line when both are present.

   Verify the result is a non-empty 40-character hex SHA. If empty, the tag does not exist upstream; stop with a clear error (e.g. "Tag v<new-version> not found in <upstream-org>/<upstream-repo>").

2. **Update the spec file:**
   - Set `%global commit0` to the new upstream commit SHA
   - Set `Version:` to `<new-version>`
   - Save the spec file to disk before proceeding (spectool reads macros from it).

3. **Clean old sources and download new ones:**
   ```bash
   rm -f <package>-*.tar.gz
   spectool -g <package>.spec
   ```

4. **Declare new sources:**
   ```bash
   rhpkg new-sources <package>-*.tar.gz
   ```

5. **Reset Release and bump the changelog:**
   First, reset Release in the spec file for the new Version:
   ```bash
   sed -i 's/^Release:.*/Release: 0%{?dist}/' <package>.spec
   ```
   Then bump the changelog (this also increments Release from 0 to 1):
   ```bash
   rpmdev-bumpspec -c "Bump to v<new-version>" <package>.spec
   ```
   The result is `Release: 1%{?dist}` with a new changelog entry.

6. **Show the full diff** to the user and wait for confirmation before proceeding:
   ```bash
   git diff
   ```

---

### Phase 3: Build

1. **Commit the changes:**
   ```bash
   git commit -asm "Bump to v<new-version>"
   ```

2. **Push** (confirm with the user first):
   ```bash
   git push
   ```

3. **Start the build:**
   - Full build: `rhpkg build`
   - Scratch build (if `--scratch`): `rhpkg build --scratch --srpm`
   - If `rhpkg build --scratch` fails on a private branch, fall back to the two-step approach: `rhpkg srpm` (capture the exact SRPM filename from its output), then `brew build --scratch <branch>-candidate <srpm-file>`

4. **Report the build task URL** from the rhpkg output.

---

### Phase 4: Summary

Print a summary table:
- Package name
- Old version (from Phase 1)
- New version
- Dist-git branch
- Build status and task URL

List next steps:
- Verify the build in Brew
- Update cri-tools version in `kubernetes/kubernetes` (if applicable)
- Update cri-tools in `cri-o/packaging` (if applicable)
- Open a PR or notify the team

## Return Value

Prints a structured summary to stdout including old version, new version, branch, and build URL. Exit status reflects the build outcome.

## Examples

### Bump cri-tools for OCP 5.0
```text
/node-rpm:bump cri-tools 1.36.0 --ocp-version 5.0
```
Clones cri-tools from dist-git, checks out the matching release branch, updates the spec to version 1.36.0, and starts a full Brew build.

### Scratch build to test changes
```text
/node-rpm:bump cri-tools 1.36.0 --ocp-version 5.0 --scratch
```
Same workflow but runs `rhpkg build --scratch --srpm` instead of a full build. Useful for validating spec changes before committing.

### Bump using a Vagrant VM
```text
/node-rpm:bump cri-tools 1.36.0 --ocp-version 5.0 --vagrant
```
Provisions a Fedora VM (if not already running), runs the entire workflow inside it, and reports the build URL.

### Bump with version prompt
```text
/node-rpm:bump cri-tools 1.36.0
```
Omits `--ocp-version`, so the command prompts the user to select the target OCP version.

## Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `<package>` | Yes | Package name (e.g. `cri-tools`) |
| `<new-version>` | Yes | Target upstream version (e.g. `1.36.0`) |
| `--ocp-version <version>` | No | Target OCP version; prompted if omitted |
| `--scratch` | No | Run a scratch build instead of a full build |
| `--vagrant` | No | Run the workflow inside a Vagrant VM |

## Notes

- The upstream repo and dist-git branch pattern for each package are defined in [`../references/rpm-workflow.md`](../references/rpm-workflow.md).
- VPN connection to the Red Hat network is required. The command checks connectivity before starting.
- Kerberos tickets expire; run `kinit` before starting if your ticket is stale. With `--vagrant`, open an interactive session (`cd .work/node-rpm && vagrant ssh`) and run `kinit` inside the VM.
- Scratch builds do not produce official Brew builds. They are disposable test builds.
- The command operates in `.work/node-rpm/` to keep dist-git clones and the Vagrant VM separate from other work directories.
- The Vagrant VM persists between runs. Run `cd .work/node-rpm && vagrant destroy` to clean up.
