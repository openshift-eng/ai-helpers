---
name: OpenShift TLS Security Profile Configuration
description: Use this skill to implement TLS security profiles for operators and workloads on OpenShift. Provides guidance on reading TLS config from APIServer CR and applying it to webhook/metrics servers, HTTP, and gRPC endpoints.
---

# OpenShift TLS Security Profile Configuration

This skill helps implement TLS security profiles for operators and workloads running on OpenShift. It provides complete guidance on reading TLS configuration from the APIServer custom resource and applying it consistently across all secured endpoints.

## Background

This skill implements the requirements defined in the [Centralized and Enforced TLS Configuration Enhancement](https://github.com/openshift/enhancements/pull/1910). The enhancement addresses the gap where many OpenShift components hardcode TLS settings or rely on library defaults rather than respecting cluster-wide TLS configuration. Key points:

- All components must honor the centralized TLS security profile from the APIServer CR
- This enables consistent cryptographic policy enforcement and Post-Quantum Cryptography (PQC) readiness

The API changes are implemented in [openshift/api#2680](https://github.com/openshift/api/pull/2680), which adds the `TLSAdherence` feature gate and `tlsAdherence` field to `apiserver.config.openshift.io/v1`.

### TLS Adherence Modes

The `tlsAdherence` field in the APIServer CR controls how strictly components adhere to the configured TLS security profile:

| Mode | Description |
|------|-------------|
| **Legacy** (default) | Backward-compatible behavior. Components attempt to honor the configured TLS profile but may fall back to their individual defaults if conflicts arise. Intended for clusters that need to maintain compatibility during migration. |
| **Strict** | Enforces strict adherence to the TLS configuration. All components must honor the configured profile without fallbacks. Recommended for security-conscious deployments and required for certain compliance frameworks. |

**Feature Gate:** The `TLSAdherence` feature gate controls this functionality. It is currently enabled in `DevPreviewNoUpgrade` and `TechPreviewNoUpgrade`.

**Implementation Note:** When implementing TLS profile support in your operator, ensure your component works correctly in both modes. In `Strict` mode, components that fail to apply the configured TLS profile should report degraded status rather than silently falling back to defaults.

### TLS Profile Sources

**Default Source: API Server Configuration**

Most components should use the API Server configuration as their TLS profile source. This is the default and preferred option. If you're unsure which source to use, start with the API Server configuration.

**Order of Precedence** (use only if you have a specific reason to deviate from API Server):

| Source | When to Use |
|--------|-------------|
| **API Server** (default) | Use this by default. Most OpenShift operators use library-go's apiserver config observer pattern, which automatically observes the API Server TLS profile. |
| **Kubelet** | Only use if your component is specifically running on the kubelet and needs to match kubelet's TLS settings. |
| **Ingress Controller** | Only use if your component is specifically handling ingress traffic and needs to match the ingress controller's TLS settings. |

**If Hardcoded TLS Exists in Code:**

Remove hardcoded TLS configurations and update your component to fetch TLS settings from one of the central configuration sources:

1. **Default: API Server configuration** - Use this for most components. This is the default and preferred option.
2. **Kubelet configuration** - Only use if your component is specifically running on the kubelet and needs to match kubelet's TLS settings.
3. **Ingress controller configuration** - Only use if your component is specifically handling ingress traffic and needs to match the ingress controller's TLS settings.

## When to Use This Skill

Use this skill when:
- Implementing TLS security profiles in a Kubernetes operator running on OpenShift
- Configuring webhook servers and metrics endpoints with cluster-wide TLS settings
- Setting up HTTP or gRPC clients/servers that need to comply with OpenShift TLS policies
- Converting OpenShift TLS profile types to Go `crypto/tls` configuration
- Troubleshooting TLS-related connection issues in OpenShift clusters

## Recommended: Use controller-runtime-common Package

For operators using controller-runtime, the **recommended approach** is to use the official package:

```
github.com/openshift/controller-runtime-common/pkg/tls
```

This package provides all necessary utilities for TLS profile implementation:

### Quick Start Example

```go
package main

import (
	"context"
	"crypto/tls"
	"os"

	configv1 "github.com/openshift/api/config/v1"
	openshifttls "github.com/openshift/controller-runtime-common/pkg/tls"
	"k8s.io/apimachinery/pkg/runtime"
	utilruntime "k8s.io/apimachinery/pkg/util/runtime"
	clientgoscheme "k8s.io/client-go/kubernetes/scheme"
	ctrl "sigs.k8s.io/controller-runtime"
	"sigs.k8s.io/controller-runtime/pkg/client"
	metricsserver "sigs.k8s.io/controller-runtime/pkg/metrics/server"
	"sigs.k8s.io/controller-runtime/pkg/webhook"
)

var scheme = runtime.NewScheme()

func init() {
	utilruntime.Must(clientgoscheme.AddToScheme(scheme))
	utilruntime.Must(configv1.AddToScheme(scheme))
}

func main() {
	// Create a cancellable context for graceful shutdown on TLS profile changes
	ctx, cancel := context.WithCancel(ctrl.SetupSignalHandler())
	defer cancel()

	cfg := ctrl.GetConfigOrDie()

	// Create a temporary client to fetch initial TLS profile
	tempClient, err := client.New(cfg, client.Options{Scheme: scheme})
	if err != nil {
		os.Exit(1)
	}

	// Fetch the TLS profile from APIServer CR
	tlsProfileSpec, err := openshifttls.FetchAPIServerTLSProfile(ctx, tempClient)
	if err != nil {
		os.Exit(1)
	}

	// Convert to TLSOpts function for controller-runtime
	tlsOpts, unsupportedCiphers := openshifttls.NewTLSConfigFromProfile(tlsProfileSpec)
	if len(unsupportedCiphers) > 0 {
		// Log warning about unsupported ciphers
	}

	mgr, err := ctrl.NewManager(cfg, ctrl.Options{
		Scheme: scheme,
		Metrics: metricsserver.Options{
			BindAddress:   ":8443",
			SecureServing: true,
			FilterProvider: filters.WithAuthenticationAndAuthorization,
			TLSOpts:       []func(*tls.Config){tlsOpts},
		},
		WebhookServer: webhook.NewServer(webhook.Options{
			Port:    9443,
			TLSOpts: []func(*tls.Config){tlsOpts},
		}),
	})
	if err != nil {
		os.Exit(1)
	}

	// Set up the TLS profile watcher to trigger graceful shutdown on changes
	watcher := &openshifttls.SecurityProfileWatcher{
		Client:                mgr.GetClient(),
		InitialTLSProfileSpec: tlsProfileSpec,
		OnProfileChange: func(ctx context.Context, old, new configv1.TLSProfileSpec) {
			// Cancel context to trigger graceful shutdown and reload
			cancel()
		},
	}
	if err := watcher.SetupWithManager(mgr); err != nil {
		os.Exit(1)
	}

	if err := mgr.Start(ctx); err != nil {
		os.Exit(1)
	}
}
```

### Package Functions

| Function | Purpose |
|----------|---------|
| `FetchAPIServerTLSProfile(ctx, client)` | Fetches TLS profile spec from APIServer CR, returns default (Intermediate) if not set |
| `GetTLSProfileSpec(profile)` | Resolves profile type (Old/Intermediate/Modern/Custom) to `TLSProfileSpec` |
| `NewTLSConfigFromProfile(spec)` | Returns a `func(*tls.Config)` for controller-runtime's TLSOpts + list of unsupported ciphers |
| `SecurityProfileWatcher` | Controller that watches APIServer and triggers callback on TLS profile changes |

### SecurityProfileWatcher

The `SecurityProfileWatcher` is a controller that watches the APIServer CR and invokes a callback when the TLS profile changes:

```go
watcher := &openshifttls.SecurityProfileWatcher{
	Client:                mgr.GetClient(),
	InitialTLSProfileSpec: initialProfile,
	OnProfileChange: func(ctx context.Context, old, new configv1.TLSProfileSpec) {
		// Common pattern: cancel context to trigger graceful shutdown
		// The operator will restart and pick up the new TLS configuration
		cancel()
	},
}
if err := watcher.SetupWithManager(mgr); err != nil {
	return err
}
```

**Note:** The watcher handles predicates internally - it only watches the "cluster" APIServer object and compares profile changes using `reflect.DeepEqual`.

### Restart vs Hot-Reload Trade-offs

| Approach | Restart Required | Existing Connections | Recommendation |
|----------|------------------|---------------------|----------------|
| **SecurityProfileWatcher** (Option A) | Yes - graceful shutdown | All connections use new TLS settings after restart | **Recommended** - ensures consistent TLS policy across all connections |
| **GetConfigForClient** (Option C) | No | **Not updated** - only new connections use new settings | Use only when restarts are not acceptable |

**Why SecurityProfileWatcher is recommended:**
- TLS profile changes are cluster-level security policy changes that should apply uniformly
- `GetConfigForClient` leaves existing long-lived connections using the old TLS configuration
- Graceful shutdown ensures all connections are re-established with the correct TLS settings
- Simpler implementation using the official package

## Requirements

Operators implementing TLS security profiles must satisfy these requirements:

1. **Read TLS profile from APIServer CR**: Fetch configuration from `apiservers.config.openshift.io/cluster`
2. **Apply to all TLS endpoints**: Webhook server, metrics server, and any HTTP/gRPC clients or servers
3. **Respond to profile changes**: If the TLS profile is updated in the cluster, the component should pick up the changes (may require restart depending on implementation)

### Handling Profile Changes

There are several approaches to respond to TLS profile changes:

**Option A: Use SecurityProfileWatcher (Recommended for controller-runtime)**

The official `github.com/openshift/controller-runtime-common/pkg/tls` package provides a ready-to-use watcher. See the "Recommended: Use controller-runtime-common Package" section above.

**Option B: Watch from Existing Controller**

If your operator manages operands that need TLS configuration, watch the APIServer resource from your existing controller. This triggers operand reconciliation when the TLS profile changes, allowing you to update operand deployments with the new TLS settings:

```go
package controller

import (
	"context"
	"reflect"

	configv1 "github.com/openshift/api/config/v1"
	"k8s.io/apimachinery/pkg/runtime"
	"k8s.io/apimachinery/pkg/types"
	ctrl "sigs.k8s.io/controller-runtime"
	"sigs.k8s.io/controller-runtime/pkg/builder"
	"sigs.k8s.io/controller-runtime/pkg/client"
	"sigs.k8s.io/controller-runtime/pkg/event"
	"sigs.k8s.io/controller-runtime/pkg/handler"
	"sigs.k8s.io/controller-runtime/pkg/predicate"
	"sigs.k8s.io/controller-runtime/pkg/reconcile"

	myv1 "myoperator/api/v1"
)

type MyOperandReconciler struct {
	client.Client
	Scheme *runtime.Scheme
}

func (r *MyOperandReconciler) Reconcile(ctx context.Context, req ctrl.Request) (ctrl.Result, error) {
	// Fetch operand
	operand := &myv1.MyOperand{}
	if err := r.Get(ctx, req.NamespacedName, operand); err != nil {
		return ctrl.Result{}, client.IgnoreNotFound(err)
	}

	// Fetch current TLS profile
	profile, err := GetTLSSecurityProfile(ctx, r.Client)
	if err != nil {
		return ctrl.Result{}, err
	}

	// Apply TLS configuration to operand's deployment/pods
	// This could involve updating a ConfigMap, Secret, or Deployment annotation
	// to trigger a rolling restart of operand pods with new TLS settings
	if err := r.reconcileOperandTLS(ctx, operand, profile); err != nil {
		return ctrl.Result{}, err
	}

	return ctrl.Result{}, nil
}

func (r *MyOperandReconciler) SetupWithManager(mgr ctrl.Manager) error {
	return ctrl.NewControllerManagedBy(mgr).
		For(&myv1.MyOperand{}).
		// Watch APIServer and trigger reconcile for all operands when TLS profile changes
		Watches(
			&configv1.APIServer{},
			handler.EnqueueRequestsFromMapFunc(r.mapAPIServerToOperands),
			builder.WithPredicates(tlsProfileChangedPredicate()),
		).
		Complete(r)
}

// mapAPIServerToOperands returns reconcile requests for all operands when APIServer changes
func (r *MyOperandReconciler) mapAPIServerToOperands(ctx context.Context, obj client.Object) []reconcile.Request {
	// Only react to the "cluster" APIServer
	if obj.GetName() != "cluster" {
		return nil
	}

	// List all operands and trigger reconcile for each
	var operands myv1.MyOperandList
	if err := r.List(ctx, &operands); err != nil {
		return nil
	}

	requests := make([]reconcile.Request, len(operands.Items))
	for i, op := range operands.Items {
		requests[i] = reconcile.Request{
			NamespacedName: types.NamespacedName{
				Name:      op.Name,
				Namespace: op.Namespace,
			},
		}
	}
	return requests
}

// tlsProfileChangedPredicate filters events to only TLS profile changes
func tlsProfileChangedPredicate() predicate.Predicate {
	return predicate.Funcs{
		CreateFunc: func(e event.CreateEvent) bool {
			return e.Object.GetName() == "cluster"
		},
		UpdateFunc: func(e event.UpdateEvent) bool {
			if e.ObjectNew.GetName() != "cluster" {
				return false
			}
			oldAPI, ok := e.ObjectOld.(*configv1.APIServer)
			if !ok {
				return false
			}
			newAPI, ok := e.ObjectNew.(*configv1.APIServer)
			if !ok {
				return false
			}
			// Only reconcile if TLS profile actually changed
			return !reflect.DeepEqual(
				oldAPI.Spec.TLSSecurityProfile,
				newAPI.Spec.TLSSecurityProfile,
			)
		},
		DeleteFunc: func(e event.DeleteEvent) bool {
			return false
		},
		GenericFunc: func(e event.GenericEvent) bool {
			return false
		},
	}
}

func (r *MyOperandReconciler) reconcileOperandTLS(
	ctx context.Context,
	operand *myv1.MyOperand,
	profile *configv1.TLSSecurityProfile,
) error {
	// Update operand deployment with new TLS settings
	// For example, update an annotation to trigger rolling restart:
	//
	// deployment.Spec.Template.Annotations["tls-profile-hash"] = hashTLSProfile(profile)
	//
	// Or update a ConfigMap/Secret that the operand mounts
	return nil
}
```

This approach is efficient because:
- Uses predicates to filter only TLS profile changes (ignores other APIServer updates)
- Integrates with existing controller logic
- Automatically reconciles all operands when the profile changes
- Follows standard controller-runtime patterns

**Option C: Dynamic TLS Config Update (Not Recommended)**

An alternative approach uses Go's `GetConfigForClient` callback to dynamically return TLS configuration for each new connection without requiring a restart. However, this approach is **not recommended** because:

- **Existing connections are not affected** - they continue using the old TLS configuration until they disconnect
- Long-lived connections may remain on outdated TLS settings indefinitely
- TLS profile changes are security policy changes that should apply uniformly to all connections

For consistent TLS policy enforcement, use Option A (SecurityProfileWatcher with graceful restart) or Option B (watch and reconcile) instead.

**Option D: For OpenShift Operators (configobserver pattern)**

This is the recommended approach for OpenShift operators using the library-go configobserver pattern. Use library-go's `ObserveTLSSecurityProfile` function from the apiserver config observer package. This function:

- Observes the API Server's TLSSecurityProfile from the cluster configuration (via `APIServerLister().Get("cluster")`) - this is the default source for all components
- Converts OpenSSL cipher names to IANA names (used by Kubernetes ServingInfo configuration) using `crypto.OpenSSLToIANACipherSuites`
- Sets `servingInfo.minTLSVersion` and `servingInfo.cipherSuites` in the observed config
- Returns the configuration as a `map[string]interface{}` in the format expected by your operator's observed config
- Centralizes profile mappings in library-go to ensure all components use consistent TLS profile handling

```go
package configobserver

import (
	"github.com/openshift/library-go/pkg/operator/configobserver"
	"github.com/openshift/library-go/pkg/operator/configobserver/apiserver"
	"github.com/openshift/library-go/pkg/operator/events"
)

// In your config observer controller's ObserveConfig method
func (c *MyConfigObserver) ObserveConfig(
	listers configobserver.Listers,
	recorder events.Recorder,
	existingConfig map[string]interface{},
) (map[string]interface{}, []error) {
	// ObserveTLSSecurityProfile observes APIServer.Spec.TLSSecurityProfile and sets
	// servingInfo.minTLSVersion and servingInfo.cipherSuites in observedConfig
	observedConfig, errs := apiserver.ObserveTLSSecurityProfile(listers, recorder, existingConfig)
	// ... merge with other observed config
	return observedConfig, errs
}
```

## TLS Profile Types

OpenShift supports four TLS profile types based on [Mozilla's Server Side TLS recommendations](https://wiki.mozilla.org/Security/Server_Side_TLS):

| Profile | Min TLS Version | Description |
|---------|-----------------|-------------|
| Old | TLS 1.0 | Legacy compatibility, not recommended for production |
| Intermediate (default) | TLS 1.2 | Recommended for general use, balances security and compatibility |
| Modern | TLS 1.3 | Highest security, may not work with older clients |
| Custom | Configurable | User-defined ciphers and minimum TLS version |

**Default Profile:** When `spec.tlsSecurityProfile` is not set in the APIServer CR, the **Intermediate** profile is used as the default. This provides a good balance between security and compatibility.

**Note:** In Go, cipher suites are not configurable for TLS 1.3 - they are automatically selected by the runtime.

## APIServer Custom Resource

The TLS profile is configured in the `APIServer` custom resource named `cluster`. If `spec.tlsSecurityProfile` is not specified, the **Intermediate** profile is used by default.

```yaml
apiVersion: config.openshift.io/v1
kind: APIServer
metadata:
  name: cluster
spec:
  audit:
    profile: Default
  # tlsSecurityProfile is optional. If not set, defaults to Intermediate profile.
  tlsSecurityProfile:
    # type can be: Old, Intermediate, Modern, or Custom
    type: Intermediate
    # Only one of the following should be set based on type:
    old: {}
    intermediate: {}
    modern: {}
    custom:
      ciphers:
        - TLS_ECDHE_RSA_WITH_AES_128_GCM_SHA256
        - TLS_ECDHE_RSA_WITH_AES_256_GCM_SHA384
      minTLSVersion: VersionTLS12
```

**Reference:**
- [APIServer Config API Reference](https://docs.redhat.com/en/documentation/openshift_container_platform/4.21/html/config_apis/apiserver-config-openshift-io-v1#spec)
- [APIServer CR Spec Example](https://github.com/robszumski/kubernetes-object-specs/blob/main/apiservers.config.openshift.io.yaml#L210)
- [TLSSecurityProfile Type Definition](https://github.com/openshift/api/blob/master/config/v1/types_tlssecurityprofile.go#L211)

## Query Commands

Check the current TLS security profile in your cluster:

```bash
# Get the full APIServer configuration
oc get apiserver cluster -o yaml

# Get just the TLS security profile (empty output means default Intermediate profile is used)
oc get apiserver cluster -o jsonpath='{.spec.tlsSecurityProfile}' | jq .

# Check the effective TLS profile type (empty means Intermediate default)
oc get apiserver cluster -o jsonpath='{.spec.tlsSecurityProfile.type}'
```

**Note:** If the above commands return empty output, the cluster is using the default **Intermediate** profile.

## Implementation Steps

### Step 1: Fetch TLS Profile from APIServer CR

Create a function to retrieve the TLS security profile from the cluster:

```go
package tlsprofile

import (
	"context"
	"fmt"

	configv1 "github.com/openshift/api/config/v1"
	"k8s.io/apimachinery/pkg/types"
	"sigs.k8s.io/controller-runtime/pkg/client"
)

// GetTLSSecurityProfile fetches the TLS security profile from the APIServer CR
func GetTLSSecurityProfile(ctx context.Context, c client.Client) (*configv1.TLSSecurityProfile, error) {
	apiServer := &configv1.APIServer{}
	if err := c.Get(ctx, types.NamespacedName{Name: "cluster"}, apiServer); err != nil {
		return nil, fmt.Errorf("failed to get APIServer cluster: %w", err)
	}

	if apiServer.Spec.TLSSecurityProfile == nil {
		// Return default Intermediate profile if not set
		return &configv1.TLSSecurityProfile{
			Type:         configv1.TLSProfileIntermediateType,
			Intermediate: &configv1.IntermediateTLSProfile{},
		}, nil
	}

	return apiServer.Spec.TLSSecurityProfile, nil
}
```

### Step 2: Convert TLS Profile to Go crypto/tls Configuration

Create a conversion function that transforms the OpenShift TLS profile into Go's `tls.Config`:

```go
package tlsprofile

import (
	"crypto/tls"
	"fmt"

	configv1 "github.com/openshift/api/config/v1"
	"github.com/openshift/library-go/pkg/crypto"
)

// TLSConfigFromProfile converts an OpenShift TLS security profile to a tls.Config
func TLSConfigFromProfile(profile *configv1.TLSSecurityProfile) (*tls.Config, error) {
	if profile == nil {
		profile = &configv1.TLSSecurityProfile{
			Type:         configv1.TLSProfileIntermediateType,
			Intermediate: &configv1.IntermediateTLSProfile{},
		}
	}

	var minVersion configv1.TLSProtocolVersion
	var ciphers []string

	switch profile.Type {
	case configv1.TLSProfileOldType:
		minVersion = configv1.TLSProfiles[configv1.TLSProfileOldType].MinTLSVersion
		ciphers = configv1.TLSProfiles[configv1.TLSProfileOldType].Ciphers
	case configv1.TLSProfileIntermediateType:
		minVersion = configv1.TLSProfiles[configv1.TLSProfileIntermediateType].MinTLSVersion
		ciphers = configv1.TLSProfiles[configv1.TLSProfileIntermediateType].Ciphers
	case configv1.TLSProfileModernType:
		minVersion = configv1.TLSProfiles[configv1.TLSProfileModernType].MinTLSVersion
		ciphers = configv1.TLSProfiles[configv1.TLSProfileModernType].Ciphers
	case configv1.TLSProfileCustomType:
		if profile.Custom == nil {
			return nil, fmt.Errorf("custom TLS profile specified but no custom configuration provided")
		}
		minVersion = profile.Custom.MinTLSVersion
		ciphers = profile.Custom.Ciphers
	default:
		return nil, fmt.Errorf("unknown TLS profile type: %s", profile.Type)
	}

	tlsMinVersion, err := tlsVersionToUint16(minVersion)
	if err != nil {
		return nil, err
	}

	// Convert OpenSSL cipher names to IANA names, then to Go constants
	ianaCiphers := crypto.OpenSSLToIANACipherSuites(ciphers)
	cipherSuites := crypto.CipherSuitesOrDie(ianaCiphers)

	return &tls.Config{
		MinVersion:   tlsMinVersion,
		CipherSuites: cipherSuites,
	}, nil
}

// tlsVersionToUint16 converts OpenShift TLS version string to Go tls constant
func tlsVersionToUint16(version configv1.TLSProtocolVersion) (uint16, error) {
	switch version {
	case configv1.VersionTLS10:
		return tls.VersionTLS10, nil
	case configv1.VersionTLS11:
		return tls.VersionTLS11, nil
	case configv1.VersionTLS12:
		return tls.VersionTLS12, nil
	case configv1.VersionTLS13:
		return tls.VersionTLS13, nil
	default:
		return 0, fmt.Errorf("unknown TLS version: %s", version)
	}
}
```

### Step 3: Apply to Controller-Runtime Webhook and Metrics Servers

Configure the controller-runtime manager with the TLS settings:

```go
package main

import (
	"context"
	"crypto/tls"
	"os"

	configv1 "github.com/openshift/api/config/v1"
	"k8s.io/apimachinery/pkg/runtime"
	utilruntime "k8s.io/apimachinery/pkg/util/runtime"
	clientgoscheme "k8s.io/client-go/kubernetes/scheme"
	ctrl "sigs.k8s.io/controller-runtime"
	"sigs.k8s.io/controller-runtime/pkg/client"
	metricsserver "sigs.k8s.io/controller-runtime/pkg/metrics/server"
	"sigs.k8s.io/controller-runtime/pkg/webhook"

	"myoperator/pkg/tlsprofile"
)

var scheme = runtime.NewScheme()

func init() {
	utilruntime.Must(clientgoscheme.AddToScheme(scheme))
	utilruntime.Must(configv1.AddToScheme(scheme))
}

func main() {
	ctx := context.Background()

	// Create a temporary client to fetch TLS profile
	cfg := ctrl.GetConfigOrDie()
	tempClient, err := client.New(cfg, client.Options{Scheme: scheme})
	if err != nil {
		os.Exit(1)
	}

	// Fetch and convert TLS profile
	profile, err := tlsprofile.GetTLSSecurityProfile(ctx, tempClient)
	if err != nil {
		os.Exit(1)
	}

	tlsConfig, err := tlsprofile.TLSConfigFromProfile(profile)
	if err != nil {
		os.Exit(1)
	}

	// Create TLS options function
	tlsOpts := func(config *tls.Config) {
		config.MinVersion = tlsConfig.MinVersion
		config.CipherSuites = tlsConfig.CipherSuites
	}

	mgr, err := ctrl.NewManager(cfg, ctrl.Options{
		Scheme: scheme,
		Metrics: metricsserver.Options{
			BindAddress:   ":8443",
			SecureServing: true,
			TLSOpts:       []func(*tls.Config){tlsOpts},
		},
		WebhookServer: webhook.NewServer(webhook.Options{
			Port:    9443,
			TLSOpts: []func(*tls.Config){tlsOpts},
		}),
	})
	if err != nil {
		os.Exit(1)
	}

	if err := mgr.Start(ctrl.SetupSignalHandler()); err != nil {
		os.Exit(1)
	}
}
```

### Step 4: Apply to HTTP Client

Configure an HTTP client with the TLS profile:

```go
package httpclient

import (
	"crypto/tls"
	"crypto/x509"
	"net/http"
	"os"
	"time"

	configv1 "github.com/openshift/api/config/v1"
	"myoperator/pkg/tlsprofile"
)

// NewHTTPClientWithTLSProfile creates an HTTP client configured with the TLS profile
func NewHTTPClientWithTLSProfile(profile *configv1.TLSSecurityProfile, caCertPath string) (*http.Client, error) {
	tlsConfig, err := tlsprofile.TLSConfigFromProfile(profile)
	if err != nil {
		return nil, err
	}

	// Load CA certificate if provided
	if caCertPath != "" {
		caCert, err := os.ReadFile(caCertPath)
		if err != nil {
			return nil, err
		}
		caCertPool := x509.NewCertPool()
		caCertPool.AppendCertsFromPEM(caCert)
		tlsConfig.RootCAs = caCertPool
	}

	return &http.Client{
		Timeout: 30 * time.Second,
		Transport: &http.Transport{
			TLSClientConfig: tlsConfig,
		},
	}, nil
}
```

### Step 5: Apply to HTTP Server

Configure an HTTP server with the TLS profile:

```go
package httpserver

import (
	"crypto/tls"
	"net/http"

	configv1 "github.com/openshift/api/config/v1"
	"myoperator/pkg/tlsprofile"
)

// NewHTTPServerWithTLSProfile creates an HTTP server configured with the TLS profile
func NewHTTPServerWithTLSProfile(
	addr string,
	handler http.Handler,
	profile *configv1.TLSSecurityProfile,
	certFile, keyFile string,
) (*http.Server, error) {
	tlsConfig, err := tlsprofile.TLSConfigFromProfile(profile)
	if err != nil {
		return nil, err
	}

	// Add recommended server settings
	// Note: PreferServerCipherSuites is deprecated in Go 1.18+ and ignored
	tlsConfig.CurvePreferences = []tls.CurveID{tls.CurveP256, tls.X25519}

	server := &http.Server{
		Addr:      addr,
		Handler:   handler,
		TLSConfig: tlsConfig,
		// Disable HTTP/2 if not needed
		TLSNextProto: make(map[string]func(*http.Server, *tls.Conn, http.Handler)),
	}

	return server, nil
}

// Example usage:
// server, err := NewHTTPServerWithTLSProfile(":8443", mux, profile, "server.crt", "server.key")
// if err != nil { ... }
// err = server.ListenAndServeTLS("server.crt", "server.key")
```

### Step 6: Apply to gRPC Client

Configure a gRPC client with the TLS profile:

```go
package grpcclient

import (
	"crypto/tls"
	"crypto/x509"
	"os"

	configv1 "github.com/openshift/api/config/v1"
	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials"

	"myoperator/pkg/tlsprofile"
)

// NewGRPCClientConnWithTLSProfile creates a gRPC client connection with the TLS profile
func NewGRPCClientConnWithTLSProfile(
	target string,
	profile *configv1.TLSSecurityProfile,
	caCertPath string,
) (*grpc.ClientConn, error) {
	tlsConfig, err := tlsprofile.TLSConfigFromProfile(profile)
	if err != nil {
		return nil, err
	}

	// Load CA certificate
	caCert, err := os.ReadFile(caCertPath)
	if err != nil {
		return nil, err
	}
	caCertPool := x509.NewCertPool()
	caCertPool.AppendCertsFromPEM(caCert)
	tlsConfig.RootCAs = caCertPool

	creds := credentials.NewTLS(tlsConfig)
	conn, err := grpc.Dial(target, grpc.WithTransportCredentials(creds))
	if err != nil {
		return nil, err
	}

	return conn, nil
}
```

### Step 7: Apply to gRPC Server

Configure a gRPC server with the TLS profile:

```go
package grpcserver

import (
	"crypto/tls"

	configv1 "github.com/openshift/api/config/v1"
	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials"

	"myoperator/pkg/tlsprofile"
)

// NewGRPCServerWithTLSProfile creates a gRPC server configured with the TLS profile
func NewGRPCServerWithTLSProfile(
	profile *configv1.TLSSecurityProfile,
	certFile, keyFile string,
) (*grpc.Server, error) {
	tlsConfig, err := tlsprofile.TLSConfigFromProfile(profile)
	if err != nil {
		return nil, err
	}

	// Load server certificate
	cert, err := tls.LoadX509KeyPair(certFile, keyFile)
	if err != nil {
		return nil, err
	}
	tlsConfig.Certificates = []tls.Certificate{cert}

	creds := credentials.NewTLS(tlsConfig)
	server := grpc.NewServer(grpc.Creds(creds))

	return server, nil
}
```

## OpenShift library-go Crypto Utilities

The `github.com/openshift/library-go/pkg/crypto` package provides essential utilities for working with TLS in OpenShift. These functions simplify converting between OpenShift TLS profile configurations and Go's `crypto/tls` types.

### Why Use library-go/pkg/crypto

- **Cipher suite name conversion**: OpenShift's `configv1.TLSProfiles` uses OpenSSL-format cipher names, not Go constants
- **Validated defaults**: Default ciphers align with Mozilla's Intermediate TLS profile
- **Consistent behavior**: Same utilities used by OpenShift core components

### Key Functions

| Function | Purpose |
|----------|---------|
| `TLSVersion(name string) (uint16, error)` | Convert TLS version name (e.g., "VersionTLS12") to Go constant |
| `TLSVersionOrDie(name string) uint16` | Same as above, panics on error |
| `DefaultTLSVersion() uint16` | Returns default TLS version (TLS 1.2) |
| `CipherSuite(name string) (uint16, error)` | Convert cipher suite name to Go constant |
| `CipherSuitesOrDie(names []string) []uint16` | Convert multiple cipher names, panics on error |
| `OpenSSLToIANACipherSuites(ciphers []string) []string` | Map OpenSSL cipher names to IANA names |
| `SecureTLSConfig(config *tls.Config) *tls.Config` | Apply secure defaults to a TLS config |
| `DefaultCiphers() []uint16` | Get default cipher suites for Intermediate profile |

### Example: Using library-go for Cipher Conversion

The `configv1.TLSProfiles` map contains cipher names in OpenSSL format. Use `OpenSSLToIANACipherSuites` to convert them:

```go
package tlsprofile

import (
	"crypto/tls"
	"fmt"

	configv1 "github.com/openshift/api/config/v1"
	"github.com/openshift/library-go/pkg/crypto"
)

// TLSConfigFromProfileWithLibraryGo uses library-go utilities for conversion
func TLSConfigFromProfileWithLibraryGo(profile *configv1.TLSSecurityProfile) (*tls.Config, error) {
	if profile == nil {
		// Use library-go defaults
		return &tls.Config{
			MinVersion:   crypto.DefaultTLSVersion(),
			CipherSuites: crypto.DefaultCiphers(),
		}, nil
	}

	var minVersionStr string
	var openSSLCiphers []string

	switch profile.Type {
	case configv1.TLSProfileOldType:
		spec := configv1.TLSProfiles[configv1.TLSProfileOldType]
		minVersionStr = string(spec.MinTLSVersion)
		openSSLCiphers = spec.Ciphers
	case configv1.TLSProfileIntermediateType:
		spec := configv1.TLSProfiles[configv1.TLSProfileIntermediateType]
		minVersionStr = string(spec.MinTLSVersion)
		openSSLCiphers = spec.Ciphers
	case configv1.TLSProfileModernType:
		spec := configv1.TLSProfiles[configv1.TLSProfileModernType]
		minVersionStr = string(spec.MinTLSVersion)
		openSSLCiphers = spec.Ciphers
	case configv1.TLSProfileCustomType:
		if profile.Custom == nil {
			return nil, fmt.Errorf("custom profile without configuration")
		}
		minVersionStr = string(profile.Custom.MinTLSVersion)
		openSSLCiphers = profile.Custom.Ciphers
	default:
		return nil, fmt.Errorf("unknown profile type: %s", profile.Type)
	}

	// Use library-go to convert TLS version
	minVersion, err := crypto.TLSVersion(minVersionStr)
	if err != nil {
		return nil, fmt.Errorf("invalid TLS version %s: %w", minVersionStr, err)
	}

	// Convert OpenSSL cipher names to IANA names, then to Go constants
	ianaCiphers := crypto.OpenSSLToIANACipherSuites(openSSLCiphers)
	cipherSuites := crypto.CipherSuitesOrDie(ianaCiphers)

	return &tls.Config{
		MinVersion:   minVersion,
		CipherSuites: cipherSuites,
	}, nil
}
```

### Using SecureTLSConfig for Additional Hardening

Apply `SecureTLSConfig` to enforce secure defaults on any TLS configuration:

```go
package main

import (
	"crypto/tls"

	"github.com/openshift/library-go/pkg/crypto"
)

func createSecureTLSConfig() *tls.Config {
	// Start with custom or empty config
	config := &tls.Config{
		// Your settings here
	}

	// Apply library-go secure defaults
	// This enforces minimum security settings used by OpenShift
	return crypto.SecureTLSConfig(config)
}
```

## Additional Resources

- [OpenShift controller-runtime-common TLS Package](https://github.com/openshift/controller-runtime-common/tree/main/pkg/tls) - **Recommended package for controller-runtime operators**
- [OpenShift TLS Security Profiles Documentation](https://docs.openshift.com/container-platform/latest/security/tls-security-profiles.html)
- [Mozilla Server Side TLS](https://wiki.mozilla.org/Security/Server_Side_TLS)
- [OpenShift API Types - TLS Security Profile](https://github.com/openshift/api/blob/master/config/v1/types_tlssecurityprofile.go)
- [TLSSecurityProfile Type Definition](https://github.com/openshift/api/blob/master/config/v1/types_tlssecurityprofile.go#L211)
- [APIServer Config API Reference](https://docs.redhat.com/en/documentation/openshift_container_platform/4.21/html/config_apis/apiserver-config-openshift-io-v1#spec)
- [APIServer CR Spec Example](https://github.com/robszumski/kubernetes-object-specs/blob/main/apiservers.config.openshift.io.yaml#L210)
- [OpenShift library-go Crypto Package](https://pkg.go.dev/github.com/openshift/library-go/pkg/crypto)
- [Go crypto/tls Package](https://pkg.go.dev/crypto/tls)
- [controller-runtime Webhook Server](https://pkg.go.dev/sigs.k8s.io/controller-runtime/pkg/webhook)
- [TLS Configuration in OpenShift](https://access.redhat.com/articles/5348961)
- [TLS Adherence](https://github.com/openshift/api/pull/2680)
