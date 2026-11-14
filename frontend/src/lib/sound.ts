// Room sounds, synthesized with the Web Audio API: soft ticks for the last five
// seconds and a chime at zero, a gurgle for a coffee break and a chord for a
// perfect consensus. No audio files.

const MUTE_KEY = "scrum-poker:muted";

let context: AudioContext | null = null;

/** Browsers only allow audio after a user gesture; call this from one. */
export function unlockAudio(): void {
  if (!context) {
    const Ctor = window.AudioContext;
    if (!Ctor) return;
    context = new Ctor();
  }
  if (context.state === "suspended") void context.resume();
}

function tone(frequency: number, start: number, length: number, peak: number): void {
  if (!context) return;
  const oscillator = context.createOscillator();
  const gain = context.createGain();
  oscillator.type = "sine";
  oscillator.frequency.value = frequency;
  gain.gain.setValueAtTime(0, start);
  gain.gain.linearRampToValueAtTime(peak, start + 0.01);
  gain.gain.exponentialRampToValueAtTime(0.0001, start + length);
  oscillator.connect(gain).connect(context.destination);
  oscillator.start(start);
  oscillator.stop(start + length + 0.05);
}

export function playTick(): void {
  if (!context) return;
  tone(1200, context.currentTime, 0.06, 0.08);
}

export function playChime(): void {
  if (!context) return;
  const now = context.currentTime;
  tone(880, now, 0.9, 0.18);
  tone(1320, now + 0.12, 1.1, 0.12);
}

/** A coffee break: a few low, wobbling bubbles, like a percolator. */
export function playGurgle(): void {
  if (!context) return;
  const now = context.currentTime;
  [0, 0.11, 0.2, 0.34, 0.43].forEach((at, i) => {
    bubble(220 + (i % 3) * 70, now + at);
  });
}

function bubble(frequency: number, start: number): void {
  if (!context) return;
  const oscillator = context.createOscillator();
  const gain = context.createGain();
  oscillator.type = "sine";
  oscillator.frequency.setValueAtTime(frequency, start);
  oscillator.frequency.exponentialRampToValueAtTime(frequency * 1.8, start + 0.08);
  gain.gain.setValueAtTime(0, start);
  gain.gain.linearRampToValueAtTime(0.12, start + 0.01);
  gain.gain.exponentialRampToValueAtTime(0.0001, start + 0.1);
  oscillator.connect(gain).connect(context.destination);
  oscillator.start(start);
  oscillator.stop(start + 0.15);
}

/** A perfect consensus: a rising major chord. */
export function playChord(): void {
  if (!context) return;
  const now = context.currentTime;
  [523.25, 659.25, 783.99, 1046.5].forEach((f, i) => tone(f, now + i * 0.09, 1.2, 0.1));
}

export function loadMuted(): boolean {
  try {
    return localStorage.getItem(MUTE_KEY) === "1";
  } catch {
    return false;
  }
}

export function saveMuted(muted: boolean): void {
  try {
    localStorage.setItem(MUTE_KEY, muted ? "1" : "0");
  } catch {
    // Private windows may refuse storage; the mute still holds for this page.
  }
}
