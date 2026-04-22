# PatternFly Plugin

A Claude Code plugin for migrating and working with PatternFly React components.

## Overview

PatternFly is Red Hat's open source design system for enterprise product experiences. This plugin helps developers migrate from PatternFly v5 to v6 and understand breaking changes in the component library.

## Commands

### `/patternfly:migrate`

Migrate React components from PatternFly 5 to PatternFly 6.

**Usage:**
```bash
/patternfly:migrate [file-path]
```

**Examples:**
```bash
# Migrate a specific file
/patternfly:migrate src/components/Dashboard.tsx

# Migrate current working directory
/patternfly:migrate
```

**What it does:**
- Analyzes code for PatternFly v5 patterns
- Applies automated migrations for component renames, prop updates, and import changes
- Identifies manual updates needed for structural changes
- Provides testing recommendations

## Skills

### `patternfly-migration`

Expert knowledge for migrating PatternFly React components from v5 to v6.

**Coverage includes:**
- Component replacements (Text → Content, Chip → Label, etc.)
- Prop renames and removals
- Import path updates
- Token migrations
- Toolbar updates
- Markup changes
- Color prop updates
- Deprecated component guidance

## Installation

This plugin is part of the `ai-helpers` repository and is automatically available when the repository is loaded.

## Related Tools

The plugin complements these official PatternFly migration tools:

- **[@patternfly/pf-codemods](https://github.com/patternfly/pf-codemods)** - Automated code transformations
- **@patternfly/class-name-updater** - CSS class name updates
- **@patternfly/css-vars-updater** - CSS variable migrations

Use this plugin for:
- AI-assisted analysis of complex migration scenarios
- One-off component migrations
- Understanding breaking changes
- Migration planning and strategy

Use official codemods for:
- Comprehensive codebase-wide migrations
- Batch processing of many files
- Standardized transformations

## Resources

- [PatternFly v6 Documentation](https://staging-v6.patternfly.org/)
- [Migration Guide](https://staging-v6.patternfly.org/get-started/migrate-to-v6/)
- [Token Reference](https://staging-v6.patternfly.org/tokens/all-patternfly-tokens)
- [Component Examples](https://staging-v6.patternfly.org/components/all-components)

## Contributing

See the main [CLAUDE.md](../../CLAUDE.md) for contribution guidelines.

When adding new commands or skills:
1. Bump version in `.claude-plugin/plugin.json`
2. Run `make lint` to validate
3. Run `make update` to sync marketplace.json
