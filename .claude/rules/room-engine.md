---
paths:
  - "app/room/**"
  - "tests/**/test_room*.py"
---

# Room engine rules

- One asyncio task per live room owns the state. Everything else sends it commands through a queue; nothing mutates room state from outside the task.
- Build each client's snapshot separately. Before reveal, a snapshot lists who has voted and never includes another player's card value.
- Keep the engine pure where you can: rounds, queue, results and scales are plain classes with no I/O, tested at Unit level. The asyncio task and the WebSocket layer wrap them.
- Time comes from an injected clock so countdown tests do not sleep.
- Results on reveal: average to one decimal, median, consensus. Cards with no numeric value (such as "?") are left out. T-shirt cards count by their mapped value.
- Counters are computed from per-ticket results every time. Do not keep running totals.
- Nothing in this package writes to SQLite.
- Name tests after the test-plan case they prove, for example `test_rq05_rewind_replaces_estimate`.
