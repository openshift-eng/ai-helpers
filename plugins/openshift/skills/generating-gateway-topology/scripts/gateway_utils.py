#!/usr/bin/env python3
"""
gateway_utils.py - Shared utilities for Gateway API topology scripts

This module provides common functions used across multiple Gateway API topology scripts.

Requirements: Python 3.6+, kubectl in PATH, optionally gwctl
"""

import errno
import json
import os
import shutil
import subprocess
import sys
from typing import List, Optional, Tuple


# Gateway API CRD names
GATEWAY_API_CRDS = [
    "gateways.gateway.networking.k8s.io",
    "gatewayclasses.gateway.networking.k8s.io",
    "httproutes.gateway.networking.k8s.io",
    "grpcroutes.gateway.networking.k8s.io",
    "tcproutes.gateway.networking.k8s.io",
    "tlsroutes.gateway.networking.k8s.io",
    "referencegrants.gateway.networking.k8s.io",
]


def detect_gwctl() -> Optional[str]:
    """Detect if gwctl is installed and return its path.

    Checks standard PATH and common Go binary locations.

    Returns:
        Path to gwctl if found, None otherwise
    """
    # Check standard PATH first
    gwctl_path = shutil.which("gwctl")

    # Also check common Go binary locations
    if not gwctl_path:
        go_bin_paths = [
            os.path.expanduser("~/go/bin/gwctl"),
            "/usr/local/go/bin/gwctl",
        ]
        for path in go_bin_paths:
            if os.path.isfile(path) and os.access(path, os.X_OK):
                gwctl_path = path
                break

    if gwctl_path:
        try:
            result = subprocess.run(
                [gwctl_path, "version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                print(f"✓ Found gwctl at: {gwctl_path}", file=sys.stderr)
                return gwctl_path
        except (subprocess.TimeoutExpired, subprocess.SubprocessError):
            pass
    return None


def run_gwctl_describe(
    gwctl_path: str,
    resource_type: str,
    name: str,
    namespace: Optional[str] = None,
    timeout: int = 30,
) -> Optional[str]:
    """Run gwctl describe and return raw output.

    Args:
        gwctl_path: Path to gwctl binary
        resource_type: Resource type (e.g., 'gateway', 'httproute')
        name: Resource name
        namespace: Resource namespace
        timeout: Command timeout in seconds

    Returns:
        Raw describe output or None if failed
    """
    cmd = [gwctl_path, "describe", resource_type, name]
    if namespace:
        cmd.extend(["-n", namespace])

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.returncode == 0:
            return result.stdout
        return None
    except (subprocess.TimeoutExpired, subprocess.SubprocessError):
        return None


def collect_endpoint_slices(
    kubeconfig: str,
    service_namespace: str,
    service_name: str,
    timeout: int = 15,
) -> List[dict]:
    """Collect EndpointSlices for a service to get pod IPs.

    Args:
        kubeconfig: Path to kubeconfig file
        service_namespace: Service namespace
        service_name: Service name
        timeout: Command timeout

    Returns:
        List of endpoint dicts with pod_name, pod_ip, ready status
    """
    endpoints = []

    try:
        # Get EndpointSlices for the service
        result = subprocess.run(
            [
                "kubectl", "--kubeconfig", kubeconfig,
                "get", "endpointslices",
                "-n", service_namespace,
                "-l", f"kubernetes.io/service-name={service_name}",
                "-o", "json",
            ],
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        if result.returncode == 0:
            data = json.loads(result.stdout)
            for item in data.get("items", []):
                item_endpoints = item.get("endpoints") or []
                for endpoint in item_endpoints:
                    addresses = endpoint.get("addresses") or []
                    conditions = endpoint.get("conditions") or {}
                    ready = conditions.get("ready", False)
                    target_ref = endpoint.get("targetRef") or {}
                    pod_name = target_ref.get("name", "unknown")

                    for addr in addresses:
                        endpoints.append({
                            "pod_name": pod_name,
                            "pod_ip": addr,
                            "ready": ready,
                        })

    except (subprocess.TimeoutExpired, subprocess.SubprocessError, json.JSONDecodeError):
        pass

    return endpoints


def extract_route_rules(rules: list, route_namespace: str) -> List[dict]:
    """Extract detailed route rules from HTTPRoute spec.

    Args:
        rules: List of rule objects from HTTPRoute spec
        route_namespace: Route's namespace for resolving backend refs

    Returns:
        List of rule dicts with match details and backend refs
    """
    extracted_rules = []

    for idx, rule in enumerate(rules or []):
        matches = rule.get("matches", [{}])
        backend_refs = rule.get("backendRefs", [])

        # Extract match conditions
        match_details = []
        for match in matches:
            match_info = {}

            # Path match
            path = match.get("path", {})
            if path:
                match_info["path_type"] = path.get("type", "PathPrefix")
                match_info["path_value"] = path.get("value", "/")

            # Header matches
            headers = match.get("headers", [])
            if headers:
                header_strs = []
                for h in headers:
                    header_strs.append(f"{h.get('name')}={h.get('value')}")
                match_info["headers"] = ", ".join(header_strs)

            # Method match
            method = match.get("method")
            if method:
                match_info["method"] = method

            if match_info:
                match_details.append(match_info)

        # Extract backends with weights
        backends = []
        for backend in backend_refs:
            backend_ns = backend.get("namespace", route_namespace)
            backend_name = backend.get("name", "unknown")
            backend_port = backend.get("port", "")
            weight = backend.get("weight", 1)

            backends.append({
                "namespace": backend_ns,
                "name": backend_name,
                "port": backend_port,
                "weight": weight,
            })

        extracted_rules.append({
            "index": idx,
            "matches": match_details,
            "backends": backends,
        })

    return extracted_rules


def check_gateway_api_installed(kubeconfig: str) -> Tuple[bool, List[str]]:
    """Check if Gateway API CRDs are installed in the cluster.

    Args:
        kubeconfig: Path to kubeconfig file

    Returns:
        Tuple of (is_installed, list of installed CRDs)
    """
    installed_crds = []

    try:
        result = subprocess.run(
            [
                "kubectl", "--kubeconfig", kubeconfig,
                "get", "crd", "-o", "jsonpath={.items[*].metadata.name}",
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )

        if result.returncode == 0:
            all_crds = result.stdout.strip().split()
            for crd in GATEWAY_API_CRDS:
                if crd in all_crds:
                    installed_crds.append(crd)

    except (subprocess.TimeoutExpired, subprocess.SubprocessError) as e:
        print(f"⚠️  Error checking CRDs: {e}", file=sys.stderr)

    is_installed = len(installed_crds) > 0
    return is_installed, installed_crds


def run_kubectl_json(
    kubeconfig: str,
    resource: str,
    namespace: Optional[str] = None,
    all_namespaces: bool = False,
    timeout: int = 30,
) -> Optional[dict]:
    """Run kubectl get with JSON output.

    Args:
        kubeconfig: Path to kubeconfig file
        resource: Resource type to get (e.g., 'gateways.gateway.networking.k8s.io')
        namespace: Specific namespace (optional)
        all_namespaces: If True, get resources from all namespaces
        timeout: Command timeout in seconds

    Returns:
        Parsed JSON data or None if failed
    """
    cmd = ["kubectl", "--kubeconfig", kubeconfig, "get", resource, "-o", "json"]

    if all_namespaces:
        cmd.append("-A")
    elif namespace:
        cmd.extend(["-n", namespace])

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        if result.returncode == 0:
            return json.loads(result.stdout)
        else:
            # Resource might not exist or no permissions
            if "NotFound" in result.stderr or "the server doesn't have" in result.stderr:
                return {"items": []}
            print(f"⚠️  kubectl get {resource} failed: {result.stderr.strip()}", file=sys.stderr)
            return None

    except json.JSONDecodeError as e:
        print(f"⚠️  Failed to parse JSON for {resource}: {e}", file=sys.stderr)
        return None
    except subprocess.TimeoutExpired:
        print(f"⚠️  Timeout getting {resource}", file=sys.stderr)
        return None
    except subprocess.SubprocessError as e:
        print(f"⚠️  Error getting {resource}: {e}", file=sys.stderr)
        return None


def run_gwctl_json(
    gwctl_path: str,
    resource: str,
    namespace: Optional[str] = None,
    all_namespaces: bool = False,
    timeout: int = 30,
) -> Optional[dict]:
    """Run gwctl get with JSON output.

    Args:
        gwctl_path: Path to gwctl binary
        resource: Resource type to get (e.g., 'gateways')
        namespace: Specific namespace (optional)
        all_namespaces: If True, get resources from all namespaces
        timeout: Command timeout in seconds

    Returns:
        Parsed JSON data or None if failed
    """
    cmd = [gwctl_path, "get", resource, "-o", "json"]

    if all_namespaces:
        cmd.append("-A")
    elif namespace:
        cmd.extend(["-n", namespace])

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        if result.returncode == 0:
            return json.loads(result.stdout)
        else:
            return None

    except json.JSONDecodeError as e:
        print(f"⚠️  Failed to parse gwctl JSON for {resource}: {e}", file=sys.stderr)
        return None
    except subprocess.TimeoutExpired:
        print(f"⚠️  Timeout running gwctl get {resource}", file=sys.stderr)
        return None
    except subprocess.SubprocessError as e:
        print(f"⚠️  Error running gwctl get {resource}: {e}", file=sys.stderr)
        return None


def count_gateways(kubeconfig: str) -> int:
    """Count the number of Gateway resources in the cluster.

    Args:
        kubeconfig: Path to kubeconfig file

    Returns:
        Number of gateways found
    """
    try:
        result = subprocess.run(
            [
                "kubectl", "--kubeconfig", kubeconfig,
                "get", "gateways.gateway.networking.k8s.io",
                "-A", "--no-headers",
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )

        if result.returncode == 0:
            lines = [l for l in result.stdout.strip().split('\n') if l.strip()]
            return len(lines)

    except (subprocess.TimeoutExpired, subprocess.SubprocessError):
        pass

    return 0


def safe_write_file(filepath: str, content: str):
    """Safely write a file using os.open() with O_NOFOLLOW to prevent symlink attacks.

    Args:
        filepath: Path to the file to write
        content: Content to write to the file

    Raises:
        OSError: If file cannot be written (e.g., symlink detected)
    """
    if os.path.lexists(filepath):
        if os.path.islink(filepath):
            raise OSError(
                f"Security violation: {filepath} is a symlink (CWE-377/CWE-59)"
            )

    flags = os.O_NOFOLLOW | os.O_CREAT | os.O_WRONLY | os.O_TRUNC
    try:
        fd = os.open(filepath, flags, 0o600)
        with os.fdopen(fd, 'w') as f:
            f.write(content)
    except OSError as e:
        if e.errno == errno.ELOOP:
            raise OSError(
                f"Security violation: {filepath} is a symlink (CWE-377/CWE-59)"
            ) from e
        raise


def safe_append_file(filepath: str, content: str):
    """Safely append to a file, checking for symlinks first.

    Args:
        filepath: Path to the file to append to
        content: Content to append to the file

    Raises:
        OSError: If file cannot be written (e.g., symlink detected)
    """
    if os.path.lexists(filepath):
        if os.path.islink(filepath):
            raise OSError(
                f"Security violation: {filepath} is a symlink (CWE-377/CWE-59)"
            )
        flags = os.O_NOFOLLOW | os.O_WRONLY | os.O_APPEND
    else:
        flags = os.O_NOFOLLOW | os.O_CREAT | os.O_WRONLY | os.O_APPEND

    try:
        fd = os.open(filepath, flags, 0o600)
        with os.fdopen(fd, 'a') as f:
            f.write(content)
    except OSError as e:
        if e.errno == errno.ELOOP:
            raise OSError(
                f"Security violation: {filepath} is a symlink (CWE-377/CWE-59)"
            ) from e
        raise


def format_listeners(listeners: list) -> str:
    """Format gateway listeners for display.

    Args:
        listeners: List of listener objects from Gateway spec

    Returns:
        Formatted string like "HTTPS:443, HTTP:80"
    """
    if not listeners:
        return "none"

    formatted = []
    for listener in listeners:
        protocol = listener.get("protocol", "unknown")
        port = listener.get("port", "?")
        name = listener.get("name", "")
        if name:
            formatted.append(f"{protocol}:{port}({name})")
        else:
            formatted.append(f"{protocol}:{port}")

    return ", ".join(formatted)


def format_addresses(addresses: list) -> str:
    """Format gateway addresses for display.

    Args:
        addresses: List of address objects from Gateway status

    Returns:
        Formatted string of addresses
    """
    if not addresses:
        return "pending"

    formatted = []
    for addr in addresses:
        addr_type = addr.get("type", "Unknown")
        value = addr.get("value", "?")
        formatted.append(f"{value} ({addr_type})")

    return ", ".join(formatted)


def format_parent_refs(parent_refs: list) -> str:
    """Format route parent references for display.

    Args:
        parent_refs: List of parentRef objects from Route spec

    Returns:
        Formatted string of parent references
    """
    if not parent_refs:
        return "none"

    formatted = []
    for ref in parent_refs:
        namespace = ref.get("namespace", "")
        name = ref.get("name", "?")
        section = ref.get("sectionName", "")

        if namespace and section:
            formatted.append(f"{namespace}/{name}:{section}")
        elif namespace:
            formatted.append(f"{namespace}/{name}")
        elif section:
            formatted.append(f"{name}:{section}")
        else:
            formatted.append(name)

    return ", ".join(formatted)


def format_backend_refs(rules: list) -> str:
    """Extract and format backend references from route rules.

    Args:
        rules: List of rule objects from Route spec

    Returns:
        Formatted string of backend references
    """
    backends = set()

    for rule in rules or []:
        for backend_ref in rule.get("backendRefs", []):
            namespace = backend_ref.get("namespace", "")
            name = backend_ref.get("name", "?")
            port = backend_ref.get("port", "")

            if namespace and port:
                backends.add(f"{namespace}/{name}:{port}")
            elif namespace:
                backends.add(f"{namespace}/{name}")
            elif port:
                backends.add(f"{name}:{port}")
            else:
                backends.add(name)

    return ", ".join(sorted(backends)) if backends else "none"
