<script lang="ts">
  import Home from "./components/Home.svelte";
  import Room from "./components/Room.svelte";
  import Settings from "./components/Settings.svelte";

  const match = location.pathname.match(/^\/r\/([a-z0-9][a-z0-9-]{0,39})(\/settings)?\/?$/);
  const slug = match ? match[1] : null;
  const settings = !!match?.[2];
</script>

{#if slug && settings}
  <Settings {slug} />
{:else if slug}
  <Room {slug} />
{:else}
  <Home />
{/if}
