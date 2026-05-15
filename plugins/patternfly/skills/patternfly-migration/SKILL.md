---
name: pf-react-migration
description: Migrate PatternFly React components from v5 to v6. Scans for component renames, prop updates, and import changes.
---

# PatternFly React Migration

Migrate PatternFly React components from version 5 to version 6.

Query the PatternFly MCP server when migration recommendations are ambiguous to verify the latest supported component patterns and tokens.

## Migration scope

### React Components and Props
- Component renames: `Text`/`TextContent`/`TextList` → `Content`, `Chip` → `Label`, `KebabToggle` → `MenuToggle`
- Prop updates: `isActive` → `isClicked`, `labelIcon` → `labelHelp`, `isOverflowLabel` → `variant="overflow"`
- Import paths: Charts `/victory`, deprecated → `/deprecated`, promoted "next" components to base
- Toolbar: Chip props → Label props (`deleteChip` → `deleteLabel`)
- Color props: `cyan` → `teal`, `gold` → `yellow`

### CSS Classes and Tokens
- Legacy versioned classes: `pf-v5-*`, `pf-v4-*`
- Unversioned legacy classes: `pf-c-*`, `pf-u-*`, `pf-l-*`
- Legacy token patterns: `--pf-v6-*`, `--pf-global-*` → `--pf-t--*` (semantic tokens)

### Deprecated Components
- ApplicationLauncher, ContextSelector, old Dropdown/Select, OptionsMenu, PageHeader, Tile, DragDrop

## Scan commands

```bash
# Find v5 imports and component usage
rg "@patternfly/react-core(?!/deprecated)" --type tsx --type jsx

# Find legacy CSS classes
rg "pf-v5-|pf-v4-|pf-c-|pf-u-|pf-l-" src

# Find legacy CSS tokens
rg "--pf-v6-|--pf-global-" src

# Find deprecated component imports
rg "from.*@patternfly/react-core/deprecated" --type tsx --type jsx

# Find specific component patterns to migrate
rg "<(Text|TextContent|TextList|Chip|KebabToggle)\b" --type tsx --type jsx
```

## Migration workflow

1. **Run automated codemods first**:
   ```bash
   npx @patternfly/pf-codemods --v6 --fix ./src
   npx @patternfly/class-name-updater --v6 --fix ./src
   npx @patternfly/css-vars-updater --fix ./src
   ```

2. **Scan for remaining issues** using commands above

3. **Apply manual fixes** for:
   - Markup changes (EmptyState, Masthead, Button icons)
   - Deprecated components requiring custom replacements
   - Color tokens (`t_temp_dev_tbd` → semantic tokens)

4. **Test** UI behavior, accessibility, and responsive design

## Replacement guidance

- **Prefer** PatternFly React component props over CSS classes
- **Use** semantic tokens (`--pf-t--*`) over legacy tokens
- **Consult** [v6 token docs](https://www.patternfly.org/tokens/all-patternfly-tokens) for color replacements
- **Run** official codemods for comprehensive coverage before manual updates

## Output format

For each finding include:

- file path and line number
- current component/class/token
- recommended PF6 replacement
- confidence (`high`, `medium`, `low`)
- whether manual testing required

**Why:** Explain breaking change or deprecation reason

**How to apply:** Provide code example if replacement is non-obvious
