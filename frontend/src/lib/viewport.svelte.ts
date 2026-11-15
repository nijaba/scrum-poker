/** Phone layout below this width (design.md, "Phones"). Wider windows are unchanged. */
export const PHONE_QUERY = "(max-width: 640px)";

const query = typeof window !== "undefined" ? window.matchMedia(PHONE_QUERY) : null;

export const viewport = $state({ phone: query?.matches ?? false });

query?.addEventListener("change", (e) => (viewport.phone = e.matches));

const REMOTE_KEY = "scrum-poker-remote";

function loadRemote(): boolean {
  try {
    return localStorage.getItem(REMOTE_KEY) === "1";
  } catch {
    return false;
  }
}

/** A player's Remote view choice, kept in the browser. */
export const remote = $state({ on: loadRemote() });

export function setRemote(on: boolean): void {
  remote.on = on;
  try {
    localStorage.setItem(REMOTE_KEY, on ? "1" : "0");
  } catch {
    // storage refused: the choice lasts for this page only
  }
}
