# Scrum poker test plan

> Copied on 2026-11-11 from the Claude doc [Scrum poker test plan](https://claude.ai/artifact/SUNjJfvXDa6aMV6GUCHHB4).
> If this file and the doc disagree, ask the owner which one is current.

Every requirement in the [Scrum poker design](design.md) has at least one test case here, grouped by area and run at the cheapest level that proves it.

## Approach

Tests run at five levels, and each case below names its level. A build step ships when the cases for its area pass.

| Level | Covers | Tool |
| --- | --- | --- |
| Unit | Room engine rules with no network: rounds, queue, results, scales | pytest |
| Integration | HTTP and WebSocket endpoints, the SQLite store, Jira calls against a fake Jira | pytest with the FastAPI test client |
| E2E | Whole flows in real browsers, one facilitator and several players at once | Playwright |
| Sandbox | Jira calls against a real Jira Cloud test site | pytest, run before each release |
| Manual | What automation cannot judge: always-on-top behaviour and sound | Checklist, run before each release |

## Test data and environments

The cases below assume these fixtures. The fake backlog gives known counters: 4 of 12 tickets estimated, 16 points.

| Item | What it is | Used by |
| --- | --- | --- |
| Fake backlog | 12 tickets in a fixed rank order: 8 without an estimate, 4 with estimates totalling 16 points | Unit, Integration, E2E |
| Fake Jira | A local stand-in for Atlassian sign-in and the board, backlog and estimation endpoints, that can be told to fail | Integration, E2E |
| Fake SSO provider | A local OAuth stand-in that signs in an owner, a delegate and an outsider | Integration, E2E |
| Jira sandbox | A Jira Cloud test site with one company-managed and one team-managed board | Sandbox |
| Real SSO accounts | One Google and one GitHub test account | Manual |
| Browsers | Desktop Chrome, Edge, Firefox and Safari | E2E, Manual |

## Room engine

### Rounds and reveal

| ID | Case | Expected | Level |
| --- | --- | --- | --- |
| RE-01 | Three players vote | Everyone sees three face-down cards; no client receives a value | Integration |
| RE-02 | Facilitator reveals | All cards turn face up on every screen | E2E |
| RE-03 | Player changes a vote before reveal | The latest card counts and stays hidden | Unit |
| RE-04 | Player votes after reveal | The vote is rejected | Unit |
| RE-05 | Facilitator restarts the vote | Cards clear and voting reopens | Unit |
| RE-06 | Player sends a facilitator command | The command is rejected | Integration |

### Results on reveal

| ID | Case | Expected | Level |
| --- | --- | --- | --- |
| RR-01 | Votes 3, 5, 5 | Average 4.3, median 5, most chosen 5 (2 of 3) | Unit |
| RR-02 | Votes 5, 5, 5 | Average 5.0, median 5, consensus on 5 | Unit |
| RR-03 | Votes 3, 5 and "?" | "?" is left out: average 4.0, median 4 | Unit |
| RR-04 | T-shirt votes S, M, M with S=2 and M=3 | Average 2.7, median 3, most chosen M (2 of 3) | Unit |
| RR-05 | Every player votes "?" | No average or median is shown | Unit |
| RR-06 | Reveal with three players | All three figures show on every screen | E2E |
| RR-07 | Votes 3, 5, 5, 8 and "?" | The spread lists 3 (1), 5 (2), 8 (1), ? (1) in scale order; highest card 8, lowest 3 | Unit |
| RR-08 | Votes 5, 5, 5 | No highest or lowest card is marked | Unit |
| RR-09 | Reveal 3, 5 and 8 in the browser | Every screen shows the spread bars and marks the players who chose 8 and 3 as highest and lowest | E2E |

### Queue and counters

| ID | Case | Expected | Level |
| --- | --- | --- | --- |
| RQ-01 | Session starts on the fake backlog | Queue holds the 8 unestimated tickets in rank order; backlog counter shows 4 of 12, 16 points | Unit |
| RQ-02 | Facilitator confirms 5 points | Session counter shows 1 ticket, 5 points; backlog shows 5 of 12, 21 points; the next ticket loads | Unit |
| RQ-03 | Facilitator skips | The next ticket loads; counters stay the same | Unit |
| RQ-04 | Facilitator rewinds | The previous ticket loads with its result | Unit |
| RQ-05 | Rewind, then confirm 8 instead of 5 | Session counter shows 1 ticket, 8 points; backlog shows 5 of 12, 24 points | Unit |
| RQ-06 | Rewind on the first ticket | Nothing changes | Unit |
| RQ-07 | Full session in the browser: vote, reveal, confirm, skip, rewind | Every screen follows the facilitator and shows the same counters | E2E |
| RQ-08 | Facilitator jumps to the third ticket after the current one | It loads; the tickets passed over stay pending; the counters do not change | Unit |
| RQ-09 | Rewind after a jump | The ticket just before it in the queue loads | Unit |
| RQ-10 | Jump to a key that is not in the queue | Rejected; nothing changes | Unit |
| RQ-11 | Facilitator chooses a ticket in Up next, in the browser | Every screen moves to that ticket | E2E |

### Countdown and sound

| ID | Case | Expected | Level |
| --- | --- | --- | --- |
| RC-01 | Start the countdown with no setting | It runs 30 s on every screen | Integration |
| RC-02 | Start the countdown set to 45 s | It runs 45 s | Integration |
| RC-03 | Countdown expires | "Time's up" shows; cards stay hidden | Integration |
| RC-04 | Player joins mid-countdown | Sees the same remaining time, within 1 s | E2E |
| RC-05 | Sound left at its default | No sound plays | Manual |
| RC-06 | Sound switched on | Ticks in the last five seconds and a chime at zero | Manual |
| RC-07 | One player mutes locally | That player hears nothing; the others still do | Manual |

### Scales

| ID | Case | Expected | Level |
| --- | --- | --- | --- |
| RS-01 | Owner picks Fibonacci | Players see the Fibonacci cards | Integration |
| RS-02 | Owner picks T-shirt | Players see sizes; confirmed points use the mapped value | Integration |
| RS-03 | Owner enters a custom list | Players see exactly those cards, in order | Integration |
| RS-04 | Owner changes the scale between rounds | The next round uses the new cards | Unit |

### Room reset

| ID | Case | Expected | Level |
| --- | --- | --- | --- |
| RX-01 | Reset with 3 connected players and 2 who left | The player list shows only the 3 connected players | Integration |
| RX-02 | A departed player returns after the reset | Seated as a new player, with the name from the cookie | E2E |
| RX-03 | Reset after two confirmed tickets | Queue position and session counters stay the same | Unit |
| RX-04 | Reset during a vote | Cards clear and voting reopens | Unit |

### Auto-reveal

| ID | Case | Expected | Level |
| --- | --- | --- | --- |
| RV-01 | Auto-reveal on; the last of three connected players votes | The cards reveal on every screen | Integration |
| RV-02 | Auto-reveal on; one seated player is away | The cards reveal once the connected players have voted | Unit |
| RV-03 | Auto-reveal off; everyone votes | The cards stay face down | Unit |
| RV-04 | Owner saves auto-reveal on in the room settings | A live session switches on; new sessions start with it on | Integration |
| RV-05 | Facilitator switches auto-reveal for the session | The session follows; the saved setting does not change | Integration |
| RV-06 | Auto-reveal switched on after everyone has voted | The cards reveal at once | Unit |
| RV-07 | Auto-reveal on; a player sends auto-reveal commands | Rejected | Integration |

### Sitting out and removing players

| ID | Case | Expected | Level |
| --- | --- | --- | --- |
| SO-01 | A player sits out | They leave the table, their vote is dropped and the voted count stops counting them; they still see the room | Unit |
| SO-02 | A player who sits out votes | Rejected | Unit |
| SO-03 | A player sits out, then joins the table | Seated again and can vote | Unit |
| SO-04 | Reset while a player sits out | They still sit out after checking in | Unit |
| SO-05 | The facilitator sits out in the browser | The table lists them as watching; the facilitator panel still works | E2E |
| RP-01 | Facilitator removes a player | The seat and its vote disappear on every screen | Integration |
| RP-02 | The removed player, in the browser | Sees that a facilitator removed them, and can join again | E2E |
| RP-03 | A player sends a remove command | Rejected | Integration |

### Session summary

| ID | Case | Expected | Level |
| --- | --- | --- | --- |
| SM-01 | Confirm two tickets and skip one | Facilitators' snapshots list the three in queue order, with status, points, average and vote counts per card, and no names | Integration |
| SM-02 | A player's snapshot | Holds no summary | Integration |
| SM-03 | Rewind and re-estimate a ticket | The summary lists it once, with the new points and votes | Unit |
| SM-04 | Facilitator copies the summary and downloads the CSV, in the browser | The text and the CSV list the same tickets and points | E2E |

## Jira Cloud

| ID | Case | Expected | Level |
| --- | --- | --- | --- |
| JC-01 | Owner connects the room to Jira | Consent asks for the seven scopes; the room can list boards | Sandbox |
| JC-02 | Load the backlog | Tickets arrive in Jira's rank order | Sandbox |
| JC-03 | Backlog mixes estimated and unestimated tickets | Only unestimated tickets enter the queue | Integration |
| JC-04 | Backlog of 120 tickets | All 120 load, in rank order | Integration |
| JC-05 | Confirm 5 points on a company-managed board | The ticket's estimate reads 5 in Jira | Sandbox |
| JC-06 | Confirm 5 points on a team-managed board | The ticket's estimate reads 5 in Jira | Sandbox |
| JC-07 | Jira rejects the write | The facilitator sees the error; the room stays on the ticket | Integration |
| JC-08 | Jira is unreachable on confirm | The room stays on the ticket; a retry succeeds once Jira is back | Integration |
| JC-09 | Access token expires mid-session | The app refreshes it, stores the new refresh token, and the write succeeds | Integration |
| JC-10 | Refresh token is no longer valid | Facilitators see that the owner must reconnect Jira | Integration |
| JC-11 | Delegate confirms points | The write uses the room's connection; Jira's history names the owner | Sandbox |
| JC-12 | The room's Jira connection is missing or lapsed when a facilitator confirms | Facilitators see that the owner must connect Jira; the room stays on the ticket | Integration |
| JC-13 | Inspect the SQLite file | Refresh tokens are stored encrypted | Integration |
| JC-14 | Ticket card | Shows key and link, type, priority, epic, labels and description; a long description is collapsed | E2E |
| JC-15 | Backlog holds epics, with and without an estimate | Epics are left out of the queue and the backlog counters; a type at Jira's epic level counts as an epic whatever its name | Integration |
| JC-16 | Backlog holds sub-tasks, with and without an estimate | Sub-tasks are left out of the queue and the backlog counters; a type at Jira's sub-task level, or flagged as a sub-task, counts as one whatever its name | Integration |
| JC-17 | Backlog holds tickets in progress, in review and done, and To Do tickets whose status has another name | Only tickets in Jira's To Do status category enter the queue and the backlog counters | Integration |
| JC-18 | Backlog response holds tickets in the active sprint, a future sprint and a closed sprint | The active- and future-sprint tickets are left out; the closed-sprint ticket enters the queue | Integration |
| JC-19 | Backlog holds resolved tickets, one in a To Do status | Resolved tickets are left out of the queue and the backlog counters, whatever their status | Integration |

## Auth, rooms and delegates

| ID | Case | Expected | Level |
| --- | --- | --- | --- |
| AR-01 | Owner signs in with Google | A signed session cookie is set; the owner can create rooms | Integration |
| AR-02 | Owner signs in with GitHub | A signed session cookie is set; the owner can create rooms | Integration |
| AR-03 | Sign in with the real Google and GitHub accounts | Both complete end to end | Manual |
| AR-04 | Account not on the allowlist signs in | It cannot create rooms | Integration |
| AR-05 | Request with a tampered session cookie | Treated as signed out | Integration |
| AR-06 | Owner creates the room "team-a" | The room opens at `/r/team-a` | Integration |
| AR-07 | A second room is named "team-a" | Rejected as taken | Integration |
| AR-08 | Owner creates a second room under another name | Both rooms run independently | Integration |
| AR-09 | Owner lists a delegate by Google email | That account gets the session controls, in that room only | Integration |
| AR-10 | Owner lists a delegate by GitHub username | That account gets the session controls, in that room only | Integration |
| AR-11 | Delegate tries to change the scale, edit delegates or delete the room | Rejected | Integration |
| AR-12 | Outsider sets a display name equal to a delegate's | Gets no controls | Integration |
| AR-13 | Owner removes a delegate | That account loses the controls | Integration |
| AR-14 | Player opens the room link | Joins after typing a name, with no sign-in | E2E |
| AR-15 | Player returns later in the same browser | Joins without the name prompt | E2E |
| AR-16 | Player's connection drops and comes back | The player gets the same seat back | E2E |

## Mini mode

The always-on-top window is checked by hand. Its content is automated through the popup fallback, which renders the same view.

| ID | Case | Expected | Level |
| --- | --- | --- | --- |
| MM-01 | Open mini mode in Chrome, Edge and Firefox | A small window opens and stays above other windows | Manual |
| MM-02 | Look at the mini view | Shows the ticket key, countdown, card row and voted count | E2E |
| MM-03 | Vote from the mini view | The vote registers and the main tab shows the same card | E2E |
| MM-04 | Facilitator moves to the next ticket | The mini view updates | E2E |
| MM-05 | Open mini mode in Safari | A normal small popup opens with the same view | Manual |
| MM-06 | Countdown ends with sound on and the mini window open | The chime plays | Manual |
| MM-07 | Close the main tab | The mini window closes | Manual |

## HTTPS

| ID | Case | Expected | Level |
| --- | --- | --- | --- |
| HS-01 | Open the app over plain HTTP | Redirected to HTTPS | Integration |
| HS-02 | Load a page over HTTPS | The response carries an HSTS header | Integration |
| HS-03 | Join a room over HTTPS | The room connects over a secure WebSocket | E2E |
| HS-04 | Inspect the session cookie and the player cookie | Both are marked Secure | Integration |
| HS-05 | Sign in with Google, GitHub and Atlassian | Each returns to an `https://` callback address | Integration |

## Packaging

| ID | Case | Expected | Level |
| --- | --- | --- | --- |
| PK-01 | Build the image from a clean checkout | The build succeeds and the container starts from environment variables alone | Integration |
| PK-02 | Open the app from the running container | The page loads and a WebSocket connects | E2E |
| PK-03 | Restart the container with the volume attached | Rooms, delegates and settings are still there; `/r/team-a` still opens | Integration |
| PK-04 | Restart during a live session | Votes and session counters are gone; points confirmed earlier are still in Jira | Integration |
| PK-05 | Inspect the SQLite file after a session | It holds no votes, results or session counters | Integration |
| PK-06 | Two rooms run sessions at once | Neither room sees the other's players or votes | Integration |
