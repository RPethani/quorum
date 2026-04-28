"use client";

import { ThemeProvider as NextThemesProvider } from "next-themes";
import type { ReactNode } from "react";

type ThemeProviderProps = {
  children: ReactNode;
};

/**
 * Wraps next-themes with Quorum's defaults:
 *   - System preference is the default theme
 *   - Class-based dark mode (matches our @custom-variant in globals.css)
 *   - Disables transitions on theme change to avoid jank during the swap
 *
 * The wrapping <html> must have `suppressHydrationWarning` to avoid the
 * SSR/CSR mismatch warning when next-themes adopts the class on first
 * paint. See app/layout.tsx.
 */
export function ThemeProvider({ children }: ThemeProviderProps) {
  return (
    <NextThemesProvider
      attribute="class"
      defaultTheme="system"
      enableSystem
      disableTransitionOnChange
    >
      {children}
    </NextThemesProvider>
  );
}
