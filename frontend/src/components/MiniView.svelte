<script lang="ts">
  import { clock, remainingAt } from "../lib/format";
  import type { RoomConnection } from "../lib/room.svelte";

  // Rendered inside the Picture-in-Picture window or the popup, but runs in the
  // main tab: it reads the main tab's room connection and votes through it.
  let {
    room,
    timers,
    ontick,
  }: {
    room: RoomConnection;
    /** The mini window, whose timers keep running while the main tab is hidden. */
    timers: Window;
    /** Called on each tick, so the main tab's countdown and sound keep time too. */
    ontick: () => void;
  } = $props();

  let now = $state(performance.now());
  $effect(() => {
    const win = timers;
    const tick = ontick;
    const ticker = win.setInterval(() => {
      now = performance.now();
      tick();
    }, 100);
    return () => win.clearInterval(ticker);
  });

  const snap = $derived(room.snapshot);
  const remaining = $derived(snap ? remainingAt(snap.countdown, room.receivedAt, now) : null);
  const voting = $derived(snap?.round.state === "voting");
  const voted = $derived(snap ? snap.players.filter((p) => p.voted).length : 0);
  const countdown = $derived(snap?.countdown);
  const progress = $derived(
    countdown?.running && countdown.duration && remaining !== null
      ? Math.max(0, Math.min(1, remaining / countdown.duration))
      : countdown?.time_up
        ? 0
        : 1,
  );
  const average = $derived(snap?.round.results?.average ?? null);

  const status = $derived.by(() => {
    if (room.ended === "deleted") return "The owner deleted this room.";
    if (room.ended) return "This room no longer exists.";
    if (!snap) return "Connecting…";
    if (snap.backlog.state === "loading") return "Loading the backlog from Jira…";
    if (snap.backlog.state === "error") return "The backlog did not load.";
    if (!snap.ticket) return "All tickets in the queue are done.";
    return null;
  });
</script>

<section class="mini" aria-label="Mini room">
  {#if status || !snap || !snap.ticket}
    <p class="status" role="status">{status}</p>
  {:else}
    <div class="top">
      <div class="line">
        <span class="key">{snap.ticket.key}</span>
        <span class="time" class:up={countdown?.time_up} aria-label="Countdown"
          >{countdown?.time_up ? "Time's up" : clock(remaining ?? snap.timer_seconds)}</span
        >
      </div>
      <span class="summary">{snap.ticket.summary}</span>
    </div>

    <div class="bar" aria-hidden="true"><div style:width="{progress * 100}%"></div></div>

    {#if !snap.you.seated}
      <p class="status">
        {snap.check_in_open ? "The room was reset. Checking in…" : "You are not seated in this round."}
      </p>
    {:else if voting}
      <div class="cards" role="group" aria-label="Cards">
        {#each snap.scale.cards as card (card.label)}
          <button
            type="button"
            class="card"
            aria-pressed={snap.you.vote === card.label}
            aria-label={card.label === "?" ? "Not sure" : undefined}
            onclick={() => room.send({ type: "vote", card: card.label })}>{card.label}</button
          >
        {/each}
      </div>
    {:else}
      <p class="status">
        Cards revealed{average !== null ? ` · Average ${average.toFixed(1)}` : ""}
      </p>
    {/if}

    <div class="foot">
      <span class="count"
        >{room.status === "open" ? `${voted} of ${snap.players.length} voted` : "Reconnecting…"}</span
      >
      {#if snap.you.vote}
        <span class="mine">You voted {snap.you.vote}</span>
      {/if}
    </div>
  {/if}
</section>

<style>
  :global(body.mini-body) {
    min-height: 0;
    background: var(--table);
    overflow: hidden;
  }
  .mini {
    box-sizing: border-box;
    height: 100vh;
    padding: 12px 14px;
    background: var(--table);
    color: var(--on-table);
    font-size: 14px;
    line-height: 1.4;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    gap: 8px;
  }
  .top {
    display: flex;
    flex-direction: column;
    gap: 2px;
    min-width: 0;
  }
  .line,
  .foot {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: 10px;
  }
  .key {
    font-weight: 600;
    font-size: 15px;
  }
  .time {
    font-family: var(--font-display);
    font-weight: 700;
    font-size: 22px;
    line-height: 1;
    white-space: nowrap;
  }
  .summary {
    font-size: 13px;
    color: var(--on-table-2);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .bar {
    flex: none;
    height: 6px;
    border-radius: 999px;
    background: var(--table-line);
    overflow: hidden;
  }
  .bar > div {
    height: 100%;
    background: var(--on-table);
  }
  .cards {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(64px, 1fr));
    gap: 8px;
    overflow-y: auto;
    min-height: 0;
  }
  .card {
    height: 48px;
    padding: 0 4px;
    border: 2px solid var(--card-face);
    border-radius: 8px;
    background: var(--card-face);
    color: var(--ink);
    font-family: var(--font-display);
    font-weight: 700;
    font-size: 20px;
  }
  .card[aria-pressed="true"] {
    background: var(--accent);
    color: #ffffff;
  }
  .card:focus-visible {
    outline-color: var(--on-table);
  }
  .foot {
    font-size: 13px;
  }
  .count {
    color: var(--on-table-2);
  }
  .mine {
    font-weight: 600;
  }
  .status {
    margin: 0;
    color: var(--on-table);
  }
</style>
