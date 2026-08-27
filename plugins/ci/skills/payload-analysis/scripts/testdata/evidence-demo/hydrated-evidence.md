# Validated evidence for `4.22.0-0.nightly-2026-08-27-example`

## `periodic-ci-openshift-release-master-nightly-4.22-e2e-aws-ovn`

### 1. Why did this job fail?

The cluster install timed out because the worker MachineConfigPool remained degraded.

Proof 1 (log, [payload-evidence/e2e-aws-ovn/build-log.txt](https://gcsweb-ci.example/artifacts/build-log.txt), lines 4-6):

```text
4 | ERROR Cluster not ready after 40m0s
5 | ERROR MachineConfigPool worker is Degraded=True
6 | ERROR timed out waiting for the condition
```

Why it supports the answer: The failing install step names the degraded worker pool as the condition that exhausted the timeout.

### 2. Why did the worker MachineConfigPool remain degraded?

The machine-config daemon could not complete the rendered-config rollout on worker-2 because CRI-O repeatedly failed to start.

Proof 1 (log, [payload-evidence/e2e-aws-ovn/machine-config-daemon.log](https://gcsweb-ci.example/artifacts/machine-config-daemon.log), lines 2-4):

```text
2 | E0827 update.go:244] worker-2: failed to start crio.service
3 | E0827 update.go:245] systemctl start crio.service exited with status 1
4 | E0827 daemon.go:902] blocking rendered config rollout until service recovers
```

Why it supports the answer: The daemon reports the exact node and blocks rollout after CRI-O fails during the update.

### 3. Why did CRI-O fail to start on worker-2?

The generated CRI-O configuration contained the unsupported field enable_pod_events, which the candidate change began emitting unconditionally.

Proof 1 (log, [payload-evidence/e2e-aws-ovn/machine-config-daemon.log](https://gcsweb-ci.example/artifacts/machine-config-daemon.log), lines 5-7):

```text
5 | E0827 crio.go:118] parsing /etc/crio/crio.conf.d/99-mco.conf
6 | E0827 crio.go:119] unknown field "enable_pod_events" in table crio.runtime
7 | E0827 crio.go:120] configuration validation failed; refusing to start
```

Why it supports the answer: CRI-O's parser rejects enable_pod_events and exits, directly explaining the service-start failure.

Proof 2 (code, [payload-evidence/e2e-aws-ovn/pr-12345.diff](https://github.com/openshift/machine-config-operator/pull/12345/files), lines 3-6):

```text
3 | --- a/pkg/controller/container-runtime-config/helpers.go
4 | +++ b/pkg/controller/container-runtime-config/helpers.go
5 | @@ -210,0 +211 @@ func renderCrioConfig(cfg *Config) string {
6 | +enable_pod_events = true
```

Why it supports the answer: The candidate diff adds the same rejected field to every generated CRI-O configuration.
