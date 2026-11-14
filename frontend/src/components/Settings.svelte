<script lang="ts">
  import { onMount } from "svelte";
  import { points } from "../lib/format";
  import {
    PROVIDER_NAMES,
    chooseJiraBoard,
    connectJiraUrl,
    deleteRoom,
    disconnectJira,
    getMe,
    getRoom,
    jiraBoards,
    jiraSites,
    previewQueue,
    signInUrl,
    updateRoom,
  } from "../lib/api";
  import type {
    Delegate,
    JiraBoard,
    JiraSettings,
    JiraSite,
    Me,
    QueueFilter,
    QueuePreview,
    RoomInfo,
    RoomSettings,
    Scale,
  } from "../lib/types";

  let { slug }: { slug: string } = $props();

  let me = $state<Me | null>(null);
  let info = $state<RoomInfo | null | undefined>(undefined); // undefined while loading
  let loadError = $state<string | null>(null);

  // The form
  let shortName = $state("");
  let kind = $state<Scale["kind"]>("fibonacci");
  let tshirtText = $state("XS=1, S=2, M=3, L=5, XL=8, XXL=13");
  let customText = $state("");
  let timer = $state(30);
  let sound = $state(false);
  let autoReveal = $state(false);
  let delegates = $state<Delegate[]>([]);
  let newDelegate = $state("");
  let newProvider = $state<Delegate["provider"]>("google");
  let filter = $state<QueueFilter>({
    subtasks: false,
    in_progress: false,
    resolved: false,
    estimated: false,
    jql: "",
  });
  let preview = $state<QueuePreview | null>(null);
  let previewing = $state(false);
  let previewError = $state<string | null>(null);

  // Jira
  let jira = $state<JiraSettings | null>(null);
  let sites = $state<JiraSite[]>([]);
  let boards = $state<JiraBoard[]>([]);
  let siteId = $state("");
  let boardId = $state<number | null>(null);
  let jiraError = $state<string | null>(null);
  const jiraReturn = new URLSearchParams(location.search).get("jira");

  let saving = $state(false);
  let saved = $state(false);
  let error = $state<string | null>(null);
  let copied = $state(false);

  // svelte-ignore state_referenced_locally
  let current = $state(slug); // the room's slug as saved
  const link = $derived(`${location.origin}/r/${current}`);

  onMount(async () => {
    try {
      me = await getMe();
      info = await getRoom(slug);
      if (info) {
        current = info.slug;
        if (info.slug !== slug) history.replaceState(null, "", `/r/${info.slug}/settings`);
        if (info.settings) {
          load(info.settings);
          await loadJira(info.settings.jira);
        }
      }
    } catch (err) {
      loadError = err instanceof Error ? err.message : "Could not load the room.";
    }
  });

  function load(s: RoomSettings) {
    shortName = current;
    kind = s.scale.kind;
    const valued = s.scale.cards.filter((c) => c.value !== null);
    if (kind === "tshirt") tshirtText = valued.map((c) => `${c.label}=${c.value}`).join(", ");
    if (kind === "custom") customText = s.scale.cards.map((c) => c.label).join(", ");
    timer = s.timer_seconds;
    sound = s.sound;
    autoReveal = s.auto_reveal;
    delegates = s.delegates;
    filter = { ...s.queue_filter };
  }

  async function runPreview() {
    previewing = true;
    previewError = null;
    try {
      preview = await previewQueue(current, { ...filter, jql: filter.jql.trim() });
    } catch (err) {
      preview = null;
      previewError = err instanceof Error ? err.message : "Could not preview the queue.";
    } finally {
      previewing = false;
    }
  }

  async function loadJira(settings: JiraSettings) {
    jira = settings;
    siteId = settings.site?.cloud_id ?? "";
    boardId = settings.board?.id ?? null;
    if (!settings.available || !settings.connected) return;
    try {
      sites = await jiraSites(current);
      if (!siteId && sites.length === 1) siteId = sites[0].cloud_id;
      if (siteId) boards = await jiraBoards(current, siteId);
      jiraError = null;
    } catch (err) {
      jiraError = err instanceof Error ? err.message : "Could not reach Jira.";
    }
  }

  async function pickSite() {
    boards = [];
    boardId = null;
    if (!siteId) return;
    try {
      boards = await jiraBoards(current, siteId);
      jiraError = null;
    } catch (err) {
      jiraError = err instanceof Error ? err.message : "Could not load the boards.";
    }
  }

  async function disconnect() {
    if (!confirm("Disconnect Jira? Sessions in this room cannot load the backlog until you connect again.")) {
      return;
    }
    try {
      await disconnectJira(current);
      const fresh = await getRoom(current);
      if (fresh?.settings) await loadJira(fresh.settings.jira);
      sites = [];
      boards = [];
    } catch (err) {
      jiraError = err instanceof Error ? err.message : "Could not disconnect.";
    }
  }

  function scaleBody(): Record<string, unknown> {
    if (kind === "fibonacci") return { kind };
    if (kind === "custom") {
      const cards = customText.split(",").map((c) => c.trim()).filter(Boolean);
      if (cards.length === 0) throw new Error("Type at least one custom card.");
      return { kind, cards };
    }
    const mapping: Record<string, number> = {};
    for (const part of tshirtText.split(",").map((p) => p.trim()).filter(Boolean)) {
      const [label, value] = part.split("=").map((x) => x.trim());
      const n = Number(value);
      if (!label || value === undefined || !Number.isFinite(n) || n < 0) {
        throw new Error(`Write T-shirt points as SIZE=POINTS, such as M=3 (not "${part}").`);
      }
      mapping[label] = n;
    }
    if (Object.keys(mapping).length === 0) throw new Error("Give at least one T-shirt size.");
    return { kind, mapping };
  }

  function addDelegate() {
    const identifier = newDelegate.trim();
    if (!identifier) return;
    const entry = { provider: newProvider, identifier: identifier.toLowerCase() };
    if (!delegates.some((d) => d.provider === entry.provider && d.identifier === entry.identifier)) {
      delegates = [...delegates, entry];
    }
    newDelegate = "";
    saved = false;
  }

  function removeDelegate(d: Delegate) {
    delegates = delegates.filter((x) => x !== d);
    saved = false;
  }

  async function save() {
    error = null;
    saved = false;
    let body: Record<string, unknown>;
    try {
      body = {
        slug: shortName.trim(),
        scale: scaleBody(),
        timer_seconds: Number(timer),
        sound,
        auto_reveal: autoReveal,
        delegates,
        queue_filter: { ...filter, jql: filter.jql.trim() },
      };
    } catch (err) {
      error = err instanceof Error ? err.message : "Check the form.";
      return;
    }
    saving = true;
    try {
      let updated = await updateRoom(current, body);
      current = updated.slug;
      const savedBoard = updated.settings?.jira.board?.id ?? null;
      const savedSite = updated.settings?.jira.site?.cloud_id ?? "";
      if (jira?.connected && siteId && boardId !== null && (boardId !== savedBoard || siteId !== savedSite)) {
        updated = await chooseJiraBoard(current, siteId, boardId);
      }
      history.replaceState(null, "", `/r/${current}/settings`);
      if (updated.settings) {
        load(updated.settings);
        jira = updated.settings.jira;
      }
      saved = true;
    } catch (err) {
      error = err instanceof Error ? err.message : "Could not save.";
    } finally {
      saving = false;
    }
  }

  async function remove() {
    if (!confirm(`Delete the room ${current}? Its link stops working and this cannot be undone.`)) {
      return;
    }
    try {
      await deleteRoom(current);
      location.href = "/";
    } catch (err) {
      error = err instanceof Error ? err.message : "Could not delete the room.";
    }
  }

  async function copyLink() {
    try {
      await navigator.clipboard.writeText(link);
      copied = true;
      setTimeout(() => (copied = false), 2000);
    } catch {
      copied = false;
    }
  }
</script>

<header class="page-header">
  <span class="page-title">{current}</span>
  <span class="text-2">Room settings</span>
  <div class="right">
    <a class="back" href="/r/{current}">Back to room</a>
    {#if me?.signed_in}
      <div class="who">
        <span class="who-name">{me.name}</span>
        <span class="who-role"
          >{info?.access === "owner" ? "Owner" : info?.access === "delegate" ? "Delegate" : me.label}</span
        >
      </div>
    {/if}
  </div>
</header>

<main class="page-main">
  {#if loadError}
    <p class="form-error" role="alert">{loadError}</p>
  {:else if info === undefined || !me}
    <p>Loading…</p>
  {:else if info === null}
    <p>There is no room called {slug}. <a href="/">Your rooms</a></p>
  {:else if !me.signed_in}
    <section class="section">
      <h2>Sign in to change this room</h2>
      <div class="row">
        {#each me.providers as provider (provider)}
          <a class="btn link-btn" href={signInUrl(provider)}>Sign in with {PROVIDER_NAMES[provider]}</a>
        {/each}
      </div>
    </section>
  {:else if info.access !== "owner"}
    <p>Only the room's owner can change its settings. <a href="/r/{current}">Back to the room</a></p>
  {:else}
    <section class="section" aria-label="Room link">
      <h2>Room link</h2>
      <div class="row">
        <div class="field grow">
          <label for="slug">Short name</label>
          <input id="slug" class="input" bind:value={shortName} maxlength="40" autocomplete="off" />
        </div>
        <button class="btn" type="button" onclick={copyLink}>{copied ? "Copied" : "Copy link"}</button>
      </div>
      <span class="text-2">
        Players join at {link}. The link keeps working across restarts, and after a rename the old
        link redirects here.
      </span>
    </section>

    <section class="section" aria-label="Jira">
      <div class="jira-head">
        <h2>Jira Cloud</h2>
        {#if jira?.available && jira.connected}
          <div class="row tight">
            <span class="text-2">Connected as {jira.email ?? "your Atlassian account"}</span>
            <a class="btn link-btn" href={connectJiraUrl(current)}>Reconnect</a>
            <button class="btn" type="button" onclick={disconnect}>Disconnect</button>
          </div>
        {/if}
      </div>
      {#if jiraReturn === "connected"}
        <p class="saved" role="status">Jira is connected. Choose the site and board below.</p>
      {:else if jiraReturn === "denied"}
        <p class="form-error" role="alert">Connecting Jira was cancelled.</p>
      {/if}
      {#if !jira?.available}
        <span class="text-2">Jira is not set up on this server.</span>
      {:else if !jira.connected}
        <span class="text-2">
          Connect this room to Jira so sessions can load its backlog and write the agreed points.
          Every write goes through this connection, so Jira's history shows your account.
        </span>
        <a class="btn-primary link-primary" href={connectJiraUrl(current)}>Connect Jira</a>
      {:else}
        <div class="grid">
          <div class="field">
            <label for="site">Site</label>
            <select id="site" class="input" bind:value={siteId} onchange={pickSite}>
              <option value="" disabled>Choose a site</option>
              {#each sites as site (site.cloud_id)}
                <option value={site.cloud_id}>{site.url.replace("https://", "")}</option>
              {/each}
            </select>
          </div>
          <div class="field">
            <label for="board">Board</label>
            <select id="board" class="input" bind:value={boardId} disabled={!siteId}>
              <option value={null} disabled>Choose a board</option>
              {#each boards as board (board.id)}
                <option value={board.id}>{board.name}</option>
              {/each}
            </select>
          </div>
        </div>
        <span class="text-2">
          Sessions score the tickets in this board's backlog that have no estimate, in rank order.
          Every write goes through this connection, so Jira's history shows your account.
        </span>
      {/if}
      {#if jiraError}<p class="form-error" role="alert">{jiraError}</p>{/if}
    </section>

    <section class="section" aria-label="Queue filter">
      <h2>Queue filter</h2>
      <span class="text-2">
        Which backlog tickets a session walks through, in rank order. By default: stories, tasks and
        bugs in a To Do status, unresolved, with no estimate. Epics and tickets in a sprint never
        enter.
      </span>
      <fieldset>
        <legend class="label">Also include</legend>
        <label class="check">
          <input type="checkbox" bind:checked={filter.subtasks} />
          <span>Sub-tasks</span>
        </label>
        <label class="check">
          <input type="checkbox" bind:checked={filter.in_progress} />
          <span>Tickets in progress</span>
        </label>
        <label class="check">
          <input type="checkbox" bind:checked={filter.resolved} />
          <span>Resolved tickets</span>
        </label>
        <label class="check">
          <input type="checkbox" bind:checked={filter.estimated} />
          <span>Tickets that already have an estimate, to re-estimate them</span>
        </label>
      </fieldset>
      <div class="field">
        <label for="jql">Extra JQL (optional)</label>
        <input
          id="jql"
          class="input"
          maxlength="500"
          bind:value={filter.jql}
          placeholder="labels = frontend"
          aria-describedby="jql-help"
        />
        <span id="jql-help" class="label">Narrows the backlog, for example by label, component or fix version.</span>
      </div>
      <div class="row tight">
        <button
          class="btn"
          type="button"
          disabled={previewing || !jira?.connected || !jira?.board}
          onclick={runPreview}>{previewing ? "Previewing…" : "Preview queue"}</button
        >
        {#if !jira?.connected || !jira?.board}
          <span class="text-2">Connect Jira and choose a board to preview.</span>
        {/if}
      </div>
      <span class="text-2">Changes apply when a session loads the backlog, or when a facilitator reloads it.</span>
      {#if previewError}<p class="form-error" role="alert">{previewError}</p>{/if}
      {#if preview}
        <div class="preview" aria-label="Queue preview" role="region">
          <p class="preview-count" role="status">
            {preview.count} {preview.count === 1 ? "ticket" : "tickets"} would be in the queue
            <span class="text-2">({preview.total} in the filtered backlog)</span>
          </p>
          {#if preview.tickets.length}
            <ol class="preview-list">
              {#each preview.tickets as t (t.key)}
                <li>
                  {#if t.url}
                    <a class="preview-key" href={t.url} target="_blank" rel="noopener noreferrer">{t.key}</a>
                  {:else}
                    <span class="preview-key">{t.key}</span>
                  {/if}
                  <span class="preview-summary">{t.summary}</span>
                  {#if t.type}<span class="chip">{t.type}</span>{/if}
                  {#if t.status}<span class="chip">{t.status}</span>{/if}
                  {#if t.estimate !== null}<span class="chip">{points(t.estimate)}</span>{/if}
                </li>
              {/each}
            </ol>
            {#if preview.count > preview.tickets.length}
              <p class="text-2">…and {preview.count - preview.tickets.length} more</p>
            {/if}
          {/if}
        </div>
      {/if}
    </section>

    <section class="section" aria-label="Scale">
      <h2>Scale</h2>
      <fieldset>
        <legend class="label">Cards players vote with</legend>
        <label class="choice" class:chosen={kind === "fibonacci"}>
          <input type="radio" name="scale" value="fibonacci" bind:group={kind} />
          <span class="choice-name">Fibonacci</span>
          <span class="choice-text">1, 2, 3, 5, 8, 13, 21, 34, 55, ?</span>
        </label>
        <label class="choice" class:chosen={kind === "tshirt"}>
          <input type="radio" name="scale" value="tshirt" bind:group={kind} />
          <span class="choice-name">T-shirt</span>
          <span class="choice-text">XS, S, M, L, XL, XXL, ?</span>
        </label>
        <label class="choice" class:chosen={kind === "custom"}>
          <input type="radio" name="scale" value="custom" bind:group={kind} />
          <span class="choice-name">Custom list</span>
          <span class="choice-text">Your own cards, separated by commas</span>
        </label>
      </fieldset>
      {#if kind === "tshirt"}
        <div class="field">
          <label for="tshirt">T-shirt points</label>
          <input id="tshirt" class="input" bind:value={tshirtText} aria-describedby="tshirt-help" />
          <span id="tshirt-help" class="label">Each size and the story points it confirms as. "?" is added for you.</span>
        </div>
      {:else if kind === "custom"}
        <div class="field">
          <label for="custom">Custom cards</label>
          <input id="custom" class="input" bind:value={customText} placeholder="1, 2, 4, 8, 16" />
        </div>
      {/if}
    </section>

    <section class="section" aria-label="Countdown, sound and reveal">
      <h2>Countdown, sound and reveal</h2>
      <div class="row wide">
        <div class="field">
          <label for="default-secs">Default seconds</label>
          <input id="default-secs" class="input secs" type="number" min="1" max="3600" bind:value={timer} />
        </div>
        <label class="check">
          <input type="checkbox" bind:checked={sound} />
          <span>Play sounds: ticks for the last five seconds, a chime at zero, and a couple of surprises</span>
        </label>
        <label class="check">
          <input type="checkbox" bind:checked={autoReveal} />
          <span>Reveal the cards by themselves once everyone at the table has voted</span>
        </label>
      </div>
      <span class="text-2">Facilitators can change these for a running session; these are the defaults.</span>
    </section>

    <section class="section" aria-label="Delegates">
      <h2>Delegates</h2>
      <span class="text-2">Delegates can run sessions in this room. They cannot change these settings.</span>
      {#if delegates.length}
        <ul class="delegates">
          {#each delegates as d (d.provider + d.identifier)}
            <li>
              <span class="who-name">{d.identifier}</span>
              <span class="chip">{PROVIDER_NAMES[d.provider]}</span>
              <button class="remove" type="button" onclick={() => removeDelegate(d)}
                aria-label="Remove {d.identifier}">Remove</button>
            </li>
          {/each}
        </ul>
      {/if}
      <div class="row">
        <div class="field grow">
          <label for="delegate">Google email or GitHub username</label>
          <input
            id="delegate"
            class="input"
            bind:value={newDelegate}
            autocomplete="off"
            onkeydown={(e) => e.key === "Enter" && (e.preventDefault(), addDelegate())}
          />
        </div>
        <div class="field">
          <label for="provider">Signs in with</label>
          <select id="provider" class="input" bind:value={newProvider}>
            <option value="google">Google</option>
            <option value="github">GitHub</option>
          </select>
        </div>
        <button class="btn" type="button" onclick={addDelegate}>Add delegate</button>
      </div>
    </section>

    {#if error}<p class="form-error" role="alert">{error}</p>{/if}
    {#if saved}<p class="saved" role="status">Saved.</p>{/if}
    <div class="actions">
      <button class="btn danger" type="button" onclick={remove}>Delete room</button>
      <button class="btn-primary save" type="button" disabled={saving} onclick={save}
        >{saving ? "Saving…" : "Save changes"}</button
      >
    </div>
  {/if}
</main>

<style>
  .right {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 16px;
    margin-left: auto;
  }
  .back {
    display: flex;
    align-items: center;
    min-height: 44px;
    font-weight: 600;
  }
  .row {
    display: flex;
    flex-wrap: wrap;
    align-items: flex-end;
    gap: 12px;
  }
  .row.tight {
    align-items: center;
  }
  .jira-head {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
  }
  .grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(min(260px, 100%), 1fr));
    gap: 12px;
  }
  .link-primary {
    align-self: flex-start;
    display: inline-flex;
    align-items: center;
    padding: 0 20px;
    text-decoration: none;
  }
  .row.wide {
    gap: 20px;
  }
  .grow {
    flex: 1 1 240px;
    min-width: 0;
  }
  .link-btn {
    display: inline-flex;
    align-items: center;
    color: var(--ink);
    text-decoration: none;
    font-weight: 600;
  }
  fieldset {
    margin: 0;
    padding: 0;
    border: none;
    display: flex;
    flex-direction: column;
    gap: 10px;
  }
  legend {
    padding: 0;
    margin-bottom: 8px;
  }
  .choice {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 10px;
    min-height: 44px;
    padding: 0 12px;
    border: 1px solid var(--border-strong);
    border-radius: 8px;
    cursor: pointer;
  }
  .choice.chosen {
    border: 1.5px solid var(--accent);
  }
  .choice input,
  .check input {
    width: 18px;
    height: 18px;
    margin: 0;
    accent-color: var(--accent);
  }
  .choice-name {
    font-weight: 600;
  }
  .choice-text {
    color: var(--text-2);
  }
  .secs {
    width: 120px;
  }
  .check {
    display: flex;
    align-items: center;
    gap: 10px;
    min-height: 44px;
  }
  .delegates {
    list-style: none;
    margin: 0;
    padding: 0;
    border: 1px solid var(--border);
    border-radius: 8px;
  }
  .delegates li {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 12px;
    padding: 6px 6px 6px 14px;
    border-bottom: 1px solid var(--border);
  }
  .delegates li:last-child {
    border-bottom: none;
  }
  .chip {
    padding: 2px 10px;
    border-radius: 999px;
    background: var(--chip);
    font-size: 13px;
    color: var(--text-2);
  }
  .preview {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .preview-count {
    font-weight: 600;
  }
  .preview-list {
    margin: 0;
    padding: 0;
    list-style: none;
    border: 1px solid var(--border);
    border-radius: 8px;
    max-height: 420px;
    overflow-y: auto;
  }
  .preview-list li {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 8px 12px;
    padding: 8px 14px;
    border-bottom: 1px solid var(--border);
  }
  .preview-list li:last-child {
    border-bottom: none;
  }
  .preview-key {
    font-weight: 600;
    white-space: nowrap;
  }
  .preview-summary {
    flex: 1 1 200px;
    min-width: 0;
  }
  .remove {
    margin-left: auto;
    min-height: 44px;
    padding: 0 14px;
    border: none;
    border-radius: 8px;
    background: none;
    font-weight: 500;
  }
  .actions {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    padding-top: 4px;
  }
  .danger {
    border-color: var(--danger);
    color: var(--danger);
    font-weight: 600;
  }
  .save {
    min-height: 48px;
    padding: 0 24px;
  }
  .saved {
    margin: 0;
    font-weight: 600;
    color: var(--link);
  }
  p {
    margin: 0;
  }
</style>
