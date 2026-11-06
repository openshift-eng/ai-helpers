# NodePools and nodes

The NodePool controller runs in the HO (`hypershift-operator/controllers/nodepool/`):
a change to it reaches every NodePool on the management cluster at once when
the HO is upgraded, whatever the hosted clusters' versions.

## What replaces or updates machines

- **Config hashes** (`config.go`: `RolloutHash`, `RolloutHashWithoutVersion`,
  `Hash`, `HashWithoutVersion`). The rollout hashes decide when machines are
  replaced (Replace upgrade type) or updated in place (InPlace); `Hash` names
  the token and user-data secrets. Adding, removing, or changing how an input
  is rendered or hashed changes the hash of every existing NodePool, so every
  machine of every pool can be replaced on HO upgrade: Critical.
- **Token and user-data secrets** (`token.go`, `secret_janitor.go`). They carry
  the ignition token new machines use to join. A defect strands new and
  replacement machines, autoscaled and Karpenter nodes included: Critical.
- **CAPI objects** the controller writes (`capi.go`: MachineDeployments,
  MachineSets, machine templates). A change to their templates rolls machines:
  Critical.
- **Ignition** (`ignition-server/`, the MachineConfig the payload renders). What
  new nodes boot with; a defect stops nodes from joining or misconfigures them:
  Critical.
- **Karpenter** (`karpenter-operator/`, AutoNode). What it provisions and
  disrupts on running clusters: Critical. Its cleanup when a hosted cluster is
  deleted follows the deletion rules in
  [Control plane workloads](control-plane-workloads.md).

Verify in the source at the base commit whether a changed value feeds a hash, a
token or user-data secret, or a machine template: read the callers.

## What stays Moderate

- New NodePool conditions, events, or metrics, and status fields no controller
  acts on.
- Reporting management-side drift without acting on it.
