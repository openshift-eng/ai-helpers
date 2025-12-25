#!/usr/bin/env python3
"""
analyze_topology.py - Build relationship graph from collected Gateway API data

Usage: analyze_topology.py <TMPDIR>

This script analyzes collected Gateway API data and builds a relationship graph
showing connections between resources:
- GatewayClass -> Gateway (implements)
- Gateway -> Routes (attaches)
- Routes -> Backend Services (references)
- Services -> Pods (endpoints)
- ReferenceGrants -> cross-namespace permissions

Input files (from TMPDIR):
  - gateway_classes_detail.txt
  - gateways_detail.txt
  - httproutes_detail.txt
  - grpcroutes_detail.txt
  - tcproutes_detail.txt
  - tlsroutes_detail.txt
  - backends_detail.txt
  - reference_grants_detail.txt

Output files (written to TMPDIR):
  - gateway_relationships.txt - source_type|source_id|relation|target_type|target_id

Exit codes:
  0 - Success
  1 - Failure

Requirements: Python 3.6+
"""

import os
import sys
from dataclasses import dataclass, field
from typing import Dict, List, Set, Tuple

from gateway_utils import safe_write_file

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
_RELATIONSHIPS_FILE = "gateway_relationships.txt"


@dataclass
class GatewayClass:
    """GatewayClass resource."""
    name: str
    controller: str
    description: str
    status: str


@dataclass
class Gateway:
    """Gateway resource."""
    namespace: str
    name: str
    gateway_class: str
    listeners: str
    addresses: str
    status: str


@dataclass
class Route:
    """Generic route resource."""
    kind: str  # HTTPRoute, GRPCRoute, TCPRoute, TLSRoute
    namespace: str
    name: str
    hostnames: str
    parent_refs: str
    backend_refs: str


@dataclass
class Backend:
    """Backend service."""
    namespace: str
    name: str
    svc_type: str
    ports: str
    pod_count: int


@dataclass
class ReferenceGrant:
    """ReferenceGrant resource."""
    namespace: str
    name: str
    from_refs: str
    to_refs: str


@dataclass
class RouteRule:
    """Detailed route rule with match conditions and backends."""
    route_namespace: str
    route_name: str
    rule_index: int
    match_condition: str  # e.g., "PathPrefix:/api;headers=x-version=2"
    backends: str  # e.g., "ns/svc:port@weight,ns/svc2:port@weight"


@dataclass
class Endpoint:
    """Pod endpoint for a service."""
    svc_namespace: str
    svc_name: str
    pod_name: str
    pod_ip: str
    ready: bool


@dataclass
class Relationship:
    """Relationship between two resources."""
    source_type: str
    source_id: str  # namespace/name or just name for cluster-scoped
    relation: str   # implements, attaches, references, grants
    target_type: str
    target_id: str


class TopologyAnalyzer:
    """Analyze Gateway API topology and build relationship graph."""

    def __init__(self, tmpdir: str):
        self.tmpdir = tmpdir
        self.gateway_classes: Dict[str, GatewayClass] = {}
        self.gateways: Dict[str, Gateway] = {}  # key: namespace/name
        self.routes: List[Route] = []
        self.backends: Dict[str, Backend] = {}  # key: namespace/name
        self.reference_grants: List[ReferenceGrant] = []
        self.route_rules: List[RouteRule] = []
        self.endpoints: List[Endpoint] = []
        self.relationships: List[Relationship] = []

    def _read_file_lines(self, filename: str) -> List[str]:
        """Read lines from a file in tmpdir."""
        filepath = os.path.join(self.tmpdir, filename)
        if not os.path.exists(filepath):
            return []
        try:
            with open(filepath, 'r') as f:
                return [line.strip() for line in f if line.strip()]
        except OSError:
            return []

    def load_gateway_classes(self):
        """Load GatewayClass resources."""
        for line in self._read_file_lines(_GATEWAY_CLASSES_FILE):
            parts = line.split("|")
            if len(parts) >= 4:
                gc = GatewayClass(
                    name=parts[0],
                    controller=parts[1],
                    description=parts[2],
                    status=parts[3],
                )
                self.gateway_classes[gc.name] = gc

    def load_gateways(self):
        """Load Gateway resources."""
        for line in self._read_file_lines(_GATEWAYS_FILE):
            parts = line.split("|")
            if len(parts) >= 6:
                gw = Gateway(
                    namespace=parts[0],
                    name=parts[1],
                    gateway_class=parts[2],
                    listeners=parts[3],
                    addresses=parts[4],
                    status=parts[5],
                )
                key = f"{gw.namespace}/{gw.name}"
                self.gateways[key] = gw

    def _load_routes(self, filename: str, kind: str, has_hostnames: bool = True):
        """Load route resources from file."""
        for line in self._read_file_lines(filename):
            parts = line.split("|")
            if has_hostnames and len(parts) >= 5:
                route = Route(
                    kind=kind,
                    namespace=parts[0],
                    name=parts[1],
                    hostnames=parts[2],
                    parent_refs=parts[3],
                    backend_refs=parts[4],
                )
                self.routes.append(route)
            elif not has_hostnames and len(parts) >= 4:
                route = Route(
                    kind=kind,
                    namespace=parts[0],
                    name=parts[1],
                    hostnames="",
                    parent_refs=parts[2],
                    backend_refs=parts[3],
                )
                self.routes.append(route)

    def load_routes(self):
        """Load all route types."""
        self._load_routes(_HTTPROUTES_FILE, "HTTPRoute", has_hostnames=True)
        self._load_routes(_GRPCROUTES_FILE, "GRPCRoute", has_hostnames=False)
        self._load_routes(_TCPROUTES_FILE, "TCPRoute", has_hostnames=False)
        self._load_routes(_TLSROUTES_FILE, "TLSRoute", has_hostnames=True)

    def load_backends(self):
        """Load backend services."""
        for line in self._read_file_lines(_BACKENDS_FILE):
            parts = line.split("|")
            if len(parts) >= 5:
                backend = Backend(
                    namespace=parts[0],
                    name=parts[1],
                    svc_type=parts[2],
                    ports=parts[3],
                    pod_count=int(parts[4]) if parts[4].isdigit() else 0,
                )
                key = f"{backend.namespace}/{backend.name}"
                self.backends[key] = backend

    def load_reference_grants(self):
        """Load ReferenceGrant resources."""
        for line in self._read_file_lines(_REFERENCE_GRANTS_FILE):
            parts = line.split("|")
            if len(parts) >= 4:
                grant = ReferenceGrant(
                    namespace=parts[0],
                    name=parts[1],
                    from_refs=parts[2],
                    to_refs=parts[3],
                )
                self.reference_grants.append(grant)

    def load_route_rules(self):
        """Load detailed route rules."""
        for line in self._read_file_lines(_ROUTE_RULES_FILE):
            parts = line.split("|")
            if len(parts) >= 5:
                rule = RouteRule(
                    route_namespace=parts[0],
                    route_name=parts[1],
                    rule_index=int(parts[2]) if parts[2].isdigit() else 0,
                    match_condition=parts[3],
                    backends=parts[4],
                )
                self.route_rules.append(rule)

    def load_endpoints(self):
        """Load endpoint (pod) data."""
        for line in self._read_file_lines(_ENDPOINTS_FILE):
            parts = line.split("|")
            if len(parts) >= 5:
                endpoint = Endpoint(
                    svc_namespace=parts[0],
                    svc_name=parts[1],
                    pod_name=parts[2],
                    pod_ip=parts[3],
                    ready=(parts[4] == "ready"),
                )
                self.endpoints.append(endpoint)

    def analyze_gatewayclass_gateway_relations(self):
        """Find GatewayClass -> Gateway relationships."""
        for key, gw in self.gateways.items():
            if gw.gateway_class in self.gateway_classes:
                self.relationships.append(Relationship(
                    source_type="GatewayClass",
                    source_id=gw.gateway_class,
                    relation="implements",
                    target_type="Gateway",
                    target_id=key,
                ))

    def _parse_parent_ref(self, ref_str: str, route_namespace: str) -> Tuple[str, str]:
        """Parse a parent reference string to namespace/name.

        Args:
            ref_str: Reference string like "ns/name:section" or "name"
            route_namespace: Route's namespace for default

        Returns:
            Tuple of (namespace, name)
        """
        # Remove section name if present
        if ":" in ref_str:
            ref_str = ref_str.split(":")[0]

        if "/" in ref_str:
            ns, name = ref_str.split("/", 1)
            return ns, name
        else:
            return route_namespace, ref_str

    def analyze_gateway_route_relations(self):
        """Find Gateway -> Route relationships."""
        for route in self.routes:
            # Parse parent refs (comma-separated)
            if not route.parent_refs or route.parent_refs == "none":
                continue

            for ref in route.parent_refs.split(","):
                ref = ref.strip()
                if not ref:
                    continue

                ns, name = self._parse_parent_ref(ref, route.namespace)
                gw_key = f"{ns}/{name}"

                if gw_key in self.gateways:
                    self.relationships.append(Relationship(
                        source_type="Gateway",
                        source_id=gw_key,
                        relation="attaches",
                        target_type=route.kind,
                        target_id=f"{route.namespace}/{route.name}",
                    ))

    def _parse_backend_ref(self, ref_str: str, route_namespace: str) -> Tuple[str, str]:
        """Parse a backend reference string to namespace/name.

        Args:
            ref_str: Reference string like "ns/name:port" or "name:port"
            route_namespace: Route's namespace for default

        Returns:
            Tuple of (namespace, name)
        """
        # Remove port if present
        if ":" in ref_str:
            ref_str = ref_str.rsplit(":", 1)[0]

        if "/" in ref_str:
            ns, name = ref_str.split("/", 1)
            return ns, name
        else:
            return route_namespace, ref_str

    def analyze_route_backend_relations(self):
        """Find Route -> Backend relationships."""
        for route in self.routes:
            if not route.backend_refs or route.backend_refs == "none":
                continue

            for ref in route.backend_refs.split(","):
                ref = ref.strip()
                if not ref:
                    continue

                ns, name = self._parse_backend_ref(ref, route.namespace)
                backend_key = f"{ns}/{name}"

                self.relationships.append(Relationship(
                    source_type=route.kind,
                    source_id=f"{route.namespace}/{route.name}",
                    relation="references",
                    target_type="Service",
                    target_id=backend_key,
                ))

    def analyze_rule_backend_relations(self):
        """Find RouteRule -> Backend relationships with weights."""
        for rule in self.route_rules:
            if not rule.backends or rule.backends == "none":
                continue

            # Rule ID for relationships
            rule_id = f"{rule.route_namespace}/{rule.route_name}/rule-{rule.rule_index}"

            # First, link route to rule
            self.relationships.append(Relationship(
                source_type="HTTPRoute",
                source_id=f"{rule.route_namespace}/{rule.route_name}",
                relation="has-rule",
                target_type="RouteRule",
                target_id=rule_id,
            ))

            # Parse backends (format: ns/svc:port@weight,ns/svc2:port@weight)
            for backend_str in rule.backends.split(","):
                backend_str = backend_str.strip()
                if not backend_str:
                    continue

                # Extract weight if present
                weight = "1"
                if "@" in backend_str:
                    backend_str, weight = backend_str.rsplit("@", 1)

                # Extract port if present
                port = ""
                if ":" in backend_str:
                    backend_str, port = backend_str.rsplit(":", 1)

                # Extract namespace/name
                if "/" in backend_str:
                    ns, name = backend_str.split("/", 1)
                else:
                    ns = rule.route_namespace
                    name = backend_str

                backend_key = f"{ns}/{name}"

                self.relationships.append(Relationship(
                    source_type="RouteRule",
                    source_id=rule_id,
                    relation=f"routes-to@{weight}",
                    target_type="Service",
                    target_id=backend_key,
                ))

    def analyze_service_endpoint_relations(self):
        """Find Service -> Endpoint (Pod) relationships."""
        for ep in self.endpoints:
            svc_key = f"{ep.svc_namespace}/{ep.svc_name}"
            pod_id = f"{ep.svc_namespace}/{ep.pod_name}"

            ready_status = "ready" if ep.ready else "not-ready"

            self.relationships.append(Relationship(
                source_type="Service",
                source_id=svc_key,
                relation=f"endpoint@{ready_status}",
                target_type="Pod",
                target_id=pod_id,
            ))

    def write_relationships(self):
        """Write relationships to output file."""
        filepath = os.path.join(self.tmpdir, _RELATIONSHIPS_FILE)

        lines = []
        for rel in self.relationships:
            lines.append(
                f"{rel.source_type}|{rel.source_id}|{rel.relation}|"
                f"{rel.target_type}|{rel.target_id}\n"
            )

        safe_write_file(filepath, "".join(lines))

    def print_summary(self):
        """Print analysis summary."""
        print()
        print("=" * 50)
        print("TOPOLOGY ANALYSIS SUMMARY")
        print("=" * 50)
        print(f"  GatewayClasses:   {len(self.gateway_classes)}")
        print(f"  Gateways:         {len(self.gateways)}")
        print(f"  Routes:           {len(self.routes)}")
        print(f"  Route Rules:      {len(self.route_rules)}")
        print(f"  Backends:         {len(self.backends)}")
        print(f"  Endpoints:        {len(self.endpoints)}")
        print(f"  ReferenceGrants:  {len(self.reference_grants)}")
        print(f"  Relationships:    {len(self.relationships)}")
        print()

        # Count by relationship type
        rel_counts: Dict[str, int] = {}
        for rel in self.relationships:
            key = f"{rel.source_type} -> {rel.target_type}"
            rel_counts[key] = rel_counts.get(key, 0) + 1

        if rel_counts:
            print("Relationship types:")
            for key, count in sorted(rel_counts.items()):
                print(f"  {key}: {count}")
            print()

        print(f"✅ Analysis complete: {len(self.relationships)} relationships found")

    def run(self) -> int:
        """Run the topology analysis."""
        print()
        print("=" * 50)
        print("ANALYZING GATEWAY API TOPOLOGY")
        print("=" * 50)
        print()

        # Load all data
        print("Loading collected data...")
        self.load_gateway_classes()
        self.load_gateways()
        self.load_routes()
        self.load_backends()
        self.load_reference_grants()
        self.load_route_rules()
        self.load_endpoints()

        print(f"  Loaded {len(self.gateway_classes)} GatewayClasses")
        print(f"  Loaded {len(self.gateways)} Gateways")
        print(f"  Loaded {len(self.routes)} Routes")
        print(f"  Loaded {len(self.route_rules)} Route Rules")
        print(f"  Loaded {len(self.backends)} Backends")
        print(f"  Loaded {len(self.endpoints)} Endpoints")
        print(f"  Loaded {len(self.reference_grants)} ReferenceGrants")
        print()

        # Analyze relationships
        print("Analyzing relationships...")
        self.analyze_gatewayclass_gateway_relations()
        self.analyze_gateway_route_relations()
        self.analyze_route_backend_relations()
        self.analyze_rule_backend_relations()
        self.analyze_service_endpoint_relations()
        print(f"  Found {len(self.relationships)} relationships")

        # Write output
        self.write_relationships()

        # Print summary
        self.print_summary()

        return 0


def main():
    """Main entry point."""
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <TMPDIR>", file=sys.stderr)
        return 1

    tmpdir = sys.argv[1]

    if not os.path.isdir(tmpdir):
        print(f"❌ Error: TMPDIR is not a directory: {tmpdir}", file=sys.stderr)
        return 1

    analyzer = TopologyAnalyzer(tmpdir)
    try:
        return analyzer.run()
    except OSError as exc:
        print(f"❌ Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
