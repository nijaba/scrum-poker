---
paths:
  - "frontend/**"
---

# Front-end rules

- The screens to build are in `docs/mockups/`: `room-voting.html`, `room-revealed.html`, `room-settings.html`, `mini-window.html`. Match their layout, colours and type; `docs/mockups/README.md` lists the tokens.
- The client never decides game state. It renders the snapshot the server sends and sends commands back.
- The countdown renders from the server's deadline, corrected for clock offset.
- Sound is synthesized with the Web Audio API: ticks for the last five seconds, a chime at zero. No audio files. Honour the room's sound setting and the player's local mute.
- Use real `<button>`, `<a>`, `<input>` and `<label>` elements. Hit targets are at least 44 px. Text contrast is at least 4.5:1.
- The room screens are fluid: the facilitator panel stacks under the main column on narrow windows.
- Mini mode uses the Document Picture-in-Picture API when `window.documentPictureInPicture` exists, and a small popup otherwise. Both render the same compact view.
