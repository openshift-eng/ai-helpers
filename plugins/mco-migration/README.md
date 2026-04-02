# MCO Migration Plugin

Automated migration of MCO test cases from openshift-tests-private to machine-config-operator.

## Overview

This plugin automates the process of porting MCO (Machine Config Operator) test cases from `openshift-tests-private/test/extended/mco/` to `machine-config-operator/test/extended-priv/`. It handles all code transformations including package renaming, import rewriting, test name reformatting, template file copying, utility function migration, and build verification.

## Commands

### `/mco-migration:migrate`

Performs the complete MCO test migration in one workflow.

**What it does:**

1. Collects source repository, destination repository, and migration target
2. Analyzes source test files and destination patterns
3. Detects already-migrated tests by PolarionID
4. Transforms package names, imports, and function references
5. Transforms test names from Author format to PolarionID format
6. Migrates helper functions and compat_otp utilities
7. Copies referenced template/testdata YAML files
8. Builds the test binary and verifies migrated tests appear
9. Optionally runs a specific test against a cluster

**Key Features:**

- **Two migration modes** - Migrate a whole test file or extract a test suite from the large `mco.go` by keyword
- **Accurate name transformation** - Converts `Author:USERNAME-Qualifiers-ID-[Tags] Description` to `[PolarionID:ID][OTP] Description`
- **Import rewriting** - Replaces all `compat_otp` references with `exutil` equivalents
- **Duplicate detection** - Skips tests and functions already present in destination
- **Code preservation** - Migrates code as-is without simplification or refactoring
- **Build verification** - Compiles the binary and verifies migrated tests are listed

## Installation

This plugin is available through the ai-helpers marketplace:

```bash
/plugin marketplace add openshift-eng/ai-helpers
/plugin install mco-migration@ai-helpers
```

## Usage

Run the migration command:

```bash
/mco-migration:migrate
```

The plugin will interactively collect:

1. **Source repository** path (openshift-tests-private)
2. **Destination repository** path (machine-config-operator)
3. **compat_otp library** path (optional, for migrating utility functions)
4. **Migration target** - whole file or suite extraction from mco.go
5. **Confirmation** of configuration before proceeding

Then it executes the migration and verification automatically.

## Key Transformations

| What | Source (openshift-tests-private) | Destination (machine-config-operator) |
|------|--------------------------------|--------------------------------------|
| Package | `package mco` | `package extended` |
| CLI import | `compat_otp "github.com/openshift/origin/test/extended/util/compat_otp"` | `exutil "github.com/openshift/machine-config-operator/test/extended-priv/util"` |
| Logger import | `logger "github.com/openshift/origin/test/extended/util/compat_otp/logext"` | `logger "github.com/openshift/machine-config-operator/test/extended-priv/util/logext"` |
| Function calls | `compat_otp.By(...)`, `compat_otp.NewCLI(...)` | `exutil.By(...)`, `exutil.NewCLI(...)` |
| Describe block | `[sig-mco] MCO <Name>` | `[sig-mco][Suite:openshift/machine-config-operator/longduration][Serial][Disruptive] MCO <Name>` |
| Test name | `Author:user-Qualifiers-ID-[Tags] Description [Serial]` | `[PolarionID:ID][OTP] Description` |
| Templates | `test/extended/testdata/mco/` | `test/extended-priv/testdata/files/` |
| ConnectedOnly | `ConnectedOnly` qualifier in name | `[Skipped:Disconnected]` tag |

## Verification

After migration, the plugin automatically:

1. **Builds** the test binary: `make machine-config-tests-ext`
2. **Lists** tests and verifies migrated PolarionIDs appear
3. **Optionally runs** a specific test (requires KUBECONFIG)

Manual verification:

```bash
# Build
make machine-config-tests-ext

# List and verify
./_output/linux/amd64/machine-config-tests-ext list | grep <polarion_id>

# Run a test
export KUBECONFIG=/path/to/kubeconfig
./_output/linux/amd64/machine-config-tests-ext run-test "<test_name>"
```

## Important Migration Rules

- **Do NOT simplify or refactor** migrated code - only change references
- **Preserve function order** from the original source file
- **Use same file names** as the original for compat_otp utility functions
- **Skip duplicates** - tests and functions already in destination are not re-migrated
- **Template files** are copied from `testdata/mco/` to `testdata/files/`
- **Large mco.go** - use suite extraction mode to break it into smaller files before migrating

## Resources

- [Machine Config Operator](https://github.com/openshift/machine-config-operator)
- [OpenShift Tests Private](https://github.com/openshift/openshift-tests-private)
