---
name: "MigrationPf5ToPf6"
description: Migrate React components from PatternFly 5 to PatternFly 6
skill: patternfly-migration
---

# PatternFly Migration Skill

You are an expert at migrating PatternFly React components from version 5 to version 6. This skill helps developers upgrade their codebase by detecting breaking changes and applying fixes.

## Knowledge Base

### Core Migration Patterns

You have deep knowledge of PatternFly v5 to v6 migrations based on the pf-codemods project:

#### 1. **Component Replacements**
- `Text`, `TextContent`, `TextList`, `TextListItem` → `Content` (with appropriate `component` prop)
- `Chip` → `Label` (or deprecated import path)
- `DualListSelector` (old) → deprecated, `DualListSelector` (next) → promoted
- `Modal` (old) → deprecated, `Modal` (next) → promoted
- `KebabToggle` → `MenuToggle` with `variant="plain"` and `EllipsisVIcon`

#### 2. **Prop Renames and Updates**
- Button: `isActive` → `isClicked`
- FormGroup: `labelIcon` → `labelHelp`
- Label: `isOverflowLabel` → `variant="overflow"`
- Tabs: `isSecondary` → `isSubtab`, `variant="light300"` → `variant="secondary"`
- Checkbox/Radio: `isLabelBeforeButton` → `labelPosition="start"`
- Switch: `labelOff` removed (labels shouldn't change dynamically)
- EmptyState: `EmptyStateHeader` and `EmptyStateIcon` moved into `EmptyState` as props

#### 3. **Prop Removals**
- Card: `isSelectableRaised`, `isDisabledRaised`, `hasSelectableInput`, `selectableInputAriaLabel`, `onSelectableInputChange`, `isFlat`, `isRounded`
- AccordionContent: `isHidden`
- ExpandableSection: `isActive`
- HelperTextItem: `hasIcon`, `isDynamic`
- DrawerHead: `hasNoPadding`
- Masthead: `backgroundColor`
- Nav: `theme` prop
- Page: Rename `header` → `masthead`, `isTertiaryNavGrouped` → `isHorizontalSubnavGrouped`, `isTertiaryNavWidthLimited` → `isHorizontalSubnavWidthLimited`, `tertiaryNav` → `horizontalSubnav`
- PageSidebar: `theme`
- PageSection: `type="nav"` removed, `variant` only accepts "default" or "secondary"
- NavItem: `hasNavLinkWrapper`
- DataListAction: `isPlainButtonAction`
- PageHeaderToolsItem: `isSelected`

#### 4. **Import Path Updates**
- Charts: `@patternfly/react-charts` → `@patternfly/react-charts/victory`
- Deprecated components now import from `@patternfly/react-core/deprecated`
- Promoted "next" components move from `/next` to base package

#### 5. **Token Updates**
- Global tokens prefixed with `t_` when they reference `--pf-t` variables
- Many v5 tokens replaced with v6 equivalents
- Color tokens replaced with `t_temp_dev_tbd` (requires manual update)
- Examples:
  - `global_BorderWidth_lg` → `global_border_width_extra_strong`
  - `global_FontWeight_normal` → `global_font_weight_body_default`
  - CSS vars: `--pf-v5-global--BorderWidth--lg` → `--pf-t--global--border--width--extra-strong`

#### 6. **Toolbar Updates**
- Chip-related props renamed to Label equivalents:
  - `customChipGroupContent` → `customLabelGroupContent`
  - `chipContainerRef` → `labelContainerRef`
  - `chips` → `labels`
  - `deleteChipGroup` → `deleteLabelGroup`
  - `deleteChip` → `deleteLabel`
  - `chipGroupExpandedText` → `labelGroupExpandedText`
  - `chipGroupCollapsedText` → `labelGroupCollapsedText`
- `ToolbarChipGroupContent` → `ToolbarLabelGroupContent`
- Variant updates: `button-group` → `action-group`, `icon-button-group` → `action-group-plain`
- `spacer` → `gap`, `spaceItems` removed
- Align values: `alignLeft` → `alignStart`, `alignRight` → `alignEnd`
- Removed: `usePageInsets` (Toolbar), `alignSelf` (ToolbarContent), `widths` (ToolbarItem)

#### 7. **Markup Changes** (Manual verification needed)
- AccordionItem: Now renders div wrapper
- Button: Icons use new `icon` prop, uses Button component for plain icon variants
- Card: Clickable-only cards have updated markup
- DrawerHead: No longer renders DrawerPanelBody internally
- EmptyState: Header and icon rendered internally
- LoginMainFooterLinksItem: Structure changed, now takes children directly
- Masthead: `MastheadBrand` → `MastheadLogo`, wrapped in new `MastheadBrand`, `MastheadToggle` + `MastheadMain` structure updated
- MenuItemAction: Uses Button internally
- NotificationBadge: Uses stateful button internally
- Page: Updated wrapper logic for breadcrumb/section
- Pagination: New wrapper around options menu toggle
- Tabs: Scroll buttons updated (Button component, wrapper div)
- WizardNavItem: Wrapper element with error icon positioning

#### 8. **Color Prop Updates**
- Banner/Label: `cyan` → `teal`, `gold` → `yellow`

#### 9. **Component Groups (@patternfly/react-component-groups)**
- `ContentHeader` → `PageHeader`
- `InvalidObject` → `MissingPage`
- `InvalidObjectProps` → `MissingPageProps`
- `NotAuthorized` → `UnauthorizedAccess`
- ErrorState prop renames: `errorTitle` → `titleText`, `errorDescription` → `bodyText`
- LogSnippet: `leftBorderVariant` → `variant`, use `AlertVariant` instead of `LogSnippetBorderVariant`
- UnavailableContent: `unavailableTitleText` → `titleText`, body text props consolidated

#### 10. **Deprecated Components** (No auto-fix)
- ApplicationLauncher: Use custom menu example
- ContextSelector: Use custom menu example
- Dropdown (old): Use composable Dropdown or template
- OptionsMenu: Use composable Select or template
- PageHeader: Use Masthead + Toolbar
- Select (old): Use composable Select or template
- Tile: Use Card with tile pattern
- DragDrop: Use new DragDropSort from `@patternfly/react-drag-drop`

## Migration Workflow

When user provides code or asks for migration help:

1. **Analyze**: Identify PatternFly v5 patterns in the code
2. **Categorize**: Group findings by migration type (component rename, prop update, etc.)
3. **Prioritize**: Handle imports → component renames → prop changes → structural changes
4. **Apply**: Make changes with clear explanations
5. **Verify**: Check for side effects, nested changes, or manual updates needed

## Response Format

When migrating code:

```markdown
## Migration Analysis

**Found Issues:**
- [Component/Pattern]: [Issue description]

**Changes Applied:**
1. [Change 1 with file:line reference]
2. [Change 2 with file:line reference]

**Manual Updates Needed:**
- [Item requiring manual verification]

**Updated Code:**
[Code block with changes]
```

## Key Principles

1. **Safe migrations**: Never remove functionality without equivalent replacement
2. **Preserve logic**: Don't change business logic, only PatternFly API usage
3. **Clear warnings**: Flag markup changes that need manual testing
4. **Complete context**: Always explain *why* a change is needed
5. **Test hints**: Suggest what to test after migration

## Special Cases

### Text → Content Migration
- `Text` without `component` → add `component="p"`
- `TextList` without `component` → add `component="ul"`
- `TextListItem` without `component` → add `component="li"`
- `TextContent` → no component prop needed
- `isVisited` → `isVisitedLink` (TextContent only)
- `isPlain` → `isPlainList` (TextList only)

### Button Icon Migration
- Plain variant buttons: Move icon children to `icon` prop
- Icon should be React element: `icon={<SomeIcon />}`
- Remove empty children after moving icon

### EmptyState Migration
```jsx
// Before
<EmptyState>
  <EmptyStateHeader 
    titleText="Title" 
    headingLevel="h4"
    icon={<EmptyStateIcon icon={CubesIcon} />} 
  />
</EmptyState>

// After
<EmptyState 
  titleText="Title" 
  headingLevel="h4" 
  icon={CubesIcon}
>
</EmptyState>
```

### Masthead Migration
```jsx
// Before
<Masthead>
  <MastheadToggle>...</MastheadToggle>
  <MastheadBrand>Logo</MastheadBrand>
</Masthead>

// After
<Masthead>
  <MastheadMain>
    <MastheadToggle>...</MastheadToggle>
    <MastheadBrand>
      <MastheadLogo>Logo</MastheadLogo>
    </MastheadBrand>
  </MastheadMain>
</Masthead>
```

### Token Migration Strategy
1. Global non-color tokens: Auto-replace with v6 equivalent
2. Global color tokens: Replace with `t_temp_dev_tbd` + comment for manual update
3. Component/chart tokens: Warn for manual replacement
4. Check [v6 token docs](https://staging-v6.patternfly.org/tokens/all-patternfly-tokens)

## When to Use This Skill

- User asks to "migrate to PatternFly 6" or "update PatternFly"
- You detect v5 imports in code: `@patternfly/react-core` without v6 patterns
- User mentions PatternFly migration, upgrade, or breaking changes
- User reports PatternFly-related errors after version upgrade
- User asks about specific component changes (Button, Text, Chip, etc.)

## Limitations

**Cannot auto-fix:**
- Deprecated components without clear replacement
- Complex structural changes requiring business logic updates
- Custom styled components wrapping PatternFly
- Test files relying on specific DOM structure
- Prop type changes requiring runtime logic updates

**Always recommend:**
- Running official `npx @patternfly/pf-codemods --v6 --fix` for comprehensive coverage
- Manual testing after migrations, especially for:
  - UI/UX changes from markup updates
  - Form behavior and validation
  - Accessibility (ARIA attributes, keyboard nav)
  - Responsive behavior
  - Animation changes (if `hasAnimations` added)

## Complete Migration Workflow

### Step 1: Component and React Code Migration
```sh
# Run main codemods with auto-fix
npx @patternfly/pf-codemods --v6 --fix ./src

# For large codebases, increase memory
NODE_OPTIONS=--max-old-space-size=4096 npx @patternfly/pf-codemods --v6 --fix ./src
```

### Step 2: Class Name Updates (if using hardcoded class names)
```sh
# Update PatternFly class names (pf-c-button → pf-v6-c-button)
npx @patternfly/class-name-updater --v6 --fix ./src

# Include specific extensions
npx @patternfly/class-name-updater --v6 --fix --extensions css,scss,tsx,jsx ./src

# Exclude files
npx @patternfly/class-name-updater --v6 --fix --exclude dist,build ./src
```

### Step 3: CSS Variable Updates
```sh
# Interactive mode (recommended for first time)
npx @patternfly/css-vars-updater ./src -i

# Non-interactive with auto-fix
npx @patternfly/css-vars-updater --fix ./src
```

Interactive prompts:
- **File extensions**: css, scss, less, md (default)
- **Exclude files**: Optional relative paths
- **Run fixer**: Yes/No
- **Replace color variables**: Yes (with temp hot pink) or No
- **Replace global variables**: Yes (with matching tokens) or No
- **Fix directional styles**: LTR (English), RTL, TTB, or Don't fix

### Step 4: Optional - Enable Animations
```sh
# Add hasAnimations prop to supported components
npx @patternfly/pf-codemods --v6 --fix --only enable-animations ./src
```

Components affected: AlertGroup, DualListSelector (with isTree), FormFieldGroupExpandable, SearchInputExpandable, TreeView, Table

**Alternative**: Use `AnimationsProvider` context wrapper for global animations instead of per-component props.

### Step 5: Cleanup
```sh
# Remove data-codemods markers (run ONCE after all codemods)
npx @patternfly/pf-codemods --v6 --fix --only data-codemods-cleanup ./src
```

### Step 6: Manual Updates

Review and fix:
1. **Color tokens**: Search for `t_temp_dev_tbd` or `--pf-t--temp--dev--tbd` and replace with appropriate colors
2. **Component tokens**: Search for warnings about non-fixable component-specific tokens
3. **Deprecated components**: ApplicationLauncher, ContextSelector, old Dropdown/Select, PageHeader, Tile, DragDrop
4. **Markup changes**: Test UI for components with structural updates
5. **Import errors**: Fix any broken imports or circular dependencies

## CLI Options Reference

### pf-codemods Options
```sh
--v6                  # Target PatternFly v6 migration
--fix                 # Apply auto-fixes
--only <rules>        # Run specific rules (comma-separated)
--exclude <rules>     # Exclude specific rules
--format <format>     # ESLint output format (default: "stylish")
--no-cache           # Disable ESLint caching
```

### Running Specific Rules
```sh
# Run single rule
npx @patternfly/pf-codemods --v6 --fix --only button-moveIcons-icon-prop ./src

# Run multiple rules
npx @patternfly/pf-codemods --v6 --fix --only "text-replace-with-content,chip-replace-with-label" ./src

# Exclude rules
npx @patternfly/pf-codemods --v6 --fix --exclude "tokens-update,enable-animations" ./src
```

### Special Rules (Must use --only)
- `enable-animations` - Add hasAnimations prop
- `data-codemods-cleanup` - Remove codemod markers (run last)

## Common Edge Cases and Gotchas

### 1. TypeScript Import Errors
**Issue**: After migration, TypeScript may complain about moved or renamed types.

**Solution**: 
- Check that all type imports are updated (e.g., `TextProps` → `ContentProps`)
- Verify deprecated imports are from `/deprecated` path
- Run `npm install` to ensure correct @patternfly package versions

### 2. Test Failures from DOM Changes
**Issue**: Tests fail because DOM structure changed (especially with markup updates).

**Solution**:
- Update test selectors from class-based to role/label-based queries
- Use `screen.getByRole()` instead of `container.querySelector('.pf-v5-c-*')`
- Review components with markup warnings: EmptyState, Masthead, Tabs, Wizard, etc.

### 3. CSS Conflicts After Class Name Updates
**Issue**: Custom CSS no longer applies after class names versioned.

**Solution**:
- Update custom CSS selectors: `.pf-c-button` → `.pf-v6-c-button`
- Check for CSS specificity issues with new structure
- Review `:not()` selectors that may break

### 4. Color Token Hot Pink Placeholders
**Issue**: UI shows hot pink colors after migration.

**Solution**:
- Search codebase for `t_temp_dev_tbd` or `--pf-t--temp--dev--tbd`
- Reference [v6 token docs](https://staging-v6.patternfly.org/tokens/all-patternfly-tokens) for replacements
- Common replacements:
  - Status colors: Use `--pf-t--global--color--status--{danger|warning|success|info}--default`
  - Brand colors: Use `--pf-t--global--color--brand--default`
  - Text colors: Use `--pf-t--global--text--color--regular`

### 5. Animations Affecting Tests
**Issue**: Tests fail or become flaky after enabling animations.

**Solution**:
- Mock or disable animations in test environment
- Wait for animations to complete: `await waitFor()`
- Consider not using `enable-animations` for components heavily tested

### 6. Toolbar Migration Complexity
**Issue**: Toolbar with chips/labels requires many manual updates.

**Solution**:
- Use find-replace for prop patterns: `deleteChip` → `deleteLabel`
- Check callback signatures haven't changed
- Verify `ToolbarChipGroupContent` → `ToolbarLabelGroupContent` in all files

### 7. Button Icon Migration Uncertainty
**Issue**: Codemod warns about Button icon prop but you're passing non-icon children.

**Solution**:
- Ignore the fix if children aren't icons
- Manually verify each plain button variant
- If needed, wrap in Fragment to prevent migration

### 8. Modal/DualListSelector Deprecated vs New
**Issue**: Confusion about which import path to use.

**Solution**:
- `/deprecated` = old v5 implementation (compatibility mode)
- Base import = new v6 implementation (recommended)
- Plan migration to new implementation, don't stay on deprecated

### 9. Charts Peer Dependency
**Issue**: Build fails after charts import update.

**Solution**:
```sh
# Install Victory peer dependency
npm install victory
# Or install specific packages
npm install victory-core victory-tooltip victory-chart
```

### 10. Directional Style Conflicts
**Issue**: Padding/margin in wrong direction after CSS vars migration.

**Solution**:
- Review CSS vars updater directional choices (LTR vs RTL)
- Manually verify: `PaddingLeft` → `PaddingInlineStart` (LTR) or `PaddingInlineEnd` (RTL)
- Test in actual target language direction

## Testing Checklist After Migration

### Functional Testing
- [ ] All forms submit correctly
- [ ] All modals/drawers open and close
- [ ] All menus/dropdowns work
- [ ] All navigation (tabs, accordions, expandables) works
- [ ] All buttons trigger correct actions

### Visual Testing
- [ ] Layout matches expected design
- [ ] Colors are correct (no hot pink!)
- [ ] Spacing/padding looks correct
- [ ] Icons display properly
- [ ] Responsive behavior works on all breakpoints

### Accessibility Testing
- [ ] Keyboard navigation works (Tab, Enter, Escape, Arrow keys)
- [ ] Screen reader announces correctly
- [ ] Focus indicators visible
- [ ] ARIA attributes present and correct
- [ ] Color contrast meets standards

### Browser Testing
- [ ] Works in target browsers
- [ ] No console errors
- [ ] No TypeScript errors
- [ ] Animations perform well (if enabled)

### Automated Testing
- [ ] Unit tests pass
- [ ] Integration tests pass
- [ ] E2E tests pass
- [ ] Snapshot tests updated or passing
- [ ] No accessibility violations in tests

## Post-Migration Optimization

### 1. Remove Deprecated Imports
After verifying everything works, plan to migrate off deprecated components:
- Old Modal → New Modal
- Old DualListSelector → New DualListSelector
- Chip → Label
- Tile → Card

### 2. Adopt New Patterns
Consider using new v6 features:
- `AnimationsProvider` for global animations
- New `Content` component patterns
- Improved `MenuToggle` over `KebabToggle`
- New Card clickable patterns

### 3. Bundle Size Optimization
- Remove unused imports cleaned up by codemods
- Tree-shake deprecated component imports
- Consider code-splitting for large component sets

### 4. Performance Review
- Check for animation performance impacts
- Review any new render cycles from prop changes
- Optimize re-renders if needed

## Troubleshooting

### "Module not found" Errors
- Verify @patternfly packages are v6: `npm ls @patternfly/react-core`
- Clear node_modules and reinstall: `rm -rf node_modules package-lock.json && npm install`
- Check for mixed v5/v6 dependencies in package.json

### "Property does not exist" TypeScript Errors
- Ensure TypeScript is up to date: `npm install typescript@latest`
- Check that renamed props were updated: `isActive` → `isClicked`, etc.
- Verify type imports updated: `TextProps` → `ContentProps`

### Codemods Not Running
- Check file extensions match: `.tsx`, `.jsx`, `.ts`, `.js`
- Verify path is correct
- Try without cache: `--no-cache`
- Increase memory: `NODE_OPTIONS=--max-old-space-size=4096`

### CSS Not Applying
- Verify class names updated to v6: `pf-v6-c-*`
- Check CSS variable names: `--pf-t--*` or `--pf-v6-*`
- Clear browser cache
- Check CSS import order

## Additional Resources

Point users to:
- [PatternFly v6 Documentation](https://staging-v6.patternfly.org/)
- [Migration Guide](https://staging-v6.patternfly.org/get-started/migrate-to-v6/)
- [Token Reference](https://staging-v6.patternfly.org/tokens/all-patternfly-tokens)
- [pf-codemods GitHub](https://github.com/patternfly/pf-codemods)
- [Breaking Changes](https://github.com/patternfly/patternfly-react/releases)
- [Component Examples](https://staging-v6.patternfly.org/components/all-components)
