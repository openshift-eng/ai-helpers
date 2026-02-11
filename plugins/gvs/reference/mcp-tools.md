---
name: MCP Tools Reference
description: MCP tool signatures and parameters for the GVS server
---

# MCP Tools Reference

This guide documents the MCP (Model Context Protocol) tools available from the GVS MCP server at `gvs.gsslab.pnq2.redhat.com:8083`.

## Table of Contents

- [lookup_cve](#lookup_cve)
- [check_package_version](#check_package_version)
- [scan_all_vulnerabilities](#scan_all_vulnerabilities)
- [scan_vulnerability](#scan_vulnerability)
- [check_symbol_reachability](#check_symbol_reachability)
- [analyze_reflection_risks](#analyze_reflection_risks)
- [get_call_graph](#get_call_graph)

---

## lookup_cve

Look up CVE details from the Go vulnerability database. Returns affected packages, vulnerable symbols, and fixed versions without scanning any repository.

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `cve` | string | Yes | CVE ID or GO-ID to look up |

### Example

```json
{
  "server": "gvs",
  "toolName": "lookup_cve",
  "arguments": {
    "cve": "CVE-2024-45338"
  }
}
```

### Response

```json
{
  "go_id": "GO-2024-3333",
  "cve_id": "CVE-2024-45338",
  "aliases": ["GHSA-xxxx-xxxx-xxxx"],
  "affected": [
    {
      "package": "golang.org/x/net/html",
      "versions": "< 0.33.0",
      "symbols": ["Parse", "ParseFragment"]
    }
  ]
}
```

---

## check_package_version

Check if a specific Go package version has known vulnerabilities. Returns list of CVEs affecting this package@version with fix versions.

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `package` | string | Yes | Go package path |
| `version` | string | Yes | Package version |

### Example

```json
{
  "server": "gvs",
  "toolName": "check_package_version",
  "arguments": {
    "package": "golang.org/x/net",
    "version": "v0.17.0"
  }
}
```

### Response

```json
{
  "package": "golang.org/x/net",
  "version": "v0.17.0",
  "status": "vulnerable",
  "count": 2,
  "vulnerabilities": [
    {
      "cve": "CVE-2024-45338",
      "fixed_version": "v0.33.0"
    }
  ]
}
```

---

## scan_all_vulnerabilities

Scan a Go repository for ALL known vulnerabilities using govulncheck. Discovers all CVEs affecting the project without needing to specify a particular CVE.

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `repo` | string | Yes | Git repository URL |
| `branch` | string | No | Branch name or commit hash (defaults to detected default) |

### Example

```json
{
  "server": "gvs",
  "toolName": "scan_all_vulnerabilities",
  "arguments": {
    "repo": "https://github.com/kubernetes/kubernetes",
    "branch": "release-1.29"
  }
}
```

### Response

```json
{
  "repo": "https://github.com/kubernetes/kubernetes",
  "branch": "release-1.29",
  "modules_scanned": 15,
  "total_vulnerabilities": 3,
  "output": [
    {
      "cve": "CVE-2024-45338",
      "package": "golang.org/x/net/html"
    }
  ]
}
```

---

## scan_vulnerability

Check if a Go repository is vulnerable to a specific CVE. Performs deep call graph analysis to determine if vulnerable code is actually reachable. Optionally generates SVG visualization.

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `repo` | string | Yes | Git repository URL |
| `cve` | string | Yes | CVE ID or GO-ID to check for |
| `branch` | string | No | Branch name or commit hash (defaults to detected default) |
| `algorithm` | string | No | Call graph algorithm: `static`, `cha`, `rta` (default), or `vta` |
| `generate_graph` | boolean | No | Generate SVG call graph visualization |

### Algorithm Options

- `static` - Fastest, least precise
- `cha` - Class hierarchy analysis
- `rta` - Rapid type analysis (default, good for reflection)
- `vta` - Variable type analysis (slowest, highest precision)

### Example

```json
{
  "server": "gvs",
  "toolName": "scan_vulnerability",
  "arguments": {
    "repo": "https://github.com/org/repo",
    "cve": "CVE-2024-45338",
    "algorithm": "rta",
    "generate_graph": true
  }
}
```

### Response

```json
{
  "is_vulnerable": "true",
  "cve": "CVE-2024-45338",
  "go_cve": "GO-2024-3333",
  "repository": "https://github.com/org/repo",
  "branch": "main",
  "algorithm": "rta",
  "summary": "Vulnerable: html.Parse is reachable from main()",
  "graph_svg": "<svg>...</svg>",
  "reflection_risks": []
}
```

---

## check_symbol_reachability

Check if a specific symbol from any Go package is reachable from entry points in a repository. Use this to manually verify if code can call a particular function without needing a CVE ID. Returns the call path if reachable.

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `repo` | string | Yes | Git repository URL |
| `package` | string | Yes | Full Go package path (e.g., `golang.org/x/crypto/ssh`) |
| `symbol` | string | Yes | Symbol name to check (e.g., `NewServerConn`) |
| `branch` | string | No | Branch name or commit hash (defaults to detected default) |
| `algorithm` | string | No | Call graph algorithm: `static`, `cha`, `rta` (default), or `vta` |
| `generate_graph` | boolean | No | Generate SVG call graph visualization if reachable |

### Example

```json
{
  "server": "gvs",
  "toolName": "check_symbol_reachability",
  "arguments": {
    "repo": "https://github.com/org/repo",
    "package": "golang.org/x/net/html",
    "symbol": "Parse",
    "generate_graph": true
  }
}
```

### Response

```json
{
  "repo": "https://github.com/org/repo",
  "branch": "main",
  "package": "golang.org/x/net/html",
  "symbol": "Parse",
  "algorithm": "rta",
  "is_reachable": true,
  "entry_point": "main()",
  "call_path": [
    "main()",
    "handleRequest()",
    "parseHTML()",
    "golang.org/x/net/html.Parse()"
  ],
  "graph_svg": "<svg>...</svg>",
  "summary": "Symbol is reachable via 4-step call path"
}
```

---

## analyze_reflection_risks

Analyze code for reflection patterns that could invoke vulnerable symbols at runtime. Detects patterns like `reflect.ValueOf`, `MethodByName`, function registries, etc.

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `repo` | string | Yes | Git repository URL |
| `branch` | string | No | Branch name or commit hash |
| `algorithm` | string | No | Call graph algorithm: `static`, `cha`, `rta` (default for reflection), or `vta` |
| `cve` | string | No | CVE ID for targeted analysis |

### Example

```json
{
  "server": "gvs",
  "toolName": "analyze_reflection_risks",
  "arguments": {
    "repo": "https://github.com/kubernetes/kubernetes",
    "algorithm": "rta"
  }
}
```

### Response

```json
{
  "repo": "https://github.com/kubernetes/kubernetes",
  "branch": "master",
  "algorithm": "rta",
  "unsafe_usage": true,
  "reflect_usage": true,
  "risk_count": 5,
  "high_confidence_risks": 1,
  "medium_confidence_risks": 2,
  "low_confidence_risks": 2,
  "reflection_risks": [
    {
      "type": "MethodByName",
      "confidence": "high",
      "location": "pkg/util/reflect.go:42",
      "evidence": ["reflect.ValueOf(obj).MethodByName(name)"],
      "symbol": "MethodByName",
      "package": "reflect"
    }
  ],
  "summary": "Found 5 reflection risks (1 high, 2 medium, 2 low confidence)"
}
```

---

## get_call_graph

Generate call graph visualization showing the path from entry points to a vulnerable symbol. Returns SVG.

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `repo` | string | Yes | Git repository URL |
| `cve` | string | Yes | CVE ID to trace |
| `branch` | string | No | Branch name or commit hash |
| `algorithm` | string | No | Call graph algorithm: `static`, `cha`, `rta` (default), or `vta` |
| `symbol` | string | No | Specific symbol to trace (defaults to first found) |

### Example

```json
{
  "server": "gvs",
  "toolName": "get_call_graph",
  "arguments": {
    "repo": "https://github.com/org/repo",
    "cve": "CVE-2024-45338",
    "algorithm": "rta"
  }
}
```

### Response

```json
{
  "svg": "<svg xmlns='http://www.w3.org/2000/svg'>...</svg>"
}
```

---

## Common Patterns

### Call Graph Algorithms

All reachability-related tools support the `algorithm` parameter:

| Algorithm | Speed | Precision | Use Case |
|-----------|-------|-----------|----------|
| `static` | Fastest | Lowest | Quick preliminary checks |
| `cha` | Fast | Low | Class hierarchy analysis |
| `rta` | Medium | Medium | Default, handles reflection well |
| `vta` | Slowest | Highest | Maximum precision needed |

### Repository URL Format

The MCP server requires HTTPS URLs. The plugin commands accept various formats and convert them automatically:

| Input Format | Converted To |
|--------------|--------------|
| `https://github.com/org/repo` | `https://github.com/org/repo` (unchanged) |
| `https://github.com/org/repo.git` | `https://github.com/org/repo` |
| `git@github.com:org/repo.git` | `https://github.com/org/repo` |
| `ssh://git@github.com/org/repo.git` | `https://github.com/org/repo` |

**Note:** Only public repositories are supported. Private repositories are not accessible by the GVS server.

### Branch Specification

The `branch` parameter accepts:

- Branch names: `main`, `master`, `release-1.29`
- Commit hashes: `a1b2c3d4e5f6...`
- Tags: `v1.0.0`
