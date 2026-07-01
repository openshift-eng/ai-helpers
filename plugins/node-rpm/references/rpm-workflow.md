# RPM Packaging Workflow

Reference for RPM packaging workflows used by the OpenShift Node team.

## Packages

| Package | Upstream Org | Upstream Repo | Dist-git Branch Pattern | Spec Conventions |
|---------|-------------|--------------|------------------------|------------------|
| cri-tools | kubernetes-sigs | cri-tools | `rhaos-<version>-rhel-{8,9,10}` (most OCP versions have two RHEL branches; check which exist for the target version) | `commit0`, `Version`, `Release` |

> **Note:** Only cri-tools is currently supported. To add a new package, add a
> row to this table with its upstream org, repo, branch pattern, and spec
> conventions, then the `/node-rpm:bump` command will pick it up automatically.
> If the package uses a non-standard Release format (e.g.
> `1.git%{shortcommit0}%{?dist}`), document it in the Spec Conventions column
> so the Release reset step can adapt.

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
packaging. A vendored [`Vagrantfile`](Vagrantfile) is included with 6 GB RAM /
4 CPUs.

Key setup steps (also needed on bare-metal Fedora):

1. **Red Hat CA certs** (required for Brew and dist-git access):
   ```bash
   curl -fsSL -o /tmp/2022-IT-Root-CA.pem https://certs.corp.redhat.com/certs/2022-IT-Root-CA.pem
   cp /tmp/2022-IT-Root-CA.pem /etc/pki/ca-trust/source/anchors/
   update-ca-trust
   mkdir -p /etc/pki/brew
   cp /tmp/2022-IT-Root-CA.pem /etc/pki/brew/RH-IT-Root-CA.crt
   ```

2. **RCM tools repo** (provides `rhpkg`):
   ```bash
   curl -fsSL -o /etc/yum.repos.d/rcm-tools-fedora.repo \
     http://download.devel.redhat.com/rel-eng/internal/rcm-tools-fedora.repo
   dnf install -y chkconfig git java-headless krb5-workstation rhpkg rpmdevtools
   ```

3. **RPM macros** (`~/.rpmmacros`):
   ```text
   %_topdir %(echo $(pwd))
   %_sourcedir     %{_topdir}
   %_specdir       %{_sourcedir}
   %_rpmdir        %{_topdir}/RPMS
   %_srcrpmdir     %{_topdir}/SRPMS
   %_builddir      %{_topdir}/BUILD
   %_tmppath       %(echo ${TMPDIR:-/var/tmp})
   %_buildroot     %{_tmppath}/%{name}-%{version}-%{release}-root-%(%{__id_u} -n)
   ```

4. **SSH config for dist-git** (`~/.ssh/config`):
   ```text
   Host pkgs.devel.redhat.com pkgs-stage.devel.redhat.com
       ProxyJump                  iad2

   Host iad2
       Hostname                   bastion-iad2.corp.redhat.com
       ProxyJump                  none

   Host rdu2
       Hostname                   bastion-rdu2.corp.redhat.com
       ProxyJump                  none

   Host *.redhat.com
       GSSAPIAuthentication       yes
       GSSAPIDelegateCredentials  yes
   ```

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
