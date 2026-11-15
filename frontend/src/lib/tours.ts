/** The steps of the room and settings tours (design.md, "Tour"). */
import type { TourStep } from "./tour.svelte";

export function roomTour(who: {
  facilitator: boolean;
  owner: boolean;
  phone: boolean;
  remote: boolean;
}): TourStep[] {
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
      (who.owner ? " As the owner you also find Room settings here: Jira, the queue filter, the scale and delegates." : "") +
      " Tour, here or in the footer, starts this tour again.",
  });
  return steps;
}

export const settingsTour = (): TourStep[] => [
  {
    target: "room-link",
    title: "Room link",
    text: "Players join at this link. Change the short name to rename the room; the old link keeps working.",
  },
  {
    target: "jira",
    title: "Jira",
    text: "Connect the room to Jira Cloud and pick the board. The backlog loads, and points are written, through this connection.",
  },
  {
    target: "queue-filter",
    title: "Queue filter",
    text: "Which backlog tickets the room estimates: by default only unestimated tickets in To Do, with no epics or sub-tasks. The preview shows the queue it gives.",
  },
  {
    target: "scale",
    title: "Scale",
    text: "The cards players choose from.",
  },
  {
    target: "countdown",
    title: "Countdown, sound and reveal",
    text: "The countdown's length, whether it ticks and chimes, and whether the cards reveal when everyone has voted.",
  },
  {
    target: "delegates",
    title: "Delegates",
    text: "People who may run sessions in this room as facilitators. They sign in with Google or GitHub; only you change the settings.",
  },
];
