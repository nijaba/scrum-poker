<script lang="ts">
  import Footer from "./components/Footer.svelte";
  import Home from "./components/Home.svelte";
  import Room from "./components/Room.svelte";
  import Settings from "./components/Settings.svelte";
  import { onMount } from "svelte";
  import { listenForCode } from "./lib/deck";

  const match = location.pathname.match(/^\/r\/([a-z0-9][a-z0-9-]{0,39})(\/settings)?\/?$/);
  const slug = match ? match[1] : null;
  const settings = !!match?.[2];

  // The Konami code switches your own deck; a short note says which one is on.
  let deckNote = $state("");
  let noteTimer: ReturnType<typeof setTimeout>;
  onMount(() =>
    listenForCode((arcade) => {
      deckNote = arcade ? "Arcade deck on. Insert coin!" : "Classic deck back.";
      clearTimeout(noteTimer);
      noteTimer = setTimeout(() => (deckNote = ""), 4000);
    }),
  );
</script>

<div class="shell">
  <div class="page">
    {#if slug && settings}
      <Settings {slug} />
    {:else if slug}
      <Room {slug} />
    {:else}
      <Home />
    {/if}
  </div>
  <Footer />
  <p class="deck-note" class:shown={deckNote} role="status">{deckNote}</p>
</div>

<style>
  /* The page fills the window, so the footer sits at the bottom. */
  .shell {
    min-height: 100vh;
    display: flex;
    flex-direction: column;
  }
  .deck-note {
    position: fixed;
    left: 50%;
    bottom: 24px;
    z-index: 50;
    margin: 0;
    padding: 10px 18px;
    border-radius: 8px;
    background: var(--ink);
    color: #ffffff;
    font-weight: 600;
    transform: translateX(-50%);
    pointer-events: none;
  }
  /* Kept in the page while empty, so screen readers hear it when the text arrives. */
  .deck-note:not(.shown) {
    opacity: 0;
  }
  .page {
    flex: 1;
    display: flex;
    flex-direction: column;
  }
</style>
