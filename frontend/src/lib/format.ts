/** Whole seconds left as m:ss, rounding up so 0:00 shows only at the end. */
export function clock(seconds: number): string {
  const whole = Math.max(0, Math.ceil(seconds));
  const m = Math.floor(whole / 60);
  const s = whole % 60;
  return `${m}:${s.toString().padStart(2, "0")}`;
}

export function plural(count: number, one: string, many = `${one}s`): string {
  return `${count} ${count === 1 ? one : many}`;
}

export function points(value: number): string {
  return plural(value, "point");
}

/**
 * Seconds left on the countdown, counted locally from the server's remaining time
 * when the snapshot arrived (`receivedAt`, from performance.now()). This sidesteps
 * any difference between the two clocks. Null when no countdown is showing.
 */
export function remainingAt(
  countdown: { running: boolean; remaining: number | null; time_up: boolean } | undefined,
  receivedAt: number,
  now: number,
): number | null {
  if (!countdown) return null;
  if (!countdown.running) return countdown.time_up ? 0 : null;
  return Math.max(0, (countdown.remaining ?? 0) - (now - receivedAt) / 1000);
}
