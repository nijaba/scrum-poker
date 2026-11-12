"""Errors the room engine raises when a command is not allowed."""


class CommandError(Exception):
    """A command was rejected. `code` is stable and goes to the client."""

    def __init__(self, code: str, message: str = "") -> None:
        super().__init__(message or code)
        self.code = code
        self.message = message or code
