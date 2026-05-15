---
description: Migrate PatternFly v5 to v6 (React components, CSS classes, tokens)
argument-hint: "[file-path]"
skill: pf-react-migration
---

## Name
patternfly:migrate

## Synopsis
```
/patternfly:migrate [file-path]
```

## Description
The `patternfly:migrate` command migrates PatternFly v5 to v6 across React components, CSS classes, and design tokens. It scans for legacy patterns, applies fixes, and identifies items requiring manual updates.

This command provides:
- Automated detection of v5 patterns (components, CSS classes, tokens)
- Actionable scan commands using ripgrep for remaining issues
- Integration guidance for official @patternfly codemods
- Clear output with file:line references and confidence levels

## Implementation
The command uses the `pf-react-migration` skill to:

1. **Scan** for PatternFly v5 patterns using ripgrep commands
2. **Categorize** findings: React code, CSS classes, tokens, deprecated components
3. **Guide** codemod usage: pf-codemods, class-name-updater, css-vars-updater
4. **Apply** manual fixes for non-automatable changes
5. **Report** with confidence levels and testing recommendations

Follows the concise, actionable pattern of the pf-class-migration-scanner skill.

## Migration Scope

### React Components & Props
- Component replacements: Text/TextContent → Content, Chip → Label, KebabToggle → MenuToggle
- Prop updates: isActive → isClicked, labelIcon → labelHelp
- Import paths: Charts /victory, deprecated → /deprecated
- Toolbar chip → label prop renames

### CSS Classes & Tokens
- Legacy classes: pf-v5-*, pf-v4-*, pf-c-*, pf-u-*, pf-l-*
- Legacy tokens: --pf-v6-*, --pf-global-* → --pf-t--* (semantic)
- Color tokens requiring manual updates

### Manual Verification Required
- Markup changes (EmptyState, Masthead, Button icons)
- Deprecated components (ApplicationLauncher, old Dropdown/Select, PageHeader, Tile)
- UI testing and accessibility

## Return Value
- **Scan results**: File paths, current patterns, PF6 replacements
- **Confidence levels**: high/medium/low for each finding
- **Code changes**: Applied fixes with explanations (Why + How to apply)
- **Manual updates**: Items requiring manual verification with testing guidance

## Examples

1. **Migrate a single component file**:
   ```
   /patternfly:migrate src/components/Dashboard.tsx
   ```
   Analyzes and migrates PatternFly components in Dashboard.tsx

2. **Migrate current working directory**:
   ```
   /patternfly:migrate
   ```
   Scans and migrates PatternFly v5 patterns in all files from the current directory

3. **Analyze before migrating**:
   ```
   /patternfly:migrate src/components --dry-run
   ```
   Shows migration plan without applying changes (if user wants to review first)

## Arguments
- `$1`: (Optional) File path or directory to migrate. If not provided, analyzes the current context or prompts for clarification.

## Related Commands
After running migrations, consider:
- Running the official codemods: `npx @patternfly/pf-codemods --v6 --fix ./src`
- Updating CSS class names: `npx @patternfly/class-name-updater --v6 --fix ./src`
- Updating CSS variables: `npx @patternfly/css-vars-updater --fix ./src`
- Running tests to verify functionality

## Notes
- This command complements but does not replace the official `@patternfly/pf-codemods` tool
- Use AI analysis for complex cases and one-off migrations
- Use official codemods for comprehensive codebase-wide migrations
- Always test migrated components, especially for markup changes
- Review color token replacements (watch for `t_temp_dev_tbd` placeholders)
