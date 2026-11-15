<script lang="ts">
  /**
   * The final points after reveal: a card to pick and Confirm. The facilitator panel
   * shows it on a wide screen, the dock on a phone (design.md, "Phones").
   */
  import type { Snippet } from "svelte";
  import { points } from "../lib/format";
  import type { Card, Snapshot } from "../lib/types";

  let {
    snap,
    send,
    docked = false,
    lead,
  }: {
    snap: Snapshot;
    send: (message: Record<string, unknown>) => void;
    /** In the phone dock: no title or note, to keep it short. */
    docked?: boolean;
    /** Drawn before Confirm on the same row: the dock's more-controls button. */
    lead?: Snippet;
  } = $props();

  const numeric = $derived(snap.scale.cards.filter((c) => c.value !== null));
  let chosen = $state<string | null>(null);
  let confirming = $state(false);

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

  function confirm() {
    if (!chosenCard) return;
    confirming = true;
    send({ type: "confirm", points: chosenCard.label });
    setTimeout(() => (confirming = false), 10_000);
  }
</script>

<section class="panel" class:docked aria-label="Final points" data-tour="final">
  <span class="panel-title">{docked ? "Final points" : "Final story points"}</span>
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
  <div class="confirm-row">
    {@render lead?.()}
    <button
      class="btn-primary"
      type="button"
      disabled={!chosenCard || confirming}
      onclick={confirm}
      >{confirming ? (snap.demo ? "Saving…" : "Writing to Jira…") : confirmLabel}</button
    >
  </div>
  {#if chosenCard && chosenCard.value !== null && snap.ticket && !docked}
    <span class="note">
      Writes {chosenCard.value} to {snap.ticket.key}
      {snap.demo ? "in the demo backlog" : "in Jira"}, then loads {snap.up_next[0]?.key ??
        "the end of the queue"}.
    </span>
  {/if}
</section>

<style>
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
    color: var(--on-accent);
  }
  .confirm-row {
    display: flex;
    gap: 10px;
  }
  .confirm-row .btn-primary {
    flex: 1;
  }
  .docked {
    padding: 0;
    border: none;
    background: none;
    gap: 10px;
  }
  /* One row that scrolls sideways if the scale is long, so the dock stays short. */
  .docked .picks {
    flex-wrap: nowrap;
    overflow-x: auto;
    padding-bottom: 2px;
  }
  .docked .pick {
    flex: none;
  }
</style>
