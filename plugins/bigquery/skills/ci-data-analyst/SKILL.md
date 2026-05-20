---
name: ci-data-analyst
description: Safely query and report on OpenShift CI prow job and test data in BigQuery with cost controls, dry-run validation, and local caching of results
---

# CI Data Analyst

An agent for querying and analyzing OpenShift CI data stored in BigQuery. Covers prow job runs, junit test results, job variants, and related tables. Prioritizes cost safety: every query is dry-run first, costs are estimated, and the user confirms before execution.

## When to Use This Skill

- Investigating test failures, flakes, or regressions across CI jobs
- Querying prow job pass/fail rates over time
- Analyzing test results by variant (platform, architecture, network, upgrade, etc.)
- Exploring CI data patterns (e.g. which jobs run a test, how often a test fails)
- Any ad-hoc BigQuery analysis against OpenShift CI datasets

## Prerequisites

- `bq` CLI installed and authenticated (`gcloud auth login`)
- BigQuery read access to the `openshift-gce-devel` project

## Core Principles

### 1. Cost Safety Is Non-Negotiable

The junit table alone is massive. Every query MUST go through this flow:

1. **Show the query** to the user before doing anything
2. **Dry-run** to get bytes scanned: `bq query --project_id=openshift-gce-devel --dry_run --use_legacy_sql=false '<query>'`
3. **Calculate cost**: bytes / 10^12 * $6.25 (on-demand pricing)
4. **If cost > $1.00**: show the estimated cost and bytes scanned, ask user to confirm before executing
5. **If cost <= $1.00**: proceed, but still report the cost in results
6. **Never loop or repeat queries.** Run once, cache locally, analyze from the cached data.

### 2. Always Use Partition Filters

Both key tables are partitioned by day:
- `junit`: partitioned on `modified_time`
- `jobs`: partitioned on `prowjob_start`

**Every query MUST include a filter on the partition column** to avoid full-table scans. Use tight date ranges:

```sql
WHERE modified_time >= DATETIME("2026-05-01")
  AND modified_time < DATETIME("2026-05-08")
```

### 3. Cache Results Locally

After executing a query, save the results to `.work/ci-data-analyst/` as JSON or CSV. Reference cached files for follow-up analysis instead of re-querying. Name files descriptively (e.g. `test-failures-apiserver-readyz-2026-05-01-to-2026-05-07.json`).

## Project and Dataset Reference

**Project**: `openshift-gce-devel` (always use this, pass `--project_id=openshift-gce-devel` to all bq commands)

### Engineering Dataset: `ci_analysis_us`

The primary dataset for engineering prow jobs. Key tables:

#### `ci_analysis_us.junit`
Junit test results. Massive table. Partitioned by DAY on `modified_time`.

| Column | Type | Notes |
|--------|------|-------|
| prowjob_build_id | STRING | Join key to jobs table |
| file_path | STRING | Artifact path of the junit XML |
| test_name | STRING | Full test name |
| testsuite | STRING | Test suite name |
| success_val | INTEGER | 1 = pass, 0 = fail |
| success | BOOLEAN | Pass/fail |
| skipped | BOOLEAN | Whether test was skipped |
| flake_count | INTEGER | >0 means this row is part of a flake |
| modified_time | DATETIME | **Partition column** - always filter on this |
| branch | STRING | Release branch (e.g. "release-4.18") |
| prowjob_name | STRING | Name of the prow job run |
| duration_ms | INTEGER | Test execution time |
| test_id | STRING | Stable test identifier |
| failure_message | STRING | Failure message from junit XML |
| failure_content | STRING | Failure body from junit XML |
| start_time | DATETIME | Test start time |
| end_time | DATETIME | Test end time |
| platform | STRING | **LEGACY - do not use for filtering** |
| arch | STRING | **LEGACY - do not use for filtering** |
| network | STRING | **LEGACY - do not use for filtering** |
| upgrade | STRING | **LEGACY - do not use for filtering** |

**IMPORTANT**: The `platform`, `arch`, `network`, `upgrade` columns on the junit table are legacy and unmaintained. Do NOT use them for filtering or grouping. Instead, join to `jobs` and then to `job_variants` for accurate variant data. See "Variant Joins" below.

#### `ci_analysis_us.jobs`
Prow job **runs** (invocations). Each row is a single execution of a job. Partitioned by DAY on `prowjob_start`.

**Important terminology**: When users say "job" they typically mean a distinct `prowjob_job_name` (e.g. `periodic-ci-openshift-release-master-nightly-4.19-e2e-aws-ovn`). The `jobs` table contains individual **runs** of those jobs, each with a unique `prowjob_build_id`. A single "job" has many runs over time. Use `prowjob_job_name` to group/identify jobs, and `prowjob_build_id` to identify specific runs.

| Column | Type | Notes |
|--------|------|-------|
| prowjob_build_id | STRING | Primary key, join key to junit |
| prowjob_job_name | STRING | Canonical job name (join key to job_variants) |
| prowjob_url | STRING | Link to prow job |
| prowjob_state | STRING | "success", "failure", "error", "aborted" |
| prowjob_start | DATETIME | **Partition column** |
| prowjob_completion | DATETIME | When job finished |
| prowjob_type | STRING | "periodic", "presubmit", "postsubmit" |
| org | STRING | GitHub org |
| repo | STRING | GitHub repo |
| pr_number | STRING | PR number (presubmits) |
| base_ref | STRING | Base branch |
| is_release_verify | BOOLEAN | Whether this is a release verification job |

#### `ci_analysis_us.job_variants`
Maps job names to their variant classifications. Not partitioned (small table).

| Column | Type | Notes |
|--------|------|-------|
| job_name | STRING | Join to `jobs.prowjob_job_name` |
| variant_name | STRING | e.g. "Platform", "Architecture", "Network", "Upgrade" |
| variant_value | STRING | e.g. "aws", "amd64", "ovn", "upgrade-micro" |

### Variant Reference

The `job_variants` table maps each job name to multiple variant dimensions. These are the primary way to categorize and filter jobs. The most important variants for analysis:

#### Release & Upgrade Variants

| Variant | Description | Key Values |
|---------|-------------|------------|
| **Release** | The OCP version being tested | `4.18`, `4.19`, `4.20`, `4.21`, `4.22`, `4.23`, `5.0`, `5.1` |
| **Upgrade** | Type of upgrade being tested | `none` (no upgrade), `micro` (z-stream), `minor` (y-stream), `major` (x-stream), `multi` (multi-hop), `micro-downgrade` |
| **FromRelease** | Source version for upgrade jobs | `4.17`, `4.18`, etc. |

- **Release** is the target version. For upgrade jobs, this is what the cluster upgrades *to*.
- **Upgrade=none** means a fresh install job, not an upgrade.
- Use Release to scope queries to a specific OCP version (e.g. "4.19 regressions").

#### Platform & Infrastructure Variants

| Variant | Description | Key Values |
|---------|-------------|------------|
| **Platform** | Cloud/infra provider | `aws`, `azure`, `gcp`, `vsphere`, `metal`, `openstack`, `nutanix`, `alibaba`, `kubevirt`, `libvirt`, `none`, `ovirt`, `rosa`, `aro`, `external-aws`, `external-oci`, `external-vsphere`, `osd-gcp` |
| **Architecture** | CPU architecture | `amd64`, `arm64`, `multi`, `ppc64le`, `s390x` |
| **Topology** | Cluster topology | `ha` (standard 3+3), `single` (SNO), `compact` (3-node), `external`, `microshift`, `two-node-arbiter`, `two-node-fencing` |
| **Installer** | Installation method | `ipi`, `upi`, `agent`, `assisted`, `hypershift`, `aro` |

#### Network Variants

| Variant | Description | Key Values |
|---------|-------------|------------|
| **Network** | CNI plugin | `ovn`, `sdn` (legacy), `cilium` |
| **NetworkStack** | IP stack | `ipv4`, `ipv6`, `dual` |
| **NetworkAccess** | Connectivity constraints | `default`, `disconnected`, `proxy`, `nat-instance` |

#### Job Classification Variants

| Variant | Description | Key Values |
|---------|-------------|------------|
| **JobTier** | How important the job is to release gating | `blocking` (blocks payloads), `informing` (signals, doesn't block), `candidate`, `standard`, `rare`, `excluded`, `hidden` |
| **Owner** | Team/org that owns the job | `eng`, `qe`, `aro`, `cnf`, `perfscale`, etc. |
| **Suite** | Test suite | `parallel`, `serial`, `etcd-scaling`, `unknown` |

#### Configuration Variants

| Variant | Description | Key Values |
|---------|-------------|------------|
| **Procedure** | Special test procedures | `none`, `serial`, `cert-rotation-shutdown`, `cpu-partitioning`, `etcd-scaling`, `ipsec`, `on-cluster-layering`, etc. |
| **SecurityMode** | FIPS mode | `default`, `fips` |
| **FeatureSet** | Feature gate mode | `default`, `techpreview` |
| **CGroupMode** | CGroup version | `v1`, `v2` |
| **ContainerRuntime** | Container runtime | `runc`, `crun` |
| **OS** | Node OS | `rhcos9`, `rhcos10`, `rhcos9-10` |
| **Aggregation** | Whether results are aggregated | `none`, `aggregated` |

#### Common Filtering Patterns

When filtering by variant, remember each dimension is a separate LEFT JOIN:

```sql
-- Find all 4.19 upgrade-from-4.18 failures on AWS
LEFT JOIN `openshift-gce-devel.ci_analysis_us.job_variants` jv_release
  ON jobs.prowjob_job_name = jv_release.job_name AND jv_release.variant_name = 'Release'
LEFT JOIN `openshift-gce-devel.ci_analysis_us.job_variants` jv_upgrade
  ON jobs.prowjob_job_name = jv_upgrade.job_name AND jv_upgrade.variant_name = 'Upgrade'
LEFT JOIN `openshift-gce-devel.ci_analysis_us.job_variants` jv_from
  ON jobs.prowjob_job_name = jv_from.job_name AND jv_from.variant_name = 'FromRelease'
LEFT JOIN `openshift-gce-devel.ci_analysis_us.job_variants` jv_platform
  ON jobs.prowjob_job_name = jv_platform.job_name AND jv_platform.variant_name = 'Platform'
WHERE jv_release.variant_value = '4.19'
  AND jv_upgrade.variant_value = 'minor'
  AND jv_from.variant_value = '4.18'
  AND jv_platform.variant_value = 'aws'
```

**Tip**: To exclude aggregated results (which are synthetic rollups, not real job runs), filter `Aggregation != 'aggregated'` or `prowjob_name NOT LIKE '%aggregated%'`.

#### `ci_analysis_us.job_labels`
Labels/annotations applied to job runs. Partitioned by DAY on `prowjob_start`.

| Column | Type | Notes |
|--------|------|-------|
| prowjob_build_id | STRING | Join key to jobs/junit |
| prowjob_start | DATETIME | **Partition column** |
| label | STRING | e.g. "InfraFailure" |
| symptom_id | STRING | Triage symptom ID |

### QE Dataset: `ci_analysis_qe`

Smaller dataset for QE prow jobs. Has the same table structure as `ci_analysis_us` (jobs, junit, job_variants, job_labels). QE jobs are slowly being migrated to the engineering system.

**Always default to `ci_analysis_us`** unless the user explicitly asks about QE data. Never assume QE dataset.

## Query Patterns

### Deduplicating Junit Results (CRITICAL)

The junit table directly models junit XML. A "flake" (test fails then passes on retry) appears as **two separate rows**: one with `success_val=0` and one with `success_val=1`. Raw queries will double-count test runs unless deduplicated.

**Always use this deduplication pattern** (from sippy):

```sql
WITH deduped AS (
  SELECT
    *,
    ROW_NUMBER() OVER(
      PARTITION BY file_path, test_name, testsuite
      ORDER BY
        CASE
          WHEN flake_count > 0 THEN 0
          WHEN success_val > 0 THEN 1
          ELSE 2
        END
    ) AS row_num,
    CASE WHEN flake_count > 0 THEN 0 ELSE success_val END AS adjusted_success_val,
    CASE WHEN flake_count > 0 THEN 1 ELSE 0 END AS adjusted_flake_count
  FROM `openshift-gce-devel.ci_analysis_us.junit`
  WHERE modified_time >= DATETIME("2026-05-01")
    AND modified_time < DATETIME("2026-05-08")
    AND skipped = false
    AND test_name LIKE '%your test pattern%'
)
SELECT * FROM deduped WHERE row_num = 1
```

**Priority order**: flakes (0) > passes (1) > failures (2). This means:
- If a test flaked, it's counted as a flake (not a failure)
- `adjusted_success_val`: 0 for flakes (they didn't cleanly pass), original value otherwise
- `adjusted_flake_count`: 1 for flakes, 0 otherwise

**When to skip deduplication**: Only when you specifically want to see raw pass/fail pairs (e.g. debugging a specific flake's failure message). In all aggregation/counting queries, always deduplicate.

### Variant Joins

To get accurate variant data for test results, join through the jobs table to job_variants:

```sql
SELECT
  junit.test_name,
  junit.modified_time,
  jv_platform.variant_value AS platform,
  jv_arch.variant_value AS architecture,
  jv_network.variant_value AS network,
  jv_upgrade.variant_value AS upgrade
FROM `openshift-gce-devel.ci_analysis_us.junit` junit
INNER JOIN `openshift-gce-devel.ci_analysis_us.jobs` jobs
  ON junit.prowjob_build_id = jobs.prowjob_build_id
  AND jobs.prowjob_start >= DATETIME("2026-05-01")
  AND jobs.prowjob_start < DATETIME("2026-05-08")
LEFT JOIN `openshift-gce-devel.ci_analysis_us.job_variants` jv_platform
  ON jobs.prowjob_job_name = jv_platform.job_name AND jv_platform.variant_name = 'Platform'
LEFT JOIN `openshift-gce-devel.ci_analysis_us.job_variants` jv_arch
  ON jobs.prowjob_job_name = jv_arch.job_name AND jv_arch.variant_name = 'Architecture'
LEFT JOIN `openshift-gce-devel.ci_analysis_us.job_variants` jv_network
  ON jobs.prowjob_job_name = jv_network.job_name AND jv_network.variant_name = 'Network'
LEFT JOIN `openshift-gce-devel.ci_analysis_us.job_variants` jv_upgrade
  ON jobs.prowjob_job_name = jv_upgrade.job_name AND jv_upgrade.variant_name = 'Upgrade'
WHERE junit.modified_time >= DATETIME("2026-05-01")
  AND junit.modified_time < DATETIME("2026-05-08")
```

Each variant dimension gets its own LEFT JOIN with a unique alias. Common variant names: `Platform`, `Architecture`, `Network`, `Upgrade`, `Release`, `Topology`, `Installer`, `Suite`.

To discover all available variant names and values:
```sql
SELECT variant_name, ARRAY_AGG(DISTINCT variant_value ORDER BY variant_value) AS variant_values
FROM `openshift-gce-devel.ci_analysis_us.job_variants`
WHERE variant_value != ""
GROUP BY variant_name
```

### Filtering Out Infrastructure Failures

To exclude jobs that failed due to infrastructure issues (not real test failures), filter using job_labels:

```sql
LEFT JOIN `openshift-gce-devel.ci_analysis_us.job_labels` jl
  ON junit.prowjob_build_id = jl.prowjob_build_id
  AND jl.prowjob_start >= DATETIME("2026-05-01")
  AND jl.prowjob_start < DATETIME("2026-05-08")
  AND jl.label = 'InfraFailure'
WHERE jl.label IS NULL  -- exclude infra failures
```

### Job Pass Rate Analysis

```sql
SELECT
  jobs.prowjob_job_name,
  COUNT(DISTINCT jobs.prowjob_build_id) AS total_runs,
  COUNT(DISTINCT IF(jobs.prowjob_state = 'success', jobs.prowjob_build_id, NULL)) AS successful_runs
FROM `openshift-gce-devel.ci_analysis_us.jobs` jobs
WHERE jobs.prowjob_start >= DATETIME("2026-05-01")
  AND jobs.prowjob_start < DATETIME("2026-05-08")
  AND jobs.prowjob_type = 'periodic'
GROUP BY jobs.prowjob_job_name
ORDER BY total_runs DESC
```

## Execution Workflow

For every user request:

### Step 1: Understand the Question
Parse what the user wants to know. Identify:
- Which table(s) are needed
- What date range to use (ask if not specified, suggest a narrow range)
- Whether deduplication is needed (yes for any junit aggregation)
- Which variants matter

### Step 2: Build the Query
Construct the SQL following the patterns above. Always include:
- Partition column filter with a tight date range
- Deduplication CTE if querying junit for aggregation
- Variant joins if variant-level breakdown is needed
- `--use_legacy_sql=false` flag

### Step 3: Show the Query
Present the query to the user so they can review it.

### Step 4: Dry Run
```bash
bq query --project_id=openshift-gce-devel --dry_run --use_legacy_sql=false '<query>'
```

Parse the output to extract bytes to be processed.

### Step 5: Confirm Cost
Calculate: `bytes / 1,000,000,000,000 * 6.25 = cost in USD`

- **<= $1.00**: Report cost and proceed
- **> $1.00**: Show cost and bytes scanned, ask user for confirmation before running
- **> $10.00**: Strongly recommend narrowing date range or filters before proceeding

### Step 6: Execute and Cache
```bash
bq query --project_id=openshift-gce-devel --use_legacy_sql=false --format=json --max_rows=10000 '<query>' > .work/ci-data-analyst/<descriptive-name>.json
```

Report total rows returned and the file where results are cached.

### Step 7: Analyze and Report
Parse the cached results and present findings. Include:
- Summary statistics
- Notable patterns
- Links to specific prow jobs when relevant (prowjob_url)
- Suggestions for follow-up queries if warranted

## Query Optimization Tips

- **Narrow date ranges first**: Start with 7 days. Widen only if needed.
- **Use test_id over test_name LIKE**: If the user provides a test_id, use exact match. LIKE with wildcards on test_name forces a full column scan.
- **Select only needed columns**: Don't SELECT * on the junit table.
- **Filter early**: Put the most selective filters in the WHERE clause.
- **Avoid repeated queries**: Cache results and analyze locally.
- **Consider the jobs table first**: If you only need job-level data (no test results), query jobs directly -- it's much smaller than junit.

## Error Handling

- **"BigQuery not enabled"**: Pass `--project_id=openshift-gce-devel` explicitly
- **Authentication errors**: Ask user to run `! gcloud auth login`
- **Timeout on large queries**: Suggest narrowing the date range
- **No results**: Verify the test name / job name exists, check the date range, verify the branch

## Example Interactions

**User**: "How often is the kube-apiserver readyz test failing this week?"

1. Build deduped query filtering junit on test_name LIKE '%readyz%' for the past 7 days
2. Show query, dry run (~1TB for a week on junit)
3. Show cost estimate, get confirmation
4. Execute, cache to `.work/ci-data-analyst/readyz-failures-2026-05-01-to-2026-05-07.json`
5. Report: X total runs, Y failures, Z flakes, pass rate = N%
6. Break down by job name or variant if helpful

**User**: "Which periodic jobs on AWS have the worst pass rate this month?"

1. Query jobs table joined to job_variants for Platform=aws, prowjob_type=periodic
2. No junit needed, just job pass/fail -- much cheaper
3. Dry run, report cost, execute
4. Report top failing jobs with pass rates
