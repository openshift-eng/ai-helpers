#!/usr/bin/env python3
"""
Template Validation Script for Jira Templates

Validates template YAML files for:
- YAML syntax
- Required fields
- Placeholder references in description_template
- Inheritance cycles

Usage:
    python validate_template.py <template-file>
    python validate_template.py ocpedge/spike.yaml
"""

import sys
import yaml
import re
from pathlib import Path
from typing import Dict, List, Set, Tuple


class TemplateValidator:
    """Validates Jira template files."""

    REQUIRED_FIELDS = ['name', 'description', 'version', 'issue_type']
    MAX_TEMPLATE_SIZE = 1024 * 1024  # 1MB - prevents DoS via large YAML files
    MAX_INHERITANCE_DEPTH = 10  # Prevents stack overflow from deep inheritance chains

    def __init__(self, template_path: str):
        # Find templates root (directory containing this script)
        self.templates_root = Path(__file__).parent.resolve()

        # Resolve template path relative to templates root
        # If already absolute, use as-is; otherwise treat as relative
        template_path_obj = Path(template_path)
        if template_path_obj.is_absolute():
            self.template_path = template_path_obj.resolve()
        else:
            self.template_path = (self.templates_root / template_path).resolve()

        # Prevent path traversal attacks - ensure path stays within templates directory
        try:
            self.template_path.relative_to(self.templates_root)
        except ValueError:
            raise ValueError(
                f"Security Error: Template path '{template_path}' resolves outside "
                f"templates directory. Resolved to: {self.template_path}, "
                f"Templates root: {self.templates_root}"
            )

        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.template_data: Dict = {}

    def validate(self) -> bool:
        """Run all validations. Returns True if valid, False otherwise."""
        print(f"Validating: {self.template_path}\n")

        # Check 1: YAML syntax
        if not self._validate_yaml_syntax():
            return False

        # Check 2: Schema validation (required fields)
        self._validate_schema()

        # Check 3: Placeholder references
        self._validate_placeholder_references()

        # Check 4: Inheritance cycles
        self._validate_inheritance()

        # Check 5: Redundant overrides
        self._validate_redundant_overrides()

        # Report results
        self._print_results()

        return len(self.errors) == 0

    def _validate_yaml_syntax(self) -> bool:
        """Validate YAML syntax."""
        try:
            # Check file size before parsing to prevent DoS attacks
            file_size = self.template_path.stat().st_size
            if file_size > self.MAX_TEMPLATE_SIZE:
                self.errors.append(
                    f"Template file too large: {file_size:,} bytes "
                    f"(max {self.MAX_TEMPLATE_SIZE:,} bytes / {self.MAX_TEMPLATE_SIZE // 1024}KB)"
                )
                print(f"✗ File size exceeds limit")
                print(f"  Size: {file_size:,} bytes, Limit: {self.MAX_TEMPLATE_SIZE:,} bytes")
                return False

            with open(self.template_path, 'r') as f:
                self.template_data = yaml.safe_load(f)
            print("✓ YAML syntax valid")
            return True
        except yaml.YAMLError as e:
            error_msg = str(e)
            # Extract line and column if available
            if hasattr(e, 'problem_mark'):
                mark = e.problem_mark
                error_msg = f"Line {mark.line + 1}, Column {mark.column + 1}: {e.problem}"
            self.errors.append(f"YAML Parse Error: {error_msg}")
            print(f"✗ YAML syntax invalid")
            print(f"  {error_msg}")
            return False
        except FileNotFoundError:
            self.errors.append(f"File not found: {self.template_path}")
            print(f"✗ File not found: {self.template_path}")
            return False

    def _validate_schema(self):
        """Validate required fields and basic schema."""
        # Get all fields from template and inheritance chain
        all_fields = self._get_all_fields()

        missing_fields = []
        for field in self.REQUIRED_FIELDS:
            if field not in all_fields:
                missing_fields.append(field)

        if missing_fields:
            self.errors.append(f"Missing required fields: {', '.join(missing_fields)}")
            print(f"✗ Schema validation failed")
            print(f"  Missing required fields: {', '.join(missing_fields)}")
        else:
            info = [
                f"name: {all_fields.get('name')}",
                f"issue_type: {all_fields.get('issue_type')}",
            ]
            if 'placeholders' in self.template_data:
                info.append(f"{len(self.template_data['placeholders'])} placeholders defined")

            print("✓ Schema validation passed")
            for line in info:
                print(f"  - {line}")

    def _validate_placeholder_references(self):
        """Validate that all placeholders referenced in description_template are defined."""
        description_template = self.template_data.get('description_template', '')
        if not description_template:
            print("⚠ No description_template found (skipping placeholder check)")
            return

        # Extract placeholder references using regex: {{placeholder_name}}
        # Matches {{name}}, {{#section}}, {{/section}}
        pattern = r'\{\{[#/]?(\w+)\}\}'
        referenced_placeholders = set(re.findall(pattern, description_template))

        # Get defined placeholders (including from inheritance chain)
        defined_placeholders = self._get_all_placeholders()

        # Find undefined references
        undefined = referenced_placeholders - defined_placeholders

        if undefined:
            self.errors.append(f"Undefined placeholders in description_template: {', '.join(sorted(undefined))}")
            print(f"✗ Placeholder reference error")
            print(f"  Template uses: {', '.join(sorted(undefined))}")
            print(f"  But placeholders not defined")
        else:
            if referenced_placeholders:
                print("✓ Placeholder references valid")
                print(f"  Uses: {', '.join(sorted(referenced_placeholders))}")
                print(f"  All defined")
            else:
                print("⚠ No placeholder references found in description_template")

    def _get_all_placeholders(self) -> Set[str]:
        """Get all placeholder names including from parent templates."""
        placeholders = set()

        # Get placeholders from current template
        for placeholder in self.template_data.get('placeholders', []):
            if 'name' in placeholder:
                placeholders.add(placeholder['name'])
            # Also collect placeholder_name (special output placeholders)
            if 'placeholder_name' in placeholder:
                placeholders.add(placeholder['placeholder_name'])

        # Get placeholders from parent templates
        current = self.template_path
        depth = 0
        while current:
            depth += 1
            if depth > self.MAX_INHERITANCE_DEPTH:
                # Silently stop traversal (error will be caught in _validate_inheritance)
                break

            try:
                with open(current, 'r') as f:
                    data = yaml.safe_load(f)
                    inherits = data.get('inherits')
                    if inherits:
                        # Resolve path from templates root
                        parent_path = (self.templates_root / inherits).resolve()
                        if parent_path.exists():
                            # Load parent and get its placeholders
                            with open(parent_path, 'r') as pf:
                                parent_data = yaml.safe_load(pf)
                                for placeholder in parent_data.get('placeholders', []):
                                    if 'name' in placeholder:
                                        placeholders.add(placeholder['name'])
                                    # Also collect placeholder_name from parents
                                    if 'placeholder_name' in placeholder:
                                        placeholders.add(placeholder['placeholder_name'])
                            current = parent_path
                        else:
                            break
                    else:
                        break
            except Exception:
                break

        return placeholders

    def _get_all_fields(self) -> Dict:
        """Get all fields from template and inheritance chain (child overrides parent)."""
        # Start with empty merged template
        merged = {}

        # Walk inheritance chain from root to current (so child overrides work)
        chain = []
        current = self.template_path

        # Build the chain
        while current:
            if len(chain) > self.MAX_INHERITANCE_DEPTH:
                # Silently stop traversal (error will be caught in _validate_inheritance)
                break

            chain.append(current)
            try:
                with open(current, 'r') as f:
                    data = yaml.safe_load(f)
                    inherits = data.get('inherits')
                    if inherits:
                        parent_path = (self.templates_root / inherits).resolve()
                        if parent_path.exists():
                            current = parent_path
                        else:
                            break
                    else:
                        break
            except Exception:
                break

        # Reverse chain so we apply from parent to child
        chain.reverse()

        # Merge fields from parent to child
        for template_path in chain:
            try:
                with open(template_path, 'r') as f:
                    data = yaml.safe_load(f)
                    # Merge all top-level fields (child overrides parent)
                    for key, value in data.items():
                        if key != 'inherits':  # Skip inherits field
                            merged[key] = value
            except Exception:
                continue

        return merged

    def _validate_inheritance(self):
        """Validate inheritance chain for cycles."""
        if 'inherits' not in self.template_data:
            print("✓ No inheritance (standalone template)")
            return

        visited: Set[Path] = set()
        chain: List[Path] = []
        current = self.template_path

        while current:
            if current in visited:
                # Cycle detected
                cycle_start = chain.index(current)
                cycle = chain[cycle_start:] + [current]
                cycle_str = ' → '.join([p.relative_to(self.templates_root) for p in cycle])
                self.errors.append(f"Circular inheritance detected: {cycle_str}")
                print(f"✗ Inheritance cycle detected")
                print(f"  {cycle_str}")
                return

            visited.add(current)
            chain.append(current)

            # Check inheritance depth to prevent stack overflow
            if len(chain) > self.MAX_INHERITANCE_DEPTH:
                chain_str = ' → '.join([str(p.relative_to(self.templates_root)) for p in chain])
                self.errors.append(
                    f"Inheritance chain too deep: {len(chain)} levels "
                    f"(max {self.MAX_INHERITANCE_DEPTH})"
                )
                print(f"✗ Inheritance depth limit exceeded")
                print(f"  Depth: {len(chain)}, Limit: {self.MAX_INHERITANCE_DEPTH}")
                print(f"  Chain: {chain_str}")
                return

            # Try to load parent
            try:
                with open(current, 'r') as f:
                    data = yaml.safe_load(f)
                    inherits = data.get('inherits')
                    if inherits:
                        # Resolve path from templates root
                        parent_path = (self.templates_root / inherits).resolve()
                        if not parent_path.exists():
                            self.warnings.append(f"Parent template not found: {inherits}")
                            print(f"⚠ Parent template not found: {inherits}")
                            break
                        current = parent_path
                    else:
                        break
            except Exception as e:
                self.warnings.append(f"Could not load parent template: {e}")
                break

        if chain and not self.errors:
            chain_str = ' → '.join([str(p.relative_to(self.templates_root)) for p in chain])
            print("✓ Inheritance chain valid")
            print(f"  {chain_str}")

    def _validate_redundant_overrides(self):
        """Check for redundant field overrides that match parent values."""
        if 'inherits' not in self.template_data:
            print("✓ No inheritance (no redundancy check needed)")
            return

        inherits = self.template_data['inherits']
        parent_path = (self.templates_root / inherits).resolve()

        if not parent_path.exists():
            # Already warned in inheritance validation
            return

        try:
            with open(parent_path, 'r') as f:
                parent_data = yaml.safe_load(f)
        except Exception:
            # Can't read parent, skip redundancy check
            return

        redundancies = []

        # Check placeholders for redundant overrides
        child_placeholders = {p['name']: p for p in self.template_data.get('placeholders', [])}
        parent_placeholders = {p['name']: p for p in parent_data.get('placeholders', [])}

        for name, child_ph in child_placeholders.items():
            if name in parent_placeholders:
                parent_ph = parent_placeholders[name]
                # Check each field for exact match
                redundant_fields = []
                for field, child_value in child_ph.items():
                    if field == 'name':
                        continue  # Name is required for merging
                    parent_value = parent_ph.get(field)
                    if parent_value is not None and child_value == parent_value:
                        redundant_fields.append(field)

                if redundant_fields:
                    redundancies.append(
                        f"Placeholder '{name}' redundantly sets: {', '.join(redundant_fields)} "
                        f"(same as parent '{parent_path.name}')"
                    )

        # Check top-level fields for redundant overrides
        # Skip certain fields that are expected to override
        skip_fields = {'inherits', 'name', 'description', 'version', 'created',
                       'author', 'source', 'placeholders'}

        for field, child_value in self.template_data.items():
            if field in skip_fields:
                continue
            parent_value = parent_data.get(field)
            if parent_value is not None and child_value == parent_value:
                redundancies.append(
                    f"Field '{field}' redundantly set to same value as parent '{parent_path.name}'"
                )

        if redundancies:
            for redundancy in redundancies:
                self.warnings.append(redundancy)
            print(f"⚠ Found {len(redundancies)} redundant override(s)")
            print(f"  Consider removing fields that match parent values")
        else:
            print("✓ No redundant overrides found")

    def _print_results(self):
        """Print validation summary."""
        print()
        if not self.errors and not self.warnings:
            print("✅ Template is valid and ready to use.")
            return

        if self.errors:
            print(f"❌ Template has {len(self.errors)} error(s):")
            for error in self.errors:
                print(f"   - {error}")

        if self.warnings:
            print(f"⚠️  Template has {len(self.warnings)} warning(s):")
            for warning in self.warnings:
                print(f"   - {warning}")

        if self.errors:
            print("\nTemplate validation failed. Fix errors before using this template.")
        else:
            print("\nTemplate validation passed with warnings.")


def main():
    if len(sys.argv) != 2:
        print("Usage: python validate_template.py <template-file>")
        print("Example: python validate_template.py ocpedge/spike.yaml")
        sys.exit(1)

    template_file = sys.argv[1]
    validator = TemplateValidator(template_file)
    is_valid = validator.validate()

    sys.exit(0 if is_valid else 1)


if __name__ == '__main__':
    main()
