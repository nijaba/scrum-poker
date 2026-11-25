import type {
  Delegate,
  JiraBoard,
  JiraSite,
  Me,
  Player,
  QueueFilter,
  QueuePreview,
  RoomInfo,
  RoomListing,
} from "./types";

/** An HTTP error, with the server's message and status. */
export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
  }
}

async function call<T>(method: string, path: string, body?: unknown): Promise<T> {
  const response = await fetch(path, {
    method,
    credentials: "same-origin",
    headers: body === undefined ? {} : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!response.ok) {
    const data = await response.json().catch(() => null);
    const detail = typeof data?.detail === "string" ? data.detail : null;
    throw new ApiError(detail ?? `Request failed (${response.status}).`, response.status);
  }
  return response.status === 204 ? (undefined as T) : response.json();
}

/** The player from the cookie, or null when this browser has not chosen a name. */
export async function getPlayer(): Promise<Player | null> {
  try {
    return await call<Player>("GET", "/api/player");
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) return null;
    throw err;
  }
}

/** Forget this browser's player: the next name is a new player. */
/** Take this browser's player off the room's table. A web request, so it works even when
 * the room's socket has dropped (design.md, "The menu behind your name"). */
export function leaveRoom(slug: string): Promise<void> {
  return call("POST", `/api/rooms/${encodeURIComponent(slug)}/leave`, {});
}

/** Change this browser's name at the table, keeping the seat (design.md, "The menu behind
 * your name"). The server renames the seat, then updates the player cookie. */
export function renameInRoom(slug: string, name: string): Promise<Player> {
  return call("POST", `/api/rooms/${encodeURIComponent(slug)}/rename`, { name });
}

export function forgetPlayer(): Promise<void> {
  return call("DELETE", "/api/player");
}

/** Set the name. The server keeps the random ID and sets the year-long cookie. */
export function setPlayerName(name: string): Promise<Player> {
  return call("POST", "/api/player", { name });
}

export function getMe(): Promise<Me> {
  return call("GET", "/api/me");
}

export function signOut(): Promise<void> {
  return call("POST", "/auth/logout");
}

export function signInUrl(provider: string, next = location.pathname): string {
  return `/auth/${provider}/login?next=${encodeURIComponent(next)}`;
}

export function listRooms(): Promise<RoomListing[]> {
  return call("GET", "/api/rooms");
}

/** Offer the room to one of its delegates. Owner only. */
export function offerOwnership(slug: string, delegate: Delegate): Promise<RoomInfo> {
  return call("POST", `/api/rooms/${encodeURIComponent(slug)}/ownership`, {
    provider: delegate.provider,
    identifier: delegate.identifier,
  });
}

export function cancelOwnershipOffer(slug: string): Promise<void> {
  return call("DELETE", `/api/rooms/${encodeURIComponent(slug)}/ownership`);
}

/** Accept or decline the room's offer to the signed-in account. */
export function answerOwnershipOffer(slug: string, accept: boolean): Promise<RoomInfo | void> {
  const verb = accept ? "accept" : "decline";
  return call("POST", `/api/rooms/${encodeURIComponent(slug)}/ownership/${verb}`, {});
}

/** The queue a session would load with this filter, not yet saved. Owner and co-owners. */
export function previewQueue(slug: string, queue_filter: QueueFilter): Promise<QueuePreview> {
  return call("POST", `/api/rooms/${encodeURIComponent(slug)}/queue-preview`, { queue_filter });
}

/** Save a demo room's settings, in memory (design.md, "Demo rooms"). No sign-in. */
export function updateDemoRoom(slug: string, changes: Record<string, unknown>): Promise<RoomInfo> {
  return call("PATCH", `/api/demo/${encodeURIComponent(slug)}/settings`, changes);
}

/** The queue a demo room's sample backlog would give with this filter, not yet saved. */
export function previewDemoQueue(slug: string, queue_filter: QueueFilter): Promise<QueuePreview> {
  return call("POST", `/api/demo/${encodeURIComponent(slug)}/queue-preview`, { queue_filter });
}

/** A new demo room, private to whoever asked for it, with bots and a made-up backlog. */
export function createDemo(): Promise<{ slug: string }> {
  return call("POST", "/api/demo", {});
}

/** Seat one more bot in a demo room. */
export function addBot(slug: string): Promise<{ name: string }> {
  return call("POST", `/api/demo/${encodeURIComponent(slug)}/bots`, {});
}

export function createRoom(slug: string): Promise<RoomInfo> {
  return call("POST", "/api/rooms", { slug });
}

/** The room, or null if there is no such room. Follows a renamed room to its new name. */
export async function getRoom(slug: string): Promise<RoomInfo | null> {
  try {
    return await call<RoomInfo>("GET", `/api/rooms/${encodeURIComponent(slug)}`);
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) return null;
    throw err;
  }
}

export function updateRoom(slug: string, changes: Record<string, unknown>): Promise<RoomInfo> {
  return call("PATCH", `/api/rooms/${encodeURIComponent(slug)}`, changes);
}

export function deleteRoom(slug: string): Promise<void> {
  return call("DELETE", `/api/rooms/${encodeURIComponent(slug)}`);
}

export function connectJiraUrl(slug: string): string {
  return `/auth/atlassian/login?room=${encodeURIComponent(slug)}`;
}

export function jiraSites(slug: string): Promise<JiraSite[]> {
  return call("GET", `/api/rooms/${encodeURIComponent(slug)}/jira/sites`);
}

export function jiraBoards(slug: string, cloudId: string): Promise<JiraBoard[]> {
  const query = `cloud_id=${encodeURIComponent(cloudId)}`;
  return call("GET", `/api/rooms/${encodeURIComponent(slug)}/jira/boards?${query}`);
}

export function chooseJiraBoard(slug: string, cloudId: string, boardId: number): Promise<RoomInfo> {
  return call("PUT", `/api/rooms/${encodeURIComponent(slug)}/jira/board`, {
    cloud_id: cloudId,
    board_id: boardId,
  });
}

export function disconnectJira(slug: string): Promise<void> {
  return call("DELETE", `/api/rooms/${encodeURIComponent(slug)}/jira`);
}

export const PROVIDER_NAMES = { google: "Google", github: "GitHub" } as const;
