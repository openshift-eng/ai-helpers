"""
NetworkPolicy security analysis engine.
Detects misconfigurations, security issues, and best practice violations.

Author: Shreyas Be <shbehera@redhat.com>
Date: 2026-06-29
"""

from typing import List, Dict, Any
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class Severity(Enum):
    """Finding severity levels"""
    CRITICAL = 'CRITICAL'
    WARNING = 'WARNING'
    INFO = 'INFO'


class SecurityAnalyzer:
    """Analyze NetworkPolicies for security issues"""

    def __init__(self, policies: List[Dict[str, Any]]):
        """
        Initialize analyzer with parsed policies.

        Args:
            policies: List of parsed NetworkPolicy dictionaries
        """
        self.policies = policies
        self.findings: List[Dict[str, Any]] = []

    def analyze(self, mode: str = 'security') -> List[Dict[str, Any]]:
        """
        Run all applicable checks based on mode.

        Args:
            mode: Analysis mode (security, performance, compliance)

        Returns:
            List of findings sorted by severity
        """
        self.findings = []

        if mode in ['security', 'compliance']:
            self._check_default_deny()
            self._check_overly_permissive()
            self._check_public_exposure()
            self._check_empty_pod_selectors()
            self._check_missing_policy_types()

        if mode in ['performance']:
            self._check_redundant_policies()
            self._check_policy_count()
            self._check_complex_selectors()

        if mode == 'compliance':
            self._check_zero_trust_compliance()
            self._check_documentation()

        logger.info(f"Analysis complete: {len(self.findings)} findings")

        # Sort by severity
        return sorted(self.findings, key=lambda f: (
            0 if f['severity'] == Severity.CRITICAL else
            1 if f['severity'] == Severity.WARNING else 2
        ))

    def _check_default_deny(self):
        """Verify default-deny ingress/egress policies exist per namespace"""
        namespaces = set(p['namespace'] for p in self.policies)

        for ns in namespaces:
            ns_policies = [p for p in self.policies if p['namespace'] == ns]

            # Check default-deny ingress
            has_default_deny_ingress = any(
                p['pod_selector'].get('match_labels', {}) == {} and
                p['pod_selector'].get('match_expressions', []) == [] and
                'Ingress' in p.get('policy_types', []) and
                len(p.get('ingress_rules', [])) == 0
                for p in ns_policies
            )

            if not has_default_deny_ingress:
                self.findings.append({
                    'severity': Severity.CRITICAL,
                    'title': 'Missing default-deny ingress policy',
                    'namespace': ns,
                    'description': f'Namespace "{ns}" has no default-deny ingress policy. '
                                   'All pods can receive traffic from any source.',
                    'recommendation': 'Create a NetworkPolicy with empty podSelector and no ingress rules:\n'
                                      '  apiVersion: networking.k8s.io/v1\n'
                                      '  kind: NetworkPolicy\n'
                                      '  metadata:\n'
                                      f'    name: default-deny-ingress\n'
                                      f'    namespace: {ns}\n'
                                      '  spec:\n'
                                      '    podSelector: {}\n'
                                      '    policyTypes:\n'
                                      '    - Ingress',
                    'references': [
                        'https://kubernetes.io/docs/concepts/services-networking/network-policies/#default-deny-all-ingress-traffic'
                    ]
                })

            # Check default-deny egress
            has_default_deny_egress = any(
                p['pod_selector'].get('match_labels', {}) == {} and
                p['pod_selector'].get('match_expressions', []) == [] and
                'Egress' in p.get('policy_types', []) and
                len(p.get('egress_rules', [])) == 0
                for p in ns_policies
            )

            if not has_default_deny_egress:
                self.findings.append({
                    'severity': Severity.WARNING,
                    'title': 'Missing default-deny egress policy',
                    'namespace': ns,
                    'description': f'Namespace "{ns}" has no default-deny egress policy. '
                                   'Pods can initiate connections to any destination.',
                    'recommendation': 'Consider creating a default-deny egress policy for zero-trust architecture.'
                })

    def _check_overly_permissive(self):
        """Detect policies allowing traffic from anywhere"""
        for policy in self.policies:
            # Check ingress rules
            for idx, rule in enumerate(policy.get('ingress_rules', [])):
                if not rule.get('from'):  # Empty 'from' = allow all
                    self.findings.append({
                        'severity': Severity.CRITICAL,
                        'title': 'Overly permissive ingress rule',
                        'policy': policy['name'],
                        'namespace': policy['namespace'],
                        'rule_index': idx,
                        'description': f'Policy "{policy["name"]}" has an ingress rule with no source restrictions. '
                                       'This allows traffic from ALL sources in the cluster.',
                        'recommendation': 'Specify explicit source selectors (podSelector, namespaceSelector, or ipBlock).'
                    })

            # Check egress rules
            for idx, rule in enumerate(policy.get('egress_rules', [])):
                if not rule.get('to'):  # Empty 'to' = allow all
                    self.findings.append({
                        'severity': Severity.WARNING,
                        'title': 'Overly permissive egress rule',
                        'policy': policy['name'],
                        'namespace': policy['namespace'],
                        'rule_index': idx,
                        'description': f'Policy "{policy["name"]}" has an egress rule with no destination restrictions.',
                        'recommendation': 'Specify explicit destination selectors to limit egress traffic.'
                    })

    def _check_public_exposure(self):
        """Detect policies allowing internet (0.0.0.0/0) access"""
        for policy in self.policies:
            # Check ingress rules
            for idx, rule in enumerate(policy.get('ingress_rules', [])):
                for peer in rule.get('from', []):
                    ip_block = peer.get('ip_block', {})
                    cidr = ip_block.get('cidr', '')

                    if cidr in ['0.0.0.0/0', '::/0']:
                        self.findings.append({
                            'severity': Severity.CRITICAL,
                            'title': 'Public internet ingress allowed',
                            'policy': policy['name'],
                            'namespace': policy['namespace'],
                            'rule_index': idx,
                            'cidr': cidr,
                            'description': f'Policy "{policy["name"]}" allows ingress traffic from {cidr} (public internet).',
                            'recommendation': 'Restrict CIDR ranges to specific known IP addresses/ranges. '
                                              'Avoid exposing services directly to the internet without proper controls.',
                            'security_impact': 'HIGH'
                        })

            # Check egress rules
            for idx, rule in enumerate(policy.get('egress_rules', [])):
                for peer in rule.get('to', []):
                    ip_block = peer.get('ip_block', {})
                    cidr = ip_block.get('cidr', '')

                    if cidr in ['0.0.0.0/0', '::/0']:
                        self.findings.append({
                            'severity': Severity.WARNING,
                            'title': 'Public internet egress allowed',
                            'policy': policy['name'],
                            'namespace': policy['namespace'],
                            'rule_index': idx,
                            'cidr': cidr,
                            'description': f'Policy "{policy["name"]}" allows egress traffic to {cidr} (public internet).',
                            'recommendation': 'Consider restricting egress to specific external services only.',
                            'security_impact': 'MEDIUM'
                        })

    def _check_empty_pod_selectors(self):
        """Check for policies with empty podSelector (excluding default-deny)"""
        for policy in self.policies:
            selector = policy['pod_selector']
            is_empty = (
                selector.get('match_labels', {}) == {} and
                selector.get('match_expressions', []) == []
            )

            # Check if this is a default-deny policy
            is_default_deny = (
                is_empty and
                (len(policy.get('ingress_rules', [])) == 0 or
                 len(policy.get('egress_rules', [])) == 0)
            )

            if is_empty and not is_default_deny:
                self.findings.append({
                    'severity': Severity.WARNING,
                    'title': 'Empty podSelector (applies to all pods)',
                    'policy': policy['name'],
                    'namespace': policy['namespace'],
                    'description': f'Policy "{policy["name"]}" has an empty podSelector, '
                                   'which applies to all pods in the namespace. '
                                   'This may be intentional but could be overly broad.',
                    'recommendation': 'Verify this is intentional. Consider using specific label selectors.'
                })

    def _check_missing_policy_types(self):
        """Check for policies missing policyTypes specification"""
        for policy in self.policies:
            if not policy.get('policy_types'):
                self.findings.append({
                    'severity': Severity.INFO,
                    'title': 'Missing policyTypes specification',
                    'policy': policy['name'],
                    'namespace': policy['namespace'],
                    'description': f'Policy "{policy["name"]}" does not specify policyTypes. '
                                   'Kubernetes will infer types based on ingress/egress rules, '
                                   'but explicit specification is recommended.',
                    'recommendation': 'Add policyTypes field to explicitly declare Ingress and/or Egress.'
                })

    def _check_redundant_policies(self):
        """Detect overlapping/redundant policies"""
        # Group policies by namespace
        by_namespace = {}
        for p in self.policies:
            ns = p['namespace']
            if ns not in by_namespace:
                by_namespace[ns] = []
            by_namespace[ns].append(p)

        # Check for redundancy within each namespace
        for ns, policies in by_namespace.items():
            for i, p1 in enumerate(policies):
                for p2 in policies[i + 1:]:
                    if self._policies_overlap(p1, p2):
                        self.findings.append({
                            'severity': Severity.INFO,
                            'title': 'Potentially redundant policies',
                            'namespace': ns,
                            'policies': [p1['name'], p2['name']],
                            'description': f'Policies "{p1["name"]}" and "{p2["name"]}" have overlapping pod selectors.',
                            'recommendation': 'Review if these policies can be merged to reduce ACL complexity.',
                            'performance_impact': 'MEDIUM'
                        })

    def _policies_overlap(self, p1: Dict, p2: Dict) -> bool:
        """Check if two policies have overlapping selectors"""
        # Simplified overlap detection - match if selectors are identical
        return (
            p1['pod_selector'] == p2['pod_selector'] and
            bool(set(p1.get('policy_types', [])) & set(p2.get('policy_types', [])))
        )

    def _check_policy_count(self):
        """Check for namespaces with excessive policy count"""
        POLICY_COUNT_THRESHOLD = 15

        by_namespace = {}
        for p in self.policies:
            ns = p['namespace']
            by_namespace[ns] = by_namespace.get(ns, 0) + 1

        for ns, count in by_namespace.items():
            if count > POLICY_COUNT_THRESHOLD:
                self.findings.append({
                    'severity': Severity.WARNING,
                    'title': f'High policy count in namespace ({count} policies)',
                    'namespace': ns,
                    'policy_count': count,
                    'description': f'Namespace "{ns}" has {count} NetworkPolicies. '
                                   f'This may indicate opportunities for consolidation.',
                    'recommendation': f'Consider merging similar policies to reduce complexity.',
                    'performance_impact': 'MEDIUM'
                })

    def _check_complex_selectors(self):
        """Check for overly complex label selectors"""
        SELECTOR_COMPLEXITY_THRESHOLD = 3

        for policy in self.policies:
            selector = policy['pod_selector']
            label_count = len(selector.get('match_labels', {}))
            expr_count = len(selector.get('match_expressions', []))
            total_complexity = label_count + expr_count

            if total_complexity > SELECTOR_COMPLEXITY_THRESHOLD:
                self.findings.append({
                    'severity': Severity.INFO,
                    'title': 'Complex label selector',
                    'policy': policy['name'],
                    'namespace': policy['namespace'],
                    'complexity': total_complexity,
                    'description': f'Policy "{policy["name"]}" has a complex selector '
                                   f'({label_count} labels, {expr_count} expressions). '
                                   f'This may impact OVN performance.',
                    'recommendation': 'Consider simplifying the selector if possible.'
                })

    def _check_zero_trust_compliance(self):
        """Check zero-trust architecture compliance"""
        namespaces = set(p['namespace'] for p in self.policies)

        for ns in namespaces:
            ns_policies = [p for p in self.policies if p['namespace'] == ns]

            if not ns_policies:
                self.findings.append({
                    'severity': Severity.CRITICAL,
                    'title': 'Zero-trust violation: No NetworkPolicies',
                    'namespace': ns,
                    'description': f'Namespace "{ns}" has no NetworkPolicies, violating zero-trust principles.',
                    'recommendation': 'Implement at least a default-deny policy.',
                    'compliance_framework': 'Zero-Trust'
                })

    def _check_documentation(self):
        """Check if policies have documentation annotations"""
        REQUIRED_ANNOTATIONS = [
            'policy.kubernetes.io/description'
        ]

        for policy in self.policies:
            annotations = policy.get('annotations', {})
            missing_annotations = [
                anno for anno in REQUIRED_ANNOTATIONS
                if anno not in annotations
            ]

            if missing_annotations:
                self.findings.append({
                    'severity': Severity.INFO,
                    'title': 'Missing documentation annotations',
                    'policy': policy['name'],
                    'namespace': policy['namespace'],
                    'missing_annotations': missing_annotations,
                    'description': f'Policy "{policy["name"]}" lacks documentation annotations.',
                    'recommendation': f'Add annotations: {", ".join(missing_annotations)}'
                })

    def get_statistics(self) -> Dict[str, Any]:
        """Generate statistics about analyzed policies"""
        if not self.policies:
            return {
                'total_policies': 0,
                'namespaces': 0,
                'critical_findings': 0,
                'warning_findings': 0,
                'info_findings': 0
            }

        namespaces = set(p['namespace'] for p in self.policies)

        return {
            'total_policies': len(self.policies),
            'namespaces': len(namespaces),
            'policies_by_namespace': {
                ns: len([p for p in self.policies if p['namespace'] == ns])
                for ns in namespaces
            },
            'critical_findings': len([f for f in self.findings if f['severity'] == Severity.CRITICAL]),
            'warning_findings': len([f for f in self.findings if f['severity'] == Severity.WARNING]),
            'info_findings': len([f for f in self.findings if f['severity'] == Severity.INFO]),
        }


if __name__ == "__main__":
    # Test the analyzer
    logging.basicConfig(level=logging.INFO)

    # Sample policy for testing
    test_policies = [
        {
            'name': 'allow-all',
            'namespace': 'test',
            'pod_selector': {'match_labels': {}, 'match_expressions': []},
            'policy_types': ['Ingress'],
            'ingress_rules': [{'from': [], 'ports': []}],  # Empty from = allow all
            'egress_rules': [],
            'annotations': {}
        }
    ]

    analyzer = SecurityAnalyzer(test_policies)
    findings = analyzer.analyze(mode='security')

    print(f"\nFound {len(findings)} issues:\n")
    for finding in findings:
        print(f"  [{finding['severity'].value}] {finding['title']}")
        print(f"    {finding['description']}\n")
