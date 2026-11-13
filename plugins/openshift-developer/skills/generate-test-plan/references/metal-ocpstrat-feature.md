# METAL OCPSTRAT Feature Test Plan Reference (IEEE 829)

Use this reference when the processed Jira issue is an **OCPSTRAT Feature** for the **Metal Platform** (project `OCPSTRAT` with Metal-related features). This template provides a concise, Metal-specific IEEE 829 test plan structure optimized for bare metal platform features.

---

## When to Use This Template

Apply this template when **ALL** of the following conditions are met:
1. Issue project is `OCPSTRAT`
2. Issue type is `Feature`
3. Feature is Metal Platform-related (baremetal-operator, cluster-baremetal-operator, Metal3, Ironic, BMC management, hardware inspection, bare metal provisioning)

---

## Metal Platform Context

The Metal Platform manages bare metal infrastructure in OpenShift through:
- **baremetal-operator (BMO)**: BareMetalHost API and controller
- **cluster-baremetal-operator (CBO)**: Cluster-level bare metal management
- **Metal3**: Upstream bare metal provisioning
- **Ironic**: OpenStack bare metal provisioning service

**Hardware Testing:** Metal features require testing with real bare metal hardware vendors (Dell, HPE, and Supermicro if available) in addition to virtual BMC.

---

## Document Structure (IEEE 829 for Metal Features)

Generate an IEEE 829-compliant test plan with the following structure and Metal-specific content:

### Test Plan Identifier
Format: `<OCPSTRAT-XXXX>-test-plan`

### 1. Introduction

#### Purpose
State what this test plan validates, derived from the Feature Overview/Goal Summary.

#### Scope
**In Scope:**
- List what will be tested from feature requirements
- Include Metal Platform-specific items (BMC interactions, hardware inspection, provisioning workflows, operator reconciliation)

**Out of Scope:**
- Explicitly list exclusions from the feature's Out of Scope section
- Common Metal exclusions: vendor-specific OEM fields, non-standard BMC protocols, complete hardware compatibility (unless specified)

### 2. Background / References

Standard references:
- **OCPSTRAT Issue:** Link to the feature
- **Component:** GitHub repository (e.g., openshift/baremetal-operator)
- **Related Documentation:** OpenShift Bare Metal IPI Documentation
- **Upstream Projects:** Metal3 Baremetal Operator

**Context paragraph (optional):** Brief 1-2 sentence context if needed.

### 3. Test Items

List software components under test:
- BareMetalHost API / Custom Resources
- Operator controllers (BMO, CBO)
- Metal3/Ironic integration points
- Hardware data schemas
- Configuration persistence mechanisms

### 4. Features to Be Tested

Organize requirements into categories:

#### Functional Requirements (from Acceptance Criteria)
- List each FR with ID (FR-01, FR-02, etc.)

#### User Goals
- List user-facing goals (UG-01, UG-02, etc.)

#### Additional Categories (if applicable)
- Inventory Coverage (INV-01, INV-02, etc.) for hardware inspection features
- API Validation for CRD changes
- Hardware Compatibility for BMC/hardware-specific features

### 5. Features Not to Be Tested

Explicitly list exclusions (5-8 items):
1. Non-applicable protocols or implementations
2. Vendor-specific extensions
3. Complete feature parity claims
4. Flow modifications outside scope
5. Related but out-of-scope functionality

### 6. Approach

#### Testing Strategy

**Manual Testing:** Functional validation, hardware compatibility, performance measurement, user workflow validation

**Automated Testing:** CI/CD integration, unit tests, integration tests with virtual BMC or real BMC

**Environments:**
- **Development:** Local clusters with virtual BMC (Sushy-tools for Redfish)
- **CI:** Automated test suites with mock/virtual infrastructure
- **Staging:** Real bare metal hardware (Dell, HPE, Supermicro if available)

**Test Execution:**
1. **Functional Validation** - Core feature functionality and acceptance criteria
2. **Platform Variations** - Vendor compatibility, performance, and configuration testing
3. **Integration & Regression** - Workflow integration and regression validation

### 7. Item Pass/Fail Criteria

Create a concise table:

| Test Item | Pass Criteria | Fail Criteria |
|-----------|---------------|---------------|
| *Item 1* | Brief success condition | Brief failure condition |
| *Item 2* | Brief success condition | Brief failure condition |

**Metal-specific criteria to consider:**
- BMC connectivity and authentication
- Hardware data population accuracy
- No unintended machine boots/reboots
- Operator reconciliation without resource leaks
- Error handling and recovery

### 8. Suspension Criteria and Resumption Requirements

#### Suspension Criteria
1. **Critical Infrastructure Failure:** Test environment unavailable
2. **Blocking Defects:** Feature causes critical failures (boots, state corruption, operator crashes)
3. **API Breaking Changes:** CRD/API changes require plan revision

#### Resumption Requirements
1. Infrastructure restored and validated
2. Blocking defects fixed and verified
3. API changes documented and plan updated

### 9. Test Deliverables

1. **Test Plan Document:** This IEEE 829-style test plan
2. **Test Case Coverage Mapping:** Test case IDs with requirement traceability (see Section 17)
3. **Test Results:** Pass/fail status with evidence and defect reports
4. **Performance Metrics:** Timing/performance data across hardware vendors (if applicable)
5. **Compatibility Matrix:** Hardware vendor/model results (if applicable)
6. **CI Automation:** Test scripts and CI configurations

### 10. Testing Tasks

Brief bullet list (6 items):
1. **Environment Setup** - Provision clusters, configure virtual/real BMC
2. **Test Case Development** - Author detailed specifications for all coverage categories
3. **Test Execution** - Execute functional, deployment, interoperability, performance, and regression suites
4. **Results Analysis** - Analyze results, categorize defects, compare vendor performance (if applicable)
5. **Defect Management** - File and track Jira issues
6. **CI/CD Integration** - Integrate automated tests into pipeline

### 11. Environmental Needs

#### Infrastructure Requirements

**Cluster Configurations:**
- OpenShift clusters with Metal3 operator and relevant CRDs
- Network connectivity to BMC endpoints (if applicable)

**Hardware Requirements:**
- Bare metal systems (Dell PowerEdge 14th gen+, HPE ProLiant Gen10+, Supermicro X11/X12 series if available) with Redfish 1.6+ (if hardware-dependent feature)
- Virtual BMC (Sushy-tools) for mock testing

**Network:**
- Isolated VLAN for BMC traffic (if applicable)
- Routing to BMC management network

### 12. Responsibilities

| Role | Testing Responsibilities |
|------|--------------------------|
| **QE Team** | Test planning, execution, analysis, defect reporting |
| **Development Team** | Unit tests, feature verification, defect fixes |
| **Release Engineering** | CI/CD integration, release criteria validation |
| **Product Management** | Acceptance criteria, scope approval |

### 13. Staffing and Training Needs

N/A

### 14. Schedule

| Milestone | Target |
|-----------|--------|
| **Test Plan Approval** | TBD |
| **Test Environment Ready** | TBD |
| **Functional Testing Complete** | TBD |
| **CI Integration Complete** | TBD |

### 15. Risks and Contingencies

| Risk | Mitigation Strategy |
|------|---------------------|
| **Hardware Availability** | Prioritize testing with real bare metal hardware |
| **BMC/Firmware Variance** | Test across vendors early; document vendor-specific issues |
| **Incomplete Hardware Data** | Document per-vendor field availability; accept partial parity (if applicable) |
| **Performance Variability** | Use configurable timeouts; test with simulated latency (if applicable) |
| **API Changes During Development** | Track changes via PRs; update plan as needed |

### 16. Approvals

This test plan requires approval from the following stakeholders:

- **QE Owner:** _[Name/Role]_ - Test execution and quality validation
- **Feature Owner:** _[Name/Role]_ - Requirements alignment and scope
- **Development Lead:** Dmitry Tantsur - Technical feasibility and implementation approach
- **Development Architect:** _[Name/Role]_ - Architecture and design review
- **Product Management:** Michal Zasepa - Business requirements
- **Release Engineering:** _[Name/Role]_ - Release readiness and CI/CD integration

**Approval Date:** TBD

### 17. Test Coverage Mapping

This section provides test coverage mapping with test case IDs, titles, and requirement traceability.

---

#### 17.1 Functional Validation

| Test Case ID | Title | Requirement Traceability | Coverage |
|--------------|-------|--------------------------|----------|
| TC-FUNC-01 | *First functional requirement test* | FR-01 | Complete |
| TC-FUNC-02 | *Second functional requirement test* | FR-02 | Complete |
| ... | ... | ... | ... |

*Generate test cases mapping each functional requirement from Section 4.*

---

#### 17.2 Testing and Validation

N/A - Covered by Functional Validation test cases above.

---

#### 17.3 Deployment/Topology Variations

**Note:** Metal features are typically topology-agnostic (work consistently across multi-node, compact, SNO).

**Default approach for topology-agnostic features:**
- Test on **multi-node bare metal cluster only** (representative validation)
- Include a note explaining the feature operates at a level independent of cluster topology

**For features with specific topology requirements or restrictions:**
- Test all relevant topologies (multi-node, compact, SNO)
- Document any topology-specific behavior or limitations

**Example (topology-agnostic feature):**

| Test Case ID | Title | Coverage |
|--------------|-------|----------|
| TC-DEPLOY-01 | Feature on multi-node bare metal cluster | Complete |

**Example (topology-dependent feature):**

| Test Case ID | Title | Coverage |
|--------------|-------|----------|
| TC-DEPLOY-01 | Feature on multi-node bare metal cluster | Complete |
| TC-DEPLOY-02 | Feature on compact 3-node cluster | Complete |
| TC-DEPLOY-03 | Feature on Single Node OpenShift (SNO) | Complete |

---

#### 17.4 Interoperability

| Test Case ID | Title | Requirement Traceability | Coverage |
|--------------|-------|--------------------------|----------|
| TC-INTEROP-01 | *Feature integration with existing workflows* | Interop requirement | Complete |
| ... | ... | ... | ... |

*Map interoperability requirements and workflow integration scenarios.*

---

#### 17.5 Upgrade/Rollback

**Determination criteria:** Check if the OCPSTRAT issue, linked PRs, or release contract documents a supported upgrade or rollback path.

- **Complete** - If upgrade/rollback path is documented: Provide test cases covering:
  - Version-skew scenarios (e.g., upgrading from version N to N+1)
  - Persisted-state scenarios (e.g., CRD changes, operator state migration)
  - Rollback path validation (if documented as supported)

- **N/A** - Only if:
  - No upgrade/rollback path is documented in the issue, PRs, or release contract
  - Feature is purely additive with no state persistence or version dependencies
  
**Note:** Do not assume "additive feature" automatically means N/A. Check for documented upgrade behavior first.

---

#### 17.6 Success Criteria

| Success Metric | Test Case ID | Pass Criteria | Coverage |
|----------------|--------------|---------------|----------|
| *Metric 1* | TC-FUNC-XX | Brief success condition | Complete |
| ... | ... | ... | ... |

*Map high-level success criteria to test cases.*

---

#### 17.7 Non-Functional Requirements

| NFR Category | Test Case ID | Title | Coverage |
|--------------|--------------|-------|----------|
| **Performance** | TC-NFR-PERF-01 | *Performance requirement 1* | Complete |
| **Performance** | TC-NFR-PERF-02 | *Performance requirement 2* | Complete |
| **Reliability** | TC-NFR-REL-01 | *Reliability requirement 1* | Complete |
| **Reliability** | TC-NFR-REL-02 | *Reliability requirement 2* | Complete |
| **Compatibility** | TC-NFR-COMPAT-01 | Dell hardware compatibility (if applicable) | Complete |
| **Compatibility** | TC-NFR-COMPAT-02 | HPE hardware compatibility (if applicable) | Complete |
| **Compatibility** | TC-NFR-COMPAT-03 | Supermicro hardware compatibility (if applicable) | Complete |
| **Security** | TC-NFR-SEC-01 | *Security requirement (e.g., credentials, TLS)* | Complete |
| **Usability** | TC-NFR-USE-01 | *Usability requirement (e.g., error messages, status)* | Complete |

*Include hardware compatibility tests only for hardware-dependent features. Adjust categories based on feature requirements.*

---

#### 17.8 Operational / Day-2

| Test Case ID | Title | Coverage |
|--------------|-------|----------|
| TC-OPS-01 | Failure troubleshooting workflow | Partial |
| TC-OPS-02 | Connectivity diagnostics (BMC if applicable) | Partial |
| TC-OPS-03 | Metrics exposure | Gap |
| TC-OPS-04 | Logging for failures | Partial |

---

#### 17.9 Negative Tests

| Test Case ID | Title | Coverage |
|--------------|-------|----------|
| TC-NEG-01 | *Out-of-scope boundary 1* | Complete |
| TC-NEG-02 | *Out-of-scope boundary 2* | Complete |
| ... | ... | ... |

*Map negative tests to out-of-scope items and error handling scenarios.*

---

#### 17.10 Regression Scenarios

| Test Case ID | Title | Coverage |
|--------------|-------|----------|
| TC-REG-01 | Existing functionality still works (baseline behavior) | Complete |
| TC-REG-02 | *Workflow integration after feature introduction* | Complete |
| TC-REG-03 | *State machine transitions unchanged* | Complete |
| TC-REG-04 | *Existing schema compatibility* | Complete |

*Verify feature introduction doesn't break existing Metal Platform functionality.*

---

### 18. Readiness Integration

- Link this test plan from the OCPSTRAT issue
- Store in Git repository: component repo under `docs/test-plans/` or `test-plans/` directory
- Derive QE work items from Testing Tasks (Section 10) and Test Coverage Mapping (Section 17) with traceability to test case IDs

---

## 19. Notes and Limitations

N/A - Unless specific implementation scope, relationship to parent features, or known limitations are documented in the OCPSTRAT issue or linked METAL tickets, this section remains N/A.

*If applicable, include:*
- **Implementation Scope:** What specific implementation this plan covers vs. broader feature vision
- **Relationship to Parent Features:** How this relates to OCPSTRAT parent or other Metal features
- **Known Limitations:** Documented constraints or future enhancements
- **Technology Dependencies:** Specific versions or configurations required

---

**Document Version:** 1.0  
**Last Updated:** *(Current date)*  
**Status:** Draft - Pending Approval

---

## Metal-Specific Guidelines

1. **Hardware Testing:** Always include real hardware testing for Dell and HPE. Include Supermicro if available. Virtual BMC alone is insufficient for hardware-dependent features.

2. **BMC Compatibility:** Test with DMTF-compliant Redfish implementations. Document vendor-specific quirks or limitations.

3. **No Payload Boot:** For inspection/discovery features, verify no unintended machine boots occur.

4. **Operator Reconciliation:** Verify operators handle failures gracefully and recover when dependencies restore.

5. **Hardcoded Stakeholders:**
   - Development Lead: Dmitry Tantsur
   - Product Management: Michal Zasepa
   - QE Owner, Feature Owner, Development Architect, Release Engineering: To be filled from Jira/project context

6. **Test Case Naming:** Use descriptive titles that include the component/feature being tested (e.g., "Fast inspection completes within 1 minute" not "Performance test 1").

7. **Coverage Column:** Mark as "Complete" when test case mapping is done, "Partial" when partially covered, "Gap" when not covered.

8. **Traceability:** Always map test cases back to functional requirements, user goals, or acceptance criteria IDs.

9. **Conciseness:** Keep explanatory text minimal. Use tables over prose. Remove verbose pass/fail criteria duplications.

10. **Avoid Redundancy:** Don't create duplicate test cases. If a scenario is covered by functional tests, don't repeat it in interoperability or regression unless it's genuinely a different test.

11. **Notes and Limitations:** Default to N/A unless the OCPSTRAT issue or linked METAL tickets document specific implementation scope boundaries, parent feature relationships, or known limitations that affect testing.
