---
name: Remediation Planning
description: Generate comprehensive remediation guidance including dependency updates, code changes, workarounds, and verification steps
---

# Remediation Planning

Creates actionable remediation plans for vulnerable Go codebases based on analysis results from previous phases.

## Supported Remediation Types

1. **Dependency Update** - Update Go package to fixed version
2. **Go Runtime Update** - Update Go itself (for stdlib vulnerabilities)
3. **Configuration Change** - Disable features, change settings, adjust security controls
4. **Code Refactoring** - Replace vulnerable patterns, add validation, refactor code
5. **Security Patch** - Apply vendor-provided patch files
6. **Workarounds** - Temporary mitigations (timeouts, rate limiting, input validation)
7. **Infrastructure** - Network policies, firewall rules, WAF configuration
8. **Combination** - Multiple remediation types together

The skill automatically determines the appropriate remediation strategy based on CVE details and impact analysis.

## When to Use This Skill

Use this skill when:
- Codebase is confirmed or likely affected by a CVE
- Need specific remediation steps beyond "update the package"
- Fixed version exists but need to assess compatibility
- No fixed version available and need workarounds
- Project uses custom build/test commands via Makefile

## Implementation Steps

### Step 1: Analyze Inputs and Determine Strategy

**Required Inputs from Previous Phases:**

**From Phase 1 (CVE Intelligence Gathering):**
- CVE ID, severity, CVSS score
- Affected package/module and vulnerable version range
- Fixed version (if available)
- Vulnerability type and remediation guidance

**From Phase 2 (Codebase Impact Analysis):**
- Impact verdict (AFFECTED/NOT AFFECTED/UNKNOWN)
- Confidence level (HIGH/MEDIUM/LOW)
- Current package version and dependency type
- Usage locations and functions being called

**From Call Graph Analysis (optional):**
- Reachability verdict and call chain
- Entry points

**From govulncheck (optional):**
- Detection result and vulnerable symbols

**Decision Tree:**

```
IF verdict = "NOT_AFFECTED":
  → No remediation needed (document why)
  
IF verdict = "AFFECTED":
  IF fixed_version EXISTS:
    IF affected_package is in go.mod → Dependency Update (Step 2)
    ELSE IF affected_package is Go stdlib → Go Runtime Update (Step 2A)
      
  IF fixed_version = null:
    IF remediation_guidance has "configuration" → Configuration Change (Step 2B)
    IF remediation_guidance has "code change" OR pattern vulnerability → Code Refactoring (Step 2C)
    IF remediation_guidance has "patch" → Apply Patch (Step 2D)
    ELSE → Workarounds (Step 3)
      
IF verdict = "UNKNOWN":
  → Manual review + defensive workarounds (Step 3)
```

---

### Step 2: Plan Dependency Update (If Applicable)

**Analyze the dependency situation:**

1. **Understand the dependency relationship:**
   - Is this a direct or indirect (transitive) dependency?
   - If indirect, which direct dependency pulls it in?
   - Are there multiple dependency paths to this package?
   - What version is currently in use?

2. **Assess the update strategy:**
   
   **For direct dependencies:**
   - Can we directly update to the fixed version?
   - What's the version jump? (major/minor/patch)
   - Are there intermediate versions we should consider?
   
   **For indirect dependencies:**
   - Should we update the parent package instead?
   - Will updating the parent also fix this issue?
   - Is the parent package actively maintained?
   - Do we need to explicitly override the version?
   - Is a `replace` directive necessary (avoid if possible)?

3. **Research breaking changes:**
   - Search for changelog and release notes
   - Look for BREAKING CHANGE markers
   - Check GitHub issues for migration problems
   - Assess semantic versioning signals:
     - Major version bump → Expect breaking changes
     - v0.x minor bump → May have breaking changes
     - Patch version → Should be safe
   - Identify specific API changes that affect your code

4. **Evaluate compatibility risks:**
   - Does the fixed version require a newer Go version?
   - Are there conflicts with other dependencies?
   - What's the blast radius if something breaks?
   - Is there test coverage for affected code paths?

5. **Plan the update approach:**
   - Decide on exact version to target
   - Determine the update commands to use
   - Plan for testing and validation
   - Consider gradual rollout strategy
   - Prepare rollback plan

**Document the chosen approach with specific commands and rationale for the decision.**

---

### Step 2A: Plan Go Runtime Update (If Applicable)

**Analyze Go runtime update requirements:**

1. **Determine version requirements:**
   - What Go version fixes the vulnerability?
   - What's the current Go version in use?
   - What's the minimum version bump needed?
   - Are there multiple affected Go versions with different fixes?

2. **Assess project constraints:**
   - What's the project's minimum supported Go version (from go.mod)?
   - Are there compatibility requirements (OS distributions, cloud providers)?
   - What Go versions are used in CI/CD pipelines?
   - What about developer environments?
   - Are there dependencies that constrain Go version?

3. **Evaluate upgrade path:**
   - Can we upgrade directly to the fixed version?
   - Should we target a newer Go version for future-proofing?
   - Are there intermediate versions to consider?
   - What's the official support status of target version?

4. **Research breaking changes:**
   - Review Go release notes for the target version
   - Check for deprecated features being removed
   - Look for behavior changes in standard library
   - Identify new language features that might affect build
   - Search for migration guides

5. **Plan the migration:**
   - Decide on target Go version
   - Update go.mod minimum version
   - Plan testing strategy
   - Update build systems and Docker base images
   - Update developer documentation

6. **Consider alternatives:**
   - If Go update is too disruptive, can we backport the fix?
   - Are there workarounds while planning the upgrade?
   - What's the risk of delaying the Go update?

**Document the chosen Go version, migration plan, and timeline.**

---

### Step 2B: Plan Configuration Changes (If Applicable)

**Analyze if configuration-based mitigation is possible:**

1. **Understand what the vulnerability requires to trigger:**
   - Does it require a specific feature to be enabled?
   - Does it depend on insecure default settings?
   - Is it protocol/algorithm-related?
   - Does it require network exposure?

2. **Evaluate configuration options:**
   - Review application/library configuration documentation
   - Check if security features can be enabled
   - Determine if vulnerable features can be disabled
   - Consider network-level controls

3. **Design configuration changes:**
   - **If vulnerable feature is optional:** Disable it
   - **If secure alternatives exist:** Switch to them (e.g., stronger crypto)
   - **If security controls are available:** Enable them
   - **If network exposure is unnecessary:** Restrict access

4. **Assess impact:**
   - Will disabling the feature break functionality?
   - Are there dependencies on the current configuration?
   - What's the performance/UX impact?
   - Is the change reversible?

**Configuration types to consider:**
- Application config files (YAML, JSON, properties)
- Environment variables
- Command-line flags
- Runtime feature flags
- Web server configuration (nginx, apache)
- Network policies (firewalls, Kubernetes NetworkPolicy)
- Infrastructure as Code (Terraform, CloudFormation)

**Document specific configuration changes needed with rationale.**

---

### Step 2C: Plan Code Refactoring (If Applicable)

**Analyze the vulnerability to determine code changes needed:**

**Step 2C.1: Identify Vulnerable Code Patterns**

1. **Review the CVE description:**
   - What specific code pattern or API usage is vulnerable?
   - Is it about how a function is called or what's passed to it?
   - Are there examples of vulnerable vs. safe usage?

2. **Locate vulnerable code in the codebase:**
   - Search for the vulnerable function/method calls
   - Identify all files and locations where it's used
   - Understand the context of each usage

3. **Categorize the refactoring type:**
   - **API migration:** Old API → new safe API
   - **Pattern replacement:** Unsafe pattern → safe pattern
   - **Input handling:** Add validation/sanitization
   - **Error handling:** Add proper error checks
   - **Resource management:** Add limits/cleanup
   - **Security controls:** Add authentication/authorization checks

**Step 2C.2: Design the Refactoring**

Based on the vulnerability type, determine the approach:

**For unsafe API usage:**
- Replace with secure alternative API
- Add security parameters/options to existing calls
- Wrap calls with safety checks

**For missing input validation:**
- Add validation before vulnerable operations
- Sanitize/escape untrusted data
- Use type-safe APIs where possible

**For resource management issues:**
- Add resource limits (size, time, count)
- Implement proper cleanup (defer, finally)
- Use safer resource handling patterns

**For logic flaws:**
- Fix incorrect conditionals/checks
- Add missing security validations
- Correct state management

**Step 2C.3: Plan Migration Strategy**

1. **Find all usage locations:**
   ```bash
   grep -r "<function-name>" --include="*.go" .
   # Or use codebase_search for semantic search
   ```

2. **Assess each usage:**
   - Is this usage vulnerable or safe?
   - What's the correct replacement?
   - Are there edge cases to handle?

3. **Create migration examples:**
   - Document "before" and "after" for each pattern
   - Explain why the change is necessary
   - Note any behavior changes

4. **Estimate scope:**
   - Number of files affected
   - Complexity of changes (simple replace vs. logic rewrite)
   - Test coverage available

5. **Plan testing:**
   - Which tests need updates?
   - Are new tests needed?
   - How to verify the fix works?

**Document specific code changes with file paths, line numbers, and refactoring rationale.**

---

### Step 2D: Apply Security Patches (If Applicable)

**When vendor provides patch files:**

1. **Obtain the patch:**
   - Download from vendor security advisory
   - Verify patch authenticity and source
   - Check patch format (unified diff, git patch, etc.)

2. **Review the patch carefully:**
   - Understand what changes it makes
   - Verify it targets the correct vulnerability
   - Check for any side effects or breaking changes
   - Ensure it's appropriate for your version

3. **Apply the patch:**
   - Test in non-production environment first
   - Use appropriate tool (`patch`, `git apply`)
   - Handle conflicts if any
   - Document what was patched

4. **Verify the patch:**
   - Confirm changes applied correctly
   - Run tests to ensure no breakage
   - Test the vulnerability is actually fixed
   - Document patch source and date

**For Go module patches:**
- Consider forking the repository
- Apply patch to your fork
- Use `replace` directive in go.mod to use patched version
- Document this is temporary until official fix

**Alternative:** If patch is complex or risky, consider workarounds (Step 3) while waiting for official release.

---

### Step 3: Plan Workarounds (If No Fix Available)

**Analyze the vulnerability to design appropriate mitigations:**

**Step 3.1: Understand the Vulnerability**

Ask these questions about the CVE:
1. **What type of vulnerability is it?**
   - DoS, RCE, injection, authentication bypass, information disclosure, etc.

2. **What triggers the vulnerability?**
   - User input, specific API calls, network requests, file operations, etc.

3. **What is the attack vector?**
   - Remote/network-based, local, requires authentication, etc.

4. **What resource/capability is affected?**
   - CPU, memory, network, data confidentiality, system integrity, etc.

5. **What conditions must exist for exploitation?**
   - Specific input patterns, race conditions, particular configurations, etc.

**Step 3.2: Identify Mitigation Strategies**

Based on vulnerability characteristics, consider appropriate defenses:

**For Input-Related Vulnerabilities:**
- Validate input size, format, and content before vulnerable code
- Sanitize/escape untrusted input
- Reject known malicious patterns
- Use allowlists instead of denylists where possible

**For Algorithmic Complexity / DoS:**
- Impose timeouts on operations
- Limit resource consumption (CPU time, memory)
- Add circuit breakers to prevent cascading failures
- Cache results when possible
- Consider simpler/safer algorithms for untrusted input

**For Resource Exhaustion:**
- Rate limit requests (per user, per IP, globally)
- Set quotas on operations
- Implement backpressure mechanisms
- Monitor and alert on unusual patterns

**For Authentication/Authorization Issues:**
- Add additional authentication checks
- Restrict network access (firewalls, NetworkPolicies)
- Require multi-factor authentication
- Log and monitor access attempts

**For Information Disclosure:**
- Redact sensitive data in responses
- Restrict access to affected endpoints
- Add encryption in transit/at rest
- Audit and minimize data exposure

**For Code Execution Vulnerabilities:**
- Run vulnerable code in sandboxes
- Reduce privileges (principle of least privilege)
- Disable dynamic code execution if possible
- Add integrity checks

**Step 3.3: Design Layered Defense**

Apply defense-in-depth principles:
1. **Layer multiple controls** - Don't rely on a single mitigation
2. **Fail securely** - If mitigation fails, fail closed not open
3. **Monitor for exploitation** - Add logging/alerting for attack attempts
4. **Consider degraded functionality** - Can you disable features temporarily?

**Step 3.4: Evaluate Trade-offs**

For each mitigation:
- **Effectiveness:** How well does it address the vulnerability?
- **Impact:** Will it break legitimate use cases?
- **Performance:** What's the overhead?
- **Complexity:** How difficult to implement and maintain?
- **Risk:** Could the workaround introduce new issues?

**Step 3.5: Document Mitigation Plan**

For each workaround, specify:
- What it protects against
- How it works
- Where to implement it (code location, config file, infrastructure)
- Expected impact on functionality/performance
- Monitoring/logging to detect bypass attempts
- When it can be removed (after patching)

**Note:** Workarounds are temporary defenses, not permanent solutions. Always prioritize updating to a fixed version when available.

---

### Step 4: Create Verification Plan

**Design a comprehensive verification strategy:**

1. **Understand project testing infrastructure:**
   - Does the project have a Makefile with standard targets?
   - What build and test commands does the project use?
   - Are there CI/CD pipelines that should be considered?
   - What testing levels exist? (unit, integration, e2e)
   - Are there performance or security-specific tests?

2. **Plan verification layers:**
   
   **Dependency Verification:**
   - Confirm the updated version is actually in use
   - Verify go.mod and go.sum are correctly updated
   - Check for unexpected transitive dependency changes
   - Ensure no conflicts were introduced
   
   **Build Verification:**
   - Confirm the project builds successfully
   - Check for new compiler warnings
   - Verify all target platforms still build
   - Test with different Go versions if applicable
   
   **Functional Verification:**
   - Run existing test suites (unit, integration, e2e)
   - Focus on code paths that use the updated dependency
   - Test edge cases related to the vulnerability
   - Consider adding regression tests for this CVE
   
   **Security Verification:**
   - Re-run vulnerability scanners (govulncheck, etc.)
   - Confirm the specific CVE is no longer reported
   - Check for new vulnerabilities introduced by the update
   - Validate security assumptions haven't changed
   
   **Regression Verification:**
   - Test critical user journeys
   - Check performance hasn't degraded
   - Verify logging and monitoring still work
   - Test error handling and edge cases

3. **Sequence the verification steps:**
   - Start with fast, cheap checks (dependency verification)
   - Progress to more expensive tests (full test suite)
   - End with manual/exploratory testing if needed
   - Consider parallel execution where possible

4. **Define success criteria:**
   - What must pass before considering the fix complete?
   - What level of test coverage is acceptable?
   - How to handle test failures (existing vs. new)?
   - What monitoring should be in place post-deployment?

5. **Plan for different environments:**
   - Local development verification
   - CI/CD pipeline checks
   - Staging environment validation
   - Production canary/gradual rollout

**Document specific verification commands, expected outcomes, and decision points for handling failures.**

---

### Step 5: Generate Remediation Plan Document

**Create a comprehensive, context-specific remediation document:**

**Structure the document based on the remediation type:**

1. **Executive Summary Section:**
   - State the CVE and its severity clearly
   - Summarize the vulnerability impact on THIS project
   - Present the recommended remediation approach
   - Highlight urgency and risk levels
   - Note any critical dependencies or blockers

2. **Detailed Remediation Steps:**
   
   **Tailor to the remediation type selected:**
   - **For dependency updates:** Explain the version change, why this version, compatibility considerations
   - **For Go runtime updates:** Explain version requirements, migration path, compatibility impacts
   - **For configuration changes:** Specify exact changes, why they work, impact on functionality
   - **For code refactoring:** Detail the code changes, locations, before/after comparisons
   - **For workarounds:** Explain each mitigation, why it's effective, limitations
   
   **Include:**
   - Step-by-step instructions (not just commands)
   - Rationale for each decision made
   - Project-specific context and considerations
   - Estimated time and effort
   - Prerequisites and dependencies

3. **Verification Plan:**
   - Specific commands appropriate to the project
   - Success criteria for each verification step
   - What to look for (not just "run tests")
   - How to interpret results
   - What to do if verification fails

4. **Risk Assessment:**
   
   **Update Risk:**
   - What could go wrong with this remediation?
   - Breaking changes identified
   - Dependencies on other changes
   - Performance implications
   - Rollback difficulty
   
   **Not Updating Risk:**
   - Exploitability in THIS environment
   - Actual exposure (reachability, network access)
   - Potential impact (data, availability, reputation)
   - Likelihood of exploitation
   - Compliance implications

5. **Implementation Strategy:**
   - Environment progression (dev → staging → prod)
   - Rollout approach (big bang, canary, gradual)
   - Monitoring and validation checkpoints
   - Rollback triggers and procedures
   - Communication plan for stakeholders

6. **Timeline and Effort:**
   - Estimated time for each phase
   - Resource requirements
   - Critical path items
   - Recommended deadline based on risk

7. **Supporting Information:**
   - Links to relevant documentation
   - References to CVE advisories
   - Related issues or PRs
   - Contact information for escalation

**Adapt the document structure and depth to:**
- Remediation complexity
- Organizational needs
- Audience (technical team, management, security)
- Risk level and urgency

**The document should enable someone to execute the remediation plan without additional context.**

---

## Return Value

Return structured plan to parent command:

```json
{
  "skill": "remediation-planning",
  "status": "success",
  
  "input_summary": {
    "cve_id": "<from Phase 1>",
    "verdict": "<from Phase 2>",
    "confidence": "<from Phase 2>",
    "reachable": "<from call-graph-analysis or unknown>",
    "fixed_version_available": "<true|false from Phase 1>"
  },
  
  "remediation_decision": {
    "strategy_selected": "<dependency_update|go_runtime_update|configuration|code_refactoring|workaround|combination>",
    "reasoning": "<why this strategy based on inputs>",
    "priority": "<CRITICAL|HIGH|MEDIUM|LOW based on severity+confidence+reachability>",
    "driven_by": {
      "primary_factor": "<main decision factor from analysis>",
      "confidence_factor": "<confidence level justification>",
      "availability_factor": "<fix availability>"
    }
  },
  
  "remediation_plan": {
    "remediation_type": "<type>",
    "complexity": "<LOW|MEDIUM|HIGH>",
    "fix_available": true,
    "requires_code_changes": false,
    "requires_go_update": false,
    "requires_config_changes": false,
    
    "update_commands": ["go get ...", "go mod tidy"],
    "config_changes": [],
    "code_changes_summary": "",
    "verification_commands": {
      "verify": "make verify || go mod verify",
      "build": "make build || go build ./...",
      "test": "make test || go test ./...",
      "vuln_check": "govulncheck ./..."
    },
    "breaking_changes": [],
    "estimated_effort": "15 minutes",
    "risk_level": "LOW"
  },
  
  "project_context": {
    "has_makefile": true,
    "available_commands": ["verify", "build", "test"],
    "go_version": "1.21",
    "dependency_type": "indirect"
  }
}
```

**Priority Determination:**

Priority should be calculated based on multiple factors:
- CVE severity (CRITICAL/HIGH/MEDIUM/LOW)
- Confidence level of impact assessment
- Reachability of vulnerable code
- Availability of fixes
- Exploitability in the specific environment
- Business criticality of affected systems

Higher priority when: severe + high confidence + reachable + fix available
Lower priority when: low severity + uncertain + not reachable + no immediate fix

**Automated Fix Eligibility - Decision Framework:**

Evaluate whether to offer automated fix application by considering:

1. **Confidence Level:**
   - HIGH confidence → Automation is safer
   - MEDIUM/LOW confidence → Manual review required

2. **Remediation Complexity:**
   - Simple dependency update with no breaking changes → Good candidate
   - Multiple steps or code changes → Manual application safer
   - Configuration changes with unclear impact → Needs review

3. **Risk Assessment:**
   - Well-tested fix from trusted source → Lower risk
   - Affects critical code paths → Manual verification needed
   - Breaking changes possible → Requires careful review

4. **Project Maturity:**
   - Strong test coverage → Automation safer
   - Limited testing → Manual application with thorough testing
   - Active development → Consider coordination

5. **Blast Radius:**
   - Small, localized change → Automation acceptable
   - Wide-ranging impact → Manual control preferred
   - Affects production systems → Needs careful planning

**General principles:**
- Only offer automation for high-confidence, low-risk scenarios
- Always provide clear rationale for the decision
- When in doubt, recommend manual application with monitoring
- Automation should never bypass testing and verification

---

## Integration with Parent Command

This skill is called from Phase 4 of `/compliance:analyze-cve`.

**Input Pipeline:**
```
Phase 1 (CVE Intelligence) → CVE profile, severity, affected package, fixed version
Phase 2 (Impact Analysis) → Verdict, confidence, current version, usage locations
  ↓ Optional: Call Graph Analysis Skill → Reachability verdict, call chain
  ↓ Optional: govulncheck → Detection result, vulnerable symbols
Phase 3 (Report Generation) → Consolidated impact assessment report
Phase 4 (THIS SKILL) → Complete remediation plan based on all inputs
Phase 5 (Fix Application) → Execute remediation using plan from this skill
```

**Output**: Complete remediation plan tailored to the specific CVE and project context, including verification strategy, risk assessment, priority determination, and automated fix eligibility decision based on thorough analysis.
