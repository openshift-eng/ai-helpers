---
description: Use this skill to implement TLS security profiles for operators and workloads on OpenShift. Provides guidance on reading TLS config from APIServer CR and applying it to webhook/metrics servers, HTTP, and gRPC endpoints.
argument-hint: "[question or implementation request]"
---

## Name

openshift-tls-profile:implement

## Synopsis

```
/openshift-tls-profile:implement [question or implementation request]
```

## Description

The `openshift-tls-profile:implement` command provides guidance on implementing TLS security profiles for operators and workloads running on OpenShift. It helps with:

- **Recommended**: Using `github.com/openshift/controller-runtime-common/pkg/tls` for controller-runtime operators (provides `FetchAPIServerTLSProfile`, `NewTLSConfigFromProfile`, and `SecurityProfileWatcher`)
- Reading TLS configuration from the APIServer custom resource
- Converting OpenShift TLS profiles to Go `crypto/tls` configuration
- Applying TLS settings to Kubernetes operator webhook servers, metrics endpoints, HTTP/gRPC clients and servers
- Using `github.com/openshift/library-go/pkg/crypto` utilities for cipher suite conversion
- Using the library-go configobserver pattern with `ObserveTLSSecurityProfile` for OpenShift operators
- Handling TLS profile changes with graceful restart (recommended over hot-reload)

## Implementation

1. Read the skill documentation from `plugins/openshift-tls-profile/skills/openshift-tls-profile/SKILL.md`
2. Based on the user's question or request, provide specific guidance from the skill
3. Include relevant code examples and implementation patterns
4. Reference OpenShift documentation and API types as needed

## Arguments

- $1: Optional question or implementation request. If not provided, displays an overview of the skill capabilities.

## Return Value

- **Format**: Guidance and code examples for implementing TLS security profiles

## Examples

1. **Get overview of TLS profile implementation**:
   ```
   /openshift-tls-profile:implement
   ```

2. **Ask about reading TLS profile from cluster**:
   ```
   /openshift-tls-profile:implement How do I read the TLS profile from the APIServer CR?
   ```

3. **Get help with gRPC server configuration**:
   ```
   /openshift-tls-profile:implement Show me how to configure a gRPC server with the TLS profile
   ```

4. **Understand profile change handling**:
   ```
   /openshift-tls-profile:implement How do I respond to TLS profile changes in the cluster?
   ```

5. **Use library-go configobserver pattern**:
   ```
   /openshift-tls-profile:implement How do I use ObserveTLSSecurityProfile in my OpenShift operator?
   ```

6. **Use controller-runtime-common package**:
   ```
   /openshift-tls-profile:implement How do I use controller-runtime-common for TLS profile support?
   ```
