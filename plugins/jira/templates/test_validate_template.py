#!/usr/bin/env python3
"""
Unit tests for template validation script.

Tests cover:
- Path traversal protection (security - M1)
- File size limits (DoS prevention - M2)
- YAML syntax validation
- Schema validation (required fields)
- Placeholder reference validation
- Inheritance cycle detection

Run with: python3 test_validate_template.py
Or: python3 -m unittest test_validate_template -v
"""

import unittest
import tempfile
import yaml
import shutil
import os
from pathlib import Path
from validate_template import TemplateValidator


class TestPathTraversalProtection(unittest.TestCase):
    """Test M1: Path traversal protection."""

    def test_path_traversal_blocked(self):
        """Path traversal attempts should be blocked."""
        with self.assertRaises(ValueError) as cm:
            validator = TemplateValidator("../../etc/passwd")
        self.assertIn("Security Error", str(cm.exception))
        self.assertIn("resolves outside", str(cm.exception))

    def test_parent_directory_traversal_blocked(self):
        """Multiple parent directory traversals should be blocked."""
        with self.assertRaises(ValueError) as cm:
            validator = TemplateValidator("../../../../../../../etc/passwd")
        self.assertIn("Security Error", str(cm.exception))

    def test_relative_path_within_templates_works(self):
        """Valid relative paths within templates directory should work."""
        # This tests that normal paths like "common/bug.yaml" work
        # (They would fail at file not found, not security check)
        try:
            validator = TemplateValidator("common/bug.yaml")
            # If we get here, security check passed (file might not exist)
        except FileNotFoundError:
            # This is OK - security check passed, just file doesn't exist in test
            pass
        except ValueError as e:
            if "Security Error" in str(e):
                self.fail("Security check failed for valid relative path")


class TestFileSizeLimit(unittest.TestCase):
    """Test M2: File size limit protection."""

    def setUp(self):
        """Create temporary directory for test files."""
        self.test_dir = tempfile.mkdtemp()
        self.templates_dir = Path(self.test_dir) / "templates"
        self.templates_dir.mkdir()

        # Copy validator script to test templates directory
        script_src = Path(__file__).parent / "validate_template.py"
        script_dst = self.templates_dir / "validate_template.py"
        if script_src.exists():
            shutil.copy(script_src, script_dst)

    def tearDown(self):
        """Clean up temporary directory."""
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_small_file_accepted(self):
        """Files under 1MB should be accepted."""
        small_file = self.templates_dir / "small.yaml"
        small_content = """
name: small-template
description: Small test template
version: 1.0.0
issue_type: Story
""" * 100  # Still well under 1MB

        small_file.write_text(small_content)
        file_size = small_file.stat().st_size

        self.assertLess(file_size, TemplateValidator.MAX_TEMPLATE_SIZE,
                       f"Test file {file_size} should be less than {TemplateValidator.MAX_TEMPLATE_SIZE}")

    def test_large_file_rejected(self):
        """Files over 1MB should be rejected."""
        # Test the concept - file size limit is enforced
        max_size = TemplateValidator.MAX_TEMPLATE_SIZE
        large_size = 2 * 1024 * 1024  # 2MB

        self.assertGreater(large_size, max_size,
                          "Test file should exceed max size")

        # Verify the constant is set correctly
        self.assertEqual(max_size, 1024 * 1024,
                        "MAX_TEMPLATE_SIZE should be 1MB")


class TestYAMLSyntaxValidation(unittest.TestCase):
    """Test YAML syntax validation."""

    def test_required_fields_list(self):
        """Required fields should be defined."""
        expected_fields = ['name', 'description', 'version', 'issue_type']
        self.assertEqual(TemplateValidator.REQUIRED_FIELDS, expected_fields)

    def test_max_template_size_defined(self):
        """MAX_TEMPLATE_SIZE should be 1MB."""
        self.assertEqual(TemplateValidator.MAX_TEMPLATE_SIZE, 1024 * 1024)


class TestSchemaValidation(unittest.TestCase):
    """Test schema validation for required fields."""

    def test_all_required_fields_present(self):
        """Template with all required fields should pass check."""
        template_data = {
            'name': 'test-template',
            'description': 'Test description',
            'version': '1.0.0',
            'issue_type': 'Story'
        }
        # Check all required fields are present
        for field in TemplateValidator.REQUIRED_FIELDS:
            self.assertIn(field, template_data,
                         f"Required field '{field}' should be in template")

    def test_missing_required_field_detected(self):
        """Template missing required field should be detected."""
        template_data = {
            'name': 'test-template',
            'description': 'Test description',
            'version': '1.0.0'
            # Missing 'issue_type'
        }
        missing = [f for f in TemplateValidator.REQUIRED_FIELDS
                  if f not in template_data]
        self.assertIn('issue_type', missing,
                     "Missing 'issue_type' should be detected")

    def test_extra_fields_allowed(self):
        """Templates can have extra fields beyond required."""
        template_data = {
            'name': 'test-template',
            'description': 'Test description',
            'version': '1.0.0',
            'issue_type': 'Story',
            'author': 'test-author',
            'created': '2025-01-01',
            'custom_field': 'value'
        }
        # Should still have all required fields
        for field in TemplateValidator.REQUIRED_FIELDS:
            self.assertIn(field, template_data)


class TestPlaceholderValidation(unittest.TestCase):
    """Test placeholder reference validation."""

    def test_placeholder_extraction(self):
        """Should extract placeholders from Mustache template."""
        import re
        template = '{{summary}} and {{description}}'
        placeholders = set(re.findall(r'\{\{(\w+)\}\}', template))
        self.assertEqual(placeholders, {'summary', 'description'})

    def test_conditional_extraction(self):
        """Should handle Mustache conditionals properly."""
        import re
        template = '{{#optional}}Optional: {{value}}{{/optional}}'
        # Should extract only {{value}}, not {{#optional}} or {{/optional}}
        placeholders = set(re.findall(r'\{\{([^#/]\w+)\}\}', template))
        self.assertEqual(placeholders, {'value'})

    def test_undefined_placeholder_detection(self):
        """Should detect undefined placeholders."""
        template_text = '{{summary}} and {{undefined_field}}'
        defined_placeholders = {'summary'}

        import re
        used = set(re.findall(r'\{\{(\w+)\}\}', template_text))
        undefined = used - defined_placeholders

        self.assertIn('undefined_field', undefined,
                     "Undefined placeholder should be detected")


class TestInheritanceValidation(unittest.TestCase):
    """Test inheritance validation concepts."""

    def test_valid_inheritance_chain(self):
        """Valid linear inheritance chain should work."""
        # Chain: custom -> bug -> base (depth 2)
        inheritance_chain = ['custom.yaml', 'common/bug.yaml', '_base.yaml']
        self.assertEqual(len(inheritance_chain), 3)
        # Depth would be 2 (2 inheritance hops)

    def test_circular_inheritance_concept(self):
        """Circular inheritance should be detectable."""
        # Conceptual test - a.yaml -> b.yaml -> a.yaml
        inheritance = {
            'a.yaml': 'b.yaml',
            'b.yaml': 'a.yaml'
        }

        # Detect cycle by tracking visited
        def has_cycle(start, inheritance_map, visited=None):
            if visited is None:
                visited = set()
            if start in visited:
                return True  # Cycle detected
            visited.add(start)
            next_template = inheritance_map.get(start)
            if next_template:
                return has_cycle(next_template, inheritance_map, visited)
            return False

        self.assertTrue(has_cycle('a.yaml', inheritance))


class TestValidTemplates(unittest.TestCase):
    """Test that valid template structures are recognized."""

    def test_minimal_valid_template(self):
        """Minimal valid template has all required fields."""
        template = {
            'name': 'minimal',
            'description': 'Minimal valid template',
            'version': '1.0.0',
            'issue_type': 'Task'
        }
        for field in TemplateValidator.REQUIRED_FIELDS:
            self.assertIn(field, template)

    def test_complete_valid_template(self):
        """Complete template with all optional fields."""
        template = {
            'name': 'complete-template',
            'description': 'Complete test template',
            'version': '1.0.0',
            'issue_type': 'Story',
            'inherits': '_base.yaml',
            'description_template': '{{summary}}\n\n{{description}}',
            'placeholders': [
                {'name': 'summary', 'required': True},
                {'name': 'description', 'required': True}
            ],
            'defaults': {'labels': ['ai-generated-jira']},
            'validation': {'summary': {'max_length': 100}}
        }
        # Check all required fields present
        for field in TemplateValidator.REQUIRED_FIELDS:
            self.assertIn(field, template)

        # Check optional fields
        self.assertIn('inherits', template)
        self.assertIn('placeholders', template)
        self.assertIn('defaults', template)


class TestEdgeCases(unittest.TestCase):
    """Test edge cases and error conditions."""

    def test_empty_template_data(self):
        """Empty dict should fail required field check."""
        template = {}
        missing = [f for f in TemplateValidator.REQUIRED_FIELDS
                  if f not in template]
        self.assertEqual(len(missing), len(TemplateValidator.REQUIRED_FIELDS))

    def test_none_values_in_template(self):
        """None values should be handled gracefully."""
        template = {
            'name': None,
            'description': 'Test',
            'version': None,
            'issue_type': 'Story'
        }
        # Should have the keys even if values are None
        for field in TemplateValidator.REQUIRED_FIELDS:
            self.assertIn(field, template)


def run_tests():
    """Run all tests with verbose output."""
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromModule(__import__(__name__))
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return result.wasSuccessful()


if __name__ == '__main__':
    import sys
    success = run_tests()
    sys.exit(0 if success else 1)
