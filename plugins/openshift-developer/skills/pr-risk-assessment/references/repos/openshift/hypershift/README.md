# openshift/hypershift

HyperShift runs OpenShift control planes as workloads on a management cluster.
A hosted cluster's control plane runs in a namespace of the management cluster;
its nodes come from NodePools.

## How a change reaches installations

| Component | Code | Runs | A change arrives |
|---|---|---|---|
| HyperShift operator (HO) | `hypershift-operator/`, and the `support/` code it calls | once per management cluster | at every HostedCluster and NodePool on that management cluster at once, when the HO is upgraded, whatever their OpenShift versions |
| Control plane operator (CPO), hosted cluster config operator (HCCO), ignition server, karpenter-operator, other control plane components | `control-plane-operator/`, `ignition-server/`, `karpenter-operator/`, `etcd-*`, the proxies, and the `support/` code they call | per hosted cluster, in its control plane namespace, from the image in its release payload | when a hosted cluster moves to a release that carries the change (a z-stream or minor upgrade) |
| CLI | `cmd/`, `product-cli/` | users' machines and CI | clusters created or changed with the new CLI |

The HO also renders some control plane objects itself, the CPO Deployment
among them: a change to them reaches every hosted cluster on the management
cluster when the HO is upgraded.

`support/` is shared code: a change there reaches every component that calls
it, each on its own path above. Trace the callers before deciding who
receives it.

## Branches

`main` feeds the next OpenShift minor release. `release-4.y` and `release-5.y`
feed z-streams of released versions: a pull request against one, including a
cherry-pick, reaches existing customer clusters in a z-stream update.

## Topics

Read the topic files whose paths the diff touches:

| Paths | Read | Why |
|---|---|---|
| `hypershift-operator/controllers/nodepool/`, `karpenter-operator/`, `ignition-server/`, token and user-data code | [NodePools and nodes](nodepool-and-nodes.md) | node replacement and in-place updates, new nodes joining |
| `control-plane-operator/hostedclusterconfigoperator/`, `support/capabilities/`, `support/globalconfig/` | [Guest cluster configuration](guest-cluster-config.md) | configuration written into every existing guest cluster |
| `hypershift-operator/controllers/hostedcluster/`, `control-plane-operator/controllers/hostedcontrolplane/`, and `support/` helpers that render control plane workloads | [Control plane workloads](control-plane-workloads.md) | fleet-wide control plane rollouts, deletion, credentials |
| `support/releaseinfo/`, `support/imageregistry/`, image and registry helpers in `support/util/`, `support/globalconfig/imagecontentsource.go` | [Control plane workloads](control-plane-workloads.md) | registry mirrors and where images are pulled from |
| `api/`, CRD manifests, `client/` | [API and version skew](api-and-skew.md) | compatibility with existing objects and other releases |
| platform code: `**/platform/<name>/`, and `aws`, `azure`, `gcp`, `kubevirt`, `agent`, `openstack`, `powervs`, `ibmcloud` directories | [Platforms](platforms.md) | cloud credentials, DNS, endpoints, load balancers |

## What does not ship

`docs/`, `test/` (e2e suites), `hack/` (tooling), `.github/` (CI workflows),
`*_test.go`, and `testdata/` do not ship: Low unless the change alters what
ships, such as a helper production code calls. `.tekton/`, `Dockerfile*`, and
`Containerfile*` build shipped images: judge a change to what the image
contains.

Fixtures under `testdata/` (`zz_fixture_*`) are the expected rendered objects of
the code they test: a changed fixture shows what that code now renders, in
every hosted cluster that runs it.
