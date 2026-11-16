/** The steps of the room and settings tours (design.md, "Tour"). */
import type { Tour, TourStep } from "./tour.svelte";

type Who = {
  facilitator: boolean;
  owner: boolean; // the owner or a co-owner: they have Room settings
  phone: boolean;
  remote: boolean;
  demo?: boolean;
};

export function roomTour(who: Who): Tour {
  return { steps: firstPart(who), more: secondPart(who) };
}

function firstPart(who: Who): TourStep[] {
  const steps: TourStep[] = [
    {
      target: "ticket",
      title: "The ticket",
      text: "The team estimates one Jira ticket at a time, in backlog order. Its key, summary and description are here.",
    },
    {
      target: "table",
      title: "The table",
      text: "Everyone in the room. A card turns face down when someone votes; nobody sees its value until the reveal.",
    },
    {
      target: "hand",
      title: "Your cards",
      text: "Pick a card to vote, and change it as often as you like until the reveal. Coffee break asks for a pause; Sit out lets you watch a round.",
    },
    {
      target: "table",
      title: "The reveal",
      text: "When the cards turn over, the table shows every vote with the average, the median and the spread. If you played the highest or the lowest card, be ready to say why.",
    },
  ];
  if (who.facilitator) {
    steps.push(
      {
        target: "reveal",
        title: "Reveal cards",
        text: who.phone
          ? "Reveal cards turns everyone's cards over, even if someone has not voted yet. The count shows how many have."
          : "Reveal cards turns everyone's cards over, even if someone has not voted yet. Below it: Restart vote, Skip, Rewind, Reset room, and Auto-reveal to reveal on the last vote.",
      },
      {
        target: ["final", "reveal"], // the final points once revealed; until then, where they come
        title: "Final points and Confirm",
        text: "After the reveal, the final points appear here. Pick the points the team agreed and Confirm: they are written to Jira and the room moves to the next ticket.",
      },
    );
    if (who.phone) {
      steps.push({
        target: "more",
        title: "More controls",
        text: "The countdown, Restart vote, Skip, Rewind, Reset room, Auto-reveal, Up next and the session summary are in this sheet.",
      });
    } else {
      steps.push(
        {
          target: "countdown",
          title: "The countdown",
          text: "Start a countdown to keep the discussion moving. Time's up is only a signal: it never reveals the cards.",
        },
        {
          target: "summary",
          title: "Up next and summary",
          text: "Up next lists the coming tickets; pick one to jump to it. The session summary lists what was estimated and skipped, ready to copy.",
        },
      );
    }
  }
  const extras = [
    who.phone ? "Mute, the counters" : "",
    who.phone && !who.facilitator ? "Remote view, to vote from your phone while the room is on a shared screen" : "",
  ].filter(Boolean);
  steps.push({
    target: "menu",
    title: "Your menu",
    text:
      `Your menu holds ${extras.length ? extras.join(", ") + " and " : ""}the light or dark theme.` +
      (who.owner ? " You also find Room settings here: Jira, the queue filter, the scale and delegates." : "") +
      " Tour, here or in the footer, starts this tour again. Show me more explains the rest of the room.",
  });
  return steps;
}

/** What Show me more adds: the rest of the room, by role. */
function secondPart(who: Who): TourStep[] {
  const steps: TourStep[] = [];
  if (!who.phone) {
    steps.push({
      target: "counters",
      title: "The counters",
      text: "Session counts the tickets and points estimated since this session began. Backlog counts how many of the queue's tickets have an estimate, and their points. Re-estimating a ticket never counts it twice.",
    });
  }
  steps.push({
    target: "copy-link",
    title: "Copy link",
    text: "Copies the room's address. Anyone with it can join as a player by typing a name: no account, nothing to install.",
  });
  if (!who.phone) {
    steps.push({
      target: "mini",
      title: "Mini mode",
      text: "A small window with the ticket key, the countdown and your cards, so you can vote while you share your screen or read the ticket in Jira. In Chrome, Edge and Firefox it floats above other windows.",
    });
  }
  steps.push(
    {
      target: "table",
      title: "Who has voted",
      text: "Thinking: no card yet. Voted: a card is down, its value hidden. Away: the connection dropped, and the seat is kept for when they come back. A cup is a coffee break, which is not a vote. Anyone sitting out is listed under Watching.",
    },
    {
      target: "table",
      title: "Reading the reveal",
      text: "Consensus means everyone chose the same card; otherwise the room shows the most-chosen card and how many chose it. Highest and Lowest mark who to hear first. Cards like ? are left out of the figures, and a vote for the top card asks whether to split the ticket.",
    },
  );
  if (!who.facilitator) return steps;
  const where = who.phone ? "more" : undefined;
  steps.push(
    {
      target: where ?? "round",
      title: "Restart, Skip and Rewind",
      text: "Restart vote clears the cards for another go on the same ticket. Skip moves on without writing to Jira. Rewind goes back a ticket to look again or re-estimate it; the counters count it once.",
    },
    {
      target: where ?? "round",
      title: who.demo ? "Reset room" : "Reset room and Reload backlog",
      text:
        "Reset room clears out people who left: everyone still here checks in by themselves within a few seconds and keeps their seat." +
        (who.demo
          ? ""
          : " Reload backlog loads the queue from Jira again, between tickets: after reordering the backlog or changing the queue filter."),
    },
    {
      target: "table",
      title: "Removing a player",
      text: "The × on a player's seat takes them off the table, for a duplicate seat or someone who has left. They can join again.",
    },
    {
      target: where ?? "auto-reveal",
      title: "Auto-reveal and sound",
      text: "Auto-reveal turns the cards over once everyone connected has voted. Sound, by the countdown, plays its ticks and chime for everyone; each person can still mute. Both apply to this session; the room settings hold the defaults.",
    },
    {
      target: where ?? "summary",
      title: "The session summary",
      text: "Every ticket estimated or skipped this session, with its points, the average and how the votes fell, never who chose what. Copy it into your notes or download a CSV before you leave: it is not kept.",
    },
  );
  if (who.owner) {
    steps.push({
      target: "menu",
      title: "Room settings",
      text: "Room settings, in your menu, is where you connect Jira, choose which tickets come up, and set the scale, the defaults and the delegates. It has its own tour.",
    });
  }
  return steps;
}

export function settingsTour(who: { owner: boolean; checklist: boolean }): Tour {
  const steps: TourStep[] = [];
  if (who.checklist) {
    steps.push({
      target: "checklist",
      title: "Getting started",
      text: "The steps to get this room ready, in order. Each one ticks itself off once it is done, and its link takes you to the section below.",
    });
  }
  steps.push(
    {
      target: "room-link",
      title: "Room link",
      text: "Players join at this link, with no account. Change the short name to rename the room; the old link keeps working and no other room can take it.",
    },
    {
      target: "jira",
      title: "Jira",
      text: "Connect the room to Jira Cloud and pick the board. The backlog loads, and every confirmed estimate is written, through this connection, so Jira records the writes under the account that connected it. Its Jira account needs to be able to edit the board's estimates.",
    },
    {
      target: "queue-filter",
      title: "Queue filter",
      text: "Which backlog tickets come up: by default stories, tasks and bugs in To Do, unresolved and without an estimate. You can add sub-tasks, tickets in progress, resolved ones, or estimated ones to re-estimate, and narrow it with JQL. Preview queue shows the result before you save.",
    },
    {
      target: "scale",
      title: "Scale",
      text: "The cards players choose from. Fibonacci suits most teams. T-shirt sizes are for rough sizing; each size is written to Jira as the points you give it. A custom list takes your own cards.",
    },
    {
      target: "countdown",
      title: "Countdown, sound and reveal",
      text: "The defaults each session starts with: the countdown's length, whether it ticks and chimes, and whether the cards turn over once everyone has voted. Facilitators can change them for a session.",
    },
    {
      target: "delegates",
      title: "Delegates",
      text:
        "People who run sessions with you, matched on their Google email or GitHub username. A facilitator runs sessions; a co-owner can also change these settings and connect Jira. Only the owner deletes the room." +
        (who.owner
          ? " Make owner… offers the room to a delegate; once they accept, you stay on as a co-owner."
          : ""),
    },
  );
  return { steps };
}
