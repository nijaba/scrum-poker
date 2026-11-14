<script lang="ts">
  import { suitOf } from "../lib/cards";
  import type { Snapshot } from "../lib/types";
  import CardFace from "./CardFace.svelte";

  let {
    snap,
    onvote,
    onsit,
    onbreak,
  }: {
    snap: Snapshot;
    onvote: (card: string) => void;
    /** Ask for a coffee break (true) or end it (false). Not a vote. */
    onbreak: (on: boolean) => void;
    /** Sit out (false) or join the table again (true). */
    onsit: (atTable: boolean) => void;
  } = $props();

  const kinds = { fibonacci: "Fibonacci", tshirt: "T-shirt sizes", custom: "Custom cards" };
  const voting = $derived(snap.round.state === "voting");

  // Up to a dozen cards fan out like a hand; longer custom scales lie in a plain row.
  const FAN_MAX = 12;
  const fan = $derived(snap.scale.cards.length <= FAN_MAX);
  function angle(i: number, n: number): number {
    const step = Math.min(3, 30 / Math.max(1, n - 1));
    return (i - (n - 1) / 2) * step;
  }
  function drop(i: number, n: number): number {
    const d = i - (n - 1) / 2;
    return d * d * Math.min(0.9, 25 / Math.max(1, ((n - 1) / 2) ** 2));
  }
</script>

<section class="panel hand" aria-label="Your card">
  {#if snap.you.sitting_out}
    <div class="head">
      <span class="panel-title">You are watching</span>
      <button class="btn" type="button" onclick={() => onsit(true)}>Join the table</button>
    </div>
    <span class="note">You are not at the table, so the voted count doesn't wait for you.</span>
  {:else if voting}
    <div class="head">
      <span class="panel-title">Your card</span>
      <span class="note">{kinds[snap.scale.kind]} · hidden from others until reveal</span>
      <span class="actions">
        <button
          class="btn coffee"
          type="button"
          aria-pressed={snap.you.on_break}
          title={snap.you.on_break ? "End your break" : "Ask for a coffee break"}
          onclick={() => onbreak(!snap.you.on_break)}
          ><span aria-hidden="true">☕</span> Coffee break</button
        >
        <button class="btn sit" type="button" onclick={() => onsit(false)}>Sit out</button>
      </span>
    </div>
    <div class="cards" class:fan style:--n={snap.scale.cards.length}>
      {#each snap.scale.cards as card, i (card.label)}
        {@const suit = suitOf(snap.scale.cards, card.label)}
        <button
          type="button"
          class="card deck-card"
          class:red={suit?.red}
          style:--r="{angle(i, snap.scale.cards.length)}deg"
          style:--y="{drop(i, snap.scale.cards.length)}px"
          aria-pressed={snap.you.vote === card.label}
          aria-label={card.label === "?" ? "Not sure" : card.label}
          onclick={() => onvote(card.label)}
          ><CardFace label={card.label} {suit} /></button
        >
      {/each}
    </div>
  {:else}
    <span class="panel-title">
      {snap.you.vote ? `You voted ${snap.you.vote}` : "You did not vote"}
    </span>
    <span class="note">Voting is closed until the facilitator restarts or moves on.</span>
    <button class="btn sit" type="button" onclick={() => onsit(false)}>Sit out</button>
  {/if}
</section>

<style>
  .hand {
    gap: 14px;
  }
  .head {
    display: flex;
    flex-wrap: wrap;
    align-items: baseline;
    justify-content: space-between;
    gap: 8px;
  }
  .actions {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin-left: auto;
  }
  .sit,
  .coffee {
    font-size: 14px;
  }
  .coffee[aria-pressed="true"] {
    border-color: var(--accent);
    background: var(--chip);
  }
  .hand > .sit {
    align-self: flex-start;
    margin-left: 0;
  }
  .cards {
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
    padding-top: 14px;
  }
  .card {
    min-width: 66px;
    height: 92px;
    padding: 0 8px;
    transition:
      transform 0.16s ease,
      box-shadow 0.16s ease;
  }
  .card:hover {
    transform: translateY(-4px);
    box-shadow: var(--card-shadow-up);
  }
  /* The chosen card rises and gets an accent edge, so it never relies on colour alone. */
  .card[aria-pressed="true"] {
    z-index: 3;
    border: 2px solid var(--accent);
    box-shadow:
      0 0 0 3px rgba(168, 75, 10, 0.18),
      var(--card-shadow-up);
    transform: translateY(-10px);
  }

  /* A fan: cards overlap, each keeping its top-left index in view, on a gentle arc. */
  .fan {
    flex-wrap: nowrap;
    justify-content: center;
    gap: 0;
    padding: 24px 8px 4px;
  }
  .fan .card {
    transform-origin: 50% 140%;
    transform: rotate(var(--r)) translateY(var(--y));
  }
  /* Overlap 12px, or more when the panel is narrow, up to 40px. */
  .fan .card + .card {
    margin-left: max(-40px, min(-12px, calc((100% - var(--n) * 66px) / (var(--n) - 1))));
  }
  .fan .card:hover {
    z-index: 2;
    transform: rotate(var(--r)) translateY(calc(var(--y) - 8px));
  }
  .fan .card[aria-pressed="true"] {
    z-index: 3;
    transform: translateY(calc(var(--y) - 20px));
  }
  /* On a narrow screen a plain wrapping row keeps every card easy to tap. */
  @media (max-width: 640px) {
    .fan {
      flex-wrap: wrap;
      justify-content: flex-start;
      gap: 10px;
      padding: 14px 0 0;
    }
    .fan .card + .card {
      margin-left: 0;
    }
    .fan .card {
      transform: none;
    }
    .fan .card:hover {
      transform: translateY(-4px);
    }
    .fan .card[aria-pressed="true"] {
      transform: translateY(-10px);
    }
  }
  @media (prefers-reduced-motion: reduce) {
    .card {
      transition: none;
    }
  }
</style>
