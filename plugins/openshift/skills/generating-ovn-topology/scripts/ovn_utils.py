#!/usr/bin/env python3
"""
ovn_utils.py - Shared utilities for OVN topology scripts

This module provides common functions used across multiple OVN topology scripts.

Requirements: Python 3.6+, kubectl in PATH
"""

import json
import subprocess
import sys
from typing import Optional


def detect_ovn_namespace(kubeconfig: str) -> str:
    """Detect OVN namespace using hybrid approach.

    Uses a two-phase detection strategy:
    1. FAST PATH: Check common namespace names (covers 99% of cases)
    2. SLOW PATH: Search all namespaces for OVN pods (future-proof fallback)

    Different OVN-Kubernetes distributions use different namespaces:
    - OpenShift: 'openshift-ovn-kubernetes'
    - Upstream: 'ovn-kubernetes'
    - Future: unknown (detected by searching for ovnkube-node pods)

    Args:
        kubeconfig: Path to kubeconfig file

    Returns:
        Detected namespace

    Raises:
        RuntimeError: If no OVN namespace found
    """
    # Common namespace names (ordered by likelihood)
    common_namespaces = ["openshift-ovn-kubernetes", "ovn-kubernetes", "kube-ovn"]

    # FAST PATH: Try common namespaces first
    for namespace in common_namespaces:
        try:
            result = subprocess.run(
                [
                    "kubectl",
                    "--kubeconfig", kubeconfig,
                    "get", "pods",
                    "-n", namespace,
                    "-o", "name",
                    "--field-selector=status.phase=Running",
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode == 0 and result.stdout.strip():
                # Found pods in this namespace
                print(f"ℹ️  Detected OVN namespace: {namespace}", file=sys.stderr)
                return namespace

        except (subprocess.TimeoutExpired, subprocess.SubprocessError):
            continue

    # SLOW PATH: Search all namespaces for OVN pods
    print("ℹ️  Common namespaces not found, searching all namespaces...", file=sys.stderr)
    namespace = _search_for_ovn_namespace(kubeconfig)
    if namespace:
        print(f"✓ Detected OVN namespace: '{namespace}' (found by searching)", file=sys.stderr)
        print(
            f"   💡 Consider adding '{namespace}' to common_namespaces list",
            file=sys.stderr,
        )
        return namespace

    # All detection strategies failed
    raise RuntimeError(
        "Could not detect OVN namespace.\n"
        "\n"
        "  Tried:\n"
        f"    1. Common namespaces: {', '.join(common_namespaces)}\n"
        "    2. Searching all namespaces for ovnkube-node pods\n"
        "\n"
        "  💡 Troubleshooting:\n"
        "     1. Check if OVN-Kubernetes is deployed:\n"
        "        kubectl get pods --all-namespaces | grep ovn\n"
        "     2. Verify OVN pods are running:\n"
        "        kubectl get pods -l app=ovnkube-node --all-namespaces\n"
        "\n"
        "  If OVN-Kubernetes is deployed in a custom namespace, please report at:\n"
        "  https://github.com/openshift-eng/ai-helpers/issues"
    )


def _search_for_ovn_namespace(kubeconfig: str) -> Optional[str]:
    """Search all namespaces for one containing ovnkube-node pods.

    Args:
        kubeconfig: Path to kubeconfig file

    Returns:
        Namespace name if found, None otherwise
    """
    try:
        # Search for pods with common OVN labels across all namespaces
        result = subprocess.run(
            [
                "kubectl",
                "--kubeconfig", kubeconfig,
                "get", "pods",
                "--all-namespaces",
                "-l", "app=ovnkube-node",
                "-o", "jsonpath={.items[0].metadata.namespace}",
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )

        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()

        # Fallback: search by pod name prefix
        result = subprocess.run(
            [
                "kubectl",
                "--kubeconfig", kubeconfig,
                "get", "pods",
                "--all-namespaces",
                "--field-selector=status.phase=Running",
                "-o", "json",
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )

        if result.returncode == 0:
            pods_data = json.loads(result.stdout)
            for item in pods_data.get('items', []):
                pod_name = item['metadata']['name']
                if pod_name.startswith('ovnkube-node-'):
                    return item['metadata']['namespace']

    except (subprocess.TimeoutExpired, subprocess.SubprocessError, json.JSONDecodeError):
        pass

    return None


def detect_ovsdb_container(kubeconfig: str, ovn_namespace: str, sample_pod: str) -> str:
    """Auto-detect the NBDB container name using hybrid approach.

    Uses a two-phase detection strategy:
    1. FAST PATH: Check common container names (covers 99% of cases)
    2. SLOW PATH: Verify by tool availability (future-proof fallback)

    Different OVN-Kubernetes distributions use different container names:
    - Upstream: 'nb-ovsdb'
    - OpenShift: 'nbdb'
    - Future: unknown (detected by tool availability)

    Args:
        kubeconfig: Path to kubeconfig file
        ovn_namespace: OVN namespace name
        sample_pod: Name of an ovnkube-node pod to query

    Returns:
        Detected container name

    Raises:
        RuntimeError: If no valid NBDB container found
    """
    # Common container names (ordered by likelihood)
    # Update this list when new platforms are discovered
    common_names = ["nbdb", "nb-ovsdb", "ovsdb-nb", "ovn-nbdb"]

    try:
        # Get all container names from the pod
        result = subprocess.run(
            [
                "kubectl", "--kubeconfig", kubeconfig,
                "get", "pod", sample_pod,
                "-n", ovn_namespace,
                "-o", "jsonpath={.spec.containers[*].name}",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode != 0:
            raise RuntimeError(
                f"Failed to query containers in pod {sample_pod}: "
                f"{result.stderr.strip()}"
            )

        containers = result.stdout.strip().split()

        # FAST PATH: Try common names first (covers 99% of cases)
        for name in common_names:
            if name in containers:
                print(f"✓ Detected OVSDB container: '{name}'", file=sys.stderr)
                return name

        # SLOW PATH: Search by tool availability (future-proof)
        print(
            f"ℹ️  Common names not found in {sample_pod}, "
            f"verifying by tool availability...",
            file=sys.stderr,
        )
        for container in containers:
            if _has_ovn_nbctl(kubeconfig, ovn_namespace, sample_pod, container):
                print(
                    f"✓ Detected OVSDB container: '{container}' "
                    f"(verified by ovn-nbctl)",
                    file=sys.stderr,
                )
                print(
                    f"   💡 New container name detected! "
                    f"Consider adding '{container}' to common_names list",
                    file=sys.stderr,
                )
                return container

        # All detection strategies failed - provide helpful error
        raise RuntimeError(
            f"Could not find NBDB container in pod {sample_pod}\n"
            f"\n"
            f"  Available containers: {', '.join(containers)}\n"
            f"\n"
            f"  Tried:\n"
            f"    1. Common names: {', '.join(common_names)}\n"
            f"    2. Searching for ovn-nbctl tool in all containers\n"
            f"\n"
            f"  💡 Troubleshooting:\n"
            f"     1. Check pod details:\n"
            f"        kubectl describe pod {sample_pod} -n {ovn_namespace}\n"
            f"     2. Verify this is an ovnkube-node pod with NBDB\n"
            f"     3. Check if ovn-nbctl exists in any container:\n"
            f"        kubectl exec {sample_pod} -n {ovn_namespace} "
            f"-c <container> -- which ovn-nbctl\n"
            f"\n"
            f"  If you believe this is a valid OVN setup, please report at:\n"
            f"  https://github.com/openshift-eng/ai-helpers/issues"
        )

    except subprocess.TimeoutExpired:
        raise RuntimeError(
            f"Timeout querying pod {sample_pod}. "
            f"Check cluster connectivity."
        )
    except subprocess.SubprocessError as e:
        raise RuntimeError(
            f"Error querying pod {sample_pod}: {e}"
        )


def _has_ovn_nbctl(kubeconfig: str, ovn_namespace: str, pod: str, container: str) -> bool:
    """Check if a container has the ovn-nbctl tool.

    Args:
        kubeconfig: Path to kubeconfig file
        ovn_namespace: OVN namespace name
        pod: Pod name
        container: Container name to check

    Returns:
        True if container has ovn-nbctl, False otherwise
    """
    try:
        result = subprocess.run(
            [
                "kubectl", "--kubeconfig", kubeconfig,
                "exec", pod,
                "-n", ovn_namespace,
                "-c", container,
                "--",
                "which", "ovn-nbctl",
            ],
            capture_output=True,
            timeout=5,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, subprocess.SubprocessError):
        return False

