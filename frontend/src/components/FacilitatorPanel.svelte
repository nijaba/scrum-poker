<script lang="ts">
  import { clock } from "../lib/format";
  import { downloadCsv, summaryText } from "../lib/summary";
  import type { Snapshot } from "../lib/types";
  import FinalPoints from "./FinalPoints.svelte";

  let {
    snap,
    remaining,
    send,
    docked = false,
  }: {
    snap: Snapshot;
    remaining: number | null;
    send: (message: Record<string, unknown>) => void;
    /** On a phone, in the more-controls sheet: Reveal and the final points are in the dock. */
    docked?: boolean;
  } = $props();

  const voting = $derived(snap.round.state === "voting");
  const countdown = $derived(snap.countdown);
  const progress = $derived(
    countdown.running && countdown.duration && remaining !== null
      ? Math.max(0, Math.min(1, remaining / countdown.duration))
      : countdown.time_up
        ? 0
        : 1,
  );

  let seconds = $state(30);
  // Follow the room's timer setting when it changes.
  $effect(() => {
    seconds = snap.timer_seconds;
  });

  function setTimer() {
    if (Number.isFinite(seconds) && seconds >= 1 && seconds <= 3600) {
      send({ type: "set_timer", seconds });
    }
  }

  const summary = $derived(snap.summary ?? []);
  const estimatedCount = $derived(summary.filter((e) => e.status === "estimated").length);
  const skippedCount = $derived(summary.length - estimatedCount);
  let copied = $state(false);

  async function copySummary() {
    try {
      await navigator.clipboard.writeText(summaryText(snap.room.slug, summary));
      copied = true;
      setTimeout(() => (copied = false), 2000);
    } catch {
      copied = false;
    }
  }

</script>

<aside class="facilitator" aria-label="Facilitator panel">
  <section class="panel" aria-label="Countdown" data-tour="countdown">
    <div class="head">
      <span class="panel-title">Countdown</span>
      <span class="note"
        >{countdown.running ? "Running" : countdown.time_up ? "Time's up" : "Ready"}</span
      >
    </div>
    <div class="time" class:running={countdown.running} data-testid="countdown-time">
      {clock(remaining ?? seconds)}
    </div>
    <div class="bar" aria-hidden="true"><div style:width="{progress * 100}%"></div></div>
    <div class="row">
      <div class="field">
        <label for="countdown-seconds">Seconds</label>
        <input
          id="countdown-seconds"
          type="number"
          min="1"
          max="3600"
          bind:value={seconds}
          onchange={setTimer}
        />
      </div>
      {#if countdown.running}
        <button class="btn" type="button" onclick={() => send({ type: "stop_countdown" })}
          >Stop</button
        >
      {:else}
        <button
          class="btn"
          type="button"
          disabled={!voting || !snap.ticket}
          onclick={() => send({ type: "start_countdown" })}>Start</button
        >
      {/if}
      <button
        class="btn sound"
        type="button"
        aria-pressed={snap.sound}
        onclick={() => send({ type: "set_sound", on: !snap.sound })}
      >
        <svg aria-hidden="true" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 9v6h4l5 4V5L8 9z"></path>{#if snap.sound}<path d="M16.5 8.5a5 5 0 0 1 0 7"></path>{/if}</svg>
        <span>{snap.sound ? "Sound on" : "Sound off"}</span>
      </button>
    </div>
  </section>

  {#if !voting && snap.ticket && !docked}
    <FinalPoints {snap} {send} />
  {/if}

  <section class="panel" aria-label="Facilitator controls" data-tour="reveal">
    <span class="panel-title">Facilitator controls</span>
    {#if voting && !docked}
      <button
        class="btn-primary"
        type="button"
        disabled={!snap.ticket}
        onclick={() => send({ type: "reveal" })}>Reveal cards</button
      >
    {/if}
    <div class="grid" data-tour="round">
      <!-- Back and forward through the queue, side by side: « Rewind, Skip ». -->
      <button
        class="btn step"
        type="button"
        disabled={snap.queue.length === 0 || (snap.queue.position <= 1 && !snap.queue.finished)}
        onclick={() => send({ type: "rewind" })}
      >
        <svg aria-hidden="true" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.25" stroke-linecap="round" stroke-linejoin="round"><path d="m11 17-5-5 5-5"></path><path d="m18 17-5-5 5-5"></path></svg>
        Rewind
      </button>
      <button
        class="btn step"
        type="button"
        disabled={!snap.ticket}
        onclick={() => send({ type: "skip" })}
      >
        Skip
        <svg aria-hidden="true" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.25" stroke-linecap="round" stroke-linejoin="round"><path d="m13 17 5-5-5-5"></path><path d="m6 17 5-5-5-5"></path></svg>
      </button>
      <button class="btn" type="button" onclick={() => send({ type: "restart" })}
        >Restart vote</button
      >
      <button class="btn" type="button" onclick={() => send({ type: "reset" })}>Reset room</button>
      <button
        class="btn"
        type="button"
        disabled={!snap.demo && !snap.queue.finished && !(voting && !snap.players.some((p) => p.voted))}
        title="Load the backlog again, with the room's saved queue filter"
        onclick={() => send({ type: "reload_backlog" })}>Reload backlog</button
      >
    </div>
    {#if snap.backlog.filter_changed}
      <p class="note" role="status">
        The queue filter changed. Reload the backlog to apply it{snap.queue.finished || (voting && !snap.players.some((p) => p.voted))
          ? "."
          : " once this ticket is done."}
      </p>
    {/if}
    <button
      class="btn toggle"
      type="button"
      data-tour="auto-reveal"
      aria-pressed={snap.auto_reveal}
      onclick={() => send({ type: "set_auto_reveal", on: !snap.auto_reveal })}
    >
      <span class="switch" aria-hidden="true"></span>
      <span>Auto-reveal when everyone has voted</span>
    </button>
    {#if voting && !docked}
      <button class="btn" type="button" disabled>Confirm points</button>
      <span class="note">Confirm becomes available after reveal.</span>
    {/if}
  </section>

  {#if snap.up_next.length}
    <section class="panel" aria-label="Up next">
      <span class="panel-title">Up next</span>
      <ul class="next">
        {#each snap.up_next as t (t.key)}
          <li>
            <button
              class="next-item"
              type="button"
              aria-label="Go to {t.key}"
              title="Go to this ticket"
              onclick={() => send({ type: "jump", key: t.key })}
            >
              <span class="next-key">{t.key}</span><span class="next-summary">{t.summary}</span>
            </button>
          </li>
        {/each}
      </ul>
    </section>
  {/if}

  <section class="panel" aria-label="Session summary" data-tour="summary">
    <div class="head">
      <span class="panel-title">Session summary</span>
      <span class="note">
        {summary.length ? `${estimatedCount} estimated · ${skippedCount} skipped` : "Nothing yet"}
      </span>
    </div>
    <div class="actions">
      <button class="btn" type="button" disabled={!summary.length} onclick={copySummary}
        >{copied ? "Copied" : "Copy summary"}</button
      >
      <button
        class="btn"
        type="button"
        disabled={!summary.length}
        onclick={() => downloadCsv(snap.room.slug, summary)}>Download CSV</button
      >
    </div>
    <span class="note">Tickets, points and vote counts from this session. Not stored.</span>
  </section>
</aside>

<style>
  .facilitator {
    flex: 1 1 300px;
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 16px;
  }
  .head {
    display: flex;
    flex-wrap: wrap;
    align-items: baseline;
    justify-content: space-between;
    gap: 2px 8px;
  }
  .time {
    font-family: var(--font-display);
    font-weight: 700;
    font-size: 60px;
    line-height: 1;
  }
  .time.running {
    color: var(--accent);
  }
  .bar {
    height: 8px;
    border-radius: 999px;
    background: var(--chip);
    overflow: hidden;
  }
  .bar > div {
    height: 100%;
    background: var(--accent);
  }
  .row {
    display: flex;
    flex-wrap: wrap;
    align-items: flex-end;
    gap: 10px;
  }
  .field {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }
  label {
    font-size: 13px;
    color: var(--text-3);
  }
  input {
    width: 84px;
    height: 44px;
    box-sizing: border-box;
    padding: 0 10px;
    border: 1px solid var(--border-strong);
    border-radius: 8px;
    background: var(--surface);
  }
  .btn {
    font-weight: 600;
  }
  .sound {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 0 12px;
    font-size: 14px;
    font-weight: 400;
  }
  .grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 10px;
  }
  .actions {
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
  }
  .actions .btn {
    flex: 1 1 auto;
    white-space: nowrap;
  }
  .grid .btn {
    font-weight: 500;
  }
  .step {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
  }
  .next {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 0;
    font-size: 14px;
  }
  .next-item {
    display: flex;
    gap: 10px;
    width: calc(100% + 16px);
    min-height: 44px;
    padding: 4px 8px;
    margin: 0 -8px;
    box-sizing: border-box;
    border: none;
    border-radius: 8px;
    background: none;
    text-align: left;
    align-items: center;
  }
  .next-item:hover {
    background: var(--chip);
  }
  .next-key {
    font-weight: 600;
    white-space: nowrap;
  }
  .next-summary {
    color: var(--text-2);
  }
  .toggle {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 8px 14px;
    font-weight: 500;
    text-align: left;
    line-height: 1.3;
  }
  .toggle[aria-pressed="true"] {
    background: var(--surface);
  }
  .switch {
    flex: none;
    position: relative;
    width: 32px;
    height: 18px;
    border-radius: 999px;
    background: var(--border-strong);
  }
  .switch::after {
    content: "";
    position: absolute;
    top: 2px;
    left: 2px;
    width: 14px;
    height: 14px;
    border-radius: 50%;
    background: #ffffff;
    transition: left 0.12s ease;
  }
  .toggle[aria-pressed="true"] .switch {
    background: var(--accent);
  }
  .toggle[aria-pressed="true"] .switch::after {
    left: 16px;
  }
  @media (prefers-reduced-motion: reduce) {
    .switch::after {
      transition: none;
    }
  }
</style>
