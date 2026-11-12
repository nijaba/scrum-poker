# Front end

Svelte with TypeScript on Vite (decided by the owner on 2026-11-11). The screens follow `docs/mockups/`.

```bash
npm install
npm run build   # writes dist/, which the Python app serves at / and /r/<slug>
npm run dev     # Vite on :5173, proxying /api and /ws to uvicorn on :8000
npm run check   # svelte-check, failing on warnings
```

- `src/lib/room.svelte.ts`: the room WebSocket; holds the latest snapshot, answers reset check-ins, reconnects
- `src/lib/sound.ts`: Web Audio ticks and chime, and the local mute
- `src/components/`: the room screens

The client never decides game state: it renders the server's snapshot and sends commands.
