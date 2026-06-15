# OpenShift Kueue Operator: Non-Obvious Notes (Tribal Knowledge)

- **Upstream Kueue**: `https://github.com/kubernetes-sigs/kueue.git`
- **Downstream Operator**: `https://github.com/openshift/kueue-operator.git`

For build commands, repo layout, CRD types, and test targets — browse the repo directly (Makefile, README, go.mod, api/).

## Architecture

The operator manages the lifecycle of upstream Kueue on OpenShift. It deploys into `openshift-kueue-operator` namespace and creates the upstream `kueue-controller-manager` in the `kueue-system` namespace.

When changes are needed in upstream Kueue itself, submit a PR to `kubernetes-sigs/kueue` first, then update the operator to consume the new version.

## OpenShift-Specific

- Built with operator-sdk framework (controller-runtime, controller-gen, OLM bundles).
- CVO override warning applies here too — scale down CVO if patching the operator deployment manually during development.
