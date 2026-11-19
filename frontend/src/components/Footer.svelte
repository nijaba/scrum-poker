<script lang="ts">
  import { THEMES, setTheme, theme, type Theme } from "../lib/theme.svelte";
  import { startTour, tour } from "../lib/tour.svelte";
  const SOURCE = "https://github.com/nijaba/scrum-poker";
  const HELP = `${SOURCE}/blob/main/docs/user-guide.md`;
  const WHY = `${SOURCE}/blob/main/docs/why-scrum-poker.md`;
  const VERSION = __APP_VERSION__;
  const NOTES = `${SOURCE}/releases/tag/v${VERSION}`;
</script>

<footer>
  {#if tour.steps}
    <button class="tour" type="button" onclick={(e) => startTour(e.currentTarget)}>Tour</button>
    <span aria-hidden="true">·</span>
  {/if}
  <a href={HELP} target="_blank" rel="noopener noreferrer">Help</a>
  <span aria-hidden="true">·</span>
  <a href={WHY} target="_blank" rel="noopener noreferrer">Why scrum poker?</a>
  <span aria-hidden="true">·</span>
  <span>Scrum poker is open source.</span>
  <a href={SOURCE} target="_blank" rel="noopener noreferrer">Source on GitHub</a>
  <a href={NOTES} target="_blank" rel="noopener noreferrer" aria-label="Version {VERSION}"
    >v{VERSION}</a
  >
  <span aria-hidden="true">·</span>
  <label class="theme">
    Theme
    <select
      value={theme.value}
      onchange={(e) => setTheme((e.currentTarget as HTMLSelectElement).value as Theme)}
    >
      {#each THEMES as t (t.value)}
        <option value={t.value}>{t.label}</option>
      {/each}
    </select>
  </label>
</footer>

<style>
  footer {
    display: flex;
    flex-wrap: wrap;
    justify-content: center;
    align-items: center;
    gap: 0 6px;
    padding: 0 16px 8px;
    font-size: 13px;
    color: var(--text-3);
  }
  a,
  .tour {
    display: inline-flex;
    align-items: center;
    min-height: 44px;
    color: var(--link);
  }
  .tour {
    padding: 0;
    border: none;
    background: none;
    font: inherit;
    text-decoration: underline;
  }
  .tour:hover {
    color: var(--link-hover);
  }
  .theme {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    min-height: 44px;
  }
  select {
    min-height: 32px;
    padding: 0 6px;
    border: 1px solid var(--border-strong);
    border-radius: 6px;
    background: var(--surface);
    color: var(--ink);
    font: inherit;
  }
</style>
