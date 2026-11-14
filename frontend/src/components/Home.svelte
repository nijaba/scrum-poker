<script lang="ts">
  import { onMount } from "svelte";
  import {
    PROVIDER_NAMES,
    createDemo,
    createRoom,
    getMe,
    listRooms,
    signInUrl,
    signOut,
  } from "../lib/api";
  import type { Me } from "../lib/types";

  let me = $state<Me | null>(null);
  let rooms = $state<{ slug: string; access: "owner" | "delegate" }[]>([]);
  let slug = $state("");
  let error = $state<string | null>(null);
  let loadError = $state<string | null>(null);
  let busy = $state(false);
  const denied = new URLSearchParams(location.search).get("signin") === "denied";

  onMount(async () => {
    try {
      me = await getMe();
      if (me.signed_in) rooms = await listRooms();
    } catch (err) {
      loadError = err instanceof Error ? err.message : "Could not load.";
    }
  });

  async function create(event: SubmitEvent) {
    event.preventDefault();
    busy = true;
    error = null;
    try {
      const room = await createRoom(slug.trim());
      location.href = `/r/${room.slug}/settings`;
    } catch (err) {
      error = err instanceof Error ? err.message : "Could not create the room.";
    } finally {
      busy = false;
    }
  }

  let demoBusy = $state(false);
  let demoError = $state<string | null>(null);
  async function tryDemo() {
    demoBusy = true;
    demoError = null;
    try {
      const demo = await createDemo();
      location.href = `/r/${demo.slug}`;
    } catch (err) {
      demoError = err instanceof Error ? err.message : "Could not start a demo.";
      demoBusy = false;
    }
  }

  async function out() {
    await signOut();
    location.reload();
  }
</script>

<header class="page-header">
  <span class="page-title">Scrum poker</span>
  {#if me?.signed_in}
    <div class="right">
      <button class="btn" type="button" onclick={out}>Sign out</button>
      <div class="who">
        <span class="who-name">{me.name}</span>
        <span class="who-role">{me.label}</span>
      </div>
    </div>
  {/if}
</header>

<main class="page-main">
  {#if loadError}
    <p class="form-error" role="alert">{loadError}</p>
  {:else if !me}
    <p>Loading…</p>
  {:else if !me.signed_in}
    <section class="section" aria-label="Sign in">
      <h2>Run a session</h2>
      <p class="text-2">
        Owners and delegates sign in to run sessions. Players don't: they open the room link the
        facilitator shares.
      </p>
      {#if denied}<p class="form-error" role="alert">Sign-in was cancelled.</p>{/if}
      <div class="buttons">
        {#each me.providers as provider (provider)}
          <a class="btn link-btn" href={signInUrl(provider, "/")}
            >Sign in with {PROVIDER_NAMES[provider]}</a
          >
        {:else}
          <p class="text-2">No sign-in provider is configured.</p>
        {/each}
      </div>
    </section>
  {:else}
    <section class="section" aria-label="Your rooms">
      <h2>Your rooms</h2>
      {#if rooms.length === 0}
        <p class="text-2">You don't own or help run any rooms yet.</p>
      {:else}
        <ul class="rooms">
          {#each rooms as room (room.slug)}
            <li>
              <a class="slug" href="/r/{room.slug}">{room.slug}</a>
              <span class="chip">{room.access === "owner" ? "Owner" : "Delegate"}</span>
              {#if room.access === "owner"}
                <a class="settings" href="/r/{room.slug}/settings">Settings</a>
              {/if}
            </li>
          {/each}
        </ul>
      {/if}
    </section>

    {#if me.can_create}
      <section class="section" aria-label="Create a room">
        <h2>Create a room</h2>
        <form class="create" onsubmit={create}>
          <div class="field grow">
            <label for="new-slug">Short name</label>
            <input
              id="new-slug"
              class="input"
              bind:value={slug}
              placeholder="team-a"
              maxlength="40"
              pattern="[a-z0-9][a-z0-9\-]*"
              autocomplete="off"
              aria-describedby="slug-help"
            />
          </div>
          <button class="btn-primary" type="submit" disabled={busy || !slug.trim()}
            >Create room</button
          >
        </form>
        <p id="slug-help" class="text-2">
          Lowercase letters, digits and hyphens. Players join at {location.origin}/r/{slug.trim() ||
            "team-a"}.
        </p>
        {#if error}<p class="form-error" role="alert">{error}</p>{/if}
      </section>
    {:else}
      <p class="text-2">This account can run sessions in rooms where it is a delegate, but cannot create rooms.</p>
    {/if}
  {/if}
  {#if me?.demo_rooms}
    <section class="section" aria-label="Try a demo">
      <h2>Practise first</h2>
      <p class="text-2">
        Open a private demo room with a team of bots and a made-up backlog. You run the session;
        nothing reaches Jira. Share its link to bring colleagues in.
      </p>
      <div class="buttons">
        <button class="btn" type="button" disabled={demoBusy} onclick={tryDemo}>Try a demo</button>
      </div>
      {#if demoError}<p class="form-error" role="alert">{demoError}</p>{/if}
    </section>
  {/if}
</main>

<style>
  .right {
    display: flex;
    align-items: center;
    gap: 16px;
    margin-left: auto;
  }
  .buttons {
    display: flex;
    flex-wrap: wrap;
    gap: 12px;
  }
  .link-btn {
    display: inline-flex;
    align-items: center;
    color: var(--ink);
    text-decoration: none;
    font-weight: 600;
  }
  .rooms {
    list-style: none;
    margin: 0;
    padding: 0;
    border: 1px solid var(--border);
    border-radius: 8px;
  }
  .rooms li {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 12px;
    min-height: 44px;
    padding: 6px 14px;
    border-bottom: 1px solid var(--border);
  }
  .rooms li:last-child {
    border-bottom: none;
  }
  .slug {
    font-weight: 600;
  }
  .chip {
    padding: 2px 10px;
    border-radius: 999px;
    background: var(--chip);
    font-size: 13px;
    color: var(--text-2);
  }
  .settings {
    margin-left: auto;
    display: inline-flex;
    align-items: center;
    min-height: 44px;
    font-weight: 600;
  }
  .create {
    display: flex;
    flex-wrap: wrap;
    align-items: flex-end;
    gap: 12px;
  }
  .grow {
    flex: 1 1 220px;
    min-width: 0;
  }
  .create .btn-primary {
    min-height: 44px;
    padding: 0 20px;
  }
  p {
    margin: 0;
  }
</style>
