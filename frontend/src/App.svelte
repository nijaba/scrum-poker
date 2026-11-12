<script lang="ts">
  import Footer from "./components/Footer.svelte";
  import Home from "./components/Home.svelte";
  import Room from "./components/Room.svelte";
  import Settings from "./components/Settings.svelte";

  const match = location.pathname.match(/^\/r\/([a-z0-9][a-z0-9-]{0,39})(\/settings)?\/?$/);
  const slug = match ? match[1] : null;
  const settings = !!match?.[2];
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
</div>

<style>
  /* The page fills the window, so the footer sits at the bottom. */
  .shell {
    min-height: 100vh;
    display: flex;
    flex-direction: column;
  }
  .page {
    flex: 1;
    display: flex;
    flex-direction: column;
  }
</style>
