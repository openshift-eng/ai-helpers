# Gateway API Topology

## Summary

| Resource Type | Count |
|---------------|-------|
| GatewayClasses | 1 |
| Gateways | 1 |
| HTTPRoutes | 2 |
| GRPCRoutes | 0 |
| TCPRoutes | 0 |
| TLSRoutes | 0 |
| Route Rules | 4 |
| Backend Services | 2 |
| Pod Endpoints | 2 |
| ReferenceGrants | 0 |

## Status

**Gateway API CRDs Installed:** Yes (5 CRDs)
- gateways.gateway.networking.k8s.io
- gatewayclasses.gateway.networking.k8s.io
- httproutes.gateway.networking.k8s.io
- grpcroutes.gateway.networking.k8s.io
- referencegrants.gateway.networking.k8s.io

**gwctl Available:** Yes

## Topology Diagram

```mermaid
graph TB
    %% GatewayClass at top (cluster-scoped)
    GC_ocp["GatewayClass: openshift-default<br/>Controller: openshift.io/gateway-controller<br/>Status: Unknown"]

    %% Per-Gateway subgraph with detailed layers
    subgraph gw1["Gateway: prod-gateway (pending)"]
        direction TB

        %% Listener Layer
        subgraph listeners1["Listeners"]
            L1_https["HTTPS:443<br/>(https)"]
            L1_http["HTTP:80<br/>(http)"]
        end

        %% Routes attached to this gateway
        subgraph routes1["Attached Routes"]
            HR1_api["HTTPRoute: api-route<br/>Host: api.example.com"]
            HR1_web["HTTPRoute: web-route<br/>Host: www.example.com"]
        end

        %% Route Rules with match conditions
        subgraph rules1["Routing Rules"]
            R1_0["Rule 0: PathPrefix:/v1"]
            R1_1a["Rule 1: PathPrefix:/v2"]
            R1_1b["Rule 1: PathPrefix:/<br/>Headers: x-api-version=2"]
            R2_0["Rule 0: PathPrefix:/"]
        end

        %% Backend Services with weights
        subgraph backends1["Backends"]
            SVC1_api["api-service:8080<br/>ClusterIP<br/>Weight: 80%"]
            SVC1_api_canary["api-service:8080<br/>(canary)<br/>Weight: 20%"]
            SVC1_web["web-service:80<br/>ClusterIP"]
        end

        %% Pod Endpoints
        subgraph pods1["Endpoints"]
            POD1_1["api-deployment-7c5fc66fcc-7fc4v<br/>10.132.0.45<br/>ready"]
            POD1_2["api-deployment-7c5fc66fcc-gqgpb<br/>10.132.0.46<br/>ready"]
        end

        %% Connections within gateway
        L1_https --> HR1_api
        L1_http --> HR1_web
        HR1_api --> R1_0
        HR1_api --> R1_1a
        HR1_api --> R1_1b
        HR1_web --> R2_0
        R1_0 -->|80%| SVC1_api
        R1_0 -->|20%| SVC1_api_canary
        R1_1a --> SVC1_api
        R1_1b --> SVC1_api
        R2_0 --> SVC1_web
        SVC1_api --> POD1_1
        SVC1_api --> POD1_2
    end

    %% GatewayClass to Gateway connection
    GC_ocp --> gw1

    %% Styles
    classDef gatewayclass fill:#e8f5e9,stroke:#2e7d32,stroke-width:2px,color:#000
    classDef listener fill:#e3f2fd,stroke:#1565c0,stroke-width:2px,color:#000
    classDef route fill:#fff3e0,stroke:#e65100,stroke-width:2px,color:#000
    classDef rule fill:#fce4ec,stroke:#c2185b,stroke-width:1px,color:#000
    classDef service fill:#f3e5f5,stroke:#6a1b9a,stroke-width:2px,color:#000
    classDef pod fill:#fff9c4,stroke:#f57f17,stroke-width:1px,color:#000

    class GC_ocp gatewayclass
    class L1_https,L1_http listener
    class HR1_api,HR1_web route
    class R1_0,R1_1a,R1_1b,R2_0 rule
    class SVC1_api,SVC1_api_canary,SVC1_web service
    class POD1_1,POD1_2 pod

    %% Subgraph Styling
    style listeners1 fill:#e1f5fe,stroke:#0277bd,stroke-width:2px
    style routes1 fill:#fff8e1,stroke:#ff8f00,stroke-width:2px
    style rules1 fill:#fce4ec,stroke:#c2185b,stroke-width:1px,stroke-dasharray: 3 3
    style backends1 fill:#f3e5f5,stroke:#7b1fa2,stroke-width:2px
    style pods1 fill:#fffde7,stroke:#fbc02d,stroke-width:1px,stroke-dasharray: 3 3
```

## Traffic Flow

### API Traffic (api.example.com)
1. **Listener:** HTTPS:443 (https)
2. **Route:** api-route
3. **Rules:**
   - PathPrefix:/v1 → api-service (80% main, 20% canary)
   - PathPrefix:/v2 → api-service
   - PathPrefix:/ with header x-api-version=2 → api-service
4. **Endpoints:**
   - api-deployment-7c5fc66fcc-7fc4v (10.132.0.45) - ready
   - api-deployment-7c5fc66fcc-gqgpb (10.132.0.46) - ready

### Web Traffic (www.example.com)
1. **Listener:** HTTP:80 (http)
2. **Route:** web-route
3. **Rules:**
   - PathPrefix:/ → web-service
4. **Endpoints:** None (0 pods)

## Resource Details

### GatewayClass: openshift-default
- **Controller:** openshift.io/gateway-controller
- **Status:** Unknown

### Gateway: default/prod-gateway
- **GatewayClass:** openshift-default
- **Listeners:**
  - HTTPS:443 (https)
  - HTTP:80 (http)
- **Address:** pending

### HTTPRoutes

| Route | Namespace | Hostnames | Parent Gateway | Backends |
|-------|-----------|-----------|----------------|----------|
| api-route | default | api.example.com | prod-gateway:https | api-service:8080 |
| web-route | default | www.example.com | prod-gateway:http | web-service:80 |

### Backend Services

| Service | Namespace | Type | Ports | Pods |
|---------|-----------|------|-------|------|
| api-service | default | ClusterIP | 8080->8080/TCP | 2 |
| web-service | default | ClusterIP | 80->8080/TCP | 0 |

---
*Generated by `/openshift:visualize-gateway-topology` with gwctl*
