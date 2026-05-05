#!/usr/bin/env python3
"""
Score plugins for staleness based on git history and structural signals.

Reads .pruneprotect, walks plugins/*, gathers git metadata, and outputs
a JSON report of scored candidates.

Usage: score-plugins.py [--threshold N] [repo-root]
  --threshold N   Minimum score to flag as candidate (default: 3)
  repo-root       Path to the repository root (default: cwd)
"""

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def parse_args():
    threshold = 3
    repo_root = os.getcwd()
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "--threshold" and i + 1 < len(args):
            threshold = int(args[i + 1])
            i += 2
        else:
            repo_root = args[i]
            i += 1
    return threshold, Path(repo_root)


def load_pruneprotect(repo_root):
    protect_file = repo_root / ".pruneprotect"
    protected = []
    if protect_file.exists():
        for line in protect_file.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            protected.append(line)
    return protected


def is_protected(path, protected):
    for prefix in protected:
        if path.startswith(prefix) or path.rstrip("/") == prefix.rstrip("/"):
            return True
    return False


def git(repo_root, *args):
    result = subprocess.run(
        ["git", "-C", str(repo_root)] + list(args),
        capture_output=True, text=True, timeout=30,
    )
    return result.stdout.strip()


def get_first_commit_date(repo_root, path):
    out = git(repo_root, "log", "--diff-filter=A", "--format=%aI", "--reverse", "--", path)
    if not out:
        return None
    first_line = out.splitlines()[0].strip()
    return datetime.fromisoformat(first_line) if first_line else None


def get_last_commit_date(repo_root, path):
    out = git(repo_root, "log", "-1", "--format=%aI", "--", path)
    if not out:
        return None
    return datetime.fromisoformat(out)


def get_last_two_commit_dates(repo_root, path):
    out = git(repo_root, "log", "-2", "--format=%aI", "--", path)
    dates = []
    for line in out.splitlines():
        line = line.strip()
        if line:
            dates.append(datetime.fromisoformat(line))
    return dates


def get_commit_count(repo_root, path):
    out = git(repo_root, "rev-list", "--count", "HEAD", "--", path)
    try:
        return int(out)
    except (ValueError, TypeError):
        return 0


def get_contributor_count(repo_root, path):
    out = git(repo_root, "shortlog", "-sn", "--all", "--", path)
    return len([l for l in out.splitlines() if l.strip()])


def get_contributors(repo_root, path):
    out = git(repo_root, "shortlog", "-sn", "--all", "--", path)
    contributors = []
    for line in out.splitlines():
        line = line.strip()
        if line:
            parts = line.split("\t", 1)
            if len(parts) == 2:
                contributors.append({"commits": int(parts[0].strip()), "name": parts[1].strip()})
    return contributors


def read_plugin_json(plugin_dir):
    pj = plugin_dir / ".claude-plugin" / "plugin.json"
    if pj.exists():
        with open(pj) as f:
            return json.load(f)
    return None


def count_commands(plugin_dir):
    cmd_dir = plugin_dir / "commands"
    if not cmd_dir.is_dir():
        return 0
    return len(list(cmd_dir.glob("*.md")))


def count_skills(plugin_dir):
    skills_dir = plugin_dir / "skills"
    if not skills_dir.is_dir():
        return 0
    return len(list(skills_dir.glob("*/SKILL.md")))


def has_hooks(plugin_dir):
    return (plugin_dir / "hooks").is_dir()


def readme_size(plugin_dir):
    readme = plugin_dir / "README.md"
    if readme.exists():
        return readme.stat().st_size
    return 0


def detect_batch_update_dates(all_dates):
    """If more than 5 plugins share the same last-commit date (day), it's likely a batch update."""
    from collections import Counter
    day_counts = Counter()
    for d in all_dates:
        if d:
            day_counts[d.date()] += 1
    return {day for day, count in day_counts.items() if count > 5}


def score_plugin(plugin_info, now, batch_dates):
    score = 0
    reasons = []

    last_date = plugin_info["last_commit_date"]
    if last_date and last_date.date() in batch_dates and plugin_info.get("second_commit_date"):
        effective_date = plugin_info["second_commit_date"]
        plugin_info["effective_last_date"] = effective_date.isoformat()
        plugin_info["batch_update_detected"] = True
    else:
        effective_date = last_date
        plugin_info["effective_last_date"] = last_date.isoformat() if last_date else None
        plugin_info["batch_update_detected"] = False

    if effective_date:
        days_inactive = (now - effective_date).days
        plugin_info["days_since_last_meaningful_commit"] = days_inactive
        if days_inactive > 90:
            score += 2
            reasons.append(f"Last meaningful commit {days_inactive} days ago (>90)")
    else:
        plugin_info["days_since_last_meaningful_commit"] = None

    first_date = plugin_info.get("first_commit_date")
    plugin_age_days = (now - first_date).days if first_date else None
    plugin_info["plugin_age_days"] = plugin_age_days
    is_young = plugin_age_days is not None and plugin_age_days < 90

    if is_young:
        reasons.append(f"Young plugin ({plugin_age_days} days old) — skipping maturity signals")
    else:
        commit_count = plugin_info["commit_count"]
        if commit_count <= 3:
            score += 2
            reasons.append(f"Only {commit_count} commits total (<=3)")
        elif commit_count <= 5:
            score += 1
            reasons.append(f"Only {commit_count} commits total (<=5)")

        contributor_count = plugin_info["contributor_count"]
        if contributor_count == 1 and effective_date:
            days_inactive = (now - effective_date).days
            if days_inactive > 60:
                score += 1
                reasons.append(f"Single contributor, inactive {days_inactive} days (>60)")

        version = plugin_info.get("version", "")
        if version.startswith("0.0."):
            score += 1
            reasons.append(f"Version stuck at {version}")

        num_commands = plugin_info["command_count"]
        num_skills = plugin_info["skill_count"]
        if num_commands + num_skills <= 2:
            score += 1
            reasons.append(f"Small footprint ({num_commands} commands, {num_skills} skills)")

        rs = plugin_info["readme_bytes"]
        if rs == 0:
            score += 1
            reasons.append("No README")
        elif rs < 100:
            score += 1
            reasons.append(f"Minimal README ({rs} bytes)")

    plugin_info["score"] = score
    plugin_info["reasons"] = reasons
    return score


def main():
    threshold, repo_root = parse_args()
    now = datetime.now(timezone.utc)
    protected = load_pruneprotect(repo_root)
    plugins_dir = repo_root / "plugins"

    if not plugins_dir.is_dir():
        print(json.dumps({"error": "No plugins/ directory found"}, indent=2))
        sys.exit(1)

    plugins = []
    all_last_dates = []

    for plugin_dir in sorted(plugins_dir.iterdir()):
        if not plugin_dir.is_dir():
            continue

        rel_path = f"plugins/{plugin_dir.name}/"
        meta = read_plugin_json(plugin_dir)

        last_date = get_last_commit_date(repo_root, rel_path)
        first_date = get_first_commit_date(repo_root, rel_path)
        all_last_dates.append(last_date)
        dates = get_last_two_commit_dates(repo_root, rel_path)

        info = {
            "name": meta.get("name", plugin_dir.name) if meta else plugin_dir.name,
            "path": rel_path,
            "version": meta.get("version", "unknown") if meta else "unknown",
            "description": meta.get("description", "") if meta else "",
            "protected": is_protected(rel_path, protected),
            "command_count": count_commands(plugin_dir),
            "skill_count": count_skills(plugin_dir),
            "has_hooks": has_hooks(plugin_dir),
            "readme_bytes": readme_size(plugin_dir),
            "first_commit_date": first_date,
            "last_commit_date": last_date,
            "second_commit_date": dates[1] if len(dates) > 1 else None,
            "commit_count": get_commit_count(repo_root, rel_path),
            "contributor_count": get_contributor_count(repo_root, rel_path),
            "contributors": get_contributors(repo_root, rel_path),
        }
        plugins.append(info)

    batch_dates = detect_batch_update_dates(all_last_dates)

    for p in plugins:
        if p["protected"]:
            p["score"] = 0
            p["reasons"] = ["Protected by .pruneprotect"]
            p["candidate"] = False
        else:
            score_plugin(p, now, batch_dates)
            p["candidate"] = p["score"] >= threshold

    # Serialize datetimes to ISO strings
    for p in plugins:
        for key in ("first_commit_date", "last_commit_date", "second_commit_date"):
            if isinstance(p[key], datetime):
                p[key] = p[key].isoformat()

    output = {
        "generated_at": now.isoformat(),
        "threshold": threshold,
        "batch_update_dates": [d.isoformat() for d in sorted(batch_dates)],
        "summary": {
            "total_plugins": len(plugins),
            "protected": sum(1 for p in plugins if p["protected"]),
            "candidates": sum(1 for p in plugins if p["candidate"]),
            "safe": sum(1 for p in plugins if not p["candidate"] and not p["protected"]),
        },
        "candidates": [p for p in plugins if p["candidate"]],
        "protected": [p for p in plugins if p["protected"]],
        "safe": [p for p in plugins if not p["candidate"] and not p["protected"]],
    }

    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
