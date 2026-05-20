# PatternFly Plugin

A Claude Code plugin for migrating and working with PatternFly React components.

## Overview

PatternFly is Red Hat's open source design system for enterprise product experiences. This plugin helps developers migrate from PatternFly v5 to v6 and implement modern glass theme (glassmorphism) effects in React applications.

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

### `pf-react-migration`

Migrate PatternFly React components, CSS classes, and tokens from v5 to v6.

**Coverage includes:**
- React component and prop migrations (Text → Content, Chip → Label, prop renames)
- CSS class migrations (pf-v5-* → pf-v6-*, legacy classes)
- Token migrations (--pf-global-* → --pf-t--*)
- Import path updates and deprecated component guidance
- Automated codemod integration
- Actionable scan commands for finding migration issues

### `pf-glass-theme`

Enable PatternFly 6 glass theme (glassmorphism) for React applications.

**Features:**
- Add `.pf-v6-theme-glass` class to enable glass effects
- Global or component-level glass theme support
- Optional runtime theme toggle component
- Dark mode compatibility (`.pf-v6-theme-glass.pf-v6-theme-dark`)
- Glass token usage examples (backdrop blur, transparency)
- Template components for glass UI patterns

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

- [PatternFly v6 Documentation](https://www.patternfly.org/)
- [Migration Guide](https://www.patternfly.org/get-started/upgrade/)
- [Token Reference](https://www.patternfly.org/tokens/all-patternfly-tokens)
- [Component Examples](https://www.patternfly.org/components/all-components)

## Contributing

See the main [CLAUDE.md](../../CLAUDE.md) for contribution guidelines.

When adding new commands or skills:
1. Bump version in `.claude-plugin/plugin.json`
2. Run `make lint` to validate
3. Run `make update` to sync marketplace.json
