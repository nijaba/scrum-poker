// Countdown sound, synthesized with the Web Audio API: soft ticks for the last
// five seconds and a chime at zero. No audio files.

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
