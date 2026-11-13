# Mock-ups

Static HTML copies of the four screens in the Claude design canvas
[Scrum poker UI mock-up](https://claude.ai/artifact/4UNXp1rViwcrJTdVyrozR4). Open them in a browser.
They are pictures of the target UI, not working code: nothing is clickable and the data is sample data.

| File | Screen |
| --- | --- |
| `room-voting.html` | The room while voting, facilitator view |
| `room-revealed.html` | The room after reveal: cards, average, median, consensus, final-points picker |
| `room-settings.html` | The owner's room settings: link, Jira board, scale, countdown and sound, delegates |
| `mini-window.html` | The always-on-top mini window, 340 by 256 px |

## Tokens

| Token | Value | Used for |
| --- | --- | --- |
| Ground | `#F2F4F3` | Page background |
| Surface | `#FFFFFF` | Panels and cards in the hand |
| Ink | `#111614` | Main text |
| Secondary text | `#2B3430`, `#3B4641` | Descriptions, labels |
| Border | `#D9DFDC`, `#B8C2BD` | Panel and control borders |
| Chip | `#E6EAE8` | Chips, counters, disabled controls |
| Table green | `#123B2E` | The players panel and the mini window |
| On table | `#E9F2EE`, `#A9C4B8` | Text on the table green |
| Card back | `#C9DDD3` | A face-down card |
| Card face | `#F4F8F6` | Mock-up only: a face-up card on the table (the app now uses card stock) |
| Card stock | `#FBFCFB` | The face of a playing card, in the hand, on the table and in the mini window |
| Card edge | `#CFD7D3` | A playing card's 1 px edge |
| Suit red | `#B0281D` | Hearts and diamonds |
| Accent | `#A84B0A` | Selected card, primary button, running countdown |
| Link | `#0F5C45` | Links |
| Danger | `#8E1B1B` | Delete room |

Cards look like they come from a deck (`frontend/src/components/CardFace.svelte`, `.deck-card` and `.deck-back` in `app.css`): a value and suit in the top-left and bottom-right corners, a large value in the middle, and a lattice back in table green. Suits go ♠ ♥ ♣ ♦ by position in the scale; cards with no value, such as "?", get none. Up to twelve cards fan out in the hand; the chosen card straightens, rises and gets a 2 px accent edge. On the table, each card lies at a small tilt taken from the player's id and turns over on reveal. The mini window keeps only the top-left value and the large value. The static mock-ups below predate this and still show flat cards.

Type: Inter for text, Space Grotesk for headings, numerals and card values.
Radius: 8 px on controls, 10 px on panels, 14 px on the table.
The sample data matches `tests/fixtures/fake_backlog.json`: the current ticket is SHOP-142, fourth of eight in the queue.
