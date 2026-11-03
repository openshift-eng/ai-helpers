#!/usr/bin/env python3
"""Generate the check-memory-drift eval case dirs (input.yaml + annotations.yaml).

Re-runnable: rewrites cases/check-memory-drift/case-NNN/. Fixtures only; running
the eval is done by the agent-eval-harness against eval-check-memory-drift.yaml.

input.yaml is native YAML: the skill reads its fields (command_args,
devel_release, bigquery, rows, manifests_present, preexisting_bugs) directly from
the workspace, per the eval's system_prompt.
"""
from collections import OrderedDict
from pathlib import Path

import yaml


def _represent_odict(dumper, data):
    return dumper.represent_mapping("tag:yaml.org,2002:map", data.items())


yaml.add_representer(OrderedDict, _represent_odict)

CASES_DIR = Path(__file__).resolve().parent.parent / "cases" / "check-memory-drift"


def run_rows(deployment, namespace, n, start_mb, request_mb, release="5.1",
             age_days=5, prefix="r", row_type="single", is_upgrade=False):
    return [
        {"job_id": f"{prefix}-{deployment}-{i}", "deployment": deployment,
         "namespace": namespace, "release": release, "age_days": age_days,
         "row_type": row_type, "is_upgrade": is_upgrade,
         "start_mb": start_mb, "request_mb": request_mb}
        for i in range(n)
    ]


def fixture(rows, command_args="", devel_release="5.1", bigquery="ok",
            manifests_present=None, preexisting_bugs=None):
    deployments = sorted({r["deployment"] for r in rows}) if manifests_present is None else manifests_present
    # Ordered so rows (the bulky list) land last in the YAML file.
    return OrderedDict([
        ("command_args", command_args),
        ("devel_release", devel_release),
        ("bigquery", bigquery),
        ("manifests_present", deployments),
        ("preexisting_bugs", preexisting_bugs or []),
        ("rows", rows),
    ])


CASES = []


def case(num, name, payload, annotations):
    CASES.append((num, name, payload, annotations))


# 001 default parameters (F1)
rows = (run_rows("network-operator", "openshift-network-operator", 3, 260, 50)
        + run_rows("old-rel", "openshift-old", 2, 260, 50, release="4.20")
        + run_rows("stale", "openshift-stale", 2, 260, 50, age_days=120))
case("001", "default-params",
     fixture(rows, devel_release="5.1"),
     {"expected_release": "5.1", "expected_window_days": 30,
      "expected_not_candidates": ["old-rel", "stale"],
      "notes": "No args: analyze devel release 5.1 over 30 days; other-release and >30d-old rows are out of scope."})

# 002 release override (F2)
rows = (run_rows("network-operator", "openshift-network-operator", 3, 260, 50, release="4.20")
        + run_rows("fivedotone", "openshift-fivedotone", 2, 260, 50, release="5.1"))
case("002", "release-override",
     fixture(rows, command_args="--release 4.20", devel_release="5.1"),
     {"expected_release": "4.20", "expected_not_candidates": ["fivedotone"],
      "notes": "--release 4.20 analyzes only 4.20 rows; 5.1 rows ignored."})

# 003 window override (F3)
rows = (run_rows("network-operator", "openshift-network-operator", 3, 260, 50, age_days=3)
        + run_rows("older", "openshift-older", 2, 260, 50, age_days=20))
case("003", "window-7",
     fixture(rows, command_args="--window-days 7"),
     {"expected_window_days": 7, "expected_not_candidates": ["older"],
      "notes": "--window-days 7 excludes rows older than 7 days."})

# 004 snapshot selection, two-row upgrade (F5)
rows = [
    {"job_id": "job-1", "deployment": "etcd-operator", "namespace": "openshift-etcd-operator",
     "release": "5.1", "age_days": 5, "row_type": "post-install", "is_upgrade": True, "start_mb": 500, "request_mb": 50},
    {"job_id": "job-1", "deployment": "etcd-operator", "namespace": "openshift-etcd-operator",
     "release": "5.1", "age_days": 5, "row_type": "post-upgrade", "is_upgrade": True, "start_mb": 1000, "request_mb": 50},
    {"job_id": "job-2", "deployment": "etcd-operator", "namespace": "openshift-etcd-operator",
     "release": "5.1", "age_days": 5, "row_type": "post-install", "is_upgrade": True, "start_mb": 600, "request_mb": 50},
    {"job_id": "job-2", "deployment": "etcd-operator", "namespace": "openshift-etcd-operator",
     "release": "5.1", "age_days": 5, "row_type": "post-upgrade", "is_upgrade": True, "start_mb": 1200, "request_mb": 50},
]
case("004", "snapshot-upgrade-row",
     fixture(rows),
     {"expected_selected": [{"job_id": "job-1", "start_mb": 1000},
                            {"job_id": "job-2", "start_mb": 1200}],
      "notes": "Upgrade runs: use the post-upgrade snapshot, not post-install."})

# 005 single-row non-upgrade (F6 part 1)
rows = [{"job_id": "job-3", "deployment": "dns-operator", "namespace": "openshift-dns-operator",
         "release": "5.1", "age_days": 5, "row_type": "single", "is_upgrade": False, "start_mb": 150, "request_mb": 50}]
case("005", "single-row-nonupgrade",
     fixture(rows),
     {"expected_selected": [{"job_id": "job-3", "start_mb": 150}],
      "expected_excluded_runs": [],
      "notes": "A non-upgrade job writes one valid row; use it."})

# 006 defective upgrade missing post-upgrade (F6 part 2)
rows = [{"job_id": "job-4", "deployment": "dns-operator", "namespace": "openshift-dns-operator",
         "release": "5.1", "age_days": 5, "row_type": "post-install", "is_upgrade": True, "start_mb": 600, "request_mb": 50}]
case("006", "defective-upgrade-missing-post",
     fixture(rows),
     {"expected_selected": [], "expected_excluded_runs": ["job-4"],
      "notes": "Upgrade run missing its post-upgrade snapshot is defective: exclude + warn naming the job."})

# 007 p90 across runs (F4)
rows = []
for i in range(1, 21):
    rows.append({"job_id": f"u-{i}", "deployment": "network-operator", "namespace": "openshift-network-operator",
                 "release": "5.1", "age_days": 5, "row_type": "post-install", "is_upgrade": True, "start_mb": 9999, "request_mb": 50})
    rows.append({"job_id": f"u-{i}", "deployment": "network-operator", "namespace": "openshift-network-operator",
                 "release": "5.1", "age_days": 5, "row_type": "post-upgrade", "is_upgrade": True, "start_mb": 100 * i, "request_mb": 50})
case("007", "p90-across-runs",
     fixture(rows, command_args="--min-runs 5"),
     {"expected_p90": {"network-operator": 1800},
      "notes": "20 runs; post-install 9999 is a within-run spike that must be ignored. p90 across the 20 post-upgrade values [100..2000] = 1800."})

# 008 threshold boundary (E05)
rows = (run_rows("dep-at", "openshift-dep-at", 1, 130.0, 110)     # recommended 143.0 -> drift exactly 30.0
        + run_rows("dep-above", "openshift-dep-above", 1, 120.0, 100))  # recommended 132.0 -> drift 32.0
case("008", "threshold-boundary",
     fixture(rows, command_args="--min-runs 1"),
     {"expected_candidates": [{"deployment": "dep-above", "direction": "raise", "recommended_mb": 132.0}],
      "expected_not_candidates": ["dep-at"],
      "notes": "A candidate needs drift STRICTLY greater than the threshold. dep-at drifts exactly 30% (excluded); dep-above 32% (included)."})

# 009 raise direction + recommendation + bug content (E04/E05/E11)
rows = run_rows("marketplace-operator", "openshift-marketplace", 1, 45.4, 5)
case("009", "raise-bug-content",
     fixture(rows, command_args="--min-runs 1"),
     {"expected_candidates": [{"deployment": "marketplace-operator", "direction": "raise", "recommended_mb": 49.9}],
      "expected_bugs_count": 1,
      "expected_bug_labels": ["issue-for-agent", "ocp-memory-requests", "ai-generated-jira"],
      "expected_description_contains": ["memory-drift-key: 5.1/openshift-marketplace/marketplace-operator", "single-node"],
      "notes": "Under-provisioned operator: one bug with both labels, recommended 45.4*1.10=49.9, drift key, and a single-node warning."})

# 010 lower direction (E05/E11)
rows = run_rows("image-registry", "openshift-image-registry", 1, 38.5, 256)
case("010", "lower-bug-content",
     fixture(rows, command_args="--min-runs 1"),
     {"expected_candidates": [{"deployment": "image-registry", "direction": "lower", "recommended_mb": 42.4}],
      "expected_bugs_count": 1,
      "expected_description_contains": ["lower"],
      "notes": "Over-provisioned: one bug phrased as lowering the request. 38.5*1.10=42.35 -> 42.4 (round half up)."})

# 011 manifest skip (C/E08)
rows = run_rows("old-test-operator", "openshift-old-test-operator", 1, 400, 50)
case("011", "manifest-skip",
     fixture(rows, command_args="--min-runs 1", manifests_present=[]),
     {"expected_skipped": [{"deployment": "old-test-operator", "reason_contains": "manifest not found"}],
      "expected_bugs_count": 0,
      "notes": "Deployment is absent from release manifests: skip with reason, open no bug."})

# 012 variable requests (E09)
rows = (run_rows("kube-apiserver-operator", "openshift-kube-apiserver-operator", 1, 212.3, 50, prefix="lo")
        + run_rows("kube-apiserver-operator", "openshift-kube-apiserver-operator", 1, 212.3, 100, prefix="hi"))
case("012", "variable-requests",
     fixture(rows, command_args="--min-runs 1"),
     {"expected_candidates": [{"deployment": "kube-apiserver-operator", "var": True}],
      "expected_description_contains": ["manifest"],
      "notes": "Same deployment configured with two different requests (50/100): flag var and tell the reviewer to check all manifests."})

# 013 idempotency (E10)
rows = run_rows("etcd-operator", "openshift-etcd-operator", 1, 160.6, 50)
bugs = [{"deployment": "etcd-operator", "namespace": "openshift-etcd-operator",
         "affected_version": "5.1", "status": "In Progress", "labels": ["ocp-memory-requests"]}]
case("013", "idempotency",
     fixture(rows, command_args="--min-runs 1", preexisting_bugs=bugs),
     {"expected_bugs_count": 0,
      "notes": "An open bug already tracks this deployment/release: reconcile, do not create a duplicate."})

# 014 dry-run (E12)
rows = run_rows("marketplace-operator", "openshift-marketplace", 1, 45.4, 5)
case("014", "dry-run",
     fixture(rows, command_args="--dry-run --min-runs 1"),
     {"expected_candidates": [{"deployment": "marketplace-operator", "direction": "raise"}],
      "expected_bugs_count": 0,
      "notes": "--dry-run: compute and report candidates but author no bugs."})

# 015 no drift (E13)
rows = run_rows("console-operator", "openshift-console-operator", 1, 100.0, 110)
case("015", "no-drift",
     fixture(rows, command_args="--min-runs 1"),
     {"expected_not_candidates": ["console-operator"], "expected_bugs_count": 0,
      "notes": "recommended 110.0 vs request 110 -> 0% drift -> no candidate, no bug."})

# 016 empty result (E14)
case("016", "empty-result",
     fixture([]),
     {"expected_bugs_count": 0,
      "notes": "No rows for the release in the window: clear report, no bug."})


def main():
    for num, name, payload, ann in CASES:
        d = CASES_DIR / f"case-{num}"
        d.mkdir(parents=True, exist_ok=True)
        with (d / "input.yaml").open("w") as f:
            f.write(f"# case-{num}: {name} — mocked input for check-memory-drift\n")
            yaml.dump(payload, f, sort_keys=False, default_flow_style=False, width=1000)
        ann = {**ann}
        notes = ann.pop("notes", "")
        with (d / "annotations.yaml").open("w") as f:
            f.write(f"# case-{num}: {name}\n")
            yaml.safe_dump(ann, f, sort_keys=False, default_flow_style=False, width=1000)
            if notes:
                yaml.safe_dump({"notes": notes}, f, sort_keys=False, default_flow_style=False, width=1000)
    print(f"generated {len(CASES)} cases in {CASES_DIR}")


if __name__ == "__main__":
    main()
