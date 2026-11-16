<script lang="ts">
  /**
   * The running tour: an outline on the part of the page a step explains, the rest
   * dimmed, and a caption beside it with Back, Next and Done. The page stays usable
   * underneath. Nothing moves, so reduced motion needs nothing extra. design.md, "Tour".
   */
  import { tick } from "svelte";
  import { endTour, showMore, tour } from "../lib/tour.svelte";

  const PAD = 6;
  const GAP = 12;
  const MARGIN = 16;

  type Box = { top: number; left: number; width: number; height: number };

  let spot = $state<Box | null>(null);
  let place = $state({ top: 0, left: 0, width: 360 });
  let caption = $state<HTMLDivElement | null>(null);
  let next = $state<HTMLButtonElement | null>(null);

  const steps = $derived(tour.running);
  const step = $derived(steps ? steps[tour.at] : null);
  const last = $derived(!!steps && tour.at === steps.length - 1);

  /** The first part of the page with this name that is drawn (a closed sheet is not). */
  function find(target: string | string[] | undefined): HTMLElement | null {
    for (const name of [target ?? []].flat()) {
      for (const el of document.querySelectorAll<HTMLElement>(`[data-tour="${name}"]`)) {
        if (el.getClientRects().length && !el.closest("dialog:not([open])")) return el;
      }
    }
    return null;
  }

  function measure() {
    if (!step) return;
    const vw = document.documentElement.clientWidth;
    const vh = window.innerHeight;
    const width = Math.min(360, vw - 2 * MARGIN);
    const el = find(step.target);
    const height = caption?.offsetHeight ?? 160;
    if (!el) {
      spot = null;
      place = { width, left: (vw - width) / 2, top: Math.max(MARGIN, (vh - height) / 2) };
      return;
    }
    const r = el.getBoundingClientRect();
    // The outline stays inside the window, so a part at its edge is still ringed all round.
    const top = Math.max(1, r.top - PAD);
    const left = Math.max(1, r.left - PAD);
    const bottom = Math.min(vh - 1, r.bottom + PAD);
    const right = Math.min(vw - 1, r.right + PAD);
    spot = { top, left, width: Math.max(0, right - left), height: Math.max(0, bottom - top) };
    const below = bottom + GAP;
    const above = top - GAP - height;
    let at: number;
    if (below + height <= vh - MARGIN) at = below;
    else if (above >= MARGIN) at = above;
    else at = r.top + r.height / 2 < vh / 2 ? vh - height - MARGIN : MARGIN; // a tall part: the far edge
    place = { width, left: Math.min(Math.max(MARGIN, r.left), vw - width - MARGIN), top: at };
  }

  async function show() {
    const el = find(step?.target);
    el?.scrollIntoView({ block: "nearest", inline: "nearest" });
    measure();
    await tick();
    measure(); // again, now the caption's height is known
    next?.focus();
  }

  // A new step: bring its part into view and move focus to the caption.
  $effect(() => {
    if (step) show();
  });

  // Follow the page while it scrolls, resizes or changes under the tour.
  $effect(() => {
    if (!steps) return;
    const timer = setInterval(measure, 250);
    window.addEventListener("scroll", measure, true);
    window.addEventListener("resize", measure);
    return () => {
      clearInterval(timer);
      window.removeEventListener("scroll", measure, true);
      window.removeEventListener("resize", measure);
    };
  });

  function go(by: number) {
    if (!steps) return;
    tour.at = Math.min(Math.max(0, tour.at + by), steps.length - 1);
  }

  function onKey(event: KeyboardEvent) {
    if (steps && event.key === "Escape") {
      event.preventDefault();
      endTour();
    }
  }
</script>

<svelte:window onkeydown={onKey} />

{#if steps && step}
  {#if spot}
    <div
      class="tour-spot"
      aria-hidden="true"
      style:top="{spot.top}px"
      style:left="{spot.left}px"
      style:width="{spot.width}px"
      style:height="{spot.height}px"
    ></div>
  {:else}
    <div class="tour-dim" aria-hidden="true"></div>
  {/if}
  <div
    bind:this={caption}
    class="tour-caption"
    role="dialog"
    aria-labelledby="tour-title"
    aria-describedby="tour-text"
    style:top="{place.top}px"
    style:left="{place.left}px"
    style:width="{place.width}px"
  >
    <div class="head">
      <span class="tour-count">Step {tour.at + 1} of {steps.length}</span>
      <button class="close" type="button" aria-label="Close" onclick={endTour}>
        <svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M18 6 6 18"></path><path d="m6 6 12 12"></path></svg>
      </button>
    </div>
    <h2 id="tour-title">{step.title}</h2>
    <p id="tour-text">{step.text}</p>
    <div class="actions">
      <button class="btn" type="button" disabled={tour.at === 0} onclick={() => go(-1)}>Back</button>
      {#if last && tour.more}
        <button class="btn" type="button" onclick={endTour}>Done</button>
        <button bind:this={next} class="btn btn-primary" type="button" onclick={showMore}
          >Show me more</button
        >
      {:else if last}
        <button bind:this={next} class="btn btn-primary" type="button" onclick={endTour}>Done</button>
      {:else}
        <button bind:this={next} class="btn btn-primary" type="button" onclick={() => go(1)}>Next</button>
      {/if}
    </div>
  </div>
{/if}

<style>
  /* The outline: a ring round the part, and a shadow that dims everything else. */
  .tour-spot {
    position: fixed;
    z-index: 60;
    box-sizing: border-box;
    border: 3px solid var(--accent);
    border-radius: 12px;
    box-shadow: 0 0 0 9999px rgb(8 12 10 / 55%);
    pointer-events: none;
  }
  .tour-dim {
    position: fixed;
    inset: 0;
    z-index: 60;
    background: rgb(8 12 10 / 55%);
    pointer-events: none;
  }
  .tour-caption {
    position: fixed;
    z-index: 61;
    box-sizing: border-box;
    display: flex;
    flex-direction: column;
    gap: 8px;
    padding: 12px 16px 16px;
    border: 1px solid var(--border);
    border-radius: 12px;
    background: var(--surface);
    color: var(--ink);
    box-shadow: var(--menu-shadow);
  }
  .head {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }
  .tour-count {
    font-size: 13px;
    font-weight: 600;
    color: var(--text-3);
  }
  .close {
    width: 44px;
    height: 44px;
    margin: -8px -10px -8px 0;
    display: flex;
    align-items: center;
    justify-content: center;
    border: none;
    border-radius: 8px;
    background: none;
  }
  .close:hover {
    background: var(--chip);
  }
  h2 {
    margin: 0;
    font-family: var(--font-display);
    font-size: 19px;
  }
  p {
    margin: 0;
    color: var(--text-2);
  }
  .actions {
    display: flex;
    justify-content: flex-end;
    gap: 10px;
    margin-top: 4px;
  }
  .actions .btn-primary {
    min-height: 44px;
    padding: 0 20px;
    font-size: 15px;
  }
</style>
