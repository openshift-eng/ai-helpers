import { useEffect } from 'react';

/**
 * Custom hook to apply PatternFly glass theme
 *
 * Options:
 * - variant: 'default' | 'redhat' - Use Red Hat branded glass theme
 *
 * IMPORTANT: This hook does NOT manage dark/light theme.
 * If your app already manages .pf-v6-theme-dark (like OpenShift console),
 * this hook will work alongside it automatically.
 */
export const useGlassTheme = (options?: { variant?: 'default' | 'redhat' }) => {
  const variant = options?.variant ?? 'default';

  useEffect(() => {
    const htmlElement = document.documentElement;

    // Apply glass theme classes
    if (variant === 'redhat' && !htmlElement.classList.contains('pf-v6-theme-redhat')) {
      htmlElement.classList.add('pf-v6-theme-redhat');
    }
    if (!htmlElement.classList.contains('pf-v6-theme-glass')) {
      htmlElement.classList.add('pf-v6-theme-glass');
    }

    // Cleanup: remove glass theme classes on unmount
    return () => {
      htmlElement.classList.remove('pf-v6-theme-glass');
      if (variant === 'redhat') {
        htmlElement.classList.remove('pf-v6-theme-redhat');
      }
    };
  }, [variant]);
};
