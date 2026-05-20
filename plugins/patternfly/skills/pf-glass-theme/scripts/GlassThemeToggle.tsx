import React from 'react';
import { Switch } from '@patternfly/react-core';

interface GlassThemeToggleProps {
  /** Optional custom label */
  label?: string;
  /** Optional callback when theme changes */
  onThemeChange?: (isGlassEnabled: boolean) => void;
}

export const GlassThemeToggle: React.FC<GlassThemeToggleProps> = ({
  label = 'Glass theme',
  onThemeChange,
}) => {
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

    onThemeChange?.(checked);
  };

  return (
    <Switch
      id="glass-theme-toggle"
      label={label}
      isChecked={isGlassEnabled}
      onChange={handleToggle}
      aria-label="Toggle glass theme"
    />
  );
};
