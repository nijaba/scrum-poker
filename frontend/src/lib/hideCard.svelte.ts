/**
 * Hide my card (design.md, "Sharing your screen"): keeps your own choice off your screen
 * until the reveal, for someone sharing it. Kept in this browser only; the server never knows.
 */
const KEY = "scrum-poker-hide-card";

function read(): boolean {
  try {
    return localStorage.getItem(KEY) === "on";
  } catch {
    return false; // storage refused: the usual hand
  }
}

export const hideCard = $state({ on: read() });

export function setHideCard(on: boolean): void {
  hideCard.on = on;
  try {
    if (on) localStorage.setItem(KEY, "on");
    else localStorage.removeItem(KEY);
  } catch {
    // storage refused: it still applies until the page closes
  }
}
