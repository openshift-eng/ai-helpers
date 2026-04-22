---
description: Migrate React components from PatternFly 5 to PatternFly 6
argument-hint: "[file-path]"
skill: patternfly-migration
---

## Name
patternfly:migrate

## Synopsis
```
/patternfly:migrate [file-path]
```

## Description
The `patternfly:migrate` command analyzes and migrates React components from PatternFly v5 to PatternFly v6. It identifies breaking changes, deprecated components, prop renames, and structural updates required for v6 compatibility.

This command leverages AI analysis to:
- Detect PatternFly v5 patterns in the codebase
- Apply automated migrations for component renames, prop updates, and import path changes
- Identify manual updates needed for complex structural changes
- Provide clear explanations for each migration step
- Suggest testing strategies for migrated components

## Implementation
The command uses the `patternfly-migration` skill to:

1. **Analyze** the provided file or codebase for PatternFly v5 patterns
2. **Categorize** findings by migration type (imports, components, props, structure)
3. **Prioritize** changes: imports → component renames → prop changes → structural changes
4. **Apply** automated fixes with explanations
5. **Report** manual updates needed and testing recommendations

The migration follows the official PatternFly v6 migration guide and pf-codemods patterns.

## Migration Coverage

### Automated Migrations
- Component replacements (Text → Content, Chip → Label, etc.)
- Prop renames (Button.isActive → isClicked, FormGroup.labelIcon → labelHelp)
- Import path updates (deprecated components, charts, promoted components)
- Token updates (global tokens, border widths, font weights)
- Toolbar chip-to-label migrations
- Color prop updates (cyan → teal, gold → yellow)

### Manual Verification Required
- Markup changes (EmptyState, Masthead, Button icons, etc.)
- Deprecated components without direct replacements
- Component-specific tokens and CSS variables
- Test updates for DOM structure changes
- Accessibility and keyboard navigation

## Return Value
- **Migration report**: Analysis of changes with file:line references
- **Code changes**: Applied via Edit tool with clear descriptions
- **Manual checklist**: Items requiring manual verification
- **Testing recommendations**: Functional, visual, and accessibility tests

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
