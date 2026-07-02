"""
NetworkPolicy parser for Kubernetes API integration.
Fetches and parses NetworkPolicy objects from clusters.

Author: Shreyas Be <shbehera@redhat.com>
Date: 2026-06-29
"""

from kubernetes import client, config
from typing import List, Dict, Any, Optional
import logging
import os

logger = logging.getLogger(__name__)


class NetworkPolicyParser:
    """Parse NetworkPolicy objects from Kubernetes cluster"""

    def __init__(self, namespace: Optional[str] = None,
                 cluster_wide: bool = False,
                 kubeconfig: Optional[str] = None):
        """
        Initialize parser with cluster connection.

        Args:
            namespace: Target namespace (None = default namespace)
            cluster_wide: Fetch from all namespaces
            kubeconfig: Path to kubeconfig file (None = in-cluster or default)
        """
        # Load kubeconfig
        if kubeconfig:
            config.load_kube_config(config_file=kubeconfig)
        else:
            try:
                # Try in-cluster config first (if running in a pod)
                config.load_incluster_config()
                logger.info("Loaded in-cluster kubeconfig")
            except config.ConfigException:
                # Fall back to default kubeconfig
                kubeconfig_path = os.getenv('KUBECONFIG', os.path.expanduser('~/.kube/config'))
                if os.path.exists(kubeconfig_path):
                    config.load_kube_config(config_file=kubeconfig_path)
                    logger.info(f"Loaded kubeconfig from: {kubeconfig_path}")
                else:
                    config.load_kube_config()
                    logger.info("Loaded default kubeconfig")

        # Initialize API clients
        self.net_v1 = client.NetworkingV1Api()
        self.core_v1 = client.CoreV1Api()
        self.namespace = namespace
        self.cluster_wide = cluster_wide

        logger.info(f"Initialized parser: namespace={namespace}, cluster_wide={cluster_wide}")

    def get_policies(self) -> List[client.V1NetworkPolicy]:
        """
        Fetch NetworkPolicy objects from cluster.

        Returns:
            List of NetworkPolicy objects

        Raises:
            ApiException: If API call fails
        """
        try:
            if self.cluster_wide:
                logger.info("Fetching NetworkPolicies from all namespaces")
                response = self.net_v1.list_network_policy_for_all_namespaces()
            elif self.namespace:
                logger.info(f"Fetching NetworkPolicies from namespace: {self.namespace}")
                response = self.net_v1.list_namespaced_network_policy(self.namespace)
            else:
                # Use default namespace
                logger.info("Fetching NetworkPolicies from default namespace")
                response = self.net_v1.list_namespaced_network_policy('default')

            logger.info(f"Found {len(response.items)} NetworkPolicies")
            return response.items

        except client.ApiException as e:
            logger.error(f"Kubernetes API error: {e.status} - {e.reason}")
            if e.status == 401:
                raise Exception("Authentication failed. Please check your kubeconfig and login credentials.")
            elif e.status == 403:
                raise Exception(f"Permission denied. Required permissions: get, list on networkpolicies")
            else:
                raise Exception(f"Kubernetes API error: {e.reason}")

    def parse_policy(self, policy: client.V1NetworkPolicy) -> Dict[str, Any]:
        """
        Extract structured data from NetworkPolicy object.

        Args:
            policy: Kubernetes NetworkPolicy object

        Returns:
            Parsed policy as dictionary with all relevant fields
        """
        return {
            # Metadata
            'name': policy.metadata.name,
            'namespace': policy.metadata.namespace,
            'uid': policy.metadata.uid,
            'creation_timestamp': policy.metadata.creation_timestamp,
            'labels': policy.metadata.labels or {},
            'annotations': policy.metadata.annotations or {},

            # Spec
            'pod_selector': self._parse_selector(policy.spec.pod_selector),
            'policy_types': policy.spec.policy_types or [],
            'ingress_rules': self._parse_ingress_rules(policy.spec.ingress or []),
            'egress_rules': self._parse_egress_rules(policy.spec.egress or []),
        }

    def _parse_selector(self, selector: Optional[client.V1LabelSelector]) -> Dict[str, Any]:
        """Parse label selector into structured format"""
        if not selector:
            return {'match_labels': {}, 'match_expressions': []}

        return {
            'match_labels': selector.match_labels or {},
            'match_expressions': [
                {
                    'key': expr.key,
                    'operator': expr.operator,
                    'values': expr.values or []
                }
                for expr in (selector.match_expressions or [])
            ]
        }

    def _parse_ingress_rules(self, rules: List) -> List[Dict[str, Any]]:
        """Parse ingress rules from NetworkPolicy spec"""
        parsed_rules = []

        for rule in rules:
            parsed_rule = {
                'ports': self._parse_ports(rule.ports or []),
                'from': self._parse_peers(getattr(rule, '_from', []) or [])
            }
            parsed_rules.append(parsed_rule)

        return parsed_rules

    def _parse_egress_rules(self, rules: List) -> List[Dict[str, Any]]:
        """Parse egress rules from NetworkPolicy spec"""
        parsed_rules = []

        for rule in rules:
            parsed_rule = {
                'ports': self._parse_ports(rule.ports or []),
                'to': self._parse_peers(rule.to or [])
            }
            parsed_rules.append(parsed_rule)

        return parsed_rules

    def _parse_ports(self, ports: List) -> List[Dict[str, Any]]:
        """Parse port specifications"""
        parsed_ports = []

        for port in ports:
            parsed_port = {
                'port': port.port,
                'protocol': port.protocol or 'TCP',
            }
            # Handle port ranges (endPort field)
            if hasattr(port, 'end_port') and port.end_port:
                parsed_port['end_port'] = port.end_port

            parsed_ports.append(parsed_port)

        return parsed_ports

    def _parse_peers(self, peers: List) -> List[Dict[str, Any]]:
        """Parse peer selectors (from/to in ingress/egress rules)"""
        parsed_peers = []

        for peer in peers:
            peer_data = {}

            # Pod selector
            if hasattr(peer, 'pod_selector') and peer.pod_selector:
                peer_data['pod_selector'] = self._parse_selector(peer.pod_selector)

            # Namespace selector
            if hasattr(peer, 'namespace_selector') and peer.namespace_selector:
                peer_data['namespace_selector'] = self._parse_selector(peer.namespace_selector)

            # IP block
            if hasattr(peer, 'ip_block') and peer.ip_block:
                peer_data['ip_block'] = {
                    'cidr': peer.ip_block.cidr,
                    'except': getattr(peer.ip_block, '_except', []) or []
                }

            parsed_peers.append(peer_data)

        return parsed_peers

    def get_pods_in_namespace(self, namespace: str) -> List[client.V1Pod]:
        """
        Fetch pods for connectivity testing.

        Args:
            namespace: Target namespace

        Returns:
            List of Pod objects
        """
        try:
            response = self.core_v1.list_namespaced_pod(namespace)
            logger.info(f"Found {len(response.items)} pods in namespace {namespace}")
            return response.items
        except client.ApiException as e:
            logger.error(f"Error fetching pods from {namespace}: {e}")
            return []

    def get_pod_by_name(self, name: str, namespace: str) -> Optional[client.V1Pod]:
        """
        Get a specific pod by name.

        Args:
            name: Pod name
            namespace: Pod namespace

        Returns:
            Pod object or None if not found
        """
        try:
            pod = self.core_v1.read_namespaced_pod(name, namespace)
            return pod
        except client.ApiException as e:
            logger.error(f"Pod {namespace}/{name} not found: {e}")
            return None

    def get_service_by_name(self, name: str, namespace: str) -> Optional[client.V1Service]:
        """
        Get a specific service by name.

        Args:
            name: Service name
            namespace: Service namespace

        Returns:
            Service object or None if not found
        """
        try:
            service = self.core_v1.read_namespaced_service(name, namespace)
            return service
        except client.ApiException as e:
            logger.error(f"Service {namespace}/{name} not found: {e}")
            return None

    def get_all_namespaces(self) -> List[str]:
        """
        Get list of all namespace names in cluster.

        Returns:
            List of namespace names
        """
        try:
            response = self.core_v1.list_namespace()
            namespaces = [ns.metadata.name for ns in response.items]
            logger.info(f"Found {len(namespaces)} namespaces in cluster")
            return namespaces
        except client.ApiException as e:
            logger.error(f"Error fetching namespaces: {e}")
            return []


def selector_matches_labels(selector: Dict[str, Any], labels: Dict[str, str]) -> bool:
    """
    Check if a label selector matches a set of labels.

    Args:
        selector: Parsed selector dict with match_labels and match_expressions
        labels: Pod/namespace labels

    Returns:
        True if selector matches labels
    """
    # Check match_labels
    match_labels = selector.get('match_labels', {})
    for key, value in match_labels.items():
        if labels.get(key) != value:
            return False

    # Check match_expressions
    for expr in selector.get('match_expressions', []):
        key = expr['key']
        operator = expr['operator']
        values = expr.get('values', [])

        if operator == 'In':
            if labels.get(key) not in values:
                return False
        elif operator == 'NotIn':
            if labels.get(key) in values:
                return False
        elif operator == 'Exists':
            if key not in labels:
                return False
        elif operator == 'DoesNotExist':
            if key in labels:
                return False

    return True


if __name__ == "__main__":
    # Test the parser
    logging.basicConfig(level=logging.INFO)

    parser = NetworkPolicyParser(namespace="default")
    policies = parser.get_policies()

    print(f"\nFound {len(policies)} NetworkPolicies:\n")
    for policy in policies:
        parsed = parser.parse_policy(policy)
        print(f"  - {parsed['namespace']}/{parsed['name']}")
        print(f"    Policy Types: {parsed['policy_types']}")
        print(f"    Ingress Rules: {len(parsed['ingress_rules'])}")
        print(f"    Egress Rules: {len(parsed['egress_rules'])}")
        print()
