## Context

The control-plane-operator (CPO) `awsprivatelink` controller sends every subnet in `AWSEndpointService.spec.subnetIDs` to `CreateVpcEndpoint`/`ModifyVpcEndpoint`, including subnets in AWS Local Zones. AWS does not allow VPC endpoints in Local Zone subnets, so the call is rejected and the endpoint reconcile fails on every retry.

Since commit 88643f6e74a ("feat(autnode): use arbitrary subnets from karpenter ec2nodeclass", landed March 2026), the hypershift-operator adds the subnets of every Karpenter `OpenshiftEC2NodeClass` to that list. An AutoNode NodeClass that selects a Local Zone subnet therefore breaks VPC endpoint reconciliation for the hosted cluster.

Original report:

```
The control-plane-operator, when reconciling the AWS VPC Endpoint for an AWS cluster, does not remove AWS local zones from the AZs it tries to create endpoitns in.
```

### Steps to Reproduce

1. Create a HostedCluster with Karpenter (AutoNode) enabled and Private or PublicAndPrivate endpoint access (the clusters that have AWSEndpointServices).
2. Add a NodePool that targets a subnet in an AWS Local Zone (reported with `us-east-1-bue-1a` through an `OpenshiftEC2NodeClass` that selects that subnet).
3. Observe the CPO erroring.

Reproducible always, while a Local Zone subnet is in the endpoint subnet list.

### Actual and expected results

- Actual: CPO fails to reconcile the VPC endpoint (see Additional info).
- Expected: CPO reconciles the VPC endpoint, removing any local zones. Local Zone subnets are left out of the endpoint, and Local Zone nodes keep reaching it through its interfaces in the region's Availability Zones, as they already do today.

### Affected versions

- 4.22.z: Confirmed. The production stack trace has `reconcileAWSEndpointService` (`awsprivatelink_controller.go:747`) as the top frame, called from `Reconcile` (`:501`). That matches `release-4.22` line for line from f1455fa789b (2026-06-11) on. On 4.23 and later this log line is in `modifyEndpointIfNeeded`, so those versions would produce a different stack. Reproduced in a unit test on `release-4.22`.
- 4.23, 5.0, 5.1, 5.2: Inferred. Same CPO behavior with no zone filtering, and Karpenter subnet propagation is present. Reproduced in a unit test on `main`.
- 4.21 and earlier HCPs: Unknown. The `karpenter-subnets` ConfigMap is written by the karpenter-operator, which runs from the HO image (standalone mode is TechPreview and opt-in), and no CPO version filters zones. Older HCPs with AutoNode under a current HO would likely fail the same way. Not observed.
- Proposed Affects Version/s: 4.22.z, 5.1.

### Impact

- The endpoint reconcile fails permanently: `AWSEndpointAvailable=False` on the AWSEndpointService and on the HostedCluster, which the HO failure-condition metrics count.
- Other subnet changes are blocked: a standard-AZ subnet added alongside the Local Zone subnet is never attached, because it is in the same rejected request.
- Steps after the endpoint (Route53 records; ExternalName services on 4.23+) are skipped while it fails.
- Latent outage: if the endpoint has to be recreated (for example, after `InvalidVpcEndpointId.NotFound` resets the status), `CreateVpcEndpoint` fails and no endpoint exists.
- Not caused by this bug: the failing reconcile does not delete, recreate, or shrink the existing endpoint (see Evidence), so it does not explain the Local Zone ignition symptom in the comments.
- Workaround: use standard-AZ subnets for new workers until fixed. Editing `spec.subnetIDs` by hand doesn't stick, because the hypershift-operator owns that list.

## Technical Details

Root cause, in openshift/hypershift:

1. karpenter-operator `reconcileKarpenterSubnetsConfigMap` (`karpenter-operator/controllers/nodeclass/ec2_nodeclass_controller.go`) writes every `OpenshiftEC2NodeClass` `status.subnets` ID to the `karpenter-subnets` ConfigMap.
2. hypershift-operator `listSubnetIDs` (`hypershift-operator/controllers/platform/aws/controller.go`) merges NodePool and Karpenter subnets into `spec.subnetIDs` of each AWSEndpointService (`private-router`, `kube-apiserver-private`).
3. CPO `ensureVPCEndpoint` only keeps one subnet per AZ (`deduplicateSubnetsByAZ`). A Local Zone has its own zone name (`us-east-1-bue-1a`), so its subnet survives and is sent in `AddSubnetIds` (or `SubnetIds` on create). AWS rejects the whole request with 400 `InvalidParameter`.

A HyperShift NodePool whose `spec.platform.aws.subnet.id` is a Local Zone subnet reaches the same field without Karpenter.

### Evidence

- Production CPO log in Additional info (ROSA HCP, `us-east-1`).
- AWS Local Zones User Guide, "How AWS Local Zones work": "You cannot create VPC endpoints inside Local Zone subnets." https://docs.aws.amazon.com/local-zones/latest/ug/how-local-zones-work.html
- Prior art: the vendored cluster-api-provider-aws models zone types (`availability-zone`, `local-zone`, `wavelength-zone`) and keeps edge zones out of core infrastructure: "Edge zones should not deploy control plane nodes, and does not support Nat Gateway and Network Load Balancers. Any resource for the core infrastructure should not consume edge zones." (`vendor/sigs.k8s.io/cluster-api-provider-aws/v2/api/v1beta2/network_types.go`, `SubnetSpec.IsEdge`)
- Unit experiment on `release-4.22` at db8d2278410 (gomock EC2, `go test ./control-plane-operator/controllers/awsprivatelink/ -run TestRefineExperiment`):
  - With `spec.subnetIDs=[subnet-std-1a, subnet-06b56643b49ed429f]` (zones `us-east-1a`, `us-east-1-bue-1a`), three reconciles each sent `ModifyVpcEndpoint AddSubnetIds=[subnet-06b56643b49ed429f] RemoveSubnetIds=[]` and returned `failed to modify vpc endpoint: InvalidParameter`.
  - `status.endpointID` was kept, and there were no DeleteVpcEndpoints, CreateVpcEndpoint, or Route53 calls.
  - Adding `subnet-std-1b` at the same time put it in the same rejected request.
  - Control (standard subnet only): no modify call, success.
- Same experiment on `main` at a0aaf80a611: same modify behavior. On the create path, `CreateVpcEndpoint SubnetIds=[subnet-06b56643b49ed429f, subnet-std-1a]` failed and no endpoint was created.
- Limitation: AWS was mocked. That a rejected `ModifyVpcEndpoint` leaves the endpoint unchanged is inferred from the 400 `InvalidParameter` response, not tested against AWS.
- Related: ROSAENG-74689, the same AWS error for standard AZs that the management-cluster NLB does not cover. It is being fixed in the management VPC infrastructure and suggests an upstream AZ intersection.

### Implementation plan

Repository openshift/hypershift, branch `main`; backport through `release-4.22`, where the incident ran.

1. In `control-plane-operator/controllers/awsprivatelink/awsprivatelink_controller.go`, extend subnet selection in `ensureVPCEndpoint`/`deduplicateSubnetsByAZ`. Reuse the `DescribeSubnets`-backed `subnetAZCache`. Before the one-per-AZ pick, drop subnets whose zone is known and is not a standard Availability Zone of `hcp.Spec.Platform.AWS.Region`. A standard AZ name is the region plus one letter (`us-east-1a`); Local Zones (`us-east-1-bue-1a`) and Wavelength Zones are excluded. Keep subnets whose zone is unknown (current behavior).
2. Both the create and modify paths already consume the selected `spec.subnetIDs` from `ensureVPCEndpoint`; there are no other call sites. Keep the existing single-subnet shortcut (no `DescribeSubnets` call); a lone Local Zone subnet can't produce a working endpoint either way.
3. Log excluded subnet IDs and zones at Info level. Avoid "local zone" in new identifiers, because this controller already uses that term for the `hypershift.local` Route53 zone.
4. If no eligible subnet remains, return a clear error naming the excluded subnets and make no Create/ModifyVpcEndpoint call. Never pass an empty desired set to the modify diff.
5. Leave the `DescribeSubnets` failure fallback unchanged, so clusters whose role lacks the permission keep today's behavior instead of failing. No new IAM permissions (`ec2:DescribeSubnets` is already in ROSAControlPlaneOperatorPolicy v7 and in the HyperShift CLI policies, including the shared-VPC endpoint role), no API change, and no NodePool config-hash impact.

### Alternatives considered

- Look up zone types with `DescribeAvailabilityZones` (explicit `ZoneType`, as cluster-api-provider-aws does): neither the CPO role nor the shared-VPC endpoint role has the permission, and ROSA's AWS-managed ROSAControlPlaneOperatorPolicy v7 doesn't grant it. With a fail-open fallback, ROSA would stay broken until AWS updates the policy.
- Intersect with the endpoint service's AZs through `DescribeVpcEndpointServices`: more general (also covers ROSAENG-74689), but also not in ROSAControlPlaneOperatorPolicy v7. Follow-up.
- Filter in the karpenter-operator using `status.subnets[].zone`: ships with the HO for every HCP version, but misses NodePool subnets and splits the endpoint rules across components. Optional complement if older streams cannot take the CPO backport.
- Parse the AWS error and retry without the subnet: the error text is not an API contract.

## Acceptance Criteria

- With a Local Zone subnet and at least one standard-AZ subnet in `spec.subnetIDs`, the CPO never sends the Local Zone subnet to `CreateVpcEndpoint`/`ModifyVpcEndpoint`. The reconcile succeeds, and `AWSEndpointAvailable=True` on both AWSEndpointServices and on the HostedCluster.
- A new standard-AZ subnet is attached while a Local Zone subnet is also present.
- Recreating the endpoint (empty `status.endpointID`) creates it in standard-AZ subnets only.
- When every inspected subnet is excluded, no Create/Modify call is made, and the error names the excluded subnets and zones.
- No change for standard-AZ-only clusters, same-AZ deduplication, or the DescribeSubnets failure fallback.
- No API, IAM policy, or NodePool config-hash change.

## Validation

- Unit tests in `awsprivatelink_controller_test.go` (gomock EC2, TESTING.md naming) for each criterion, including Wavelength zone names, GovCloud and China region names, and cold and warm caches; `make test` and `make verify`.
- Manual: an AWS HCP in `us-east-1` with AutoNode and an `OpenshiftEC2NodeClass` selecting a subnet in an enabled Local Zone. Check that:
  - the `karpenter-subnets` ConfigMap lists the subnet;
  - the CPO logs the exclusion and no `failed to modify vpc endpoint`;
  - `AWSEndpointAvailable=True`;
  - `aws ec2 describe-vpc-endpoints` shows standard-AZ subnets only.
- Then launch a fresh Local Zone worker (gp2 volumes, since gp3 isn't offered in `us-east-1-bue-1a`), capture its first-boot ignition and kubelet logs, and check that it registers. If it still fails to register with the endpoint healthy, keep the logs and track the bootstrap failure in a separate bug.
- Shared VPC: EC2 calls run under the shared-VPC endpoint role. For ROSA shared VPC, confirm that role allows `ec2:DescribeSubnets`; otherwise the filter falls back to today's behavior.
- A CI e2e would need the CI account opted into a Local Zone group (optional).

## Out of scope

- Standard AZs not served by the management-cluster endpoint service (ROSAENG-74689).
- Ignition payload not applied on Local Zone nodes (comment of 2026-10-21). This bug does not explain it: the failing reconcile makes no destructive calls, and the node reached the ignition server through the existing endpoint after boot. The fresh-node check above will show whether it persists; if so, it gets its own bug.

## Additional info

Original CPO log (namespace anonymized in this fixture):

```
control-plane-operator-77956d5bcc-jc26f {"level":"error","ts":"2026-10-21T19:41:39Z","msg":"failed to modify vpc endpoint","controller":"awsendpointservice","controllerGroup":"hypershift.openshift.io","controllerKind":"AWSEndpointService","AWSEndpointService":{"name":"private-router","namespace":"ocm-production-2aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa-user-lz"},"namespace":"ocm-production-2aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa-user-lz","name":"private-router","reconcileID":"a578b86a-a279-44d5-a404-9359e6698f6e","error":"operation error EC2: ModifyVpcEndpoint, https response error StatusCode: 400, RequestID: 61738cd9-ed62-426c-a006-c922111ed0dc, api error InvalidParameter: The VPC endpoint service com.amazonaws.vpce.us-east-1.vpce-svc-0b5823fd0960bc111 does not support the availability zone of the subnet: subnet-06b56643b49ed429f.","stacktrace":"github.com/openshift/hypershift/control-plane-operator/controllers/awsprivatelink.(*AWSEndpointServiceReconciler).reconcileAWSEndpointService\n\t/hypershift/control-plane-operator/controllers/awsprivatelink/awsprivatelink_controller.go:747\ngithub.com/openshift/hypershift/control-plane-operator/controllers/awsprivatelink.(*AWSEndpointServiceReconciler).Reconcile\n\t/hypershift/control-plane-operator/controllers/awsprivatelink/awsprivatelink_controller.go:501\nsigs.k8s.io/controller-runtime/pkg/internal/controller.(*Controller[...]).Reconcile\n\t/hypershift/vendor/sigs.k8s.io/controller-runtime/pkg/internal/controller/controller.go:116\nsigs.k8s.io/controller-runtime/pkg/internal/controller.(*Controller[...]).reconcileHandler\n\t/hypershift/vendor/sigs.k8s.io/controller-runtime/pkg/internal/controller/controller.go:303\nsigs.k8s.io/controller-runtime/pkg/internal/controller.(*Controller[...]).processNextWorkItem\n\t/hypershift/vendor/sigs.k8s.io/controller-runtime/pkg/internal/controller/controller.go:263\nsigs.k8s.io/controller-runtime/pkg/internal/controller.(*Controller[...]).Start.func2.2\n\t/hypershift/vendor/sigs.k8s.io/controller-runtime/pkg/internal/controller/controller.go:224"}
```
