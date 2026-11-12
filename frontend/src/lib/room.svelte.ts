import type { ServerMessage, Snapshot } from "./types";

export type Status = "connecting" | "open" | "reconnecting";
/** Why the room will not come back: it was deleted, or never existed. */
export type Ended = "deleted" | "missing" | null;

const CLOSE_NO_ROOM = 4404;
const CLOSE_DELETED = 4410;

/**
 * The room's WebSocket. Holds the latest snapshot, answers reset check-ins and
 * reconnects with backoff. The player cookie identifies this browser, so a
 * reconnect gets the same seat back.
 */
export class RoomConnection {
  snapshot = $state<Snapshot | null>(null);
  status = $state<Status>("connecting");
  error = $state<string | null>(null);
  ended = $state<Ended>(null);
  slug = $state("");
  /** performance.now() when the latest snapshot arrived; the countdown counts from it. */
  receivedAt = $state(0);

  #url: string;
  #socket: WebSocket | null = null;
  #retry = 0;
  #timer: ReturnType<typeof setTimeout> | null = null;
  #closed = false;
  #errorTimer: ReturnType<typeof setTimeout> | null = null;

  constructor(slug: string) {
    this.slug = slug;
    this.#url = RoomConnection.#urlFor(slug);
    this.#open();
  }

  static #urlFor(slug: string): string {
    const scheme = location.protocol === "https:" ? "wss" : "ws";
    return `${scheme}://${location.host}/ws/rooms/${encodeURIComponent(slug)}`;
  }

  send(message: Record<string, unknown>): void {
    if (this.#socket?.readyState === WebSocket.OPEN) {
      this.#socket.send(JSON.stringify(message));
    } else {
      this.#showError("Not connected. Reconnecting…");
    }
  }

  close(): void {
    this.#closed = true;
    if (this.#timer) clearTimeout(this.#timer);
    this.#socket?.close();
  }

  #open(): void {
    const socket = new WebSocket(this.#url);
    this.#socket = socket;
    socket.addEventListener("open", () => {
      this.status = "open";
      this.#retry = 0;
    });
    socket.addEventListener("message", (event) => this.#receive(event.data));
    socket.addEventListener("close", (event) => {
      if (this.#socket !== socket || this.#closed) return;
      if (event.code === CLOSE_DELETED || event.code === CLOSE_NO_ROOM) {
        this.ended ??= event.code === CLOSE_DELETED ? "deleted" : "missing";
        this.#closed = true;
        return;
      }
      this.status = "reconnecting";
      const delay = Math.min(10_000, 500 * 2 ** this.#retry++);
      this.#timer = setTimeout(() => this.#open(), delay);
    });
  }

  #receive(raw: string): void {
    let message: ServerMessage;
    try {
      message = JSON.parse(raw);
    } catch {
      return;
    }
    if (message.type === "state") {
      this.snapshot = message;
      this.receivedAt = performance.now();
    } else if (message.type === "check_in") {
      // The facilitator reset the room: answer, so this browser is seated again.
      this.send({ type: "check_in" });
    } else if (message.type === "moved") {
      // The owner renamed the room: follow it, so reconnects and the address bar stay right.
      this.slug = message.slug;
      this.#url = RoomConnection.#urlFor(message.slug);
      history.replaceState(null, "", `/r/${message.slug}${location.search}`);
    } else if (message.type === "deleted") {
      this.ended = "deleted";
    } else if (message.type === "error") {
      this.#showError(message.message);
    }
  }

  #showError(text: string): void {
    this.error = text;
    if (this.#errorTimer) clearTimeout(this.#errorTimer);
    this.#errorTimer = setTimeout(() => (this.error = null), 6000);
  }
}
