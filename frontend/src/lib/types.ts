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
  on_break: boolean; // asked for a coffee break; not a vote
  card?: string | null; // only after reveal
}

export interface Results {
  votes: number;
  average: number | null;
  median: number | null;
  consensus: boolean;
  top: { label: string; count: number } | null;
  spread: { label: string; count: number }[]; // in scale order
  high: string | null; // the highest numeric card, when the numbers differ
  low: string | null;
  split_hint: boolean; // someone chose the scale's highest numeric card
  nobody_knows: boolean; // every vote is a card without a value
  perfect: boolean; // five or more players chose the same numeric card
}

export interface SummaryEntry {
  key: string;
  summary: string;
  status: "estimated" | "skipped";
  points: number | null;
  average: number | null;
  votes: { label: string; count: number }[];
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
  /** Jira's estimate already on the ticket, in a re-estimation session; only after reveal. */
  estimate?: number;
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
    sitting_out: boolean;
    on_break: boolean;
    removed: boolean;
    role: "player" | "facilitator";
    access: "owner" | "delegate" | null;
    account_name: string | null;
  };
  room: { slug: string };
  backlog: {
    state: "loading" | "ready" | "error";
    code: string | null;
    message: string | null;
    /** Facilitators only: the owner saved a queue filter this session hasn't loaded yet. */
    filter_changed?: boolean;
  };
  scale: Scale;
  next_scale: Scale | null;
  round: { state: "voting" | "revealed" | "confirmed"; results?: Results };
  players: PlayerView[]; // at the table
  watchers: { id: string; name: string; connected: boolean }[]; // sitting out
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
  auto_reveal: boolean;
  check_in_open: boolean;
  demo?: boolean; // a demo room: bots, a made-up backlog, anyone facilitates
  demo_idle_seconds?: number; // a demo room ends after this long with nobody in it
  summary?: SummaryEntry[]; // facilitators only
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
  demo_rooms: boolean; // the server offers demo rooms
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

/** Which backlog tickets a session walks through. All false and no JQL is the default. */
export interface QueueFilter {
  subtasks: boolean;
  in_progress: boolean;
  resolved: boolean;
  estimated: boolean;
  jql: string;
}

export interface QueuePreview {
  count: number;
  total: number;
  tickets: {
    key: string;
    summary: string;
    type: string | null;
    status: string | null;
    estimate: number | null;
    url: string | null;
  }[];
}

export interface RoomSettings {
  scale: Scale;
  timer_seconds: number;
  sound: boolean;
  auto_reveal: boolean;
  delegates: Delegate[];
  queue_filter: QueueFilter;
  jira: JiraSettings;
}

export interface RoomInfo {
  slug: string;
  access: Access;
  demo?: boolean;
  settings?: RoomSettings;
}
