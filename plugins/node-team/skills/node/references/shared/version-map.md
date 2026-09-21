# OpenShift to Kubernetes/CRI-O Version Mapping

Canonical version mapping for all Node team plugins. Other plugins (e.g.
`node-cve`) reference this file instead of maintaining their own copies.

## Formula

For OCP 4.Y: `K8s/CRI-O minor = Y + 13` (e.g., OCP 4.18 ships K8s 1.31).

The formula gives the upstream version, not the downstream branch name. For
example, OCP 4.18: K8s minor = 18 + 13 = 31, so the upstream CRI-O branch is
`release-1.31`, while the downstream `openshift/cri-o` and MCO branches are
both `release-4.18`.

## OCP 5.x Formula

For OCP 5.Y: `K8s/CRI-O minor = Y + 36` (e.g., OCP 5.0 ships K8s 1.36,
OCP 5.1 ships K8s 1.37).

## Exceptions

OCP 4.23 and 5.0 share the same K8s/CRI-O base (1.36). This is the transition
point between the two formulas.

## Branch Naming Conventions

Downstream forks use OCP-aligned versioning (`release-4.Y` or `release-5.Y`):
openshift/cri-o, openshift/kubernetes, openshift/machine-config-operator,
openshift/driver-toolkit, openshift/node-problem-detector,
openshift/kubernetes-sigs-kueue, openshift/instaslice-operator (4.18 to 4.20
only).

Upstream repos use K8s-aligned versioning (`release-1.X`): cri-o/cri-o,
kubernetes/kubernetes. Use these only for upstream work or to look up which
upstream release a downstream branch is based on.

Special cases:

- openshift/kueue-operator follows the operator version (`release-1.X`), not
  the OCP version.
- cri-tools, conmon, conmon-rs, crun and cadvisor have no current downstream
  release branches. See the pscomponent table in
  [components.md](components.md) for which repo and ref to analyze.

Never hardcode a "latest" OCP version. Derive it from the newest `release-*`
branch that exists downstream:

```bash
git ls-remote --heads https://github.com/openshift/kubernetes 'release-[45].*' \
  | sed 's|.*refs/heads/release-||' | sort -V | tail -3
```

The newest branches are usually still in development; the newest GA version is
lower. The current GA release is the `Name:` line of the stable channel on the
public mirror (one directory per major version, where a major without a GA
release may mirror the previous one; take the highest):

```bash
for v in 4 5; do
  curl -s --max-time 15 "https://mirror.openshift.com/pub/openshift-v$v/clients/ocp/stable/release.txt" | sed -n 's/^Name: *//p'
done | sort -uV | tail -1
```

When the distinction matters (for example CVE tracker ownership) and the
mirror is not reachable, ask the user or pass the version explicitly.
