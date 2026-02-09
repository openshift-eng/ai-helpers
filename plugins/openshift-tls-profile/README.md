# OpenShift TLS Profile

A skill for implementing TLS security profiles in Kubernetes operators and workloads running on OpenShift.

## Overview

This skill provides guidance on:

- **Reading TLS Configuration**: Fetching TLS security profiles from the APIServer custom resource
- **Profile Conversion**: Converting OpenShift TLS profiles to Go `crypto/tls` configuration
- **Applying TLS Settings**: Configuring webhook servers, metrics endpoints, HTTP/gRPC clients and servers
- **library-go Utilities**: Using `github.com/openshift/library-go/pkg/crypto` for cipher suite conversion

## TLS Profile Types

OpenShift supports four TLS profile types based on Mozilla's Server Side TLS recommendations:

| Profile | Min TLS Version | Use Case |
|---------|-----------------|----------|
| Old | TLS 1.0 | Legacy compatibility (not recommended) |
| Intermediate (default) | TLS 1.2 | Recommended for general use |
| Modern | TLS 1.3 | Highest security |
| Custom | Configurable | User-defined ciphers and TLS version |

**Note:** When `spec.tlsSecurityProfile` is not set in the APIServer CR, the **Intermediate** profile is used as the default.

## When to Use This Skill

Use this skill when:

- Implementing TLS security profiles in a Kubernetes operator running on OpenShift
- Configuring controller-runtime webhook servers and metrics endpoints
- Setting up HTTP or gRPC clients/servers that need to comply with OpenShift TLS policies
- Converting OpenShift TLS profile types to Go `crypto/tls` configuration
- Troubleshooting TLS-related connection issues in OpenShift clusters

## Quick Start

### Check Cluster TLS Profile

```bash
# Get the current TLS security profile (empty output means default Intermediate profile)
oc get apiserver cluster -o jsonpath='{.spec.tlsSecurityProfile}' | jq .

# Check the profile type (empty means Intermediate default)
oc get apiserver cluster -o jsonpath='{.spec.tlsSecurityProfile.type}'
```

### Basic Implementation Pattern

1. **Fetch TLS profile** from `APIServer` CR named `cluster`
2. **Convert profile** to Go `tls.Config` using library-go utilities
3. **Apply to endpoints** (webhook server, metrics server, HTTP/gRPC)

```go
// Fetch profile from cluster
apiServer := &configv1.APIServer{}
client.Get(ctx, types.NamespacedName{Name: "cluster"}, apiServer)
profile := apiServer.Spec.TLSSecurityProfile

// Convert to tls.Config
minVersion, _ := crypto.TLSVersion(string(profile.MinTLSVersion))
ciphers := crypto.OpenSSLToIANACipherSuites(profile.Ciphers)
cipherSuites := crypto.CipherSuitesOrDie(ciphers)

tlsConfig := &tls.Config{
    MinVersion:   minVersion,
    CipherSuites: cipherSuites,
}
```

## Key Dependencies

```go
import (
    configv1 "github.com/openshift/api/config/v1"
    "github.com/openshift/library-go/pkg/crypto"
)
```

- `github.com/openshift/api` - OpenShift API types including `TLSSecurityProfile`
- `github.com/openshift/library-go` - Crypto utilities for TLS version and cipher conversion

## library-go Crypto Utilities

The `library-go/pkg/crypto` package provides essential functions:

| Function | Purpose |
|----------|---------|
| `TLSVersion(name)` | Convert TLS version name to Go constant |
| `OpenSSLToIANACipherSuites(ciphers)` | Convert OpenSSL cipher names to IANA names |
| `CipherSuitesOrDie(names)` | Convert cipher names to Go constants |
| `SecureTLSConfig(config)` | Apply secure defaults to TLS config |
| `DefaultTLSVersion()` | Get default TLS version (1.2) |
| `DefaultCiphers()` | Get default cipher suites |

## Skill Documentation

See [skills/skills/SKILL.md](skills/skills/SKILL.md) for complete implementation details including:

- Step-by-step implementation guide
- Complete code examples for all endpoint types
- Full operator example with controller-runtime
- Troubleshooting guide
- Verification commands

## Resources

- [OpenShift TLS Security Profiles Documentation](https://docs.openshift.com/container-platform/latest/security/tls-security-profiles.html)
- [Mozilla Server Side TLS](https://wiki.mozilla.org/Security/Server_Side_TLS)
- [OpenShift API - TLS Security Profile Types](https://github.com/openshift/api/blob/master/config/v1/types_tlssecurityprofile.go)
- [OpenShift library-go Crypto Package](https://pkg.go.dev/github.com/openshift/library-go/pkg/crypto)
- [TLS Configuration in OpenShift (Red Hat KB)](https://access.redhat.com/articles/5348961)
