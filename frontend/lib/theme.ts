export type ThemeMode = "light" | "dark" | "system";

export function resolveTheme(mode: ThemeMode, systemDark: boolean): "light" | "dark" {
  return mode === "system" ? (systemDark ? "dark" : "light") : mode;
}

export function readThemeMode(value: string | null): ThemeMode {
  return value === "light" || value === "dark" || value === "system" ? value : "system";
}

export function persistThemeMode(mode: ThemeMode, storage: Pick<Storage, "setItem">) {
  storage.setItem("eamms-theme", mode);
}

export const THEME_BOOTSTRAP_SCRIPT = `(()=>{try{const k='eamms-theme';const v=localStorage.getItem(k);const m=v==='light'||v==='dark'||v==='system'?v:'system';const d=window.matchMedia('(prefers-color-scheme: dark)').matches;document.documentElement.dataset.themeMode=m;document.documentElement.dataset.theme=m==='system'?(d?'dark':'light'):m}catch{document.documentElement.dataset.theme='light';document.documentElement.dataset.themeMode='system'}})()`;
