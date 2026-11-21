-- Count of defective upgrade runs excluded from the baseline: upgrade runs that
-- emitted only one snapshot (missing their post-upgrade reading). For the report.
-- Params: @release (STRING), @window_days (INT64).
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
run_snaps AS (
  SELECT
    p.JobRunName, u.is_upgrade,
    COUNT(DISTINCT REGEXP_EXTRACT(p.Source, r'_(\d{8}-\d{6})-autodl')) AS snap_count
  FROM `openshift-ci-data-analysis.ci_data_autodl.control_plane_singleton_pods` p
  JOIN release_runs u USING (JobRunName)
  WHERE p.PartitionTime >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL @window_days DAY)
    AND p.Namespace NOT LIKE 'openshift-e2e-%'
    AND p.Namespace NOT LIKE 'openshift-must-gather%'
    AND p.Namespace NOT LIKE 'e2e-%'
  GROUP BY p.JobRunName, u.is_upgrade
)
SELECT COUNT(*) AS defective_upgrade_runs
FROM run_snaps
WHERE is_upgrade AND snap_count < 2
