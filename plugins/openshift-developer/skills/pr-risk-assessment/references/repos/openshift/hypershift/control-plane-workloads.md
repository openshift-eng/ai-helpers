# Control plane workloads

## Who renders what

- The HO renders the CPO Deployment for every hosted cluster
  (`hypershift-operator/controllers/hostedcluster/`). A change to its pod
  template (image, arguments, environment, volumes) rolls the CPO of every
  hosted cluster on the management cluster when the HO is upgraded.
- The CPO renders the other workloads in its namespace
  (`control-plane-operator/controllers/hostedcontrolplane/`): kube-apiserver,
  etcd, OAuth, konnectivity, the HCCO, the ignition server, the guest's
  cluster-version operator, and others. A change to their pod templates rolls
  them in each hosted cluster when it moves to the release carrying the change.

A pod template includes the environment variables and arguments computed from
configuration: a change that only reorders or normalizes a rendered value still
changes the template, and rolls the workload once where it lands.

## Blast radius

- A one-time rollout of operators and controllers (the CPO, the HCCO, the
  cluster-version operator, other operators) is routine: Moderate, when the new
  configuration cannot keep them from running correctly.
- kube-apiserver, etcd, OAuth, konnectivity, and the ignition server carry the
  hosted cluster's API, data, authentication, node connectivity, and new nodes
  joining: a change that could leave them unavailable or misbehaving is
  Critical. Changes to etcd membership, storage, defragmentation, or backups
  are Critical.

## Registry mirrors

The HO reads the management cluster's ImageDigestMirrorSet and
ImageContentSourcePolicy objects into a list of mirrors per source
(`support/globalconfig/imagecontentsource.go`) and renders them into the CPO's
`OPENSHIFT_IMG_OVERRIDES`; the CPO renders them for the HCCO and the ignition
server. Release and image-metadata lookups try a source's mirrors in list
order, verify that a mirror has the image before using it, and otherwise fall
back to the source (`support/releaseinfo/registry_image_content_policies.go`,
`support/util/imagemetadata.go`).

Both kinds of objects declare digest mirrors: copies of the same images.
Changing the order of the mirrors, or which one wins, changes which registry
serves an image, not which image runs. A defect costs slower pulls, or a
verification timeout for each unreachable mirror: Moderate, together with the
one-time rollout of the workloads whose environment changes. It is Critical
when a change can skip the verification, rewrite image references, or leave
components without any mirror that has the image.

## Deletion and finalizers

Deleting a HostedCluster runs finalizers that clean up cloud resources, DNS
records, and guest-side objects (`hypershift-operator/controllers/hostedcluster/`
and platform code).

- A defect in cleaning up a cluster that is already being deleted leaves
  resources behind (cost, quota) or blocks the deletion: Moderate.
- Critical when the defect could act on a cluster that is not being deleted, or
  remove resources that running clusters still use, such as shared networks,
  DNS zones, load balancers, or identity providers.

## Credentials

The HO and the CPO provision the credentials control plane components use for
the cloud (STS roles, workload identity, service account keys). Changing how
credentials are issued, scoped, stored, or rotated is Critical. Reading whether
a credential is valid to decide something is not changing credentials: judge
the decision's blast radius.
