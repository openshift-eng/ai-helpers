-- Per-deployment at-rest (pre-suite) memory usage for control-plane singletons.
-- Params: @release (STRING, e.g. "5.1"), @window_days (INT64).
-- Raw observations only — the ×1.10 recommendation, drift, threshold and
-- candidate selection are applied by scripts/select-candidates.py.
WITH release_runs AS (
  SELECT DISTINCT
    j.prowjob_build_id AS JobRunName,
    COALESCE(jv_upgrade.variant_value IN ('micro','minor','major','multi'), FALSE) AS is_upgrade
  FROM `openshift-gce-devel.ci_analysis_us.jobs` j
  JOIN `openshift-gce-devel.ci_analysis_us.job_variants` jv_release
    ON j.prowjob_job_name = jv_release.job_name
   AND jv_release.variant_name = 'Release'
   AND jv_release.variant_value = @release
  LEFT JOIN `openshift-gce-devel.ci_analysis_us.job_variants` jv_upgrade
    ON j.prowjob_job_name = jv_upgrade.job_name
   AND jv_upgrade.variant_name = 'Upgrade'
  WHERE j.prowjob_start >= DATETIME_SUB(CURRENT_DATETIME(), INTERVAL @window_days DAY)
    AND j.prowjob_state = 'success'
),
snapshots AS (
  SELECT
    p.JobRunName, p.Namespace, p.Deployment,
    p.MemoryRequestMB, p.StartMemoryUsageMB, u.is_upgrade,
    DENSE_RANK() OVER (
      PARTITION BY p.JobRunName, p.Deployment
      ORDER BY REGEXP_EXTRACT(p.Source, r'_(\d{8}-\d{6})-autodl') DESC
    ) AS snapshot_rank,
    COUNT(*) OVER (PARTITION BY p.JobRunName, p.Deployment) AS snap_count
  FROM `openshift-ci-data-analysis.ci_data_autodl.control_plane_singleton_pods` p
  JOIN release_runs u USING (JobRunName)
  WHERE p.PartitionTime >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL @window_days DAY)
    AND p.Namespace NOT LIKE 'openshift-e2e-%'
    AND p.Namespace NOT LIKE 'openshift-must-gather%'
    AND p.Namespace NOT LIKE 'e2e-%'
),
post_upgrade AS (
  SELECT JobRunName, Namespace, Deployment, MemoryRequestMB, StartMemoryUsageMB
  FROM snapshots
  WHERE snapshot_rank = 1
    AND NOT (is_upgrade AND snap_count < 2)
)
SELECT
  Namespace, Deployment,
  COUNT(DISTINCT JobRunName) AS job_runs,
  ROUND(APPROX_QUANTILES(StartMemoryUsageMB, 100)[OFFSET(90)], 1) AS p90_start_mb,
  ROUND(APPROX_QUANTILES(StartMemoryUsageMB, 100)[OFFSET(50)], 1) AS p50_start_mb,
  ROUND(APPROX_QUANTILES(MemoryRequestMB, 100)[OFFSET(50)], 1) AS request_mb,
  ROUND(MIN(MemoryRequestMB), 1) AS request_mb_min,
  ROUND(MAX(MemoryRequestMB), 1) AS request_mb_max
FROM post_upgrade
GROUP BY Namespace, Deployment
ORDER BY Namespace, Deployment
