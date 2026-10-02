---
name: jobs-and-tests
description: Use when querying OpenShift CI prow job runs and junit test results in BigQuery (ci_analysis_us dataset) with deduplication, variant joins, and infrastructure failure filtering
---

# Jobs and Tests

Query and analyze prow job runs and junit test results stored in `openshift-gce-devel.ci_analysis_us`. This is the primary dataset for investigating test failures, flakes, regressions, and job pass rates.

Follow the `foundations` skill for cost safety, caching, and execution workflow.

## When to Use This Skill

- Investigating test failures, flakes, or regressions across CI jobs
- Querying prow job pass/fail rates over time
- Analyzing test results by variant (platform, architecture, network, upgrade, etc.)
- Exploring CI data patterns (e.g. which jobs run a test, how often a test fails)

## Tables

### `ci_analysis_us.junit`
Junit test results. Massive table. Partitioned by DAY on `modified_time`. **Clustered on `release`**.

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
| modified_time | DATETIME | **Partition column** — always filter on this |
| release | STRING | OCP release (e.g. "4.22", "5.0"). **Clustering column** — always filter for ~60-70% cost reduction |
| branch | STRING | **LEGACY — do not use.** Use `release` instead |
| prowjob_name | STRING | Name of the prow job run |
| duration_ms | INTEGER | Test execution time |
| test_id | STRING | Stable test identifier |
| failure_message | STRING | Failure message from junit XML |
| failure_content | STRING | Failure body from junit XML |
| start_time | DATETIME | Test start time |
| end_time | DATETIME | Test end time |
| platform | STRING | **LEGACY — do not use for filtering** |
| arch | STRING | **LEGACY — do not use for filtering** |
| network | STRING | **LEGACY — do not use for filtering** |
| upgrade | STRING | **LEGACY — do not use for filtering** |

**IMPORTANT**: The `platform`, `arch`, `network`, `upgrade` columns on junit are legacy and unmaintained. Join to `jobs` then `job_variants` for accurate variant data.

### `ci_analysis_us.jobs`
Prow job **runs** (invocations). Each row is a single execution. Partitioned by DAY on `prowjob_start`.

**Terminology**: "job" = a distinct `prowjob_job_name`. The table contains individual **runs**, each with a unique `prowjob_build_id`. Use `prowjob_job_name` to group/identify jobs, `prowjob_build_id` for specific runs.

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

### `ci_analysis_us.job_variants`
Maps job names to variant classifications. Not partitioned (small table).

| Column | Type | Notes |
|--------|------|-------|
| job_name | STRING | Join to `jobs.prowjob_job_name` |
| variant_name | STRING | e.g. "Platform", "Architecture" |
| variant_value | STRING | e.g. "aws", "amd64" |

### `ci_analysis_us.job_labels`
Labels/annotations on job runs. Partitioned by DAY on `prowjob_start`.

| Column | Type | Notes |
|--------|------|-------|
| prowjob_build_id | STRING | Join key to jobs/junit |
| prowjob_start | DATETIME | **Partition column** |
| label | STRING | e.g. "InfraFailure" |
| symptom_id | STRING | Triage symptom ID |

## Variant Reference

Each job maps to multiple variant dimensions via `job_variants`. Each dimension is a separate LEFT JOIN.

### Release & Upgrade

| Variant | Key Values |
|---------|------------|
| **Release** | `4.18`, `4.19`, `4.20`, `4.21`, `4.22`, `4.23`, `5.0`, `5.1` |
| **Upgrade** | `none`, `micro`, `minor`, `major`, `multi`, `micro-downgrade` |
| **FromRelease** | `4.17`, `4.18`, etc. |

### Platform & Infrastructure

| Variant | Key Values |
|---------|------------|
| **Platform** | `aws`, `azure`, `gcp`, `vsphere`, `metal`, `openstack`, `nutanix`, `alibaba`, `kubevirt`, `libvirt`, `none`, `ovirt`, `rosa`, `aro`, `external-aws`, `external-oci`, `external-vsphere`, `osd-gcp` |
| **Architecture** | `amd64`, `arm64`, `multi`, `ppc64le`, `s390x` |
| **Topology** | `ha`, `single`, `compact`, `external`, `microshift`, `two-node-arbiter`, `two-node-fencing` |
| **Installer** | `ipi`, `upi`, `agent`, `assisted`, `hypershift`, `aro` |

### Network

| Variant | Key Values |
|---------|------------|
| **Network** | `ovn`, `sdn`, `cilium` |
| **NetworkStack** | `ipv4`, `ipv6`, `dual` |
| **NetworkAccess** | `default`, `disconnected`, `proxy`, `nat-instance` |

### Job Classification

| Variant | Key Values |
|---------|------------|
| **JobTier** | `blocking`, `informing`, `candidate`, `standard`, `rare`, `excluded`, `hidden` |
| **Owner** | `eng`, `qe`, `aro`, `cnf`, `perfscale`, etc. |
| **Suite** | `parallel`, `serial`, `etcd-scaling`, `unknown` |

### Configuration

| Variant | Key Values |
|---------|------------|
| **Procedure** | `none`, `serial`, `cert-rotation-shutdown`, `cpu-partitioning`, `etcd-scaling`, `ipsec`, `on-cluster-layering`, etc. |
| **SecurityMode** | `default`, `fips` |
| **FeatureSet** | `default`, `techpreview` |
| **CGroupMode** | `v1`, `v2` |
| **ContainerRuntime** | `runc`, `crun` |
| **OS** | `rhcos9`, `rhcos10`, `rhcos9-10` |
| **Aggregation** | `none`, `aggregated` |

## Query Patterns

### Deduplicating Junit Results (CRITICAL)

A "flake" appears as **two rows**: one fail, one pass. Raw queries double-count unless deduplicated. **Always use this pattern** for aggregation:

```sql
WITH deduped AS (
  SELECT
    *,
    ROW_NUMBER() OVER(
      PARTITION BY prowjob_build_id, file_path, test_name, testsuite
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
  WHERE modified_time >= DATETIME_SUB(CURRENT_DATETIME(), INTERVAL 7 DAY)
    AND release = '4.22'
    AND skipped = false
    AND test_name LIKE '%your test pattern%'
)
SELECT * FROM deduped WHERE row_num = 1
```

Priority: flakes (0) > passes (1) > failures (2). Skip deduplication only when debugging a specific flake's failure message.

### Variant Joins

Each dimension is a separate LEFT JOIN with a unique alias:

```sql
LEFT JOIN `openshift-gce-devel.ci_analysis_us.job_variants` jv_release
  ON jobs.prowjob_job_name = jv_release.job_name AND jv_release.variant_name = 'Release'
LEFT JOIN `openshift-gce-devel.ci_analysis_us.job_variants` jv_platform
  ON jobs.prowjob_job_name = jv_platform.job_name AND jv_platform.variant_name = 'Platform'
WHERE jv_release.variant_value = '4.19'
  AND jv_platform.variant_value = 'aws'
```

**Tip**: Exclude aggregated results with `Aggregation != 'aggregated'` or `prowjob_name NOT LIKE '%aggregated%'`.

### Filtering Out Infrastructure Failures

```sql
LEFT JOIN `openshift-gce-devel.ci_analysis_us.job_labels` jl
  ON junit.prowjob_build_id = jl.prowjob_build_id
  AND jl.prowjob_start >= DATETIME_SUB(CURRENT_DATETIME(), INTERVAL 7 DAY)
  AND jl.label = 'InfraFailure'
WHERE jl.label IS NULL
```

### Job Pass Rate Analysis

```sql
SELECT
  jobs.prowjob_job_name,
  COUNT(DISTINCT jobs.prowjob_build_id) AS total_runs,
  COUNT(DISTINCT IF(jobs.prowjob_state = 'success', jobs.prowjob_build_id, NULL)) AS successful_runs
FROM `openshift-gce-devel.ci_analysis_us.jobs` jobs
WHERE jobs.prowjob_start >= DATETIME_SUB(CURRENT_DATETIME(), INTERVAL 7 DAY)
  AND jobs.prowjob_type = 'periodic'
GROUP BY jobs.prowjob_job_name
ORDER BY total_runs DESC
```

## QE Dataset: `ci_analysis_qe`

Same table structure as `ci_analysis_us`. Smaller. QE jobs are slowly migrating to the engineering system. **Default to `ci_analysis_us`** unless the user explicitly asks about QE data.
