<script lang="ts">
  import { clock } from "../lib/format";
  import type { Snapshot } from "../lib/types";

  let {
    snap,
    remaining,
    showCountdown,
  }: { snap: Snapshot; remaining: number | null; showCountdown: boolean } = $props();

  const revealed = $derived(snap.round.state !== "voting");
  const voted = $derived(snap.players.filter((p) => p.voted).length);
  const results = $derived(snap.round.results);
</script>

<section class="table" aria-label={revealed ? "Players and results" : "Players"}>
  <div class="head">
    <span class="state">{revealed ? "Cards revealed" : "Voting open"}</span>
    {#if showCountdown && remaining !== null}
      <span class="countdown" class:up={snap.countdown.time_up} aria-label="Countdown">
        {snap.countdown.time_up ? "Time's up" : clock(remaining)}
      </span>
    {/if}
    <span class="count">{voted} of {snap.players.length} voted</span>
  </div>

  {#if snap.players.length === 0}
    <p class="empty">Nobody is seated yet.</p>
  {:else}
    <ul class="seats">
      {#each snap.players as p (p.id)}
        <li class="seat" class:away={!p.connected} data-player={p.name}>
          {#if revealed}
            {#if p.card != null}
              <div class="card face" aria-label="{p.name} played {p.card}">{p.card}</div>
            {:else}
              <div class="card slot" aria-label="{p.name} did not vote"></div>
            {/if}
          {:else if p.voted}
            <div class="card back" aria-label="{p.name} has voted"><div></div></div>
          {:else}
            <div class="card slot" aria-label="{p.name} has not voted"></div>
          {/if}
          <span class="name">{p.name}</span>
          {#if !revealed}
            <span class="status">{p.connected ? (p.voted ? "Voted" : "Thinking") : "Away"}</span>
          {/if}
        </li>
      {/each}
    </ul>
  {/if}

  {#if revealed && results}
    <div class="results" aria-label="Results">
      <div class="figure">
        <span class="figure-label">Average</span>
        <span class="figure-value" data-figure="average"
          >{results.average === null ? "–" : results.average.toFixed(1)}</span
        >
      </div>
      <div class="figure">
        <span class="figure-label">Median</span>
        <span class="figure-value" data-figure="median">{results.median ?? "–"}</span>
      </div>
      <div class="figure">
        <span class="figure-label">Consensus</span>
        {#if results.votes === 0}
          <span class="figure-text" data-figure="consensus">No votes</span>
        {:else if results.consensus && results.top}
          <span class="figure-text" data-figure="consensus">Consensus on {results.top.label}</span>
        {:else if results.top}
          <span class="figure-text" data-figure="consensus">No consensus</span>
          <span class="figure-sub"
            >Most chosen: {results.top.label} ({results.top.count} of {results.votes})</span
          >
        {/if}
      </div>
    </div>
  {/if}
</section>

<style>
  .table {
    background: var(--table);
    color: var(--on-table);
    border-radius: 14px;
    padding: 20px 24px;
    display: flex;
    flex-direction: column;
    gap: 18px;
  }
  .head {
    display: flex;
    flex-wrap: wrap;
    align-items: baseline;
    gap: 8px 16px;
  }
  .state {
    font-family: var(--font-display);
    font-weight: 700;
    font-size: 18px;
  }
  .countdown {
    font-family: var(--font-display);
    font-weight: 700;
    font-size: 18px;
    color: #ffd9b8;
  }
  .countdown.up {
    color: var(--on-table);
  }
  .count {
    margin-left: auto;
    font-size: 14px;
    color: var(--on-table-2);
  }
  .empty {
    margin: 0;
    color: var(--on-table-2);
  }
  .seats {
    list-style: none;
    margin: 0;
    padding: 0;
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(min(110px, 100%), 1fr));
    gap: 16px;
  }
  .seat {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 8px;
  }
  .seat.away {
    opacity: 0.6;
  }
  .card {
    width: 64px;
    height: 88px;
    box-sizing: border-box;
    border-radius: 8px;
  }
  .back {
    background: var(--card-back);
    padding: 6px;
  }
  .back > div {
    width: 100%;
    height: 100%;
    box-sizing: border-box;
    border: 2px solid var(--table);
    border-radius: 4px;
  }
  .slot {
    border: 2px dashed var(--empty-slot);
  }
  .face {
    background: var(--card-face);
    color: var(--ink);
    display: flex;
    align-items: center;
    justify-content: center;
    font-family: var(--font-display);
    font-weight: 700;
    font-size: 30px;
  }
  .name {
    font-size: 14px;
    font-weight: 600;
    text-align: center;
    overflow-wrap: anywhere;
  }
  .status {
    font-size: 12px;
    color: var(--on-table-2);
  }
  .results {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(min(180px, 100%), 1fr));
    gap: 16px;
    padding-top: 18px;
    border-top: 1px solid var(--table-line);
  }
  .figure {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }
  .figure-label {
    font-size: 13px;
    color: var(--on-table-2);
  }
  .figure-value {
    font-family: var(--font-display);
    font-weight: 700;
    font-size: 38px;
    line-height: 1.1;
  }
  .figure-text {
    font-family: var(--font-display);
    font-weight: 700;
    font-size: 22px;
    line-height: 1.3;
  }
  .figure-sub {
    font-size: 14px;
    color: var(--on-table-2);
  }
</style>
