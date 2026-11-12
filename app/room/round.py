"""One round of voting on one ticket: voting -> revealed -> confirmed."""

from __future__ import annotations

from app.room.errors import CommandError
from app.room.results import Results, compute_results
from app.room.scales import Card, Scale

VOTING = "voting"
REVEALED = "revealed"
CONFIRMED = "confirmed"


class Round:
    def __init__(self, scale: Scale) -> None:
        self.scale = scale
        self.state = VOTING
        self.votes: dict[str, Card] = {}
        self.results: Results | None = None

    def vote(self, player_id: str, label: str) -> None:
        """Cast or change a vote. The latest card counts."""
        if self.state != VOTING:
            raise CommandError("voting_closed", "Voting is closed for this round.")
        card = self.scale.card(label) if isinstance(label, str) else None
        if card is None:
            raise CommandError("unknown_card", "That card is not on this room's scale.")
        self.votes[player_id] = card

    def withdraw(self, player_id: str) -> None:
        if self.state != VOTING:
            raise CommandError("voting_closed", "Voting is closed for this round.")
        self.votes.pop(player_id, None)

    def drop(self, player_id: str) -> None:
        """Forget a player's vote, for example after a reset."""
        if self.state == VOTING:
            self.votes.pop(player_id, None)

    def reveal(self) -> Results:
        if self.state != VOTING:
            raise CommandError("not_voting", "Only a round that is voting can be revealed.")
        self.state = REVEALED
        self.results = compute_results(self.votes.values(), self.scale.cards)
        return self.results

    def confirm(self) -> None:
        if self.state != REVEALED:
            raise CommandError("not_revealed", "Reveal the cards before confirming points.")
        self.state = CONFIRMED
