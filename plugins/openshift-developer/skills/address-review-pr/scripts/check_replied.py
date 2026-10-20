#!/usr/bin/env python3
"""
Check if bot has already replied to a PR comment or review thread.

Usage:
    check_replied.py <owner> <repo> <pr_number> <id> --type <issue_comment|review|review_comment|review_thread> [--agent-login <login>]

Returns:
    Exit 0: Safe to reply (no existing bot reply found)
    Exit 1: Already replied, or the comment is gone (comment_not_found, no_comments_found)
    Exit 2: Error occurred

Output:
    JSON with check results including reason and any existing reply details.
"""

import argparse
import json
import subprocess
import sys
from collections.abc import Callable
from typing import Any

# Bot accounts that indicate we've already replied
BOT_SIGNATURES = [
    "hypershift-jira-solve-ci[bot]",
    "hypershift-jira-solve-ci",
    "github-actions",
    "github-actions[bot]",
]

# Text signatures that appear in bot replies. Keep the provider-specific
# signature for replies created before the provider-neutral wording was adopted.
REPLY_SIGNATURES = (
    "*AI-assisted response*",
    "*AI-assisted response via Claude Code*",
)


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


def paginated_items(
    endpoint: str, fetch: Callable[[list[str]], Any] | None = None,
) -> list[dict]:
    """Fetch and flatten all pages from a REST array endpoint."""
    pages = (fetch or run_gh)(["api", endpoint, "--paginate", "--slurp"])
    if not isinstance(pages, list) or any(not isinstance(page, list) for page in pages):
        raise ValueError("REST response must contain arrays of items")
    items = [item for page in pages for item in page]
    if any(not isinstance(item, dict) for item in items):
        raise ValueError("REST response contains an invalid item")
    return items


def normalized_login(login: str) -> str:
    """Normalize GitHub App and user forms of the same login."""
    return login.lower().removesuffix("[bot]")


def is_bot_reply(login: str, body: str, agent_login: str = "") -> bool:
    """Check if a comment is from our bot or contains our signature."""
    if not login:
        return False
    if agent_login and normalized_login(login) == normalized_login(agent_login):
        return True
    # Check if author is a known bot (only our specific bots, not all [bot] accounts)
    if login in BOT_SIGNATURES:
        return True
    # Check if body contains one of our signatures (in case of a different bot account)
    if body and any(signature in body for signature in REPLY_SIGNATURES):
        return True
    return False


def check_review_thread(
    owner: str, repo: str, pr_number: int, thread_id: str, agent_login: str = "",
) -> dict:
    """Check if bot already replied to a review thread."""
    # Query with pagination support for PRs with >100 review threads
    query = '''
    query($owner: String!, $repo: String!, $number: Int!, $cursor: String) {
      repository(owner: $owner, name: $repo) {
        pullRequest(number: $number) {
          reviewThreads(first: 100, after: $cursor) {
            nodes {
              id
              isResolved
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
            "safe_to_reply": False,
            "reason": "thread_not_found",
            "message": f"Thread {thread_id} not found - may have been resolved"
        }

    if target_thread.get("isResolved"):
        return {
            "safe_to_reply": False,
            "reason": "thread_resolved",
            "message": f"Thread {thread_id} is resolved"
        }

    # Check if our bot replied after the latest non-agent feedback in the thread.
    # Note: If a thread has >100 comments, we may need additional pagination
    # but this is extremely rare for review threads
    comments = target_thread["comments"]["nodes"]
    latest_feedback = ""
    latest_reply = None
    for comment in comments:
        author = comment["author"]["login"] if comment["author"] else ""
        body = comment.get("body", "")
        if is_bot_reply(author, body, agent_login):
            if latest_reply is None or comment["createdAt"] > latest_reply[0]["createdAt"]:
                latest_reply = (comment, author, body)
        else:
            latest_feedback = max(latest_feedback, comment["createdAt"])

    if latest_reply and latest_feedback and latest_reply[0]["createdAt"] > latest_feedback:
        comment, author, body = latest_reply
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


def check_issue_comment(
    owner: str, repo: str, pr_number: int, comment_id: str, agent_login: str = "",
) -> dict:
    """Check if bot already replied after an issue comment."""
    comments = paginated_items(
        f"repos/{owner}/{repo}/issues/{pr_number}/comments"
    )

    if not comments:
        return {
            "safe_to_reply": False,
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
            "safe_to_reply": False,
            "reason": "comment_not_found",
            "message": f"Comment {comment_id} not found"
        }

    # Check for bot replies after this comment
    for comment in comments:
        if comment["created_at"] <= target_time:
            continue
        author = comment["user"]["login"] if comment.get("user") else ""
        body = comment.get("body", "")
        if is_bot_reply(author, body, agent_login):
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


def check_review(
    owner: str, repo: str, pr_number: int, review_id: str, agent_login: str = "",
) -> dict:
    """Check if bot already replied after a PR review body (REST numeric review id)."""
    review = run_gh([
        "api", f"repos/{owner}/{repo}/pulls/{pr_number}/reviews/{review_id}"
    ])

    if not review:
        return {
            "safe_to_reply": False,
            "reason": "review_not_found",
            "message": f"Review {review_id} not found"
        }

    submitted_at = review.get("submitted_at")
    if not submitted_at:
        return {
            "safe_to_reply": False,
            "reason": "review_not_found",
            "message": f"Review {review_id} has no submitted_at"
        }

    conversation = paginated_items(
        f"repos/{owner}/{repo}/issues/{pr_number}/comments"
    )
    inline = paginated_items(
        f"repos/{owner}/{repo}/pulls/{pr_number}/comments"
    )

    for comment in (conversation or []) + (inline or []):
        if comment.get("created_at", "") <= submitted_at:
            continue
        author = comment["user"]["login"] if comment.get("user") else ""
        body = comment.get("body", "")
        if is_bot_reply(author, body, agent_login):
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


def check_review_comment(
    owner: str, repo: str, pr_number: int, comment_id: str, agent_login: str = "",
) -> dict:
    """Check if bot already replied to a review comment (inline code comment)."""
    comments = paginated_items(
        f"repos/{owner}/{repo}/pulls/{pr_number}/comments"
    )

    if not comments:
        return {
            "safe_to_reply": False,
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
            "safe_to_reply": False,
            "reason": "comment_not_found",
            "message": f"Review comment {comment_id} not found"
        }

    # GitHub points every reply at the thread root, even when the feedback being
    # handled is a child comment. Normalize both sides to that root and only
    # count replies newer than the specific target so later human follow-ups
    # remain eligible.
    target_root_id = int(target_comment.get("in_reply_to_id") or target_comment["id"])
    target_time = target_comment["created_at"]
    for comment in comments:
        comment_root_id = int(comment.get("in_reply_to_id") or comment["id"])
        if comment_root_id != target_root_id or comment["created_at"] <= target_time:
            continue
        author = comment["user"]["login"] if comment.get("user") else ""
        body = comment.get("body", "")
        if is_bot_reply(author, body, agent_login):
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
    parser.add_argument(
        "comment_id",
        help="REST numeric id (issue_comment, review, review_comment) or GraphQL global thread id (review_thread)",
    )
    parser.add_argument(
        "--type",
        choices=["issue_comment", "review", "review_comment", "review_thread"],
        required=True,
        help="Type of comment to check"
    )
    parser.add_argument(
        "--agent-login",
        help="Agent GitHub login (otherwise discovered from the authenticated gh user when available)",
    )

    args = parser.parse_args()

    try:
        agent_login = args.agent_login or ""
        if not agent_login:
            try:
                user = run_gh(["api", "user"])
                discovered_login = user.get("login", "") if isinstance(user, dict) else ""
                if isinstance(discovered_login, str):
                    agent_login = discovered_login
            except (RuntimeError, TypeError, ValueError, OSError):
                # Identity discovery is optional. Known account and body
                # signatures still provide best-effort duplicate detection.
                pass
        if args.type == "review_thread":
            result = check_review_thread(
                args.owner, args.repo, args.pr_number, args.comment_id, agent_login,
            )
        elif args.type == "issue_comment":
            result = check_issue_comment(
                args.owner, args.repo, args.pr_number, args.comment_id, agent_login,
            )
        elif args.type == "review":
            result = check_review(
                args.owner, args.repo, args.pr_number, args.comment_id, agent_login,
            )
        elif args.type == "review_comment":
            result = check_review_comment(
                args.owner, args.repo, args.pr_number, args.comment_id, agent_login,
            )
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
