<script lang="ts">
  import type { Snapshot } from "../lib/types";

  let { snap, onvote }: { snap: Snapshot; onvote: (card: string) => void } = $props();

  const kinds = { fibonacci: "Fibonacci", tshirt: "T-shirt sizes", custom: "Custom cards" };
  const voting = $derived(snap.round.state === "voting");
</script>

<section class="panel hand" aria-label="Your card">
  {#if voting}
    <div class="head">
      <span class="panel-title">Your card</span>
      <span class="note">{kinds[snap.scale.kind]} · hidden from others until reveal</span>
    </div>
    <div class="cards">
      {#each snap.scale.cards as card (card.label)}
        <button
          type="button"
          class="card"
          aria-pressed={snap.you.vote === card.label}
          aria-label={card.label === "?" ? "Not sure" : undefined}
          onclick={() => onvote(card.label)}>{card.label}</button
        >
      {/each}
    </div>
  {:else}
    <span class="panel-title">
      {snap.you.vote ? `You voted ${snap.you.vote}` : "You did not vote"}
    </span>
    <span class="note">Voting is closed until the facilitator restarts or moves on.</span>
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
  .cards {
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
    padding-top: 6px;
  }
  .card {
    min-width: 60px;
    height: 84px;
    padding: 0 6px;
    border: 1.5px solid var(--border-strong);
    border-radius: 8px;
    background: var(--surface);
    font-family: var(--font-display);
    font-weight: 700;
    font-size: 26px;
    transition: transform 0.12s ease;
  }
  .card[aria-pressed="true"] {
    border-color: var(--accent);
    background: var(--accent);
    color: #ffffff;
    transform: translateY(-6px);
  }
  @media (prefers-reduced-motion: reduce) {
    .card {
      transition: none;
    }
  }
</style>
