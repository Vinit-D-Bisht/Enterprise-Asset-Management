"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { persistThemeMode, readThemeMode, resolveTheme, type ThemeMode } from "@/lib/theme";

type ThemeContextValue = { mode: ThemeMode; setMode: (mode: ThemeMode) => void };
const ThemeContext = createContext<ThemeContextValue | null>(null);

export function ThemeProvider({ children }: Readonly<{ children: React.ReactNode }>) {
  const [mode, updateMode] = useState<ThemeMode>("system");
  const setMode = useCallback((next: ThemeMode) => {
    persistThemeMode(next, localStorage);
    updateMode(next);
    document.documentElement.dataset.themeMode = next;
    document.documentElement.dataset.theme = resolveTheme(next, window.matchMedia("(prefers-color-scheme: dark)").matches);
  }, []);

  useEffect(() => {
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const sync = () => {
      const current = readThemeMode(localStorage.getItem("eamms-theme"));
      updateMode(current);
      document.documentElement.dataset.themeMode = current;
      document.documentElement.dataset.theme = resolveTheme(current, media.matches);
    };
    sync();
    media.addEventListener("change", sync);
    return () => media.removeEventListener("change", sync);
  }, []);

  const value = useMemo(() => ({ mode, setMode }), [mode, setMode]);
  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme() {
  const context = useContext(ThemeContext);
  if (!context) throw new Error("useTheme must be used inside ThemeProvider");
  return context;
}
