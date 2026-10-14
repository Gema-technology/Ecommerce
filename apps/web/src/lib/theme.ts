export type Theme = "light" | "dark";

export const THEME_STORAGE_KEY = "gema-theme";

export function formatServerTimestamp(date = new Date()): string {
  return new Intl.DateTimeFormat("es-EC", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

export function resolveTheme(stored: string | null): Theme | null {
  if (stored === "light" || stored === "dark") return stored;
  return null;
}

export const THEME_INIT_SCRIPT = `(function(){try{var k="${THEME_STORAGE_KEY}";var t=localStorage.getItem(k);if(t==="dark"||t==="light"){document.documentElement.setAttribute("data-theme",t);return}if(window.matchMedia("(prefers-color-scheme: dark)").matches){document.documentElement.setAttribute("data-theme","dark")}}catch(e){}})();`;
