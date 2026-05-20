# PatternFly Glass Theme Skill

Enable glassmorphism (glass theme) effects in PatternFly 6 React applications.

## Overview

This skill helps implement the PatternFly 6 glass theme, which provides modern glassmorphism UI effects using backdrop blur and transparency. Glass theme uses PatternFly's built-in glass design tokens and the `.pf-v6-theme-glass` theme class.

## What It Does

1. **Adds glass theme class** to your app (global or component-level)
2. **Provides theme toggle component** for runtime switching (optional)
3. **Supports dark mode** combination (`.pf-v6-theme-glass.pf-v6-theme-dark`)
4. **Includes example components** using glass tokens

## Glass Theme Tokens

When `.pf-v6-theme-glass` is applied, these tokens activate:

- `--pf-t--global--background--color--glass--primary--default`
- `--pf-t--global--background--color--glass--floating--default`
- `--pf-t--global--background--filter--glass--blur--primary` (0px → 12.5px)
- `--pf-t--global--background--filter--glass--blur--floating`
- `--pf-t--global--background--opacity--glass--primary` (100% → 80%)

## Template Files

### `scripts/useGlassTheme.ts` ⭐ **Recommended**
Custom React hook for glass theme management with proper cleanup. Supports both default PatternFly glass and Red Hat branded glass variants.

### `scripts/glass-theme-enhanced.css`
Enhanced CSS for making glass effects visible:
- Subtle background gradients (Red Hat brand colors)
- Visual indicator badge
- Card hover effects
- Supports both light and dark modes

### `scripts/GlassThemeToggle.tsx`
React component with a PatternFly Switch to toggle glass theme on/off at runtime.

### `scripts/glass-example.tsx`
Example components demonstrating glass token usage:
- `GlassCard` - Basic card with glass background
- `GlassFloatingCard` - Elevated card with glass effects for modals/popovers

## Usage Examples

### Global Glass Theme (Recommended: Use Hook)

**Best Practice - Custom Hook:**
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

**Alternative - HTML:**
```html
<!-- Default glass -->
<html class="pf-v6-theme-glass">

<!-- Red Hat branded glass -->
<html class="pf-v6-theme-redhat pf-v6-theme-glass">
```

### Component-Level Glass Theme

Wrap specific components:
```tsx
<div className="pf-v6-theme-glass">
  {/* Glass-themed content */}
</div>
```

### Glass + Dark Mode

Combine theme classes:
```html
<html class="pf-v6-theme-glass pf-v6-theme-dark">
```

### Custom Glass Component

Use glass tokens directly:
```tsx
<Card style={{
  backgroundColor: 'var(--pf-t--global--background--color--glass--primary--default)',
  backdropFilter: 'var(--pf-t--global--background--filter--glass--blur--primary)',
}}>
  {/* Content */}
</Card>
```

## OpenShift Console Plugins

For console plugins, use the hook pattern:
```tsx
import { useGlassTheme } from './hooks/useGlassTheme';
import './styles/glass-theme-enhanced.css';

export const MyConsolePage: React.FC = () => {
  // Use Red Hat variant for console plugins
  useGlassTheme({ variant: 'redhat' });
  
  return <div>...</div>;
};
```

**IMPORTANT**: The console manages `.pf-v6-theme-dark` automatically. Your hook should ONLY manage glass classes, not dark/light theme.

## Making Glass Effects Visible

Glass effects require layered content. Import the enhanced CSS:
```tsx
import './styles/glass-theme-enhanced.css';
```

This adds:
- ✅ Subtle background gradients
- ✅ Visual indicator badge
- ✅ Card hover effects

## Common Pitfalls

❌ **Don't** manage `.pf-v6-theme-dark` in your glass hook  
❌ **Don't** use hardcoded backgrounds (blocks glass effect)  
❌ **Don't** forget to cleanup classes on unmount  
✅ **Do** use the `useGlassTheme` hook  
✅ **Do** remove hardcoded backgrounds  
✅ **Do** add background gradients for visibility  

## Requirements

- PatternFly 6 CSS loaded
- `@patternfly/react-core` v6 for React components
- Modern browser with backdrop-filter support (Chrome 76+, Safari 9+, Firefox 103+)

## Related Skills

- `pf-token-auditor` - Validate glass token usage in Figma designs
- `pf-react-migration` - Migrate from PatternFly 5 to 6

## Resources

- [PatternFly Tokens](https://www.patternfly.org/tokens/all-patternfly-tokens)
- [PatternFly Themes](https://www.patternfly.org/get-started/develop#themes)
