#!/usr/bin/env python3
"""Bayesian estimation of activity type distributions from a sample.

Uses Dirichlet-Multinomial conjugate model to estimate category proportions
with credible intervals. Only requires Python stdlib (random, math, json).

Samples human and bot subpopulations independently to ensure both have
adequate precision, then uses post-stratification weighting for the
combined "overall" estimate.

Workflow:
  1. Read all fetched issues (unclassified)
  2. Draw independent stratified samples for human and bot populations
  3. Classify only the sample via classify_issues.py
  4. Compute Bayesian posterior estimates for each population and overall

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


def _get_is_bot(issue):
    """Extract bot flag from an issue, handling both Snowflake and processed formats."""
    val = issue.get("IS_BOT", issue.get("is_bot", False))
    if isinstance(val, str):
        return val.lower() in ("true", "1", "yes")
    return bool(val)


def _allocate_proportional(pool_by_project, budget, rng):
    """Allocate a sample budget across projects proportionally.

    Guarantees at least 1 issue per project (if budget allows),
    then distributes remaining slots proportional to project size.
    Returns {project: count} allocations.
    """
    total = sum(len(v) for v in pool_by_project.values())
    n = min(budget, total)

    if n >= total:
        return {proj: len(issues) for proj, issues in pool_by_project.items()}

    if n <= 0:
        return {proj: 0 for proj in pool_by_project}

    allocations = {}
    remaining = n
    for proj, issues in pool_by_project.items():
        allocations[proj] = min(1, len(issues))
        remaining -= allocations[proj]

    if remaining > 0:
        proportional = {}
        for proj, issues in pool_by_project.items():
            proportional[proj] = len(issues) / total * n
        for proj in pool_by_project:
            proportional[proj] = max(0, proportional[proj] - allocations[proj])
        prop_total = sum(proportional.values())
        if prop_total > 0:
            for proj in pool_by_project:
                extra = int(proportional[proj] / prop_total * remaining)
                extra = min(extra, len(pool_by_project[proj]) - allocations[proj])
                allocations[proj] += extra
                remaining -= extra

        if remaining > 0:
            projects_by_size = sorted(pool_by_project.keys(),
                                      key=lambda p: len(pool_by_project[p]),
                                      reverse=True)
            for proj in projects_by_size:
                if remaining <= 0:
                    break
                can_add = len(pool_by_project[proj]) - allocations[proj]
                add = min(can_add, remaining)
                allocations[proj] += add
                remaining -= add

    return allocations


def stratified_sample(issues, human_n, bot_n, seed=42):
    """Draw independent stratified samples for human and bot populations.

    Each population is sampled separately and stratified by project.
    Guarantees at least 1 issue per project within each population
    (if budget allows).

    Returns:
        (sample_list, {
            "human": {"total": int, "by_project": {proj: count}},
            "bot":   {"total": int, "by_project": {proj: count}},
        })
    """
    rng = random.Random(seed)

    human_by_project = {}
    bot_by_project = {}
    for issue in issues:
        proj = issue.get("PROJECT_KEY", issue.get("project_key", "UNKNOWN"))
        if _get_is_bot(issue):
            bot_by_project.setdefault(proj, []).append(issue)
        else:
            human_by_project.setdefault(proj, []).append(issue)

    human_total = sum(len(v) for v in human_by_project.values())
    bot_total = sum(len(v) for v in bot_by_project.values())

    human_n = min(human_n, human_total)
    bot_n = min(bot_n, bot_total)

    human_alloc = _allocate_proportional(human_by_project, human_n, rng)
    bot_alloc = _allocate_proportional(bot_by_project, bot_n, rng)

    sample = []
    human_counts = {}
    for proj, count in human_alloc.items():
        if count > 0:
            drawn = rng.sample(human_by_project[proj],
                               min(count, len(human_by_project[proj])))
            sample.extend(drawn)
            human_counts[proj] = len(drawn)

    bot_counts = {}
    for proj, count in bot_alloc.items():
        if count > 0:
            drawn = rng.sample(bot_by_project[proj],
                               min(count, len(bot_by_project[proj])))
            sample.extend(drawn)
            bot_counts[proj] = len(drawn)

    rng.shuffle(sample)

    metadata = {
        "human": {
            "total": sum(human_counts.values()),
            "by_project": human_counts,
        },
        "bot": {
            "total": sum(bot_counts.values()),
            "by_project": bot_counts,
        },
    }
    return sample, metadata


def dirichlet_sample(alphas, n_samples=10000, seed=None):
    """Sample from Dirichlet distribution using Gamma variates (stdlib only)."""
    rng = random.Random(seed)
    samples = []
    for _ in range(n_samples):
        raw = [rng.gammavariate(a, 1.0) for a in alphas]
        total = sum(raw)
        if total == 0:
            k = len(alphas)
            samples.append([1.0 / k] * k)
        else:
            samples.append([x / total for x in raw])
    return samples


def estimate_distribution(classified_issues, categories=None, prior=1.0,
                          confidence=0.95, n_mc_samples=10000, seed=None):
    """Bayesian estimation of category proportions with credible intervals."""
    if categories is None:
        categories = ACTIVITY_TYPES

    counts = Counter(issue.get("activity_type", "Uncategorized")
                     for issue in classified_issues)

    alphas = [prior + counts.get(cat, 0) for cat in categories]
    total_count = sum(counts.values())

    samples = dirichlet_sample(alphas, n_mc_samples, seed=seed)

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

    estimates.sort(key=lambda x: x["posterior_mean"], reverse=True)

    return {
        "estimates": estimates,
        "sample_size": total_count,
        "total_categories": len(categories),
        "prior": prior,
        "confidence": confidence,
    }


def weighted_overall_estimate(human_classified, bot_classified,
                              human_pop, bot_pop, categories=None,
                              prior=1.0, confidence=0.95,
                              n_mc_samples=10000, seed=None):
    """Post-stratification weighted estimate combining human and bot posteriors.

    Draws paired MC samples from independent Dirichlet posteriors and
    weights each draw by population proportion. This properly propagates
    uncertainty from both subpopulations into the overall CIs.

    Falls back to estimate_distribution() when one population is empty.
    """
    if categories is None:
        categories = ACTIVITY_TYPES

    if not human_classified:
        return estimate_distribution(bot_classified, categories, prior,
                                     confidence, n_mc_samples, seed)
    if not bot_classified:
        return estimate_distribution(human_classified, categories, prior,
                                     confidence, n_mc_samples, seed)

    total_pop = human_pop + bot_pop
    w_human = human_pop / total_pop
    w_bot = bot_pop / total_pop

    human_counts = Counter(i.get("activity_type", "Uncategorized")
                           for i in human_classified)
    bot_counts = Counter(i.get("activity_type", "Uncategorized")
                         for i in bot_classified)

    human_alphas = [prior + human_counts.get(cat, 0) for cat in categories]
    bot_alphas = [prior + bot_counts.get(cat, 0) for cat in categories]

    rng = random.Random(seed)
    seed_h = rng.randint(0, 2**31)
    seed_b = rng.randint(0, 2**31)
    human_samples = dirichlet_sample(human_alphas, n_mc_samples, seed=seed_h)
    bot_samples = dirichlet_sample(bot_alphas, n_mc_samples, seed=seed_b)

    weighted_samples = []
    for h_draw, b_draw in zip(human_samples, bot_samples):
        weighted = [w_human * h + w_bot * b for h, b in zip(h_draw, b_draw)]
        weighted_samples.append(weighted)

    tail = (1.0 - confidence) / 2.0
    lo_idx = int(tail * n_mc_samples)
    hi_idx = int((1.0 - tail) * n_mc_samples)

    estimates = []
    for i, cat in enumerate(categories):
        col = sorted(s[i] for s in weighted_samples)
        mean = sum(col) / n_mc_samples
        ci_low = col[lo_idx]
        ci_high = col[hi_idx]
        observed = human_counts.get(cat, 0) + bot_counts.get(cat, 0)

        estimates.append({
            "category": cat,
            "observed_count": observed,
            "posterior_mean": round(mean, 4),
            "ci_low": round(ci_low, 4),
            "ci_high": round(ci_high, 4),
            "ci_width": round(ci_high - ci_low, 4),
            "confidence": confidence,
        })

    estimates.sort(key=lambda x: x["posterior_mean"], reverse=True)

    total_sample = len(human_classified) + len(bot_classified)
    return {
        "estimates": estimates,
        "sample_size": total_sample,
        "total_categories": len(categories),
        "prior": prior,
        "confidence": confidence,
        "weighting": {
            "human_weight": round(w_human, 4),
            "bot_weight": round(w_bot, 4),
        },
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

    Uses the "typical largest category" heuristic: assume the largest
    category is ~40%, giving a realistic recommendation.

    Returns recommended n, capped at total_issues.
    """
    z = 1.96  # ~95% coverage
    p = 0.4   # assume largest category ~40%
    half_width = target_width / 2.0
    n = math.ceil(z**2 * p * (1 - p) / half_width**2)
    n = max(200, n)
    return min(n, total_issues)


def recommend_sample_sizes(issues, target_width=0.10):
    """Recommend independent sample sizes for human and bot populations.

    Calls recommend_sample_size() independently for each subpopulation,
    ensuring both get adequate precision for the target CI width.
    """
    human_pop = sum(1 for i in issues if not _get_is_bot(i))
    bot_pop = len(issues) - human_pop

    human_n = recommend_sample_size(human_pop, target_width=target_width) if human_pop > 0 else 0
    bot_n = recommend_sample_size(bot_pop, target_width=target_width) if bot_pop > 0 else 0

    return {
        "human_n": human_n,
        "bot_n": bot_n,
        "human_pop": human_pop,
        "bot_pop": bot_pop,
    }


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
                        help="Total sample budget (0 = auto-recommend per population)")
    parser.add_argument("--confidence", type=float, default=0.95,
                        help="Credible interval confidence level (default: 0.95)")
    parser.add_argument("--seed", type=int, default=42,
                        help="Random seed for reproducibility")
    parser.add_argument("--target-width", type=float, default=0.10,
                        help="Target CI width for auto sample size (default: 0.10 = ±5%%)")
    args = parser.parse_args()

    with open(args.input) as f:
        all_issues = json.load(f)
    total = len(all_issues)
    if total == 0:
        print("No issues to process.", file=sys.stderr)
        sys.exit(1)
    print(f"Total issues: {total}")

    sizes = recommend_sample_sizes(all_issues, target_width=args.target_width)
    human_pop = sizes["human_pop"]
    bot_pop = sizes["bot_pop"]

    if args.sample_size <= 0:
        human_n = sizes["human_n"]
        bot_n = sizes["bot_n"]
        print(f"Auto-recommended sample sizes "
              f"(target CI width: ±{args.target_width*50:.1f}%):")
        print(f"  Human: {human_n} of {human_pop}")
        if bot_pop > 0:
            print(f"  Bot:   {bot_n} of {bot_pop}")
        print(f"  Total: {human_n + bot_n}")
    else:
        budget = min(args.sample_size, total)
        recommended_total = sizes["human_n"] + sizes["bot_n"]
        if bot_pop == 0:
            human_n = budget
            bot_n = 0
        else:
            ratio = sizes["human_n"] / max(recommended_total, 1)
            human_n = min(int(budget * ratio), human_pop)
            bot_n = min(budget - human_n, bot_pop)
            if human_n + bot_n < budget:
                human_n = min(human_n + (budget - human_n - bot_n), human_pop)
        if budget < recommended_total:
            print(f"WARNING: Budget {budget} < recommended {recommended_total}. "
                  f"CIs will be wider than ±{args.target_width*50:.1f}%.",
                  file=sys.stderr)
        print(f"Sample budget: {budget}")
        print(f"  Human: {human_n} of {human_pop}")
        if bot_pop > 0:
            print(f"  Bot:   {bot_n} of {bot_pop}")

    if human_n >= human_pop and bot_n >= bot_pop:
        print("Sample size >= total issues — classify all instead of sampling.")

    # Mode 1: Draw sample for classification
    if args.draw_sample:
        sample, sample_meta = stratified_sample(all_issues, human_n, bot_n,
                                                seed=args.seed)
        os.makedirs(os.path.dirname(os.path.abspath(args.draw_sample)),
                    exist_ok=True)
        with open(args.draw_sample, "w") as f:
            json.dump(sample, f, indent=2)

        h_sampled = sample_meta["human"]["total"]
        b_sampled = sample_meta["bot"]["total"]
        print(f"\nSample drawn: {len(sample)} of {total} issues "
              f"({len(sample)/total*100:.1f}%)")
        print(f"  Human: {h_sampled} of {human_pop} "
              f"({h_sampled/human_pop*100:.1f}%)" if human_pop > 0 else "")
        if bot_pop > 0:
            print(f"  Bot:   {b_sampled} of {bot_pop} "
                  f"({b_sampled/bot_pop*100:.1f}%)")

        # Display project-level breakdown
        all_projects = set(list(sample_meta["human"]["by_project"].keys()) +
                           list(sample_meta["bot"]["by_project"].keys()))

        proj_totals = {}
        for i in all_issues:
            proj = i.get("PROJECT_KEY", i.get("project_key", "UNKNOWN"))
            proj_totals[proj] = proj_totals.get(proj, 0) + 1

        has_bots = b_sampled > 0

        print("\nStratification by project:")
        for proj in sorted(all_projects):
            proj_total = proj_totals.get(proj, 0)
            h_count = sample_meta["human"]["by_project"].get(proj, 0)
            b_count = sample_meta["bot"]["by_project"].get(proj, 0)
            sampled = h_count + b_count
            pct = (sampled / proj_total * 100) if proj_total else 0.0
            bot_info = ""
            if has_bots and b_count > 0:
                bot_info = f"  (human: {h_count}, bot: {b_count})"
            print(f"  {proj:<20s} {sampled:>4d} of {proj_total:>5d} "
                  f"({pct:.1f}%){bot_info}")

        if has_bots:
            print(f"\n  Total: {h_sampled} human + {b_sampled} bot "
                  f"= {len(sample)} sampled")

        print(f"\nSample written to: {args.draw_sample}")
        print("Next: classify this sample with classify_issues.py, "
              "then re-run with --classified-sample")
        return

    # Mode 2: Estimate from classified sample
    if args.classified_sample:
        with open(args.classified_sample) as f:
            classified = json.load(f)

        print(f"Classified sample: {len(classified)} issues")

        human_classified = [i for i in classified if not _get_is_bot(i)]
        bot_classified = [i for i in classified if _get_is_bot(i)]
        human_total = sum(1 for i in all_issues if not _get_is_bot(i))
        bot_total = total - human_total

        overall = weighted_overall_estimate(
            human_classified, bot_classified,
            human_total, bot_total,
            confidence=args.confidence, seed=args.seed
        )

        per_project = estimate_by_project(
            classified, confidence=args.confidence, seed=args.seed
        )

        human_estimates = None
        bot_estimates = None
        if human_classified and bot_classified:
            human_estimates = {
                "population": human_total,
                "sample_size": len(human_classified),
                **estimate_distribution(
                    human_classified, confidence=args.confidence, seed=args.seed
                ),
            }
            bot_estimates = {
                "population": bot_total,
                "sample_size": len(bot_classified),
                **estimate_distribution(
                    bot_classified, confidence=args.confidence, seed=args.seed
                ),
            }
        elif human_classified:
            human_estimates = {
                "population": human_total,
                "sample_size": len(human_classified),
                **estimate_distribution(
                    human_classified, confidence=args.confidence, seed=args.seed
                ),
            }
        elif bot_classified:
            bot_estimates = {
                "population": bot_total,
                "sample_size": len(bot_classified),
                **estimate_distribution(
                    bot_classified, confidence=args.confidence, seed=args.seed
                ),
            }

        result = {
            "method": "Dirichlet-Multinomial Bayesian estimation (dual-population)",
            "total_population": total,
            "sample_size": len(classified),
            "sample_fraction": round(len(classified) / total, 4),
            "confidence": args.confidence,
            "seed": args.seed,
            "sampling": {
                "approach": "independent_per_population",
                "human_population": human_total,
                "bot_population": bot_total,
                "human_sample_size": len(human_classified),
                "bot_sample_size": len(bot_classified),
                "target_width": args.target_width,
            },
            "overall": overall,
            "human": human_estimates,
            "bot": bot_estimates,
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

        if human_estimates and bot_estimates:
            print(f"\nBot/Human Split: {human_total} human + {bot_total} bot "
                  f"= {total} total")
            print(f"  Sample: {len(human_classified)} human + "
                  f"{len(bot_classified)} bot = {len(classified)}")

            print(f"\nHuman Work ({len(human_classified)} of {human_total}):")
            for est in human_estimates["estimates"]:
                mean_pct = est["posterior_mean"] * 100
                print(f"  {est['category']:<45s} {mean_pct:>5.1f}%")

            print(f"\nAutomated/Bot Work ({len(bot_classified)} of {bot_total}):")
            for est in bot_estimates["estimates"]:
                mean_pct = est["posterior_mean"] * 100
                print(f"  {est['category']:<45s} {mean_pct:>5.1f}%")

        if args.output:
            os.makedirs(os.path.dirname(os.path.abspath(args.output)),
                        exist_ok=True)
            with open(args.output, "w") as f:
                json.dump(result, f, indent=2)
            print(f"\nEstimates written to: {args.output}")
        else:
            print(f"\n{json.dumps(result, indent=2)}")
        return

    print("\nSpecify either --draw-sample or --classified-sample.")
    print("  Step 1: --draw-sample sample.json  (draw a sample)")
    print("  Step 2: classify sample.json with classify_issues.py")
    print("  Step 3: --classified-sample classified_sample.json --output estimates.json")
    sys.exit(1)


if __name__ == "__main__":
    main()
