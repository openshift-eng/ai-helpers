# Guest cluster configuration

The hosted cluster config operator (HCCO,
`control-plane-operator/hostedclusterconfigoperator/`) runs in each hosted
cluster's control plane and continuously reconciles objects inside the guest
cluster (`controllers/resources/`): the ClusterVersion spec, including its
enabled capabilities; `config.openshift.io` resources such as proxy, network,
DNS, ingress, image, and OAuth; CRDs, RBAC, namespaces, monitoring, storage,
the image registry; and platform credentials and webhooks.

## Existing guests receive every change

Whatever the HCCO writes, it writes into every existing guest cluster on its
next reconcile once the cluster runs a release with the change. A change to
what it writes, or to a `support/` helper it calls (`support/capabilities/`,
`support/globalconfig/`, and others), is a default applied to existing
installations, even when the same helper also feeds objects rendered at
creation, such as a bootstrap manifest.

- **Critical** when a defect could break guest operators, workloads, or
  upgrades. The ClusterVersion spec drives the guest's cluster-version operator:
  an unexpected or invalid spec can stop reconciliation or upgrades of the
  guest.
- **Moderate** when it only adds an object or field that nothing in the guest
  acts on yet.

## Verify

- Callers of the changed function under `controllers/resources/` reconcile its
  output into existing guests.
- Unit tests that change the expected guest objects (for example under
  `controllers/resources/configuration/`) show that the reconciled output
  changes.
