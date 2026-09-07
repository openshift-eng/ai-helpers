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

Configure a Go project to use Go's native FIPS 140 module (`GOFIPS140`). With `CGO_ENABLED=0`, this produces static binaries that no longer depend on the `openssl` RPM. Projects that require cgo should keep `CGO_ENABLED=1` and adjust their FIPS setup accordingly. Works for both new projects and migrating existing openssl-based FIPS setups.

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

When migrating a downstream build from the OpenSSL backend to native FIPS on 1.26+ builders, retain `GOEXPERIMENT=strictfipsruntime` and add `-tags no_openssl` to disable the OpenSSL backend. The 1.26+ builders imply `GODEBUG=fips140=auto` whenever the FIPS module is compiled in, so the binary works on both FIPS and non-FIPS hosts:

```bash
CGO_ENABLED=0 GOFIPS140=v1.26.0 GOEXPERIMENT=strictfipsruntime go build -tags no_openssl ...
```

For upstream Go (which has no `strictfipsruntime` or OpenSSL backend):

```bash
CGO_ENABLED=0 GOFIPS140=certified go build ...
```

### Runtime: `GODEBUG=fips140=<value>`

Controls FIPS activation at runtime. **You almost never need to set this explicitly.** When a binary is built with `GOFIPS140`, the toolchain sets an appropriate default: upstream Go defaults to `fips140=on`, and the downstream `golang-fips/go` toolchain defaults (or will soon default) to `fips140=auto`. Only override this if you need behavior different from the toolchain default.

| Value | Behavior | Availability |
|-------|----------|--------------|
| `fips140=auto` | Follow the host's FIPS setting (`/proc/sys/crypto/fips_enabled`) | Downstream `golang-fips/go` only |
| `fips140=on` | Always enable FIPS, regardless of host | Upstream Go and downstream |
| `fips140=only` | Best-effort FIPS-only mode — non-FIPS crypto calls may return an error or panic. May produce false positives/negatives. Test and assessment only — not for production. | Upstream Go and downstream |

Upstream Go (go.dev) supports `off`, `on`, and `only`. The `auto` value is provided by the downstream [`golang-fips/go`](https://github.com/golang-fips/go) toolchain.

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

**Why this is unnecessary for Go binaries:** A statically-compiled Go binary (`CGO_ENABLED=0`) with `GOFIPS140` uses its own `crypto/tls` stack — it does not link against OpenSSL, GnuTLS, or NSS. OS-level crypto-policies back-end configs have zero effect on Go binaries. Such binaries have no runtime library dependencies, so they can run in minimal scratch-like images such as [Hardened Images - Static](https://images.redhat.com/?name=static&version=latest).

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

## Glossary

| Name | Type | Values | Description |
|------|------|--------|-------------|
| `GOFIPS140` | Build env var | `certified`, `latest`, `v1.0.0`, `v1.26.0` | Selects which FIPS 140 crypto module to embed. `certified` resolves to the latest validated module. |
| `GOEXPERIMENT=strictfipsruntime` | Build env var | (flag) | Downstream only. Adds a startup panic if FIPS config is incompatible with the host. |
| `CGO_ENABLED` | Build env var | `0`, `1` | `0` produces a static binary with no C dependencies. `1` links against C libraries (needed if the project requires cgo). |
| `-tags no_openssl` | Build tag | (flag) | Disables the downstream OpenSSL crypto backend so the binary uses only Go's native FIPS module. Not needed for upstream Go. |
| `fips140v1.26` | Synthesized build tag | (automatic) | Injected by the toolchain when `GOFIPS140=v1.26.0` is set. Not user-specified. |
| `GODEBUG=fips140` | Runtime env var | `auto`, `on`, `only`, `off` | Controls FIPS activation at runtime. Rarely needs to be set — the toolchain picks the right default when built with `GOFIPS140`. `auto` is downstream only. |
