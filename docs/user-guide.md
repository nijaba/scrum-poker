# Scrum poker user guide

Scrum poker walks your team through the Jira tickets that still need an estimate, one at a
time, in the order they sit in your backlog. Everyone picks a card in secret, the cards turn
over together, and the agreed points go straight back to Jira.

This guide has three parts, one per role. Read the one that matches what you do:

- [Players](#players): you got a link and want to vote
- [Facilitators](#facilitators): you run the session
- [Room owners](#room-owners): you set the room up

## Who does what

| Role | Signs in? | What they can do |
| --- | --- | --- |
| Player | No, just types a name | Vote on each ticket |
| Delegate | Yes, with Google or GitHub | Everything a player can, plus run the session |
| Owner | Yes, with Google or GitHub | Everything a delegate can, plus change the room's settings, connect it to Jira and delete it |

Owners and delegates are both *facilitators* while a session runs: they see the facilitator
panel on the right of the room (under the cards on a phone). A room can have several
facilitators at once.

## Players

### Joining

1. Open the room link your facilitator shared, such as `https://poker.nijalabs.com/r/team-a`.
2. Type your name (up to 40 characters) and choose **Join room**.

There is no account and no password. Your browser remembers your name for a year, so next
time you go straight in. If you close the tab or lose your connection, you get your seat back
when you return, with your card still chosen.

### Voting

The top of the room shows the ticket being estimated: its key (a link to Jira), type,
priority, epic, labels and description. Choose **Show more** to read a long description.

1. Pick a card under **Your card**. You can change your mind until the cards are revealed.
2. Choose **?** when you can't estimate the ticket. It doesn't count towards the average.

Until the reveal, everyone sees only *that* you voted, never what. The table shows each person
as **Thinking**, **Voted** or **Away**, and how many have voted, such as "3 of 5 voted".

### The reveal

When the facilitator reveals, every card turns face up on every screen, with three figures:

- **Average**, to one decimal
- **Median**, the middle value
- **Consensus**, when everyone picked the same card; otherwise the most-chosen card and how
  many picked it, such as "Most chosen: 5 (3 of 5)"

Cards without a number, such as **?**, are left out of all three. T-shirt sizes count by the
points they stand for.

Under the figures, bars show how many people chose each card. When the numbers differ, the
players who chose the highest and lowest cards are marked **Highest** and **Lowest**: hearing
from them first is usually the quickest way to agree.

Voting stays closed until the facilitator restarts the vote or moves to the next ticket.

### The countdown

A facilitator can start a countdown. It shows next to the voted count, and is the same on
every screen. When it reaches zero it shows **Time's up**: that's a nudge, not a reveal, so you
can still vote until the facilitator reveals.

If the room has sound on, you hear soft ticks for the last five seconds and a chime at zero.
Choose **Mute** in the header to silence it on your screen only.

### Sitting out

If you're there to listen rather than estimate, choose **Sit out** under your cards. You leave
the table, your card is dropped, and the voted count stops waiting for you, but you still see
everything. The table lists you under "Watching". Choose **Join the table** to vote again.

### Mini mode

**Mini mode** in the header opens a small window with the ticket key, the countdown, your cards
and the voted count, so you can vote while you share your screen or read the ticket in Jira.

- In Chrome, Edge and Firefox it floats above your other windows.
- In Safari it opens as an ordinary small window that doesn't stay on top.

Keep the main room tab open: the mini window works through it, and closes when you close
the room tab. Sound plays from the room tab.

### Messages you might see

| Message | What it means |
| --- | --- |
| Connecting… / Connection lost. Reconnecting… | Your connection dropped. The page reconnects by itself and you keep your seat. |
| The room was reset. Checking in… | A facilitator cleared out people who left. Wait a few seconds and you're seated again. |
| You are not seated in this round. | You didn't check in after a reset in time. Choose **Join again**. |
| A facilitator removed you from the table. | A facilitator tidied the table. If that was a mistake, choose **Join again**. |
| The owner deleted this room. | The room no longer exists. Ask your facilitator for a new link. |
| There is no room called … | The link is wrong, or the room was renamed or deleted. |

## Facilitators

You're a facilitator if you own the room, or the owner added you as a delegate. Sign in first:
open the app's home page, choose **Sign in with Google** or **Sign in with GitHub**, then open
the room. The header shows
your role, **Owner** or **Delegate**, under your name.

### Starting a session

1. Open the room. The first ticket without an estimate is already loaded, in backlog order.
   Epics and sub-tasks are left out; the tickets inside an epic still come up like any other.
2. Choose **Copy link** in the header and share it with the team.
3. Wait for everyone to appear on the table.

The header shows two counters: **Session**, the tickets and points estimated since this
session began, and **Backlog**, the same for the whole backlog.

### Running a round

| Control | What it does |
| --- | --- |
| **Start** / **Stop** | Starts or stops the countdown. **Seconds** sets its length for this session. |
| **Sound on** / **Sound off** | Turns the countdown sound on or off for everyone, for this session. |
| **Reveal cards** | Turns all cards face up and shows the average, median and consensus. |
| **Restart vote** | Clears everyone's cards and reopens voting on the same ticket. |
| **Final story points** | After the reveal, pick the points to record. It starts on the most-chosen card. |
| **Confirm** | Writes the chosen points to the ticket in Jira, then loads the next ticket. |
| **Skip** | Moves to the next ticket without writing anything. |
| **Rewind** | Goes back to the previous ticket, to look at it again or re-estimate it. |
| **Reset room** | Clears out people who left. See below. |
| **Auto-reveal when everyone has voted** | Turns the cards over by themselves once everyone at the table who is connected has voted. For this session; the owner sets the default. |
| **×** on a player's card | Removes that player from the table, for a duplicate or someone who left. They can join again. |
| **Up next** | The next five tickets. Choose one to go straight to it. |
| **Copy summary** / **Download CSV** | This session's tickets, points and vote counts. See below. |

A typical round: start the countdown, wait for the votes, choose **Reveal cards**, talk about
the highest and lowest cards, then **Confirm** the agreed points, or **Restart vote** for
another go.

Facilitators can **Sit out** too: you keep the facilitator panel but the round stops waiting
for your card.

### Confirming points

**Confirm** writes to Jira first, and the room moves on only once Jira has accepted the points.
If Jira refuses or can't be reached, the room stays on the ticket and shows why, so nothing is
lost. Try again, or skip the ticket.

Points are written through the room's Jira connection, so Jira's history shows the room
owner's account as the one who set them, whoever pressed **Confirm**.

### Skipping and rewinding

**Skip** leaves a ticket unestimated and moves on. **Rewind** goes back one ticket at a time:
the ticket shows "Skipped earlier." or "Estimated earlier at 5 points." Estimating it again
replaces the earlier points, and the session counter counts it only once.

When every ticket is done, the room says "All tickets in the queue are done." You can still
rewind.

Choosing a ticket in **Up next** goes straight to it. The ticket you leave keeps its result and
isn't marked skipped, and **Rewind** still steps back one ticket in queue order.

### Auto-reveal

With auto-reveal on, the cards turn over by themselves once everyone at the table who is
connected has voted. Players shown as **Away**, and anyone sitting out, don't hold it up. The
countdown still never reveals: it only says **Time's up**.

### Session summary

**Session summary** in the facilitator panel lists every ticket estimated or skipped this
session, with its points, the average and how many chose each card. It never lists who chose
what.

- **Copy summary** copies it as text, ready to paste into your sprint notes or chat.
- **Download CSV** saves it as a spreadsheet file.

The summary is never stored: it's gone when the session ends, so copy it before you leave.

### Resetting the room

Use **Reset room** when the table lists people who have left. Everyone still in the room
checks in automatically within a few seconds and keeps their seat; anyone who doesn't drops
off the table. The current ticket, the session counters and your place in the queue don't
change, and voting on the current ticket starts again.

### When the session ends

A session ends once nobody has been in the room for 15 minutes. The next time someone opens
it, the backlog loads fresh from Jira and the session counters start at zero. Points you
confirmed are already in Jira, so the queue picks up after them.

A short drop-out or a page reload doesn't end the session.

### When the backlog doesn't load

The room says "The backlog did not load" and why. Most causes are fixed by the owner in the
room's settings:

| Message | Fix |
| --- | --- |
| The room's owner needs to connect Jira in the room settings. | The owner connects Jira. |
| The room's owner needs to choose a Jira board in the room settings. | The owner picks a board. |
| Jira no longer accepts this room's connection. … | The owner chooses **Reconnect**. This happens after 90 days without use, or if access was revoked in Atlassian. |
| Jira cannot find the room's board. … | The board was deleted or the owner lost access. The owner picks another board. |
| Could not reach Jira. Try again. | A network or Jira problem. Choose **Try again**. |

Once it's fixed, choose **Try again** in the room.

## Room owners

### Creating a room

1. Open the app's home page and choose **Sign in with Google** or **Sign in with GitHub**.
2. Under **Create a room**, type a **Short name**: lowercase letters, digits and hyphens, such
   as `team-a`. It becomes the room's link, `/r/team-a`.
3. Choose **Create room**. The room's settings open.

If the page says your account "cannot create rooms", ask your administrator to add you. You
can still run sessions in rooms where you are a delegate.

**Your rooms** on the home page lists every room you own or help run.

### Connecting Jira

Each room has one Jira connection, set up by its owner. The room reads its backlog and writes
every confirmed estimate through it.

1. In the room's settings, under **Jira Cloud**, choose **Connect Jira**.
2. Atlassian asks you to allow access. Choose your Jira site and accept.
3. Back in the settings, pick the **Site** and the **Board**, then **Save changes**.

The settings show "Connected as" with your Atlassian email. Use **Reconnect** if the room
loses access, and **Disconnect** to remove the connection; sessions can't load a backlog until
you connect again.

The queue is the board's backlog: tickets with no estimate yet, in the backlog's order, which
you can rearrange in Jira as usual. Changing the board during a session reloads the queue.

If several rooms should use Jira, connect each of them. They can use different sites or
Atlassian accounts.

### Settings

The settings page, **Settings** in the room header, is only for the owner. Choose
**Save changes** after changing anything.

| Section | Settings |
| --- | --- |
| **Room link** | The room's **Short name**. Renaming keeps the old link working: it redirects to the new one, and no other room can take the old name. |
| **Jira Cloud** | The connection, site and board. See above. |
| **Scale** | The cards players vote with: **Fibonacci** (1, 2, 3, 5, 8, 13, 21, ?), **T-shirt** (XS to XXL, with the points each size confirms as, XS=1 to XXL=13) or a **Custom list** of your own cards, separated by commas. |
| **Countdown, sound and reveal** | **Default seconds** for the countdown, whether the countdown sound plays, and whether cards reveal by themselves once everyone has voted. Facilitators can change these for a running session; these are the defaults. |
| **Delegates** | People who can run sessions in this room. |
| **Delete room** | Removes the room for good. Everyone in it sees that it was deleted. |

About scales:

- A **?** card is always added to T-shirt sizes. Custom cards that are numbers count by that
  number; other custom cards, such as `?` or `coffee`, are left out of the figures and can't
  be confirmed.
- A scale has at most 30 cards, each up to 10 characters.
- A new scale applies at once if nobody has voted yet, otherwise from the next round.

### Delegates

Delegates run sessions with you: they get the facilitator panel but can't change settings,
connect Jira or delete the room.

1. Under **Delegates**, type their **Google email or GitHub username**.
2. Under **Signs in with**, choose **Google** or **GitHub**.
3. Choose **Add delegate**, then **Save changes**.

They are recognised by their verified Google email or their GitHub username, never by display
name. A Google entry only matches a Google sign-in, and a GitHub entry only a GitHub sign-in.

### What is kept

The room, its settings, delegates and Jira connection are saved. Votes, results and session
counters are not: they exist only while the session runs. The points you confirm are in Jira.
