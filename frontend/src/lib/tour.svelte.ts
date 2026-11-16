/**
 * The guided tour (design.md, "Tour"). A page offers its tour by calling
 * `offerTour` with a key and its steps; Tour.svelte draws the running tour,
 * TourOffer.svelte the once-only offer, and the menu and footer start it again.
 */

export type TourStep = {
  /** The `data-tour` value of the part of the page the step explains, or several to try in
   * turn; none for a caption alone. */
  target?: string | string[];
  title: string;
  text: string;
};

/** A tour: its steps, and an optional second part that Show me more adds at the end. */
export type Tour = { steps: TourStep[]; more?: TourStep[] };

export type TourKey = "room" | "settings";

const storageKey = (key: TourKey) => `scrum-poker-tour-${key}`;

function seen(key: TourKey): boolean {
  try {
    return localStorage.getItem(storageKey(key)) === "seen";
  } catch {
    return true; // storage refused: never nag
  }
}

function markSeen(key: TourKey): void {
  try {
    localStorage.setItem(storageKey(key), "seen");
  } catch {
    // storage refused
  }
}

export const tour = $state({
  /** The page's tour, or null when the page has none. */
  key: null as TourKey | null,
  steps: null as (() => Tour) | null,
  /** Show the once-only offer. */
  offered: false,
  /** The steps of the running tour, fixed when it starts; null when it is not running. */
  running: null as TourStep[] | null,
  /** The second part, while Show me more can still add it. */
  more: null as TourStep[] | null,
  at: 0,
});

/** The page has a tour. Returns the function that withdraws it. */
export function offerTour(key: TourKey, steps: () => Tour): () => void {
  tour.key = key;
  tour.steps = steps;
  tour.offered = !seen(key);
  return () => {
    if (tour.key !== key) return;
    tour.key = null;
    tour.steps = null;
    tour.offered = false;
    tour.running = null;
    tour.more = null;
  };
}

let returnFocus: HTMLElement | null = null;

/** Start the tour; `from` is the control that started it, where focus returns at the end
 * (Safari does not focus a button when it is clicked). */
export function startTour(from?: unknown): void {
  if (!tour.key || !tour.steps) return;
  markSeen(tour.key);
  tour.offered = false;
  returnFocus =
    from instanceof HTMLElement
      ? from
      : document.activeElement instanceof HTMLElement
        ? document.activeElement
        : null;
  const chosen = tour.steps();
  tour.running = chosen.steps;
  tour.more = chosen.more?.length ? chosen.more : null;
  tour.at = 0;
}

/** Show me more: carry on into the second part, numbered on from the first. */
export function showMore(): void {
  if (!tour.running || !tour.more) return;
  tour.running = [...tour.running, ...tour.more];
  tour.more = null;
  tour.at += 1;
}

export function declineTour(): void {
  if (tour.key) markSeen(tour.key);
  tour.offered = false;
}

export function endTour(): void {
  tour.running = null;
  tour.more = null;
  const back = returnFocus;
  returnFocus = null;
  if (back?.isConnected) back.focus();
}
