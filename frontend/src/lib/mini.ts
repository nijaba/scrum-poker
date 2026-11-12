// Mini mode: a small window with the ticket key, countdown, card row and voted
// count. It uses the Document Picture-in-Picture API, which keeps the window on
// top, where the browser has it, and a small popup otherwise. Both render the
// same view, mounted from this tab: the main tab keeps the one connection.

import { mount, unmount } from "svelte";
import MiniView from "../components/MiniView.svelte";
import type { RoomConnection } from "./room.svelte";

const WIDTH = 340;
const HEIGHT = 256;

interface DocumentPictureInPicture {
  requestWindow(options: { width: number; height: number }): Promise<Window>;
}

declare global {
  interface Window {
    documentPictureInPicture?: DocumentPictureInPicture;
  }
}

let current: Window | null = null;

export function miniOpen(): boolean {
  return !!current && !current.closed;
}

/**
 * Opens the mini window, or brings the open one forward. Call it from a click:
 * both the API and popups need a user gesture. `onclose` runs when it closes.
 */
export async function openMini(
  room: RoomConnection,
  ontick: () => void,
  onclose: () => void,
): Promise<void> {
  if (current && !current.closed) {
    current.focus();
    return;
  }
  const win = await openWindow();
  if (!win) return;
  current = win;

  const doc = win.document;
  doc.title = `${room.slug} · Scrum poker`;
  doc.documentElement.lang = "en";
  copyHead(doc);
  doc.body.className = "mini-body";
  doc.body.replaceChildren();

  const view = mount(MiniView, { target: doc.body, props: { room, timers: win, ontick } });

  // The main tab owns the connection, so the mini window goes when it goes.
  // A Picture-in-Picture window does this by itself; a popup does not.
  const closeWithTab = () => win.close();
  window.addEventListener("pagehide", closeWithTab);

  win.addEventListener("pagehide", () => {
    window.removeEventListener("pagehide", closeWithTab);
    void unmount(view);
    if (current === win) current = null;
    onclose();
  });
}

async function openWindow(): Promise<Window | null> {
  const pip = window.documentPictureInPicture;
  if (pip) {
    try {
      return await pip.requestWindow({ width: WIDTH, height: HEIGHT });
    } catch {
      // Not allowed here (no gesture, or not a secure page): use the popup.
    }
  }
  return window.open("", "scrum-poker-mini", `popup,width=${WIDTH},height=${HEIGHT}`);
}

/** The new window starts blank: give it this page's styles, fonts and icon. */
function copyHead(doc: Document): void {
  const nodes = document.head.querySelectorAll('style, link[rel="stylesheet"], link[rel="icon"]');
  for (const node of nodes) {
    if (node instanceof HTMLLinkElement) {
      const link = doc.createElement("link");
      link.rel = node.rel;
      link.href = node.href; // absolute, so it resolves from the blank window
      if (node.type) link.type = node.type;
      if (node.sizes.value) link.setAttribute("sizes", node.sizes.value);
      doc.head.append(link);
    } else {
      const style = doc.createElement("style");
      style.textContent = node.textContent;
      doc.head.append(style);
    }
  }
}
