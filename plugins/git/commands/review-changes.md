---
description: OpenShift CI configuration review and validation
argument-hint: [--staged|--pr-ready|--commits N]
---

## Name
git:review-changes

## Synopsis
```text
/git:review-changes                    # Review OpenShift CI config changes
/git:review-changes --staged           # Review staged CI configs only
/git:review-changes --pr-ready         # Generate CI-focused PR summary
/git:review-changes --commits N        # Review CI changes in last N commits
```

## Description
Specialized OpenShift CI configuration reviewer that validates Prow configurations, ci-operator configs, and step-registry components. Focuses on CI/CD pipeline best practices specific to OpenShift development workflows.

**Key Features:**
- ci-operator configuration validation
- Prow job definition analysis
- Step-registry component best practices
- YAML syntax and structure validation
- Resource usage optimization recommendations
- Integration pattern validation

**Use cases:**
- Pre-commit CI configuration validation
- Step-registry component review
- Prow job optimization analysis
- CI pipeline best practice enforcement
- Release engineering workflow validation

**Scope:**
This command specifically targets OpenShift CI configurations and does NOT perform general code review (use CodeRabbit for that). It focuses on areas where domain-specific knowledge of OpenShift CI patterns is essential.

## Implementation

## Phase 1: Parse Arguments and Determine Scope

**Argument Processing:**
```bash
# Parse command line arguments to determine review scope
case "$1" in
    "--staged")     SCOPE="staged"    ; DIFF_CMD="git diff --cached" ;;
    "--pr-ready")   SCOPE="pr-ready"  ; DIFF_CMD="git diff HEAD" ; FORMAT="markdown" ;;
    "--commits")    SCOPE="commits"   ; DIFF_CMD="git diff HEAD~$2..HEAD" ;;
    "")            SCOPE="workdir"   ; DIFF_CMD="git diff HEAD" ;;
    *)             echo "Invalid argument: $1" ; exit 1 ;;
esac
```

**Validation Rules:**
- `--commits` requires numeric argument (1-20)
- Cannot combine `--staged` with `--commits` 
- `--pr-ready` can combine with `--staged` or `--commits`
- Default behavior when no arguments provided

**Scope Determination:**
- **Default/Working Directory**: All uncommitted changes (`git diff HEAD`)
- **Staged Only**: Changes in staging area (`git diff --cached`) 
- **Commit History**: Last N commits (`git diff HEAD~N..HEAD`)
- **PR Ready**: Any scope with markdown output formatting

## Phase 1.5: OpenShift CI Environment Detection

**Repository Validation:**
```bash
# Verify this is an OpenShift CI repository
if [[ ! -d "ci-operator/config" ]] && [[ ! -d "ci-operator/step-registry" ]]; then
    echo "❌ Not an OpenShift CI repository - use CodeRabbit for general code review"
    exit 1
fi

# Detect CI component types in changes
CI_COMPONENTS=""
if grep -q "ci-operator/config" <<< "$CHANGED_FILES"; then
    CI_COMPONENTS="$CI_COMPONENTS,ci-configs"
fi
if grep -q "ci-operator/step-registry" <<< "$CHANGED_FILES"; then
    CI_COMPONENTS="$CI_COMPONENTS,step-registry"
fi
if grep -q "ci-operator/jobs" <<< "$CHANGED_FILES"; then
    CI_COMPONENTS="$CI_COMPONENTS,prow-jobs"
fi
if grep -q "core-services" <<< "$CHANGED_FILES"; then
    CI_COMPONENTS="$CI_COMPONENTS,core-services"
fi

# Load OpenShift CI patterns and conventions
source /path/to/openshift-ci-patterns.sh  # Contains known good patterns
```

**CI-Specific Context Loading:**
- Load known ci-operator configuration patterns
- Reference step-registry best practices
- Check against Prow job naming conventions
- Validate resource usage patterns
- Cross-reference with OpenShift release requirements

## Phase 2: Change Detection
1. Execute determined diff command to get changes
2. Extract changed files and diff content  
3. Identify file types for language-specific analysis
4. Filter out binary files and generated code
5. Apply repository-specific context if available

## Phase 3: OpenShift CI Configuration Analysis

**CI-Operator Configuration Review (`ci-operator/config/`):**
1. **Configuration Structure**
   - Validate required fields: `base_images`, `build_root`, `images`, `tests`
   - Check naming conventions: `{org}-{repo}-{branch}.yaml`
   - Ensure proper image references and tags
   - Validate resource requests/limits

2. **Build Configuration**
   - Review base image choices and security implications
   - Validate Dockerfile paths and build contexts
   - Check image promotion targets
   - Analyze build dependencies and caching strategies

3. **Test Configuration**
   - Validate test step references to step-registry
   - Check for proper test isolation and cleanup
   - Review resource allocation for test workloads
   - Ensure test naming follows conventions

4. **Release Integration**
   - Validate promotion configuration
   - Check release branch patterns
   - Review integration with release controllers
   - Ensure proper tagging and versioning

**Step-Registry Component Review (`ci-operator/step-registry/`):**
1. **Component Structure**
   - Validate required files: `{name}-ref.yaml`, `{name}-commands.sh`
   - Check component metadata and documentation
   - Review parameter definitions and defaults
   - Validate component dependencies

2. **Script Quality**
   - Shell script best practices and error handling
   - Proper exit codes and error propagation
   - Resource cleanup and teardown procedures
   - Security considerations in script execution

3. **Reusability Patterns**
   - Check for duplicate functionality across components
   - Validate component composition patterns
   - Review parameter passing and environment setup
   - Ensure consistent naming and categorization

**Prow Job Analysis (`ci-operator/jobs/`):**
1. **Job Configuration**
   - Validate generated job configurations
   - Check job triggers and conditions
   - Review resource allocation and limits
   - Ensure proper cleanup and timeout settings

2. **Integration Patterns**
   - Validate webhook configurations
   - Check branch protection integration
   - Review notification and reporting setup
   - Ensure proper secret and credential handling

**Core Services Review (`core-services/`):**
1. **Service Configuration**
   - Validate Kubernetes resource definitions
   - Check service mesh and networking configuration
   - Review monitoring and alerting setup
   - Validate backup and disaster recovery procedures

## Phase 4: Generate Structured Report
1. **Summary Section**: High-level change overview
2. **Critical Issues**: Security and performance blockers
3. **Recommendations**: Specific improvement suggestions
4. **Review Checklist**: Items for human reviewers to verify
5. **Test Plan**: Suggested testing approach

## Phase 5: Format Output
- `--pr-ready` flag generates markdown formatted for PR descriptions
- Standard output uses terminal-friendly formatting with colors/icons
- Include file references with line numbers for easy navigation

## Examples

```bash
# Review all uncommitted changes
/git:review-changes

# Review only staged files before commit
git add src/auth.ts src/middleware.ts
/git:review-changes --staged

# Generate PR description with review summary
/git:review-changes --pr-ready

# Review changes in last 3 commits
/git:review-changes --commits 3
```

### OpenShift CI-Specific Examples

**CI-Operator Configuration Review:**
```bash
# Review changes to ci-operator configs before commit
git add ci-operator/config/openshift/cluster-authentication-operator/
/git:review-changes --staged

# Output includes:
# ✅ CI-Operator Config: openshift-cluster-authentication-operator-master.yaml
#    - Build configuration: ✅ Valid base images
#    - Test steps: ⚠️  Missing integration test coverage
#    - Resource limits: ✅ Appropriate resource allocation
#    - Promotion: ✅ Correct promotion targets
```

**Step-Registry Component Review:**
```bash
# Review new step-registry components
git add ci-operator/step-registry/openshift/e2e/
/git:review-changes --pr-ready

# Output includes:
# 🔧 Step-Registry Component: openshift-e2e-test
#    - Component structure: ✅ All required files present
#    - Shell script quality: ⚠️  Missing error handling in line 45
#    - Reusability: ✅ Follows naming conventions
#    - Documentation: ❌ Missing usage examples in ref.yaml
```

**Multi-Component Changes:**
```bash
# Review complex CI changes affecting multiple components
/git:review-changes --commits 3

# Output includes:
# 📊 CI Configuration Analysis Summary
#    - 5 ci-operator configs modified
#    - 2 new step-registry components added
#    - 12 generated prow jobs updated
#    - Overall impact: Medium (affects 3 repositories)
```

**Generated Prow Jobs Review:**
```bash
# Review auto-generated prow job changes
git add ci-operator/jobs/openshift/
/git:review-changes

# Output includes:
# 🤖 Generated Prow Jobs: openshift-cluster-authentication-operator
#    - Job generation: ✅ Properly generated from config
#    - Resource allocation: ⚠️  High memory usage for presubmit-unit
#    - Triggers: ✅ Appropriate trigger conditions
#    - Timeouts: ✅ Reasonable timeout settings
```

## Return Value

**Standard Format:**
```text
🔍 OpenShift CI Configuration Analysis

📋 SUMMARY
- 4 CI configs changed, 2 step-registry components added
- Components: ci-operator (3), step-registry (2), prow-jobs (12 generated)
- Scope: Authentication operator CI pipeline updates

🔴 CRITICAL ISSUES
- ci-operator/config/openshift-cluster-auth-master.yaml:45 - Missing required test step
- ci-operator/step-registry/auth/validate/commands.sh:23 - Unsafe shell expansion

⚠️  CI/CD CONCERNS  
- Resource allocation: 4GB memory request may cause scheduling issues
- Job timeout: 6h timeout excessive for unit tests
- Missing cleanup: No teardown steps for integration tests

✅ POSITIVE CHANGES
- Proper step-registry component structure
- Appropriate base image selection (UBI9)
- Good resource isolation between test phases
- Comprehensive test matrix coverage

📝 RECOMMENDATIONS
1. Add missing integration test step to ci-operator config
2. Fix shell script vulnerabilities in step-registry components
3. Reduce resource requests for unit test jobs
4. Add proper cleanup steps for integration tests
5. Consider using existing openshift-e2e-* components instead of custom steps

🧪 CI VALIDATION CHECKLIST
- [ ] All ci-operator configs validate against schema
- [ ] Step-registry components follow naming conventions
- [ ] Generated prow jobs have appropriate resource limits
- [ ] Test steps properly reference existing components
- [ ] Release promotion targets are correctly configured

📁 CI COMPONENTS REVIEWED
- ci-operator/config/openshift/cluster-authentication-operator/master.yaml (32 lines)
- ci-operator/step-registry/openshift/auth/validate/ref.yaml (new file)
- ci-operator/step-registry/openshift/auth/validate/commands.sh (new file)
- ci-operator/jobs/openshift/cluster-authentication-operator/ (12 generated jobs)
```

**PR-Ready Format (`--pr-ready`):**
```markdown
## OpenShift CI Configuration Review

### Changes Overview
- **CI Components:** 4 ci-operator configs, 2 step-registry components
- **Generated Jobs:** 12 prow jobs auto-generated
- **Scope:** Authentication operator CI pipeline enhancement

### Critical Issues ⚠️
- **BLOCKING**: Missing required test step in ci-operator config
- **SECURITY**: Unsafe shell expansion in step-registry script

### CI/CD Impact ✅
- **RESOURCE**: 4GB memory requests may cause node pressure
- **TIMEOUT**: 6h timeout excessive for unit tests
- **IMPROVEMENT**: Good step-registry component reusability

### CI Review Checklist
- [ ] Verify ci-operator configs validate against schema
- [ ] Confirm step-registry components follow naming conventions  
- [ ] Test generated prow jobs have appropriate resources
- [ ] Validate release promotion configuration
- [ ] Check integration with existing CI workflows

### CI Validation Plan
- Schema validation for all ci-operator configs
- Step-registry component integration testing
- Resource usage analysis for generated jobs
- End-to-end CI pipeline testing
- Release controller integration verification
```

## Security Guidelines

**The command follows these security principles:**
- Never logs or displays actual secret values
- Provides generic warnings about credential patterns
- Suggests secure alternatives for identified issues
- Focuses on defensive security practices only

## OpenShift CI Component Reviews

**CI-Operator Configurations:**
- YAML schema validation and syntax
- Required field presence and format
- Resource request/limit appropriateness
- Base image security and currency
- Test step reference validation
- Promotion target configuration

**Step-Registry Components:**
- Shell script security and best practices
- Error handling and exit code patterns
- Component reusability and composition
- Parameter definition and validation
- Documentation completeness and examples
- Naming convention compliance

**Generated Prow Jobs:**
- Resource allocation optimization
- Trigger condition appropriateness  
- Timeout and retry configuration
- Secret and credential handling
- Cleanup and teardown procedures
- Integration with existing workflows

**Core Services:**
- Kubernetes resource definition validation
- Service mesh configuration review
- Monitoring and alerting setup
- Backup and recovery procedures

## Arguments

- **--staged**: Review only staged changes (git diff --cached)
- **--pr-ready**: Format output as PR-ready markdown summary
- **--commits N**: Review changes in last N commits (1-20)
- **[default]**: Review all uncommitted changes in working directory

## See Also
- **`/ci:add-debug-wait`** - Add debug waits to failing CI jobs
- **`/ci:query-job-status`** - Check status of OpenShift CI jobs
- **`/git:commit-suggest`** - Generate CI-focused conventional commit messages
- **`/utils:generate-test-plan`** - Create CI validation test plans
- **`/step-finder`** - Search step-registry for reusable components