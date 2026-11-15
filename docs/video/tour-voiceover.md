# Room tour video: voice-over script

For [`tour.mp4`](../../frontend/public/tour.mp4), the narrated video (online at <https://poker.nijalabs.com/tour.mp4>), and [`tour.webm`](tour.webm), the silent
recording it is made from: 30 seconds, 1280 × 720. It follows the room's
guided tour as a facilitator (and room owner) sees it, while four teammates vote and the cards
are revealed. Everything on screen comes from the app's fakes: made-up people and tickets.

`scripts/tour_video.py` records the silent video again after a screen changes, and prints the
time each step starts. Keep the cues below in line with those times. `scripts/tour_voiceover.py`
then speaks each line of the table below at its cue, in Kokoro's open-source neural voice
`af_heart`, and makes `frontend/public/tour.mp4`; its docstring says how to set Kokoro up. A voice actor can
read the same lines to the same cues instead.

**Pace:** about 2.5 words a second, calm and friendly. Each line fits inside its step with a
breath to spare; start each one on its cue rather than running lines together.

| Time | On screen | Voice-over |
| --- | --- | --- |
| 0:00.0 | The room opens; a note under the header offers the tour | New to scrum poker? Here is a quick tour. |
| 0:02.4 | **The ticket** outlined | Here's the ticket to estimate, from your Jira backlog. |
| 0:05.4 | **The table** outlined; three cards land face down | Your team sits here. Votes land face down. |
| 0:08.4 | **Your cards** outlined; a 5 is picked | Pick your card. You can change it until the reveal. |
| 0:11.5 | **The reveal** step; the last vote arrives | When everyone's in, the cards turn over together. |
| 0:14.5 | **Reveal cards** outlined in the facilitator controls | As facilitator, you decide when to reveal. |
| 0:17.1 | Cards turn over; **Final points and Confirm** outlined | Agree the points and confirm: they go straight to Jira. |
| 0:20.7 | **The countdown** outlined | A countdown keeps the voting moving. |
| 0:23.5 | **Up next and summary** outlined | See what's next, and copy the summary. |
| 0:26.3 | **Your menu** outlined | Theme and the tour live in your menu. |
| 0:28.4 | The last step, just before the tour closes | Happy estimating. |

## Whole script

New to scrum poker? Here is a quick tour.
Here's the ticket to estimate, from your Jira backlog.
Your team sits here. Votes land face down.
Pick your card. You can change it until the reveal.
When everyone's in, the cards turn over together.
As facilitator, you decide when to reveal.
Agree the points and confirm: they go straight to Jira.
A countdown keeps the voting moving.
See what's next, and copy the summary.
Theme and the tour live in your menu.
Happy estimating.

(About 80 words.)
