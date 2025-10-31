---
name: Test Case Generator
description: Generate comprehensive test cases with DOCX export capability
---

# Test Case Generator Skill

This skill provides the implementation details for generating comprehensive test cases from feature descriptions and exporting them to multiple formats.

## When to Use This Skill

Use this skill when the `/testing:create-testcases` command needs to:
- Generate detailed test cases for a new feature
- Export test cases to DOCX format
- Apply priority or component filters
- Create professional test documentation

## Prerequisites

### For Markdown Output
- No additional dependencies required

### For DOCX Output
- Python 3.7 or higher
- `python-docx` library

Check Python version:
```bash
python3 --version
```

Check if python-docx is installed:
```bash
python3 -c "import docx; print('python-docx installed')" 2>/dev/null || echo "python-docx not installed"
```

Install python-docx if needed:
```bash
pip install python-docx
```

## Implementation Details

### DOCX Generation Script

**Location**: `plugins/testing/skills/testcase-generator/generate_docx.py`

**Purpose**: Converts markdown-formatted test cases into a professionally formatted Microsoft Word document.

**Usage**:
```bash
python3 plugins/testing/skills/testcase-generator/generate_docx.py \
  --input testcases-{feature-name}.md \
  --output testcases-{feature-name}.docx \
  --title "Test Cases: {Feature Name}"
```

**Parameters**:
- `--input` / `-i`: Path to input markdown file (required)
- `--output` / `-o`: Path to output DOCX file (required)
- `--title` / `-t`: Document title (required)

**What the Script Does**:

1. **Reads Markdown File**:
   - Parses markdown content line by line
   - Handles frontmatter (YAML between `---`)
   - Processes markdown elements

2. **Converts to DOCX**:
   - Headings (`#`, `##`, `###`) → Word Heading styles
   - Bold text (`**text**`) → Bold formatting
   - Code blocks (` ``` `) → Courier New font
   - Tables (`|...|`) → Formatted Word tables
   - Lists (`-`, `*`, `1.`) → Bullet and numbered lists
   - Horizontal rules (`---`) → Separator lines

3. **Applies Styling**:
   - Title: Calibri 24pt, Bold, Dark Blue
   - Headings: Calibri, Dark Blue
   - Normal text: Calibri 11pt
   - Code: Courier New 9pt
   - Tables: Light Grid Accent 1 style with blue header

4. **Creates Output**:
   - Saves to specified output path
   - Reports document statistics (pages, sections)

### Error Handling

**Missing python-docx**:
```
Error: python-docx library not found.
Install it with: pip install python-docx
```

**Solution**: Install the library
```bash
pip install python-docx
```

**Input file not found**:
```
Error: Input file not found: {path}
```

**Solution**: Verify the markdown file was created successfully before calling the DOCX generator

**Conversion errors**:
```
Error converting markdown to DOCX: {error message}
```

**Solution**: Check markdown formatting, ensure valid UTF-8 encoding

## Output Format

### Markdown Document Structure

```markdown
# Test Cases: {Feature Name}

**Generated**: {timestamp}
**Feature**: {feature_name}
**Component**: {component_names}
**Priority Filter**: {priority_filter}
**Total Test Cases**: {count}

---

## Table of Contents
...

## 1. Overview
Feature description and scope

## 2. Test Environment Requirements
Prerequisites, test data, dependencies

## 3. Test Cases

### 3.1 Functional Tests
TC-001: Test case title
**Priority**: High
**Component**: component-name
**Tags**: [Functional, Regression]
...

### 3.2 Regression Tests
...

### 3.3 Smoke Tests
...

### 3.4 Edge Cases
...

### 3.5 Security Tests
...

### 3.6 Performance Tests
...

## 4. Critical Test Cases Summary
Quick validation table

## 5. Test Execution Notes
Execution order, known issues, reporting

## Appendix
Test case statistics
```

### DOCX Document Features

- Professional formatting with styled headings
- Tables with blue headers
- Proper spacing and indentation
- Monospace font for code blocks
- Approximately 1 page per 40 paragraphs
- Section counting for navigation

## Examples

### Example 1: Basic DOCX Generation

**Input Markdown**: `testcases-user-auth.md`

**Command**:
```bash
python3 plugins/testing/skills/testcase-generator/generate_docx.py \
  --input testcases-user-auth.md \
  --output testcases-user-auth.docx \
  --title "Test Cases: User Authentication"
```

**Output**:
```
✓ DOCX document created: testcases-user-auth.docx
  Pages: Approximately 5
  Sections: 23
```

### Example 2: With Complex Feature Name

**Input**: Feature with special characters

**Command**:
```bash
python3 plugins/testing/skills/testcase-generator/generate_docx.py \
  --input "testcases-payment-processing-v2.md" \
  --output "testcases-payment-processing-v2.docx" \
  --title "Test Cases: Payment Processing v2.0"
```

## Tips

- **Always create markdown first**: Generate markdown output, then convert to DOCX
- **Validate markdown**: Ensure markdown is well-formed before conversion
- **Use descriptive titles**: DOCX title appears in the document header
- **Check dependencies**: Verify python-docx is installed before attempting conversion
- **Handle spaces**: Quote file paths with spaces
- **Verify output**: Check the generated DOCX opens correctly in Word or LibreOffice

## Integration with Main Command

The `/testing:create-testcases` command uses this skill in the following flow:

1. **Parse arguments**: Extract feature name, priority, component, format
2. **Generate test cases**: Create comprehensive test case content
3. **Write markdown**: Always create markdown file first
4. **If DOCX requested**:
   - Check python-docx availability
   - Call `generate_docx.py` script
   - Verify DOCX creation
   - Report both markdown and DOCX file locations

## Troubleshooting

### Issue: DOCX not generated

**Check**:
```bash
# Verify python-docx
python3 -c "import docx"

# Check file permissions
ls -la testcases-*.md

# Manually test script
python3 plugins/testing/skills/testcase-generator/generate_docx.py --help
```

### Issue: Formatting issues in DOCX

**Common causes**:
- Malformed markdown tables
- Unclosed code blocks
- Invalid UTF-8 characters

**Solution**: Review and fix markdown formatting

### Issue: Script not found

**Check working directory**:
```bash
pwd
ls -la plugins/testing/skills/testcase-generator/generate_docx.py
```

**Solution**: Use full path or ensure running from repository/directory root

## Version History

### v0.0.1
- Initial implementation
- Markdown to DOCX conversion
- Basic styling and formatting
- Table support
- Code block formatting
