---
description: Automate OpenShift Tests Extension (OTE) migration for component repositories
argument-hint: ""
---

## Name

ote-migration:migrate

## Synopsis

```bash
/ote-migration:migrate
```

## Description

The `ote-migration:migrate` command automates the complete migration of OpenShift component repositories to use the openshift-tests-extension (OTE) framework. It handles everything from repository setup to code generation, test migration, dependency resolution, and Docker integration.

**What it does:**

1. Collects configuration (directory strategy, repositories, paths)
2. Sets up source and target repositories
3. Creates directory structure (monorepo or single-module)
4. Generates code (go.mod, cmd/extension/main.go, Makefile, bindata.mk, fixtures.go)
5. Migrates tests (replaces FixturePath calls, updates imports, adds annotations)
6. Resolves dependencies (go mod tidy + vendor at root for monorepo)
7. Integrates with Docker (automated or manual)

**Key Features:**

- **No sig filtering** - All tests included without filtering logic
- **CMD at root (monorepo)** - Places cmd/extension/main.go at repository root, not under test/
- **Simple annotations** - Adds [OTP] at beginning of Describe blocks, [Level0] at beginning of test names only
- **Vendor at root only (monorepo)** - Dependencies vendored only at repository root
- **Atomic test migration** - Backup and rollback on failure
- **Automated Docker integration** - Optional automated Dockerfile updates with backup

## Implementation

**IMPORTANT: Use the OTE Migration Workflow skill for implementation.**

This command uses the `ote-migration-workflow` skill which provides detailed step-by-step implementation guidance for all 8 phases of the migration.

To execute this command:

1. **Invoke the skill** to get detailed implementation instructions:
   - The skill is located at: `plugins/ote-migration/skills/ote-migration-workflow/SKILL.md`
   - Follow the skill's 8-phase workflow exactly as documented

2. **The workflow phases are:**
   - **Phase 1**: User Input Collection (10 inputs - includes Dockerfile integration choice)
   - **Phase 2**: Repository Setup
   - **Phase 3**: Structure Creation
   - **Phase 4**: Code Generation
   - **Phase 5**: Test Migration (atomic with rollback)
   - **Phase 6**: Dependency Resolution and Verification
   - **Phase 7**: Dockerfile Integration (uses choice from Input 10)
   - **Phase 8**: Final Summary and Next Steps

3. **Critical implementation notes:**
   - Extension name (Input 4) is AUTO-DETECTED - do NOT ask user
   - Switch to target repository happens after Input 3
   - Phase 5 has atomic error handling with backup/rollback
   - For monorepo: vendor ONLY at root, NOT in test module
   - For monorepo: CMD at `cmd/extension/main.go` (at root, NOT under test/)

**For complete implementation details, error handling, and code templates, refer to the skill documentation.**

## Return Value

**Format**: Migration summary with next steps

**On success:**

- All files created and configured
- Binary built and verified
- Comprehensive next steps provided
- Lists all files created/modified

**On failure:**

- Clear error message indicating which phase failed
- For Phase 5 failures: automatic rollback to backup
- Guidance on how to resolve the issue and retry

## Examples

### Basic usage

```bash
/ote-migration:migrate
```

The command will:

1. Ask for directory strategy (monorepo or single-module)
2. Ask for workspace directory
3. Ask for target repository (local path or Git URL)
4. Auto-detect extension name
5. Ask for test directory name (monorepo only, if test/e2e exists)
6. Ask for source repository details
7. Ask for Dockerfile integration choice (automated or manual)
8. If automated: Search target repository for all Dockerfiles and ask user to select which to update
9. Display migration configuration summary (including selected Dockerfiles)
10. Execute migration phases 2-8
11. Provide comprehensive summary and next steps

### Example interaction

```text
User: /ote-migration:migrate

AI: Which directory structure strategy do you want to use?
    1. Monorepo strategy (integrate into existing repo)
    2. Single-module strategy (isolated directory)

User: 1

AI: What is the working directory path for migration workspace?

User: /home/user/repos

AI: What is the path to your target repository, or provide a Git URL to clone?

User: /home/user/repos/router

... (continues with remaining inputs and migration phases)
```

## Arguments

This command takes no arguments. All configuration is collected interactively during execution.

## Notes

- **Prerequisites**: Go toolchain (1.21+), Git, access to openshift-tests-private
- **Atomic migration**: Phase 5 backs up test files and rolls back on failure
- **Vendor location**: For monorepo, dependencies are vendored ONLY at repository root
- **CMD location**: For monorepo, cmd/extension/main.go is at repository root (NOT under test/)
- **No sig filtering**: All tests are included without filtering logic
- **Docker integration**: Choose between automated (with backup) or manual integration

## See Also

- Plugin README: `plugins/ote-migration/README.md`
- Implementation skill: `plugins/ote-migration/skills/ote-migration-workflow/SKILL.md`
- OTE Framework: <https://github.com/openshift-eng/openshift-tests-extension>
