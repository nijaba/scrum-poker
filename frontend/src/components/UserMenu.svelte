<script lang="ts">
  /**
   * Your name and role in the room header, as a button that opens a small menu:
   * Your rooms and Log out for anyone signed in, Room settings too for the owner and
   * co-owners, Change name for anyone seated, and Log out for everyone.
   */
  import { tick } from "svelte";
  import { THEMES, setTheme, theme } from "../lib/theme.svelte";

  let {
    name,
    role,
    signedIn,
    settingsHref,
    onlogout,
    info = [],
    muted = null,
    onmute,
    remote = null,
    onremote,
    ontour,
    onrename,
  }: {
    name: string;
    role: string;
    signedIn: boolean;
    settingsHref: string | null; // only the owner gets one
    onlogout: () => void;
    /** On a phone: the counters the wide header shows, as lines of text. */
    info?: string[];
    /** On a phone, when the room has sound: the local mute, as a menu switch. */
    muted?: boolean | null;
    onmute?: () => void;
    /** On a phone, for a player: Remote view on or off. */
    remote?: boolean | null;
    onremote?: () => void;
    /** Start the room's tour. */
    ontour?: () => void;
    /** For anyone seated: open the Change name form. */
    onrename?: () => void;
  } = $props();

  let open = $state(false);
  let root: HTMLDivElement;
  let button: HTMLButtonElement;
  let menu = $state<HTMLDivElement | null>(null);

  function entries(): HTMLElement[] {
    return menu ? Array.from(menu.querySelectorAll<HTMLElement>('[role^="menuitem"]')) : [];
  }

  async function show() {
    open = true;
    await tick();
    entries()[0]?.focus();
  }

  function hide(refocus = true) {
    open = false;
    if (refocus) button.focus();
  }

  function toggle() {
    if (open) hide();
    else show();
  }

  function onMenuKey(event: KeyboardEvent) {
    const items = entries();
    const at = items.indexOf(document.activeElement as HTMLElement);
    if (event.key === "Escape") {
      event.preventDefault();
      hide();
    } else if (event.key === "ArrowDown") {
      event.preventDefault();
      items[(at + 1) % items.length]?.focus();
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      items[(at - 1 + items.length) % items.length]?.focus();
    } else if (event.key === "Home") {
      event.preventDefault();
      items[0]?.focus();
    } else if (event.key === "End") {
      event.preventDefault();
      items[items.length - 1]?.focus();
    } else if (event.key === "Tab") {
      hide(false);
    }
  }

  function onWindowPointer(event: PointerEvent) {
    if (open && !root.contains(event.target as Node)) hide(false);
  }

  function logOut() {
    open = false;
    onlogout();
  }
</script>

<svelte:window onpointerdown={onWindowPointer} />

<div class="user-menu" bind:this={root} data-tour="menu">
  <button
    bind:this={button}
    class="who-btn"
    type="button"
    aria-haspopup="menu"
    aria-expanded={open}
    aria-controls={open ? "user-menu-list" : undefined}
    onclick={toggle}
  >
    <span class="who">
      <span class="who-name">{name}</span>
      <span class="who-role">{role}</span>
    </span>
    <svg class="chevron" class:up={open} aria-hidden="true" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="m6 9 6 6 6-6"></path></svg>
  </button>

  {#if open}
    <!-- svelte-ignore a11y_interactive_supports_focus -->
    <div
      bind:this={menu}
      id="user-menu-list"
      class="menu"
      role="menu"
      aria-label="Account"
      onkeydown={onMenuKey}
    >
      {#if info.length}
        <div class="info">
          {#each info as line (line)}<span>{line}</span>{/each}
        </div>
      {/if}
      {#if remote !== null}
        <button
          class="item radio"
          role="menuitemcheckbox"
          type="button"
          aria-checked={remote}
          onclick={() => {
            open = false;
            onremote?.();
          }}>Remote view</button
        >
      {/if}
      {#if muted !== null}
        <button
          class="item radio"
          role="menuitemcheckbox"
          type="button"
          aria-checked={muted}
          onclick={() => onmute?.()}>Mute</button
        >
      {/if}
      {#if signedIn}
        <a class="item" role="menuitem" href="/">Your rooms</a>
      {/if}
      {#if signedIn && settingsHref}
        <a class="item" role="menuitem" href={settingsHref}>Room settings</a>
      {/if}
      <div class="group" role="group" aria-label="Theme">
        <span class="group-label" aria-hidden="true">Theme</span>
        {#each THEMES as t (t.value)}
          <button
            class="item radio"
            role="menuitemradio"
            type="button"
            aria-checked={theme.value === t.value}
            onclick={() => setTheme(t.value)}>{t.label}</button
          >
        {/each}
      </div>
      {#if onrename}
        <button
          class="item"
          role="menuitem"
          type="button"
          onclick={() => {
            hide(false);
            onrename();
          }}>Change name</button
        >
      {/if}
      {#if ontour}
        <button
          class="item"
          role="menuitem"
          type="button"
          onclick={() => {
            hide();
            ontour();
          }}>Tour</button
        >
      {/if}
      <button class="item" role="menuitem" type="button" onclick={logOut}>Log out</button>
    </div>
  {/if}
</div>

<style>
  .user-menu {
    position: relative;
  }
  .who-btn {
    display: flex;
    align-items: center;
    gap: 6px;
    min-height: 44px;
    padding: 0 8px 0 4px;
    border: 1px solid transparent;
    border-radius: 8px;
    background: none;
    color: var(--ink);
    font: inherit;
    text-align: left;
    cursor: pointer;
  }
  .who-btn:hover,
  .who-btn[aria-expanded="true"] {
    border-color: var(--border);
    background: var(--chip);
  }
  .who-btn:focus-visible {
    outline: 2px solid var(--link);
    outline-offset: 2px;
  }
  /* Phone: the first name only, so the header stays one row. */
  @media (max-width: 640px) {
    .who-role {
      display: none;
    }
    .who-name {
      display: block;
      max-width: 96px;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
  }
  .chevron {
    flex: none;
    color: var(--text-3);
    transition: transform 0.15s;
  }
  .chevron.up {
    transform: rotate(180deg);
  }
  .menu {
    position: absolute;
    top: calc(100% + 6px);
    right: 0;
    z-index: 20;
    display: flex;
    flex-direction: column;
    min-width: 180px;
    padding: 6px;
    border: 1px solid var(--border);
    border-radius: 10px;
    background: var(--surface);
    box-shadow: var(--menu-shadow);
  }
  .item {
    display: flex;
    align-items: center;
    min-height: 44px;
    padding: 0 12px;
    border: none;
    border-radius: 6px;
    background: none;
    color: var(--ink);
    font: inherit;
    font-size: 14px;
    text-align: left;
    text-decoration: none;
    cursor: pointer;
  }
  .info {
    display: flex;
    flex-direction: column;
    gap: 2px;
    padding: 8px 12px 10px;
    margin-bottom: 4px;
    border-bottom: 1px solid var(--border);
    font-size: 13px;
    color: var(--text-2);
  }
  .group {
    display: flex;
    flex-direction: column;
    margin: 4px 0;
    padding: 4px 0;
    border-top: 1px solid var(--border);
    border-bottom: 1px solid var(--border);
  }
  .group:first-child {
    margin-top: 0;
    border-top: none;
  }
  .group-label {
    padding: 4px 12px 0;
    font-size: 12px;
    font-weight: 600;
    color: var(--text-3);
  }
  /* A check mark beside the chosen theme or a switch that is on, never colour alone. */
  .radio::before {
    content: "";
    width: 18px;
    flex: none;
  }
  .radio[aria-checked="true"]::before {
    content: "✓";
    font-weight: 700;
  }
  .item:hover,
  .item:focus-visible {
    background: var(--chip);
    outline: none;
  }
  .item:focus-visible {
    box-shadow: inset 0 0 0 2px var(--link);
  }
</style>
