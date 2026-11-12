// The snapshot the server sends each client. The client renders it and never
// decides game state itself. See app/room/room.py `snapshot_for`.

export interface Card {
  label: string;
  value: number | null;
}

export interface Scale {
  kind: "fibonacci" | "tshirt" | "custom";
  cards: Card[];
}

export interface PlayerView {
  id: string;
  name: string;
  connected: boolean;
  voted: boolean;
  card?: string | null; // only after reveal
}

export interface Results {
  votes: number;
  average: number | null;
  median: number | null;
  consensus: boolean;
  top: { label: string; count: number } | null;
}

export interface TicketView {
  key: string;
  summary: string;
  type: string | null;
  priority: string | null;
  epic: string | null;
  labels: string[];
  description: string;
  url: string | null;
  result: { status: "pending" | "estimated" | "skipped"; points: number | null };
}

export interface Countdown {
  running: boolean;
  duration: number | null;
  remaining: number | null;
  time_up: boolean;
}

export interface Snapshot {
  type: "state";
  you: {
    player_id: string | null;
    name: string | null;
    seated: boolean;
    vote: string | null;
    role: "player" | "facilitator";
    access: "owner" | "delegate" | null;
    account_name: string | null;
  };
  room: { slug: string };
  backlog: { state: "loading" | "ready" | "error"; code: string | null; message: string | null };
  scale: Scale;
  next_scale: Scale | null;
  round: { state: "voting" | "revealed" | "confirmed"; results?: Results };
  players: PlayerView[];
  ticket: TicketView | null;
  up_next: { key: string; summary: string }[];
  queue: { position: number; length: number; finished: boolean };
  counters: {
    session: { tickets: number; points: number };
    backlog: { estimated: number; total: number; points: number };
  };
  countdown: Countdown;
  timer_seconds: number;
  sound: boolean;
  check_in_open: boolean;
}

export interface ServerError {
  type: "error";
  code: string;
  message: string;
}

export type ServerMessage =
  | Snapshot
  | ServerError
  | { type: "check_in" }
  | { type: "moved"; slug: string }
  | { type: "deleted" };

export interface Player {
  id: string;
  name: string;
}

export interface Me {
  signed_in: boolean;
  providers: ("google" | "github")[];
  provider?: "google" | "github";
  name?: string;
  label?: string;
  can_create?: boolean;
}

export type Access = "owner" | "delegate" | null;

export interface Delegate {
  provider: "google" | "github";
  identifier: string;
}

export interface JiraSite {
  cloud_id: string;
  name: string;
  url: string;
}

export interface JiraBoard {
  id: number;
  name: string;
  type?: string | null;
}

export interface JiraSettings {
  available: boolean;
  connected: boolean;
  email: string | null;
  site: JiraSite | null;
  board: { id: number; name: string } | null;
}

export interface RoomSettings {
  scale: Scale;
  timer_seconds: number;
  sound: boolean;
  delegates: Delegate[];
  jira: JiraSettings;
}

export interface RoomInfo {
  slug: string;
  access: Access;
  settings?: RoomSettings;
}
