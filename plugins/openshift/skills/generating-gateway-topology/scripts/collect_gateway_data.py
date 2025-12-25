#!/usr/bin/env python3
"""
collect_gateway_data.py - Collect Gateway API data from live cluster

Usage: collect_gateway_data.py <KUBECONFIG> <TMPDIR>

This script collects Gateway API data from a live Kubernetes cluster:
1. GatewayClasses - cluster-wide gateway implementations
2. Gateways - gateway instances with listeners
3. HTTPRoutes - HTTP routing rules
4. GRPCRoutes - gRPC routing rules
5. TCPRoutes - TCP routing rules
6. TLSRoutes - TLS passthrough routes
7. ReferenceGrants - cross-namespace permissions
8. Backend Services - services referenced by routes

Outputs (all files written to TMPDIR):
  - gateway_classes_detail.txt - name|controller|description|status
  - gateways_detail.txt - namespace|name|class|listeners|addresses|status
  - httproutes_detail.txt - namespace|name|hostnames|parent_refs|backend_refs
  - grpcroutes_detail.txt - namespace|name|parent_refs|backend_refs
  - tcproutes_detail.txt - namespace|name|parent_refs|backend_refs
  - tlsroutes_detail.txt - namespace|name|hostnames|parent_refs|backend_refs
  - backends_detail.txt - namespace|name|type|ports|pod_count
  - reference_grants_detail.txt - namespace|name|from_refs|to_refs

Exit codes:
  0 - Success (all or partial data collected)
  1 - Total failure (no data collected)

Requirements: Python 3.6+, kubectl in PATH, optionally gwctl
"""

import json
import os
import sys
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

from gateway_utils import (
    check_gateway_api_installed,
    collect_endpoint_slices,
    detect_gwctl,
    extract_route_rules,
    format_addresses,
    format_backend_refs,
    format_listeners,
    format_parent_refs,
    run_kubectl_json,
    safe_write_file,
)

# File name constants
_GATEWAY_CLASSES_FILE = "gateway_classes_detail.txt"
_GATEWAYS_FILE = "gateways_detail.txt"
_HTTPROUTES_FILE = "httproutes_detail.txt"
_GRPCROUTES_FILE = "grpcroutes_detail.txt"
_TCPROUTES_FILE = "tcproutes_detail.txt"
_TLSROUTES_FILE = "tlsroutes_detail.txt"
_BACKENDS_FILE = "backends_detail.txt"
_REFERENCE_GRANTS_FILE = "reference_grants_detail.txt"
_ROUTE_RULES_FILE = "route_rules_detail.txt"
_ENDPOINTS_FILE = "endpoints_detail.txt"


@dataclass
class CollectionStats:
    """Track collection statistics."""
    gateway_classes: int = 0
    gateways: int = 0
    httproutes: int = 0
    grpcroutes: int = 0
    tcproutes: int = 0
    tlsroutes: int = 0
    backends: int = 0
    reference_grants: int = 0
    route_rules: int = 0
    endpoints: int = 0
    errors: List[str] = field(default_factory=list)


class GatewayDataCollector:
    """Collect Gateway API data from live cluster."""

    def __init__(self, kubeconfig: str, tmpdir: str):
        self.kubeconfig = kubeconfig
        self.tmpdir = tmpdir
        self.stats = CollectionStats()
        self.gwctl_path = detect_gwctl()

        # Track backend references for collection
        self.backend_refs: Set[str] = set()  # "namespace/name"

        # Store detailed route rules for diagram generation
        self.route_rules_data: List[Dict] = []

        # Output files
        self.gateway_classes_file = os.path.join(tmpdir, _GATEWAY_CLASSES_FILE)
        self.gateways_file = os.path.join(tmpdir, _GATEWAYS_FILE)
        self.httproutes_file = os.path.join(tmpdir, _HTTPROUTES_FILE)
        self.grpcroutes_file = os.path.join(tmpdir, _GRPCROUTES_FILE)
        self.tcproutes_file = os.path.join(tmpdir, _TCPROUTES_FILE)
        self.tlsroutes_file = os.path.join(tmpdir, _TLSROUTES_FILE)
        self.backends_file = os.path.join(tmpdir, _BACKENDS_FILE)
        self.reference_grants_file = os.path.join(tmpdir, _REFERENCE_GRANTS_FILE)
        self.route_rules_file = os.path.join(tmpdir, _ROUTE_RULES_FILE)
        self.endpoints_file = os.path.join(tmpdir, _ENDPOINTS_FILE)

    def initialize_output_files(self):
        """Create/clear output files."""
        for filepath in [
            self.gateway_classes_file,
            self.gateways_file,
            self.httproutes_file,
            self.grpcroutes_file,
            self.tcproutes_file,
            self.tlsroutes_file,
            self.backends_file,
            self.reference_grants_file,
            self.route_rules_file,
            self.endpoints_file,
        ]:
            safe_write_file(filepath, "")

    def collect_gateway_classes(self) -> bool:
        """Collect GatewayClass resources."""
        print("  Collecting GatewayClasses...")

        data = run_kubectl_json(
            self.kubeconfig,
            "gatewayclasses.gateway.networking.k8s.io",
        )

        if data is None:
            self.stats.errors.append("Failed to collect GatewayClasses")
            return False

        lines = []
        for item in data.get("items", []):
            name = item.get("metadata", {}).get("name", "unknown")
            spec = item.get("spec", {})
            controller = spec.get("controllerName", "unknown")
            description = spec.get("description", "")

            # Get status
            status = item.get("status", {})
            conditions = status.get("conditions", [])
            status_str = "Unknown"
            for cond in conditions:
                if cond.get("type") == "Accepted":
                    status_str = cond.get("status", "Unknown")
                    break

            # Clean description (remove newlines, limit length)
            description = description.replace("\n", " ").replace("|", "-")[:100]

            lines.append(f"{name}|{controller}|{description}|{status_str}\n")
            self.stats.gateway_classes += 1

        if lines:
            safe_write_file(self.gateway_classes_file, "".join(lines))

        print(f"    ✓ Collected {self.stats.gateway_classes} GatewayClasses")
        return True

    def collect_gateways(self) -> bool:
        """Collect Gateway resources."""
        print("  Collecting Gateways...")

        data = run_kubectl_json(
            self.kubeconfig,
            "gateways.gateway.networking.k8s.io",
            all_namespaces=True,
        )

        if data is None:
            self.stats.errors.append("Failed to collect Gateways")
            return False

        lines = []
        for item in data.get("items", []):
            metadata = item.get("metadata", {})
            namespace = metadata.get("namespace", "default")
            name = metadata.get("name", "unknown")

            spec = item.get("spec", {})
            gateway_class = spec.get("gatewayClassName", "unknown")
            listeners = spec.get("listeners", [])

            status = item.get("status", {})
            addresses = status.get("addresses", [])

            # Format listeners and addresses
            listeners_str = format_listeners(listeners)
            addresses_str = format_addresses(addresses)

            # Get overall status
            conditions = status.get("conditions", [])
            status_str = "Unknown"
            for cond in conditions:
                if cond.get("type") in ["Accepted", "Programmed"]:
                    status_str = cond.get("status", "Unknown")
                    break

            lines.append(
                f"{namespace}|{name}|{gateway_class}|{listeners_str}|"
                f"{addresses_str}|{status_str}\n"
            )
            self.stats.gateways += 1

        if lines:
            safe_write_file(self.gateways_file, "".join(lines))

        print(f"    ✓ Collected {self.stats.gateways} Gateways")
        return True

    def _extract_backend_refs(self, rules: list, route_namespace: str):
        """Extract backend references from route rules."""
        for rule in rules or []:
            for backend_ref in rule.get("backendRefs", []):
                namespace = backend_ref.get("namespace", route_namespace)
                name = backend_ref.get("name", "")
                if name:
                    self.backend_refs.add(f"{namespace}/{name}")

    def collect_httproutes(self) -> bool:
        """Collect HTTPRoute resources."""
        print("  Collecting HTTPRoutes...")

        data = run_kubectl_json(
            self.kubeconfig,
            "httproutes.gateway.networking.k8s.io",
            all_namespaces=True,
        )

        if data is None:
            self.stats.errors.append("Failed to collect HTTPRoutes")
            return False

        lines = []
        rules_lines = []
        for item in data.get("items", []):
            metadata = item.get("metadata", {})
            namespace = metadata.get("namespace", "default")
            name = metadata.get("name", "unknown")

            spec = item.get("spec", {})
            hostnames = spec.get("hostnames", [])
            parent_refs = spec.get("parentRefs", [])
            rules = spec.get("rules", [])

            # Extract and track backend refs
            self._extract_backend_refs(rules, namespace)

            # Extract detailed route rules for enhanced diagram
            detailed_rules = extract_route_rules(rules, namespace)
            for rule in detailed_rules:
                # Store for later analysis
                self.route_rules_data.append({
                    "route_type": "HTTPRoute",
                    "route_namespace": namespace,
                    "route_name": name,
                    "hostnames": hostnames,
                    "parent_refs": parent_refs,
                    "rule": rule,
                })

                # Format rule for output file
                # Format: route_ns|route_name|rule_idx|match_type|match_value|backends
                for match in rule.get("matches", [{}]):
                    path_type = match.get("path_type", "PathPrefix")
                    path_value = match.get("path_value", "/")
                    headers = match.get("headers", "")
                    method = match.get("method", "")

                    match_str = f"{path_type}:{path_value}"
                    if headers:
                        match_str += f";headers={headers}"
                    if method:
                        match_str += f";method={method}"

                    # Format backends with weights
                    backends_with_weights = []
                    for backend in rule.get("backends", []):
                        bns = backend.get("namespace", namespace)
                        bname = backend.get("name", "?")
                        bport = backend.get("port", "")
                        weight = backend.get("weight", 1)
                        if bport:
                            backends_with_weights.append(
                                f"{bns}/{bname}:{bport}@{weight}"
                            )
                        else:
                            backends_with_weights.append(f"{bns}/{bname}@{weight}")

                    backends_str = ",".join(backends_with_weights) or "none"
                    rules_lines.append(
                        f"{namespace}|{name}|{rule['index']}|{match_str}|"
                        f"{backends_str}\n"
                    )
                    self.stats.route_rules += 1

            # Format for output
            hostnames_str = ", ".join(hostnames) if hostnames else "*"
            parent_refs_str = format_parent_refs(parent_refs)
            backend_refs_str = format_backend_refs(rules)

            lines.append(
                f"{namespace}|{name}|{hostnames_str}|{parent_refs_str}|"
                f"{backend_refs_str}\n"
            )
            self.stats.httproutes += 1

        if lines:
            safe_write_file(self.httproutes_file, "".join(lines))

        if rules_lines:
            safe_write_file(self.route_rules_file, "".join(rules_lines))

        print(f"    ✓ Collected {self.stats.httproutes} HTTPRoutes")
        print(f"    ✓ Extracted {self.stats.route_rules} route rules")
        return True

    def collect_grpcroutes(self) -> bool:
        """Collect GRPCRoute resources."""
        print("  Collecting GRPCRoutes...")

        data = run_kubectl_json(
            self.kubeconfig,
            "grpcroutes.gateway.networking.k8s.io",
            all_namespaces=True,
        )

        if data is None:
            # GRPCRoutes might not exist in cluster
            print("    ℹ️  GRPCRoutes not found or not accessible")
            return True

        lines = []
        for item in data.get("items", []):
            metadata = item.get("metadata", {})
            namespace = metadata.get("namespace", "default")
            name = metadata.get("name", "unknown")

            spec = item.get("spec", {})
            parent_refs = spec.get("parentRefs", [])
            rules = spec.get("rules", [])

            self._extract_backend_refs(rules, namespace)

            parent_refs_str = format_parent_refs(parent_refs)
            backend_refs_str = format_backend_refs(rules)

            lines.append(f"{namespace}|{name}|{parent_refs_str}|{backend_refs_str}\n")
            self.stats.grpcroutes += 1

        if lines:
            safe_write_file(self.grpcroutes_file, "".join(lines))

        print(f"    ✓ Collected {self.stats.grpcroutes} GRPCRoutes")
        return True

    def collect_tcproutes(self) -> bool:
        """Collect TCPRoute resources."""
        print("  Collecting TCPRoutes...")

        data = run_kubectl_json(
            self.kubeconfig,
            "tcproutes.gateway.networking.k8s.io",
            all_namespaces=True,
        )

        if data is None:
            print("    ℹ️  TCPRoutes not found or not accessible")
            return True

        lines = []
        for item in data.get("items", []):
            metadata = item.get("metadata", {})
            namespace = metadata.get("namespace", "default")
            name = metadata.get("name", "unknown")

            spec = item.get("spec", {})
            parent_refs = spec.get("parentRefs", [])
            rules = spec.get("rules", [])

            self._extract_backend_refs(rules, namespace)

            parent_refs_str = format_parent_refs(parent_refs)
            backend_refs_str = format_backend_refs(rules)

            lines.append(f"{namespace}|{name}|{parent_refs_str}|{backend_refs_str}\n")
            self.stats.tcproutes += 1

        if lines:
            safe_write_file(self.tcproutes_file, "".join(lines))

        print(f"    ✓ Collected {self.stats.tcproutes} TCPRoutes")
        return True

    def collect_tlsroutes(self) -> bool:
        """Collect TLSRoute resources."""
        print("  Collecting TLSRoutes...")

        data = run_kubectl_json(
            self.kubeconfig,
            "tlsroutes.gateway.networking.k8s.io",
            all_namespaces=True,
        )

        if data is None:
            print("    ℹ️  TLSRoutes not found or not accessible")
            return True

        lines = []
        for item in data.get("items", []):
            metadata = item.get("metadata", {})
            namespace = metadata.get("namespace", "default")
            name = metadata.get("name", "unknown")

            spec = item.get("spec", {})
            hostnames = spec.get("hostnames", [])
            parent_refs = spec.get("parentRefs", [])
            rules = spec.get("rules", [])

            self._extract_backend_refs(rules, namespace)

            hostnames_str = ", ".join(hostnames) if hostnames else "*"
            parent_refs_str = format_parent_refs(parent_refs)
            backend_refs_str = format_backend_refs(rules)

            lines.append(
                f"{namespace}|{name}|{hostnames_str}|{parent_refs_str}|"
                f"{backend_refs_str}\n"
            )
            self.stats.tlsroutes += 1

        if lines:
            safe_write_file(self.tlsroutes_file, "".join(lines))

        print(f"    ✓ Collected {self.stats.tlsroutes} TLSRoutes")
        return True

    def collect_reference_grants(self) -> bool:
        """Collect ReferenceGrant resources."""
        print("  Collecting ReferenceGrants...")

        data = run_kubectl_json(
            self.kubeconfig,
            "referencegrants.gateway.networking.k8s.io",
            all_namespaces=True,
        )

        if data is None:
            print("    ℹ️  ReferenceGrants not found or not accessible")
            return True

        lines = []
        for item in data.get("items", []):
            metadata = item.get("metadata", {})
            namespace = metadata.get("namespace", "default")
            name = metadata.get("name", "unknown")

            spec = item.get("spec", {})
            from_refs = spec.get("from", [])
            to_refs = spec.get("to", [])

            # Format from references
            from_strs = []
            for ref in from_refs:
                group = ref.get("group", "")
                kind = ref.get("kind", "")
                ns = ref.get("namespace", "")
                from_strs.append(f"{kind}({ns})")
            from_refs_str = ", ".join(from_strs) if from_strs else "none"

            # Format to references
            to_strs = []
            for ref in to_refs:
                group = ref.get("group", "")
                kind = ref.get("kind", "")
                to_strs.append(kind)
            to_refs_str = ", ".join(to_strs) if to_strs else "none"

            lines.append(f"{namespace}|{name}|{from_refs_str}|{to_refs_str}\n")
            self.stats.reference_grants += 1

        if lines:
            safe_write_file(self.reference_grants_file, "".join(lines))

        print(f"    ✓ Collected {self.stats.reference_grants} ReferenceGrants")
        return True

    def collect_backends(self) -> bool:
        """Collect backend Services referenced by routes."""
        print("  Collecting Backend Services...")

        if not self.backend_refs:
            print("    ℹ️  No backend references found in routes")
            return True

        lines = []
        endpoint_lines = []
        for backend_ref in sorted(self.backend_refs):
            namespace, name = backend_ref.split("/", 1)

            # Get service details
            data = run_kubectl_json(
                self.kubeconfig,
                f"service/{name}",
                namespace=namespace,
            )

            if data is None or "items" in data:
                # Service not found
                lines.append(f"{namespace}|{name}|Service|unknown|0\n")
                continue

            spec = data.get("spec", {})
            ports = spec.get("ports", [])
            svc_type = spec.get("type", "ClusterIP")

            # Format ports
            ports_strs = []
            for port in ports:
                port_num = port.get("port", "?")
                target_port = port.get("targetPort", port_num)
                protocol = port.get("protocol", "TCP")
                ports_strs.append(f"{port_num}->{target_port}/{protocol}")
            ports_str = ", ".join(ports_strs) if ports_strs else "none"

            # Collect detailed endpoint data using EndpointSlices
            endpoints = collect_endpoint_slices(self.kubeconfig, namespace, name)
            pod_count = len(endpoints)

            # Write endpoint details for diagram generation
            # Format: svc_namespace|svc_name|pod_name|pod_ip|ready
            for ep in endpoints:
                ready_str = "ready" if ep.get("ready", False) else "not-ready"
                endpoint_lines.append(
                    f"{namespace}|{name}|{ep.get('pod_name', 'unknown')}|"
                    f"{ep.get('pod_ip', '?')}|{ready_str}\n"
                )
                self.stats.endpoints += 1

            lines.append(f"{namespace}|{name}|{svc_type}|{ports_str}|{pod_count}\n")
            self.stats.backends += 1

        if lines:
            safe_write_file(self.backends_file, "".join(lines))

        if endpoint_lines:
            safe_write_file(self.endpoints_file, "".join(endpoint_lines))

        print(f"    ✓ Collected {self.stats.backends} Backend Services")
        print(f"    ✓ Collected {self.stats.endpoints} Endpoints")
        return True

    def is_collection_successful(self) -> bool:
        """Check if collection was successful."""
        # Success if we collected at least gateway classes or gateways
        return self.stats.gateway_classes > 0 or self.stats.gateways > 0

    def print_summary(self):
        """Print collection summary."""
        print()
        print("=" * 50)
        print("COLLECTION SUMMARY")
        print("=" * 50)
        print(f"  GatewayClasses:   {self.stats.gateway_classes}")
        print(f"  Gateways:         {self.stats.gateways}")
        print(f"  HTTPRoutes:       {self.stats.httproutes}")
        print(f"  GRPCRoutes:       {self.stats.grpcroutes}")
        print(f"  TCPRoutes:        {self.stats.tcproutes}")
        print(f"  TLSRoutes:        {self.stats.tlsroutes}")
        print(f"  ReferenceGrants:  {self.stats.reference_grants}")
        print(f"  Backend Services: {self.stats.backends}")
        print(f"  Route Rules:      {self.stats.route_rules}")
        print(f"  Endpoints:        {self.stats.endpoints}")
        print()

        if self.stats.errors:
            print("Errors encountered:")
            for error in self.stats.errors:
                print(f"  ⚠️  {error}")
            print()

        total = (
            self.stats.gateway_classes + self.stats.gateways +
            self.stats.httproutes + self.stats.grpcroutes +
            self.stats.tcproutes + self.stats.tlsroutes +
            self.stats.reference_grants + self.stats.backends +
            self.stats.route_rules + self.stats.endpoints
        )

        if self.is_collection_successful():
            print(f"✅ Collection complete: {total} resources collected")
        else:
            print("❌ Collection failed: no Gateway API resources found")

    def run(self) -> int:
        """Run the complete collection process."""
        print()
        print("=" * 50)
        print("COLLECTING GATEWAY API DATA")
        print("=" * 50)
        print()

        # Verify Gateway API is installed
        is_installed, installed_crds = check_gateway_api_installed(self.kubeconfig)
        if not is_installed:
            print("❌ Gateway API CRDs not found in cluster", file=sys.stderr)
            return 1

        print(f"✓ Gateway API installed ({len(installed_crds)} CRDs)")
        if self.gwctl_path:
            print(f"✓ gwctl available at {self.gwctl_path}")
        else:
            print("ℹ️  gwctl not found, using kubectl")
        print()

        # Initialize output files
        self.initialize_output_files()

        # Collect all resource types
        self.collect_gateway_classes()
        self.collect_gateways()
        self.collect_httproutes()
        self.collect_grpcroutes()
        self.collect_tcproutes()
        self.collect_tlsroutes()
        self.collect_reference_grants()
        self.collect_backends()

        # Print summary
        self.print_summary()

        return 0 if self.is_collection_successful() else 1


def main():
    """Main entry point."""
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <KUBECONFIG> <TMPDIR>", file=sys.stderr)
        return 1

    kubeconfig = sys.argv[1]
    tmpdir = sys.argv[2]

    if not os.path.exists(kubeconfig):
        print(f"❌ Error: Kubeconfig not found: {kubeconfig}", file=sys.stderr)
        return 1

    if not os.path.isdir(tmpdir):
        print(f"❌ Error: TMPDIR is not a directory: {tmpdir}", file=sys.stderr)
        return 1

    collector = GatewayDataCollector(kubeconfig, tmpdir)
    try:
        return collector.run()
    except OSError as exc:
        print(f"❌ Error writing output files: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
