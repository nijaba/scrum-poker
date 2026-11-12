<script lang="ts">
  import { clock, points } from "../lib/format";
  import type { Card, Snapshot } from "../lib/types";

  let {
    snap,
    remaining,
    send,
  }: {
    snap: Snapshot;
    remaining: number | null;
    send: (message: Record<string, unknown>) => void;
  } = $props();

  const voting = $derived(snap.round.state === "voting");
  const countdown = $derived(snap.countdown);
  const numeric = $derived(snap.scale.cards.filter((c) => c.value !== null));
  const progress = $derived(
    countdown.running && countdown.duration && remaining !== null
      ? Math.max(0, Math.min(1, remaining / countdown.duration))
      : countdown.time_up
        ? 0
        : 1,
  );

  let seconds = $state(30);
  let chosen = $state<string | null>(null);
  let confirming = $state(false);

  // Follow the room's timer setting when it changes.
  $effect(() => {
    seconds = snap.timer_seconds;
  });

  // Each new round starts with the most-chosen card picked, or the card nearest the median.
  $effect(() => {
    void snap.ticket?.key;
    void snap.round.state;
    chosen = defaultChoice(snap, numeric);
  });

  // A new snapshot means the confirm finished, one way or the other.
  $effect(() => {
    void snap;
    confirming = false;
  });

  function defaultChoice(s: Snapshot, cards: Card[]): string | null {
    const results = s.round.results;
    if (!results) return null;
    const top = cards.find((c) => c.label === results.top?.label);
    if (top) return top.label;
    if (results.median === null || cards.length === 0) return null;
    const median = results.median;
    return cards.reduce((best, c) =>
      Math.abs((c.value ?? 0) - median) < Math.abs((best.value ?? 0) - median) ? c : best,
    ).label;
  }

  const chosenCard = $derived(numeric.find((c) => c.label === chosen) ?? null);
  const confirmLabel = $derived.by(() => {
    if (!chosenCard || chosenCard.value === null) return "Confirm points";
    if (chosenCard.label === String(chosenCard.value)) return `Confirm ${points(chosenCard.value)}`;
    return `Confirm ${chosenCard.label} (${points(chosenCard.value)})`;
  });

  function setTimer() {
    if (Number.isFinite(seconds) && seconds >= 1 && seconds <= 3600) {
      send({ type: "set_timer", seconds });
    }
  }

  function confirm() {
    if (!chosenCard) return;
    confirming = true;
    send({ type: "confirm", points: chosenCard.label });
    setTimeout(() => (confirming = false), 10_000);
  }
</script>

<aside class="facilitator" aria-label="Facilitator panel">
  <section class="panel" aria-label="Countdown">
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

  {#if !voting && snap.ticket}
    <section class="panel" aria-label="Final points">
      <span class="panel-title">Final story points</span>
      <div class="picks">
        {#each numeric as card (card.label)}
          <button
            class="pick"
            type="button"
            aria-pressed={chosen === card.label}
            onclick={() => (chosen = card.label)}>{card.label}</button
          >
        {/each}
      </div>
      <button
        class="btn-primary"
        type="button"
        disabled={!chosenCard || confirming}
        onclick={confirm}>{confirming ? "Writing to Jira…" : confirmLabel}</button
      >
      {#if chosenCard && chosenCard.value !== null}
        <span class="note">
          Writes {chosenCard.value} to {snap.ticket.key} in Jira, then loads {snap.up_next[0]
            ?.key ?? "the end of the queue"}.
        </span>
      {/if}
    </section>
  {/if}

  <section class="panel" aria-label="Facilitator controls">
    <span class="panel-title">Facilitator controls</span>
    {#if voting}
      <button
        class="btn-primary"
        type="button"
        disabled={!snap.ticket}
        onclick={() => send({ type: "reveal" })}>Reveal cards</button
      >
    {/if}
    <div class="grid">
      <button class="btn" type="button" onclick={() => send({ type: "restart" })}
        >Restart vote</button
      >
      <button
        class="btn"
        type="button"
        disabled={!snap.ticket}
        onclick={() => send({ type: "skip" })}>Skip</button
      >
      <button
        class="btn"
        type="button"
        disabled={snap.queue.length === 0 || (snap.queue.position <= 1 && !snap.queue.finished)}
        onclick={() => send({ type: "rewind" })}>Rewind</button
      >
      <button class="btn" type="button" onclick={() => send({ type: "reset" })}>Reset room</button>
    </div>
    {#if voting}
      <button class="btn" type="button" disabled>Confirm points</button>
      <span class="note">Confirm becomes available after reveal.</span>
    {/if}
  </section>

  {#if snap.up_next.length}
    <section class="panel" aria-label="Up next">
      <span class="panel-title">Up next</span>
      <ul class="next">
        {#each snap.up_next as t (t.key)}
          <li><span class="next-key">{t.key}</span><span>{t.summary}</span></li>
        {/each}
      </ul>
    </section>
  {/if}
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
    align-items: baseline;
    justify-content: space-between;
    gap: 8px;
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
  .picks {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }
  .pick {
    min-width: 44px;
    height: 44px;
    padding: 0 8px;
    border: 1.5px solid var(--border-strong);
    border-radius: 8px;
    background: var(--surface);
    font-family: var(--font-display);
    font-weight: 700;
    font-size: 17px;
  }
  .pick[aria-pressed="true"] {
    border-color: var(--accent);
    background: var(--accent);
    color: #ffffff;
  }
  .grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 10px;
  }
  .grid .btn {
    font-weight: 500;
  }
  .next {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 8px;
    font-size: 14px;
  }
  .next li {
    display: flex;
    gap: 10px;
  }
  .next-key {
    font-weight: 600;
    white-space: nowrap;
  }
  .next li span:last-child {
    color: var(--text-2);
  }
</style>
