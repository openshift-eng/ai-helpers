#!/usr/bin/env python3
"""
Gap Analyzer - Analyze test coverage gaps for e2e test files
Identifies what features are tested vs not tested
"""

import re
import os
import json
import sys
import argparse
from datetime import datetime
from typing import Dict, List, Tuple, Set

# Component type constants - shared across analyzer and reports
NETWORK_COMPONENTS = {'networking', 'router', 'dns', 'network-observability'}
STORAGE_COMPONENTS = {'storage', 'csi'}
CONTROL_PLANE_COMPONENTS = {'apiserver', 'etcd'}
OPERATOR_COMPONENTS = {'operators', 'mco', 'installer'}


class GapAnalyzer:
    """Analyzes OpenShift/Kubernetes test files to identify coverage gaps (component-agnostic)"""

    def __init__(self, file_path: str, language: str = 'go'):
        self.file_path = file_path
        self.language = language
        self.content = self._read_file()
        # Detect component type for informational purposes (doesn't affect analysis)
        self.component_type = self._detect_component_type()

    def _read_file(self) -> str:
        """Read the test file content"""
        with open(self.file_path, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read()

    def _detect_component_type(self) -> str:
        """Detect component type from file path and content (for informational purposes only)"""
        path_lower = self.file_path.lower()
        content_lower = self.content.lower()

        # Detect OpenShift/Kubernetes component type from file path
        # Network-related components
        if re.search(r'/networking/|network[-_]|sdn|ovn|ingress|egress', path_lower):
            return 'networking'
        elif re.search(r'/router/|haproxy|ingress.*controller', path_lower):
            return 'router'
        elif re.search(r'/dns/|coredns', path_lower):
            return 'dns'
        elif re.search(r'network.*observability|netobserv', path_lower):
            return 'network-observability'

        # Storage-related components
        elif re.search(r'/storage/|volume|pv|pvc|storageclass', path_lower):
            return 'storage'
        elif re.search(r'/csi/|container.*storage.*interface', path_lower):
            return 'csi'
        elif re.search(r'/image[-_]?registry|imageregistry', path_lower):
            return 'image-registry'

        # Node and runtime components
        elif re.search(r'/node/|kubelet|crio|container.*runtime', path_lower):
            return 'node'
        elif re.search(r'/kata/|kata.*containers', path_lower):
            return 'kata'
        elif re.search(r'/windows/|windows.*containers?|winc', path_lower):
            return 'windows-containers'

        # Control plane components
        elif re.search(r'/apiserver|kube[-_]?apiserver', path_lower):
            return 'apiserver'
        elif re.search(r'/etcd/', path_lower):
            return 'etcd'

        # Cluster configuration and management
        elif re.search(r'/mco/|machine[-_]?config|machineconfig', path_lower):
            return 'mco'
        elif re.search(r'/installer/|openshift[-_]?install', path_lower):
            return 'installer'
        elif re.search(r'/hypershift/|hosted.*control.*plane|hcp', path_lower):
            return 'hypershift'

        # Workloads and operators
        elif re.search(r'/workload/|deployment|statefulset|daemonset', path_lower):
            return 'workloads'
        elif re.search(r'/operator/|/controllers?/|olm', path_lower):
            return 'operators'

        # Monitoring and observability
        elif re.search(r'/monitoring/|prometheus|alertmanager|grafana', path_lower):
            return 'monitoring'
        elif re.search(r'/observability/|metrics|logging|telemetry', path_lower):
            return 'observability'

        # Other components
        elif re.search(r'/auth/|rbac|oauth|serviceaccount', path_lower):
            return 'auth'
        elif re.search(r'/image/|imagestream(?!registry)', path_lower):
            return 'image'
        elif re.search(r'/builds/|buildconfig', path_lower):
            return 'builds'

        # Check content for hints if path didn't match
        if re.search(r'sig-networking|networkpolicy|egressip', content_lower):
            return 'networking'
        elif re.search(r'sig-storage|persistentvolume', content_lower):
            return 'storage'
        elif re.search(r'sig-node|kubelet|crio|init.*container|termination.*grace', content_lower):
            return 'node'
        elif re.search(r'apiserver|kube.*api', content_lower):
            return 'apiserver'
        elif re.search(r'etcd|etcdctl', content_lower):
            return 'etcd'
        elif re.search(r'machine.*config.*operator|mco', content_lower):
            return 'mco'
        elif re.search(r'hypershift|hosted.*control.*plane', content_lower):
            return 'hypershift'
        elif re.search(r'kata.*container|sandboxed.*container', content_lower):
            return 'kata'
        elif re.search(r'windows.*container|winc', content_lower):
            return 'windows-containers'
        elif re.search(r'prometheus|alertmanager|monitoring', content_lower):
            return 'monitoring'
        elif re.search(r'image.*registry', content_lower):
            return 'image-registry'
        elif re.search(r'coredns|dns.*operator', content_lower):
            return 'dns'
        elif re.search(r'ingress.*controller|router|haproxy', content_lower):
            return 'router'

        # Unknown component - still works for any OpenShift/K8s component
        return 'unknown'

    def analyze_ginkgo_tests(self) -> Dict:
        """Analyze Ginkgo BDD test file for coverage"""

        # Extract test cases
        test_cases = []
        # Match both prefixed (g.It, o.It) and bare (It) calls with single or double quotes
        test_pattern = r'(?:g\.|o\.)?It\(\s*["\']([^"\']+)["\']'
        for match in re.finditer(test_pattern, self.content):
            test_name = match.group(1)
            line_num = self.content[:match.start()].count('\n') + 1
            test_cases.append({
                'name': test_name,
                'line': line_num,
                'id': self._extract_test_id(test_name),
                'tags': self._extract_tags(test_name)
            })

        # Analyze coverage - component-agnostic for all OpenShift/Kubernetes components
        coverage = {
            'platforms': self._analyze_platforms(),
            'protocols': self._analyze_protocols(),
            'service_types': self._analyze_service_types(),
            'ip_stacks': self._analyze_ip_stacks(),
            'topologies': self._analyze_topologies(),
            'storage_classes': self._analyze_storage_classes(),
            'volume_modes': self._analyze_volume_modes(),
            'scenarios': self._analyze_scenarios(),
            'features': self._analyze_features()
        }
        gaps = {
            'platforms': self._identify_platform_gaps(),
            'protocols': self._identify_protocol_gaps(),
            'service_types': self._identify_service_type_gaps(),
            'ip_stacks': self._identify_ip_stack_gaps(),
            'topologies': self._identify_topology_gaps(),
            'storage_classes': self._identify_storage_class_gaps(),
            'volume_modes': self._identify_volume_mode_gaps(),
            'scenarios': self._identify_scenario_gaps()
        }

        # Filter gaps based on component type
        gaps = self._filter_component_gaps(gaps)

        return {
            'file': self.file_path,
            'component_type': self.component_type,
            'test_count': len(test_cases),
            'test_cases': test_cases,
            'coverage': coverage,
            'gaps': gaps,
            'analysis_date': datetime.now().isoformat()
        }

    def _extract_test_id(self, test_name: str) -> str:
        """Extract test ID from test name"""
        match = re.search(r'-(\d+)-', test_name)
        return match.group(1) if match else ''

    def _extract_tags(self, test_name: str) -> List[str]:
        """Extract tags like [Serial], [Disruptive]"""
        tags = re.findall(r'\[([^\]]+)\]', test_name)
        return tags

    def _analyze_protocols(self) -> Dict:
        """Analyze protocol coverage (TCP, UDP, SCTP)"""
        # Detect explicit protocol mentions
        # Note: ICMP is not included as OpenShift officially doesn't support it

        # Check for explicit TCP keyword
        tcp_explicit = bool(re.search(r'\bTCP\b', self.content, re.IGNORECASE))

        # Check for HTTP/HTTPS via curl, wget, or HTTP URLs (these are TCP-based)
        tcp_via_http = bool(re.search(r'\bcurl\b|\bwget\b|http://|https://|\bHTTP\b', self.content, re.IGNORECASE))

        protocols = {
            'TCP': tcp_explicit or tcp_via_http,
            'UDP': bool(re.search(r'\bUDP\b', self.content, re.IGNORECASE)),
            'SCTP': bool(re.search(r'\bSCTP\b', self.content, re.IGNORECASE)),
        }

        return {
            'tested': [p for p, tested in protocols.items() if tested],
            'not_tested': [p for p, tested in protocols.items() if not tested],
            'count': sum(protocols.values())
        }

    def _analyze_ip_stacks(self) -> Dict:
        """Analyze IP stack coverage"""
        has_ipv4 = bool(re.search(r'ipv4|IPv4', self.content))
        has_ipv6 = bool(re.search(r'ipv6|IPv6', self.content))
        has_dualstack = bool(re.search(r'dualstack|dual.stack', self.content, re.IGNORECASE))

        tested = []
        not_tested = []

        if has_ipv4:
            tested.append('IPv4')
        else:
            not_tested.append('IPv4')

        if has_ipv6:
            tested.append('IPv6')
        else:
            not_tested.append('IPv6')

        if has_dualstack:
            tested.append('Dual Stack')
        else:
            not_tested.append('Dual Stack')

        return {
            'tested': tested,
            'not_tested': not_tested,
            'count': len(tested)
        }

    def _analyze_topologies(self) -> Dict:
        """Analyze network topology coverage"""
        topologies = {
            'Single Node': bool(re.search(r'single.node|sno', self.content, re.IGNORECASE)),
            'Multi-Node': bool(re.search(r'multi.node|\bHA\b|high.availability', self.content, re.IGNORECASE)),
            'Hosted Control Plane': bool(re.search(r'hypershift|hosted.control.plane|hcp', self.content, re.IGNORECASE)),
        }

        return {
            'tested': [t for t, tested in topologies.items() if tested],
            'not_tested': [t for t, tested in topologies.items() if not tested],
            'count': sum(topologies.values())
        }

    def _analyze_platforms(self) -> Dict:
        """
        Analyze platform coverage.

        Key insight: If a test doesn't have platform-specific skip conditions,
        it means the test runs on ALL platforms by default.

        Only mark platforms as "not tested" if there are explicit platform checks/skips.
        """
        # Define all platforms to track
        all_platforms = ['vSphere', 'ROSA', 'AWS', 'Azure', 'GCP', 'Bare Metal']

        # Detect explicit platform mentions in test names/tags (informational only)
        platform_mentions = {
            'vSphere': bool(re.search(r'vsphere', self.content, re.IGNORECASE)),
            'ROSA': bool(re.search(r'ROSA', self.content, re.IGNORECASE)),
            'AWS': bool(re.search(r'\bAWS\b|aws.*platform', self.content, re.IGNORECASE)),
            'Azure': bool(re.search(r'azure', self.content, re.IGNORECASE)),
            'GCP': bool(re.search(r'\bGCP\b|google.*cloud', self.content, re.IGNORECASE)),
            'Bare Metal': bool(re.search(r'baremetal|bare.metal', self.content, re.IGNORECASE)),
        }

        # Check if there are platform-specific skip patterns with actual platform names
        has_platform_specific_skips = bool(re.search(
            r'skipIf.*(?:aws|azure|gcp|vsphere|baremetal)|'
            r'skipUnless.*(?:aws|azure|gcp|vsphere|baremetal)|'
            r'only.*(?:aws|azure|gcp|vsphere|baremetal)|'
            r'(?:aws|azure|gcp|vsphere|baremetal).*only|'
            r'framework\.SkipUnless.*(?:aws|azure|gcp|vsphere|baremetal)|'
            r'checkPlatform\s*\(.*?\).*?g\.Skip',  # OpenShift pattern: platform := checkPlatform(oc) + g.Skip
            self.content,
            re.IGNORECASE | re.DOTALL
        ))

        # Extract individual test cases to analyze per-test platform restrictions
        test_pattern = r'(?:g\.|o\.)?It\(\s*["\']([^"\']+)["\'].*?\}\)'
        test_cases = re.finditer(test_pattern, self.content, re.DOTALL)

        # Track which platforms are covered across all test cases
        platforms_with_tests = set()
        platforms_explicitly_skipped = set()

        for test_match in test_cases:
            test_body = test_match.group(0)

            # Check if this specific test has platform restrictions
            has_platform_check = bool(re.search(r'checkPlatform\s*\(', test_body))

            if has_platform_check:
                # Test has platform restrictions - find which platforms are allowed
                # Look for platform names in skip conditions
                if re.search(r'vsphere', test_body, re.IGNORECASE):
                    platforms_with_tests.add('vSphere')
                    # If vsphere is the only allowed platform, others are skipped
                    if re.search(r'Skip.*not vsphere', test_body, re.IGNORECASE):
                        platforms_explicitly_skipped.update(['AWS', 'Azure', 'GCP', 'Bare Metal'])
            else:
                # Test has NO platform check = runs on ALL platforms
                platforms_with_tests.update(all_platforms)

        # Decision logic:
        # If we found tests that run on all platforms OR no platform-specific logic exists,
        # assume all platforms are tested
        if not has_platform_specific_skips:
            # No platform-specific logic anywhere = runs on all platforms
            tested_platforms = all_platforms
            not_tested_platforms = []
        elif platforms_with_tests:
            # Some tests run on all platforms, some have restrictions
            # Platform is tested if ANY test runs on it
            tested_platforms = sorted(list(platforms_with_tests))
            not_tested_platforms = sorted([p for p in all_platforms if p not in platforms_with_tests])
        else:
            # Fallback: use platform mentions (conservative estimate)
            tested_platforms = [p for p, mentioned in platform_mentions.items() if mentioned]
            not_tested_platforms = [p for p, mentioned in platform_mentions.items() if not mentioned]

        return {
            'tested': tested_platforms,
            'not_tested': not_tested_platforms,
            'count': len(tested_platforms)
        }

    def _analyze_service_types(self) -> Dict:
        """Analyze Kubernetes service type coverage"""
        service_types = {
            'NodePort': bool(re.search(r'NodePort', self.content)),
            'LoadBalancer': bool(re.search(r'LoadBalancer', self.content)),
            'ClusterIP': bool(re.search(r'ClusterIP', self.content)),
        }

        return {
            'tested': [s for s, tested in service_types.items() if tested],
            'not_tested': [s for s, tested in service_types.items() if not tested],
            'count': sum(service_types.values())
        }

    def _analyze_features(self) -> Dict:
        """Analyze feature coverage"""
        features = {
            'installation': bool(re.search(r'install|installation', self.content, re.IGNORECASE)),
            'metrics': bool(re.search(r'metrics', self.content, re.IGNORECASE)),
            'events': bool(re.search(r'events|logging', self.content, re.IGNORECASE)),
            'allow_rules': bool(re.search(r'Allow', self.content)),
            'deny_rules': bool(re.search(r'Deny', self.content)),
            'multiple_cidrs': bool(re.search(r'multiple.*cidr', self.content, re.IGNORECASE)),
            'port_ranges': bool(re.search(r'port.*range|range.*port', self.content, re.IGNORECASE)),
        }

        return {
            'tested': [f.replace('_', ' ').title() for f, tested in features.items() if tested],
            'count': sum(features.values())
        }

    def _analyze_scenarios(self) -> Dict:
        """Analyze test scenario coverage"""
        scenarios = {
            'Failover': bool(re.search(r'failover|fail.*over', self.content, re.IGNORECASE)),
            'Node Reboot': bool(re.search(r'reboot', self.content, re.IGNORECASE)),
            'Restart': bool(re.search(r'restart', self.content, re.IGNORECASE)),
            'Node Deletion': bool(re.search(r'node.*delet|delet.*node|DeleteMachine', self.content, re.IGNORECASE)),
            'Network Deletion/Recreation': bool(re.search(r'delet.*recreat|recreat.*delet|network.*delet.*recreat', self.content, re.IGNORECASE)),
            'Load Balancing': bool(re.search(r'load.*balanc', self.content, re.IGNORECASE)),
            'Namespace Isolation': bool(re.search(r'isolation|isolat.*namespace|namespace.*isolat', self.content, re.IGNORECASE)),
            'Error Handling': bool(re.search(r'invalid|malformed|negative|error.*handl', self.content, re.IGNORECASE)),
            'Operator Upgrades': bool(re.search(r'upgrade|migration', self.content, re.IGNORECASE)),
            'Concurrent Operations': bool(re.search(r'concurrent|parallel|race', self.content, re.IGNORECASE)),
            'Performance/Scale': bool(re.search(r'performance|scale|benchmark', self.content, re.IGNORECASE)),
            'RBAC/Security': bool(re.search(r'rbac|permission|unauthorized|security', self.content, re.IGNORECASE)),
            'Traffic Disruption': bool(re.search(r'traffic.*disrupt|packet.*loss|latency|jitter|network.*delay|chaos|fault.*injection', self.content, re.IGNORECASE)),
        }

        return {
            'tested': [s for s, tested in scenarios.items() if tested],
            'not_tested': [s for s, tested in scenarios.items() if not tested],
            'count': sum(scenarios.values())
        }

    # Storage-specific analysis methods
    def _analyze_storage_classes(self) -> Dict:
        """Analyze storage class coverage"""
        storage_classes = {
            'gp2/gp3': bool(re.search(r'\bgp2\b|\bgp3\b', self.content)),
            'standard': bool(re.search(r'\bstandard\b.*storage', self.content, re.IGNORECASE)),
            'csi': bool(re.search(r'\bcsi\b|container.*storage.*interface', self.content, re.IGNORECASE)),
        }

        return {
            'tested': [sc for sc, tested in storage_classes.items() if tested],
            'not_tested': [sc for sc, tested in storage_classes.items() if not tested],
            'count': sum(storage_classes.values())
        }

    def _analyze_volume_modes(self) -> Dict:
        """Analyze volume access mode coverage"""
        volume_modes = {
            'ReadWriteOnce': bool(re.search(r'ReadWriteOnce|RWO', self.content)),
            'ReadWriteMany': bool(re.search(r'ReadWriteMany|RWX', self.content)),
            'ReadOnlyMany': bool(re.search(r'ReadOnlyMany|ROX', self.content)),
        }

        return {
            'tested': [vm for vm, tested in volume_modes.items() if tested],
            'not_tested': [vm for vm, tested in volume_modes.items() if not tested],
            'count': sum(volume_modes.values())
        }

    def _analyze_provisioners(self) -> Dict:
        """Analyze storage provisioner coverage"""
        provisioners = {
            'dynamic': bool(re.search(r'dynamic.*provisioning', self.content, re.IGNORECASE)),
            'static': bool(re.search(r'static.*provisioning|pre.*provisioned', self.content, re.IGNORECASE)),
        }

        return {
            'tested': [p for p, tested in provisioners.items() if tested],
            'count': sum(provisioners.values())
        }

    def _analyze_storage_features(self) -> Dict:
        """Analyze storage-specific features"""
        features = {
            'snapshots': bool(re.search(r'snapshot|volumesnapshot', self.content, re.IGNORECASE)),
            'cloning': bool(re.search(r'clone|volumeclone', self.content, re.IGNORECASE)),
            'expansion': bool(re.search(r'expand|resize', self.content, re.IGNORECASE)),
            'encryption': bool(re.search(r'encrypt', self.content, re.IGNORECASE)),
        }

        return {
            'tested': [f.replace('_', ' ').title() for f, tested in features.items() if tested],
            'count': sum(features.values())
        }

    def _identify_protocol_gaps(self) -> List[Dict]:
        """Identify protocol testing gaps (TCP, UDP, SCTP)"""
        gaps = []

        # Check for TCP testing
        tcp_explicit = bool(re.search(r'\bTCP\b', self.content, re.IGNORECASE))
        tcp_via_http = bool(re.search(r'\bcurl\b|\bwget\b|http://|https://|\bHTTP\b', self.content, re.IGNORECASE))

        # TCP gap analysis
        if not tcp_explicit and not tcp_via_http:
            # No TCP testing at all
            gaps.append({
                'protocol': 'TCP',
                'priority': 'high',
                'impact': 'Most common protocol not tested',
                'recommendation': 'Add TCP protocol tests',
                'effort': 'medium',
                'coverage_improvement': 8.0
            })
        elif tcp_via_http and not tcp_explicit:
            # TCP tested via HTTP/curl, but suggest non-HTTP TCP tests as well
            gaps.append({
                'protocol': 'TCP (non-HTTP)',
                'priority': 'low',
                'impact': 'TCP tested via HTTP/curl, but non-HTTP TCP traffic (databases, custom protocols) not explicitly validated',
                'recommendation': 'Consider adding explicit non-HTTP TCP tests (e.g., database connections, custom ports)',
                'effort': 'low',
                'coverage_improvement': 2.0
            })

        if not re.search(r'\bUDP\b', self.content, re.IGNORECASE):
            gaps.append({
                'protocol': 'UDP',
                'priority': 'high',
                'impact': 'Common protocol for DNS, streaming not tested',
                'recommendation': 'Add UDP protocol tests',
                'effort': 'medium',
                'coverage_improvement': 7.0
            })

        if not re.search(r'\bSCTP\b', self.content, re.IGNORECASE):
            gaps.append({
                'protocol': 'SCTP',
                'priority': 'medium',
                'impact': 'Multi-streaming protocol not tested',
                'recommendation': 'Add SCTP protocol tests',
                'effort': 'high',
                'coverage_improvement': 5.0
            })

        return gaps

    def _identify_platform_gaps(self) -> List[Dict]:
        """
        Identify platform testing gaps.

        Uses the platform coverage analysis which treats tests without
        platform-specific checks as running on ALL platforms.
        """
        gaps = []
        platforms_coverage = self._analyze_platforms()
        not_tested_platforms = platforms_coverage.get('not_tested', [])

        # Define priority and impact for each platform
        platform_metadata = {
            'Azure': {
                'priority': 'high',
                'impact': 'Major cloud provider - production blocker',
                'recommendation': 'Add Azure platform-specific tests'
            },
            'GCP': {
                'priority': 'high',
                'impact': 'Major cloud provider - production blocker',
                'recommendation': 'Add GCP platform-specific tests'
            },
            'AWS': {
                'priority': 'high',
                'impact': 'Major cloud provider - production blocker',
                'recommendation': 'Add AWS platform-specific tests'
            },
            'vSphere': {
                'priority': 'medium',
                'impact': 'On-premise VMware deployments',
                'recommendation': 'Add vSphere platform tests'
            },
            'Bare Metal': {
                'priority': 'medium',
                'impact': 'Edge/on-premise deployments',
                'recommendation': 'Add bare metal platform tests'
            },
            'ROSA': {
                'priority': 'medium',
                'impact': 'Managed OpenShift on AWS',
                'recommendation': 'Add ROSA platform tests'
            }
        }

        # Only report gaps for platforms that are actually not tested
        for platform in not_tested_platforms:
            if platform in platform_metadata:
                gap = {'platform': platform}
                gap.update(platform_metadata[platform])
                gaps.append(gap)

        return gaps

    def _identify_service_type_gaps(self) -> List[Dict]:
        """Identify service type testing gaps"""
        gaps = []

        if not re.search(r'LoadBalancer', self.content):
            gaps.append({
                'service_type': 'LoadBalancer',
                'priority': 'high',
                'impact': 'External traffic not tested with LoadBalancer services',
                'recommendation': 'Add LoadBalancer service type tests'
            })

        if not re.search(r'ClusterIP', self.content):
            gaps.append({
                'service_type': 'ClusterIP',
                'priority': 'medium',
                'impact': 'Internal traffic not tested with ClusterIP services',
                'recommendation': 'Add ClusterIP service type tests'
            })

        if not re.search(r'NodePort', self.content):
            gaps.append({
                'service_type': 'NodePort',
                'priority': 'medium',
                'impact': 'Node port access not tested',
                'recommendation': 'Add NodePort service type tests'
            })

        return gaps

    def _identify_storage_class_gaps(self) -> List[Dict]:
        """Identify storage class testing gaps"""
        gaps = []

        if not re.search(r'\bgp2\b|\bgp3\b', self.content):
            gaps.append({
                'storage_class': 'gp2/gp3',
                'priority': 'high',
                'impact': 'AWS EBS storage not tested',
                'recommendation': 'Add gp2/gp3 storage class tests'
            })

        if not re.search(r'\bcsi\b|container.*storage.*interface', self.content, re.IGNORECASE):
            gaps.append({
                'storage_class': 'CSI',
                'priority': 'high',
                'impact': 'CSI drivers not tested',
                'recommendation': 'Add CSI storage class tests'
            })

        return gaps

    def _identify_volume_mode_gaps(self) -> List[Dict]:
        """Identify volume mode testing gaps"""
        gaps = []

        if not re.search(r'ReadWriteOnce|RWO', self.content):
            gaps.append({
                'volume_mode': 'ReadWriteOnce',
                'priority': 'high',
                'impact': 'Single-node write access not tested',
                'recommendation': 'Add ReadWriteOnce (RWO) volume tests'
            })

        if not re.search(r'ReadWriteMany|RWX', self.content):
            gaps.append({
                'volume_mode': 'ReadWriteMany',
                'priority': 'high',
                'impact': 'Multi-node write access not tested',
                'recommendation': 'Add ReadWriteMany (RWX) volume tests'
            })

        if not re.search(r'ReadOnlyMany|ROX', self.content):
            gaps.append({
                'volume_mode': 'ReadOnlyMany',
                'priority': 'medium',
                'impact': 'Multi-node read-only access not tested',
                'recommendation': 'Add ReadOnlyMany (ROX) volume tests'
            })

        return gaps

    def _identify_scenario_gaps(self) -> List[Dict]:
        """Identify scenario testing gaps based on analyzed coverage"""
        gaps = []
        scenarios = self._analyze_scenarios()
        not_tested = scenarios['not_tested']

        # Define gap details for each scenario
        scenario_details = {
            'Error Handling': {
                'priority': 'high',
                'impact': 'Invalid configs not validated',
                'recommendation': 'Add negative test cases for invalid configurations',
                'effort': 'low',
                'coverage_improvement': 6.0
            },
            'Operator Upgrades': {
                'priority': 'high',
                'impact': 'Upgrade path not tested',
                'recommendation': 'Add operator upgrade scenario tests',
                'effort': 'high',
                'coverage_improvement': 8.0
            },
            'Concurrent Operations': {
                'priority': 'medium',
                'impact': 'Race conditions not tested',
                'recommendation': 'Add concurrent rule update tests',
                'effort': 'medium',
                'coverage_improvement': 5.0
            },
            'Performance/Scale': {
                'priority': 'medium',
                'impact': 'Scale limits unknown',
                'recommendation': 'Add performance and scale tests',
                'effort': 'high',
                'coverage_improvement': 4.0
            },
            'RBAC/Security': {
                'priority': 'medium',
                'impact': 'Security boundaries not verified',
                'recommendation': 'Add RBAC and security tests',
                'effort': 'medium',
                'coverage_improvement': 5.0
            },
            'Traffic Disruption': {
                'priority': 'high',
                'impact': 'Network resilience under adverse conditions not tested',
                'recommendation': 'Add traffic disruption tests (packet loss, latency, jitter, network chaos)',
                'effort': 'high',
                'coverage_improvement': 7.0
            }
        }

        # Only report gaps for scenarios that are not tested
        for scenario in not_tested:
            if scenario in scenario_details:
                # Filter Traffic Disruption to networking components only
                if scenario == 'Traffic Disruption' and self.component_type not in NETWORK_COMPONENTS:
                    continue

                gap = {'scenario': scenario}
                gap.update(scenario_details[scenario])
                gaps.append(gap)

        return gaps

    def _identify_ip_stack_gaps(self) -> List[Dict]:
        """Identify IP stack testing gaps"""
        gaps = []
        ip_stacks = self._analyze_ip_stacks()

        for stack in ip_stacks['not_tested']:
            priority = 'high' if stack in ['IPv4', 'Dual Stack'] else 'medium'
            gaps.append({
                'ip_stack': stack,
                'priority': priority,
                'impact': f'{stack} networking not tested',
                'recommendation': f'Add {stack} test cases',
                'effort': 'medium',
                'coverage_improvement': 5.0
            })

        return gaps

    def _identify_topology_gaps(self) -> List[Dict]:
        """Identify topology testing gaps"""
        gaps = []
        topologies = self._analyze_topologies()

        priority_map = {
            'Multi-Node': 'high',
            'Single Node': 'medium',
            'Hosted Control Plane': 'medium'
        }

        effort_map = {
            'Multi-Node': 'low',
            'Single Node': 'medium',
            'Hosted Control Plane': 'high'
        }

        for topo in topologies['not_tested']:
            gaps.append({
                'topology': topo,
                'priority': priority_map.get(topo, 'low'),
                'impact': f'{topo} topology not tested',
                'recommendation': f'Add {topo} topology test cases',
                'effort': effort_map.get(topo, 'medium'),
                'coverage_improvement': 4.0
            })

        return gaps

    def _filter_component_gaps(self, gaps: Dict) -> Dict:
        """Filter gaps to only include component-relevant categories"""

        # Determine relevant categories based on component type using shared constants
        if self.component_type in NETWORK_COMPONENTS:
            relevant_categories = ['platforms', 'protocols', 'service_types', 'ip_stacks', 'topologies', 'scenarios']
        elif self.component_type in STORAGE_COMPONENTS:
            relevant_categories = ['platforms', 'storage_classes', 'volume_modes', 'scenarios']
        elif self.component_type in CONTROL_PLANE_COMPONENTS:
            relevant_categories = ['platforms', 'topologies', 'scenarios']
        elif self.component_type in OPERATOR_COMPONENTS:
            relevant_categories = ['platforms', 'scenarios']
        elif self.component_type in ('auth', 'observability', 'monitoring', 'image', 'image-registry', 'builds'):
            relevant_categories = ['platforms', 'scenarios']
        elif self.component_type in ('node', 'kata', 'windows-containers', 'workloads'):
            relevant_categories = ['platforms', 'scenarios']
        elif self.component_type == 'hypershift':
            relevant_categories = ['platforms', 'topologies', 'scenarios']
        else:
            # Default for unknown components - include platforms and scenarios
            relevant_categories = ['platforms', 'scenarios']

        # Filter gaps to only include relevant categories
        filtered_gaps = {}
        for category, gap_list in gaps.items():
            if category in relevant_categories:
                filtered_gaps[category] = gap_list
            else:
                # Set to empty list for irrelevant categories
                filtered_gaps[category] = []

        return filtered_gaps

    def calculate_coverage_score(self, analysis: Dict) -> Dict:
        """Calculate overall coverage score (component-agnostic for all OpenShift/K8s components)"""
        coverage = analysis['coverage']

        # Scenario score - tests for error handling, upgrades, security, performance, etc.
        scenario_data = coverage.get('scenarios', {'tested': [], 'not_tested': []})
        total_scenarios = len(scenario_data['tested']) + len(scenario_data['not_tested'])
        scenario_score = (len(scenario_data['tested']) / max(total_scenarios, 1)) * 100

        # Platform score - tests across different platforms (AWS, Azure, GCP, etc.)
        platform_data = coverage.get('platforms', {'tested': [], 'not_tested': []})
        total_platforms = len(platform_data['tested']) + len(platform_data['not_tested'])
        platform_score = (len(platform_data['tested']) / max(total_platforms, 1)) * 100

        # Protocol score - network protocol coverage
        protocol_data = coverage.get('protocols', {'tested': [], 'not_tested': []})
        total_protocols = len(protocol_data['tested']) + len(protocol_data['not_tested'])
        protocol_score = (len(protocol_data['tested']) / max(total_protocols, 1)) * 100

        # Service type score - Kubernetes service type coverage
        service_data = coverage.get('service_types', {'tested': [], 'not_tested': []})
        total_service_types = len(service_data['tested']) + len(service_data['not_tested'])
        service_type_score = (len(service_data['tested']) / max(total_service_types, 1)) * 100

        # Storage class score - storage class coverage
        storage_class_data = coverage.get('storage_classes', {'tested': [], 'not_tested': []})
        total_storage_classes = len(storage_class_data['tested']) + len(storage_class_data['not_tested'])
        storage_class_score = (len(storage_class_data['tested']) / max(total_storage_classes, 1)) * 100

        # Volume mode score - volume access mode coverage
        volume_mode_data = coverage.get('volume_modes', {'tested': [], 'not_tested': []})
        total_volume_modes = len(volume_mode_data['tested']) + len(volume_mode_data['not_tested'])
        volume_mode_score = (len(volume_mode_data['tested']) / max(total_volume_modes, 1)) * 100

        # IP stack score - IPv4/IPv6/Dual Stack coverage
        ip_stack_data = coverage.get('ip_stacks', {'tested': [], 'not_tested': []})
        total_ip_stacks = len(ip_stack_data['tested']) + len(ip_stack_data['not_tested'])
        ip_stack_score = (len(ip_stack_data['tested']) / max(total_ip_stacks, 1)) * 100

        # Topology score - Single/Multi-Node/HCP coverage
        topology_data = coverage.get('topologies', {'tested': [], 'not_tested': []})
        total_topologies = len(topology_data['tested']) + len(topology_data['not_tested'])
        topology_score = (len(topology_data['tested']) / max(total_topologies, 1)) * 100

        # Component-aware scoring - select relevant metrics based on component type

        # Network-related components (protocols, IP stacks, topologies)
        if self.component_type in NETWORK_COMPONENTS:
            metric_values = [platform_score, protocol_score, service_type_score, ip_stack_score, topology_score, scenario_score]

        # Storage-related components (storage classes, volume modes)
        elif self.component_type in STORAGE_COMPONENTS:
            metric_values = [platform_score, storage_class_score, volume_mode_score, scenario_score]

        # Node/runtime components (platform + scenario + topology for different node types)
        elif self.component_type in ('node', 'kata', 'windows-containers'):
            metric_values = [platform_score, topology_score, scenario_score]

        # Control plane components (platform + scenario + topology for HA/SNO/HCP)
        elif self.component_type in CONTROL_PLANE_COMPONENTS:
            metric_values = [platform_score, topology_score, scenario_score]

        # Cluster management (platform + topology for different cluster types)
        elif self.component_type in OPERATOR_COMPONENTS:
            metric_values = [platform_score, topology_score, scenario_score]

        # Hypershift gets topology support
        elif self.component_type == 'hypershift':
            metric_values = [platform_score, topology_score, scenario_score]

        # Infrastructure components (platform + scenario only)
        elif self.component_type in ('auth', 'monitoring', 'observability', 'image-registry', 'image', 'builds', 'workloads'):
            metric_values = [platform_score, scenario_score]

        else:
            # Unknown component - use all applicable metrics with non-zero values
            all_metrics = [platform_score, protocol_score, service_type_score, ip_stack_score, topology_score, storage_class_score, volume_mode_score, scenario_score]
            metric_values = [m for m in all_metrics if m > 0] or [platform_score, scenario_score]

        overall = sum(metric_values) / max(len(metric_values), 1)

        # Build component-aware score dictionary (only include relevant scores)
        scores = {
            'overall': round(overall, 1),
            'platform_coverage': round(platform_score, 1),
            'scenario_coverage': round(scenario_score, 1)
        }

        # Add component-specific scores ONLY if they're relevant to the component
        # AND detected in the test content (non-zero total items)

        # Network components - add scores if networking patterns detected
        if self.component_type in NETWORK_COMPONENTS:
            # Only add protocol coverage if protocols are mentioned in tests
            if len(coverage.get('protocols', {}).get('tested', [])) + len(coverage.get('protocols', {}).get('not_tested', [])) > 0:
                scores['protocol_coverage'] = round(protocol_score, 1)
            # Only add service type coverage if service types are mentioned
            if len(coverage.get('service_types', {}).get('tested', [])) + len(coverage.get('service_types', {}).get('not_tested', [])) > 0:
                scores['service_type_coverage'] = round(service_type_score, 1)
            # Only add IP stack coverage if IP stacks are mentioned
            if len(coverage.get('ip_stacks', {}).get('tested', [])) + len(coverage.get('ip_stacks', {}).get('not_tested', [])) > 0:
                scores['ip_stack_coverage'] = round(ip_stack_score, 1)
            # Only add topology if topologies are mentioned
            if len(coverage.get('topologies', {}).get('tested', [])) + len(coverage.get('topologies', {}).get('not_tested', [])) > 0:
                scores['topology_coverage'] = round(topology_score, 1)

        # Storage components - add scores if storage patterns detected
        elif self.component_type in STORAGE_COMPONENTS:
            # Only add storage class coverage if storage classes are mentioned
            if len(coverage.get('storage_classes', {}).get('tested', [])) + len(coverage.get('storage_classes', {}).get('not_tested', [])) > 0:
                scores['storage_class_coverage'] = round(storage_class_score, 1)
            # Only add volume mode coverage if volume modes are mentioned
            if len(coverage.get('volume_modes', {}).get('tested', [])) + len(coverage.get('volume_modes', {}).get('not_tested', [])) > 0:
                scores['volume_mode_coverage'] = round(volume_mode_score, 1)

        # Components that may care about topology - only add if detected in tests
        elif self.component_type in ('node', 'kata', 'windows-containers') or self.component_type in CONTROL_PLANE_COMPONENTS or self.component_type in OPERATOR_COMPONENTS or self.component_type == 'hypershift':
            # Only add topology coverage if topology patterns are actually detected
            if len(coverage.get('topologies', {}).get('tested', [])) + len(coverage.get('topologies', {}).get('not_tested', [])) > 0:
                scores['topology_coverage'] = round(topology_score, 1)

        return scores


def main():
    """Main entry point for e2e test gap analysis CLI"""
    # Import report generators (late import to avoid circular dependencies)
    try:
        from .reports import (
            generate_gap_json_report,
            generate_gap_text_report
        )
        from .report_template import generate_custom_gap_report
    except ImportError:
        from reports import (
            generate_gap_json_report,
            generate_gap_text_report
        )
        from report_template import generate_custom_gap_report

    parser = argparse.ArgumentParser(
        description='Analyze e2e test files for coverage gaps'
    )

    parser.add_argument('test_file', help='Path to OpenShift/Kubernetes e2e test file')
    parser.add_argument('--output', default='.work/test-coverage/gaps/',
                        help='Output directory for reports')

    args = parser.parse_args()

    # Validate inputs
    if not os.path.isfile(args.test_file):
        print(f"Error: Test file not found: {args.test_file}", file=sys.stderr)
        return 1

    # Create output directory
    os.makedirs(args.output, exist_ok=True)

    print(f"Analyzing test file: {os.path.basename(args.test_file)}")
    print()

    # Run gap analysis (Go only, component-agnostic)
    analyzer = GapAnalyzer(args.test_file, 'go')
    analysis = analyzer.analyze_ginkgo_tests()
    scores = analyzer.calculate_coverage_score(analysis)

    # Show detected component for informational purposes
    component = analysis['component_type']
    if component != 'unknown':
        print(f"Detected component: {component}")
    print()

    # Generate reports
    print("Generating reports...")

    html_path = os.path.join(args.output, 'test-gaps-report.html')
    json_path = os.path.join(args.output, 'test-gaps.json')
    text_path = os.path.join(args.output, 'test-gaps-summary.txt')

    generate_custom_gap_report(analysis, scores, html_path)
    generate_gap_json_report(analysis, scores, json_path)
    generate_gap_text_report(analysis, scores, text_path)

    print(f"✓ HTML report generated: {html_path}")
    print()

    # Print summary
    print("=" * 60)
    print("OpenShift/Kubernetes Test Coverage Gap Analysis")
    print("=" * 60)
    print()
    print(f"File: {os.path.basename(args.test_file)}")
    print(f"Test Cases: {analysis['test_count']}")
    if component != 'unknown':
        print(f"Component: {component}")
    print()
    print("Coverage Scores:")
    print(f"  Overall:               {scores['overall']:.1f}%")
    print(f"  Platform Coverage:     {scores['platform_coverage']:.1f}%")
    print(f"  Scenario Coverage:     {scores['scenario_coverage']:.1f}%")
    print()

    # Show high priority gaps (component-agnostic)
    all_gaps = []
    for entries in analysis['gaps'].values():
        if entries:
            all_gaps.extend(entries)
    high_priority = [g for g in all_gaps if g.get('priority') == 'high']

    if high_priority:
        print(f"High Priority Gaps ({len(high_priority)}):")
        for i, gap in enumerate(high_priority[:5], 1):
            name = (gap.get('platform') or gap.get('scenario') or
                    gap.get('protocol') or gap.get('topology') or
                    gap.get('storage_class') or gap.get('service_type') or
                    gap.get('volume_mode') or gap.get('ip_stack'))
            impact = gap.get('impact', 'Unknown impact')
            print(f"  {i}. {name} - {impact}")
        print()

    print("Reports Generated:")
    print(f"  HTML:  {html_path}")
    print(f"  JSON:  {json_path}")
    print(f"  Text:  {text_path}")
    print()

    target_score = min(95, scores['overall'] + 20)
    print("Recommendation:")
    print(f"  Add 5-7 test cases to address high-priority gaps")
    print(f"  Target: Improve coverage from {scores['overall']:.0f}% to {target_score:.0f}%")

    return 0


if __name__ == '__main__':
    sys.exit(main())
