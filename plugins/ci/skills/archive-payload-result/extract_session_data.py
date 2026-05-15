#!/usr/bin/env python3
"""Extract API responses and job references from a Claude payload analysis session tarball.

Usage:
    python3 extract-session-data.py <session-tarball> <output-dir> <payload-tag>

Extracts:
- fetch_payloads.py API response → api-responses/fetch-payloads-{arch}-{version}-{stream}.json
- fetch_new_prs_in_payload.py responses → api-responses/fetch-new-prs-{tag}.json
- Failed job GCS paths → failed-direct-jobs.txt, failed-aggregated-jobs.txt
- Reference output files (HTML, YAML, JSON) from the session workspace
"""

import json
import os
import re
import sys
import tarfile
import tempfile


def _extract_curl_responses(cmd, result, output_dir, found):
    """Extract and cache curl responses from a Bash tool result."""
    # Extract URLs from curl commands
    urls = re.findall(r'(?:curl\s+[^"]*")(https?://[^"]+)', cmd)
    if not urls:
        urls = re.findall(r"(?:curl\s+[^']*')(https?://[^']+)", cmd)
    if not urls:
        urls = re.findall(r'curl\s+\S+\s+(https?://\S+)', cmd)

    for url in urls:
        # Release controller API
        if "ocp.releases.ci.openshift.org/api/" in url:
            cache_dir = f"{output_dir}/api-responses"
            os.makedirs(cache_dir, exist_ok=True)
            # Create a cache filename from the URL path
            path = re.sub(r'https?://[^/]+/', '', url)
            path = path.replace('/', '_').rstrip('_')
            # Truncate long paths
            if len(path) > 200:
                path = path[:200]
            cache_path = f"{cache_dir}/curl-rc-{path}.json"
            if not os.path.exists(cache_path):
                with open(cache_path, "w") as f:
                    f.write(result.strip())
                found["curl_api"] = found.get("curl_api", 0) + 1

        # Sippy API
        elif "sippy.dptools.openshift.org" in url:
            cache_dir = f"{output_dir}/api-responses"
            os.makedirs(cache_dir, exist_ok=True)
            path = re.sub(r'https?://[^/]+/', '', url)
            path = re.sub(r'[?&]', '_', path).replace('/', '_').rstrip('_')
            if len(path) > 200:
                path = path[:200]
            cache_path = f"{cache_dir}/curl-sippy-{path}.json"
            if not os.path.exists(cache_path):
                with open(cache_path, "w") as f:
                    f.write(result.strip())
                found["curl_api"] = found.get("curl_api", 0) + 1

        # GitHub raw content
        elif "raw.githubusercontent.com" in url:
            cache_dir = f"{output_dir}/gh-cache/raw"
            os.makedirs(cache_dir, exist_ok=True)
            # e.g. openshift/origin/refs/heads/master/test/extended/.../file.go
            path = re.sub(r'https?://raw.githubusercontent.com/', '', url)
            # Flatten to filename
            safe_name = path.replace('/', '_')
            if len(safe_name) > 200:
                safe_name = safe_name[:200]
            cache_path = f"{cache_dir}/{safe_name}"
            if not os.path.exists(cache_path):
                with open(cache_path, "w") as f:
                    f.write(result.strip())
                found["curl_github"] = found.get("curl_github", 0) + 1


def _extract_gh_responses(cmd, result, output_dir, found):
    """Extract and cache gh command responses from a Bash tool result."""
    # gh pr view <number> --repo <org/repo> [--json ...]
    # Also: gh pr view https://github.com/<org>/<repo>/pull/<number> [--json ...]
    pr_matches = list(re.finditer(r"gh pr view (\d+) --repo ([\w.-]+/[\w.-]+)", cmd))
    for m in re.finditer(r"gh pr view https://github\.com/([\w.-]+/[\w.-]+)/pull/(\d+)", cmd):
        pr_matches.append(m)
    for m in pr_matches:
        groups = m.groups()
        if groups[0].isdigit():
            pr_num, repo = groups[0], groups[1]
        else:
            repo, pr_num = groups[0], groups[1]
        cache_dir = f"{output_dir}/gh-cache/{repo}"
        os.makedirs(cache_dir, exist_ok=True)
        cache_path = f"{cache_dir}/{pr_num}.json"
        if os.path.exists(cache_path):
            continue
        # Try to parse the result as JSON
        try:
            data = json.loads(result.strip())
            with open(cache_path, "w") as f:
                json.dump(data, f, indent=2)
            found["gh"] = found.get("gh", 0) + 1
        except json.JSONDecodeError:
            # Multiple chained commands — find JSON blocks
            for jb in re.finditer(r'\{[^{}]+\}', result):
                try:
                    data = json.loads(jb.group())
                    if "number" in data or "title" in data or "author" in data:
                        with open(cache_path, "w") as f:
                            json.dump(data, f, indent=2)
                        found["gh"] = found.get("gh", 0) + 1
                        break
                except json.JSONDecodeError:
                    continue

    # gh pr list --repo <org/repo> [--search ...] [--json ...]
    for m in re.finditer(r"gh pr list --repo ([\w.-]+/[\w.-]+)", cmd):
        repo = m.group(1)
        # Extract search term if present
        search_m = re.search(r'--search\s+"([^"]+)"', cmd)
        search = search_m.group(1) if search_m else "default"
        safe_search = re.sub(r'[^a-zA-Z0-9_-]', '_', search)
        cache_dir = f"{output_dir}/gh-cache/{repo}"
        os.makedirs(cache_dir, exist_ok=True)
        cache_path = f"{cache_dir}/pr-list-{safe_search}.json"
        if os.path.exists(cache_path):
            continue
        with open(cache_path, "w") as f:
            f.write(result.strip())
        found["gh"] = found.get("gh", 0) + 1

    # gh api <endpoint>
    for m in re.finditer(r"gh api\s+(\S+)", cmd):
        endpoint = m.group(1)
        safe_name = re.sub(r'[^a-zA-Z0-9_.-]', '_', endpoint)
        if len(safe_name) > 200:
            safe_name = safe_name[:200]
        cache_dir = f"{output_dir}/gh-cache/api"
        os.makedirs(cache_dir, exist_ok=True)
        cache_path = f"{cache_dir}/{safe_name}.json"
        if os.path.exists(cache_path):
            continue
        with open(cache_path, "w") as f:
            f.write(result.strip())
        found["gh"] = found.get("gh", 0) + 1


def _resolve_persisted_output(content, session_dir):
    """Resolve <persisted-output> references to actual file content."""
    if not isinstance(content, str):
        return content
    m = re.search(r"<persisted-output>\s*.*?saved to:\s*(\S+)", content)
    if not m:
        return content
    ref_path = m.group(1)
    # Strip /home/claude/.claude/ or /home/<user>/.claude/ prefix
    rel = re.sub(r".*/\.claude/", "", ref_path)
    resolved = os.path.join(session_dir, rel)
    if os.path.isfile(resolved):
        with open(resolved) as f:
            return f.read()
    # Try just the tool-results/<id>.txt part
    tr_match = re.search(r"(tool-results/\S+)", ref_path)
    if tr_match:
        for root, dirs, files in os.walk(session_dir):
            candidate = os.path.join(root, tr_match.group(1))
            if os.path.isfile(candidate):
                with open(candidate) as f:
                    return f.read()
    return content


def extract_api_data(session_dir, output_dir, payload_tag):
    version = re.match(r"(\d+\.\d+)", payload_tag).group(1)
    stream_match = re.search(r"\d+\.\d+\.\d+-\d+\.(\w+)-", payload_tag)
    stream = stream_match.group(1) if stream_match else "nightly"
    arch = "amd64"
    arch_match = re.search(rf"\.{stream}-(\w+)-\d{{4}}", payload_tag)
    if arch_match and arch_match.group(1) not in ["2026", "2025", "2024"]:
        arch = arch_match.group(1)

    os.makedirs(f"{output_dir}/api-responses", exist_ok=True)
    os.makedirs(f"{output_dir}/gh-cache", exist_ok=True)
    os.makedirs(f"{output_dir}/test-platform-results/logs", exist_ok=True)

    tool_commands = {}
    found = {"fetch_payloads": False, "fetch_new_prs": 0}

    jsonl_files = []
    for root, dirs, files in os.walk(session_dir):
        for fname in sorted(files):
            if fname.endswith(".jsonl"):
                jsonl_files.append(os.path.join(root, fname))

    for fpath in jsonl_files:
        with open(fpath) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    msg = json.loads(line)
                except Exception:
                    continue

                if msg.get("type") == "assistant":
                    content = msg.get("message", {}).get("content", [])
                    if isinstance(content, list):
                        for b in content:
                            if b.get("type") == "tool_use":
                                tool_commands[b["id"]] = {
                                    "name": b.get("name", ""),
                                    "input": b.get("input", {}),
                                }

                if msg.get("type") == "user":
                    content = msg.get("message", {}).get("content", [])
                    if isinstance(content, list):
                        for b in content:
                            if not isinstance(b, dict) or b.get("type") != "tool_result":
                                continue
                            tid = b.get("tool_use_id", "")
                            rc = b.get("content", "")
                            if isinstance(rc, list):
                                rc = "\n".join(
                                    c.get("text", "")
                                    for c in rc
                                    if isinstance(c, dict)
                                )
                            if not isinstance(rc, str):
                                continue
                            rc = _resolve_persisted_output(rc, session_dir)

                            cmd_info = tool_commands.get(tid, {})
                            cmd = (
                                cmd_info.get("input", {}).get("command", "")
                                if cmd_info.get("name") == "Bash"
                                else ""
                            )

                            if "blockingJobs" in rc and len(rc) > 5000:
                                payloads = None
                                # Try object format: {"payloads": [...]}
                                obj_start = rc.find("{")
                                if obj_start >= 0:
                                    try:
                                        obj = json.loads(rc[obj_start:])
                                        if isinstance(obj, dict) and "payloads" in obj:
                                            payloads = obj["payloads"]
                                    except json.JSONDecodeError:
                                        pass
                                # Try array format: [...]
                                if payloads is None:
                                    arr_start = rc.find("[")
                                    if arr_start >= 0:
                                        try:
                                            payloads = json.loads(rc[arr_start:])
                                        except json.JSONDecodeError:
                                            pass
                                if payloads and isinstance(payloads, list):
                                    outpath = f"{output_dir}/api-responses/fetch-payloads-{arch}-{version}-{stream}.json"
                                    with open(outpath, "w") as out:
                                        json.dump(payloads, out, indent=2)
                                    print(
                                        f"  Saved fetch_payloads: {len(payloads)} payloads"
                                    )
                                    found["fetch_payloads"] = True

                            if "fetch_new_prs" in cmd and len(rc) > 100:
                                m = re.search(
                                    r"(\d+\.\d+\.\d+-\d+\.\w+-(?:\w+-)?[\d-]+)", cmd
                                )
                                if m:
                                    tag = m.group(1)
                                    start = rc.find("[")
                                    if start >= 0:
                                        outpath = f"{output_dir}/api-responses/fetch-new-prs-{tag}.json"
                                        try:
                                            data = json.loads(rc[start:])
                                            with open(outpath, "w") as out:
                                                json.dump(data, out, indent=2)
                                        except json.JSONDecodeError:
                                            with open(outpath, "w") as out:
                                                out.write(rc[start:])
                                        print(f"  Saved fetch_new_prs for {tag}")
                                        found["fetch_new_prs"] += 1

                            # Extract curl responses (API calls, gcsweb, etc.)
                            if "curl " in cmd and rc.strip():
                                _extract_curl_responses(cmd, rc, output_dir, found)

                            # Extract gh command responses
                            if cmd.strip().startswith("gh ") or "&&" in cmd and "gh " in cmd:
                                _extract_gh_responses(cmd, rc, output_dir, found)

    return found


def extract_failed_jobs(fetch_payloads_path, target_tag, output_dir):
    with open(fetch_payloads_path) as f:
        content = f.read().strip()
    # Skip non-JSON header lines (e.g. "Release stream: ...")
    start = content.find("[")
    if start < 0:
        print(f"  WARNING: no JSON array found in {fetch_payloads_path}")
        return
    try:
        payloads = json.loads(content[start:])
    except json.JSONDecodeError:
        print(f"  WARNING: invalid JSON in {fetch_payloads_path}")
        return

    target = None
    for p in payloads:
        if p["tag"] == target_tag:
            target = p
            break

    if not target:
        print(f"  WARNING: {target_tag} not found in payload data")
        return

    direct_jobs = []
    aggregated_jobs = []

    blocking = target.get("results", {}).get("blockingJobs", {})
    for job_short, info in blocking.items():
        if info.get("state") != "Failed":
            continue

        url = info["url"]
        gcs_path = url.replace("https://prow.ci.openshift.org/view/gs/", "")

        if job_short.startswith("aggregated-"):
            aggregated_jobs.append(gcs_path)
        else:
            direct_jobs.append(gcs_path)
            for prev_url in info.get("previousAttemptURLs", []):
                prev_path = prev_url.replace(
                    "https://prow.ci.openshift.org/view/gs/", ""
                )
                direct_jobs.append(prev_path)

    direct_path = f"{output_dir}/failed-direct-jobs.txt"
    agg_path = f"{output_dir}/failed-aggregated-jobs.txt"
    if direct_jobs or not os.path.exists(direct_path):
        with open(direct_path, "w") as f:
            f.write("\n".join(direct_jobs) + "\n" if direct_jobs else "")
    if aggregated_jobs or not os.path.exists(agg_path):
        with open(agg_path, "w") as f:
            f.write("\n".join(aggregated_jobs) + "\n" if aggregated_jobs else "")

    print(f"  Direct failed jobs: {len(direct_jobs)}")
    print(f"  Aggregated failed jobs: {len(aggregated_jobs)}")


def main():
    if len(sys.argv) < 3:
        print(
            f"Usage: {sys.argv[0]} <session-tarball> <output-dir> [payload-tag]"
        )
        print()
        print(
            "If payload-tag is omitted, attempts to detect it from session content."
        )
        sys.exit(1)

    tarball = sys.argv[1]
    output_dir = sys.argv[2]
    payload_tag = sys.argv[3] if len(sys.argv) > 3 else None

    with tempfile.TemporaryDirectory() as tmpdir:
        print(f"Extracting {tarball}...")
        with tarfile.open(tarball) as tf:
            tf.extractall(tmpdir)

        if payload_tag is None:
            for root, dirs, files in os.walk(tmpdir):
                for fname in files:
                    if fname.endswith(".jsonl"):
                        with open(os.path.join(root, fname)) as f:
                            for line in f:
                                m = re.search(
                                    r"analyze-payload\s+(\d+\.\d+\.\d+-\d+\.\w+-(?:\w+-)?[\d-]+)",
                                    line,
                                )
                                if m:
                                    payload_tag = m.group(1)
                                    break
                        if payload_tag:
                            break
                if payload_tag:
                    break

        if not payload_tag:
            print("ERROR: Could not detect payload tag. Please provide it as argument.")
            sys.exit(1)

        print(f"Payload tag: {payload_tag}")
        print(f"Output dir: {output_dir}")

        print("\nExtracting API responses...")
        found = extract_api_data(tmpdir, output_dir, payload_tag)

        if not found["fetch_payloads"]:
            print("  WARNING: fetch_payloads response not found in session")
        if found["fetch_new_prs"] == 0:
            print("  WARNING: no fetch_new_prs responses found in session")
        if found.get("curl_api", 0) > 0:
            print(f"  Cached {found['curl_api']} curl API responses")
        if found.get("curl_github", 0) > 0:
            print(f"  Cached {found['curl_github']} GitHub raw content files")
        if found.get("gh", 0) > 0:
            print(f"  Cached {found['gh']} gh command responses")

        fp_path = None
        for f in os.listdir(f"{output_dir}/api-responses"):
            if f.startswith("fetch-payloads-"):
                fp_path = f"{output_dir}/api-responses/{f}"
                break

        if fp_path:
            print("\nExtracting failed job lists...")
            extract_failed_jobs(fp_path, payload_tag, output_dir)
        else:
            print("\nSkipping failed job extraction (no fetch_payloads data)")

    print("\nDone. Next steps:")
    print(f"  1. Download GCS artifacts:")
    print(
        f"     while read p; do gcloud storage cp -r \"gs://$p/*\" \"{output_dir}/$p/\"; done < {output_dir}/failed-direct-jobs.txt"
    )
    print(
        f"     while read p; do gcloud storage cp -r \"gs://$p/*\" \"{output_dir}/$p/\"; done < {output_dir}/failed-aggregated-jobs.txt"
    )
    print(f"  2. Download reference outputs from the session's GCS artifacts")
    print(f"  3. Create eval case in eval/cases/ with input.yaml and annotations.yaml")


if __name__ == "__main__":
    main()
