#!/usr/bin/env python3
"""Bayesian estimation of activity type distributions from a sample.

Uses Dirichlet-Multinomial conjugate model to estimate category proportions
with credible intervals. Only requires Python stdlib (random, math, json).

Workflow:
  1. Read all fetched issues (unclassified)
  2. Draw a stratified random sample (by project)
  3. Classify only the sample via classify_issues.py
  4. Compute Bayesian posterior estimates for the full population

Usage:
    python3 sample_and_estimate.py \
        --input issues.json \
        --classified-sample classified_sample.json \
        --output estimates.json \
        [--sample-size 400] \
        [--confidence 0.95] \
        [--seed 42]

    # Or just draw the sample (before classification):
    python3 sample_and_estimate.py \
        --input issues.json \
        --draw-sample sample_to_classify.json \
        [--sample-size 400] \
        [--seed 42]
"""

import argparse
import json
import math
import os
import random
import sys
from collections import Counter

ACTIVITY_TYPES = [
    "Associate Wellness & Development",
    "Incidents & Support",
    "Security & Compliance",
    "Quality / Stability / Reliability",
    "Future Sustainability",
    "Product / Portfolio Work",
    "Uncategorized",
]


def stratified_sample(issues, sample_size, seed=42):
    """Draw a stratified random sample proportional to project size.

    Ensures every project gets at least 1 issue in the sample (if possible),
    then allocates remaining slots proportionally.
    """
    rng = random.Random(seed)

    by_project = {}
    for issue in issues:
        proj = issue.get("PROJECT_KEY", issue.get("project_key", "UNKNOWN"))
        by_project.setdefault(proj, []).append(issue)

    total = len(issues)
    n = min(sample_size, total)

    if n >= total:
        return list(issues), {p: len(v) for p, v in by_project.items()}

    # Guarantee at least 1 per project, then proportional allocation
    allocations = {}
    remaining = n
    for proj, proj_issues in by_project.items():
        allocations[proj] = min(1, len(proj_issues))
        remaining -= allocations[proj]

    # Distribute remaining proportionally
    if remaining > 0:
        proportional = {}
        for proj, proj_issues in by_project.items():
            proportional[proj] = len(proj_issues) / total * n
        # Subtract already-allocated minimum
        for proj in by_project:
            proportional[proj] = max(0, proportional[proj] - allocations[proj])
        # Normalize to fill remaining slots
        prop_total = sum(proportional.values())
        if prop_total > 0:
            for proj in by_project:
                extra = int(proportional[proj] / prop_total * remaining)
                extra = min(extra, len(by_project[proj]) - allocations[proj])
                allocations[proj] += extra
                remaining -= extra

        # Distribute any leftover slots to largest projects
        if remaining > 0:
            projects_by_size = sorted(by_project.keys(),
                                      key=lambda p: len(by_project[p]),
                                      reverse=True)
            for proj in projects_by_size:
                if remaining <= 0:
                    break
                can_add = len(by_project[proj]) - allocations[proj]
                add = min(can_add, remaining)
                allocations[proj] += add
                remaining -= add

    # Draw samples
    sample = []
    sample_counts = {}
    for proj, count in allocations.items():
        proj_issues = by_project[proj]
        drawn = rng.sample(proj_issues, min(count, len(proj_issues)))
        sample.extend(drawn)
        sample_counts[proj] = len(drawn)

    rng.shuffle(sample)
    return sample, sample_counts


def dirichlet_sample(alphas, n_samples=10000, seed=None):
    """Sample from Dirichlet distribution using Gamma variates (stdlib only)."""
    rng = random.Random(seed)
    samples = []
    for _ in range(n_samples):
        raw = [rng.gammavariate(a, 1.0) for a in alphas]
        total = sum(raw)
        if total == 0:
            # Degenerate case — uniform
            k = len(alphas)
            samples.append([1.0 / k] * k)
        else:
            samples.append([x / total for x in raw])
    return samples


def estimate_distribution(classified_issues, categories=None, prior=1.0,
                          confidence=0.95, n_mc_samples=10000, seed=None):
    """Bayesian estimation of category proportions with credible intervals.

    Args:
        classified_issues: list of dicts with 'activity_type' field
        categories: list of category names (default: ACTIVITY_TYPES)
        prior: Dirichlet prior concentration per category (1.0 = uniform)
        confidence: credible interval width (default 0.95)
        n_mc_samples: Monte Carlo samples for interval estimation
        seed: random seed for reproducibility

    Returns:
        dict with 'estimates' (per-category), 'sample_size', 'total_categories'
    """
    if categories is None:
        categories = ACTIVITY_TYPES

    counts = Counter(issue.get("activity_type", "Uncategorized")
                     for issue in classified_issues)

    # Posterior: Dirichlet(prior + n_i for each category)
    alphas = [prior + counts.get(cat, 0) for cat in categories]
    total_count = sum(counts.values())

    # Monte Carlo sampling from the posterior
    samples = dirichlet_sample(alphas, n_mc_samples, seed=seed)

    # Compute credible intervals
    tail = (1.0 - confidence) / 2.0
    lo_idx = int(tail * n_mc_samples)
    hi_idx = int((1.0 - tail) * n_mc_samples)

    estimates = []
    for i, cat in enumerate(categories):
        col = sorted(s[i] for s in samples)
        mean = sum(col) / n_mc_samples
        ci_low = col[lo_idx]
        ci_high = col[hi_idx]
        observed = counts.get(cat, 0)

        estimates.append({
            "category": cat,
            "observed_count": observed,
            "posterior_mean": round(mean, 4),
            "ci_low": round(ci_low, 4),
            "ci_high": round(ci_high, 4),
            "ci_width": round(ci_high - ci_low, 4),
            "confidence": confidence,
        })

    # Sort by posterior mean descending
    estimates.sort(key=lambda x: x["posterior_mean"], reverse=True)

    return {
        "estimates": estimates,
        "sample_size": total_count,
        "total_categories": len(categories),
        "prior": prior,
        "confidence": confidence,
    }


def estimate_by_project(classified_issues, categories=None, prior=1.0,
                        confidence=0.95, n_mc_samples=10000, seed=None):
    """Per-project Bayesian estimation."""
    if categories is None:
        categories = ACTIVITY_TYPES

    by_project = {}
    for issue in classified_issues:
        proj = issue.get("project_key", "UNKNOWN")
        by_project.setdefault(proj, []).append(issue)

    results = {}
    for proj in sorted(by_project.keys()):
        results[proj] = estimate_distribution(
            by_project[proj], categories, prior, confidence, n_mc_samples, seed
        )
    return results


def recommend_sample_size(total_issues, n_categories=7, target_width=0.05):
    """Recommend a sample size for a target credible interval width.

    For a multinomial with k categories, the typical proportion for a
    well-represented category is ~1/k. The CI width for a proportion p
    is approximately 2 * z * sqrt(p*(1-p)/n).

    We use the "typical largest category" heuristic: assume the largest
    category is ~40% (common in practice), giving a more realistic
    recommendation than worst-case p=0.5.

    Returns recommended n, capped at total_issues.
    """
    z = 1.96  # ~95% coverage
    p = 0.4   # assume largest category ~40%
    half_width = target_width / 2.0
    n = math.ceil(z**2 * p * (1 - p) / half_width**2)
    # Floor at 200, cap at total
    n = max(200, n)
    return min(n, total_issues)


def main():
    parser = argparse.ArgumentParser(
        description="Bayesian sampling and estimation for activity type distributions"
    )
    parser.add_argument("--input", required=True,
                        help="Input JSON file (all unclassified issues)")
    parser.add_argument("--draw-sample", default=None,
                        help="Output: draw a sample and write it for classification")
    parser.add_argument("--classified-sample", default=None,
                        help="Input: classified sample to estimate from")
    parser.add_argument("--output", default=None,
                        help="Output: estimation results JSON")
    parser.add_argument("--sample-size", type=int, default=0,
                        help="Sample size (0 = auto-recommend)")
    parser.add_argument("--confidence", type=float, default=0.95,
                        help="Credible interval confidence level (default: 0.95)")
    parser.add_argument("--seed", type=int, default=42,
                        help="Random seed for reproducibility")
    parser.add_argument("--target-width", type=float, default=0.10,
                        help="Target CI width for auto sample size (default: 0.10 = ±5%%)")
    args = parser.parse_args()

    # Load all issues
    with open(args.input) as f:
        all_issues = json.load(f)
    total = len(all_issues)
    print(f"Total issues: {total}")

    # Auto-recommend sample size
    if args.sample_size <= 0:
        recommended = recommend_sample_size(total, target_width=args.target_width)
        sample_size = recommended
        print(f"Auto-recommended sample size: {sample_size} "
              f"(target CI width: ±{args.target_width*50:.1f}%)")
    else:
        sample_size = min(args.sample_size, total)
        print(f"Requested sample size: {sample_size}")

    if sample_size >= total:
        print("Sample size >= total issues — classify all instead of sampling.")

    # Mode 1: Draw sample for classification
    if args.draw_sample:
        sample, sample_counts = stratified_sample(all_issues, sample_size,
                                                   seed=args.seed)
        os.makedirs(os.path.dirname(os.path.abspath(args.draw_sample)),
                    exist_ok=True)
        with open(args.draw_sample, "w") as f:
            json.dump(sample, f, indent=2)

        print(f"\nSample drawn: {len(sample)} of {total} issues "
              f"({len(sample)/total*100:.1f}%)")
        print("Stratification by project:")
        for proj in sorted(sample_counts.keys()):
            proj_total = sum(1 for i in all_issues
                            if (i.get("PROJECT_KEY", i.get("project_key"))
                                == proj))
            pct = (sample_counts[proj] / proj_total * 100) if proj_total else 0.0
            print(f"  {proj:<20s} {sample_counts[proj]:>4d} of {proj_total:>5d} "
                  f"({pct:.1f}%)")

        print(f"\nSample written to: {args.draw_sample}")
        print("Next: classify this sample with classify_issues.py, "
              "then re-run with --classified-sample")
        return

    # Mode 2: Estimate from classified sample
    if args.classified_sample:
        with open(args.classified_sample) as f:
            classified = json.load(f)

        print(f"Classified sample: {len(classified)} issues")

        # Overall estimates
        overall = estimate_distribution(
            classified, confidence=args.confidence, seed=args.seed
        )

        # Per-project estimates
        per_project = estimate_by_project(
            classified, confidence=args.confidence, seed=args.seed
        )

        result = {
            "method": "Dirichlet-Multinomial Bayesian estimation",
            "total_population": total,
            "sample_size": len(classified),
            "sample_fraction": round(len(classified) / total, 4),
            "confidence": args.confidence,
            "seed": args.seed,
            "overall": overall,
            "by_project": per_project,
        }

        # Print summary
        print(f"\n{'='*70}")
        print(f"Bayesian Activity Type Estimates "
              f"(sample: {len(classified)} of {total}, "
              f"{len(classified)/total*100:.1f}%)")
        print(f"{'='*70}")
        ci_pct = int(args.confidence * 100)
        print(f"\n{'Category':<45s} {'Mean':>6s}  "
              f"{ci_pct}% Credible Interval")
        print(f"{'-'*45} {'-'*6}  {'-'*25}")
        for est in overall["estimates"]:
            mean_pct = est["posterior_mean"] * 100
            lo_pct = est["ci_low"] * 100
            hi_pct = est["ci_high"] * 100
            print(f"{est['category']:<45s} {mean_pct:>5.1f}%  "
                  f"[{lo_pct:>5.1f}% — {hi_pct:>5.1f}%]")

        if args.output:
            os.makedirs(os.path.dirname(os.path.abspath(args.output)),
                        exist_ok=True)
            with open(args.output, "w") as f:
                json.dump(result, f, indent=2)
            print(f"\nEstimates written to: {args.output}")
        else:
            # Print JSON to stdout
            print(f"\n{json.dumps(result, indent=2)}")
        return

    # No mode specified
    print("\nSpecify either --draw-sample or --classified-sample.")
    print("  Step 1: --draw-sample sample.json  (draw a sample)")
    print("  Step 2: classify sample.json with classify_issues.py")
    print("  Step 3: --classified-sample classified_sample.json --output estimates.json")
    sys.exit(1)


if __name__ == "__main__":
    main()
