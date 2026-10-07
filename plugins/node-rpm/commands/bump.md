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

The workflow follows the established pattern for Node team RPM packages (cri-tools as the primary template). Each phase presents its changes to the user for review before proceeding. Nothing leaves the machine before the user has reviewed the diff: the lookaside upload (`rhpkg new-sources`), the push and the full Brew build each need an explicit confirmation. With `--scratch` nothing is uploaded to the lookaside cache, committed or pushed.

When `--vagrant` is passed, the entire workflow runs inside a Fedora Vagrant VM that is automatically provisioned with all required tools. This is the recommended approach when rhpkg and related tools are not installed locally.

## Implementation

### Phase 0: Setup and Argument Parsing

1. **Parse required arguments:**
   - `<package>` (required): The package name, e.g. `cri-tools`. Must exist in the Packages table in [`../references/rpm-workflow.md`](../references/rpm-workflow.md). If not found, list supported packages and stop.
   - `<new-version>` (required): The target upstream version, e.g. `1.36.0`

2. **Parse optional arguments:**
   - `--ocp-version <version>`: Target OCP version. If omitted, prompt the user to specify one.
   - `--scratch`: Run a scratch build from the local working tree instead of a full build. Does not upload sources, commit or push.
   - `--vagrant`: Run the workflow inside a Vagrant VM.

3. **Sanity-check the version against the OCP release** using the `node-team` shared data (declared plugin dependency):
   - Read [shared/version-map.md](../../node-team/skills/node/references/shared/version-map.md) and compute the Kubernetes minor for `--ocp-version` with the formula given there. For packages that follow Kubernetes versioning (cri-tools), the minor of `<new-version>` must equal that Kubernetes minor, for example cri-tools `1.36.x` for OCP 5.0 (K8s 1.36). On a mismatch, show both numbers and ask the user whether to continue. Do not continue silently.
   - If [shared/components.md](../../node-team/skills/node/references/shared/components.md) has a `pscomponent:<package>` row, its upstream repo must match the Upstream Repo in the Packages table of `rpm-workflow.md`. On a mismatch, stop and ask the user which one is right.
   - Locating shared data: the links above are relative to a repo checkout. When the plugin is installed, read the files from `"${CLAUDE_PLUGIN_ROOT}"/../../node-team/*/skills/node/references/shared/` (glob the version directory), or invoke the `node-team:node` skill and read from its base directory. If the files cannot be found, say so, skip this check, and ask the user to confirm the version pairing.

4. **Check VPN connectivity:**
   ```bash
   curl -s --connect-timeout 5 http://download.devel.redhat.com > /dev/null 2>&1 || echo "UNREACHABLE"
   ```
   If unreachable, warn the user to connect to the Red Hat VPN and stop.

5. **Validate prerequisites:**

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
     If it exists but differs from the vendored file (`diff -q`), the VM was created from an older Vagrantfile (for example an end-of-life Fedora release). Tell the user and offer to recreate the VM (`vagrant destroy -f`, copy the new file, `vagrant up`). Do not destroy the VM without confirmation.
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

6. **Resolve the dist-git branch pattern:**
   - Look up the package in [`../references/rpm-workflow.md`](../references/rpm-workflow.md) for the branch pattern and RHEL version cutoff. The pattern comes from `--ocp-version` plus the Dist-git Branch Pattern column (e.g. `rhaos-<version>-rhel-{8,9,10}`).
   - Most OCP versions have two RHEL branches (e.g. RHEL 9 + RHEL 10 for OCP 5.0). Which ones exist is checked against the clone in Phase 1 step 3.

---

### Execution Mode

All shell commands in Phases 1-3 run differently depending on `--vagrant`:

- **Local (default):** Commands run directly in the shell, inside `.work/node-rpm/<package>`. Shell state does not persist between Bash tool calls, so each call starts with `cd .work/node-rpm/<package> && ...`.
- **Vagrant:** Commands are prefixed with `cd .work/node-rpm && vagrant ssh -c "cd <package> && ..."`. Each `vagrant ssh -c` invocation opens a fresh session in `/home/vagrant`, so every command after the initial clone must include the `cd <package>` prefix. The dist-git clone and build happen inside the VM. Output is captured and shown to the user as normal.
- **Spec file access in Vagrant mode:** the clone exists only inside the VM and no folder is synced to the host, so the Read and Edit tools cannot reach the spec. Read it with `vagrant ssh -c "cat <package>/<package>.spec"` and change it only with the `sed` and `rpmdev-bumpspec` commands given in Phase 2, run through `vagrant ssh -c`. Put the remote command in double quotes and keep the `sed` scripts in single quotes inside it, exactly as shown in Phase 2, so the host shell does not expand `%{?dist}` or `\1`.
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
   ```
   With `--vagrant`, this runs inside the VM. The clone lives in the VM's filesystem. Offer `rm -rf` or `git reset --hard` only after showing `git status --short` of the existing clone, since both discard local changes.

3. **Check which release branches exist** for the target version (run in the clone):
   ```bash
   git branch -r --list 'origin/rhaos-<ocp-version>-rhel-*'
   ```
   - No match: stop and report that no dist-git branch exists for that OCP version. List `git branch -r --list 'origin/rhaos-*'` so the user can pick a valid version.
   - One or more matches: show them and let the user confirm which to bump. Repeat Phases 1 (from step 4) to 3 for each selected branch.

4. **Check out the branch:**
   ```bash
   git checkout <branch>
   ```

5. **Read the current spec file** (`cat <package>.spec`, through `vagrant ssh -c` in Vagrant mode) and extract:
   - Current `Version:` value
   - Current `Release:` value
   - Current `%global commit0` value (the upstream commit hash)

6. **Display current state** to the user:
   - Package name, current version, current commit hash, branch name
   - If the current version already equals `<new-version>`, say so and ask whether to continue.

---

### Phase 2: Update Spec File

1. **Get the upstream commit for the new version:**
   Look up the upstream org and repo from the Packages table in [`../references/rpm-workflow.md`](../references/rpm-workflow.md) (e.g. `kubernetes-sigs` / `cri-tools`).
   ```bash
   git ls-remote https://github.com/<upstream-org>/<upstream-repo> "v<new-version>" "v<new-version>^{}" | tail -1 | cut -f1
   ```
   The `^{}` suffix dereferences annotated tags to the underlying commit SHA. For lightweight tags, only the first pattern matches. `tail -1` picks the dereferenced line when both are present.

   Verify the result is a non-empty 40-character hex SHA. If empty, the tag does not exist upstream; stop with a clear error (e.g. "Tag v<new-version> not found in <upstream-org>/<upstream-repo>").

2. **Update the spec file** with these commands (identical in local and Vagrant mode, so the edit is reproducible and works without host access to the file):
   ```bash
   sed -i -E 's/^(%global[[:space:]]+commit0[[:space:]]+).*/\1<commit-sha>/; s/^(Version:[[:space:]]+).*/\1<new-version>/' <package>.spec
   grep -E '^(%global[[:space:]]+commit0|Version:)' <package>.spec
   ```
   Verify that the `grep` output shows the new SHA and version. If a line did not change, the spec does not follow the conventions in the Packages table; stop and show the relevant lines to the user.

3. **Reset Release and bump the changelog:**
   First, reset Release in the spec file for the new Version:
   ```bash
   sed -i 's/^Release:.*/Release: 0%{?dist}/' <package>.spec
   ```
   Then bump the changelog (this also increments Release from 0 to 1):
   ```bash
   rpmdev-bumpspec -c "Bump to v<new-version>" <package>.spec
   ```
   The result is `Release: 1%{?dist}` with a new changelog entry.

4. **Clean old sources and download new ones** (local download only, nothing is uploaded yet):
   ```bash
   rm -f <package>-*.tar.gz
   spectool -g <package>.spec
   sha256sum <package>-*.tar.gz
   ```

5. **Review gate.** Show the user the full diff and the downloaded tarball name and checksum, then wait for confirmation:
   ```bash
   git diff
   ```
   State what happens next: with `--scratch`, a scratch build from the working tree (no upload, commit or push); otherwise an upload of the tarball to the dist-git lookaside cache, which cannot be undone. Do not continue without an explicit yes.

6. **Declare new sources** (full build only, skip with `--scratch`). This uploads the tarball to the lookaside cache and rewrites `sources` and `.gitignore`:
   ```bash
   rhpkg new-sources <package>-*.tar.gz
   git status --short
   ```

---

### Phase 3: Build

**With `--scratch`:** do not commit and do not push. Build the SRPM from the working tree and submit it:

1. `rhpkg build --scratch --srpm`
2. If that fails on a private branch, fall back to the two-step approach: `rhpkg srpm` (capture the exact SRPM filename from its output), then `brew build --scratch <branch>-candidate <srpm-file>`.
3. Report the build task URL. The working tree keeps the uncommitted changes, so after a successful scratch build the user can re-run the command without `--scratch` and choose to reuse the clone.

**Without `--scratch`:**

1. **Commit the changes:**
   ```bash
   git commit -asm "Bump to v<new-version>"
   git log -1 --stat
   ```

2. **Push.** Show the commit and the target (`origin/<branch>`), then ask for confirmation. Only after an explicit yes:
   ```bash
   git push
   ```
   If the user declines, stop here and leave the commit in the clone.

3. **Start the build.** A full build produces an official Brew build for the release branch. Ask for confirmation again, separately from the push. Only after an explicit yes:
   ```bash
   rhpkg build
   ```

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
- After a scratch build: re-run without `--scratch` for the official build
- Repeat for the remaining RHEL branches of the OCP version, if any
- Notify the team

The downstream bump is the last step of the upstream release checklist in [`../references/rpm-workflow.md`](../references/rpm-workflow.md). The `kubernetes/kubernetes` and `cri-o/packaging` updates come before it. Remind the user to confirm those are done; do not list them as follow-ups.

## Return Value

Prints a structured summary including old version, new version, branch, build type (scratch or full), build status and the Brew task URL. If the user declined a confirmation, the summary states at which step the workflow stopped and what was left in `.work/node-rpm/<package>`.

## Examples

### Bump cri-tools for OCP 5.0
```text
/node-rpm:bump cri-tools 1.36.0 --ocp-version 5.0
```
Clones cri-tools from dist-git, checks out the matching release branch, updates the spec to version 1.36.0, and, after the user confirms the diff, the push and the build, starts a full Brew build.

### Scratch build to test changes
```text
/node-rpm:bump cri-tools 1.36.0 --ocp-version 5.0 --scratch
```
Same spec changes, but builds with `rhpkg build --scratch --srpm` from the working tree. Nothing is uploaded to the lookaside cache, committed or pushed, so this validates spec changes before committing.

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
| `--scratch` | No | Run a scratch build from the working tree; no source upload, commit or push |
| `--vagrant` | No | Run the workflow inside a Vagrant VM |

## Notes

- The upstream repo and dist-git branch pattern for each package are defined in [`../references/rpm-workflow.md`](../references/rpm-workflow.md).
- VPN connection to the Red Hat network is required. The command checks connectivity before starting.
- Kerberos tickets expire; run `kinit` before starting if your ticket is stale. With `--vagrant`, open an interactive session (`cd .work/node-rpm && vagrant ssh`) and run `kinit` inside the VM.
- Scratch builds do not produce official Brew builds. They are disposable test builds.
- Outward-facing steps (lookaside upload, push, full build) each require an explicit confirmation. There is no flag to skip them.
- Version pairing is checked against the `node-team` plugin's `shared/version-map.md`.
- The command operates in `.work/node-rpm/` to keep dist-git clones and the Vagrant VM separate from other work directories.
- The Vagrant VM persists between runs. Run `cd .work/node-rpm && vagrant destroy` to clean up.
