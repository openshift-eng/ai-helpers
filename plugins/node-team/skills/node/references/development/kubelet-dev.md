# Kubelet (OpenShift): Non-Obvious Notes (Tribal Knowledge)

- **Upstream**: `https://github.com/kubernetes/kubernetes.git`
- **Downstream (OpenShift)**: `https://github.com/openshift/kubernetes.git`

For build commands, repo layout, and test targets — browse the repo directly (Makefile, README, go.mod, openshift-hack/).

## Carry Patch Conventions

OpenShift maintains patches on top of upstream kubernetes. Commits use these prefixes:

- `UPSTREAM: <carry>:` — OpenShift-specific patch, not intended for upstream
- `UPSTREAM: <merge>:` — merge commit from upstream rebase
- `UPSTREAM: 12345:` — cherry-pick of upstream PR #12345

These are in the `UPSTREAM/` directory and as commit prefixes in git history.

## OpenShift-Specific

- The kubelet binary ships inside the **`ose-hyperkube`** image in OCP.
- Kubelet configuration on RHCOS is rendered at `/etc/kubernetes/kubelet.conf`, managed by MCO. Customize via `KubeletConfig` CR, not by editing the file.
- For active development, work against `master` unless backporting a fix to `release-4.X`.
