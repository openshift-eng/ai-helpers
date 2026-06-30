# RPM Packaging Workflow

Reference for RPM packaging workflows used by the OpenShift Node team.

## Packages

| Package | Upstream Org | Upstream Repo | Dist-git Branch Pattern | Spec Conventions |
|---------|-------------|--------------|------------------------|------------------|
| cri-tools | kubernetes-sigs | cri-tools | `rhaos-<version>-rhel-{8,9,10}` (most OCP versions have two RHEL branches; check which exist for the target version) | `commit0`, `Version`, `Release` |

> **Note:** Only cri-tools is currently supported. To add a new package, add a
> row to this table with its upstream org, repo, branch pattern, and spec
> conventions. The `/node-rpm:bump` command currently hardcodes the cri-tools
> workflow (commit0, v-prefixed tags, Release reset via sed). Adding a package
> with different conventions (e.g. `1.git%{shortcommit0}%{?dist}` Release
> format, no tag prefix, or different tarball naming) will require updating
> bump.md to read the Spec Conventions column and adapt accordingly.

## Workflow Steps

1. **Clone the dist-git repo:**
   ```bash
   rhpkg clone <package>
   cd <package>
   git checkout <release-branch>
   ```

2. **Update the spec file:**
   - Set `%global commit0` to the upstream tag's full commit SHA
   - Set `Version:` to the new upstream version
   - Save the file before proceeding (spectool reads macros from it)

3. **Clean old sources and download new ones:**
   ```bash
   rm -f <package>-*.tar.gz
   spectool -g <package>.spec
   ```

4. **Declare new sources in dist-git:**
   ```bash
   rhpkg new-sources <package>-*.tar.gz
   ```

5. **Reset Release and bump the changelog:**
   ```bash
   sed -i 's/^Release:.*/Release: 0%{?dist}/' <package>.spec
   rpmdev-bumpspec -c "Bump to v<new-version>" <package>.spec
   ```

6. **Commit and push:**
   ```bash
   git commit -asm "Bump to v<new-version>"
   git push
   ```

7. **Start the build:**
   ```bash
   rhpkg build
   ```

## Scratch Builds

Use scratch builds to test changes before committing to a full build.

Standard approach (works on public release branches):

```bash
rhpkg build --scratch --srpm
```

For private branches where `rhpkg build --scratch` may not work, use the
two-step approach:

```bash
rhpkg srpm
brew build --scratch <branch>-candidate <package>-<version>-<release>.src.rpm
```

Scratch builds do not produce official builds in Brew. They are disposable
and useful for verifying spec changes compile correctly.

## cri-tools Upstream Release Checklist

1. Vendor the final RC of Kubernetes into `kubernetes-sigs/cri-tools`
2. Create a GitHub release (tag `v<version>`)
3. Ask the Kubernetes Release Manager to run OBS stage and release
4. Update the cri-tools version in `kubernetes-sigs/cri-tools`
5. Update the cri-tools version references in `kubernetes/kubernetes`
6. Update cri-tools in `cri-o/packaging`
7. Bump the downstream RPM for OpenShift (this is the `/node-rpm:bump` workflow)

## Prerequisites

- **VPN**: Connected to the Red Hat VPN
- **Kerberos auth**: `kinit user@IPA.REDHAT.COM` (verify with `klist`)
- **Tools installed**: `rhpkg`, `spectool`, `rpmdev-bumpspec`

## Environment Setup

A Fedora Vagrant VM (Fedora 42+) is the recommended environment for RPM
packaging. The vendored [`Vagrantfile`](Vagrantfile) is the source of truth for
provisioning: it installs Red Hat CA certs, RCM tools (rhpkg, spectool,
rpmdev-bumpspec, krb5-workstation), configures RPM macros, and sets up SSH
config for dist-git access (including bastion ProxyJump entries). For bare-metal
Fedora setups, refer to the Vagrantfile provisioning script for the exact steps.

## Vagrant Lifecycle

The `--vagrant` flag on `/node-rpm:bump` manages a Fedora VM automatically:

- **First run:** Copies the vendored Vagrantfile into `.work/node-rpm/` and
  runs `vagrant up`. Provisioning installs all tools
  (rhpkg, spectool, rpmdev-bumpspec, krb5-workstation) and configures SSH
  and RPM macros. This takes a few minutes on first boot.
- **Subsequent runs:** Detects the existing VM and reuses it. No re-provisioning.
- **Kerberos:** Tickets inside the VM expire independently. If `klist -s`
  fails, the command stops and asks you to authenticate. Open an interactive
  session to refresh:
  ```bash
  cd .work/node-rpm && vagrant ssh
  # inside the VM:
  kinit user@IPA.REDHAT.COM
  exit
  ```
- **Cleanup:** The VM persists between runs. To remove it:
  ```bash
  cd .work/node-rpm && vagrant destroy -f
  ```
