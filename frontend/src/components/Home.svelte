<script lang="ts">
  import { onMount } from "svelte";
  import {
    ApiError,
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

  // The 30-second tour video, in a player over the page (design.md, "Demo rooms").
  let player = $state<HTMLDialogElement | null>(null);
  let video = $state<HTMLVideoElement | null>(null);
  function watch() {
    player?.showModal();
    video?.play().catch(() => {}); // a browser may refuse; the controls are there
  }
  function stopVideo() {
    video?.pause();
  }
  let demoError = $state<string | null>(null);
  let demoFull = $state<string | null>(null);
  async function tryDemo() {
    demoBusy = true;
    demoError = null;
    demoFull = null;
    try {
      const demo = await createDemo();
      location.href = `/r/${demo.slug}`;
    } catch (err) {
      // Every demo room is taken: not a fault, so say so kindly rather than in red.
      if (err instanceof ApiError && err.status === 503) demoFull = err.message;
      else demoError = err instanceof Error ? err.message : "Could not start a demo.";
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
  {#if me?.tour_video && !me.demo_rooms}
    <section class="section" aria-label="Watch the video">
      <h2>See it in 30 seconds</h2>
      <p class="text-2">A short narrated tour of a session, from the first vote to the points in Jira.</p>
      <div class="buttons">{@render watchButton()}</div>
    </section>
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
        {#if me.tour_video}{@render watchButton()}{/if}
      </div>
      {#if demoFull}
        <p class="full" role="status"><span class="cup" aria-hidden="true">☕</span> {demoFull}</p>
      {/if}
      {#if demoError}<p class="form-error" role="alert">{demoError}</p>{/if}
    </section>
  {/if}
</main>

{#snippet watchButton()}
  <button class="btn" type="button" aria-haspopup="dialog" onclick={watch}>
    <svg aria-hidden="true" width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M7 4.5v15l13-7.5z"></path></svg>
    Watch the video
  </button>
{/snippet}

<dialog class="player" bind:this={player} aria-labelledby="player-title" onclose={stopVideo}>
  <div class="player-head">
    <h2 id="player-title">Scrum poker in 30 seconds</h2>
    <button class="btn close" type="button" aria-label="Close" onclick={() => {
        stopVideo();
        player?.close();
      }}>
      <svg aria-hidden="true" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M18 6 6 18"></path><path d="m6 6 12 12"></path></svg>
    </button>
  </div>
  <!-- The narration is the tour's captions read aloud: the same words are on screen. -->
  <!-- svelte-ignore a11y_media_has_caption -->
  <video bind:this={video} src="/tour.mp4" controls preload="none" playsinline></video>
</dialog>

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
  .buttons .btn {
    display: inline-flex;
    align-items: center;
    gap: 8px;
  }
  .player {
    width: min(960px, calc(100vw - 32px));
    box-sizing: border-box;
    padding: 12px 16px 16px;
    border: 1px solid var(--border);
    border-radius: 12px;
    background: var(--surface);
    color: var(--ink);
  }
  .player::backdrop {
    background: rgb(8 12 10 / 70%);
  }
  .player-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    padding-bottom: 10px;
  }
  .player-head h2 {
    margin: 0;
    font-family: var(--font-display);
    font-size: 18px;
  }
  .close {
    width: 44px;
    padding: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    border: none;
    background: none;
  }
  .player video {
    display: block;
    width: 100%;
    aspect-ratio: 16 / 9;
    border-radius: 8px;
    background: #000;
  }
  .link-btn {
    display: inline-flex;
    align-items: center;
    color: var(--ink);
    text-decoration: none;
    font-weight: 600;
  }
  .full {
    display: flex;
    align-items: center;
    gap: 10px;
    margin: 12px 0 0;
    padding: 10px 14px;
    border: 1px solid var(--border);
    border-radius: 8px;
    background: var(--chip);
    color: var(--text-2);
  }
  .cup {
    font-size: 22px;
    animation: steam 2.4s ease-in-out infinite;
  }
  @keyframes steam {
    50% {
      transform: translateY(-2px) rotate(-6deg);
    }
  }
  @media (prefers-reduced-motion: reduce) {
    .cup {
      animation: none;
    }
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
