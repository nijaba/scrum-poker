<script lang="ts">
  import { onMount } from "svelte";
  import {
    ApiError,
    PROVIDER_NAMES,
    answerOwnershipOffer,
    createDemo,
    createRoom,
    getMe,
    listRooms,
    signInUrl,
    signOut,
  } from "../lib/api";
  import { ACCESS_NAMES, canManage } from "../lib/types";
  import type { Me, RoomListing } from "../lib/types";

  let me = $state<Me | null>(null);
  let rooms = $state<RoomListing[]>([]);
  const firstName = $derived(me?.name?.trim().split(/\s+/)[0] ?? "");
  let offerError = $state<string | null>(null);

  // An owner's offer of a room to this account (design.md, "Co-owners and handing a room over").
  async function answer(slug: string, accept: boolean) {
    offerError = null;
    try {
      await answerOwnershipOffer(slug, accept);
      rooms = await listRooms();
    } catch (err) {
      offerError = err instanceof Error ? err.message : "Could not answer the offer.";
      rooms = await listRooms().catch(() => rooms);
    }
  }
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

<header class="hero" class:compact={me?.signed_in}>
  <div class="bar">
    <span class="page-title">Scrum poker</span>
    {#if me?.signed_in}
      <div class="right">
        <div class="who">
          <span class="who-name">{me.name}</span>
          <span class="who-role">{me.label}</span>
        </div>
        <button class="btn btn-on-table" type="button" onclick={out}>Sign out</button>
      </div>
    {/if}
  </div>

  {#if me && !me.signed_in}
    <div class="hero-body">
      <div class="hero-text">
        <h1>Estimate your Jira backlog together, with cards face down.</h1>
        <p class="lead">
          The team votes in secret, the cards turn over together, and the agreed points go
          straight back to Jira.
        </p>
        {@render tryIt(true)}
      </div>
      {@render fan()}
    </div>
  {:else if me?.signed_in}
    <div class="hero-body">
      <div class="hero-text">
        <h1>Welcome back{firstName ? `, ${firstName}` : ""}.</h1>
        <p class="lead">Pick a room to run a session, or set up a new one.</p>
      </div>
    </div>
  {/if}
</header>

<main class="page-main home" class:signed-in={me?.signed_in}>
  {#if loadError}
    <p class="form-error" role="alert">{loadError}</p>
  {:else if !me}
    <p>Loading…</p>
  {:else if !me.signed_in}
    <section class="section signin" aria-label="Sign in">
      <div>
        <h2>Run a session</h2>
        <p class="text-2">
          Owners and delegates sign in to run sessions. Players don't: they open the room link
          the facilitator shares.
        </p>
      </div>
      {#if denied}<p class="form-error" role="alert">Sign-in was cancelled.</p>{/if}
      <div class="buttons">
        {#each me.providers as provider (provider)}
          <a class="btn link-btn" href={signInUrl(provider, "/")}
            >{@render providerIcon(provider)} Sign in with {PROVIDER_NAMES[provider]}</a
          >
        {:else}
          <p class="text-2">No sign-in provider is configured.</p>
        {/each}
      </div>
    </section>

    <ol class="steps" aria-label="How a session runs">
      <li>
        <span class="step-n">1</span>
        <h3>Connect a board</h3>
        <p>The queue fills with the backlog tickets that still need an estimate, in rank order.</p>
      </li>
      <li>
        <span class="step-n">2</span>
        <h3>Share the link</h3>
        <p>Players type a name and join. No account, on a laptop or a phone.</p>
      </li>
      <li>
        <span class="step-n">3</span>
        <h3>Vote in secret</h3>
        <p>The table shows who has voted, never what, until the reveal.</p>
      </li>
      <li>
        <span class="step-n">4</span>
        <h3>Agree and move on</h3>
        <p>The facilitator confirms the points and they are written to Jira.</p>
      </li>
    </ol>
  {:else}
    <section class="rooms-section" aria-label="Your rooms">
      <h2>Your rooms</h2>
      {#if offerError}<p class="form-error" role="alert">{offerError}</p>{/if}
      <ul class="rooms">
        {#each rooms as room (room.slug)}
          <li class="room" class:offered={room.offer}>
            <div class="room-top">
              <span class="mini-card" aria-hidden="true">{room.slug.charAt(0).toUpperCase()}</span>
              <div class="room-name">
                <a class="slug" href="/r/{room.slug}">{room.slug}</a>
                <span class="chip">{ACCESS_NAMES[room.access]}</span>
              </div>
            </div>
            {#if room.offer}
              <div class="offer" role="group" aria-label="Ownership offer for {room.slug}">
                <span>{room.offer.from} offered you ownership of {room.slug}.</span>
                <div class="offer-buttons">
                  <button
                    class="btn btn-primary"
                    type="button"
                    onclick={() => answer(room.slug, true)}>Accept</button
                  >
                  <button class="btn" type="button" onclick={() => answer(room.slug, false)}
                    >Decline</button
                  >
                </div>
              </div>
            {/if}
            <div class="room-links">
              <span class="open" aria-hidden="true">Open room →</span>
              {#if canManage(room.access)}
                <a class="settings" href="/r/{room.slug}/settings">Settings</a>
              {/if}
            </div>
          </li>
        {/each}
        {#if me.can_create}
          <li class="room new-room">
            <section aria-label="Create a room">
              <h3>Create a room</h3>
              <form class="create" onsubmit={create}>
                <div class="field">
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
                Lowercase letters, digits and hyphens. Players join at {location.host}/r/{slug.trim() ||
                  "team-a"}.
              </p>
              {#if error}<p class="form-error" role="alert">{error}</p>{/if}
            </section>
          </li>
        {/if}
      </ul>
      {#if rooms.length === 0}
        <p class="text-2">You don't own or help run any rooms yet.</p>
      {/if}
      {#if !me.can_create}
        <p class="text-2">
          This account can run sessions in rooms where it is a delegate, but cannot create rooms.
        </p>
      {/if}
    </section>

    {#if me.demo_rooms || me.tour_video}
      <div class="practice">
        <div>
          <h2>{me.demo_rooms ? "Practise first" : "See it in 30 seconds"}</h2>
          <p class="text-2">
            {#if me.demo_rooms}
              A private demo room with a team of bots and a made-up backlog. Nothing reaches Jira.
            {:else}
              A short narrated tour of a session, from the first vote to the points in Jira.
            {/if}
          </p>
        </div>
        {@render tryIt(false)}
      </div>
    {/if}
  {/if}
</main>

{#snippet tryIt(onTable: boolean)}
  {#if me?.demo_rooms}
    <section class="try" class:on-table={onTable} aria-label="Try a demo">
      <div class="buttons">
        <button
          class={onTable ? "btn-primary big" : "btn"}
          type="button"
          disabled={demoBusy}
          onclick={tryDemo}>Try a demo</button
        >
        {#if me.tour_video}{@render watchButton(onTable)}{/if}
      </div>
      {#if onTable}
        <p class="fine">No sign-in: you run a session with bot players, and nothing reaches Jira.</p>
      {/if}
      {#if demoFull}
        <p class="full" role="status"><span class="cup" aria-hidden="true">☕</span> {demoFull}</p>
      {/if}
      {#if demoError}<p class="form-error" role="alert">{demoError}</p>{/if}
    </section>
  {:else if me?.tour_video}
    <section class="try" class:on-table={onTable} aria-label="Watch the video">
      <div class="buttons">{@render watchButton(onTable)}</div>
    </section>
  {/if}
{/snippet}

{#snippet fan()}
  <div class="fan" aria-hidden="true">
    <div class="fcard c1 back"></div>
    <div class="fcard c2"><span>3</span><b>3</b><i>♠</i></div>
    <div class="fcard c3 red"><span>5</span><b>5</b><i>♥</i></div>
    <div class="fcard c4"><span>8</span><b>8</b><i>♣</i></div>
    <div class="fcard c5 red"><span>13</span><b>13</b><i>♦</i></div>
  </div>
{/snippet}

{#snippet providerIcon(provider: string)}
  {#if provider === "github"}
    <svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M12 .5a11.5 11.5 0 0 0-3.64 22.41c.58.1.79-.25.79-.56v-2c-3.2.7-3.88-1.37-3.88-1.37-.53-1.33-1.28-1.69-1.28-1.69-1.05-.71.08-.7.08-.7 1.16.08 1.77 1.19 1.77 1.19 1.03 1.77 2.7 1.26 3.36.96.1-.75.4-1.26.73-1.55-2.55-.29-5.24-1.28-5.24-5.68 0-1.26.45-2.28 1.19-3.09-.12-.29-.52-1.46.11-3.04 0 0 .97-.31 3.17 1.18a11 11 0 0 1 5.77 0c2.2-1.49 3.17-1.18 3.17-1.18.63 1.58.23 2.75.11 3.04.74.81 1.19 1.83 1.19 3.09 0 4.41-2.69 5.38-5.25 5.67.41.36.78 1.06.78 2.14v3.17c0 .31.21.67.8.56A11.5 11.5 0 0 0 12 .5Z"></path></svg>
  {:else if provider === "google"}
    <svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24"><path fill="#4285F4" d="M23.5 12.27c0-.85-.08-1.67-.22-2.45H12v4.64h6.45a5.5 5.5 0 0 1-2.39 3.61v3h3.86c2.26-2.08 3.58-5.15 3.58-8.8Z"></path><path fill="#34A853" d="M12 24c3.24 0 5.95-1.07 7.93-2.91l-3.86-3c-1.08.72-2.45 1.15-4.07 1.15-3.13 0-5.78-2.11-6.73-4.95H1.28v3.1A12 12 0 0 0 12 24Z"></path><path fill="#FBBC05" d="M5.27 14.29a7.2 7.2 0 0 1 0-4.58v-3.1H1.28a12 12 0 0 0 0 10.78l3.99-3.1Z"></path><path fill="#EA4335" d="M12 4.75c1.76 0 3.34.61 4.59 1.8l3.43-3.43A11.5 11.5 0 0 0 12 0 12 12 0 0 0 1.28 6.61l3.99 3.1C6.22 6.86 8.87 4.75 12 4.75Z"></path></svg>
  {/if}
{/snippet}

{#snippet watchButton(onTable = false)}
  <button class={onTable ? "btn btn-on-table big" : "btn"} type="button" aria-haspopup="dialog" onclick={watch}>
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
  /* The hero: the green of the table, like the room and the project page */
  .hero {
    color: var(--on-table);
    background:
      radial-gradient(ellipse at 75% 30%, rgb(255 255 255 / 7%), transparent 60%),
      linear-gradient(160deg, var(--table), #0b261d);
    padding: 0 24px 72px;
    overflow: hidden;
  }
  .hero.compact {
    padding-bottom: 112px;
  }
  .bar {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 12px 20px;
    max-width: 1040px;
    margin: 0 auto;
    padding: 14px 0;
  }
  .right {
    display: flex;
    align-items: center;
    gap: 16px;
    margin-left: auto;
  }
  .who {
    display: flex;
    flex-direction: column;
    align-items: flex-end;
    line-height: 1.25;
  }
  .who-name {
    font-weight: 600;
  }
  .who-role {
    font-size: 13px;
    color: var(--on-table-2);
  }
  .hero-body {
    display: grid;
    grid-template-columns: minmax(0, 1.2fr) minmax(0, 1fr);
    align-items: center;
    gap: 40px;
    max-width: 1040px;
    margin: 28px auto 0;
  }
  .compact .hero-body {
    grid-template-columns: minmax(0, 1fr);
    margin-top: 12px;
  }
  .hero h1 {
    margin: 0 0 14px;
    font-family: var(--font-display);
    font-size: clamp(30px, 4.6vw, 48px);
    line-height: 1.1;
    letter-spacing: -0.02em;
  }
  .compact h1 {
    font-size: clamp(26px, 3.6vw, 36px);
    margin-bottom: 6px;
  }
  .lead {
    margin: 0;
    font-size: 17px;
    max-width: 34em;
    color: var(--on-table);
  }
  .compact .lead {
    color: var(--on-table-2);
  }
  .fine {
    margin: 12px 0 0;
    font-size: 14px;
    color: var(--on-table-2);
  }
  .btn-on-table {
    background: transparent;
    border: 1px solid var(--on-table-2);
    color: var(--on-table);
  }
  .btn-on-table:hover {
    background: rgb(233 242 238 / 8%);
  }
  .big {
    min-height: 52px;
    padding: 0 24px;
    font-size: 16px;
  }
  .btn-primary.big {
    font-weight: 600;
  }
  .try.on-table {
    margin-top: 24px;
  }
  .try.on-table .full {
    border-color: var(--table-line);
    background: rgb(0 0 0 / 22%);
    color: var(--on-table);
  }

  /* A fanned hand of cards */
  .fan {
    position: relative;
    height: 250px;
  }
  .fcard {
    position: absolute;
    left: 50%;
    bottom: 0;
    width: 112px;
    height: 160px;
    margin-left: -56px;
    border-radius: 11px;
    background: var(--card-stock);
    border: 1px solid var(--card-edge);
    box-shadow: 0 10px 28px rgb(0 0 0 / 35%);
    color: var(--card-ink);
    transform-origin: 50% 170%;
    transform: rotate(var(--turn));
    animation: deal 700ms cubic-bezier(0.2, 0.7, 0.2, 1) both;
  }
  .fcard span,
  .fcard i {
    position: absolute;
    font: 700 16px var(--font-display);
    font-style: normal;
  }
  .fcard span {
    top: 8px;
    left: 10px;
  }
  .fcard i {
    bottom: 8px;
    right: 10px;
  }
  .fcard b {
    position: absolute;
    inset: 0;
    display: grid;
    place-items: center;
    font: 700 46px var(--font-display);
  }
  .fcard.red {
    color: var(--suit-red);
  }
  .fcard.back {
    background:
      repeating-linear-gradient(45deg, transparent 0 7px, rgb(201 221 211 / 35%) 7px 8px),
      repeating-linear-gradient(-45deg, transparent 0 7px, rgb(201 221 211 / 35%) 7px 8px),
      var(--table);
    border: 5px solid var(--card-stock);
  }
  .c1 {
    --turn: -30deg;
  }
  .c2 {
    --turn: -15deg;
    animation-delay: 80ms;
  }
  .c3 {
    --turn: 0deg;
    animation-delay: 160ms;
  }
  .c4 {
    --turn: 15deg;
    animation-delay: 240ms;
    animation-name: deal-chosen;
    outline: 2px solid var(--accent);
    outline-offset: -1px;
  }
  .c5 {
    --turn: 30deg;
    animation-delay: 320ms;
  }
  @keyframes deal {
    from {
      opacity: 0;
      transform: rotate(0deg) translateY(60px);
    }
    to {
      opacity: 1;
      transform: rotate(var(--turn));
    }
  }
  @keyframes deal-chosen {
    from {
      opacity: 0;
      transform: rotate(0deg) translateY(60px);
    }
    to {
      opacity: 1;
      transform: rotate(var(--turn)) translateY(-24px);
    }
  }

  /* The page below the hero lifts onto it */
  .home {
    max-width: 1088px;
    margin-top: -40px;
    gap: 24px;
  }
  /* Signed in, the rooms' label sits on the green and the cards overlap its edge. */
  .home.signed-in {
    margin-top: -96px;
  }
  .home h2 {
    margin: 0;
    font-family: var(--font-display);
    font-size: 20px;
  }
  .home h3 {
    margin: 0;
    font-family: var(--font-display);
    font-size: 16px;
  }
  .section.signin {
    flex-direction: row;
    flex-wrap: wrap;
    align-items: center;
    justify-content: space-between;
    gap: 16px 32px;
    padding: 24px;
    box-shadow: var(--menu-shadow);
  }
  .signin > div:first-child {
    flex: 1 1 320px;
  }
  .signin h2 {
    margin-bottom: 6px;
  }
  .buttons {
    display: flex;
    flex-wrap: wrap;
    gap: 12px;
  }
  .buttons .btn,
  .buttons .btn-primary {
    display: inline-flex;
    align-items: center;
    gap: 8px;
  }
  .link-btn {
    display: inline-flex;
    align-items: center;
    gap: 10px;
    color: var(--ink);
    text-decoration: none;
    font-weight: 600;
  }
  .link-btn:hover {
    color: var(--ink);
    border-color: var(--ink);
  }

  .steps {
    list-style: none;
    margin: 0;
    padding: 0;
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 16px;
  }
  .steps li {
    padding: 18px;
    border: 1px solid var(--border);
    border-radius: 10px;
    background: var(--surface);
  }
  .steps h3 {
    margin-bottom: 4px;
  }
  .steps p {
    font-size: 14px;
    color: var(--text-3);
  }
  .step-n {
    display: inline-grid;
    place-items: center;
    width: 32px;
    height: 32px;
    margin-bottom: 10px;
    border-radius: 8px;
    background: var(--table);
    color: var(--on-table);
    font: 700 16px var(--font-display);
  }

  /* Rooms as cards */
  .rooms-section {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }
  .rooms-section > h2 {
    color: var(--on-table);
    font-size: 15px;
    font-weight: 500;
    letter-spacing: 0.04em;
    text-transform: uppercase;
  }
  .rooms {
    list-style: none;
    margin: 0;
    padding: 0;
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
    gap: 16px;
  }
  .room {
    position: relative;
    display: flex;
    flex-direction: column;
    gap: 14px;
    padding: 18px;
    border: 1px solid var(--border);
    border-radius: 12px;
    background: var(--surface);
    box-shadow: var(--card-shadow);
    transition:
      border-color 120ms ease,
      box-shadow 120ms ease;
  }
  .room:not(.new-room):hover {
    border-color: var(--border-strong);
    box-shadow: var(--card-shadow-up);
  }
  .room.offered {
    border-color: var(--accent);
    box-shadow: 0 0 0 1px var(--accent), var(--card-shadow);
  }
  .room-top {
    display: flex;
    align-items: center;
    gap: 14px;
  }
  .mini-card {
    flex: none;
    display: grid;
    place-items: center;
    width: 40px;
    height: 56px;
    border-radius: 6px;
    background: var(--card-stock);
    border: 1px solid var(--card-edge);
    box-shadow: var(--card-shadow);
    color: var(--card-ink);
    font: 700 20px var(--font-display);
  }
  .room-name {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: 4px;
    min-width: 0;
  }
  .slug {
    font-family: var(--font-display);
    font-weight: 700;
    font-size: 19px;
    color: var(--ink);
    text-decoration: none;
    overflow-wrap: anywhere;
  }
  /* The whole card opens the room; Settings and the offer's buttons sit above it. */
  .slug::after {
    content: "";
    position: absolute;
    inset: 0;
    border-radius: 12px;
  }
  .slug:focus-visible {
    outline: none;
  }
  .slug:focus-visible::after {
    outline: 3px solid var(--accent);
    outline-offset: 2px;
  }
  .chip {
    padding: 2px 10px;
    border-radius: 999px;
    background: var(--chip);
    font-size: 13px;
    color: var(--text-2);
  }
  .room-links {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-top: auto;
    padding-top: 10px;
    border-top: 1px solid var(--border);
  }
  .open {
    font-weight: 600;
    color: var(--link);
  }
  .settings {
    position: relative;
    margin-left: auto;
    display: inline-flex;
    align-items: center;
    min-height: 44px;
    margin-block: -10px;
    font-weight: 600;
  }
  .offer {
    position: relative;
    display: flex;
    flex-direction: column;
    gap: 10px;
    padding: 12px;
    border-radius: 8px;
    background: var(--chip);
  }
  .offer-buttons {
    display: flex;
    gap: 8px;
  }
  .offer .btn-primary {
    min-height: 44px;
    padding: 0 18px;
    font-size: 15px;
  }
  .new-room {
    border-style: dashed;
    border-width: 2px;
    box-shadow: none;
    background: var(--ground);
  }
  .new-room section {
    display: flex;
    flex-direction: column;
    gap: 10px;
  }
  .create {
    display: flex;
    flex-wrap: wrap;
    align-items: flex-end;
    gap: 10px;
  }
  .create .field {
    flex: 1 1 140px;
    min-width: 0;
  }
  .create .btn-primary {
    min-height: 44px;
    padding: 0 18px;
    font-size: 15px;
  }
  .rooms-section > .text-2 {
    margin-top: 4px;
  }

  .practice {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: space-between;
    gap: 12px 24px;
    padding: 20px 24px;
    border: 1px solid var(--border);
    border-radius: 12px;
    background: var(--surface);
  }
  .practice > div:first-child {
    flex: 1 1 300px;
  }
  .practice h2 {
    margin-bottom: 4px;
  }

  /* The video player */
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
  p {
    margin: 0;
  }

  @media (prefers-reduced-motion: reduce) {
    .cup,
    .fcard {
      animation: none;
    }
  }

  @media (max-width: 860px) {
    .hero-body {
      grid-template-columns: minmax(0, 1fr);
      gap: 12px;
    }
    .fan {
      height: 210px;
      transform: scale(0.85);
    }
    .steps {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }
  }
  @media (max-width: 560px) {
    .hero {
      padding: 0 16px 64px;
    }
    .home {
      padding: 16px;
    }
    .fan {
      display: none;
    }
    .steps {
      grid-template-columns: minmax(0, 1fr);
    }
    .who {
      display: none;
    }
    .big {
      flex: 1 1 auto;
      justify-content: center;
    }
  }
</style>
