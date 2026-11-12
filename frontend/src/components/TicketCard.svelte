<script lang="ts">
  import { points } from "../lib/format";
  import type { Snapshot, TicketView } from "../lib/types";

  let { ticket, queue }: { ticket: TicketView; queue: Snapshot["queue"] } = $props();

  let expanded = $state(false);
  let overflowing = $state(false);
  let description = $state<HTMLDivElement | null>(null);

  // A new ticket starts collapsed. Measure whether its description needs "Show more".
  $effect(() => {
    void ticket.key;
    expanded = false;
    queueMicrotask(measure);
  });

  function measure() {
    if (!description) return;
    overflowing = description.scrollHeight > description.clientHeight + 1;
  }
</script>

<svelte:window onresize={() => !expanded && measure()} />

<section class="panel ticket" aria-label="Current ticket">
  <div class="chips">
    {#if ticket.url}
      <a class="key" href={ticket.url} target="_blank" rel="noopener noreferrer">{ticket.key}</a>
    {:else}
      <span class="key">{ticket.key}</span>
    {/if}
    {#if ticket.type}<span class="chip">{ticket.type}</span>{/if}
    {#if ticket.priority}<span class="chip">{ticket.priority} priority</span>{/if}
    {#if ticket.epic}<span class="chip">Epic: {ticket.epic}</span>{/if}
    {#each ticket.labels as label (label)}<span class="chip chip-outline">{label}</span>{/each}
    <span class="position">Ticket {queue.position} of {queue.length}</span>
  </div>
  <h1>{ticket.summary}</h1>
  {#if ticket.result.status === "estimated" && ticket.result.points !== null}
    <p class="result">Estimated earlier at {points(ticket.result.points)}.</p>
  {:else if ticket.result.status === "skipped"}
    <p class="result">Skipped earlier.</p>
  {/if}
  {#if ticket.description}
    <!-- Jira's rendered HTML, sanitized on the server (app/jira/html.py). -->
    <div
      id="ticket-description"
      class="description"
      class:collapsed={!expanded}
      bind:this={description}
    >
      {@html ticket.description}
    </div>
    {#if overflowing || expanded}
      <button
        class="more"
        type="button"
        aria-expanded={expanded}
        aria-controls="ticket-description"
        onclick={() => (expanded = !expanded)}>{expanded ? "Show less" : "Show more"}</button
      >
    {/if}
  {/if}
</section>

<style>
  .ticket {
    padding: 20px;
    gap: 10px;
  }
  .chips {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 8px;
  }
  .key {
    font-weight: 600;
  }
  .chip {
    padding: 2px 10px;
    border-radius: 999px;
    background: var(--chip);
    font-size: 13px;
    color: var(--text-2);
  }
  .chip-outline {
    background: none;
    border: 1px solid var(--border-strong);
  }
  .position {
    margin-left: auto;
    font-size: 13px;
    font-weight: 600;
    color: var(--text-3);
  }
  h1 {
    margin: 0;
    font-family: var(--font-display);
    font-weight: 700;
    font-size: 26px;
    line-height: 1.2;
    text-wrap: pretty;
  }
  .result {
    margin: 0;
    font-size: 14px;
    font-weight: 600;
    color: var(--text-3);
  }
  .description {
    margin: 0;
    color: var(--text-2);
    max-width: 72ch;
    text-wrap: pretty;
    overflow-wrap: anywhere;
  }
  .description :global(p),
  .description :global(ul),
  .description :global(ol),
  .description :global(pre),
  .description :global(blockquote) {
    margin: 0 0 8px;
  }
  .description :global(pre) {
    white-space: pre-wrap;
  }
  .description :global(:last-child) {
    margin-bottom: 0;
  }
  .collapsed {
    /* Three lines. line-clamp does not clamp across the paragraphs Jira renders. */
    max-height: calc(3 * 1.45em);
    overflow: hidden;
  }
  .more {
    align-self: flex-start;
    min-height: 44px;
    padding: 0;
    border: none;
    background: none;
    color: var(--link);
    font-weight: 600;
  }
</style>
