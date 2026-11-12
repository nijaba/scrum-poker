<script lang="ts">
  import { setPlayerName } from "../lib/api";
  import type { Player } from "../lib/types";

  let {
    slug,
    initialName = "",
    onjoined,
  }: { slug: string; initialName?: string; onjoined: (player: Player) => void } = $props();

  // svelte-ignore state_referenced_locally
  let name = $state(initialName);
  let error = $state<string | null>(null);
  let busy = $state(false);

  async function submit(event: SubmitEvent) {
    event.preventDefault();
    if (!name.trim()) {
      error = "Type a name so the team knows who voted.";
      return;
    }
    busy = true;
    error = null;
    try {
      onjoined(await setPlayerName(name));
    } catch (err) {
      error = err instanceof Error ? err.message : "Could not join.";
    } finally {
      busy = false;
    }
  }
</script>

<main class="join">
  <form class="panel" onsubmit={submit}>
    <h1>Join {slug}</h1>
    <label for="player-name">Your name</label>
    <!-- svelte-ignore a11y_autofocus -->
    <input
      id="player-name"
      bind:value={name}
      maxlength="40"
      autocomplete="nickname"
      autofocus
      aria-describedby={error ? "join-error" : undefined}
    />
    {#if error}<p id="join-error" class="error" role="alert">{error}</p>{/if}
    <button class="btn-primary" type="submit" disabled={busy}>Join room</button>
    <p class="note">No sign-in. This browser remembers your name.</p>
  </form>
</main>

<style>
  .join {
    max-width: 26rem;
    margin: 0 auto;
    padding: 64px 16px;
  }
  h1 {
    margin: 0 0 4px;
    font-family: var(--font-display);
    font-size: 26px;
  }
  label {
    font-size: 13px;
    color: var(--text-3);
  }
  input {
    height: 44px;
    box-sizing: border-box;
    padding: 0 10px;
    border: 1px solid var(--border-strong);
    border-radius: 8px;
    background: var(--surface);
  }
  .error {
    margin: 0;
    color: var(--danger);
    font-size: 14px;
  }
  .note {
    margin: 0;
  }
</style>
