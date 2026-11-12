<script lang="ts">
  import { clock } from "../lib/format";
  import type { Snapshot } from "../lib/types";

  let {
    snap,
    remaining,
    showCountdown,
    onremove,
  }: {
    snap: Snapshot;
    remaining: number | null;
    showCountdown: boolean;
    /** Facilitators get a remove button on each seat. */
    onremove?: (playerId: string) => void;
  } = $props();

  const revealed = $derived(snap.round.state !== "voting");
  const voted = $derived(snap.players.filter((p) => p.voted).length);
  const results = $derived(snap.round.results);
  const most = $derived(Math.max(1, ...(results?.spread ?? []).map((s) => s.count)));

  function mark(card: string | null | undefined): "Highest" | "Lowest" | null {
    if (!revealed || !results || card == null) return null;
    if (card === results.high) return "Highest";
    if (card === results.low) return "Lowest";
    return null;
  }
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
          {#if onremove}
            <button
              class="remove"
              type="button"
              aria-label="Remove {p.name}"
              title="Remove from the table"
              onclick={() => onremove(p.id)}
            >
              <svg aria-hidden="true" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><path d="M6 6l12 12M18 6L6 18"></path></svg>
            </button>
          {/if}
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
          {#if mark(p.card)}
            <span class="mark" class:high={mark(p.card) === "Highest"}>{mark(p.card)}</span>
          {/if}
          {#if !revealed}
            <span class="status">{p.connected ? (p.voted ? "Voted" : "Thinking") : "Away"}</span>
          {/if}
        </li>
      {/each}
    </ul>
  {/if}

  {#if snap.watchers.length}
    <p class="watchers">Watching: {snap.watchers.map((w) => w.name).join(", ")}</p>
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
    {#if results.spread.length}
      <ul class="spread" aria-label="Vote spread">
        {#each results.spread as s (s.label)}
          <li aria-label="{s.label}: {s.count} {s.count === 1 ? 'vote' : 'votes'}">
            <span class="spread-label" aria-hidden="true">{s.label}</span>
            <span class="spread-bar" aria-hidden="true"
              ><span
                style:width="{(s.count / most) * 100}%"
                class:high={s.label === results.high}
                class:low={s.label === results.low}
              ></span></span
            >
            <span class="spread-count" aria-hidden="true">{s.count}</span>
          </li>
        {/each}
      </ul>
    {/if}
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
    position: relative;
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
  .remove {
    position: absolute;
    top: -12px;
    right: calc(50% - 54px);
    width: 44px;
    height: 44px;
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1;
    border: none;
    background: none;
    color: var(--on-table-2);
    opacity: 0;
  }
  .remove::before {
    content: "";
    position: absolute;
    width: 24px;
    height: 24px;
    border-radius: 50%;
    background: var(--table-line);
    z-index: -1;
  }
  .seat:hover .remove,
  .remove:focus-visible {
    opacity: 1;
  }
  @media (hover: none) {
    .remove {
      opacity: 1;
    }
  }
  .remove:hover {
    color: #ffffff;
  }
  .mark {
    font-size: 12px;
    font-weight: 600;
    padding: 1px 8px;
    border-radius: 999px;
    background: var(--table-line);
    color: var(--on-table);
  }
  .mark.high {
    background: #ffd9b8;
    color: var(--ink);
  }
  .watchers {
    margin: 0;
    font-size: 14px;
    color: var(--on-table-2);
  }
  .spread {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 6px;
  }
  .spread li {
    display: grid;
    grid-template-columns: 40px 1fr 28px;
    align-items: center;
    gap: 10px;
    font-size: 14px;
  }
  .spread-label {
    font-family: var(--font-display);
    font-weight: 700;
    text-align: right;
  }
  .spread-bar {
    height: 10px;
    border-radius: 999px;
    background: var(--table-line);
    overflow: hidden;
  }
  .spread-bar > span {
    display: block;
    height: 100%;
    border-radius: 999px;
    background: var(--on-table-2);
  }
  .spread-bar > span.high {
    background: #ffd9b8;
  }
  .spread-bar > span.low {
    background: var(--card-back);
  }
  .spread-count {
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
