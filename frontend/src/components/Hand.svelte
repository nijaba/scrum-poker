<script lang="ts">
  import { suitOf } from "../lib/cards";
  import { hideCard, setHideCard } from "../lib/hideCard.svelte";
  import type { Snapshot } from "../lib/types";
  import CardFace from "./CardFace.svelte";

  let {
    snap,
    onvote,
    onsit,
    onbreak,
    compact = false,
  }: {
    snap: Snapshot;
    /** In the phone dock: rows of five small cards, no panel around them. */
    compact?: boolean;
    onvote: (card: string) => void;
    /** Ask for a coffee break (true) or end it (false). Not a vote. */
    onbreak: (on: boolean) => void;
    /** Sit out (false) or join the table again (true). */
    onsit: (atTable: boolean) => void;
  } = $props();

  const kinds = { fibonacci: "Fibonacci", tshirt: "T-shirt sizes", custom: "Custom cards" };
  const voting = $derived(snap.round.state === "voting");
  // Hide my card: the chosen card is drawn like the others (design.md, "Sharing your screen").
  // Not in the phone dock, which is not the screen being shared.
  const hiding = $derived(hideCard.on && !compact);

  // Up to a dozen cards fan out like a hand; longer custom scales lie in a plain row.
  const FAN_MAX = 12;
  const fan = $derived(!compact && snap.scale.cards.length <= FAN_MAX);
  function angle(i: number, n: number): number {
    const step = Math.min(3, 30 / Math.max(1, n - 1));
    return (i - (n - 1) / 2) * step;
  }
  function drop(i: number, n: number): number {
    const d = i - (n - 1) / 2;
    return d * d * Math.min(0.9, 25 / Math.max(1, ((n - 1) / 2) ** 2));
  }
</script>

<section class="panel hand" class:compact aria-label="Your card" data-tour="hand">
  {#if snap.you.sitting_out}
    <div class="head">
      <span class="panel-title">You are watching</span>
      <button class="btn" type="button" onclick={() => onsit(true)}>Join the table</button>
    </div>
    <span class="note">You are not at the table, so the voted count doesn't wait for you.</span>
  {:else if voting}
    <div class="head">
      <span class="panel-title">Your card</span>
      <span class="note"
        >{compact
          ? "hidden until reveal"
          : hiding
            ? snap.you.vote
              ? "Card chosen · hidden on this screen until reveal"
              : `${kinds[snap.scale.kind]} · your choice stays hidden on this screen`
            : `${kinds[snap.scale.kind]} · hidden from others until reveal`}</span
      >
      <span class="actions">
        {#if !compact}
          <button
            class="btn hide"
            type="button"
            aria-pressed={hideCard.on}
            title="Keep your card off this screen until the reveal, for when you share it"
            onclick={() => setHideCard(!hideCard.on)}
            ><svg aria-hidden="true" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10.7 5.1A10 10 0 0 1 12 5c6.5 0 10 7 10 7a17.6 17.6 0 0 1-2.2 3.2"></path><path d="M6.6 6.6C3.9 8.4 2 12 2 12s3.5 7 10 7a9.7 9.7 0 0 0 5.4-1.6"></path><path d="M9.9 9.9a3 3 0 0 0 4.2 4.2"></path><path d="m2 2 20 20"></path></svg>
            Hide my card</button
          >
        {/if}
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
          class:shown={snap.you.vote === card.label && !hiding}
          style:--r="{angle(i, snap.scale.cards.length)}deg"
          style:--y="{drop(i, snap.scale.cards.length)}px"
          aria-pressed={snap.you.vote === card.label}
          aria-label={card.label === "?" ? "Not sure" : card.label}
          onclick={() => onvote(card.label)}
          ><CardFace label={card.label} {suit} {compact} /></button
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
  .hide {
    display: inline-flex;
    align-items: center;
    gap: 6px;
  }
  .hide[aria-pressed="true"],
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
  .card.shown {
    z-index: 3;
    border: 2px solid var(--accent);
    box-shadow:
      0 0 0 3px color-mix(in srgb, var(--accent) 22%, transparent),
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
  .fan .card.shown {
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
    .fan .card.shown {
      transform: translateY(-10px);
    }
  }
  /* The phone dock: no panel, rows of five cards that fill the width. */
  .compact {
    padding: 0;
    border: none;
    border-radius: 0;
    background: none;
    gap: 8px;
  }
  .compact .head {
    align-items: center;
    flex-wrap: nowrap;
  }
  .compact .note {
    flex: 1;
    min-width: 0;
  }
  .compact .actions {
    flex-wrap: nowrap;
    gap: 6px;
  }
  .compact .sit,
  .compact .coffee {
    min-height: 40px;
    padding: 0 10px;
    font-size: 13px;
  }
  .compact .cards {
    display: grid;
    grid-template-columns: repeat(5, minmax(0, 1fr));
    gap: 8px;
    padding-top: 10px;
  }
  .compact .card {
    min-width: 0;
    height: 60px;
    padding: 0 4px;
  }
  .compact .card.shown {
    transform: translateY(-8px);
  }
  @media (prefers-reduced-motion: reduce) {
    .card {
      transition: none;
    }
  }
</style>
