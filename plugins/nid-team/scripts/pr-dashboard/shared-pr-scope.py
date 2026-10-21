#!/usr/bin/env python3
"""Recognize component evidence before adding a shared-repository candidate."""

import json
import re
import sys


def scope_reason(repo, data, component_repos):
    if repo in component_repos:
        return "component repository"
    title = data.get("title", "")
    if re.search(r"\bNE-\d+\b", title):
        return "linked Network Edge issue"
    if re.search(r"\b(?:HAProxy|IngressController|Gateway API|GWAPI|CoreDNS|"
                 r"External DNS|external-dns|ALBO|BGP Cloud Connector|bgp-cloud-connector)\b",
                 title, re.IGNORECASE):
        return "component named in PR title"
    files = [item["path"] for item in data.get("files", [])]
    if repo == "openshift/api":
        api_paths = ("operator/v1/types_ingress.go", "operator/v1/types_ingresscontroller.go",
                     "operator/v1/types_dns.go", "config/v1/types_ingress.go",
                     "config/v1/types_dns.go")
        if any(path in api_paths or path.startswith("route/v1/") or
               re.search(r"/(?:ingresscontrollers|ingresses|dnses)\.(?:operator|config)\.openshift\.io",
                         path) for path in files):
            return "ingress, route, or DNS API files"
    if repo == "openshift/origin" and any(path.startswith(
            ("test/extended/router/", "test/extended/dns/", "test/extended/networking/dns/"))
            for path in files):
        return "ingress or DNS tests"
    if repo == "openshift/enhancements" and any(path.startswith(
            ("enhancements/ingress/", "enhancements/dns/", "enhancements/external-dns/",
             "enhancements/bgp-cloud-connector/")) for path in files):
        return "component enhancement"
    if repo in ("openshift/release", "openshift/images"):
        for component in component_repos:
            if any(re.search(r"(?:^|/)" + re.escape(component) + "/", path)
                   for path in files):
                return "component configuration: " + component
    return None


if __name__ == "__main__":
    reason = scope_reason(sys.argv[1], json.load(sys.stdin), set(sys.argv[2:]))
    if not reason:
        raise SystemExit(1)
    print(reason)
