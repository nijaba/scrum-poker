<script lang="ts">
  /**
   * Remote view: a player's phone as a remote while the session is on a shared
   * screen. Large cards to vote, then their card beside the most-chosen one.
   * design.md, "Phones".
   */
  import { suitOf } from "../lib/cards";
  import { clock } from "../lib/format";
  import type { Snapshot } from "../lib/types";
  import CardFace from "./CardFace.svelte";

  let {
    snap,
    remaining,
    onvote,
    onsit,
    onbreak,
  }: {
    snap: Snapshot;
    remaining: number | null;
    onvote: (card: string) => void;
    onsit: (atTable: boolean) => void;
    onbreak: (on: boolean) => void;
  } = $props();

  const voting = $derived(snap.round.state === "voting");
  const voted = $derived(snap.players.filter((p) => p.voted).length);
  const share = $derived(snap.players.length ? voted / snap.players.length : 0);
  const results = $derived(snap.round.results);
  const mine = $derived(snap.you.vote);
  const mark = $derived(
    !results || mine == null ? null : mine === results.high ? "highest" : mine === results.low ? "lowest" : null,
  );
</script>

<section class="remote" aria-label="Remote view">
  {#if snap.backlog.state !== "ready"}
    <h1>{snap.backlog.state === "loading" ? "Loading the backlog…" : "The backlog did not load"}</h1>
  {:else if !snap.ticket}
    <h1>All tickets in the queue are done.</h1>
  {:else}
    <div class="ticket">
      <span class="key">{snap.ticket.key} · Ticket {snap.queue.position} of {snap.queue.length}</span>
      <h1>{snap.ticket.summary}</h1>
    </div>

    <div class="progress">
      <div class="bar" aria-hidden="true"><div style:width="{share * 100}%"></div></div>
      <span
        >{voted} of {snap.players.length} voted{#if remaining !== null && voting}
          · {snap.countdown.time_up ? "Time's up" : clock(remaining)}{/if}</span
      >
    </div>

    {#if snap.you.sitting_out}
      <div class="message">
        <p>You are watching this round.</p>
        <button class="btn" type="button" onclick={() => onsit(true)}>Join the table</button>
      </div>
    {:else if voting}
      <div class="cards" aria-label="Your card">
        {#each snap.scale.cards as card (card.label)}
          {@const suit = suitOf(snap.scale.cards, card.label)}
          <button
            type="button"
            class="card deck-card"
            class:red={suit?.red}
            aria-pressed={mine === card.label}
            aria-label={card.label === "?" ? "Not sure" : card.label}
            onclick={() => onvote(card.label)}><CardFace label={card.label} {suit} compact /></button
          >
        {/each}
        <button
          type="button"
          class="side-btn"
          aria-pressed={snap.you.on_break}
          onclick={() => onbreak(!snap.you.on_break)}>Coffee break</button
        >
        <button type="button" class="side-btn" onclick={() => onsit(false)}>Sit out</button>
      </div>
      <p class="status" role="status">
        {mine ? `You played ${mine}. Tap another card to change it.` : "Pick a card. Nobody sees it until the reveal."}
      </p>
    {:else if results}
      <div class="reveal" aria-label="Results">
        <div class="pair">
          <div class="big">
            {#if mine}
              {@const suit = suitOf(snap.scale.cards, mine)}
              <div class="card deck-card mine" class:red={suit?.red} aria-label="Your card: {mine}">
                <CardFace label={mine} {suit} compact />
              </div>
            {:else}
              <div class="card slot" aria-label="You did not vote"></div>
            {/if}
            <span>Your card{mark ? ` · ${mark}` : ""}</span>
          </div>
          {#if results.top}
            {@const suit = suitOf(snap.scale.cards, results.top.label)}
            <div class="big">
              <div class="card deck-card" class:red={suit?.red} aria-label="Most chosen: {results.top.label}">
                <CardFace label={results.top.label} {suit} compact />
              </div>
              <span>{results.consensus ? "Consensus" : `Most chosen ×${results.top.count}`}</span>
            </div>
          {/if}
        </div>
        <div class="figures">
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
        </div>
        {#if mark}
          <p class="message">You played the {mark} card. Be ready to say why.</p>
        {/if}
      </div>
    {/if}
  {/if}
</section>

<style>
  .remote {
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: 16px;
    padding: 12px 20px 24px;
    background: var(--table);
    color: var(--on-table);
  }
  h1 {
    margin: 0;
    font-family: var(--font-display);
    font-weight: 700;
    font-size: 22px;
    line-height: 1.2;
  }
  .ticket {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }
  .key {
    font-size: 13px;
    font-weight: 600;
    color: var(--on-table-2);
  }
  .progress {
    display: flex;
    align-items: center;
    gap: 12px;
    font-size: 14px;
    color: var(--on-table-2);
  }
  .bar {
    flex: 1;
    height: 8px;
    border-radius: 999px;
    background: var(--table-line);
    overflow: hidden;
  }
  .bar > div {
    height: 100%;
    border-radius: 999px;
    background: var(--card-back);
  }
  .cards {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 12px;
  }
  .card {
    height: 96px;
    box-sizing: border-box;
    border-radius: 12px;
    font-size: 30px;
    transition: transform 0.16s ease;
  }
  .card[aria-pressed="true"] {
    border: 3px solid var(--accent);
    transform: translateY(-6px);
    box-shadow: var(--card-shadow-up);
  }
  .side-btn {
    min-height: 96px;
    border: 1.5px dashed var(--empty-slot);
    border-radius: 12px;
    background: none;
    color: var(--on-table);
    font-weight: 600;
  }
  .side-btn[aria-pressed="true"] {
    border-style: solid;
    border-color: var(--accent);
  }
  .status {
    margin: 0;
    text-align: center;
    font-weight: 600;
  }
  .message {
    margin: 0;
    padding: 12px 14px;
    border-radius: 10px;
    background: var(--table-line);
    display: flex;
    flex-direction: column;
    gap: 10px;
  }
  .message p {
    margin: 0;
  }
  .reveal {
    display: flex;
    flex-direction: column;
    gap: 20px;
  }
  .pair {
    display: flex;
    justify-content: center;
    gap: 28px;
  }
  .big {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 10px;
    font-size: 14px;
    font-weight: 600;
  }
  .big .card {
    width: 104px;
    height: 146px;
  }
  /* Large values: the card face sizes its pip for a small card. */
  .cards .card :global(.pip) {
    font-size: 34px;
  }
  .big .card :global(.pip) {
    font-size: 54px;
  }
  .mine {
    border: 3px solid var(--accent);
  }
  .slot {
    border: 2px dashed var(--empty-slot);
  }
  .figures {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 10px;
  }
  .figure {
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 10px;
    border-radius: 10px;
    background: var(--table-line);
  }
  .figure-label {
    font-size: 13px;
    color: var(--on-table);
  }
  .figure-value {
    font-family: var(--font-display);
    font-weight: 700;
    font-size: 28px;
  }
  @media (prefers-reduced-motion: reduce) {
    .card {
      transition: none;
    }
  }
</style>
