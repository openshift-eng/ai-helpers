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

                            cmd_info = tool_commands.get(tid, {})
                            cmd = (
                                cmd_info.get("input", {}).get("command", "")
                                if cmd_info.get("name") == "Bash"
                                else ""
                            )

                            if "blockingJobs" in rc and len(rc) > 5000:
                                start = rc.find("[")
                                if start >= 0:
                                    try:
                                        data = json.loads(rc[start:])
                                        outpath = f"{output_dir}/api-responses/fetch-payloads-{arch}-{version}-{stream}.json"
                                        with open(outpath, "w") as out:
                                            json.dump(data, out, indent=2)
                                        print(
                                            f"  Saved fetch_payloads: {len(data)} payloads"
                                        )
                                        found["fetch_payloads"] = True
                                    except json.JSONDecodeError:
                                        pass

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

    return found


def extract_failed_jobs(fetch_payloads_path, target_tag, output_dir):
    with open(fetch_payloads_path) as f:
        payloads = json.load(f)

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

    with open(f"{output_dir}/failed-direct-jobs.txt", "w") as f:
        f.write("\n".join(direct_jobs) + "\n" if direct_jobs else "")
    with open(f"{output_dir}/failed-aggregated-jobs.txt", "w") as f:
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
