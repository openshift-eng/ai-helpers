---
description: Bump the release version in ci-operator config files
---

## Name
prow-job:bump-release-version

## Synopsis
```bash
/prow-job:bump-release-version <config-file>[,<config-file>...] [--bump=N]
```

## Description

The `prow-job:bump-release-version` command creates new ci-operator config files with bumped OpenShift release versions. It intelligently updates all version references, generates new random cron schedules while preserving test frequencies, and creates properly named output files.

**Usage Examples:**

1. **Bump a single config file by 1 minor version (default)**:
   ```bash
   /prow-job:bump-release-version openshift-verification-tests-main__installation-nightly-4.21.yaml
   ```
   Creates: `openshift-verification-tests-main__installation-nightly-4.22.yaml`

2. **Bump by 2 minor versions**:
   ```bash
   /prow-job:bump-release-version openshift-verification-tests-main__ota-multi-stable-4.20-cpou-upgrade-from-stable-4.18.yaml -b 2
   ```
   Creates: `openshift-verification-tests-main__ota-multi-stable-4.22-cpou-upgrade-from-stable-4.20.yaml`

3. **Bump multiple files**:
   ```bash
   /prow-job:bump-release-version file1-4.21.yaml,file2-4.21.yaml
   ```

## Implementation

### Phase 1: Input Parsing and Validation

1. **Parse arguments**:
   - Extract comma-separated config file names
   - Parse optional `--bump=N` or `-b N` parameter (default: 1)
   - Validate bump increment is a positive integer

2. **Locate files**:
   - Check current working directory
   - Report missing files and skip them

### Phase 2: Version Detection

For each file:

1. **Read file content** and identify current version from:
   - Filename pattern: `*-4.21.yaml`
   - `base_images[*].name` fields: `"4.21"`
   - `releases[*].version` fields: `"4.21"`
   - `zz_generated_metadata.variant`: `installation-nightly-4.21`

2. **Calculate target version**:
   - Parse as MAJOR.MINOR format (e.g., 4.21)
   - Apply formula: `NEW_MINOR = CURRENT_MINOR + BUMP_INCREMENT`
   - Examples:
     - 4.21 + bump=1 → 4.22
     - 4.20 + bump=2 → 4.22

### Phase 3: File Generation

1. **Replace all version references** throughout the file:
   - `base_images[*].name`: `"4.21"` → `"4.22"`
   - `releases[*].version`: `"4.21"` → `"4.22"`
   - `zz_generated_metadata.variant`: `installation-nightly-4.21` → `installation-nightly-4.22`

2. **Generate new cron schedules** for ALL test entries:
   - Preserve test frequency from original cron
   - Analyze original cron to identify frequency pattern:
     - f7 (weekly): 4 runs/month, all months (e.g., `2,9,16,23 * *`)
     - f14 (biweekly): 2 runs/month, all months (e.g., `5,19 * *`)
     - f28 (monthly): 1 run/month, all months (e.g., `12 * *`)
     - f60 (every 2 months): 1 run, alternating months (e.g., `7 2,4,6,8,10,12 *`)

   - Generate new random cron maintaining same frequency:
     - Always randomize: MINUTE (0-59), HOUR (0-23)
     - Preserve exactly: MONTH pattern (e.g., `2,4,6,8,10,12` stays `2,4,6,8,10,12`)
     - Randomize with same count: DAY values (e.g., 2 days → 2 different days)
     - Preserve: DOW (day of week) pattern

   - Examples:
     ```text
     Original: 32 14 2,9,16,23 * *  (f7 - weekly)
     New:      45  8 3,10,17,24 * * (still f7 - different times, same frequency)

     Original: 21 6 5,19 * *         (f14 - biweekly)
     New:      18 12 7,21 * *        (still f14 - different times, same frequency)

     Original: 33 23 7 2,4,6,8,10,12 * *  (f60 - even months)
     New:      40 10 15 2,4,6,8,10,12 * * (still f60 - same months, different day/time)
     ```

3. **Write new file** with bumped version in filename:
   - Input:  `openshift-verification-tests-main__installation-nightly-4.21.yaml`
   - Output: `openshift-verification-tests-main__installation-nightly-4.22.yaml`

### Phase 4: Verification

1. **Compare files** line-by-line to verify ONLY these changed:
   - Version numbers (all occurrences)
   - Cron schedules

2. **Report changes**:
   - Count version replacements
   - Count cron schedule updates
   - Flag any unexpected differences

### Phase 5: Summary Report

Provide structured summary:

```text
Processing 1 file(s)...
Bump increment: 1

[1/1] Processing: openshift-verification-tests-main__installation-nightly-4.21.yaml
  ✓ File exists
  ✓ Detected version: 4.21
  ✓ Target version: 4.22
  ✓ Created: openshift-verification-tests-main__installation-nightly-4.22.yaml
  ✓ Version replacements: 47
  ✓ Cron schedules updated: 85
  ✓ Verification passed

Summary:
┌────────────────────────────────────────────────────────────────┬──────────┬────────┐
│ File                                                            │ Version  │ Status │
├────────────────────────────────────────────────────────────────┼──────────┼────────┤
│ openshift-verification-tests-main__installation-nightly-4.21   │ 4.21→4.22│   ✓    │
└────────────────────────────────────────────────────────────────┴──────────┴────────┘

Total: 1 processed, 1 successful, 0 failed
```

## Arguments

- **`<config-file>[,<config-file>...]`** (required): One or more ci-operator config filenames, comma-separated. Files can be in current directory or `ci-operator/config/` subdirectories.

- **`--bump=N`** or **`-b N`** (optional, default: 1): Number of minor versions to bump. Must be a positive integer.

## Important Notes

- This command creates **NEW** files; it does NOT modify the original files
- Generated files should be reviewed before committing
- After generation, run `make jobs` to update Prow job configurations
- Ensure the new version is valid for the OpenShift release you're targeting

