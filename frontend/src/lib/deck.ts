// The arcade deck: a browser-only preference, switched by the Konami code. It sets
// data-deck="arcade" on the page's root (and the mini window's), and app.css does
// the rest. Nobody else's screen changes, and the server is never told.

const DECK_KEY = "scrum-poker:deck";
const CODE = [
  "arrowup",
  "arrowup",
  "arrowdown",
  "arrowdown",
  "arrowleft",
  "arrowright",
  "arrowleft",
  "arrowright",
  "b",
  "a",
];

export function loadArcade(): boolean {
  try {
    return localStorage.getItem(DECK_KEY) === "arcade";
  } catch {
    return false;
  }
}

function saveArcade(on: boolean): void {
  try {
    localStorage.setItem(DECK_KEY, on ? "arcade" : "classic");
  } catch {
    // Private windows may refuse storage; the deck still changes for this page.
  }
}

/** Show the chosen deck in a document: this page, or the mini window. */
export function applyDeck(doc: Document, arcade = loadArcade()): void {
  if (arcade) doc.documentElement.dataset.deck = "arcade";
  else delete doc.documentElement.dataset.deck;
}

function typing(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  return target.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName);
}

/**
 * Listen for the Konami code outside text fields. Each time it is typed the deck
 * switches, and `onswitch` hears the new state. Returns a function that stops listening.
 */
export function listenForCode(onswitch: (arcade: boolean) => void): () => void {
  let at = 0;
  function onKey(event: KeyboardEvent) {
    if (typing(event.target) || event.metaKey || event.ctrlKey || event.altKey) {
      at = 0;
      return;
    }
    const key = event.key.toLowerCase();
    if (key === CODE[at]) at += 1;
    // A miss starts again, but an extra "up" after "up up" still counts as "up up".
    else if (key === CODE[0]) at = at === 2 ? 2 : 1;
    else at = 0;
    if (at < CODE.length) return;
    at = 0;
    const arcade = document.documentElement.dataset.deck !== "arcade";
    saveArcade(arcade);
    applyDeck(document, arcade);
    onswitch(arcade);
  }
  window.addEventListener("keydown", onKey);
  return () => window.removeEventListener("keydown", onKey);
}
