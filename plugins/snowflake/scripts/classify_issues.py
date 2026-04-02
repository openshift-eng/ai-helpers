#!/usr/bin/env python3
"""Classify Jira issues into activity types using Claude via Vertex AI.

Reads a JSON array of issues, sends them in batches to Claude for
classification, and writes the results back with an activity_type field.

Requires:
  - gcloud CLI authenticated (gcloud auth login)
  - Environment variables: CLOUD_ML_REGION, ANTHROPIC_VERTEX_PROJECT_ID
  - Optional: ANTHROPIC_SMALL_FAST_MODEL (default: claude-sonnet-4-6)
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.request
import urllib.error

ACTIVITY_TYPE_DEFINITIONS = {
    "Associate Wellness & Development": (
        "Work related to team member growth, training, learning, mentorship, "
        "onboarding, conferences, career development, process documentation, "
        "knowledge sharing, and team building activities."
    ),
    "Incidents & Support": (
        "Reactive work responding to production incidents, customer escalations, "
        "on-call duties, access requests, account provisioning, firefighting, "
        "service outages, and direct support activities."
    ),
    "Security & Compliance": (
        "Work related to CVE remediation, security vulnerabilities, compliance "
        "requirements, credential management, security audits, FIPS compliance, "
        "and regulatory requirements."
    ),
    "Quality / Stability / Reliability": (
        "Work focused on improving CI/CD reliability, fixing flaky tests, test "
        "infrastructure improvements, build system improvements, monitoring, "
        "observability, bug fixes, and overall system stability."
    ),
    "Future Sustainability": (
        "Technical debt reduction, architecture improvements, capacity planning, "
        "infrastructure modernization, deprecation work, long-term scalability "
        "improvements, and foundational changes that prevent future issues."
    ),
    "Product / Portfolio Work": (
        "New feature development, product roadmap items, enhancements, "
        "customer-driven feature requests, integrations, and planned development "
        "work that adds new capabilities."
    ),
    "Uncategorized": (
        "Issues that don't clearly fit into any of the above categories, or where "
        "there is insufficient information to make a determination."
    ),
}

VALID_CATEGORIES = set(ACTIVITY_TYPE_DEFINITIONS.keys())


def build_prompt(batch):
    """Build the classification prompt for a batch of issues."""
    defs_text = "\n\n".join(
        f"{name}: {desc}" for name, desc in ACTIVITY_TYPE_DEFINITIONS.items()
    )

    issue_blocks = []
    for issue in batch:
        desc = (issue.get("DESCRIPTION_EXCERPT") or issue.get("description_excerpt") or "")[:800]
        block = (
            f"ISSUE: {issue.get('ISSUEKEY', issue.get('issue_key', ''))}\n"
            f"PROJECT: {issue.get('PROJECT_KEY', issue.get('project_key', ''))}\n"
            f"TYPE: {issue.get('ISSUE_TYPE', issue.get('issue_type', ''))}\n"
            f"STATUS: {issue.get('STATUS', issue.get('status', ''))}\n"
            f"COMPONENTS: {issue.get('COMPONENTS', issue.get('components', ''))}\n"
            f"SUMMARY: {issue.get('SUMMARY', issue.get('summary', ''))}\n"
            f"DESCRIPTION: {desc}"
        )
        issue_blocks.append(block)

    issues_text = "\n\n---\n\n".join(issue_blocks)

    return (
        "You are classifying Jira issues into activity types for an engineering "
        "organization. For each issue below, assign exactly ONE of these activity types:\n\n"
        f"{defs_text}\n\n"
        "IMPORTANT RULES:\n"
        "- Use ONLY the exact category names listed above.\n"
        "- Base your classification on ALL available signals: summary, description, "
        "issue type, components, and project context.\n"
        "- Security & Compliance always wins if security-related content is present.\n"
        "- Incidents & Support takes precedence for production emergencies.\n"
        "- If an issue is about CI failures, test flakiness, or build problems, "
        "classify as 'Quality / Stability / Reliability'.\n"
        "- If an issue is about new features, enhancements, or roadmap items, "
        "classify as 'Product / Portfolio Work'.\n"
        "- Only use 'Uncategorized' when there is genuinely insufficient information.\n\n"
        "Return your answer as a JSON array with objects containing 'issue_key' and "
        "'activity_type'. Return ONLY the JSON, no other text.\n\n"
        f"ISSUES:\n\n{issues_text}"
    )


def get_gcloud_token():
    """Get OAuth token via gcloud CLI."""
    try:
        result = subprocess.run(
            ["gcloud", "auth", "print-access-token"],
            capture_output=True, text=True, check=True, timeout=30,
        )
        token = result.stdout.strip()
        if not token:
            raise RuntimeError("gcloud auth print-access-token returned empty")
        return token
    except FileNotFoundError:
        print("Error: gcloud CLI not found. Install it from https://cloud.google.com/sdk", file=sys.stderr)
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        print(f"Error: gcloud auth failed: {e.stderr}", file=sys.stderr)
        print("Run: gcloud auth login", file=sys.stderr)
        sys.exit(1)


def classify_batch(batch, token, endpoint, model):
    """Send a batch to Claude via Vertex AI and return (classifications, usage)."""
    prompt = build_prompt(batch)

    body = json.dumps({
        "anthropic_version": "vertex-2023-10-16",
        "max_tokens": 4096,
        "messages": [{"role": "user", "content": prompt}],
    }).encode("utf-8")

    req = urllib.request.Request(
        endpoint,
        data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    resp = urllib.request.urlopen(req, timeout=120)
    resp_body = json.loads(resp.read().decode("utf-8"))

    raw_text = resp_body["content"][0]["text"]
    # Strip markdown code fences if present
    clean_text = re.sub(r"^```json\s*", "", raw_text.strip())
    clean_text = re.sub(r"\s*```$", "", clean_text).strip()

    results = json.loads(clean_text)

    # Validate and normalize category names
    for item in results:
        if item.get("activity_type") not in VALID_CATEGORIES:
            item["activity_type"] = "Uncategorized"

    usage = resp_body.get("usage", {})
    return results, usage


def main():
    parser = argparse.ArgumentParser(description="Classify Jira issues using Claude via Vertex AI")
    parser.add_argument("--input", required=True, help="Input JSON file (array of issues)")
    parser.add_argument("--output", required=True, help="Output JSON file (issues with activity_type)")
    parser.add_argument("--batch-size", type=int, default=15, help="Issues per API call (default: 15)")
    parser.add_argument("--model", default=None, help="Claude model ID (default: from env or claude-sonnet-4-6)")
    args = parser.parse_args()

    # Read env vars
    region = os.environ.get("CLOUD_ML_REGION")
    project_id = os.environ.get("ANTHROPIC_VERTEX_PROJECT_ID")

    if not region or not project_id:
        print("Error: CLOUD_ML_REGION and ANTHROPIC_VERTEX_PROJECT_ID environment variables are required.", file=sys.stderr)
        print("These are typically set in your devcontainer or shell profile.", file=sys.stderr)
        sys.exit(1)

    model = args.model or os.environ.get("ANTHROPIC_SMALL_FAST_MODEL", "claude-sonnet-4-6")
    endpoint = (
        f"https://{region}-aiplatform.googleapis.com/v1/projects/{project_id}"
        f"/locations/{region}/publishers/anthropic/models/{model}:rawPredict"
    )

    # Load issues
    with open(args.input) as f:
        issues = json.load(f)

    print(f"Loaded {len(issues)} issues from {args.input}")
    print(f"Model: {model} | Region: {region} | Project: {project_id}")

    # Get auth token
    token = get_gcloud_token()

    # Split into batches
    batches = [issues[i:i + args.batch_size] for i in range(0, len(issues), args.batch_size)]
    print(f"Processing {len(batches)} batches of up to {args.batch_size} issues\n")

    all_classifications = []
    total_input_tokens = 0
    total_output_tokens = 0
    start_time = time.time()

    for i, batch in enumerate(batches):
        print(f"  Batch {i + 1}/{len(batches)} ({len(batch)} issues)...", end="", flush=True)

        last_error = None
        for attempt in range(3):
            try:
                results, usage = classify_batch(batch, token, endpoint, model)
                all_classifications.extend(results)
                total_input_tokens += usage.get("input_tokens", 0)
                total_output_tokens += usage.get("output_tokens", 0)
                print(" done")
                break
            except urllib.error.HTTPError as e:
                last_error = e
                if e.code == 401:
                    print(" auth expired, refreshing token...", end="", flush=True)
                    token = get_gcloud_token()
                elif e.code == 429 or e.code >= 500:
                    wait = 5 * (attempt + 1)
                    print(f" retrying in {wait}s...", end="", flush=True)
                    time.sleep(wait)
                else:
                    error_body = e.read().decode("utf-8", errors="replace")
                    print(f" error {e.code}: {error_body[:200]}", file=sys.stderr)
                    raise
            except Exception as e:
                last_error = e
                wait = 5 * (attempt + 1)
                print(f" error: {e}, retrying in {wait}s...", end="", flush=True)
                time.sleep(wait)
        else:
            print(f" FAILED after 3 attempts: {last_error}", file=sys.stderr)

        if i < len(batches) - 1:
            time.sleep(1)

    # Build lookup of classifications
    classified_keys = {item["issue_key"]: item["activity_type"] for item in all_classifications}

    # Merge classifications back into issues
    issue_key_field = "ISSUEKEY" if "ISSUEKEY" in issues[0] else "issue_key"
    output = []
    missing = 0
    for issue in issues:
        key = issue[issue_key_field]
        activity_type = classified_keys.get(key)
        if not activity_type:
            activity_type = "Uncategorized"
            missing += 1

        output.append({
            "issue_key": key,
            "project_key": issue.get("PROJECT_KEY", issue.get("project_key", "")),
            "summary": issue.get("SUMMARY", issue.get("summary", "")),
            "activity_type": activity_type,
            "issue_type": issue.get("ISSUE_TYPE", issue.get("issue_type", "")),
            "status": issue.get("STATUS", issue.get("status", "")),
            "components": issue.get("COMPONENTS", issue.get("components", "")),
            "created": issue.get("CREATED", issue.get("created", "")),
        })

    # Write output
    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    with open(args.output, "w") as f:
        json.dump(output, f, indent=2)

    elapsed = time.time() - start_time

    print(f"\nClassified {len(output)} issues → {args.output}")
    if missing:
        print(f"  ({missing} issues defaulted to 'Uncategorized' due to missing API response)")

    # Print distribution
    from collections import Counter
    dist = Counter(item["activity_type"] for item in output)
    print("\nActivity Type Distribution:")
    for cat, count in dist.most_common():
        pct = count / len(output) * 100
        print(f"  {cat:<45s} {count:>4d} ({pct:.1f}%)")

    # Print cost summary
    total_tokens = total_input_tokens + total_output_tokens
    print(f"\nAPI Usage:")
    print(f"  Input tokens:  {total_input_tokens:>10,}")
    print(f"  Output tokens: {total_output_tokens:>10,}")
    print(f"  Total tokens:  {total_tokens:>10,}")
    print(f"  API calls:     {len(batches):>10}")
    print(f"  Wall time:     {elapsed:>9.1f}s")
    # Estimate cost (Sonnet 4: $3/MTok input, $15/MTok output)
    est_input_cost = total_input_tokens / 1_000_000 * 3.0
    est_output_cost = total_output_tokens / 1_000_000 * 15.0
    est_total = est_input_cost + est_output_cost
    print(f"  Est. cost:     ${est_total:>8.4f} (Sonnet pricing: $3/MTok in, $15/MTok out)")

    # Write usage summary to sidecar file for report generation
    usage_summary = (
        f"{total_input_tokens:,} input + {total_output_tokens:,} output = "
        f"{total_tokens:,} tokens, {len(batches)} API calls, "
        f"~${est_total:.4f} ({model})"
    )
    usage_path = os.path.splitext(args.output)[0] + "_usage.txt"
    with open(usage_path, "w") as f:
        f.write(usage_summary)
    print(f"  Usage file:    {usage_path}")


if __name__ == "__main__":
    main()
