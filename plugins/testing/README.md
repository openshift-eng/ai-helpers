# Testing Plugin

Comprehensive test case generation and QA automation tools for Claude Code.

## Overview

The Testing plugin provides powerful commands to automate the creation of detailed, professional test cases for any feature or functionality. It helps QA engineers, developers, and product teams quickly generate comprehensive test plans with proper categorization, priority tagging, and multiple output formats.

## Commands

### `/testing:generate-test-case-doc`

Generate comprehensive test cases for a feature with priority filtering and multiple output formats.

**Synopsis:**
```
/testing:generate-test-case-doc <feature_name> [--priority high|medium|low] [--component name] [--format markdown|docx]
```

**Description:**

Automatically generates detailed test cases including:
- **Functional Tests**: Core feature functionality and user workflows
- **Regression Tests**: Existing functionality validation
- **Smoke Tests**: Critical path quick checks
- **Edge Cases**: Boundary values and negative scenarios
- **Security Tests**: Authentication, authorization, and data privacy
- **Performance Tests**: Load, response time, and resource usage

Each test case includes:
- Title and unique ID
- Priority level (High/Medium/Low)
- Component/module tags
- Test type tags (Functional, Regression, Smoke, etc.)
- Detailed test steps
- Clear expected results
- Preconditions and test data
- Notes and related test cases

**Features:**
- 📋 **Comprehensive Coverage**: Automatically generates test cases across multiple categories
- 🎯 **Priority Filtering**: Generate only high-priority tests for critical path validation
- 🏷️ **Component Tagging**: Organize tests by module or component
- 📄 **Multiple Formats**: Output as Markdown or Microsoft Word (DOCX)
- ⚡ **Critical Test Summary**: Dedicated section for smoke and high-priority tests
- 📊 **Statistics**: Detailed breakdown by priority and test type

**Basic Usage:**

Generate all test cases for a feature:
```bash
/testing:generate-test-case-doc "User Authentication with OAuth2"
```

**Advanced Usage:**

High-priority test cases only, with component tagging, in DOCX format:
```bash
/testing:generate-test-case-doc "Payment Processing" --priority high --component payment,security --format docx
```

**Options:**

- `--priority <level>`: Filter by priority
  - Values: `high`, `medium`, `low`, `all` (default: all)
  - Example: `--priority high` for critical tests only

- `--component <name>`: Tag with component/module name(s)
  - Single: `--component auth`
  - Multiple: `--component auth,api,ui`

- `--format <type>`: Output format
  - Values: `markdown` (default), `docx`
  - Markdown: Version control friendly, text-based
  - DOCX: Professional formatting for stakeholders

**Output:**

Creates a file in the current directory:
- Markdown: `testcases-{feature-name}.md`
- DOCX: `testcases-{feature-name}.docx`

The document includes:
1. **Overview**: Feature description and scope
2. **Test Environment Requirements**: Prerequisites and dependencies
3. **Test Cases**: Organized by type (Functional, Regression, Smoke, etc.)
4. **Critical Test Cases Summary**: Quick validation checklist
5. **Test Execution Notes**: Execution order and reporting guidelines
6. **Appendix**: Test case statistics

**Examples:**

1. **Basic feature test cases**:
   ```bash
   /testing:generate-test-case-doc "Shopping Cart Updates"
   ```

2. **High-priority smoke tests**:
   ```bash
   /testing:generate-test-case-doc "API Gateway" --priority high
   ```

3. **Component-specific tests**:
   ```bash
   /testing:generate-test-case-doc "User Profile Management" --component profile,api
   ```

4. **Professional DOCX for stakeholders**:
   ```bash
   /testing:generate-test-case-doc "Payment Integration" --format docx
   ```

5. **Critical security tests**:
   ```bash
   /testing:generate-test-case-doc "OAuth2 Implementation" --priority high --component auth,security --format docx
   ```

## Installation

### From Marketplace

```bash
# Add the marketplace
/plugin marketplace add openshift-eng/ai-helpers

# Install the testing plugin
/plugin install testing@ai-helpers
```

### Manual Installation

```bash
# Clone the repository
git clone https://github.com/openshift-eng/ai-helpers.git

# Link to Claude Code plugins directory
ln -s $(pwd)/ai-helpers/plugins/testing ~/.claude/plugins/testing
```

## Prerequisites

### For Markdown Output (Default)
- No additional dependencies required
- Works out of the box

### For DOCX Output
- Python 3.7+
- `python-docx` library

Install dependencies:
```bash
pip install python-docx
```

Or using requirements file:
```bash
# Create requirements.txt
echo "python-docx>=0.8.11" > requirements.txt

# Install
pip install -r requirements.txt
```

## Use Cases

### For QA Engineers
- **New Feature Testing**: Quickly generate comprehensive test plans for new features
- **Regression Suites**: Build regression test suites for major releases
- **Critical Path Testing**: Generate smoke tests for quick validation

### For Developers
- **Feature Documentation**: Document testing requirements alongside code
- **Test Coverage**: Ensure comprehensive test coverage during development
- **PR Validation**: Create test cases for pull request validation

### For Product Teams
- **Acceptance Criteria**: Generate test cases from feature requirements
- **Stakeholder Review**: Create professional DOCX documents for review
- **Release Planning**: Build test plans for release validation

### For CI/CD Integration
- **Automated Documentation**: Generate test case documentation as part of CI
- **Version Control**: Maintain test cases in markdown format alongside code
- **Test Management**: Import generated test cases into test management tools

## Output Structure

### Markdown Format
```markdown
# Test Cases: Feature Name

**Generated**: 2025-01-15 10:30:00
**Feature**: Feature Name
**Component**: component-name
**Total Test Cases**: 25

---

## 1. Overview
Feature description and scope...

## 2. Test Environment Requirements
Prerequisites and dependencies...

## 3. Test Cases

### 3.1 Functional Tests
TC-001: Test Case Title
...

### 3.2 Regression Tests
TC-010: Test Case Title
...

### 3.3 Smoke Tests
TC-020: Test Case Title
...

## 4. Critical Test Cases Summary
Quick validation checklist...

## 5. Test Execution Notes
Execution order and reporting...

## Appendix
Test case statistics...
```

### DOCX Format
Professional Word document with:
- Styled headings and formatting
- Tables for test case summaries
- Proper spacing and structure
- Blue color scheme for headings
- Easy sharing with stakeholders

## Tips and Best Practices

### Priority Levels
- **High**: Critical functionality, blocking issues, smoke tests
  - Use for: Core features, security, data integrity
  - Execute first in testing cycles

- **Medium**: Important features, common scenarios
  - Use for: Standard workflows, integration testing
  - Execute after high-priority tests

- **Low**: Edge cases, optional features
  - Use for: Nice-to-have features, rare scenarios
  - Execute time permitting

### Component Organization
- Use consistent component names across projects
- Examples: `auth`, `api`, `ui`, `database`, `payment`, `security`
- Multiple components for cross-functional features
- Helps organize and filter test cases

### Format Selection
- **Use Markdown when**:
  - Storing test cases in version control
  - Collaborating with developers
  - Automating test case updates
  - Integrating with CI/CD

- **Use DOCX when**:
  - Sharing with non-technical stakeholders
  - Creating formal test plans
  - Presenting to management
  - Archiving test documentation

### Customization
Generated test cases should be reviewed and enhanced:
- Add specific test data values
- Update preconditions for your environment
- Add links to related documentation
- Include screenshots or diagrams
- Update expected results with exact values

### Integration with Test Management Tools
Generated test cases can be imported into:
- TestRail
- Zephyr
- qTest
- Azure Test Plans
- JIRA Test Management

Export format: Markdown or DOCX → Convert using tool-specific importers

## Troubleshooting

### DOCX Generation Fails

**Error**: `ImportError: No module named 'docx'`

**Solution**:
```bash
pip install python-docx
```

### Invalid Priority Value

**Error**: `Invalid priority filter`

**Solution**: Use one of: `high`, `medium`, `low`, `all`

### File Permission Denied

**Error**: `Permission denied: testcases-*.md`

**Solution**:
- Check write permissions in current directory
- Try saving to a different directory
- Verify disk space availability

### Empty Test Cases Generated

**Issue**: Very few or generic test cases created

**Solution**:
- Provide more context about the feature
- Include feature description or requirements
- Reference existing documentation or specs
- Manually add feature details to the prompt

## Contributing

Contributions welcome! To add new features or improve test case generation:

1. Fork the repository
2. Create a feature branch
3. Update the command or add new commands
4. Test thoroughly
5. Submit a pull request

## Support

- **Issues**: https://github.com/openshift-eng/ai-helpers/issues
- **Documentation**: https://github.com/openshift-eng/ai-helpers
- **Discussions**: https://github.com/openshift-eng/ai-helpers/discussions

## Related Commands

- `/utils:generate-test-plan` - Generate test plans from GitHub PRs
- `/jira:generate-test-plan` - Generate test plans from JIRA issues

## License

See repository LICENSE file for details.

## Version History

### v0.0.1 (2025-01-15)
- Initial release
- Feature-based test case generation
- Priority filtering
- Component tagging
- Markdown and DOCX output formats
- Critical test case summary
