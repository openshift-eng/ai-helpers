#!/usr/bin/env python3
"""
Check if bot has already replied to a PR comment or review thread.

Usage:
    check_replied.py <owner> <repo> <pr_number> <comment_id> --type <issue_comment|review_thread|review_comment>

Returns:
    Exit 0: Safe to reply (no existing bot reply found)
    Exit 1: Already replied (bot reply exists after this comment)
    Exit 2: Error occurred

Output:
    JSON with check results including reason and any existing reply details.
"""

import argparse
import json
import subprocess
import sys
from typing import Any

# Bot accounts that indicate we've already replied
BOT_SIGNATURES = [
    "hypershift-jira-solve-ci[bot]",
    "hypershift-jira-solve-ci",
]

# Text signature that appears in bot replies
REPLY_SIGNATURE = "*AI-assisted response via Claude Code*"


def run_gh(args: list[str]) -> Any:
    """Run gh CLI command and return JSON output."""
    result = subprocess.run(
        ["gh"] + args,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"gh command failed: {result.stderr}")
    return json.loads(result.stdout) if result.stdout.strip() else None


def is_bot_reply(login: str, body: str) -> bool:
    """Check if a comment is from our bot or contains our signature."""
    if not login:
        return False
    # Check if author is a known bot (only our specific bots, not all [bot] accounts)
    if login in BOT_SIGNATURES:
        return True
    # Check if body contains our signature (in case of different bot account)
    if body and REPLY_SIGNATURE in body:
        return True
    return False


def check_review_thread(owner: str, repo: str, pr_number: int, thread_id: str) -> dict:
    """Check if bot already replied to a review thread."""
    # Query with pagination support for PRs with >100 review threads
    query = '''
    query($owner: String!, $repo: String!, $number: Int!, $cursor: String) {
      repository(owner: $owner, name: $repo) {
        pullRequest(number: $number) {
          reviewThreads(first: 100, after: $cursor) {
            nodes {
              id
              comments(first: 100) {
                nodes {
                  id
                  author { login }
                  body
                  createdAt
                }
                pageInfo {
                  hasNextPage
                  endCursor
                }
              }
            }
            pageInfo {
              hasNextPage
              endCursor
            }
          }
        }
      }
    }
    '''

    # Fetch all review threads with pagination
    all_threads = []
    cursor = None

    while True:
        args = [
            "api", "graphql",
            "-f", f"query={query}",
            "-f", f"owner={owner}",
            "-f", f"repo={repo}",
            "-F", f"number={pr_number}"
        ]
        if cursor:
            args.extend(["-f", f"cursor={cursor}"])

        result = run_gh(args)

        threads_data = result["data"]["repository"]["pullRequest"]["reviewThreads"]
        all_threads.extend(threads_data["nodes"])

        page_info = threads_data["pageInfo"]
        if not page_info["hasNextPage"]:
            break
        cursor = page_info["endCursor"]

    # Find the specific thread
    target_thread = None
    for thread in all_threads:
        if thread["id"] == thread_id:
            target_thread = thread
            break

    if not target_thread:
        return {
            "safe_to_reply": True,
            "reason": "thread_not_found",
            "message": f"Thread {thread_id} not found - may have been resolved"
        }

    # Check if any bot reply exists in the thread
    # Note: If a thread has >100 comments, we may need additional pagination
    # but this is extremely rare for review threads
    comments = target_thread["comments"]["nodes"]
    for comment in comments:
        author = comment["author"]["login"] if comment["author"] else ""
        body = comment.get("body", "")
        if is_bot_reply(author, body):
            return {
                "safe_to_reply": False,
                "reason": "bot_already_replied",
                "existing_reply": {
                    "author": author,
                    "created_at": comment["createdAt"],
                    "body_preview": body[:200] if body else ""
                }
            }

    return {
        "safe_to_reply": True,
        "reason": "no_bot_reply_found"
    }


def check_issue_comment(owner: str, repo: str, pr_number: int, comment_id: str) -> dict:
    """Check if bot already replied after an issue comment."""
    try:
        comments = run_gh([
            "api", f"repos/{owner}/{repo}/issues/{pr_number}/comments", "--paginate"
        ])
    except RuntimeError as e:
        return {
            "safe_to_reply": False,
            "reason": "api_error",
            "message": str(e)
        }

    if not comments:
        return {
            "safe_to_reply": True,
            "reason": "no_comments_found"
        }

    # Find the target comment and check for bot replies after it
    target_comment = None
    target_time = None

    for comment in comments:
        if str(comment["id"]) == str(comment_id):
            target_comment = comment
            target_time = comment["created_at"]
            break

    if not target_comment:
        return {
            "safe_to_reply": True,
            "reason": "comment_not_found",
            "message": f"Comment {comment_id} not found"
        }

    # Check for bot replies after this comment
    for comment in comments:
        if comment["created_at"] <= target_time:
            continue
        author = comment["user"]["login"] if comment.get("user") else ""
        body = comment.get("body", "")
        if is_bot_reply(author, body):
            return {
                "safe_to_reply": False,
                "reason": "bot_replied_after",
                "existing_reply": {
                    "author": author,
                    "created_at": comment["created_at"],
                    "body_preview": body[:200] if body else ""
                }
            }

    return {
        "safe_to_reply": True,
        "reason": "no_bot_reply_after"
    }


def check_review_comment(owner: str, repo: str, pr_number: int, comment_id: str) -> dict:
    """Check if bot already replied to a review comment (inline code comment)."""
    try:
        comments = run_gh([
            "api", f"repos/{owner}/{repo}/pulls/{pr_number}/comments", "--paginate"
        ])
    except RuntimeError as e:
        return {
            "safe_to_reply": False,
            "reason": "api_error",
            "message": str(e)
        }

    if not comments:
        return {
            "safe_to_reply": True,
            "reason": "no_comments_found"
        }

    # Find the target comment
    target_comment = None
    for comment in comments:
        if str(comment["id"]) == str(comment_id):
            target_comment = comment
            break

    if not target_comment:
        return {
            "safe_to_reply": True,
            "reason": "comment_not_found",
            "message": f"Review comment {comment_id} not found"
        }

    # Check for bot replies in the same thread (same in_reply_to_id or replies to this comment)
    target_id = int(comment_id)
    for comment in comments:
        # Check if this is a reply to the target comment
        in_reply_to = comment.get("in_reply_to_id")
        if in_reply_to == target_id:
            author = comment["user"]["login"] if comment.get("user") else ""
            body = comment.get("body", "")
            if is_bot_reply(author, body):
                return {
                    "safe_to_reply": False,
                    "reason": "bot_already_replied",
                    "existing_reply": {
                        "author": author,
                        "created_at": comment["created_at"],
                        "body_preview": body[:200] if body else ""
                    }
                }

    return {
        "safe_to_reply": True,
        "reason": "no_bot_reply_found"
    }


def main():
    parser = argparse.ArgumentParser(
        description="Check if bot has already replied to a PR comment"
    )
    parser.add_argument("owner", help="Repository owner (e.g., 'openshift')")
    parser.add_argument("repo", help="Repository name (e.g., 'hypershift')")
    parser.add_argument("pr_number", type=int, help="Pull request number")
    parser.add_argument("comment_id", help="Comment or thread ID to check")
    parser.add_argument(
        "--type",
        choices=["issue_comment", "review_thread", "review_comment"],
        required=True,
        help="Type of comment to check"
    )

    args = parser.parse_args()

    try:
        if args.type == "review_thread":
            result = check_review_thread(args.owner, args.repo, args.pr_number, args.comment_id)
        elif args.type == "issue_comment":
            result = check_issue_comment(args.owner, args.repo, args.pr_number, args.comment_id)
        elif args.type == "review_comment":
            result = check_review_comment(args.owner, args.repo, args.pr_number, args.comment_id)
        else:
            result = {"error": f"Unknown type: {args.type}"}
            print(json.dumps(result, indent=2))
            sys.exit(2)

        print(json.dumps(result, indent=2))
        sys.exit(0 if result.get("safe_to_reply", False) else 1)

    except (RuntimeError, KeyError, TypeError, ValueError) as e:
        result = {"error": str(e), "safe_to_reply": False, "reason": "error_fallback"}
        print(json.dumps(result, indent=2))
        sys.exit(2)


if __name__ == "__main__":
    main()
