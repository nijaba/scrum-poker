<script lang="ts">
  import type { Suit } from "../lib/cards";

  // The printed face of a playing card: corner indices and a large centre value.
  // Decorative only; the element around it carries the accessible name and must be
  // positioned (the .deck-card class does that), since the corners sit on it.
  let {
    label,
    suit,
    compact = false,
  }: {
    label: string;
    suit: Suit | null;
    /** The mini window: top-left index and centre value only. */
    compact?: boolean;
  } = $props();

  const length = $derived([...label].length);
  // Long custom labels keep only the suit in the corners, so they don't run into the centre.
  const cornerText = $derived(length <= 3 ? label : "");
  const size = $derived(length <= 1 ? "l1" : length === 2 ? "l2" : length <= 4 ? "l3" : "l5");
</script>

<span class="face" class:compact aria-hidden="true">
  {#if cornerText || (suit && !compact)}
    <span class="idx tl"><b>{cornerText}</b>{#if suit && !compact}<i>{suit.symbol}</i>{/if}</span>
  {/if}
  <span class="pip {size}">{label}</span>
  {#if !compact && (cornerText || suit)}
    <span class="idx br"><b>{cornerText}</b>{#if suit}<i>{suit.symbol}</i>{/if}</span>
  {/if}
</span>

<style>
  /* The face sits in the flow, so a long custom label widens the card; the corners are placed on the card itself. */
  .face {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 100%;
    height: 100%;
    font-family: var(--font-display);
    font-weight: 700;
    pointer-events: none;
  }
  /* a faint inner frame, like the border printed on a real card */
  .face:not(.compact)::after {
    content: "";
    position: absolute;
    inset: 18px 13px;
    border: 1px solid currentColor;
    border-radius: 3px;
    opacity: 0.14;
  }
  .idx {
    position: absolute;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 1px;
    font-size: 13px;
    line-height: 1;
  }
  .idx b {
    font-weight: 700;
  }
  .idx i {
    font-style: normal;
    font-size: 11px;
  }
  .tl {
    top: 5px;
    left: 5px;
  }
  .br {
    right: 5px;
    bottom: 5px;
    transform: rotate(180deg);
  }
  .pip {
    letter-spacing: -0.02em;
    white-space: nowrap;
  }
  .l1 {
    font-size: 30px;
  }
  .l2 {
    font-size: 25px;
  }
  .l3 {
    font-size: 19px;
  }
  .l5 {
    font-size: 15px;
  }
  .compact .idx {
    top: 3px;
    left: 4px;
    font-size: 9px;
  }
  .compact .l1 {
    font-size: 19px;
  }
  .compact .l2 {
    font-size: 16px;
  }
  .compact .l3 {
    font-size: 13px;
  }
  .compact .l5 {
    font-size: 11px;
  }
</style>
