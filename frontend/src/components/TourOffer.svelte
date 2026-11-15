<script lang="ts">
  /** The once-only offer of the page's tour, under the header. design.md, "Tour". */
  import { declineTour, startTour, tour } from "../lib/tour.svelte";

  let { text }: { text: string } = $props();
</script>

{#if tour.offered}
  <section class="offer" aria-label="Tour offer">
    <span>{text}</span>
    <div class="actions">
      <button class="btn btn-primary" type="button" onclick={() => startTour()}>Take the tour</button>
      <button class="btn" type="button" onclick={declineTour}>No thanks</button>
    </div>
  </section>
{/if}

<style>
  .offer {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 10px 16px;
    margin: 16px 24px 0;
    padding: 10px 16px;
    border: 1px solid var(--border);
    border-left: 4px solid var(--accent);
    border-radius: 8px;
    background: var(--surface);
  }
  .actions {
    display: flex;
    gap: 10px;
    margin-left: auto;
  }
  .btn-primary {
    min-height: 44px;
    padding: 0 16px;
    font-size: 15px;
  }
  @media (max-width: 640px) {
    .offer {
      margin: 12px 16px 0;
    }
    .actions {
      margin-left: 0;
    }
  }
</style>
