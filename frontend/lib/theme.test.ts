import { describe, expect, it, vi } from "vitest";
import { persistThemeMode, readThemeMode, resolveTheme, THEME_BOOTSTRAP_SCRIPT } from "@/lib/theme";

describe("theme preferences", () => {
  it("switches explicit light and dark modes regardless of system preference", () => {
    expect(resolveTheme("light", true)).toBe("light");
    expect(resolveTheme("dark", false)).toBe("dark");
  });

  it("follows either system color preference in system mode", () => {
    expect(resolveTheme("system", true)).toBe("dark");
    expect(resolveTheme("system", false)).toBe("light");
  });

  it("persists each selection and reads it back on subsequent app loads", () => {
    let stored: string | null = null;
    const storage = { setItem: vi.fn((_key: string, value: string) => { stored = value; }) };
    for (const mode of ["light", "dark", "system"] as const) {
      persistThemeMode(mode, storage);
      expect(storage.setItem).toHaveBeenLastCalledWith("eamms-theme", mode);
      expect(readThemeMode(stored)).toBe(mode);
    }
  });

  it("renders a pre-hydration bootstrap that applies stored mode and system preference", () => {
    expect(THEME_BOOTSTRAP_SCRIPT).toContain("localStorage.getItem(k)");
    expect(THEME_BOOTSTRAP_SCRIPT).toContain("window.matchMedia");
    expect(THEME_BOOTSTRAP_SCRIPT).toContain("dataset.themeMode=m");
    expect(THEME_BOOTSTRAP_SCRIPT).toContain("document.documentElement.dataset.theme=");
    expect(readThemeMode("unsupported")).toBe("system");
  });
});
