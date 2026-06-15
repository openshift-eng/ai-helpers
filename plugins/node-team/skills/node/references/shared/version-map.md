# OpenShift to Kubernetes/CRI-O Version Mapping

Canonical version mapping for all Node team plugins. Other plugins (e.g.
`node-cve`) reference this file instead of maintaining their own copies.

## Formula

For OCP 4.Y: `K8s/CRI-O minor = Y + 13` (e.g., OCP 4.18 ships K8s 1.31).

Apply the formula to derive branch names (see Branch Naming Conventions below).
For example, OCP 4.18: K8s minor = 18 + 13 = 31, so CRI-O branch is
`release-1.31` and MCO branch is `release-4.18`.

## OCP 5.x Formula

For OCP 5.Y: `K8s/CRI-O minor = Y + 36` (e.g., OCP 5.0 ships K8s 1.36,
OCP 5.1 ships K8s 1.37).

## Exceptions

OCP 4.23 and 5.0 share the same K8s/CRI-O base (1.36). This is the transition
point between the two formulas.

## Branch Naming Conventions

Repos using K8s-aligned versioning (`release-1.X`): openshift/cri-o,
openshift/kubernetes, openshift/cri-tools.

Repos using OCP-aligned versioning (`release-4.Y` or `release-5.Y`):
openshift/machine-config-operator, openshift/driver-toolkit,
openshift/google-cadvisor, openshift/conmon, openshift/conmon-rs,
openshift/kueue-operator, openshift/node-problem-detector,
openshift/instaslice-operator.
