<script lang="ts">
  import { onDestroy, onMount } from "svelte";
  import { addBot, forgetPlayer, getMe, getPlayer, getRoom, signOut } from "../lib/api";
  import { duration, plural, points, remainingAt } from "../lib/format";
  import { RoomConnection } from "../lib/room.svelte";
  import { openMini } from "../lib/mini";
  import {
    loadMuted,
    playChime,
    playChord,
    playGurgle,
    playTick,
    saveMuted,
    unlockAudio,
  } from "../lib/sound";
  import type { Me, Player } from "../lib/types";
  import { roomTour } from "../lib/tours";
  import { offerTour, startTour } from "../lib/tour.svelte";
  import { remote, setRemote, viewport } from "../lib/viewport.svelte";
  import FacilitatorPanel from "./FacilitatorPanel.svelte";
  import FinalPoints from "./FinalPoints.svelte";
  import Hand from "./Hand.svelte";
  import Join from "./Join.svelte";
  import RemoteView from "./RemoteView.svelte";
  import Table from "./Table.svelte";
  import TicketCard from "./TicketCard.svelte";
  import TourOffer from "./TourOffer.svelte";
  import UserMenu from "./UserMenu.svelte";

  let { slug }: { slug: string } = $props();

  let player = $state<Player | null | undefined>(undefined); // undefined while loading
  let me = $state<Me | null>(null);
  let missing = $state(false);
  let joinName = $state<string | null>(null); // the name the room refused, to edit
  let joinError = $state<string | null>(null);
  let loadError = $state<string | null>(null);
  let room = $state<RoomConnection | null>(null);
  let copied = $state(false);
  let muted = $state(loadMuted());
  let now = $state(performance.now());

  const snap = $derived(room?.snapshot ?? null);
  const isFacilitator = $derived(snap?.you.role === "facilitator");
  const currentSlug = $derived(room?.slug || slug);
  const roleLabel = $derived(
    snap?.you.access === "owner"
      ? "Owner"
      : snap?.you.access === "delegate"
        ? "Delegate"
        : isFacilitator
          ? "Facilitator"
          : "Player",
  );

  // Phones get their own arrangement of the same pieces (design.md, "Phones").
  const phone = $derived(viewport.phone);
  const remoteView = $derived(phone && !isFacilitator && remote.on);
  const phoneInfo = $derived(
    phone && snap
      ? [
          `Session: ${plural(snap.counters.session.tickets, "ticket")} · ${points(snap.counters.session.points)}`,
          `Backlog: ${snap.counters.backlog.estimated} of ${plural(snap.counters.backlog.total, "ticket")} · ${points(snap.counters.backlog.points)}`,
        ]
      : [],
  );
  let sheet = $state<HTMLDialogElement | null>(null);

  const remaining = $derived(
    room ? remainingAt(snap?.countdown, room.receivedAt, now) : null,
  );

  let ticker: ReturnType<typeof setInterval>;

  // The tour, by role, once the room is on screen (design.md, "Tour").
  const inRoom = $derived(!!snap && !room?.ended);
  $effect(() => {
    if (!inRoom) return;
    return offerTour("room", () =>
      roomTour({
        facilitator: isFacilitator,
        owner: snap?.you.access === "owner",
        phone,
        remote: remoteView,
      }),
    );
  });

  onMount(async () => {
    ticker = setInterval(() => (now = performance.now()), 100);
    try {
      const [found, p, m] = await Promise.all([getRoom(slug), getPlayer(), getMe().catch(() => null)]);
      me = m;
      if (!found) {
        missing = true;
        player = null;
        return;
      }
      player = p;
      if (player) connect();
    } catch (err) {
      loadError = err instanceof Error ? err.message : "Could not load the room.";
    }
  });

  onDestroy(() => {
    clearInterval(ticker);
    room?.close();
  });

  function connect() {
    room = new RoomConnection(slug);
  }

  /** Leave the table, then sign out and go home, or forget the player's name. */
  async function logOut() {
    room?.send({ type: "leave" });
    room?.close();
    room = null;
    try {
      if (me?.signed_in) {
        await signOut();
        location.assign("/");
      } else {
        await forgetPlayer();
        player = null;
      }
    } catch (err) {
      loadError = err instanceof Error ? err.message : "Could not log out.";
    }
  }

  // The room refused the name: back to the name form, with the name and the reason.
  $effect(() => {
    const taken = room?.nameTaken;
    if (!taken) return;
    joinName = player?.name ?? null;
    joinError = taken;
    room?.close();
    room = null;
    player = null;
  });

  function joined(p: Player) {
    joinName = joinError = null;
    player = p;
    unlockAudio();
    connect();
  }

  let botError = $state<string | null>(null);
  async function moreBots() {
    botError = null;
    try {
      await addBot(currentSlug);
    } catch (err) {
      botError = err instanceof Error ? err.message : "Could not add a bot.";
    }
  }

  async function copyLink() {
    try {
      await navigator.clipboard.writeText(`${location.origin}/r/${currentSlug}`);
      copied = true;
      setTimeout(() => (copied = false), 2000);
    } catch {
      copied = false;
    }
  }

  async function startMini() {
    unlockAudio(); // the countdown sound plays from this tab
    if (room) await openMini(room, () => (now = performance.now()), () => {});
  }

  function toggleMute() {
    muted = !muted;
    saveMuted(muted);
  }

  // Sound: ticks for the last five seconds, a chime at zero. Plain variables,
  // not state, so the effect only reruns when the countdown or settings change.
  let lastSecond: number | null = null;
  let chimed = false;
  $effect(() => {
    const countdown = snap?.countdown;
    const left = remaining;
    const enabled = !!snap?.sound && !muted;
    if (!countdown || left === null) {
      lastSecond = null;
      chimed = false;
      return;
    }
    const second = Math.ceil(left);
    if (countdown.running && second > 0) chimed = false;
    if (enabled && lastSecond !== null && second !== lastSecond && second >= 1 && second <= 5) {
      playTick();
    }
    if (enabled && !chimed && (second === 0 || countdown.time_up)) playChime();
    if (second === 0 || countdown.time_up) chimed = true;
    lastSecond = second;
  });

  // The little extras: a gurgle when someone starts a coffee break, a chord on a
  // perfect consensus. Plain variables again; the first snapshot only sets them.
  let onBreak: Set<string> | null = null;
  let celebrated: boolean | null = null; // null until the first snapshot
  $effect(() => {
    const players = snap?.players;
    const enabled = !!snap?.sound && !muted;
    if (!players) return;
    const now = new Set(players.filter((p) => p.on_break).map((p) => p.id));
    if (enabled && onBreak && [...now].some((id) => !onBreak!.has(id))) playGurgle();
    onBreak = now;
  });
  $effect(() => {
    if (!snap) return;
    const perfect = !!snap.round.results?.perfect;
    const enabled = snap.sound && !muted;
    if (perfect && celebrated === false && enabled) playChord();
    celebrated = perfect;
  });
</script>

{#snippet moreButton()}
  <button
    class="btn more"
    type="button"
    aria-label="More controls"
    aria-haspopup="dialog"
    data-tour="more"
    onclick={() => sheet?.showModal()}
  >
    <svg aria-hidden="true" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="5" cy="12" r="1.5"></circle><circle cx="12" cy="12" r="1.5"></circle><circle cx="19" cy="12" r="1.5"></circle></svg>
  </button>
{/snippet}

{#if missing}
  <p class="loading">There is no room called {slug}. <a href="/">Scrum poker home</a></p>
{:else if player === undefined}
  <p class="loading">{loadError ?? "Loading…"}</p>
{:else if player === null}
  <Join
    {slug}
    initialName={joinName ?? (me?.signed_in ? (me.name ?? "") : "")}
    initialError={joinError}
    onjoined={joined}
  />
{:else}
  <!-- svelte-ignore a11y_no_static_element_interactions -->
  <div class="room" onpointerdown={unlockAudio} onkeydown={unlockAudio}>
    <header>
      <div class="title">
        <a class="slug" href="/" title="Scrum poker home">{currentSlug}</a>
        {#if phone && snap?.ticket}
          <span class="position">Ticket {snap.queue.position} of {snap.queue.length}</span>
        {/if}
        <button
          class="btn icon-btn copy"
          type="button"
          aria-label={phone ? (copied ? "Copied" : "Copy link") : undefined}
          onclick={copyLink}
        >
          <svg aria-hidden="true" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10 13a5 5 0 0 0 7 0l3-3a5 5 0 0 0-7-7l-1 1"></path><path d="M14 11a5 5 0 0 0-7 0l-3 3a5 5 0 0 0 7 7l1-1"></path></svg>
          {#if !phone}<span>{copied ? "Copied" : "Copy link"}</span>{/if}
        </button>
      </div>
      {#if snap && phone}
        <div class="meta">
          {#if remoteView}
            <button class="btn icon-btn" type="button" onclick={() => setRemote(false)}>Full room</button>
          {/if}
          <UserMenu
            name={snap.you.name ?? player.name}
            role={roleLabel}
            signedIn={!!me?.signed_in}
            settingsHref={snap.you.access === "owner" ? `/r/${currentSlug}/settings` : null}
            onlogout={logOut}
            info={phoneInfo}
            muted={snap.sound ? muted : null}
            onmute={toggleMute}
            remote={isFacilitator ? null : remote.on}
            onremote={() => setRemote(!remote.on)}
            ontour={() => startTour()}
          />
        </div>
      {:else if snap}
        <div class="meta">
          <div class="counter" aria-label="Session counter">
            <span class="counter-label">Session</span>
            <span class="counter-value"
              >{plural(snap.counters.session.tickets, "ticket")} · {points(
                snap.counters.session.points,
              )}</span
            >
          </div>
          <div class="counter" aria-label="Backlog counter">
            <span class="counter-label">Backlog</span>
            <span class="counter-value"
              >{snap.counters.backlog.estimated} of {plural(snap.counters.backlog.total, "ticket")}
              · {points(snap.counters.backlog.points)}</span
            >
          </div>
          {#if snap.sound}
            <button class="btn icon-btn" type="button" aria-pressed={muted} onclick={toggleMute}>
              {muted ? "Unmute" : "Mute"}
            </button>
          {/if}
          <button class="btn icon-btn" type="button" onclick={startMini}>
            <svg aria-hidden="true" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="16" rx="2"></rect><rect x="12" y="12" width="7" height="6" rx="1"></rect></svg>
            <span>Mini mode</span>
          </button>
          <UserMenu
            name={snap.you.name ?? player.name}
            role={roleLabel}
            signedIn={!!me?.signed_in}
            settingsHref={snap.you.access === "owner" ? `/r/${currentSlug}/settings` : null}
            onlogout={logOut}
            ontour={() => startTour()}
          />
        </div>
      {/if}
    </header>

    {#if snap?.demo && !room?.ended}
      <p class="banner demo" role="note">
        <span
          ><strong>Demo room.</strong> The other players are bots and the backlog is made up; nothing
          reaches Jira. The room ends after {duration(snap.demo_idle_seconds ?? 1800)} with
          nobody here.</span
        >
        <span class="demo-actions">
          <button class="btn" type="button" onclick={(e) => startTour(e.currentTarget)}
            >Take the tour</button
          >
          <button class="btn" type="button" onclick={moreBots}>Add a bot</button>
        </span>
        {#if botError}<span class="bot-error" role="alert">{botError}</span>{/if}
      </p>
    {/if}
    {#if snap && !room?.ended && !snap.demo}
      <TourOffer text="New here? A short tour shows how the room works." />
    {/if}
    {#if room?.ended}
      <p class="banner banner-error" role="alert">
        {room.ended === "deleted"
          ? "The owner deleted this room."
          : `There is no room called ${slug}.`}
        <a href="/">Scrum poker home</a>
      </p>
    {:else if room && room.status !== "open"}
      <p class="banner" role="status">
        {room.status === "connecting" ? "Connecting…" : "Connection lost. Reconnecting…"}
      </p>
    {/if}
    {#if room?.error}
      <p class="banner banner-error" role="alert">{room.error}</p>
    {/if}
    {#if snap && !snap.you.seated}
      <p class="banner" role="status">
        {#if snap.check_in_open}
          The room was reset. Checking in…
        {:else}
          {snap.you.removed
            ? "A facilitator removed you from the table."
            : "You are not seated in this round."}
          <button class="btn" type="button" onclick={() => room?.send({ type: "join" })}
            >Join again</button
          >
        {/if}
      </p>
    {/if}

    {#if snap && room && !room.ended && remoteView}
      <RemoteView
        {snap}
        {remaining}
        onvote={(card) => room?.send({ type: "vote", card })}
        onsit={(atTable) => room?.send({ type: atTable ? "sit_in" : "sit_out" })}
        onbreak={(on) => room?.send({ type: "break", on })}
      />
    {:else if snap && room && !room.ended && phone}
      <main class="phone">
        {#if snap.backlog.state !== "ready"}
          <section class="panel" aria-label="Backlog" aria-live="polite" data-tour="ticket">
            <h1 class="done">
              {snap.backlog.state === "loading"
                ? "Loading the backlog from Jira…"
                : "The backlog did not load"}
            </h1>
            {#if snap.backlog.state === "error"}<p class="note">{snap.backlog.message}</p>{/if}
          </section>
        {:else if snap.ticket}
          <TicketCard ticket={snap.ticket} queue={snap.queue} />
        {:else}
          <section class="panel" aria-label="Current ticket" data-tour="ticket">
            <h1 class="done">All tickets in the queue are done.</h1>
          </section>
        {/if}
        <Table
          {snap}
          {remaining}
          compact
          showCountdown
          onremove={isFacilitator
            ? (id) => room?.send({ type: "remove_player", player_id: id })
            : undefined}
        />
      </main>
      <div class="dock">
        {#if snap.ticket && snap.you.seated && (snap.round.state === "voting" || !isFacilitator)}
          <Hand
            {snap}
            compact
            onvote={(card) => room?.send({ type: "vote", card })}
            onsit={(atTable) => room?.send({ type: atTable ? "sit_in" : "sit_out" })}
            onbreak={(on) => room?.send({ type: "break", on })}
          />
        {/if}
        {#if isFacilitator}
          {#if snap.ticket && snap.round.state !== "voting"}
            <FinalPoints {snap} send={(m) => room?.send(m)} docked lead={moreButton} />
          {:else}
            <div class="dock-actions" data-tour="reveal">
              {@render moreButton()}
              {#if snap.ticket}
                <button class="btn-primary" type="button" onclick={() => room?.send({ type: "reveal" })}
                  >Reveal cards · {snap.players.filter((p) => p.voted).length} of {snap.players
                    .length}</button
                >
              {/if}
            </div>
          {/if}
        {/if}
      </div>
      {#if isFacilitator}
        <dialog class="sheet" bind:this={sheet} aria-label="Session controls">
          <div class="sheet-head">
            <h2>Session controls</h2>
            <button class="btn icon-btn" type="button" aria-label="Close" onclick={() => sheet?.close()}>
              <svg aria-hidden="true" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M18 6 6 18"></path><path d="m6 6 12 12"></path></svg>
            </button>
          </div>
          <FacilitatorPanel {snap} {remaining} send={(m) => room?.send(m)} docked />
        </dialog>
      {/if}
    {:else if snap && room && !room.ended}
      <main>
        <div class="main-column">
          {#if snap.backlog.state !== "ready"}
            <section class="panel" aria-label="Backlog" aria-live="polite" data-tour="ticket">
              {#if snap.backlog.state === "loading"}
                <h1 class="done">Loading the backlog from Jira…</h1>
              {:else}
                <h1 class="done">The backlog did not load</h1>
                <p class="note">{snap.backlog.message}</p>
                <div class="backlog-actions">
                  {#if isFacilitator}
                    <button class="btn" type="button" onclick={() => room?.send({ type: "reload_backlog" })}
                      >Try again</button
                    >
                  {/if}
                  {#if snap.you.access === "owner"}
                    <a class="btn icon-btn settings-link" href="/r/{currentSlug}/settings"
                      >Open room settings</a
                    >
                  {/if}
                </div>
              {/if}
            </section>
          {:else if snap.ticket}
            <TicketCard ticket={snap.ticket} queue={snap.queue} />
          {:else}
            <section class="panel" aria-label="Current ticket" data-tour="ticket">
              <h1 class="done">All tickets in the queue are done.</h1>
              <p class="note">The facilitator can rewind to revisit one.</p>
            </section>
          {/if}
          <Table
            {snap}
            {remaining}
            showCountdown={!isFacilitator}
            onremove={isFacilitator
              ? (id) => room?.send({ type: "remove_player", player_id: id })
              : undefined}
          />
          {#if snap.ticket && snap.you.seated}
            <Hand
              {snap}
              onvote={(card) => room?.send({ type: "vote", card })}
              onsit={(atTable) => room?.send({ type: atTable ? "sit_in" : "sit_out" })}
              onbreak={(on) => room?.send({ type: "break", on })}
            />
          {/if}
        </div>
        {#if isFacilitator}
          <FacilitatorPanel {snap} {remaining} send={(m) => room?.send(m)} />
        {/if}
      </main>
    {/if}
  </div>
{/if}

<style>
  .loading {
    padding: 48px 24px;
  }
  .room {
    flex: 1;
    display: flex;
    flex-direction: column;
  }
  header {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 12px 20px;
    padding: 12px 24px;
    background: var(--surface);
    border-bottom: 1px solid var(--border);
  }
  .title {
    display: flex;
    align-items: center;
    gap: 12px;
  }
  .slug {
    font-family: var(--font-display);
    font-weight: 700;
    font-size: 22px;
    color: inherit;
    text-decoration: none;
  }
  .slug:hover,
  .slug:focus-visible {
    text-decoration: underline;
  }
  .icon-btn {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 0 12px;
    font-size: 14px;
    font-weight: 400;
  }
  .meta {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 10px;
    margin-left: auto;
  }
  .counter {
    display: flex;
    flex-direction: column;
    padding: 6px 14px;
    border-radius: 8px;
    background: var(--chip);
  }
  .counter-label {
    font-size: 12px;
    font-weight: 600;
    color: var(--text-3);
  }
  .counter-value {
    font-size: 14px;
    font-weight: 600;
  }
  .backlog-actions {
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
  }
  .settings-link {
    color: var(--ink);
    text-decoration: none;
  }
  .banner {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 12px;
    margin: 16px 24px 0;
    padding: 10px 16px;
    border-radius: 8px;
    background: var(--chip);
  }
  .banner.demo {
    border: 1px dashed var(--accent);
    background: var(--surface);
  }
  .demo-actions {
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
  }
  .bot-error {
    color: var(--danger);
  }
  .banner-error {
    background: var(--danger-bg);
    color: var(--danger);
  }
  main {
    display: flex;
    flex-wrap: wrap;
    align-items: flex-start;
    gap: 20px;
    padding: 20px 24px;
  }
  .main-column {
    flex: 999 1 560px;
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 16px;
  }
  .done {
    margin: 0;
    font-family: var(--font-display);
    font-size: 22px;
  }
  @media (max-width: 480px) {
    header,
    main {
      padding-left: 16px;
      padding-right: 16px;
    }
  }

  /* Phones (design.md, "Phones"): one-row header, a compact column, a docked hand. */
  .position {
    font-size: 13px;
    font-weight: 600;
    color: var(--text-3);
    white-space: nowrap;
  }
  @media (max-width: 640px) {
    header {
      flex-wrap: nowrap;
      gap: 8px;
      min-height: 56px;
      box-sizing: border-box;
      padding: 0 8px 0 16px;
    }
    .title {
      flex: 1;
      min-width: 0;
      gap: 8px;
    }
    .slug {
      font-size: 20px;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    .copy {
      flex: none;
      width: 44px;
      justify-content: center;
      padding: 0;
      border: none;
      background: none;
    }
    .meta {
      flex-wrap: nowrap;
      gap: 4px;
    }
    .banner {
      margin: 12px 16px 0;
    }
  }
  main.phone {
    flex: 1;
    flex-direction: column;
    flex-wrap: nowrap;
    align-items: stretch;
    gap: 12px;
    padding: 12px 16px;
  }
  .dock {
    position: sticky;
    bottom: 0;
    z-index: 10;
    display: flex;
    flex-direction: column;
    gap: 12px;
    padding: 10px 16px max(14px, env(safe-area-inset-bottom));
    background: var(--surface);
    border-top: 1px solid var(--border);
    box-shadow: 0 -6px 18px rgb(0 0 0 / 8%);
  }
  .dock:empty {
    display: none;
  }
  .dock-actions {
    display: flex;
    gap: 10px;
  }
  .dock-actions .btn-primary {
    flex: 1;
  }
  .more {
    flex: none;
    width: 52px;
    min-height: 52px;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 0;
  }
  .sheet {
    position: fixed;
    inset: auto 0 0 0;
    width: 100%;
    max-width: 640px;
    max-height: 88vh;
    box-sizing: border-box;
    margin: auto auto 0;
    padding: 8px 16px max(20px, env(safe-area-inset-bottom));
    border: none;
    border-radius: 18px 18px 0 0;
    background: var(--ground);
    color: var(--ink);
    overflow-y: auto;
  }
  .sheet::backdrop {
    background: rgb(17 22 20 / 45%);
  }
  .sheet-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding-bottom: 8px;
  }
  .sheet-head h2 {
    margin: 0;
    font-family: var(--font-display);
    font-size: 20px;
  }
</style>
