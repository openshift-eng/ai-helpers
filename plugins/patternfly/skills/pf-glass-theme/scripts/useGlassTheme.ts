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

    // Increment reference counts
    const glassCount = parseInt(htmlElement.dataset.pfGlassCount || '0', 10) + 1;
    htmlElement.dataset.pfGlassCount = glassCount.toString();

    let redhatCount = 0;
    if (variant === 'redhat') {
      redhatCount = parseInt(htmlElement.dataset.pfGlassRedhatCount || '0', 10) + 1;
      htmlElement.dataset.pfGlassRedhatCount = redhatCount.toString();
    }

    // Apply classes only if this is the first consumer
    if (glassCount === 1) {
      htmlElement.classList.add('pf-v6-theme-glass');
    }
    if (variant === 'redhat' && redhatCount === 1) {
      htmlElement.classList.add('pf-v6-theme-redhat');
    }

    // Cleanup: decrement counts and remove classes only when last consumer unmounts
    return () => {
      const newGlassCount = parseInt(htmlElement.dataset.pfGlassCount || '1', 10) - 1;
      htmlElement.dataset.pfGlassCount = Math.max(0, newGlassCount).toString();

      if (newGlassCount === 0) {
        htmlElement.classList.remove('pf-v6-theme-glass');
      }

      if (variant === 'redhat') {
        const newRedhatCount = parseInt(htmlElement.dataset.pfGlassRedhatCount || '1', 10) - 1;
        htmlElement.dataset.pfGlassRedhatCount = Math.max(0, newRedhatCount).toString();

        if (newRedhatCount === 0) {
          htmlElement.classList.remove('pf-v6-theme-redhat');
        }
      }
    };
  }, [variant]);
};
