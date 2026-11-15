/**
 * The page's theme: System follows the device, Light and Dark override it.
 * The choice lives in localStorage; index.html applies it before the page draws.
 */

export type Theme = "system" | "light" | "dark";
export const THEMES: { value: Theme; label: string }[] = [
  { value: "system", label: "System" },
  { value: "light", label: "Light" },
  { value: "dark", label: "Dark" },
];
const KEY = "scrum-poker-theme"; // index.html reads the same key

function load(): Theme {
  try {
    const saved = localStorage.getItem(KEY);
    return saved === "light" || saved === "dark" ? saved : "system";
  } catch {
    return "system";
  }
}

export const theme = $state({ value: load() });

/** Show the theme on a document: no attribute means follow the device. */
export function applyTheme(doc: Document, value: Theme): void {
  if (value === "system") delete doc.documentElement.dataset.theme;
  else doc.documentElement.dataset.theme = value;
}

export function setTheme(value: Theme): void {
  theme.value = value;
  applyTheme(document, value);
  try {
    if (value === "system") localStorage.removeItem(KEY);
    else localStorage.setItem(KEY, value);
  } catch {
    // private windows may refuse storage: the choice lasts for this page only
  }
}
