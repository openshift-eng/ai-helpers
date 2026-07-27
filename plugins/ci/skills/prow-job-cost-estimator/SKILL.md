---
name: prow-job-cost-estimator
description: Estimate cloud compute cost for OpenShift CI prow jobs based on duration and platform
---

# Prow Job Cost Estimator

Estimates the cloud compute cost of running OpenShift CI prow jobs. Takes a list of jobs with their durations and run/skip decisions, and returns per-job cost breakdowns plus aggregate totals for recommended cost, savings from skipped required jobs, and added cost from optional jobs triggered.

## When to Use This Skill

Use this skill when you need to:

- Estimate how much a set of CI jobs will cost to run
- Calculate savings from skipping unnecessary e2e jobs
- Compare the cost of different testing strategies
- Report cost impact of job recommendations

## Prerequisites

1. **Python 3**: Python 3.6 or later (uses only standard library)
2. **Job data**: A JSON array of job objects with name, duration, decision, and CI status

## Implementation Steps

### Step 1: Prepare the Jobs Input

Create a JSON array of job objects. Each object must have:

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Job name (platform is inferred from this) |
| `duration_minutes` | number | Average runtime in minutes (from Sippy `current_average_duration_minutes` or estimated) |
| `decision` | string | `"run"` or `"skip"` |
| `ci_status` | string | `"required"` or `"optional"` (from CI config `optional` field) |

Example input:

```json
[
  {"name": "e2e-aws-ovn-fips", "duration_minutes": 182, "decision": "skip", "ci_status": "required"},
  {"name": "e2e-gcp-ovn", "duration_minutes": 180, "decision": "run", "ci_status": "required"},
  {"name": "e2e-vsphere-ovn", "duration_minutes": 165, "decision": "skip", "ci_status": "required"}
]
```

### Step 2: Run the Estimator

```bash
script_path="plugins/ci/skills/prow-job-cost-estimator/estimate_cost.py"

# From a file
python3 "$script_path" --input /tmp/pr-risk-jobs.json --format summary

# From stdin
echo '<json>' | python3 "$script_path" --format json

# JSON output for programmatic use
python3 "$script_path" --input /tmp/pr-risk-jobs.json --format json
```

### Step 3: Use the Output

**Summary format** prints human-readable per-job costs and totals:

```
Per-job breakdown:
  e2e-aws-ovn-fips: 182 min x $1/hr (aws) = $3.03 [skip]
  e2e-gcp-ovn: 180 min x $2/hr (gcp) = $6.00 [run]
  e2e-vsphere-ovn: 165 min x $4/hr (vsphere) = $11.00 [skip]

Recommended cost: $6.00
Savings (skipped required): $14.03
Added (optional triggered): $0.00
Net savings: $14.03
```

**JSON format** returns a structured object:

```json
{
  "recommended_cost_usd": 6.00,
  "savings_from_skipped_required_usd": 14.03,
  "added_cost_from_optional_usd": 0.00,
  "net_savings_usd": 14.03,
  "jobs": [
    {
      "name": "e2e-aws-ovn-fips",
      "duration_minutes": 182,
      "decision": "skip",
      "ci_status": "required",
      "platform": "aws",
      "rate_per_hr": 1,
      "cost_usd": 3.03
    }
  ]
}
```

## Platform Rates

The estimator uses fixed per-job hourly rates. These are simplified cost units representing relative cloud expense, not actual VM pricing:

| Platform   | Rate      | Inferred when job name contains |
|------------|-----------|----------------------------------|
| MicroShift | $0.15/hr  | `microshift`                     |
| AWS        | $1/hr     | `aws`                            |
| GCP        | $2/hr     | `gcp`                            |
| Azure      | $2/hr     | `azure`                          |
| Metal      | $3/hr     | `metal`                          |
| vSphere    | $4/hr     | `vsphere`                        |

MicroShift is matched first — a job named `e2e-aws-ovn-microshift` matches `microshift`, not `aws`.

If no platform keyword is found in the job name, AWS ($1/hr) is assumed.

**About MicroShift:** MicroShift is a single-node, minimal OpenShift distribution. The only OpenShift kube APIs available are Route and SecurityContextConstraints — all other OpenShift-specific APIs (OLM, Machine API, Console, Monitoring, ImageRegistry, Samples operator, etc.) are unavailable. This makes MicroShift unsuitable for testing most PRs, but for changes that only touch Route or SCC code paths, it is by far the most cost-effective testing option.

## Cost Definitions

- **Recommended cost** — total cost of all jobs marked `"run"`
- **Savings from skipped required** — cost of jobs with `ci_status: "required"` that were marked `"skip"` (these would have run by default without intervention)
- **Added cost from optional** — cost of jobs with `ci_status: "optional"` that were marked `"run"` (these would not have run without intervention)
- **Net savings** — savings minus added cost (positive = saved money, negative = spent more than default)

## Error Handling

- Missing `name` or `duration_minutes` fields will raise a KeyError
- Invalid JSON input will raise a JSONDecodeError
- Exit code 0 on success, 1 on error

## See Also

- Related Skill: `fetch-jobs` (fetches job durations from Sippy)
- Related Skill: `assess-pr-risk` (uses cost estimates in PR risk reports)
