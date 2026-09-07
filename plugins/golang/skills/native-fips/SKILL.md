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

### Build-time: `GOEXPERIMENT=strictfipsruntime` (downstream only)

The downstream [`golang-fips/go`](https://github.com/golang-fips/go) toolchain (used in RHEL/CentOS Go Toolset) provides `GOEXPERIMENT=strictfipsruntime`, which adds a startup check that panics if the binary's FIPS configuration is incompatible with the host environment. This is separate from `GOFIPS140` — it provides fail-closed startup enforcement, not module selection.

When using the downstream toolchain with native FIPS, retain `GOEXPERIMENT=strictfipsruntime` and add `-tags no_openssl` to switch from the OpenSSL backend to the native Go FIPS module:

```bash
CGO_ENABLED=0 GOEXPERIMENT=strictfipsruntime GOFIPS140=certified go build -tags no_openssl ...
```

Upstream Go does not support `strictfipsruntime`.

### Runtime: `GODEBUG=fips140=<value>`

Controls FIPS activation at runtime. Must be set wherever the binary is deployed (Dockerfile `ENV`, Kubernetes pod spec, systemd unit, etc.).

| Value | Behavior | Availability |
|-------|----------|--------------|
| `fips140=auto` | Follow the host's FIPS setting (`/proc/sys/crypto/fips_enabled`) | Downstream `golang-fips/go` only |
| `fips140=on` | Always enable FIPS, regardless of host | Upstream Go and downstream |
| `fips140=only` | FIPS-only mode, errors/panics on any non-FIPS crypto call. Test and assessment only — not for production. | Upstream Go and downstream |

Upstream Go (go.dev) supports `off`, `on`, and `only`. The `auto` value is provided by the downstream [`golang-fips/go`](https://github.com/golang-fips/go) toolchain. For upstream Go, use `fips140=on` to unconditionally enable FIPS.

### Post-quantum cryptography (ML-KEM)

Go 1.24+ includes `crypto/mlkem` (FIPS 203) and `crypto/tls` uses X25519MLKEM768 by default for TLS connections. This means ML-KEM is built into the binary — no OS-level crypto-policies configuration is needed.

The old approach required a separate [`crypto-policies`](https://gitlab.com/redhat-crypto/fedora-crypto-policies) setup (via RPM or manual config) to enable `DEFAULT:PQ`. This configured system C libraries (OpenSSL, GnuTLS, NSS, etc.) by generating per-library config files in `/etc/crypto-policies/back-ends/`:

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

## Verification with tls-scanner

The `tls-scanner` tool can verify endpoint TLS compliance on a running cluster — it connects to pod endpoints and checks their TLS configuration (protocol versions, cipher suites, and with `PQC_CHECK=true`, TLS 1.3 and ML-KEM readiness). It does not verify binary-level FIPS properties such as `GOFIPS140` module embedding, runtime FIPS activation, or non-TLS cryptographic usage.

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
