# OpenShift Kueue Operator: Non-Obvious Notes (Tribal Knowledge)

- **Upstream Kueue**: `https://github.com/kubernetes-sigs/kueue.git`
- **Downstream Operator**: `https://github.com/openshift/kueue-operator.git`
- **Downstream operand fork**: `https://github.com/openshift/kubernetes-sigs-kueue.git`

For build commands, repo layout, CRD types, and test targets: browse the repo directly (Makefile, README, go.mod, api/).

## Architecture

The operator manages the lifecycle of upstream Kueue on OpenShift. It deploys into `openshift-kueue-operator` namespace and creates the upstream `kueue-controller-manager` in the `kueue-system` namespace.

When changes are needed in upstream Kueue itself, submit a PR to `kubernetes-sigs/kueue` first, then update the operator to consume the new version.

## OpenShift-Specific

- Built with operator-sdk framework (controller-runtime, controller-gen, OLM bundles).
- The operator is installed through OLM, not managed by the CVO. OLM reconciles
  the operator Deployment from its ClusterServiceVersion, so manual patches to
  the Deployment are reverted. For development, patch the CSV (or scale down
  the operator and run it locally) instead.
- The operator is released on its own cadence with `release-1.X` branches; it
  does not follow OCP `release-4.Y` branching.
