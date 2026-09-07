---
name: native-fips
description: |
  Configure Go projects to use Go's native FIPS 140 module instead of openssl-based FIPS.
  Use when the user wants to enable FIPS compliance in a Go project, migrate from openssl-based FIPS
  to native Go FIPS, or when build configs contain GOEXPERIMENT=strictfipsruntime or openssl-based FIPS patterns.
  Triggers on: 'native FIPS', 'GOFIPS140', 'FIPS without openssl', 'enable FIPS', 'migrate FIPS',
  'GOEXPERIMENT=strictfipsruntime', 'strictfipsruntime', 'fips140', 'Go FIPS module'.
---

# Native FIPS

Configure a Go project to use Go's native FIPS 140 module (`GOFIPS140`), producing static binaries (`CGO_ENABLED=0`) that no longer depend on the `openssl` RPM. Works for both new projects and migrating existing openssl-based FIPS setups.

## Reference

### Build-time: `GOFIPS140`

Tells the Go compiler which FIPS 140 crypto module to embed into the binary.

| Value | Status | ML-KEM | ML-DSA | Notes |
|-------|--------|--------|--------|-------|
| `v1.0.0` | Validation completed | Yes | No | Validated, stable |
| `v1.26.0` | Module In Process (MIP) | Yes | Yes | Adds ML-DSA + better entropy |
| `latest` | Alias | — | — | Resolves to newest available module |
| `certified` | Alias | — | — | Resolves to newest FIPS-certified module |

Use `certified` in `go build` as it automatically resolves to the latest certified module (currently `v1.0.0`). Both modules support ML-KEM (post-quantum key encapsulation), so post-quantum key exchange is available without the old `DEFAULT:PQ` crypto-policies stage.

### Runtime: `GODEBUG=fips140=<value>`

Controls FIPS activation at runtime. Must be set wherever the binary is deployed (Dockerfile `ENV`, Kubernetes pod spec, systemd unit, etc.).

| Value | Behavior |
|-------|----------|
| `fips140=auto` | Follow the host's FIPS setting (`/proc/sys/crypto/fips_enabled`) |
| `fips140=on` | Always enable FIPS, regardless of host |
| `fips140=only` | FIPS-only mode, panics on any non-FIPS crypto call (useful for testing) |

### Post-quantum cryptography (ML-KEM)

Go 1.24+ includes `crypto/mlkem` (FIPS 203) and `crypto/tls` uses X25519MLKEM768 by default for TLS connections. This means ML-KEM is built into the binary — no OS-level crypto-policies configuration is needed.

The old approach required a separate `crypto-policies` setup (via RPM or manual config) to enable `DEFAULT:PQ`. This configured system C libraries (OpenSSL, GnuTLS, NSS, etc.) by generating per-library config files in `/etc/crypto-policies/back-ends/`:

| Backend file | Library |
|---|---|
| `openssl.config` / `opensslcnf.config` | OpenSSL |
| `gnutls.config` | GnuTLS |
| `nss.config` | NSS (Mozilla) |
| `openssh.config` / `opensshserver.config` | OpenSSH |
| `java.config` | Java/OpenJDK |
| `krb5.config` | Kerberos |
| `libssh.config` | libssh |

The `:PQ` subpolicy prepends hybrid ML-KEM groups at highest priority, adding `X25519MLKEM768`, `P256-MLKEM768`, `P384-MLKEM1024` etc. to each backend in its native syntax.

**Why this is unnecessary for Go binaries:** A statically-compiled Go binary (`CGO_ENABLED=0`) with `GOFIPS140` uses its own `crypto/tls` stack — it does not link against OpenSSL, GnuTLS, or NSS. OS-level crypto-policies back-end configs have zero effect on Go binaries.

## Steps

### Step 1: Find go build commands

Search the project for `go build` invocations across Dockerfiles, Makefiles, shell scripts, and CI configs:

```bash
grep -rn "go build" --include="Dockerfile*" --include="Makefile*" --include="*.sh" --include="*.yaml" --include="*.yml" .
```

Classify each as:
- **Migration target**: contains old FIPS patterns (`GOEXPERIMENT=strictfipsruntime`, `CGO_ENABLED=1`, `-tags strictfipsruntime`)
- **New FIPS target**: contains `go build` but no FIPS configuration yet
- **Skip**: not a Go build command (e.g., comments, documentation)

Report findings to the user before making changes.

### Step 2: Update go build commands

For each `go build` invocation, set:

```
CGO_ENABLED=0 GOFIPS140=certified go build ... -tags no_openssl ...
```

Specifically:
- Set `CGO_ENABLED=0` (replaces `CGO_ENABLED=1`)
- Set `GOFIPS140=certified` (replaces `GOEXPERIMENT=strictfipsruntime`)
- Replace `-tags strictfipsruntime` with `-tags no_openssl`
- If there are existing `-tags` with multiple values, append `no_openssl` and remove `strictfipsruntime`
- Preserve all other build flags (`-trimpath`, `-ldflags`, `-mod`, `-o`, etc.)

### Step 3: Add runtime GODEBUG

Set `GODEBUG=fips140=auto` at runtime, wherever the binary is deployed:
- **Dockerfile**: add `ENV GODEBUG=fips140=auto` before the `USER` or `ENTRYPOINT` directive
- **Kubernetes**: add to the container's `env` in the pod spec
- **systemd**: add `Environment=GODEBUG=fips140=auto` to the unit file
- **Shell**: export `GODEBUG=fips140=auto` before running the binary

### Step 4: Clean up old openssl/crypto-policies artifacts (migration only)

If old FIPS patterns were detected, the openssl and [crypto-policies](https://gitlab.com/redhat-crypto/fedora-crypto-policies) infrastructure can be removed as a side effect — it is no longer needed for Go binaries.

1. **Remove `openssl` from package installs.** If `openssl` was the only package being installed in a Dockerfile stage, the entire stage can be removed.

2. **Remove crypto-policies infrastructure.** Look for both RPM-based and manual configurations:
   - Build stages installing `crypto-policies-scripts` and running `update-crypto-policies --set DEFAULT:PQ`
   - `COPY --from=crypto-policies /etc/crypto-policies/ /etc/crypto-policies/` lines
   - Manual overrides: files copied into `/etc/crypto-policies/local.d/`, modified symlinks in `/etc/crypto-policies/back-ends/`, or direct OpenSSL group overrides in `/etc/pki/tls/openssl.cnf`
   - Custom OpenSSH `KexAlgorithms` entries for `mlkem768x25519-sha256`

   All of these are unnecessary for Go binaries — see the Reference section above for why.

3. **Update `rpms.in.yaml`** (if it exists): remove `openssl` and `crypto-policies-scripts` entries.

## Verification with tls-scanner

The `tls-scanner` tool can verify FIPS and post-quantum TLS compliance on a running cluster. It deploys a scanner pod that connects to all pod endpoints and checks their TLS configuration.

The tool source and documentation is at https://github.com/openshift/tls-scanner. The `tls-scanner-run` step ref is defined in the `openshift/release` step registry at `ci-operator/step-registry/tls/scanner/run/`.

### Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `SCAN_NAMESPACE` | `""` (all) | Comma-separated namespaces to scan. Empty scans all namespaces. |
| `PQC_CHECK` | `"false"` | Set `"true"` to check post-quantum cryptography readiness (TLS 1.3 + ML-KEM support). |
| `SCANNER_NAMESPACE` | `""` | Namespace where the scanner pod is deployed. Empty creates a dedicated `tls-scanner` namespace. |
| `SCAN_LIMIT_IPS` | `""` | Max IPs to scan (empty/0 = no limit). Useful for smoke testing. |
| `TLS_PROFILE_TYPE` | `""` | Expected TLS profile type (`Old`, `Intermediate`, `Modern`). When set, overrides reading from APIServer/cluster. |
| `TLS_SCANNER_CLUSTER_LABEL` | `""` | HyperShift target: `"management"` or `"guest"`. Empty scans via the step's KUBECONFIG. |
