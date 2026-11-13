import type { Card } from "./types";

export interface Suit {
  symbol: string;
  red: boolean;
}

const SUITS: Suit[] = [
  { symbol: "♠", red: false },
  { symbol: "♥", red: true },
  { symbol: "♣", red: false },
  { symbol: "♦", red: true },
];

/** Suits go round by position in the scale; cards with no value, such as "?", get none. */
export function suitOf(cards: Card[], label: string): Suit | null {
  const i = cards.findIndex((c) => c.label === label);
  if (i < 0 || cards[i].value === null) return null;
  return SUITS[i % SUITS.length];
}

/** A small fixed tilt for a card lying on the table, taken from the player's id. */
export function tiltOf(id: string): number {
  let h = 0;
  for (const ch of id) h = (h * 31 + ch.charCodeAt(0)) % 997;
  return ((h % 9) - 4) * 1.2;
}
