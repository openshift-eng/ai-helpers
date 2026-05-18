---
name: pf-glass-theme
description: Enable PatternFly 6 glass theme (glassmorphism with backdrop blur and transparency)
---

# PatternFly Glass Theme

Enable the PatternFly 6 glass theme for React applications using `.pf-v6-theme-glass` class and glass tokens.

## Step 1: Determine Theme Scope

Ask the user:
- **Global glass theme**: Apply to entire app (add class to `<html>` or root element)
- **Component-level glass**: Apply to specific components only
- **Toggle support**: Include runtime theme switcher
- **Theme variant**: Default PatternFly glass OR Red Hat branded glass (`.pf-v6-theme-redhat`)
- **Console plugin**: For OpenShift console plugins, the console already manages `.pf-v6-theme-dark`

Default to global if not specified.

## Step 2: Find and Update Root Element

### For Global Glass Theme

**RECOMMENDED APPROACH**: Use the custom hook pattern for proper cleanup.

1. **Copy** the `useGlassTheme` hook from `scripts/useGlassTheme.ts` to `src/hooks/useGlassTheme.ts`

2. **Integrate** in your root component or page components:
   ```tsx
   import { useGlassTheme } from './hooks/useGlassTheme';
   
   export const MyPage: React.FC = () => {
     // Default PatternFly glass
     useGlassTheme();
     
     // OR Red Hat branded glass
     useGlassTheme({ variant: 'redhat' });
     
     return <div>...</div>;
   };
   ```

**ALTERNATIVE**: If HTML modification is preferred:
1. **Find** the HTML template or root render file:
   - Try: `public/index.html`, `index.html`, `src/index.html`

2. **Read** the file

3. **Check** if `pf-v6-theme-glass` class already exists on `<html>` or root element

4. **Edit** to add the class:
   ```html
   <!-- Default glass -->
   <html class="pf-v6-theme-glass">
   
   <!-- OR Red Hat branded glass -->
   <html class="pf-v6-theme-redhat pf-v6-theme-glass">
   ```

### For Component-Level Glass

Guide the user to add the class to specific component wrappers:
```tsx
<div className="pf-v6-theme-glass">
  {/* Glass-themed components */}
</div>
```

## Step 3: Optional - Add Theme Switcher

If user wants toggle support, create a theme switcher component.

1. **Copy** template from `scripts/GlassThemeToggle.tsx` (if available) OR create inline:

```tsx
import React from 'react';
import { Switch } from '@patternfly/react-core';

export const GlassThemeToggle: React.FC = () => {
  const [isGlassEnabled, setIsGlassEnabled] = React.useState(() =>
    document.documentElement.classList.contains('pf-v6-theme-glass')
  );

  const handleToggle = (_event: React.FormEvent<HTMLInputElement>, checked: boolean) => {
    setIsGlassEnabled(checked);
    if (checked) {
      document.documentElement.classList.add('pf-v6-theme-glass');
    } else {
      document.documentElement.classList.remove('pf-v6-theme-glass');
    }
  };

  return (
    <Switch
      id="glass-theme-toggle"
      label="Glass theme"
      isChecked={isGlassEnabled}
      onChange={handleToggle}
    />
  );
};
```

2. **Write** to `src/components/GlassThemeToggle.tsx`

3. Guide user to add `<GlassThemeToggle />` in their app layout/settings

## Step 4: Dark Mode Support (IMPORTANT)

**CRITICAL WARNING**: The glass theme hook should NEVER manage `.pf-v6-theme-dark` class.

### For OpenShift Console Plugins:
- The console ALREADY manages `.pf-v6-theme-dark` based on user preferences
- Your glass theme hook should ONLY add `.pf-v6-theme-glass` (and optionally `.pf-v6-theme-redhat`)
- The combination happens automatically:
  - Light: `.pf-v6-theme-glass` (or `.pf-v6-theme-redhat.pf-v6-theme-glass`)
  - Dark: `.pf-v6-theme-glass.pf-v6-theme-dark` (console adds the dark class)

### For Standalone Apps:
If your app manages its own dark mode:
```tsx
// Your existing dark mode logic
if (isDarkMode) {
  document.documentElement.classList.add('pf-v6-theme-dark');
} else {
  document.documentElement.classList.remove('pf-v6-theme-dark');
}

// Glass theme hook runs separately
useGlassTheme();
```

Glass theme combines with dark mode: `.pf-v6-theme-glass.pf-v6-theme-dark`

## Step 5: Make Glass Effects Visible

**IMPORTANT**: Glass effects are only visible when there's layered content behind them.

### Option A: Add Enhanced CSS (Recommended)
1. **Copy** `scripts/glass-theme-enhanced.css` to `src/styles/`
2. **Import** in your page components:
   ```tsx
   import './styles/glass-theme-enhanced.css';
   ```
3. This adds:
   - Subtle background gradients (Red Hat brand colors)
   - Optional visual indicator badge
   - Card hover effects

### Option B: Custom Background
Add your own background gradient/image to make glass visible.

**Why this is needed**: Glass effect requires something behind it to blur. Without background content, glass appears identical to solid surfaces.

## Step 6: Verify Glass Token Usage

Remind user that glass theme uses these tokens:
- `--pf-t--global--background--color--glass--primary--default`
- `--pf-t--global--background--color--glass--floating--default`
- `--pf-t--global--background--filter--glass--blur--primary` (12.5px when active)
- `--pf-t--global--background--opacity--glass--primary` (80% when active)

Components using these tokens will automatically get glassmorphism effects when the theme is enabled.

## Glass Token Reference

When `.pf-v6-theme-glass` is applied:
- Background opacity: 100% → 80%
- Backdrop blur: 0px → 12.5px
- Works with contexts: `primary`, `floating`

## Output Format

Confirm with the user:
- ✅ Glass theme class added to [location]
- ✅ Scope: [global/component-level/with-toggle]
- ✅ Dark mode: [enabled/disabled]
- ✅ Theme switcher: [added/not-added]

Tell the user:
- Glass effects activate on components using `--pf-t--global--background--color--glass--*` tokens
- To use glass on custom components, apply the glass background tokens
- Glass theme can be combined with dark mode (`.pf-v6-theme-glass.pf-v6-theme-dark`)

## Common Pitfalls

### 1. **Managing Dark Mode Incorrectly**
❌ DON'T add/remove `.pf-v6-theme-dark` in your glass theme hook
✅ DO let the console or app's theme system manage dark mode

### 2. **Hardcoded Backgrounds**
❌ DON'T use hardcoded backgrounds like `background: '#1e1e1e'` - they block glass effects
✅ DO remove hardcoded backgrounds and let PatternFly tokens work

### 3. **Glass Effect Not Visible**
Problem: Glass looks like solid backgrounds
Solution:
- Add background gradients (use enhanced CSS template)
- Ensure layered content exists
- Try dark mode (effect often more visible)
- Check browser supports `backdrop-filter`

### 4. **Inconsistent Glass Across Pages**
Problem: Some pages have glass, some don't
Solution:
- Use glass hook in ALL page components
- OR add glass class to `<html>` globally
- Ensure enhanced CSS is imported consistently

### 5. **No Cleanup on Unmount**
❌ DON'T forget cleanup when using inline `useEffect`
✅ DO use the `useGlassTheme` hook which handles cleanup

### 6. **Browser Compatibility**
Glass theme requires `backdrop-filter` support:
- ✅ Chrome/Edge 76+
- ✅ Safari 9+
- ✅ Firefox 103+
- ❌ Older browsers (graceful degradation to solid backgrounds)

## Notes

- Always use Read tool before Edit tool
- Use Edit tool (not Write) for modifying existing files
- Check for existing theme classes to avoid duplicates
- Glass theme requires PatternFly 6 CSS to be loaded
- Glass tokens are defined in `tokens-glass.scss` and `tokens-local.scss`
- **Prefer the custom hook pattern over inline useEffect** for better cleanup and reusability
